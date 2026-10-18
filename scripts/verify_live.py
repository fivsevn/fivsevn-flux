"""Confirm that the public domain serves this artifact before reporting success."""
from pathlib import Path
import hashlib
import json
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    request = Request(url, headers={'User-Agent': 'fivsevn-flux-verifier/1',
                                    'Cache-Control': 'no-cache'})
    with urlopen(request, timeout=15) as response:
        return response.read()


def verify_once(base_url, expected, read=fetch):
    query = '?flux_verify=' + expected['site_sha256']
    actual = json.loads(read(base_url.rstrip('/') + '/deployment.json' + query))
    if actual != expected:
        raise ValueError('The public domain is still serving another deployment')
    for path, digest in expected['files'].items():
        url = base_url.rstrip('/') + '/' + quote(path) + query
        if hashlib.sha256(read(url)).hexdigest() != digest:
            raise ValueError(f'The public file does not match the deployed artifact: {path}')


def main():
    expected = json.loads((ROOT / '_site/deployment.json').read_text())
    domain = (ROOT / 'CNAME').read_text().strip()
    for attempt in range(12):
        try:
            verify_once('https://' + domain, expected)
            print(f'Confirmed live artifact {expected["site_sha256"]} and {len(expected["files"])} public files at {domain}.')
            return
        except (URLError, TimeoutError, ValueError) as error:
            if attempt == 11:
                raise
            print(f'Waiting for the public deployment: {error}', flush=True)
            time.sleep(5)


if __name__ == '__main__':
    main()
