from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen
import mimetypes
import re

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg'}


def normalize_asset_url(url: str) -> str:
    """Normalize common GitHub asset URLs to directly downloadable URLs."""
    url = (url or '').strip()
    if not url:
        return url

    # https://github.com/fivsevn/fivsevn-assets/blob/main/path/file.webp
    m = re.match(r'^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)$', url)
    if m:
        owner, repo, branch, path = m.groups()
        return f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'

    # GitHub raw query wrapper variants are left as-is.
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


def download_asset(url: str, assets_dir: Path, index: int, prefix: str = 'image') -> tuple[str | None, str | None]:
    """Download one remote asset into assets_dir.

    Returns (relative_markdown_path, original_normalized_url). On failure returns (None, normalized_url).
    """
    normalized = normalize_asset_url(url)
    if not is_remote_url(normalized):
        return None, normalized

    assets_dir.mkdir(parents=True, exist_ok=True)
    req = Request(normalized, headers={'User-Agent': 'fivsevn-flux-importer/1.0'})
    try:
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type')
    except Exception as exc:
        print(f'[media] skip failed download: {normalized} ({exc})')
        return None, normalized

    ext = guess_ext(normalized, content_type)
    filename = f'{prefix}-{index:02d}{ext}'
    target = assets_dir / filename
    target.write_bytes(data)
    return f'./assets/{filename}', normalized


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
