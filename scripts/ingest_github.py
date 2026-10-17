#!/usr/bin/env python3
"""Import committed trigger snapshots and post/stream images, without WordPress.

Each source has a durable commit cursor. Process every intervening commit oldest
first, and use stable source identities so retries never duplicate or overwrite
an edited flux entry. No source writes or cross-repository secrets are needed.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".publishing/state.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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
    text = text.replace("\r\n", "\n").lstrip("\ufeff")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("Unclosed trigger frontmatter")
    meta = yaml.safe_load("".join(lines[1:end])) or {}
    if not isinstance(meta, dict):
        raise ValueError("Trigger frontmatter must be a mapping")
    return meta, "".join(lines[end + 1:]).strip()


def pending_commits(source: dict, read=api) -> list[dict]:
    """Never silently replay history if a cursor disappeared after a force push."""
    pending = []
    for page in range(1, 101):
        query = urlencode({"sha": "main", "path": source["path"], "per_page": 100, "page": page})
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
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=parent) as staging:
        staging = Path(staging)
        if media:
            (staging / "assets").mkdir()
            (staging / "assets" / media[0]).write_bytes(media[1])
        (staging / "index.md").write_text("---\n" + yaml.safe_dump(fields, allow_unicode=True, sort_keys=False) + "---\n\n" + body.strip() + "\n", encoding="utf-8")
        staging.rename(target)
    return target


def import_text(root: Path, source: dict, commit: dict, keys: set[str], read=fetch) -> bool:
    sha = commit["sha"]
    data = read(f"https://raw.githubusercontent.com/{source['repository']}/{sha}/{quote(source['path'])}").decode("utf-8-sig")
    meta, body = split_frontmatter(data)
    if not body.strip():
        return False
    status = str(meta.get("wp_status") or "publish")
    if status not in {"publish", "draft", "pending", "private"}:
        raise ValueError("Use publish, draft, pending or private; scheduled publication is not supported")
    slug = str(meta.get("slug") or f"github-text-{sha[:7]}")
    key = f"github:{source['repository']}:{sha}"
    if key in keys or slug in keys:
        return False
    save_package(root, source_date(commit), sha[:12], {
        "source": "github-trigger", "source_key": key, "source_commit": sha,
        "source_repository": source["repository"], "publish_slug": slug,
        "status": "published" if status == "publish" else "draft",
    }, body)
    keys.update((key, slug))
    return True


def asset_slug(path: str) -> str:
    return "asset-" + path.lower().replace("/", "-").replace("_", "-").replace(".", "-")


def import_images(root: Path, source: dict, commit: dict, keys: set[str], files: list[dict], read=fetch) -> int:
    count = 0
    sha = commit["sha"]
    # Match the existing shortcut: the extended commit description is the caption.
    caption = commit["commit"]["message"].partition("\n")[2].strip()
    for item in files:
        path = item["filename"]
        parts = PurePosixPath(path)
        if item["status"] == "removed" or not path.startswith("post/stream/") or parts.suffix.lower() not in EXTENSIONS or ".." in parts.parts:
            continue
        key = f"asset:{source['repository']}:{path}"
        slug = asset_slug(path)
        if key in keys or slug in keys:
            continue
        media = read(f"https://raw.githubusercontent.com/{source['repository']}/{sha}/{quote(path)}")
        if not media:
            raise ValueError(f"Empty image: {path}")
        import hashlib
        suffix = hashlib.sha256(path.encode()).hexdigest()[:12]
        filename = "image" + parts.suffix.lower()
        body = f"![](assets/{filename})"
        if caption:
            body += "\n\n" + caption
        save_package(root, source_date(commit), suffix, {
            "source": "github-image", "source_key": key, "source_commit": sha,
            "source_repository": source["repository"], "source_asset_path": path,
            "publish_slug": slug, "status": "published",
        }, body, (filename, media))
        keys.update((key, slug))
        count += 1
    return count


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    keys = existing_keys(ROOT)
    total = 0
    for kind, source in state["sources"].items():
        commits = pending_commits(source)
        for commit in commits:
            if kind == "text":
                total += import_text(ROOT, source, commit, keys)
            else:
                total += import_images(ROOT, source, commit, keys, commit_files(source["repository"], commit["sha"]))
            source["cursor"] = commit["sha"]
    # Daily activity keeps GitHub's public-repository schedule from expiring after
    # 60 quiet days. This does not change any content or require a redeployment.
    state["last_checked_day"] = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    # Content and cursor are committed together by the workflow, after all imports succeed.
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {total} new entries from GitHub. WordPress was not contacted.")


if __name__ == "__main__":
    main()
