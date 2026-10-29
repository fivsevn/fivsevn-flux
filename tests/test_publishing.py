import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ingest_github as pub
IMAGE_BYTES = (ROOT / 'site-assets/pocket.webp').read_bytes()


def commit(sha='a'*40, message='post', date='2026-10-18T00:00:00Z'):
    return {'sha': sha, 'commit': {'committer': {'date': date}, 'message': message}}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = {'repository': 'owner/repo', 'path': 'trigger_text.md', 'cursor': 'c'*40}
    def tearDown(self):
        self.tmp.cleanup()
    def test_all_queued_snapshots_in_order(self):
        rows = [commit('a'*40), commit('b'*40), commit('c'*40)]
        self.assertEqual([x['sha'] for x in pub.pending_commits(self.source, lambda p: rows)], ['b'*40, 'a'*40])
    def test_missing_cursor_fails_without_replaying(self):
        with self.assertRaises(ValueError):
            pub.pending_commits(self.source, lambda p: [commit()])
    def test_markdown_preserved_and_retry_does_not_overwrite_edit(self):
        body = '[文字](https://example.com)\n第二行\n\n- 一\n- 二'
        keys = set()
        self.assertTrue(pub.import_text(self.root, self.source, commit(), keys, lambda u: body.encode()))
        path = next((self.root/'flux').glob('**/index.md'))
        text = path.read_text().replace('第二行', '人工修改')
        path.write_text(text)
        self.assertFalse(pub.import_text(self.root, self.source, commit(), pub.existing_keys(self.root), lambda u: body.encode()))
        self.assertEqual(path.read_text(), text)
        self.assertIn("2026-10-18T08:00:00+08:00", text)
    def test_historical_wordpress_slug_prevents_duplicate(self):
        self.assertFalse(pub.import_text(self.root, self.source, commit(), {'github-text-aaaaaaa'}, lambda u: b'hello'))
    def test_explicit_slug_preserves_create_only_behavior(self):
        keys=set()
        raw=b'---\nslug: fixed\n---\nhello'
        self.assertTrue(pub.import_text(self.root, self.source, commit(), keys, lambda u: raw))
        self.assertFalse(pub.import_text(self.root, self.source, commit('b'*40), keys, lambda u: raw))
    def test_empty_and_invalid_inputs(self):
        self.assertFalse(pub.import_text(self.root, self.source, commit(), set(), lambda u: b'---\nwp_status: publish\n---\n'))
        for raw in [b'---\nbroken', b'---\n- list\n---\nhello', b'---\nwp_status: future\n---\nhello']:
            with self.assertRaises(ValueError): pub.import_text(self.root, self.source, commit(), set(), lambda u: raw)
    def test_draft_is_not_published(self):
        pub.import_text(self.root, self.source, commit(), set(), lambda u: b'---\nwp_status: private\n---\nhello')
        meta,_=pub.split_frontmatter(next((self.root/'flux').glob('**/index.md')).read_text())
        self.assertEqual(meta['status'], 'draft')
    def test_flux_status_and_optional_title_are_independent_of_date(self):
        for i, (title, status) in enumerate([('', 'published'), ('我的标题: <随手记>', 'published'), ('草稿', 'draft')]):
            import yaml
            raw=('---\n'+yaml.safe_dump({'status':status,'title':title},allow_unicode=True)+'---\n正文').encode()
            pub.import_text(self.root,self.source,commit(str(i)*40),set(),lambda u:raw)
            path=next((self.root/'flux').glob(f'**/*-{str(i)*12}/index.md'))
            meta,body=pub.split_frontmatter(path.read_text())
            self.assertEqual(meta['title'],title or '18 Oct, 2026 08:00')
            self.assertEqual(meta['date'],'2026-10-18T08:00:00+08:00')
            self.assertEqual(meta['status'],status)
            self.assertEqual(body,'正文')
        with self.assertRaises(ValueError):
            pub.import_text(self.root,self.source,commit(),set(),lambda u:b'---\nstatus: published\ntitle: [invalid]\n---\nhello')
    def test_images_caption_scope_and_retry(self):
        self.source['path']='post/flux'
        rows=[{'filename': 'post/flux/a.PNG', 'status':'added'}, {'filename':'stills/b.png','status':'added'}, {'filename':'post/flux/deleted.png','status':'removed'}]
        keys=set()
        c=commit(message='feat\n\n配文 [链接](https://example.com)')
        self.assertEqual(pub.import_images(self.root,self.source,c,keys,rows,lambda u:IMAGE_BYTES),1)
        self.assertEqual(pub.import_images(self.root,self.source,c,pub.existing_keys(self.root),rows,lambda u:IMAGE_BYTES),0)
        p=next((self.root/'flux').glob('**/index.md'))
        self.assertIn('配文 [链接](https://example.com)',p.read_text())
        self.assertEqual((p.parent/'assets/image.webp').read_bytes(),IMAGE_BYTES)
    def test_media_failure_does_not_create_partial_entry(self):
        self.source['path']='post/flux'
        rows=[{'filename':'post/flux/a.png','status':'added'}]
        with self.assertRaises(ValueError): pub.import_images(self.root,self.source,commit(),set(),rows,lambda u:b'')
        self.assertEqual(list((self.root/'flux').glob('**/index.md')),[])
    def test_renamed_images_keep_historical_identity(self):
        self.source.update(path='post/flux', previous_paths=['post/stream'])
        rows=[{'filename':'post/flux/old.PNG','previous_filename':'post/stream/old.PNG','status':'renamed'},
              {'filename':'post/flux/new.png','status':'added'},
              {'filename':'post/2026/unrelated.png','status':'added'}]
        for key in ('asset-post-stream-old-png','asset:owner/repo:post/stream/old.PNG'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                self.assertEqual(pub.import_images(root,self.source,commit(),{key},rows,lambda u:IMAGE_BYTES),1)
                entry=next((root/'flux').glob('**/index.md')).read_text()
                self.assertIn('post/flux/new.png',entry)
                self.assertNotIn('old.PNG',entry)
    def test_folder_rename_keeps_cursor_in_parent_history(self):
        from urllib.parse import parse_qs,urlparse
        self.source.update(path='post/flux',history_path='post')
        def read(url):
            self.assertEqual(parse_qs(urlparse(url).query)['path'],['post'])
            return [commit('d'*40),commit('c'*40)]
        self.assertEqual([c['sha'] for c in pub.pending_commits(self.source,read)],['d'*40])
    def test_build_and_package_markdown_and_private_exclusion(self):
        (self.root/'scripts').mkdir()
        for name in ('build.py','package_site.py','ingest_github.py','image_inbox.py'): shutil.copy2(ROOT/'scripts'/name,self.root/'scripts'/name)
        (self.root/'site-assets').mkdir()
        (self.root/'style.css').write_text('')
        (self.root/'CNAME').write_text('flux.fivsevn.com')
        pub.import_text(self.root,self.source,commit(),set(),lambda u:'[链接](https://example.com)\n下一行\n\n- 第一\n- 第二\n\n> 引用'.encode())
        pub.import_text(self.root,self.source,commit('b'*40),set(),lambda u:b'---\nwp_status: draft\n---\nDRAFT_SENTINEL')
        import json
        (self.root/'.publishing').mkdir()
        (self.root/'.publishing/state.json').write_text(json.dumps({'sources': {'text': {**self.source, 'cursor': 'a'*40}}}))
        subprocess.run([sys.executable,str(self.root/'scripts/build.py')],check=True,capture_output=True)
        subprocess.run([sys.executable,str(self.root/'scripts/package_site.py')],check=True,capture_output=True)
        html=(self.root/'index.html').read_text()
        self.assertIn('<a href="https://example.com">链接</a>',html)
        self.assertIn('<br />',html)
        self.assertIn('<ul>',html)
        self.assertIn('<blockquote>',html)
        self.assertNotIn('DRAFT_SENTINEL',html)
        self.assertLess(html.index('class="brand"'),html.index('class="pocket-bubble"'))
        self.assertLess(html.index('class="pocket-bubble"'),html.index('class="nav"'))
        self.assertIn('This content is licensed under',html)
        self.assertEqual(len(list((self.root/'_site/page').glob('**/index.html'))),1)
        self.assertFalse((self.root/'_site/scripts').exists())
        receipt = json.loads((self.root/'_site/deployment.json').read_text())
        self.assertEqual(receipt['site_sha256'], (self.root/'.publishing/site.sha256').read_text().strip())
        self.assertEqual(len(receipt['files']), 2)
        self.assertNotIn('DRAFT_SENTINEL', json.dumps(receipt))
        # Editing the upper title updates both views without moving the page or
        # changing the lower publication timestamp.
        path=next(p for p in (self.root/'flux').glob('**/index.md') if 'DRAFT_SENTINEL' not in p.read_text())
        import yaml
        meta,body=pub.split_frontmatter(path.read_text())
        meta['title']='新标题 <测试>'
        page_path=self.root/'page/2026/10'/meta['id']/'index.html'
        path.write_text('---\n'+yaml.safe_dump(meta,allow_unicode=True)+'---\n'+body)
        subprocess.run([sys.executable,str(self.root/'scripts/build.py')],check=True,capture_output=True)
        for rendered in [(self.root/'index.html').read_text(),page_path.read_text()]:
            self.assertIn('新标题 &lt;测试&gt;',rendered)
            self.assertIn('2026-10-18T08:00:00+08:00',rendered)
            self.assertIn('/page/2026/10/'+meta['id']+'/',rendered)

if __name__=='__main__': unittest.main()
