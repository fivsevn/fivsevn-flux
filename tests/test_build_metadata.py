"""Integration checks for the public artifact, metadata gate, and existing URLs."""
from pathlib import Path
from io import BytesIO
from html.parser import HTMLParser
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build as renderer
import ingest_github as publisher
from site_post_metadata import dump_frontmatter, normalize_metadata, read_frontmatter, validate_metadata
from support import copy_builder


class EntryCounter(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.entries = []
        self.feed(document)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'article' and attributes.get('class') == 'entry':
            self.entries.append(attributes['id'])


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        copy_builder(self.root)
        (self.root / 'style.css').write_text('body{color:white}')
        (self.root / 'CNAME').write_text('flux.fivsevn.com\n')

    def post(self, number, status='published', visibility='public', media=False):
        ident = f'2026-10-18-080000-{number:012d}'
        package = self.root / 'flux/2026/10' / ident
        package.mkdir(parents=True)
        metadata = normalize_metadata({'id': ident, 'title': f'Post {number}', 'date': '2026-10-18T08:00:00+08:00',
                                       'status': status, 'visibility': visibility}, site='flux')
        body = f'POST_CONTENT_{number}\n'
        if media:
            (package / 'assets').mkdir()
            image = BytesIO()
            Image.new('RGB', (3, 2), 'red').save(image, 'PNG')
            (package / 'assets/original.png').write_bytes(image.getvalue())
            body += '\n![](assets/original.png)\n'
        (package / 'index.md').write_text(dump_frontmatter(metadata) + '\n' + body)
        return ident, package, metadata

    def test_eleven_public_posts_per_page_and_preserved_routes(self):
        for number in range(13):
            self.post(number, status=('active', 'publish', 'published')[number % 3], media=number == 0)
        for number, status, visibility in [(20, 'draft', 'public'), (21, 'hidden', 'public'),
                                            (22, 'published', 'private'), (23, 'active', 'internal')]:
            self.post(number, status, visibility, media=True)
        renderer.build(self.root)
        site = self.root / '_site'
        self.assertEqual(len(EntryCounter((site / 'index.html').read_text()).entries), 11)
        self.assertEqual(len(EntryCounter((site / 'feed/2/index.html').read_text()).entries), 2)
        self.assertEqual(len(list((site / 'page').glob('**/index.html'))), 13)
        self.assertFalse((self.root / 'index.html').exists())
        self.assertFalse((self.root / 'page').exists())
        self.assertFalse((self.root / 'feed').exists())
        original = self.root / 'flux/2026/10/2026-10-18-080000-000000000000/assets/original.png'
        self.assertEqual((site / original.relative_to(self.root)).read_bytes(), original.read_bytes())
        self.assertTrue((site / 'page/2026/10/2026-10-18-080000-000000000000/index.html').exists())
        artifact_text = '\n'.join(path.read_text() for path in site.rglob('*.html'))
        for number in range(20, 24):
            self.assertNotIn(f'POST_CONTENT_{number}', artifact_text)
            self.assertFalse((site / f'flux/2026/10/2026-10-18-080000-{number:012d}').exists())

    def test_schema_failure_precedes_artifact_replacement(self):
        _, package, metadata = self.post(1)
        site = self.root / '_site'
        site.mkdir()
        (site / 'sentinel').write_text('keep prior artifact')
        metadata['date'] = '2026-10-18T08:00:00+08:00'
        import yaml
        (package / 'index.md').write_text('---\n' + yaml.safe_dump(metadata) + '---\ninvalid source')
        with self.assertRaises(ValueError):
            renderer.build(self.root)
        self.assertEqual((site / 'sentinel').read_text(), 'keep prior artifact')

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to execute the bookmark compatibility script')
    def test_old_feed_bookmark_follows_post_to_new_page(self):
        for number in range(13):
            self.post(number)
        renderer.build(self.root)
        script = (self.root / '_site/site-assets/navigation.js').read_text()
        ident = '2026-10-18-080000-000000000012'
        mock = "const urls=[];const location={pathname:'/feed/10/',search:'?from=bookmark',hash:'#" + ident + "',replace:url=>urls.push(url)};"
        result = subprocess.check_output(['node', '-e', mock + script + '\nconsole.log(JSON.stringify(urls));'], text=True)
        self.assertEqual(json.loads(result), ['/?from=bookmark#' + ident])

    def test_text_trigger_fills_core_and_keeps_explicit_controls(self):
        source = {'repository': 'owner/flux', 'path': 'trigger_text.md'}
        commit = {'sha': 'a' * 40, 'commit': {'committer': {'date': '2026-10-18T00:00:00Z'}, 'message': 'Save'}}
        raw = b'---\nstatus: hidden\nvisibility: internal\ntags: [field-note]\n---\nbody'
        publisher.import_text(self.root, source, commit, set(), lambda _: raw)
        source_file = next((self.root / 'flux').glob('**/index.md'))
        metadata, body = read_frontmatter(source_file)
        validate_metadata(metadata, site='flux', schema_dir=self.root / 'schemas')
        self.assertEqual(metadata['status'], 'hidden')
        self.assertEqual(metadata['visibility'], 'internal')
        self.assertEqual(metadata['tags'], ['field-note'])
        self.assertEqual(metadata['created'], '2026-10-18')
        self.assertEqual(metadata['extra']['published_at'], '2026-10-18T08:00:00+08:00')
        self.assertNotIn('date', metadata)
        self.assertNotIn('source_key', metadata)
        self.assertIn('source_key', metadata['extra'])
        self.assertEqual(body.strip(), 'body')


if __name__ == '__main__':
    unittest.main()
