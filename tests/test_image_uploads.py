from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlparse, unquote

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ingest_github as pub
from support import copy_builder, read_saved
from verify_live import verify_once


def image_bytes(format='PNG'):
    output = BytesIO()
    Image.new('RGB', (2, 2), (75, 110, 90)).save(output, format=format)
    return output.getvalue()


class ImageUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = {'repository': 'owner/flux', 'path': 'trigger_imgs', 'cursor': 'c'*40}
        self.commit = {'sha': 'a'*40, 'commit': {'committer': {'date': '2026-10-18T00:00:00Z'},
                                               'message': 'Add photos\n\n配文 [链接](https://example.com)\n第二行'}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_multiple_images_convert_to_webp_preserve_caption_and_retry_identity(self):
        payloads = {'trigger_imgs/a.PNG': image_bytes(), 'trigger_imgs/b.gif': image_bytes('GIF')}
        files = [{'filename': path, 'status': 'added'} for path in payloads]
        def read(url):
            return payloads[unquote(url).split('/' + self.commit['sha'] + '/')[1]]
        keys = set()
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, keys, files, read), 2)
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, pub.existing_keys(self.root), files, read), 0)
        entries = list((self.root/'flux').glob('**/index.md'))
        self.assertEqual(len(entries), 2)
        for path in entries:
            meta, body = read_saved(path.read_text())
            self.assertIn('配文 [链接](https://example.com)\n第二行', body)
            asset = next((path.parent/'assets').iterdir())
            self.assertEqual(asset.read_bytes(), pub.convert_image(payloads[meta['source_asset_path']], meta['source_asset_path']))
            self.assertEqual(meta['upload']['sha256'], hashlib.sha256(payloads[meta['source_asset_path']]).hexdigest())

    def test_no_caption_and_unicode_paths(self):
        self.commit['commit']['message'] = 'Add photo'
        urls = []
        def read(url):
            urls.append(url)
            return image_bytes()
        files = [{'filename': 'trigger_imgs/2026/自拍 #1.PNG', 'status': 'added'}]
        pub.import_images(self.root, self.source, self.commit, set(), files, read)
        self.assertIn('%20%231.PNG', urls[0])
        _, body = read_saved(next((self.root/'flux').glob('**/index.md')).read_text())
        self.assertEqual(body, '![](assets/image.webp)')

    def test_phone_mpo_uses_primary_photo_without_animating_gain_map(self):
        output = BytesIO()
        first = Image.new('RGB', (2, 2), (75, 110, 90))
        second = Image.new('RGB', (2, 2), (45, 60, 50))
        first.save(output, format='MPO', save_all=True, append_images=[second])
        payload = output.getvalue()
        with Image.open(BytesIO(payload)) as image:
            self.assertEqual(image.format, 'MPO')
        files = [{'filename': 'trigger_imgs/phone.jpeg', 'status': 'added'}]
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, set(), files, lambda _: payload), 1)
        saved = next((self.root/'flux').glob('**/assets/image.webp'))
        with Image.open(saved) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(image.n_frames, 1)
            self.assertEqual(image.size, (2, 2))

    def test_migrated_sources_keep_their_old_identity(self):
        self.source['previous_sources'] = [
            {'repository': 'owner/assets', 'path': 'post/flux'},
            {'repository': 'owner/assets', 'path': 'post/stream'},
        ]
        files = [{'filename': 'trigger_imgs/old.PNG', 'status': 'added'}]
        for key in ('asset:owner/assets:post/flux/old.PNG', 'asset-post-stream-old-png'):
            with self.subTest(key=key):
                self.assertEqual(pub.import_images(self.root, self.source, self.commit, {key}, files,
                    lambda _: self.fail('A migrated image must not be downloaded or republished')), 0)

    def test_unsupported_and_damaged_uploads_fail_before_creating_an_entry(self):
        for filename, payload, message in [('phone.mov', b'video', 'Unsupported upload'),
                                            ('bad.png', b'not an image', 'damaged'),
                                            ('empty.jpg', b'', 'Empty image')]:
            with self.subTest(filename=filename):
                files = [{'filename': 'trigger_imgs/' + filename, 'status': 'added'}]
                with self.assertRaisesRegex(ValueError, message):
                    pub.import_images(self.root, self.source, self.commit, set(), files, lambda _: payload)
                self.assertEqual(list((self.root/'flux').glob('**/index.md')), [])

    def test_upload_guide_and_deletions_do_not_create_posts(self):
        files = [{'filename': 'trigger_imgs/README.md', 'status': 'modified'},
                 {'filename': 'trigger_imgs/old.png', 'status': 'removed'}]
        self.assertEqual(pub.import_images(self.root, self.source, self.commit, set(), files,
            lambda _: self.fail('No image download expected')), 0)

    def test_public_receipt_checks_actual_image_bytes(self):
        (self.root/'scripts').mkdir()
        copy_builder(self.root)
        (self.root/'style.css').write_text('')
        (self.root/'CNAME').write_text('example.com')
        (self.root/'.publishing').mkdir()
        source = {**self.source, 'cursor': 'b'*40, 'verification_commits': ['a'*40, 'b'*40]}
        (self.root/'.publishing/state.json').write_text(json.dumps({'sources': {'images': source}}))
        files = [{'filename': 'trigger_imgs/new.png', 'status': 'added'}]
        pub.import_images(self.root, self.source, self.commit, set(), files, lambda _: image_bytes())
        second = {**self.commit, 'sha': 'b'*40}
        pub.import_images(self.root, self.source, second, set(),
                          [{'filename': 'trigger_imgs/second.png', 'status': 'added'}], lambda _: image_bytes())
        subprocess.run([sys.executable, str(self.root/'scripts/build.py')], check=True, capture_output=True)
        site = self.root/'_site'
        receipt = json.loads((site/'deployment.json').read_text())
        self.assertEqual(len(receipt['files']), 5)
        image = next(p for p in receipt['files'] if '/assets/' in p)
        self.assertEqual(receipt['files'][image], hashlib.sha256(pub.convert_image(image_bytes(), 'new.png')).hexdigest())
        def read(url):
            return (site/unquote(urlparse(url).path.lstrip('/'))).read_bytes()
        verify_once('https://example.com', receipt, read)
        (site/image).write_bytes(b'bad CDN response')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            verify_once('https://example.com', receipt, read)
        self.assertFalse((site/'uploads').exists())

    def test_same_second_posts_have_stable_order_across_checkouts(self):
        html = []
        for number, order in enumerate([['a', 'b'], ['b', 'a']]):
            root = self.root/str(number)
            (root/'scripts').mkdir(parents=True)
            copy_builder(root)
            for suffix in order:
                snapshot = {**self.commit, 'sha': suffix*40}
                pub.import_text(root, self.source, snapshot, set(), lambda _: b'text')
            subprocess.run([sys.executable, str(root/'scripts/build.py')], check=True, capture_output=True)
            html.append((root/'_site/index.html').read_text())
        self.assertEqual(html[0], html[1])

    def test_both_inputs_are_direct_local_pushes(self):
        import yaml
        workflow = yaml.load((ROOT/'.github/workflows/build.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('trigger_text.md', workflow['on']['push']['paths'])
        self.assertIn('trigger_imgs/**', workflow['on']['push']['paths'])
        self.assertNotIn('schedule', workflow['on'])
        state = json.loads((ROOT/'.publishing/state.json').read_text())
        self.assertEqual({source['repository'] for source in state['sources'].values()}, {'fivsevn/fivsevn-flux'})


if __name__ == '__main__':
    unittest.main()
