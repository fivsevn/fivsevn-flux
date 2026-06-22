#!/usr/bin/env python3
"""Import published WordPress posts in category `posts` from a WXR XML export.

Default behavior is safe: existing flux packages are not overwritten.
Images are downloaded into each package's assets/ folder by default.
"""
from pathlib import Path
import argparse
import re
import sys
import xml.etree.ElementTree as ET
import shutil
import hashlib
from collections import defaultdict
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from media_utils import download_asset, is_remote_url  # noqa: E402

NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'wp': 'http://wordpress.org/export/1.2/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def text(el, path):
    return el.findtext(path, default='', namespaces=NS) or ''


def cats(it, domain):
    return [
        {'nicename': c.attrib.get('nicename', ''), 'name': c.text or ''}
        for c in it.findall('category')
        if c.attrib.get('domain') == domain
    ]



def strip_wp_comments(raw_html: str) -> str:
    return re.sub(r'<!--\s*/?wp:[^>]*-->', '', raw_html or '')


def canonical_source(raw_html: str) -> str:
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


def clean_and_localize(raw_html: str, item_dir: Path, download_media: bool = True):
    raw_html = strip_wp_comments(raw_html)
    soup = BeautifulSoup(raw_html, 'html.parser')

    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for fig in soup.find_all('figure'):
        fig.unwrap()

    media = []
    img_index = 0
    for img in soup.find_all('img'):
        src = img.get('src') or ''
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
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out, media


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wxr_xml')
    ap.add_argument('--force', action='store_true', help='overwrite existing packages')
    ap.add_argument('--no-media', action='store_true', help='do not download image files into package assets/')
    args = ap.parse_args()

    root = ET.parse(args.wxr_xml).getroot()
    ch = root.find('channel')
    if ch is None:
        raise SystemExit('Invalid WXR: missing channel')

    used = defaultdict(int)
    count = 0
    skipped = 0

    for it in ch.findall('item'):
        if text(it, 'wp:post_type') != 'post' or text(it, 'wp:status') != 'publish':
            continue
        if not any(c['nicename'] == 'posts' or c['name'] == 'posts' for c in cats(it, 'category')):
            continue

        date = text(it, 'wp:post_date')
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})', date)
        if not m:
            continue
        y, mo, d, h, mi, se = m.groups()
        base = f'{y}-{mo}-{d}-{h}{mi}{se}'
        pid = text(it, 'wp:post_id')
        used[base] += 1
        ident = base if used[base] == 1 else f'{base}-{pid}'

        item_dir = ROOT / 'flux' / y / mo / ident
        if item_dir.exists() and not args.force:
            skipped += 1
            continue
        if item_dir.exists():
            shutil.rmtree(item_dir)
        (item_dir / 'assets').mkdir(parents=True, exist_ok=True)

        raw_html = text(it, 'content:encoded')
        body, media = clean_and_localize(raw_html, item_dir, download_media=not args.no_media)
        if not media:
            (item_dir / 'assets' / '.gitkeep').write_text('', encoding='utf-8')

        fm = {
            'id': ident,
            'date': f'{y}-{mo}-{d}T{h}:{mi}:{se}+08:00',
            'title': text(it, 'title').strip() or ident,
            'source': 'wordpress',
            'sync': 'auto',
            'source_hash': source_hash(raw_html),
            'wp_post_id': int(pid) if pid.isdigit() else pid,
            'wp_url': text(it, 'link'),
            'wp_slug': text(it, 'wp:post_name'),
            'status': 'published',
            'tags': [c['name'] for c in cats(it, 'post_tag')],
            'comments': int(text(it, 'wp:comment_count') or 0),
        }
        if media:
            fm['media'] = media

        (item_dir / 'index.md').write_text(
            '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n\n' + body + '\n',
            encoding='utf-8',
        )
        count += 1

    print(f'imported {count}; skipped {skipped}')


if __name__ == '__main__':
    main()
