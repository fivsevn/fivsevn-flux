"""Shared test fixtures for canonical packages and the independent build artifact."""
from pathlib import Path
import shutil

from site_post_metadata import metadata_view, read_frontmatter

ROOT = Path(__file__).resolve().parents[1]


def read_saved(text):
    metadata, body = read_frontmatter(text)
    return metadata_view(metadata), body.strip()


def copy_builder(root):
    (root / 'scripts').mkdir(exist_ok=True)
    for name in ('build.py', 'ingest_github.py', 'image_inbox.py', 'site_post_metadata.py'):
        shutil.copy2(ROOT / 'scripts' / name, root / 'scripts' / name)
    shutil.copytree(ROOT / 'schemas', root / 'schemas', dirs_exist_ok=True)
