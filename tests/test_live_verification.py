import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_live import verify_once


class LiveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.page = '真实正文'.encode()
        self.receipt = {'version': 1, 'site_sha256': 'abc', 'sources': {},
                        'files': {'index.html': hashlib.sha256(self.page).hexdigest()}}

    def test_receipt_and_page_must_both_match(self):
        urls = []
        def read(url):
            urls.append(url)
            return json.dumps(self.receipt).encode() if '/deployment.json?' in url else self.page
        verify_once('https://example.com', self.receipt, read)
        self.assertEqual(len(urls), 2)
        self.assertTrue(all('?flux_verify=abc' in url for url in urls))

    def test_stale_success_receipt_is_rejected(self):
        stale = {**self.receipt, 'site_sha256': 'previous'}
        with self.assertRaisesRegex(ValueError, 'another deployment'):
            verify_once('https://example.com', self.receipt, lambda _: json.dumps(stale).encode())

    def test_wrong_page_is_rejected_even_when_receipt_matches(self):
        def read(url):
            return json.dumps(self.receipt).encode() if '/deployment.json?' in url else b'old page'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            verify_once('https://example.com', self.receipt, read)


if __name__ == '__main__':
    unittest.main()
