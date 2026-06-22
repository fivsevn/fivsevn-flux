#!/usr/bin/env python3
"""Download remote Markdown image links in existing flux packages into local assets/ folders.

Safe by default: only rewrites index.md when a remote image is successfully downloaded.
"""
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from media_utils import localize_markdown_images  # noqa: E402


def split_frontmatter(text: str):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def dump_frontmatter(fm: dict, body: str) -> str:
    return '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n\n' + body.strip() + '\n'


def main():
    changed = 0
    total_media = 0
    for md_path in sorted((ROOT / 'flux').glob('**/index.md')):
        original = md_path.read_text(encoding='utf-8')
        fm, body = split_frontmatter(original)
        new_body, media = localize_markdown_images(body, md_path.parent)
        if not media:
            continue
        existing = fm.get('media') or []
        fm['media'] = existing + media
        md_path.write_text(dump_frontmatter(fm, new_body), encoding='utf-8')
        changed += 1
        total_media += len(media)
        print(f'[media] {md_path.relative_to(ROOT)}: {len(media)} file(s)')
    print(f'localized {total_media} media file(s) in {changed} package(s)')


if __name__ == '__main__':
    main()
