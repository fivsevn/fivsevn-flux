#!/usr/bin/env python3
"""Import committed trigger snapshots and trigger_imgs/ images from this repository.

Each source has a durable commit cursor. Process every intervening commit oldest
first, and use stable source identities so retries never duplicate or overwrite
an edited flux entry. No cross-repository secrets are needed. Verified inbox originals are cleared
only after deployment by image_inbox.py.
"""
from __future__ import annotations

import json
import hashlib
from io import BytesIO
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from site_post_metadata import CORE_FIELDS, dump_frontmatter, metadata_view, normalize_metadata, read_frontmatter, validate_metadata

register_heif_opener(thumbnails=False)

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".publishing/state.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}


def fetch(url: str) -> bytes:
    headers = {"User-Agent": "fivsevn-flux-publisher/2"}
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"
        if os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return response.read()


def api(path: str):
    return json.loads(fetch("https://api.github.com/" + path))


def split_frontmatter(text: str):
    meta, body = read_frontmatter(text)
    return meta, body.strip()


def pending_commits(source: dict, read=api) -> list[dict]:
    """Never silently replay history if a cursor disappeared after a force push."""
    pending = []
    for page in range(1, 101):
        parameters = {"sha": "main", "per_page": 100, "page": page}
        history_path = source.get("history_path", source["path"])
        if history_path:
            parameters["path"] = history_path
        query = urlencode(parameters)
        commits = read(f"repos/{source['repository']}/commits?{query}")
        if not isinstance(commits, list):
            raise ValueError("Unexpected commit listing")
        for commit in commits:
            if commit["sha"] == source["cursor"]:
                return list(reversed(pending))
            pending.append(commit)
        if len(commits) < 100:
            break
    raise ValueError(f"Source cursor missing for {source['repository']}; review history before importing")


def commit_files(repository: str, sha: str, read=api) -> list[dict]:
    files = []
    for page in range(1, 31):
        response = read(f"repos/{repository}/commits/{sha}?per_page=100&page={page}")
        batch = response.get("files", [])
        files.extend(batch)
        if len(batch) < 100:
            return files
    raise ValueError("Commit file listing exceeded API pagination limit")


def source_date(commit: dict) -> datetime:
    return datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Shanghai"))


def existing_keys(root: Path) -> set[str]:
    keys = set()
    for path in (root / "flux").glob("**/index.md"):
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        meta = metadata_view(meta)
        for field in ("source_key", "wp_slug", "publish_slug"):
            if meta.get(field):
                keys.add(str(meta[field]))
    return keys


def save_package(root: Path, date: datetime, suffix: str, meta: dict, body: str, media: tuple[str, bytes] | None = None):
    ident = date.strftime("%Y-%m-%d-%H%M%S") + "-" + suffix
    parent = root / "flux" / date.strftime("%Y/%m")
    target = parent / ident
    if target.exists():
        raise ValueError(f"Package path collision: {ident}")
    parent.mkdir(parents=True, exist_ok=True)
    fields = {"id": ident, "date": date.isoformat(timespec="seconds"),
              "title": f"{date.day} {date.strftime('%b, %Y %H:%M')}",
              "sync": "manual", **meta}
    fields = normalize_metadata(fields, site="flux", post_id=ident,
                                published_at=date.isoformat(timespec="seconds"))
    validate_metadata(fields, site="flux")
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=parent) as staging:
        staging = Path(staging)
        if media:
            (staging / "assets").mkdir()
            (staging / "assets" / media[0]).write_bytes(media[1])
        (staging / "index.md").write_text(dump_frontmatter(fields) + "\n" + body.strip() + "\n", encoding="utf-8")
        staging.rename(target)
    return target


def import_text(root: Path, source: dict, commit: dict, keys: set[str], read=fetch) -> bool:
    sha = commit["sha"]
    data = read(f"https://raw.githubusercontent.com/{source['repository']}/{sha}/{quote(source['path'])}").decode("utf-8-sig")
    meta, body = split_frontmatter(data)
    if not body.strip():
        return False
    status = str(meta.get("status") or meta.get("wp_status") or "published")
    if status not in {"published", "publish", "active", "draft", "hidden", "pending", "private"}:
        raise ValueError("Use published, draft, hidden, or private; scheduled publication is not supported")
    visibility = str(meta.get("visibility") or ("private" if status == "private" else "public"))
    if visibility not in {"public", "private", "internal"}:
        raise ValueError("Unknown content visibility")
    title = meta.get("title")
    if title is not None and not isinstance(title, str):
        raise ValueError('title must be text; use title: "" for the default time title')
    title = (title or "").strip()
    slug = str(meta.get("slug") or f"github-text-{sha[:7]}")
    key = f"github:{source['repository']}:{sha}"
    if key in keys or slug in keys:
        return False
    controls = {key: value for key, value in meta.items()
                if key in CORE_FIELDS and key not in {"id", "extra", "legacy"}}
    save_package(root, source_date(commit), sha[:12], {
        **controls,
        "source": "github-trigger", "source_key": key, "source_commit": sha,
        "source_repository": source["repository"], "publish_slug": slug,
        "status": "draft" if status == "pending" else status,
        "visibility": visibility,
        **({"title": title} if title else {}),
    }, body)
    keys.update((key, slug))
    return True


def asset_slug(path: str) -> str:
    return "asset-" + path.lower().replace("/", "-").replace("_", "-").replace(".", "-")


def convert_image(media: bytes, path: str) -> bytes:
    """Keep WebP uploads; encode photos at quality 85, graphics losslessly.

    GIF/APNG frames are composited by Pillow before WebP encoding. MPO/HEIF
    auxiliary images (for example HDR gain maps) are not animation frames.
    Original uploads remain recoverable from their immutable Git commits.
    """
    if not media:
        raise ValueError(f"Empty image: {path}")
    try:
        with Image.open(BytesIO(media)) as image:
            fmt = image.format
            if fmt not in {"JPEG", "MPO", "PNG", "WEBP", "GIF", "HEIF"}:
                raise ValueError(f"Unsupported image format in {path}")
            if fmt == "WEBP":
                for n in range(image.n_frames):
                    image.seek(n)
                    image.load()
                return media
            animated = fmt in {"GIF", "PNG"} and getattr(image, "is_animated", False)
            # For lossless WebP, quality controls encoder effort, not pixels.
            # Maximum effort makes ordinary multi-frame phone GIFs very slow.
            options = {"method": 4 if fmt in {"PNG", "GIF"} else 6,
                       "lossless": fmt in {"PNG", "GIF"},
                       "quality": 75 if fmt in {"PNG", "GIF"} else 85}
            if image.info.get("icc_profile"):
                options["icc_profile"] = image.info["icc_profile"]
            if animated:
                frames, durations = [], []
                loop = image.info.get("loop")
                options["loop"] = (0 if loop == 0 else (loop + 1 if loop is not None else 1)) if fmt == "GIF" else (loop or 0)
                start = 1 if image.info.get("default_image") else 0
                for n in range(start, image.n_frames):
                    image.seek(n)
                    frames.append(image.convert("RGBA"))
                    durations.append(image.info.get("duration", 100) or 100)
                options.update(save_all=True, append_images=frames[1:], duration=durations,
                               minimize_size=False)
                primary = frames[0]
            else:
                primary = ImageOps.exif_transpose(image)
                exif = primary.getexif()
                if exif:
                    options["exif"] = exif.tobytes()
                primary = primary.convert("RGBA" if "A" in primary.getbands() or "transparency" in primary.info else "RGB")
            output = BytesIO()
            primary.save(output, format="WEBP", **options)
            result = output.getvalue()
        # Decode the result before making an entry durable.
        with Image.open(BytesIO(result)) as check:
            for n in range(check.n_frames):
                check.seek(n)
                check.load()
        return result
    except (OSError, SyntaxError, EOFError) as error:
        raise ValueError(f"Invalid or damaged image: {path}") from error


def import_images(root: Path, source: dict, commit: dict, keys: set[str], files: list[dict], read=fetch, superseded: set[str] = frozenset()) -> int:
    count = 0
    sha = commit["sha"]
    # Match the existing shortcut: the extended commit description is the caption.
    caption = commit["commit"]["message"].partition("\n")[2].strip()
    identity = source.get("identity", "legacy-path")
    if identity not in {"legacy-path", "commit-path"}:
        raise ValueError(f"Unknown image identity policy: {identity}")
    date = source_date(commit)
    # Sort the committed paths, so retry/API ordering cannot renumber a batch.
    uploads = sorted((item for item in files
                      if item["status"] != "removed"
                      and item["filename"].startswith(source["path"].rstrip("/") + "/")
                      and ".." not in PurePosixPath(item["filename"]).parts
                      and PurePosixPath(item["filename"]).name not in {"README.md", ".keep", ".gitkeep"}),
                     key=lambda item: item["filename"])
    for number, item in enumerate(uploads, start=1):
        path = item["filename"]
        parts = PurePosixPath(path)
        if item["status"] == "removed" or not path.startswith(source["path"].rstrip("/") + "/") or ".." in parts.parts:
            continue
        if parts.name in {"README.md", ".keep", ".gitkeep"}:
            continue
        if parts.suffix.lower() not in EXTENSIONS:
            if path in superseded:
                print(f"Skipped a replaced or removed unsupported upload: {path}")
                continue
            raise ValueError(f"Unsupported upload: {path}; use JPG/JPEG, PNG, WebP, GIF or HEIC/HEIF.")
        if identity == "commit-path":
            key = f"asset-event:{source['repository']}:{sha}:{path}"
            slug = f"github-image-{sha[:12]}-{hashlib.sha256(path.encode()).hexdigest()[:12]}"
            aliases = {key, slug}
        else:
            key = f"asset:{source['repository']}:{path}"
            slug = asset_slug(path)
            aliases = {key, slug}
            # Historical WordPress slugs are stable identities, not current URLs.
            # A directory rename must not republish the same image.
            for prefix in source.get("previous_paths", []):
                old_path = prefix.rstrip("/") + "/" + path[len(source["path"].rstrip("/")) + 1:]
                aliases.update((f"asset:{source['repository']}:{old_path}", asset_slug(old_path)))
            for previous in source.get("previous_sources", []):
                old_path = previous['path'].rstrip('/') + '/' + path[len(source['path'].rstrip('/')) + 1:]
                aliases.update((f"asset:{previous['repository']}:{old_path}", asset_slug(old_path)))
        if aliases & keys:
            continue
        media = read(f"https://raw.githubusercontent.com/{source['repository']}/{sha}/{quote(path)}")
        try:
            converted = convert_image(media, path)
        except ValueError:
            if path not in superseded:
                raise
            print(f"Skipped a replaced or removed invalid upload: {path}")
            continue
        suffix = hashlib.sha256((sha + ":" + path if identity == "commit-path" else path).encode()).hexdigest()[:12]
        filename = date.strftime("%Y%m%d-%H%M%S") + f"-{number:02d}.webp" if identity == "commit-path" else "image.webp"
        body = f"![](assets/{filename})"
        if caption:
            body += "\n\n" + caption
        save_package(root, date, suffix, {
            "source": "github-image", "source_key": key, "source_commit": sha,
            "source_repository": source["repository"], "source_asset_path": path,
            "publish_slug": slug, "status": "published",
            "upload": {"path": path, "uploaded_at": date.isoformat(timespec="seconds"),
                       "sha256": hashlib.sha256(media).hexdigest(),
                       "file": "assets/" + filename, "file_sha256": hashlib.sha256(converted).hexdigest()},
        }, body, (filename, converted))
        # A later event owns a reused inbox path, even if its saved post is hidden.
        # Persist this with the post and cursor; archive deletion must not restore
        # an older post's claim over a newer original with identical bytes.
        source.setdefault("latest_uploads", {})[path] = sha
        keys.update((key, slug))
        count += 1
    return count


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    keys = existing_keys(ROOT)
    total = 0
    for kind, source in state["sources"].items():
        commits = pending_commits(source)
        consumed = []
        batches = [(commit, commit_files(source["repository"], commit["sha"])) for commit in commits]
        last_change = {}
        for index, (_, files) in enumerate(batches):
            for item in files:
                last_change[item["filename"]] = index
                if item.get("previous_filename"):
                    last_change[item["previous_filename"]] = index
        for index, (commit, files) in enumerate(batches):
            if kind == "text":
                if not any(item["filename"] == source["path"] and item["status"] != "removed" for item in files):
                    continue
                total += import_text(ROOT, source, commit, keys)
            else:
                # Bot cleanup deletions and build commits are not new input.
                if not any(item["filename"].startswith(source["path"] + "/")
                           and item["status"] != "removed" for item in files):
                    continue
                superseded = {item["filename"] for item in files if last_change[item["filename"]] > index}
                total += import_images(ROOT, source, commit, keys, files, superseded=superseded)
            source["cursor"] = commit["sha"]
            consumed.append(commit["sha"])
        if consumed:
            # Keep every imported snapshot in the receipt, including earlier
            # commits that arrived in the same push. Retain this list on retry.
            source["verification_commits"] = consumed
    # Both inputs are now local push events; no scheduled or external polling.
    state["last_checked_day"] = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    # Content and cursor are committed together by the workflow, after all imports succeed.
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {total} new Flux entries from committed GitHub inputs.")


if __name__ == "__main__":
    main()
