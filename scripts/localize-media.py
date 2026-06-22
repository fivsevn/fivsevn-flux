#!/usr/bin/env python3
"""Download remote image links into each flux package assets/ folder.

Also refreshes already-localized images from the recorded original source in frontmatter,
so older thumbnail/cached downloads can be replaced by the original GitHub/jsDelivr asset.
"""
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from media_utils import localize_markdown_images, refresh_local_media_from_frontmatter  # noqa: E402


def split_frontmatter(text: str):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def dump_frontmatter(fm: dict, body: str) -> str:
    return '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n\n' + body.strip() + '\n'


def merge_media(existing, new):
    existing = existing or []
    if not isinstance(existing, list):
        existing = []
    seen = {(m.get('file'), m.get('source')) for m in existing if isinstance(m, dict)}
    out = list(existing)
    for m in new:
        key = (m.get('file'), m.get('source'))
        if key not in seen:
            out.append(m)
            seen.add(key)
    return out


def main():
    changed = 0
    total_new = 0
    total_refreshed = 0
    for md_path in sorted((ROOT / 'flux').glob('**/index.md')):
        original = md_path.read_text(encoding='utf-8')
        fm, body = split_frontmatter(original)

        refreshed = refresh_local_media_from_frontmatter(fm, md_path.parent)
        new_body, new_media = localize_markdown_images(body, md_path.parent)

        if refreshed or new_media:
            if new_media:
                fm['media'] = merge_media(fm.get('media'), new_media)
            md_path.write_text(dump_frontmatter(fm, new_body), encoding='utf-8')
            changed += 1
            total_new += len(new_media)
            total_refreshed += len(refreshed)
            print(f'[media] {md_path.relative_to(ROOT)}: new {len(new_media)}, refreshed {len(refreshed)}')

    print(f'localized {total_new} new media file(s), refreshed {total_refreshed} existing file(s), changed {changed} package(s)')


if __name__ == '__main__':
    main()
