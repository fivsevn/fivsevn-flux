#!/usr/bin/env python3
"""Convert saved Flux/UI raster images to WebP as one offline transaction.

The upload inbox is deliberately excluded. Its immutable event paths and original
checksums remain valid until a deployment has been verified and cleanup runs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

from image_codec import convert_image, validate_image
from site_post_metadata import dump_frontmatter, read_frontmatter, validate_metadata

ROOT = Path(__file__).resolve().parents[1]
RASTER = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.avif', '.bmp', '.tif', '.tiff', '.ico'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def safe(root, path):
    path = Path(path)
    if not path.is_relative_to(root) or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
        raise ValueError('Unsafe saved image path: ' + str(path))
    return path


def image_paths(root):
    for folder in (root / 'flux', root / 'site-assets'):
        if folder.is_symlink():
            raise ValueError('Image folder follows a symlink: ' + str(folder))
        if folder.exists():
            for path in sorted(folder.rglob('*')):
                if path.suffix.lower() in RASTER and (path.is_file() or path.is_symlink()):
                    yield safe(root, path)


def rewrite(text, aliases):
    # Local references only: the boundary excludes URLs to immutable source
    # commits, while retaining Markdown, HTML, CSS, query strings and fragments.
    for old, new in sorted(aliases.items(), key=lambda pair: -len(pair[0])):
        text = re.sub(r'(?<![\w/:%])' + re.escape(old) + r'(?=$|[^\w.%/-])', lambda _: new, text)
    return text


def aliases_for(root, source, target, package=None):
    old, new = source.relative_to(root).as_posix(), target.relative_to(root).as_posix()
    pairs = {old: new, '/' + old: '/' + new}
    if package is not None and source.is_relative_to(package):
        old, new = source.relative_to(package).as_posix(), target.relative_to(package).as_posix()
        pairs.update({old: new, './' + old: './' + new})
    pairs.update({quote(old, safe='/'): quote(new, safe='/') for old, new in list(pairs.items())})
    return pairs


def normalize(root=ROOT):
    root = Path(root).resolve()
    images = []
    # Decode the entire batch before changing any file, including existing WebP.
    for source in image_paths(root):
        data = source.read_bytes()
        converted = convert_image(data, source.name)
        target = source if source.suffix.lower() == '.webp' else source.with_suffix('.webp')
        safe(root, target)
        images.append({'source': source, 'target': target, 'before': data, 'after': converted})
    targets = {}
    for item in images:
        target = item['target']
        if target in targets:
            raise ValueError('Two images map to the same WebP: ' + str(target))
        targets[target] = item['source']
        if target != item['source'] and target.exists():
            raise ValueError('Refusing to overwrite an existing WebP: ' + str(target))
    changed = [item for item in images if item['source'] != item['target'] or item['before'] != item['after']]
    metadata = {}
    for post in sorted((root / 'flux').rglob('index.md')):
        safe(root, post)
        before = post.read_bytes()
        meta, body = read_frontmatter(before.decode('utf-8'))
        validate_metadata(meta, site='flux', schema_dir=root / 'schemas')
        updated = deepcopy(meta)
        aliases = {}
        for item in changed:
            aliases.update(aliases_for(root, item['source'], item['target'], post.parent))

        def update_paths(value):
            if isinstance(value, dict):
                return {key: update_paths(item) for key, item in value.items()}
            if isinstance(value, list):
                return [update_paths(item) for item in value]
            return aliases.get(value, value) if isinstance(value, str) else value

        # Only exact path values change; provenance URLs and original inbox
        # identities/checksums remain untouched for retries and verified cleanup.
        updated = update_paths(updated)
        upload = updated.get('extra', {}).get('upload')
        old_upload = meta.get('extra', {}).get('upload')
        if isinstance(upload, dict) and isinstance(old_upload, dict):
            old_path = old_upload.get('file')
            for item in changed:
                if old_path in aliases_for(root, item['source'], item['target'], post.parent):
                    upload['file_sha256'] = digest(item['after'])
                    break
        body_after = rewrite(body, aliases)
        if updated != meta or body_after != body:
            validate_metadata(updated, site='flux', schema_dir=root / 'schemas')
            metadata[post] = (before, (dump_frontmatter(updated) + body_after).encode())
    aliases = {}
    for item in changed:
        aliases.update(aliases_for(root, item['source'], item['target']))
    text_paths = [root / 'style.css', *sorted((root / 'site-assets').rglob('*'))]
    for path in text_paths:
        if path.is_file() and path.suffix in {'.css', '.js', '.html'}:
            safe(root, path)
            before = path.read_bytes()
            after = rewrite(before.decode('utf-8'), aliases).encode()
            if before != after:
                metadata[path] = (before, after)
    files = [{'path': item['source'].relative_to(root).as_posix(),
              'target_path': item['target'].relative_to(root).as_posix(),
              'source_blob_sha': blob_sha(item['before']), 'target_blob_sha': blob_sha(item['after']),
              'source_sha256': digest(item['before']), 'file_sha256': digest(item['after']),
              'before_bytes': len(item['before']), 'after_bytes': len(item['after'])} for item in changed]
    stats = {'count': len(changed), 'image_count': len(images), 'unchanged_count': len(images) - len(changed),
             'before_bytes': sum(item['before_bytes'] for item in files),
             'after_bytes': sum(item['after_bytes'] for item in files), 'files': files}
    if not changed:
        return stats
    for item in images:
        if item['source'].read_bytes() != item['before']:
            raise ValueError('Image changed during conversion: ' + str(item['source']))
    for path, (before, _) in metadata.items():
        if path.read_bytes() != before:
            raise ValueError('Metadata changed during conversion: ' + str(path))
    with tempfile.TemporaryDirectory(prefix='.flux-webp-', dir=root) as temporary:
        staging = Path(temporary)
        for i, item in enumerate(changed):
            (staging / f'image-{i}').write_bytes(item['after'])
        for i, (_, after) in enumerate(metadata.values()):
            (staging / f'text-{i}').write_bytes(after)
        installed_images, installed_text = [], []
        try:
            for i, item in enumerate(changed):
                if item['target'] != item['source'] and item['target'].exists():
                    raise ValueError('WebP destination changed during conversion: ' + str(item['target']))
                backup = staging / f'image-old-{i}'
                os.replace(item['source'], backup)
                installed_images.append((item, backup))
                os.replace(staging / f'image-{i}', item['target'])
            for i, path in enumerate(metadata):
                backup = staging / f'text-old-{i}'
                os.replace(path, backup)
                installed_text.append((path, backup))
                os.replace(staging / f'text-{i}', path)
        except BaseException:
            for path, backup in reversed(installed_text):
                path.unlink(missing_ok=True)
                os.replace(backup, path)
            for item, backup in reversed(installed_images):
                item['target'].unlink(missing_ok=True)
                os.replace(backup, item['source'])
            raise
    return stats


def check(root=ROOT, output=None):
    root = Path(root).resolve()
    checked = 0
    paths = list(image_paths(root))
    if output is not None:
        output = Path(output).resolve()
        paths.extend(path for path in output.rglob('*') if path.is_file() and path.suffix.lower() in RASTER)
    for path in paths:
        if path.suffix.lower() != '.webp':
            raise ValueError('Saved/public raster image must be WebP: ' + str(path))
        data = path.read_bytes()
        validate_image(data, path.name)
        if data[:4] != b'RIFF' or data[8:12] != b'WEBP':
            raise ValueError('Image has a misleading WebP extension: ' + str(path))
        checked += 1
    return {'webp_images_checked': checked}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.root, args.output) if args.check else normalize(args.root), ensure_ascii=False))
