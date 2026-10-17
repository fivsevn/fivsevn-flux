"""Publish rendered pages and visible media; exclude scripts and draft packages."""
from pathlib import Path
import shutil
import hashlib
from ingest_github import split_frontmatter

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
digest = hashlib.sha256()
for path in sorted(OUT.rglob('*')):
    if path.is_file():
        digest.update(path.relative_to(OUT).as_posix().encode() + b'\0')
        digest.update(path.read_bytes())
(ROOT / '.publishing').mkdir(exist_ok=True)
(ROOT / '.publishing/site.sha256').write_text(digest.hexdigest() + '\n')
print('Packaged published pages and media for GitHub Pages.')
