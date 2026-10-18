from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ingest_github as pub
import image_inbox as inbox


class ImageNamingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = {'repository': 'owner/flux', 'path': 'trigger_imgs', 'identity': 'commit-path'}
        self.commit = {'sha': 'a' * 40, 'commit': {'committer': {'date': '2026-10-18T04:30:12Z'}, 'message': 'Upload'}}
        out = BytesIO(); Image.new('RGB', (3, 2), 'red').save(out, 'PNG'); self.raw = out.getvalue()

    def tearDown(self): self.tmp.cleanup()

    def entries(self, root=None):
        return [(path, *pub.split_frontmatter(path.read_text())) for path in ((root or self.root) / 'flux').glob('**/index.md')]

    def test_original_names_become_upload_time_and_batch_sequence(self):
        files = [{'filename': 'trigger_imgs/说明/IMG_0001.PNG', 'status': 'added'},
                 {'filename': 'trigger_imgs/README.md', 'status': 'modified'},
                 {'filename': 'trigger_imgs/相片/IMG_0001.PNG', 'status': 'added'}]
        for order in [files, list(reversed(files))]:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.assertEqual(pub.import_images(root, self.source, self.commit, set(), order, lambda _: self.raw), 2)
                actual = {}
                for path, meta, body in self.entries(root):
                    name = Path(meta['upload']['file']).name
                    actual[meta['source_asset_path']] = name
                    self.assertEqual(meta['upload']['uploaded_at'], '2026-10-18T12:30:12+08:00')
                    self.assertEqual(meta['date'], '2026-10-18T12:30:12+08:00')
                    self.assertEqual(body, '![](assets/' + name + ')')
                    self.assertTrue((path.parent / meta['upload']['file']).is_file())
                self.assertEqual(actual, {'trigger_imgs/相片/IMG_0001.PNG': '20261018-123012-01.webp',
                                          'trigger_imgs/说明/IMG_0001.PNG': '20261018-123012-02.webp'})

    def test_same_filename_and_bytes_in_two_upload_commits_create_two_posts(self):
        files = [{'filename': 'trigger_imgs/IMG_0001.PNG', 'status': 'added'}]
        for sha in ['a' * 40, 'b' * 40]:
            commit = {**self.commit, 'sha': sha}
            self.assertEqual(pub.import_images(self.root, self.source, commit, pub.existing_keys(self.root), files, lambda _: self.raw), 1)
            self.assertEqual(pub.import_images(self.root, self.source, commit, pub.existing_keys(self.root), files,
                             lambda _: self.fail('Retry must not download or import again')), 0)
        entries = self.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(len({meta['id'] for _, meta, _ in entries}), 2)
        self.assertEqual(len({meta['source_key'] for _, meta, _ in entries}), 2)
        # Two uploads in the same second are isolated by their package IDs.
        self.assertEqual({Path(meta['upload']['file']).name for _, meta, _ in entries}, {'20261018-123012-01.webp'})

    def test_a_deliberate_new_upload_can_reuse_a_historical_phone_filename(self):
        self.source['previous_paths'] = ['uploads']
        self.source['previous_sources'] = [{'repository': 'owner/assets', 'path': 'post/flux'}]
        keys = {'asset:owner/flux:trigger_imgs/IMG_0001.PNG', 'asset:owner/flux:uploads/IMG_0001.PNG', 'asset-post-flux-img-0001-png'}
        files = [{'filename': 'trigger_imgs/IMG_0001.PNG', 'status': 'added'}]
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, keys, files, lambda _: self.raw), 1)

    def test_reused_identical_inbox_original_is_verified_for_both_packages_and_deleted_once(self):
        (self.root / 'trigger_imgs').mkdir()
        original = self.root / 'trigger_imgs/IMG_0001.PNG'; original.write_bytes(self.raw)
        files = [{'filename': 'trigger_imgs/IMG_0001.PNG', 'status': 'added'}]
        for sha in ['a' * 40, 'b' * 40]:
            pub.import_images(self.root, self.source, {**self.commit, 'sha': sha}, pub.existing_keys(self.root), files, lambda _: self.raw)
        (self.root / '.publishing').mkdir()
        (self.root / '.publishing/state.json').write_text(json.dumps({'sources': {'images': self.source}}))
        receipt = {'site_sha256': 'verified', 'files': {}}
        candidates = inbox.candidates(self.root)
        self.assertEqual(len(candidates), 2)
        for _, asset, page in candidates:
            for public, payload in [(asset, (self.root / asset).read_bytes()), (page, b'<html>published</html>')]:
                path = self.root / '_site' / public; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
                receipt['files'][str(public)] = hashlib.sha256(payload).hexdigest()
        (self.root / '_site/deployment.json').write_text(json.dumps(receipt))
        (self.root / '_site/.verified.sha256').write_text('verified')
        (self.root / '.publishing/deployed.sha256').write_text('verified')
        self.assertEqual(inbox.clear_verified(self.root), (1, len(self.raw)))
        self.assertFalse(original.exists())
        self.assertEqual(len(self.entries()), 2)
        self.assertEqual(inbox.clear_verified(self.root), (0, 0))

    def test_unknown_identity_policy_fails_without_importing(self):
        self.source['identity'] = 'mistyped-policy'
        with self.assertRaisesRegex(ValueError, 'identity policy'):
            pub.import_images(self.root, self.source, self.commit, set(), [], lambda _: self.raw)


if __name__ == '__main__': unittest.main()
