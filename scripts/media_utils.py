from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, unquote, urlunparse
from urllib.request import Request, urlopen
import mimetypes
import re

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg'}


def strip_query_fragment(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))


def normalize_asset_url(url: str) -> str:
    """Normalize common image URLs to the closest original, directly downloadable URL.

    Important cases:
    - github.com/.../blob/main/file -> raw.githubusercontent.com/.../main/file
    - cdn.jsdelivr.net/gh/fivsevn/fivsevn-assets@main/file -> raw.githubusercontent.com/fivsevn/fivsevn-assets/main/file
    - cdn.jsdelivr.net/gh/fivsevn/fivsevn-assets/file -> raw.githubusercontent.com/fivsevn/fivsevn-assets/main/file
    - query strings are removed for stable filenames and original downloads when safe.
    """
    url = (url or '').strip().strip('"\'')
    if not url:
        return url

    # Decode HTML escaped ampersands if they leaked through markdown conversion.
    url = url.replace('&amp;', '&')

    # https://github.com/fivsevn/fivsevn-assets/blob/main/path/file.webp
    m = re.match(r'^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)$', url)
    if m:
        owner, repo, branch, path = m.groups()
        return f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'

    # https://cdn.jsdelivr.net/gh/fivsevn/fivsevn-assets@main/path/file.webp
    m = re.match(r'^https://cdn\.jsdelivr\.net/gh/([^/]+)/([^/@]+)(?:@([^/]+))?/(.*)$', url)
    if m:
        owner, repo, branch, path = m.groups()
        branch = branch or 'main'
        return f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'

    # For common image CDN links, remove resize/cache query parameters so we fetch the cleanest URL.
    if is_remote_url(url):
        parsed = urlparse(url)
        if parsed.query and Path(unquote(parsed.path)).suffix.lower() in IMAGE_EXTS:
            return strip_query_fragment(url)

    return url


def is_remote_url(url: str) -> bool:
    return url.startswith('http://') or url.startswith('https://')


def guess_ext(url: str, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    ext = Path(unquote(parsed.path)).suffix.lower()
    if ext in IMAGE_EXTS:
        return ext
    if content_type:
        content_type = content_type.split(';', 1)[0].strip().lower()
        ext = mimetypes.guess_extension(content_type) or ''
        if ext == '.jpe':
            ext = '.jpg'
        if ext in IMAGE_EXTS:
            return ext
    return '.bin'


def filename_from_url(url: str, index: int, content_type: str | None = None, prefix: str = 'image') -> str:
    ext = guess_ext(url, content_type)
    parsed = urlparse(url)
    stem = Path(unquote(parsed.path)).stem
    stem = re.sub(r'[^A-Za-z0-9._-]+', '-', stem).strip('-._')
    if not stem or len(stem) > 80:
        stem = f'{prefix}-{index:02d}'
    return f'{index:02d}-{stem}{ext}'


def download_asset(url: str, assets_dir: Path, index: int, prefix: str = 'image', overwrite: bool = True, target_name: str | None = None) -> tuple[str | None, str | None]:
    """Download one remote asset into assets_dir.

    Returns (relative_markdown_path, normalized_source_url). On failure returns (None, normalized_url).
    """
    normalized = normalize_asset_url(url)
    if not is_remote_url(normalized):
        return None, normalized

    assets_dir.mkdir(parents=True, exist_ok=True)
    req = Request(normalized, headers={'User-Agent': 'fivsevn-flux-media/1.2'})
    try:
        with urlopen(req, timeout=45) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type')
    except Exception as exc:
        print(f'[media] skip failed download: {normalized} ({exc})')
        return None, normalized

    filename = target_name or filename_from_url(normalized, index, content_type, prefix)
    target = assets_dir / filename
    if target.exists() and not overwrite:
        return f'./assets/{filename}', normalized
    target.write_bytes(data)
    return f'./assets/{filename}', normalized


def parse_srcset(srcset: str) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    for part in (srcset or '').split(','):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        u = bits[0]
        width = 0
        for bit in bits[1:]:
            m = re.match(r'^(\d+)w$', bit)
            if m:
                width = int(m.group(1))
        candidates.append((u, width))
    return candidates


def best_img_url(img) -> str:
    """Pick the best original-ish URL from a BeautifulSoup img tag.

    WordPress often keeps original URLs in data-orig-file / data-full-url, while src can be a resized thumbnail. For GitHub/jsDelivr assets, src itself is already the source object.
    """
    priority_attrs = [
        'data-orig-file',
        'data-full-url',
        'data-large-file',
        'data-src',
        'data-lazy-src',
    ]
    for attr in priority_attrs:
        val = img.get(attr)
        if val and is_remote_url(val):
            return val

    srcset = img.get('srcset') or img.get('data-srcset')
    candidates = parse_srcset(srcset)
    if candidates:
        # Largest width first. Unknown width stays below known sizes.
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates[0][0]:
            return candidates[0][0]

    return img.get('src') or ''


def localize_markdown_images(markdown_text: str, package_dir: Path) -> tuple[str, list[dict]]:
    """Download remote markdown image URLs and replace them with package-local paths."""
    assets_dir = package_dir / 'assets'
    media: list[dict] = []
    counter = 0

    def repl(match: re.Match) -> str:
        nonlocal counter
        alt = match.group(1)
        url = match.group(2).strip()
        # Leave local/package-relative links alone.
        if not is_remote_url(url):
            return match.group(0)
        counter += 1
        local, original = download_asset(url, assets_dir, counter)
        if local:
            media.append({'file': local, 'source': original})
            return f'![{alt}]({local})'
        return match.group(0)

    # Markdown image form: ![alt](url)
    markdown_text = re.sub(r'!\[([^\]]*)\]\((https?://[^)\s]+)\)', repl, markdown_text)
    return markdown_text, media


def refresh_local_media_from_frontmatter(fm: dict, package_dir: Path) -> list[dict]:
    """Re-download local ./assets files from their recorded original source.

    This repairs earlier runs that localized thumbnails or cached CDN variants.
    """
    refreshed: list[dict] = []
    media = fm.get('media') or []
    if not isinstance(media, list):
        return refreshed
    assets_dir = package_dir / 'assets'
    for i, item in enumerate(media, start=1):
        if not isinstance(item, dict):
            continue
        src = item.get('source') or item.get('original') or item.get('url')
        local_file = item.get('file')
        if not src or not local_file or not is_remote_url(src):
            continue
        target_name = Path(str(local_file).replace('./assets/', '')).name
        local, original = download_asset(src, assets_dir, i, overwrite=True, target_name=target_name)
        if local:
            item['file'] = local
            item['source'] = original
            refreshed.append({'file': local, 'source': original})
    return refreshed
