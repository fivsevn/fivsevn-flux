#!/usr/bin/env python3
"""Sync public posts from the live WordPress site into flux packages.

Rules:
- New WordPress post: create flux/YYYY/MM/{id}/index.md
- Existing package with sync: auto: update when the WordPress source hash changes
- Existing package with sync: manual: never overwrite
- Full rescan + soft delete: packages missing from WordPress are marked status: hidden
  instead of being physically deleted.

This keeps WordPress as the source during the transition, while allowing any
individual flux package to be taken over by editing `sync: manual` in frontmatter.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from media_utils import download_asset, is_remote_url, best_img_url  # noqa: E402

DEFAULT_SITE = "https://fivsevn.com"
DEFAULT_POSTS_URL = "https://fivsevn.com/posts/"
UA = "fivsevn-flux-sync/1.3 (+https://github.com/fivsevn/fivsevn-flux)"


def fetch_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")


def fetch_json(url: str):
    return json.loads(fetch_text(url))


def iso_parts(date_iso: str):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", date_iso or "")
    if not m:
        return None
    return m.groups()


def normalize_date(date_iso: str) -> str:
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", date_iso or ""):
        return f"{date_iso}+08:00"
    return date_iso


def build_ident(date_iso: str, suffix: str | int | None = None):
    parts = iso_parts(date_iso)
    if not parts:
        return None
    y, mo, d, h, mi, se = parts
    ident = f"{y}-{mo}-{d}-{h}{mi}{se}"
    if suffix:
        ident = f"{ident}-{suffix}"
    return ident


def item_dir_from_date(date_iso: str, ident: str) -> Path:
    y, mo, *_ = iso_parts(date_iso)
    return ROOT / "flux" / y / mo / ident


def split_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def read_existing(item_dir: Path) -> tuple[dict, str]:
    p = item_dir / "index.md"
    if not p.exists():
        return {}, ""
    return split_frontmatter(p.read_text(encoding="utf-8"))


def write_existing(item_dir: Path, fm: dict, body: str):
    p = item_dir / "index.md"
    text = (
        "---\n"
        + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
        + "\n---\n\n"
        + body.strip()
        + "\n"
    )
    p.write_text(text, encoding="utf-8")


def strip_wp_comments(raw_html: str) -> str:
    return re.sub(r"<!--\s*/?wp:.*?-->", "", raw_html or "", flags=re.S)


def canonical_source(raw_html: str) -> str:
    """Return a stable representation for change detection."""
    soup = BeautifulSoup(strip_wp_comments(raw_html), "html.parser")

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    for tag in soup.find_all(True):
        keep = {}
        for attr in ["href", "src", "alt", "title"]:
            if tag.has_attr(attr):
                keep[attr] = tag[attr]
        tag.attrs = keep

    text = str(soup).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def source_hash(raw_html: str) -> str:
    return hashlib.sha256(canonical_source(raw_html).encode("utf-8")).hexdigest()[:16]


def post_source_hash(post: dict) -> str:
    """Hash WordPress post content plus metadata that should trigger a resync."""
    title = BeautifulSoup(
        (post.get("title") or {}).get("rendered") or "",
        "html.parser",
    ).get_text("").strip()

    raw_html = (post.get("content") or {}).get("rendered") or ""

    payload = {
        "title": title,
        "content": canonical_source(raw_html),
        "slug": post.get("slug") or "",
        "link": post.get("link") or "",
        "date": post.get("date") or post.get("date_gmt") or "",
        "modified": post.get("modified") or post.get("modified_gmt") or "",
        "status": post.get("status") or "",
    }

    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def cleanup_markdown(text: str) -> str:
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    cleaned: list[str] = []

    i = 0
    while i < len(lines):
        current = lines[i].strip()

        if current == ".":
            look = "\n".join(lines[i : i + 8])
            if "tags:" in look and "comment:" in look:
                i += 1
                while i < len(lines):
                    s = lines[i].strip()
                    if re.match(r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", s):
                        i += 1
                        break
                    i += 1
                continue

        if current in {"tags:", "comment:"}:
            i += 1
            continue

        if re.match(r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", current):
            i += 1
            continue

        cleaned.append(lines[i])
        i += 1

    out = "\n".join(cleaned).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def clean_and_localize(raw_html: str, item_dir: Path, download_media: bool = True):
    soup = BeautifulSoup(strip_wp_comments(raw_html), "html.parser")

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    for fig in soup.find_all("figure"):
        fig.unwrap()

    media = []
    img_index = 0

    for img in soup.find_all("img"):
        src = best_img_url(img)

        if download_media and is_remote_url(src):
            img_index += 1
            local, original = download_asset(src, item_dir / "assets", img_index)
            if local:
                img["src"] = local
                media.append({"file": local, "source": original})

    for tag in soup.find_all(True):
        keep = {}
        for attr in ["href", "src", "alt", "title"]:
            if tag.has_attr(attr):
                keep[attr] = tag[attr]
        tag.attrs = keep

    out = md(
        str(soup),
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    ).strip()
    out = cleanup_markdown(out)

    return out, media


def dump_package(item_dir: Path, fm: dict, body: str, force: bool = False) -> bool:
    if item_dir.exists() and not force:
        return False

    if item_dir.exists():
        shutil.rmtree(item_dir)

    (item_dir / "assets").mkdir(parents=True, exist_ok=True)

    if not fm.get("media"):
        (item_dir / "assets" / ".gitkeep").write_text("", encoding="utf-8")

    write_existing(item_dir, fm, body)
    return True


def maybe_write_package(item_dir: Path, fm: dict, body: str, force: bool = False) -> str:
    if not item_dir.exists():
        dump_package(item_dir, fm, body, force=True)
        return "created"

    old_fm, _ = read_existing(item_dir)

    if force:
        dump_package(item_dir, fm, body, force=True)
        return "updated"

    if old_fm.get("sync") == "manual":
        return "manual"

    old_hash = old_fm.get("source_hash")
    if old_hash == fm.get("source_hash") and old_fm.get("status") != "hidden":
        return "skipped"

    # If a previously hidden post reappears in WordPress, unhide it by writing status: published.
    dump_package(item_dir, fm, body, force=True)
    return "updated"


def get_posts_category_id(site: str) -> int:
    categories = fetch_json(
        f"{site}/wp-json/wp/v2/categories?{urlencode({'slug': 'posts', 'per_page': 100})}"
    )
    if not categories:
        raise RuntimeError("REST category slug `posts` not found")
    return categories[0]["id"]


def iter_flux_packages():
    for p in (ROOT / "flux").glob("**/index.md"):
        item_dir = p.parent
        fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        ident = fm.get("id") or item_dir.name
        yield ident, item_dir, fm, body


def should_soft_delete(fm: dict) -> bool:
    if fm.get("sync") == "manual":
        return False

    # Only soft-delete WordPress-derived packages.
    source = str(fm.get("source", ""))
    if not source.startswith("wordpress"):
        return False

    # Already hidden, no need to rewrite.
    if fm.get("status") == "hidden":
        return False

    return True


def soft_delete_missing(remote_idents: set[str], remote_wp_ids: set[int | str]) -> int:
    """Mark missing WordPress-derived local packages as hidden.

    This does not delete files. It only changes frontmatter:
      status: hidden
      deleted_from_wordpress: true
      deleted_checked_at: <UTC timestamp>

    It respects sync: manual.
    """
    count = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for ident, item_dir, fm, body in iter_flux_packages():
        if not should_soft_delete(fm):
            continue

        wp_id = fm.get("wp_post_id")
        ident_missing = ident not in remote_idents
        wp_missing = bool(wp_id) and wp_id not in remote_wp_ids and str(wp_id) not in remote_wp_ids

        # Prefer wp_post_id when present; otherwise use generated id/date ident.
        missing = wp_missing if wp_id else ident_missing

        if missing:
            fm["status"] = "hidden"
            fm["deleted_from_wordpress"] = True
            fm["deleted_checked_at"] = now
            write_existing(item_dir, fm, body)
            count += 1

    return count


def sync_rest(
    site: str,
    limit: int | None,
    full_rescan: bool,
    soft_delete_missing_enabled: bool,
    force: bool,
    no_media: bool,
) -> dict[str, int]:
    cat_id = get_posts_category_id(site)
    stats = defaultdict(int)
    page = 1
    seen = 0
    remote_idents: set[str] = set()
    remote_wp_ids: set[int | str] = set()

    while True:
        if full_rescan:
            per_page = 100
        else:
            remaining = max(0, (limit or 0) - seen)
            if remaining <= 0:
                break
            per_page = min(100, remaining)

        url = (
            f"{site}/wp-json/wp/v2/posts?"
            + urlencode(
                {
                    "categories": cat_id,
                    "per_page": per_page,
                    "page": page,
                    "status": "publish",
                    "_embed": "1",
                }
            )
        )

        try:
            posts = fetch_json(url)
        except HTTPError as exc:
            if exc.code == 400 and page > 1:
                break
            raise

        if not posts:
            break

        for post in posts:
            seen += 1

            date = post.get("date") or post.get("date_gmt")
            ident = build_ident(date)
            if not ident:
                stats["bad_date"] += 1
                continue

            remote_idents.add(ident)
            if post.get("id") is not None:
                remote_wp_ids.add(post.get("id"))
                remote_wp_ids.add(str(post.get("id")))

            item_dir = item_dir_from_date(date, ident)
            raw_html = (post.get("content") or {}).get("rendered") or ""
            shash = post_source_hash(post)

            old_fm, _ = read_existing(item_dir)

            if item_dir.exists() and not force and old_fm.get("sync") == "manual":
                stats["manual"] += 1
                continue

            if (
                item_dir.exists()
                and not force
                and old_fm.get("source_hash") == shash
                and old_fm.get("status") != "hidden"
            ):
                stats["skipped"] += 1
                continue

            title = BeautifulSoup(
                (post.get("title") or {}).get("rendered") or ident,
                "html.parser",
            ).get_text("").strip()

            body, media = clean_and_localize(raw_html, item_dir, not no_media)

            fm = {
                "id": ident,
                "date": normalize_date(date),
                "title": title or ident,
                "source": "wordpress-live",
                "sync": "auto",
                "source_hash": shash,
                "wp_post_id": post.get("id"),
                "wp_url": post.get("link"),
                "wp_slug": post.get("slug"),
                "status": "published",
            }

            if media:
                fm["media"] = media

            result = maybe_write_package(item_dir, fm, body, force=force)
            stats[result] += 1

        page += 1

        if len(posts) < per_page:
            break

    if full_rescan and soft_delete_missing_enabled:
        stats["soft_hidden"] = soft_delete_missing(remote_idents, remote_wp_ids)

    stats["seen"] = seen
    return dict(stats)


def parse_live_html(
    posts_url: str,
    limit: int | None,
    full_rescan: bool,
    soft_delete_missing_enabled: bool,
    force: bool,
    no_media: bool,
) -> dict[str, int]:
    # HTML fallback can only scan what appears on /posts/.
    # It cannot safely soft-delete missing older posts.
    html = fetch_text(posts_url)
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup.find("article") or soup.body or soup
    headings = root.find_all(["h2", "h3"])

    if not full_rescan and limit:
        headings = headings[:limit]

    stats = defaultdict(int)
    used = defaultdict(int)

    for h in headings:
        title = h.get_text(" ", strip=True)
        if not title:
            continue

        nodes = []
        for sib in h.next_siblings:
            name = getattr(sib, "name", None)
            if name in ["h2", "h3"]:
                break
            nodes.append(str(sib))

        raw = "".join(nodes)
        text = BeautifulSoup(raw, "html.parser").get_text("\n")
        iso_match = re.search(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)?", text)
        if not iso_match:
            continue

        date = iso_match.group(0)
        ident = build_ident(date)
        if not ident:
            continue

        used[ident] += 1
        if used[ident] > 1:
            ident = f"{ident}-{used[ident]}"

        item_dir = item_dir_from_date(date, ident)
        shash = source_hash(raw)

        old_fm, _ = read_existing(item_dir)

        if item_dir.exists() and not force and old_fm.get("sync") == "manual":
            stats["manual"] += 1
            continue

        if (
            item_dir.exists()
            and not force
            and old_fm.get("source_hash") == shash
            and old_fm.get("status") != "hidden"
        ):
            stats["skipped"] += 1
            continue

        body, media = clean_and_localize(raw, item_dir, not no_media)

        fm = {
            "id": ident,
            "date": date,
            "title": title,
            "source": "wordpress-live-html",
            "sync": "auto",
            "source_hash": shash,
            "wp_url": posts_url,
            "status": "published",
        }

        if media:
            fm["media"] = media

        result = maybe_write_package(item_dir, fm, body, force=force)
        stats[result] += 1

    if full_rescan and soft_delete_missing_enabled:
        stats["soft_hidden"] = 0
        print("[sync] Warning: soft-delete skipped because HTML fallback cannot safely identify all WordPress posts.")

    return dict(stats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=DEFAULT_SITE)
    ap.add_argument("--posts-url", default=DEFAULT_POSTS_URL)
    ap.add_argument("--limit", type=int, default=50, help="maximum recent posts to inspect")
    ap.add_argument(
        "--full-rescan",
        action="store_true",
        help="scan every WordPress post in the posts category through the REST API",
    )
    ap.add_argument(
        "--soft-delete-missing",
        action="store_true",
        help="during --full-rescan, mark WordPress-derived local packages missing from WordPress as status: hidden",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing packages, including sync: manual; do not use in normal workflows",
    )
    ap.add_argument("--no-media", action="store_true", help="do not download images into package assets/")
    ap.add_argument("--html-only", action="store_true", help="skip REST API and parse /posts/ directly")
    args = ap.parse_args()

    site = args.site.rstrip("/")

    if args.soft_delete_missing and not args.full_rescan:
        raise SystemExit("--soft-delete-missing requires --full-rescan")

    if args.html_only:
        stats = parse_live_html(
            args.posts_url,
            args.limit,
            args.full_rescan,
            args.soft_delete_missing,
            args.force,
            args.no_media,
        )
    else:
        try:
            stats = sync_rest(
                site,
                args.limit,
                args.full_rescan,
                args.soft_delete_missing,
                args.force,
                args.no_media,
            )
        except Exception as exc:
            print(f"[sync] REST failed, falling back to HTML parse: {exc}")
            if args.full_rescan:
                print("[sync] Warning: HTML fallback cannot truly full-rescan older paginated posts.")
            stats = parse_live_html(
                args.posts_url,
                args.limit,
                args.full_rescan,
                args.soft_delete_missing,
                args.force,
                args.no_media,
            )

    if stats:
        print("synced live posts: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
    else:
        print("synced live posts: no changes")


if __name__ == "__main__":
    main()
