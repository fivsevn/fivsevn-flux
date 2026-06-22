#!/usr/bin/env python3
"""Sync public posts from the live WordPress site into flux packages.

Rules:
- New WordPress post: create flux/YYYY/MM/{id}/index.md
- Existing package with sync: auto: update when the WordPress source hash changes
- Existing package with sync: manual: never overwrite

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

from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from media_utils import download_asset, is_remote_url, best_img_url  # noqa: E402

DEFAULT_SITE = 'https://fivsevn.com'
DEFAULT_POSTS_URL = 'https://fivsevn.com/posts/'
UA = 'fivsevn-flux-sync/1.1 (+https://github.com/fivsevn/fivsevn-flux)'


def fetch_text(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={'User-Agent': UA})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or 'utf-8'
        return data.decode(charset, errors='replace')


def fetch_json(url: str):
    return json.loads(fetch_text(url))


def iso_parts(date_iso: str):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})', date_iso or '')
    if not m:
        return None
    return m.groups()


def normalize_date(date_iso: str) -> str:
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', date_iso or ''):
        return f'{date_iso}+08:00'
    return date_iso


def build_ident(date_iso: str, suffix: str | int | None = None):
    parts = iso_parts(date_iso)
    if not parts:
        return None
    y, mo, d, h, mi, se = parts
    ident = f'{y}-{mo}-{d}-{h}{mi}{se}'
    if suffix:
        ident = f'{ident}-{suffix}'
    return ident


def item_dir_from_date(date_iso: str, ident: str) -> Path:
    y, mo, *_ = iso_parts(date_iso)
    return ROOT / 'flux' / y / mo / ident


def split_frontmatter(text: str):
    if not text.startswith('---'):
        return {}, text
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def read_existing(item_dir: Path) -> tuple[dict, str]:
    p = item_dir / 'index.md'
    if not p.exists():
        return {}, ''
    return split_frontmatter(p.read_text(encoding='utf-8'))


def strip_wp_comments(raw_html: str) -> str:
    return re.sub(r'<!--\s*/?wp:[^>]*-->', '', raw_html or '')


def canonical_source(raw_html: str) -> str:
    """Return a stable text representation for change detection.

    This is based on the current WordPress source, not on local Markdown paths,
    so localizing images to ./assets/ does not cause false positives.
    """
    soup = BeautifulSoup(strip_wp_comments(raw_html), 'html.parser')
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()
    for tag in soup.find_all(True):
        keep = {}
        for attr in ['href', 'src', 'alt', 'title']:
            if tag.has_attr(attr):
                keep[attr] = tag[attr]
        tag.attrs = keep
    text = str(soup).strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def source_hash(raw_html: str) -> str:
    return hashlib.sha256(canonical_source(raw_html).encode('utf-8')).hexdigest()[:16]


def cleanup_markdown(text: str) -> str:
    # Remove the old WordPress stream footer lines: '.', tags:, comment:, count, ISO timestamp.
    lines = [ln.rstrip() for ln in (text or '').splitlines()]
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i].strip()
        if current == '.':
            look = '\n'.join(lines[i:i+8])
            if 'tags:' in look and 'comment:' in look:
                i += 1
                while i < len(lines):
                    s = lines[i].strip()
                    if re.match(r'^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d', s):
                        i += 1
                        break
                    i += 1
                continue
        if current in {'tags:', 'comment:'}:
            i += 1
            continue
        if re.match(r'^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$', current):
            i += 1
            continue
        cleaned.append(lines[i])
        i += 1
    out = '\n'.join(cleaned).strip()
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out


def clean_and_localize(raw_html: str, item_dir: Path, download_media: bool = True):
    soup = BeautifulSoup(strip_wp_comments(raw_html), 'html.parser')

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for fig in soup.find_all('figure'):
        fig.unwrap()

    media = []
    img_index = 0
    for img in soup.find_all('img'):
        src = best_img_url(img)
        if download_media and is_remote_url(src):
            img_index += 1
            local, original = download_asset(src, item_dir / 'assets', img_index)
            if local:
                img['src'] = local
                media.append({'file': local, 'source': original})

    for tag in soup.find_all(True):
        keep = {}
        for attr in ['href', 'src', 'alt', 'title']:
            if tag.has_attr(attr):
                keep[attr] = tag[attr]
        tag.attrs = keep

    out = md(str(soup), heading_style='ATX', bullets='-', strip=['script', 'style']).strip()
    out = cleanup_markdown(out)
    return out, media


def dump_package(item_dir: Path, fm: dict, body: str, force: bool = False) -> bool:
    if item_dir.exists() and not force:
        return False
    if item_dir.exists():
        shutil.rmtree(item_dir)
    (item_dir / 'assets').mkdir(parents=True, exist_ok=True)
    if not fm.get('media'):
        (item_dir / 'assets' / '.gitkeep').write_text('', encoding='utf-8')
    text = '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n\n' + body.strip() + '\n'
    (item_dir / 'index.md').write_text(text, encoding='utf-8')
    return True


def maybe_write_package(item_dir: Path, fm: dict, body: str, force: bool = False) -> str:
    """Create/update/skip one package. Return created|updated|skipped|manual."""
    if not item_dir.exists():
        dump_package(item_dir, fm, body, force=True)
        return 'created'

    old_fm, _ = read_existing(item_dir)
    if force:
        dump_package(item_dir, fm, body, force=True)
        return 'updated'

    if old_fm.get('sync') == 'manual':
        return 'manual'

    # Existing items are treated as auto unless explicitly marked manual.
    old_hash = old_fm.get('source_hash')
    if old_hash == fm.get('source_hash'):
        return 'skipped'

    # Preserve a user-set sync:auto and update from WordPress.
    dump_package(item_dir, fm, body, force=True)
    return 'updated'


def sync_rest(site: str, limit: int, force: bool, no_media: bool) -> dict[str, int]:
    categories = fetch_json(f'{site}/wp-json/wp/v2/categories?{urlencode({"slug":"posts","per_page":100})}')
    if not categories:
        raise RuntimeError('REST category slug `posts` not found')
    cat_id = categories[0]['id']

    stats = defaultdict(int)
    page = 1
    seen = 0
    while seen < limit:
        per_page = min(100, max(1, limit - seen))
        url = f'{site}/wp-json/wp/v2/posts?{urlencode({"categories":cat_id,"per_page":per_page,"page":page,"status":"publish","_embed":"1"})}'
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
            date = post.get('date') or post.get('date_gmt')
            ident = build_ident(date)
            if not ident:
                continue
            item_dir = item_dir_from_date(date, ident)
            raw_html = (post.get('content') or {}).get('rendered') or ''
            shash = source_hash(raw_html)
            old_fm, _ = read_existing(item_dir)
            if item_dir.exists() and not force and old_fm.get('sync') == 'manual':
                stats['manual'] += 1
                continue
            if item_dir.exists() and not force and old_fm.get('source_hash') == shash:
                stats['skipped'] += 1
                continue

            title = BeautifulSoup((post.get('title') or {}).get('rendered') or ident, 'html.parser').get_text('').strip()
            body, media = clean_and_localize(raw_html, item_dir, not no_media)
            fm = {
                'id': ident,
                'date': normalize_date(date),
                'title': title or ident,
                'source': 'wordpress-live',
                'sync': 'auto',
                'source_hash': shash,
                'wp_post_id': post.get('id'),
                'wp_url': post.get('link'),
                'wp_slug': post.get('slug'),
                'status': 'published',
            }
            if media:
                fm['media'] = media
            result = maybe_write_package(item_dir, fm, body, force=force)
            stats[result] += 1
        page += 1
        if len(posts) < per_page:
            break
    return dict(stats)


def parse_live_html(posts_url: str, limit: int, force: bool, no_media: bool) -> dict[str, int]:
    html = fetch_text(posts_url)
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.find('main') or soup.find('article') or soup.body or soup
    headings = root.find_all(['h2', 'h3'])
    stats = defaultdict(int)
    used = defaultdict(int)

    for h in headings[:limit]:
        title = h.get_text(' ', strip=True)
        if not title:
            continue
        nodes = []
        for sib in h.next_siblings:
            name = getattr(sib, 'name', None)
            if name in ['h2', 'h3']:
                break
            nodes.append(str(sib))
        raw = ''.join(nodes)
        iso_match = re.search(r'20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:[+-]\d\d:\d\d)?', BeautifulSoup(raw, 'html.parser').get_text('\n'))
        if not iso_match:
            continue
        date = iso_match.group(0)
        ident = build_ident(date)
        if not ident:
            continue
        used[ident] += 1
        if used[ident] > 1:
            ident = f'{ident}-{used[ident]}'
        item_dir = item_dir_from_date(date, ident)
        shash = source_hash(raw)
        old_fm, _ = read_existing(item_dir)
        if item_dir.exists() and not force and old_fm.get('sync') == 'manual':
            stats['manual'] += 1
            continue
        if item_dir.exists() and not force and old_fm.get('source_hash') == shash:
            stats['skipped'] += 1
            continue
        body, media = clean_and_localize(raw, item_dir, not no_media)
        fm = {
            'id': ident,
            'date': date,
            'title': title,
            'source': 'wordpress-live-html',
            'sync': 'auto',
            'source_hash': shash,
            'wp_url': posts_url,
            'status': 'published',
        }
        if media:
            fm['media'] = media
        result = maybe_write_package(item_dir, fm, body, force=force)
        stats[result] += 1
    return dict(stats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default=DEFAULT_SITE)
    ap.add_argument('--posts-url', default=DEFAULT_POSTS_URL)
    ap.add_argument('--limit', type=int, default=50, help='maximum recent posts to inspect')
    ap.add_argument('--force', action='store_true', help='overwrite existing packages, including sync: manual')
    ap.add_argument('--no-media', action='store_true', help='do not download images into package assets/')
    ap.add_argument('--html-only', action='store_true', help='skip REST API and parse /posts/ directly')
    args = ap.parse_args()

    if args.html_only:
        stats = parse_live_html(args.posts_url, args.limit, args.force, args.no_media)
    else:
        try:
            stats = sync_rest(args.site.rstrip('/'), args.limit, args.force, args.no_media)
        except Exception as exc:
            print(f'[sync] REST failed, falling back to HTML parse: {exc}')
            stats = parse_live_html(args.posts_url, args.limit, args.force, args.no_media)

    print('synced live posts: ' + ', '.join(f'{k} {v}' for k, v in sorted(stats.items())) if stats else 'synced live posts: no changes')


if __name__ == '__main__':
    main()
