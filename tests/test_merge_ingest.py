"""Exercise the GitHub API importer against real local Git merge histories."""
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ingest_github as publisher
from site_post_metadata import metadata_view


def photo(color):
    stream = BytesIO()
    Image.new("RGB", (3, 2), color).save(stream, "PNG")
    return stream.getvalue()


class MergeImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Flux merge test")
        self.git("config", "user.email", "flux-test@example.invalid")
        (self.root / "seed").write_text("seed")
        self.base = self.commit("Initialize", "01:00:00")
        self.state_path = self.root / ".publishing/state.json"

    def git_bytes(self, *arguments, env=None, check=True):
        return subprocess.run(["git", "-C", str(self.root), *arguments],
                              capture_output=True, check=check, env=env)

    def git(self, *arguments, env=None):
        return self.git_bytes(*arguments, env=env).stdout.decode().strip()

    def stamp_env(self, time):
        return {**os.environ, "GIT_AUTHOR_DATE": "2026-11-03T" + time + "Z",
                "GIT_COMMITTER_DATE": "2026-11-03T" + time + "Z"}

    def commit(self, message, time):
        self.git("add", ".")
        self.git("commit", "-m", message, env=self.stamp_env(time))
        return self.git("rev-parse", "HEAD")

    def write(self, filename, data):
        path = self.root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def initialize_state(self, cursor=None):
        self.state_path.parent.mkdir(exist_ok=True)
        self.state_path.write_text(json.dumps({"version": 1, "sources": {
            "text": {"repository": "owner/flux", "path": "trigger_text.md",
                     "history_path": "", "cursor": cursor or self.base},
            "images": {"repository": "owner/flux", "path": "trigger_imgs",
                       "history_path": "", "identity": "commit-path",
                       "cursor": cursor or self.base},
        }}))

    def commit_record(self, sha):
        timestamp, message = self.git("show", "-s", "--format=%cI%x00%B", sha).split("\0", 1)
        return {"sha": sha, "commit": {"committer": {"date": timestamp}, "message": message},
                "parents": [{"sha": parent} for parent in self.git("show", "-s", "--format=%P", sha).split()]}

    def api(self, path):
        """Return API-shaped metadata derived from Git objects, without HTTP."""
        parsed = urlsplit("https://api.github.com/" + path)
        endpoint = parsed.path.removeprefix("/repos/owner/flux/")
        if endpoint == "git/ref/heads/main":
            return {"object": {"sha": self.git("rev-parse", "main")}}
        if endpoint.startswith("compare/"):
            base, head = endpoint.removeprefix("compare/").split("...", 1)
            rows = [self.commit_record(sha) for sha in self.git(
                "rev-list", "--reverse", "--topo-order", head, "^" + base).splitlines()]
            query = parse_qs(parsed.query)
            page = int(query.get("page", ["1"])[0])
            ancestor = self.git("merge-base", base, head)
            return {"status": "identical" if base == head else "ahead" if ancestor == base else "diverged",
                    "merge_base_commit": {"sha": ancestor}, "total_commits": len(rows),
                    "commits": rows[(page - 1) * 100:page * 100]}
        if endpoint == "commits":
            query = parse_qs(parsed.query)
            rows = [self.commit_record(sha) for sha in self.git(
                "log", "--date-order", "--format=%H", query["sha"][0]).splitlines()]
            page = int(query.get("page", ["1"])[0])
            return rows[(page - 1) * 100:page * 100]
        if endpoint.startswith("commits/"):
            sha = endpoint.split("/")[1]
            record = self.commit_record(sha)
            parent = record["parents"][0]["sha"]
            changes = self.git_bytes("diff", "--name-status", "-z", "--no-renames", parent, sha).stdout.split(b"\0")
            files = []
            for index in range(0, len(changes) - 1, 2):
                status, filename = changes[index].decode(), changes[index + 1].decode()
                revision = parent if status == "D" else sha
                files.append({"filename": filename,
                              "status": {"A": "added", "D": "removed", "M": "modified", "T": "changed"}[status],
                              "sha": self.git("rev-parse", revision + ":" + filename)})
            return {**record, "files": files}
        if endpoint.startswith("git/commits/"):
            sha = endpoint.split("/")[2]
            return {"tree": {"sha": self.git("rev-parse", sha + "^{tree}")},
                    "parents": self.commit_record(sha)["parents"]}
        if endpoint.startswith("git/trees/"):
            sha = endpoint.split("/")[2]
            entries = []
            for row in self.git_bytes("ls-tree", "-z", sha).stdout.split(b"\0"):
                if row:
                    metadata, filename = row.split(b"\t", 1)
                    mode, kind, blob = metadata.decode().split()
                    entries.append({"path": filename.decode(), "mode": mode, "type": kind, "sha": blob})
            return {"tree": entries, "truncated": False}
        self.fail("Unexpected API path: " + path)

    def download(self, url):
        path = unquote(urlsplit(url).path).removeprefix("/owner/flux/")
        sha, filename = path.split("/", 1)
        return self.git_bytes("show", sha + ":" + filename).stdout

    def ingest(self):
        pending, files, selected = publisher.pending_commits, publisher.commit_files, publisher.publication_files
        owners = publisher.update_image_owners
        text, images = publisher.import_text, publisher.import_images
        with patch.object(publisher, "ROOT", self.root), patch.object(publisher, "STATE", self.state_path), \
             patch.object(publisher, "pending_commits", side_effect=lambda source, **options: pending(source, read=self.api, **options)), \
             patch.object(publisher, "commit_files", side_effect=lambda repository, sha: files(repository, sha, read=self.api)), \
             patch.object(publisher, "publication_files", side_effect=lambda source, commit, rows, **options: selected(source, commit, rows, read=self.api, **options)), \
             patch.object(publisher, "update_image_owners", side_effect=lambda *args, **options: owners(*args, read=self.api, **options)), \
             patch.object(publisher, "import_text", side_effect=lambda *args, **options: text(*args, read=self.download, **options)), \
             patch.object(publisher, "import_images", side_effect=lambda *args, **options: images(*args, read=self.download, **options)):
            publisher.main()

    def posts(self):
        return [metadata_view(publisher.split_frontmatter(path.read_text())[0])
                for path in (self.root / "flux").glob("**/index.md")]

    def test_parent_uploads_are_not_republished_by_the_merge_or_retry(self):
        self.git("checkout", "-b", "phone")
        filename = "trigger_imgs/山间/相片 #1.png"
        self.write(filename, photo("red"))
        self.write("trigger_text.md", "一则文字".encode())
        upload = self.commit("Upload image and text", "03:00:00")
        self.git("checkout", "main")
        self.write("unrelated.txt", b"main edit")
        cursor = self.commit("Update elsewhere", "02:00:00")
        self.git("merge", "--no-ff", "phone", "-m", "Merge phone", env=self.stamp_env("04:00:00"))
        merge = self.git("rev-parse", "HEAD")
        self.initialize_state(cursor)
        self.ingest()
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual({post["source_commit"] for post in posts}, {upload})
        state = json.loads(self.state_path.read_text())
        for source in state["sources"].values():
            self.assertEqual(source["cursor"], merge)
            self.assertEqual(source["verification_commits"], [upload])
        self.assertEqual(state["sources"]["images"]["latest_uploads"], {filename: upload})
        saved = next((self.root / "flux").glob("**/index.md"))
        saved.write_text(saved.read_text().replace("status: published", "status: hidden") + "\nEdited caption.\n")
        edited = saved.read_bytes()
        self.ingest()
        self.assertEqual(len(self.posts()), 2)
        self.assertEqual(saved.read_bytes(), edited)

    def retained_main_owner(self, branch_color, hidden=False, strategy="ours"):
        self.git("checkout", "-b", "phone")
        self.write("trigger_imgs/photo.png", photo(branch_color))
        upload = self.commit("Offline phone upload", "03:00:00")
        self.git("checkout", "main")
        self.write("trigger_imgs/photo.png", photo("red"))
        main_upload = self.commit("Main photo", "04:00:00")
        self.initialize_state()
        self.ingest()
        if hidden:
            saved = next((self.root / "flux").glob("**/index.md"))
            saved.write_text(saved.read_text().replace("status: published", "status: hidden"))
        self.commit("Save published main photo", "04:30:00")
        self.git("merge", "--no-ff", "-X", strategy, "phone", "-m", "Choose the retained photo",
                 env=self.stamp_env("05:00:00"))
        merge = self.git("rev-parse", "HEAD")
        owner = upload if strategy == "theirs" else main_upload
        retained = branch_color if strategy == "theirs" else "red"
        for attempt in range(3):
            self.ingest()
            state = json.loads(self.state_path.read_text())
            source = state["sources"]["images"]
            self.assertEqual(source["cursor"], merge)
            self.assertEqual(source["verification_commits"], [upload])
            self.assertEqual(source["latest_uploads"], {"trigger_imgs/photo.png": owner})
            self.assertEqual(len(self.posts()), 2)
            self.assertEqual((self.root / "trigger_imgs/photo.png").read_bytes(), photo(retained))
        from image_inbox import candidates
        matches = candidates(self.root)
        if hidden and strategy == "ours":
            self.assertEqual(matches, [])
        else:
            self.assertEqual(len(matches), 1)
            archive = self.root / matches[0][1]
            meta, _ = publisher.split_frontmatter((archive.parent.parent / "index.md").read_text())
            self.assertEqual(metadata_view(meta)["source_commit"], owner)

    def test_merge_retaining_main_owner_keeps_cursor_and_retries_stable(self):
        self.retained_main_owner("blue")

    def test_equal_byte_branch_upload_cannot_replace_a_hidden_main_owner(self):
        self.retained_main_owner("red", hidden=True)

    def test_merge_retaining_phone_owner_keeps_cursor_and_retries_stable(self):
        self.retained_main_owner("blue", strategy="theirs")

    def test_merge_restoring_an_already_saved_parent_updates_owner_without_a_new_post(self):
        self.write("trigger_imgs/photo.png", photo("blue"))
        blue = self.commit("First saved photo", "02:00:00")
        self.initialize_state()
        self.ingest()
        self.commit("Save blue package", "02:30:00")
        self.git("checkout", "-b", "phone")
        self.write("unrelated.txt", b"phone edit")
        self.commit("Phone work", "03:00:00")
        self.git("checkout", "main")
        self.write("trigger_imgs/photo.png", photo("red"))
        red = self.commit("Replace the photo", "04:00:00")
        self.ingest()
        self.commit("Save red package", "04:30:00")
        self.git("merge", "--no-ff", "--no-commit", "phone")
        self.write("trigger_imgs/photo.png", photo("blue"))
        merge = self.commit("Retain the older parent photo", "05:00:00")
        for _ in range(3):
            self.ingest()
            source = json.loads(self.state_path.read_text())["sources"]["images"]
            self.assertEqual(source["cursor"], merge)
            self.assertEqual(source["latest_uploads"], {"trigger_imgs/photo.png": blue})
            self.assertEqual(source["verification_commits"], [red])
            self.assertEqual(len(self.posts()), 2)
        from image_inbox import candidates
        matches = candidates(self.root)
        self.assertEqual(len(matches), 1)
        archive = self.root / matches[0][1]
        meta, _ = publisher.split_frontmatter((archive.parent.parent / "index.md").read_text())
        self.assertEqual(metadata_view(meta)["source_commit"], blue)

    def test_newly_merged_upload_older_than_the_cursor_is_not_lost(self):
        self.git("checkout", "-b", "phone")
        self.write("trigger_imgs/phone.png", photo("blue"))
        self.write("trigger_text.md", b"old phone text")
        upload = self.commit("Offline phone upload", "01:30:00")
        self.git("checkout", "main")
        self.write("trigger_imgs/main.png", photo("red"))
        cursor = self.commit("Already processed main upload", "02:00:00")
        self.git("merge", "--no-ff", "phone", "-m", "Merge old phone work", env=self.stamp_env("04:00:00"))
        merge = self.git("rev-parse", "HEAD")
        self.initialize_state(cursor)
        self.ingest()
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual({post["source_commit"] for post in posts}, {upload})
        self.assertEqual({post["source"] for post in posts}, {"github-trigger", "github-image"})
        for source in json.loads(self.state_path.read_text())["sources"].values():
            self.assertEqual(source["cursor"], merge)
            self.assertEqual(source["verification_commits"], [upload])

    def test_new_merge_resolutions_publish_with_the_merge_identity(self):
        self.write("trigger_imgs/photo.png", photo("black"))
        self.write("trigger_text.md", b"base text")
        base = self.commit("Initial triggers", "01:10:00")
        self.git("checkout", "-b", "phone")
        self.write("trigger_imgs/photo.png", photo("blue"))
        self.write("trigger_text.md", b"phone text")
        phone_commit = self.commit("Phone upload", "03:00:00")
        self.git("checkout", "main")
        self.write("trigger_imgs/photo.png", photo("red"))
        self.write("trigger_text.md", b"main text")
        main_commit = self.commit("Main upload", "02:00:00")
        result = self.git_bytes("merge", "--no-ff", "phone", "-m", "Merge phone", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.write("trigger_imgs/photo.png", photo("green"))
        self.write("trigger_text.md", b"resolved text")
        merge = self.commit("Resolve both uploads", "04:00:00")
        self.initialize_state(base)
        self.ingest()
        posts = self.posts()
        self.assertEqual(len(posts), 6)
        self.assertEqual({post["source_commit"] for post in posts}, {phone_commit, main_commit, merge})
        merge_posts = [post for post in posts if post["source_commit"] == merge]
        self.assertEqual({post["source"] for post in merge_posts}, {"github-trigger", "github-image"})

    def test_new_merge_path_is_an_upload_even_when_its_bytes_match_a_parent(self):
        self.git("checkout", "-b", "phone")
        self.write("trigger_imgs/old.png", photo("red"))
        upload = self.commit("Upload photo", "03:00:00")
        self.git("checkout", "main")
        self.write("unrelated.txt", b"main edit")
        cursor = self.commit("Update elsewhere", "02:00:00")
        self.git("merge", "--no-ff", "--no-commit", "phone")
        self.git("mv", "trigger_imgs/old.png", "trigger_imgs/new.png")
        merge = self.commit("Rename while merging", "04:00:00")
        self.initialize_state(cursor)
        self.ingest()
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual({post["source_commit"] for post in posts}, {upload, merge})
        self.assertEqual({post["source_asset_path"] for post in posts}, {"trigger_imgs/old.png", "trigger_imgs/new.png"})

    def test_independent_identical_reupload_still_creates_a_new_post(self):
        self.write("trigger_imgs/photo.png", photo("red"))
        first = self.commit("First upload", "02:00:00")
        (self.root / "trigger_imgs/photo.png").unlink()
        self.commit("Clear earlier upload", "03:00:00")
        self.write("trigger_imgs/photo.png", photo("red"))
        second = self.commit("Upload the same photo again", "04:00:00")
        self.initialize_state()
        self.ingest()
        posts = self.posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual({post["source_commit"] for post in posts}, {first, second})

    def test_inherited_merge_cannot_hide_a_damaged_pending_upload(self):
        self.git("checkout", "-b", "phone")
        self.write("trigger_imgs/bad.png", b"damaged")
        self.commit("Damaged phone upload", "03:00:00")
        self.git("checkout", "main")
        self.write("unrelated.txt", b"main edit")
        cursor = self.commit("Update elsewhere", "02:00:00")
        self.git("merge", "--no-ff", "phone", "-m", "Merge phone", env=self.stamp_env("04:00:00"))
        self.initialize_state(cursor)
        state_before = self.state_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "damaged"):
            self.ingest()
        self.assertEqual(self.state_path.read_bytes(), state_before)
        self.assertEqual(self.posts(), [])

    def test_same_blob_with_a_new_file_mode_is_not_treated_as_inheritance(self):
        self.git("checkout", "-b", "phone")
        (self.root / "trigger_text.md").symlink_to("seed")
        self.commit("Phone trigger symlink", "03:00:00")
        self.git("checkout", "main")
        self.write("unrelated.txt", b"main edit")
        self.commit("Update elsewhere", "02:00:00")
        self.git("merge", "--no-ff", "--no-commit", "phone")
        (self.root / "trigger_text.md").unlink()
        self.write("trigger_text.md", b"seed")
        merge = self.commit("Make the trigger a regular file", "04:00:00")
        record = self.commit_record(merge)
        files = publisher.commit_files("owner/flux", merge, read=self.api)
        selected = publisher.publication_files({"repository": "owner/flux", "path": "trigger_text.md"}, record, files, read=self.api)
        self.assertTrue(any(item["filename"] == "trigger_text.md" for item in selected))


if __name__ == "__main__":
    unittest.main()
