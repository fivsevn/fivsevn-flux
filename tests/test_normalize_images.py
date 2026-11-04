"""Protect editable references and originals during a saved-image migration."""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from normalize_images import normalize, check
from site_post_metadata import dump_frontmatter, normalize_metadata, read_frontmatter


def png():
    image = Image.new('RGBA', (13, 9), (11, 22, 33, 0))
    image.putpixel((0, 0), (100, 120, 140, 127))
    stream = BytesIO(); image.save(stream, 'PNG')
    return stream.getvalue()


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'schemas', self.root / 'schemas')
        self.package = self.root / 'flux/2026/10/example'
        (self.package / 'assets').mkdir(parents=True)
        self.photo = self.package / 'assets/photo.png'
        self.raw = png(); self.photo.write_bytes(self.raw)
        meta = normalize_metadata({'id': 'example', 'title': 'Keep title', 'status': 'hidden',
                                   'date': '2026-10-18T08:00:00+08:00',
                                   'upload': {'path': 'trigger_imgs/original.png', 'sha256': 'upload-digest',
                                              'file': './assets/photo.png', 'file_sha256': hashlib.sha256(self.raw).hexdigest()}}, site='flux')
        self.post = self.package / 'index.md'
        self.post.write_text(dump_frontmatter(meta) + '\n![caption](./assets/photo.png)\n'
                             '[photo](assets/photo.png?full=1#x)\n'
                             '<img src="/flux/2026/10/example/assets/photo.png" width="7">\n'
                             '[source](https://example.test/assets/photo.png)\n')
        (self.root / 'site-assets').mkdir()
        (self.root / 'site-assets/avatar.png').write_bytes(self.raw)
        (self.root / 'style.css').write_text('a{background:url("/site-assets/avatar.png")}')
        (self.root / '.publishing').mkdir()
        (self.root / '.publishing/state.json').write_text(json.dumps({'cursor': 'unchanged', 'path': 'trigger_imgs/original.png'}))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_local_references_identity_upload_checksum_and_ui_survive(self):
        before, _ = read_frontmatter(self.post)
        state = (self.root / '.publishing/state.json').read_bytes()
        stats = normalize(self.root)
        self.assertEqual(stats['count'], 2)
        after, body = read_frontmatter(self.post)
        for field in ['id', 'title', 'status', 'visibility', 'created', 'updated', 'metadata_updated']:
            self.assertEqual(after[field], before[field])
        upload = after['extra']['upload']
        self.assertEqual(upload['path'], 'trigger_imgs/original.png')
        self.assertEqual(upload['sha256'], 'upload-digest')
        self.assertEqual(upload['file'], './assets/photo.webp')
        self.assertEqual(upload['file_sha256'], hashlib.sha256(self.photo.with_suffix('.webp').read_bytes()).hexdigest())
        self.assertIn('![caption](./assets/photo.webp)', body)
        self.assertIn('assets/photo.webp?full=1#x', body)
        self.assertIn('src="/flux/2026/10/example/assets/photo.webp" width="7"', body)
        self.assertIn('https://example.test/assets/photo.png', body)
        self.assertIn('/site-assets/avatar.webp', (self.root / 'style.css').read_text())
        self.assertEqual((self.root / '.publishing/state.json').read_bytes(), state)
        with Image.open(self.photo.with_suffix('.webp')) as saved, Image.open(BytesIO(self.raw)) as original:
            self.assertEqual(saved.size, (13, 9))
            self.assertEqual(saved.convert('RGBA').tobytes(), original.convert('RGBA').tobytes())
        self.assertFalse(self.photo.exists())
        check(self.root)
        snapshot = self.snapshot()
        self.assertEqual(normalize(self.root)['count'], 0)
        self.assertEqual(self.snapshot(), snapshot)

    def test_invalid_image_and_target_collision_never_change_other_sources(self):
        for collision in [False, True]:
            path = self.package / ('assets/photo.webp' if collision else 'assets/bad.jpg')
            path.write_bytes(self.raw if collision else b'broken')
            snapshot = self.snapshot()
            with self.assertRaises(ValueError):
                normalize(self.root)
            self.assertEqual(self.snapshot(), snapshot)
            path.unlink()

    def test_install_failure_rolls_back_images_and_references(self):
        snapshot = self.snapshot()
        replace = os.replace
        failed = False
        def fail_once(source, target):
            nonlocal failed
            if Path(target).resolve() == self.post.resolve() and not failed:
                failed = True
                raise OSError('simulated metadata install failure')
            return replace(source, target)
        with patch('normalize_images.os.replace', side_effect=fail_once), self.assertRaises(OSError):
            normalize(self.root)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), snapshot)


if __name__ == '__main__':
    unittest.main()
