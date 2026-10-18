"""Publish rendered pages and visible media; exclude scripts and draft packages."""
from pathlib import Path
import shutil
import hashlib
import json
from ingest_github import split_frontmatter
from image_inbox import candidates

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
for name in ('index.html', 'style.css', 'CNAME'):
    shutil.copy2(ROOT / name, OUT / name)
for name in ('page', 'feed', 'site-assets'):
    if (ROOT / name).exists():
        shutil.copytree(ROOT / name, OUT / name)
for path in (ROOT / 'flux').glob('**/index.md'):
    meta, body = split_frontmatter(path.read_text(encoding='utf-8'))
    if meta.get('status', 'published') != 'published':
        continue
    assets = path.parent / 'assets'
    if assets.exists():
        shutil.copytree(assets, OUT / assets.relative_to(ROOT))
(OUT / '.nojekyll').touch()
state_path = ROOT / '.publishing/state.json'
sources = json.loads(state_path.read_text())['sources'] if state_path.exists() else {}
receipt = {
    'version': 1,
    'sources': {kind: {key: source[key] for key in ('repository', 'path', 'cursor')}
                for kind, source in sources.items()},
    'files': {'index.html': hashlib.sha256((OUT / 'index.html').read_bytes()).hexdigest()},
}
# Check every published snapshot from the last import batch and its media.
for path in (ROOT / 'flux').glob('**/index.md'):
    meta, _ = split_frontmatter(path.read_text(encoding='utf-8'))
    if meta.get('status', 'published') != 'published':
        continue
    if any(meta.get('source_repository') == source['repository']
           and meta.get('source_commit') in source.get('verification_commits', [source['cursor']])
           for source in sources.values()):
        page = Path('page', *path.parent.relative_to(ROOT / 'flux').parts, 'index.html')
        receipt['files'][page.as_posix()] = hashlib.sha256((OUT / page).read_bytes()).hexdigest()
        for asset in (path.parent / 'assets').rglob('*'):
            if asset.is_file():
                relative = asset.relative_to(ROOT)
                receipt['files'][relative.as_posix()] = hashlib.sha256((OUT / relative).read_bytes()).hexdigest()
# Inbox cleanup also needs proof for previously archived (migrated) pictures.
if sources.get('images'):
    for _, archived, page in candidates(ROOT):
        for public in (archived, page):
            receipt['files'][public.as_posix()] = hashlib.sha256((OUT / public).read_bytes()).hexdigest()
digest = hashlib.sha256()
for path in sorted(OUT.rglob('*')):
    if path.is_file():
        digest.update(path.relative_to(OUT).as_posix().encode() + b'\0')
        digest.update(path.read_bytes())
# Include source positions even for drafts, so their receipt is deployed as well.
digest.update(json.dumps(receipt, sort_keys=True).encode())
receipt['site_sha256'] = digest.hexdigest()
(OUT / 'deployment.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
(ROOT / '.publishing').mkdir(exist_ok=True)
(ROOT / '.publishing/site.sha256').write_text(digest.hexdigest() + '\n')
print('Packaged published pages and media for GitHub Pages.')
