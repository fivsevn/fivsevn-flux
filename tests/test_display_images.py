"""Exercise display media without changing archived images or authored layouts."""
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build
from site_post_metadata import dump_frontmatter, normalize_metadata
from support import copy_builder


class Images(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.images = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images.append(dict(attrs))


class DisplayImageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        copy_builder(self.root)

    def post(self, ident, filename, raw, status='published'):
        package = self.root / 'flux/2026/10' / ident
        (package / 'assets').mkdir(parents=True)
        source = package / 'assets' / filename
        source.write_bytes(raw)
        meta = normalize_metadata({'id': ident, 'title': ident, 'status': status,
                                   'date': '2026-10-18T08:00:00+08:00'}, site='flux')
        (package / 'index.md').write_text(dump_frontmatter(meta) + '\n![](assets/' + filename + ')\n')
        return source

    def feed_images(self):
        return Images((self.root / '_site/index.html').read_text()).images[1:]

    def test_static_preview_reduces_transfer_while_detail_and_archive_keep_original(self):
        data = BytesIO()
        Image.new('RGB', (2400, 1200), 'green').save(data, 'JPEG', quality=96)
        original = data.getvalue()
        source = self.post('photo', 'original.jpg', original)
        receipt = build.build(self.root)
        image, = self.feed_images()
        display = self.root / '_site' / image['src'].lstrip('/')
        self.assertTrue(image['src'].startswith('/display/'))
        self.assertLess(len(display.read_bytes()), len(original) // 2)
        self.assertEqual((image['width'], image['height']), ('2400', '1200'))
        self.assertEqual((image['loading'], image['decoding']), ('lazy', 'async'))
        with Image.open(display) as preview:
            self.assertEqual(preview.size, (1220, 610))
        detail = Images((self.root / '_site/page/2026/10/photo/index.html').read_text()).images[0]
        self.assertEqual(detail['src'], '/' + source.relative_to(self.root).as_posix())
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual((self.root / '_site' / source.relative_to(self.root)).read_bytes(), original)
        self.assertEqual(receipt['files'][display.relative_to(self.root / '_site').as_posix()],
                         hashlib.sha256(display.read_bytes()).hexdigest())

    def test_transparent_png_retains_alpha_and_uses_correct_orientation_and_dimensions(self):
        photo = Image.new('RGBA', (1800, 900), (25, 100, 200, 0))
        photo.paste((255, 0, 0, 255), (450, 225, 1350, 675))
        data = BytesIO()
        photo.save(data, 'PNG')
        self.post('transparent', 'diagram.png', data.getvalue())
        build.build(self.root)
        image, = self.feed_images()
        with Image.open(self.root / '_site' / image['src'].lstrip('/')) as preview:
            self.assertEqual(preview.size, (1220, 610))
            self.assertEqual(preview.convert('RGBA').getpixel((0, 0))[3], 0)
            self.assertEqual(preview.convert('RGBA').getpixel((610, 305)), (255, 0, 0, 255))
        data = BytesIO()
        oriented = Image.new('RGB', (2400, 1600), 'red')
        exif = Image.Exif()
        exif[274] = 6
        oriented.save(data, 'JPEG', exif=exif)
        self.post('oriented', 'portrait.jpg', data.getvalue())
        build.build(self.root)
        portrait = next(img for img in self.feed_images() if img['width'] == '1600')
        self.assertEqual(portrait['height'], '2400')
        with Image.open(self.root / '_site' / portrait['src'].lstrip('/')) as preview:
            self.assertEqual(preview.size, (1220, 1830))
            self.assertNotIn(274, preview.getexif())

    def test_gif_apng_and_webp_animations_are_not_flattened_or_reencoded(self):
        for suffix, format_name in [('gif', 'GIF'), ('png', 'PNG'), ('webp', 'WEBP')]:
            first = Image.new('RGBA', (32, 24), (255, 0, 0, 255))
            second = Image.new('RGBA', (32, 24), (0, 0, 255, 128))
            data = BytesIO()
            first.save(data, format_name, save_all=True, append_images=[second],
                       duration=[100, 240], loop=2)
            self.post(suffix, 'animation.' + suffix, data.getvalue())
        build.build(self.root)
        for image in self.feed_images():
            self.assertTrue(image['src'].endswith(('.gif', '.png', '.webp')))
            self.assertFalse(image['src'].startswith('/display/'))
            output = self.root / '_site' / image['src'].lstrip('/')
            source = self.root / image['src'].lstrip('/')
            self.assertEqual(output.read_bytes(), source.read_bytes())
            self.assertEqual((image['width'], image['height']), ('32', '24'))
            self.assertEqual(image['loading'], 'lazy')
            with Image.open(output) as animation:
                self.assertEqual(animation.n_frames, 2)
                self.assertEqual(animation.info.get('loop'), 2)
        self.assertFalse((self.root / '_site/display').exists())

    def test_mpo_auxiliary_photo_does_not_prevent_a_static_display_copy(self):
        first = Image.new('RGB', (2400, 1200), 'green')
        auxiliary = Image.new('RGB', (64, 32), 'gray')
        data = BytesIO()
        first.save(data, 'MPO', save_all=True, append_images=[auxiliary])
        source = self.post('hdr', 'phone.jpg', data.getvalue())
        with Image.open(source) as archive:
            self.assertEqual(archive.n_frames, 2)
        build.build(self.root)
        image, = self.feed_images()
        self.assertTrue(image['src'].startswith('/display/'))
        self.assertEqual((image['width'], image['height']), ('2400', '1200'))
        self.assertEqual((self.root / '_site' / source.relative_to(self.root)).read_bytes(), data.getvalue())

    def test_rebuild_is_deterministic_and_removes_obsolete_previews(self):
        data = BytesIO()
        Image.new('RGB', (2400, 1200), 'blue').save(data, 'JPEG', quality=96)
        source = self.post('changing', 'original.jpg', data.getvalue())
        first = build.build(self.root)
        old_display = self.feed_images()[0]['src']
        self.assertTrue(old_display.startswith('/display/'))
        self.assertEqual(first, build.build(self.root))
        replacement = BytesIO()
        Image.new('RGB', (3, 2), 'red').save(replacement, 'PNG')
        source.write_bytes(replacement.getvalue())
        build.build(self.root)
        self.assertFalse((self.root / '_site' / old_display.lstrip('/')).exists())
        self.assertEqual(source.read_bytes(), replacement.getvalue())
        meta_path = source.parent.parent / 'index.md'
        meta_path.write_text(meta_path.read_text().replace('status: published', 'status: hidden'))
        build.build(self.root)
        self.assertEqual(self.feed_images(), [])
        self.assertFalse((self.root / '_site/display').exists())
        self.assertFalse((self.root / '_site' / source.relative_to(self.root)).exists())

    def test_markup_entities_and_authored_image_size_are_preserved(self):
        fragment = '<a title="2 > 1">A &amp; B</a>\n<img src="/test.png" width="20" height="10" alt="A &amp; B" />'
        output = build.render_images(fragment, {'/test.png': {'src': '/display/test.webp', 'width': 200, 'height': 100}})
        self.assertTrue(output.startswith('<a title="2 > 1">A &amp; B</a>\n'))
        image, = Images(output).images
        self.assertEqual((image['width'], image['height']), ('20', '10'))
        self.assertEqual(image['alt'], 'A & B')
        self.assertEqual(image['src'], '/display/test.webp')
        external, = Images(build.render_images('<img src="https://example.test/image.png">', {})).images
        self.assertEqual(external['src'], 'https://example.test/image.png')
        self.assertEqual(external['loading'], 'lazy')


if __name__ == '__main__':
    unittest.main()
