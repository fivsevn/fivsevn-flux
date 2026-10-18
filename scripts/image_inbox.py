"""Delete only matching inbox originals whose saved page and media went live."""
import hashlib
import json
from pathlib import Path
from ingest_github import split_frontmatter

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates(root):
    state = json.loads((root / '.publishing/state.json').read_text())
    inbox = root / state['sources']['images']['path']
    found = []
    for entry in (root / 'flux').glob('**/index.md'):
        meta, _ = split_frontmatter(entry.read_text(encoding='utf-8'))
        upload = meta.get('upload')
        if not isinstance(upload, dict) or meta.get('status', 'published') != 'published':
            continue
        original = root / upload['path']
        archived = entry.parent / upload['file']
        # Never follow symlinks or metadata that escapes the input/package roots.
        if (original.is_symlink() or archived.is_symlink()
                or not original.resolve().is_relative_to(inbox.resolve())
                or not archived.resolve().is_relative_to((entry.parent / 'assets').resolve())):
            raise ValueError(f'Unsafe image cleanup path: {entry}')
        if not original.is_file() or not archived.is_file():
            continue
        # Leave a newer upload or a manually replaced archive intact.
        if digest(original) != upload['sha256'] or digest(archived) != upload['file_sha256']:
            continue
        page = Path('page', *entry.parent.relative_to(root / 'flux').parts, 'index.html')
        found.append((original, archived.relative_to(root), page))
    return found


def clear_verified(root):
    site = root / '_site'
    receipt = json.loads((site / 'deployment.json').read_text())
    fingerprint = receipt['site_sha256']
    # The local marker is written only by a successful live byte verification.
    if ((site / '.verified.sha256').read_text().strip() != fingerprint
            or (root / '.publishing/deployed.sha256').read_text().strip() != fingerprint):
        raise ValueError('Refusing image cleanup before the public deployment is verified')
    pending = candidates(root)
    # Check every candidate first; a missing/mismatched receipt deletes nothing.
    for original, archived, page in pending:
        for public in (archived, page):
            expected = receipt['files'].get(public.as_posix())
            if not expected or digest(site / public) != expected:
                raise ValueError(f'Image package was not verified live: {public}')
        if digest(root / archived) != receipt['files'][archived.as_posix()]:
            raise ValueError(f'Saved image changed after verification: {archived}')
    total = 0
    originals = {original for original, _, _ in pending}
    for original in sorted(originals):
        # Several posts may own identical uploads at a reused input path.
        # Verify all their packages, but delete the physical inbox file once.
        # candidates() rechecks bytes against the archive before this process;
        # no other workflow process writes inputs while this step runs.
        total += original.stat().st_size
        original.unlink()
    return len(originals), total


if __name__ == '__main__':
    count, size = clear_verified(ROOT)
    print(f'Cleared {count} verified inbox originals ({size:,} bytes). Saved packages are retained.')
