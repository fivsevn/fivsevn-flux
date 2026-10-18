from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ingest_github as pub
import image_inbox as inbox


class WebPTests(unittest.TestCase):
    def encode(self, image, fmt, **options):
        out = BytesIO()
        image.save(out, format=fmt, **options)
        return out.getvalue()

    def test_transparency_pixels_and_icc_are_lossless(self):
        image = Image.new('RGBA', (4, 3), (22, 75, 108, 80))
        image.putpixel((0, 0), (10, 20, 30, 255))
        raw = self.encode(image, 'PNG', icc_profile=b'test-profile')
        with Image.open(BytesIO(pub.convert_image(raw, 'phone.png'))) as webp:
            self.assertEqual(webp.format, 'WEBP')
            self.assertEqual(webp.convert('RGBA').tobytes(), image.tobytes())
            self.assertEqual(webp.info['icc_profile'], b'test-profile')

    def test_orientation_is_applied_and_not_applied_twice(self):
        image = Image.new('RGB', (8, 4), 'red')
        exif = Image.Exif(); exif[274] = 6
        raw = self.encode(image, 'JPEG', exif=exif)
        with Image.open(BytesIO(pub.convert_image(raw, 'phone.jpg'))) as webp:
            self.assertEqual(webp.size, (4, 8))
            self.assertNotIn(274, webp.getexif())

    def test_gif_motion_timing_and_finite_loop_count(self):
        frames = [Image.new('RGB', (4, 4), color) for color in ('red', 'blue', 'green')]
        for loops, expected in [(None, 1), (0, 0), (2, 3)]:
            options = {} if loops is None else {'loop': loops}
            raw = self.encode(frames[0], 'GIF', save_all=True, append_images=frames[1:], duration=[40, 120, 80], **options)
            with Image.open(BytesIO(pub.convert_image(raw, 'animated.gif'))) as webp:
                self.assertEqual(webp.n_frames, 3)
                self.assertEqual(webp.info['loop'], expected)
                durations = []
                for n, frame in enumerate(frames):
                    webp.seek(n); webp.load()
                    durations.append(webp.info['duration'])
                    self.assertEqual(webp.convert('RGB').tobytes(), frame.tobytes())
                self.assertEqual(durations, [40, 120, 80])

    def test_heic_decodes_on_server(self):
        image = Image.new('RGB', (16, 8), (50, 80, 90))
        raw = self.encode(image, 'HEIF')
        with Image.open(BytesIO(pub.convert_image(raw, 'phone.HEIC'))) as webp:
            self.assertEqual(webp.format, 'WEBP')
            self.assertEqual(webp.size, image.size)
            self.assertEqual(webp.n_frames, 1)

    def test_existing_webp_is_not_recompressed(self):
        raw = self.encode(Image.new('RGBA', (3, 3), (50, 80, 90, 70)), 'WEBP')
        self.assertEqual(pub.convert_image(raw, 'uploaded.webp'), raw)


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.source = {'repository': 'owner/flux', 'path': 'trigger_imgs', 'history_path': '', 'cursor': 'c'*40}
        self.commit = {'sha': 'a'*40, 'commit': {'committer': {'date': '2026-10-18T00:00:00Z'}, 'message': 'Add photo'}}
        out = BytesIO(); Image.new('RGB', (4, 4), 'red').save(out, 'PNG'); self.raw = out.getvalue()
        (self.root / 'trigger_imgs').mkdir()
        self.original = self.root / 'trigger_imgs/20261018-080000.png'
        self.original.write_bytes(self.raw)
        self.files = [{'filename': 'trigger_imgs/20261018-080000.png', 'status': 'added'}]
        pub.import_images(self.root, self.source, self.commit, set(), self.files, lambda _: self.raw)
        self.entry = next((self.root / 'flux').glob('**/index.md'))
        (self.root / '.publishing').mkdir()
        self.state = self.root / '.publishing/state.json'
        self.state.write_text(json.dumps({'sources': {'images': self.source}}))
        (self.root / '_site').mkdir()
        self.receipt = {'site_sha256': 'artifact', 'files': {}}
        for _, archived, page in inbox.candidates(self.root):
            for path, data in [(archived, (self.root / archived).read_bytes()), (page, b'<html>post</html>')]:
                target = self.root / '_site' / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
                self.receipt['files'][path.as_posix()] = hashlib.sha256(data).hexdigest()
        self.save_receipt()

    def tearDown(self): self.tmp.cleanup()

    def save_receipt(self):
        (self.root / '_site/deployment.json').write_text(json.dumps(self.receipt))
        (self.root / '_site/.verified.sha256').write_text('artifact')
        (self.root / '.publishing/deployed.sha256').write_text('artifact')

    def test_only_verified_original_is_removed_and_archive_retry_survives(self):
        (self.root / 'trigger_imgs/new.png').write_bytes(b'not processed')
        self.assertEqual(inbox.clear_verified(self.root), (1, len(self.raw)))
        self.assertTrue(self.entry.exists())
        self.assertFalse(self.original.exists())
        self.assertTrue((self.root / 'trigger_imgs/new.png').exists())
        self.assertEqual(inbox.clear_verified(self.root), (0, 0))
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, pub.existing_keys(self.root), self.files,
                         lambda _: self.fail('Retry must use stored package')), 0)

    def test_unverified_or_incomplete_deployment_never_deletes(self):
        (self.root / '_site/.verified.sha256').write_text('stale')
        with self.assertRaisesRegex(ValueError, 'before'): inbox.clear_verified(self.root)
        self.assertTrue(self.original.exists())
        self.save_receipt(); self.receipt['files'] = {}; self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'not verified'): inbox.clear_verified(self.root)
        self.assertTrue(self.original.exists())

    def test_changed_upload_and_manually_replaced_archive_are_kept(self):
        self.original.write_bytes(b'newer upload')
        self.assertEqual(inbox.clear_verified(self.root), (0, 0))
        self.original.write_bytes(self.raw)
        (self.entry.parent / 'assets/image.webp').write_bytes(b'manually edited')
        self.assertEqual(inbox.clear_verified(self.root), (0, 0))
        self.assertTrue(self.original.exists())

    def test_replaced_or_deleted_invalid_images_can_be_consumed_without_a_post(self):
        for filename, payload in [('bad.png', b'broken'), ('wrong.mov', b'video')]:
            path = 'trigger_imgs/' + filename
            files = [{'filename': path, 'status': 'added'}]
            self.assertEqual(pub.import_images(self.root, self.source, self.commit, set(), files,
                             lambda _: payload, superseded={path}), 0)
            self.assertEqual(len(list((self.root / 'flux').glob('**/index.md'))), 1)
            self.assertTrue(self.original.exists())

    def test_valid_queued_images_are_retained_even_if_a_later_commit_changes_the_path(self):
        path = 'trigger_imgs/queued.png'
        files = [{'filename': path, 'status': 'added'}]
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, set(), files,
                         lambda _: self.raw, superseded={path}), 1)

    def test_invalid_snapshot_followed_by_valid_replacement_recovers_the_queue(self):
        original_root, original_state = pub.ROOT, pub.STATE
        pub.ROOT, pub.STATE = self.root, self.state
        real_import = pub.import_images
        files = [{'filename': 'trigger_imgs/replaced.png', 'status': 'modified'}]
        replacement = {**self.commit, 'sha': 'b'*40}
        def import_snapshot(root, source, commit, keys, files, **options):
            return real_import(root, source, commit, keys, files,
                               read=lambda _: self.raw if commit['sha'] == 'b'*40 else b'broken', **options)
        try:
            with patch.object(pub, 'pending_commits', return_value=[self.commit, replacement]), \
                 patch.object(pub, 'commit_files', return_value=files), \
                 patch.object(pub, 'import_images', side_effect=import_snapshot):
                pub.main()
            source = json.loads(self.state.read_text())['sources']['images']
            self.assertEqual(source['cursor'], 'b'*40)
            new = [pub.split_frontmatter(p.read_text())[0] for p in (self.root / 'flux').glob('**/index.md')]
            self.assertEqual(sum(meta.get('source_asset_path') == 'trigger_imgs/replaced.png' for meta in new), 1)
            self.assertTrue(any(meta['source_commit'] == 'b'*40 for meta in new))
        finally: pub.ROOT, pub.STATE = original_root, original_state

    def test_cleanup_and_build_commits_do_not_change_cursor_or_receipt_batch(self):
        original_root, original_state = pub.ROOT, pub.STATE
        pub.ROOT, pub.STATE = self.root, self.state
        try:
            deleted = {**self.commit, 'sha': 'b'*40}
            with patch.object(pub, 'pending_commits', return_value=[self.commit, deleted]), \
                 patch.object(pub, 'commit_files', side_effect=[self.files, [{'filename': self.files[0]['filename'], 'status': 'removed'}]]):
                pub.main()
            source = json.loads(self.state.read_text())['sources']['images']
            self.assertEqual(source['cursor'], 'a'*40)
            self.assertEqual(source['verification_commits'], ['a'*40])
        finally: pub.ROOT, pub.STATE = original_root, original_state


if __name__ == '__main__': unittest.main()
