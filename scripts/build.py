#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlparse
import argparse
import hashlib
import html
import json
import re
import shutil

import mistune

from ingest_github import split_frontmatter
from image_inbox import candidates
from site_post_metadata import is_published, metadata_view, published_datetime, validate_metadata


ROOT = Path(__file__).resolve().parents[1]
PER_PAGE = 11


markdown = mistune.create_markdown(
    escape=False,
    plugins=["strikethrough", "table", "url"],
)


trigger_markdown = mistune.create_markdown(escape=False, hard_wrap=True, plugins=["strikethrough", "table", "url"])


def rewrite_local_asset_paths(rendered_html, item_dir):
    def normalize_url(url):
        if not url:
            return url

        parsed = urlparse(url)
        if parsed.scheme or url.startswith("#") or url.startswith("//") or url.startswith("/"):
            return url

        if url.startswith("./assets/"):
            return f"/{item_dir}/{url[2:]}"

        if url.startswith("assets/"):
            return f"/{item_dir}/{url}"

        return url

    def replace_attr(match):
        before, url, after = match.group(1), match.group(2), match.group(3)
        fixed = normalize_url(html.unescape(url))
        return f'{before}{html.escape(fixed, quote=True)}{after}'

    rendered_html = re.sub(
        r'(<img\b[^>]*?\bsrc=")([^"]+)(")',
        replace_attr,
        rendered_html,
        flags=re.I,
    )

    rendered_html = re.sub(
        r'(<a\b[^>]*?\bhref=")([^"]+)(")',
        replace_attr,
        rendered_html,
        flags=re.I,
    )

    return rendered_html


def page_rel_dir(fm):
    parts = fm["_dir"].split("/")
    if len(parts) >= 4 and parts[0] == "flux":
        _, year, month, ident = parts[:4]
        return f"page/{year}/{month}/{ident}"

    ident = fm.get("id") or parts[-1]
    return f"page/{ident}"


def page_url(fm):
    return f"/{page_rel_dir(fm)}/"


def feed_url(page_number):
    if page_number <= 1:
        return "/"
    return f"/feed/{page_number}/"


def render_entry(fm, body, title_href=None):
    ident = fm.get("id") or fm["_dir"].split("/")[-1]
    title = fm.get("title") or ident
    date = fm.get("date", "")

    renderer = trigger_markdown if fm.get("source") in {"github-trigger", "github-image"} else markdown
    html_body = renderer(body) if body else ""
    html_body = rewrite_local_asset_paths(html_body, fm["_dir"])

    title_text = html.escape(str(title))
    if title_href:
        title_html = f'<a href="{html.escape(title_href, quote=True)}">{title_text}</a>'
    else:
        title_html = title_text

    timestamp = ""
    if date:
        date_text = html.escape(str(date))
        timestamp = f'\n <div class="entry-meta"><time datetime="{date_text}">{date_text}</time></div>'

    return f'''<article class="entry" id="{html.escape(str(ident))}">
 <h2 class="entry-title">{title_html}</h2>
 <div class="entry-body">{html_body}</div>{timestamp}
</article>'''


def render_head(title, description):
    return f'''<!doctype html>
<html lang="zh-Hans">
<head>
 <meta charset="utf-8">
 <meta name="viewport" content="width=device-width, initial-scale=1">
 <title>{html.escape(title)}</title>
 <meta name="description" content="{html.escape(description, quote=True)}">
 <link rel="stylesheet" href="/style.css">
</head>
<body>
<main class="site">
'''


def render_close(extra="", navigation_version=""):
    navigation = "/site-assets/navigation.js" + ("?v=" + navigation_version if navigation_version else "")
    return f'''{extra}
<script src="{navigation}"></script>
</main>
</body>
</html>
'''


def render_brand():
    return '<a class="brand" href="/" aria-label="typing">typing...</a>'


def render_return_bubble(href="/"):
    return f'<a class="brand return-brand" href="{html.escape(href, quote=True)}" aria-label="still typing">still typing...</a>'


def render_nav_bubble():
    return '''<div class="nav">??? 分享了一条链接：[ <a href="https://devlog.fivsevn.com/posts/">内容仓库</a> ]</div>'''


def render_pocket_bubble():
    return '<div class="pocket-bubble"><a href="https://fivsevn.com/" aria-label="五月七日主页"><img src="/site-assets/pocket.webp" alt="布口袋" width="125"></a></div>'


def render_license_bubble():
    return '<footer class="entry license-bubble"><div class="entry-body">This content is licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a>.</div></footer>'


def render_feed_header():
    # Every feed page follows the same chat-message sequence.
    return f'''{render_brand()}
{render_pocket_bubble()}
{render_nav_bubble()}'''

def render_pager(current_page, total_pages):
    if total_pages <= 1:
        return ""

    parts = ['<span class="pager-label">Zzz...</span>']

    def add_page(page_number):
        label = str(page_number)
        if page_number == current_page:
            parts.append(f'<span class="pager-current" aria-current="page">{label}</span>')
        else:
            parts.append(f'<a href="{feed_url(page_number)}">{label}</a>')

    def add_gap():
        if parts[-1] != '<span class="pager-gap">…</span>':
            parts.append('<span class="pager-gap">…</span>')

    if total_pages <= 7:
        for page_number in range(1, total_pages + 1):
            add_page(page_number)
    else:
        add_page(1)

        start = max(2, current_page - 2)
        end = min(total_pages - 1, current_page + 2)

        if current_page <= 4:
            start = 2
            end = 6

        if current_page >= total_pages - 3:
            start = total_pages - 5
            end = total_pages - 1

        if start > 2:
            add_gap()

        for page_number in range(start, end + 1):
            add_page(page_number)

        if end < total_pages - 1:
            add_gap()

        add_page(total_pages)

    if current_page < total_pages:
        parts.append(f'<a href="{feed_url(current_page + 1)}" aria-label="older">»</a>')

    return f'<nav class="pager" aria-label="pagination">{" ".join(parts)}</nav>'


def render_feed_page(page_items, current_page, total_pages, navigation_version=""):
    entries = [render_entry(fm, body, title_href=page_url(fm)) for fm, body in page_items]
    pager = render_pager(current_page, total_pages)
    return f'''{render_head("flux.fivsevn", "五月七日的思考札记")}
{render_feed_header()}
<section class="feed" aria-label="flux">
{chr(10).join(entries)}
{pager}
</section>
{render_close(render_license_bubble(), navigation_version)}'''


def read_posts(root):
    items = []
    seen = set()
    for source in sorted((root / "flux").glob("**/index.md")):
        canonical, body = split_frontmatter(source.read_text(encoding="utf-8"))
        validate_metadata(canonical, site="flux", schema_dir=root / "schemas")
        if canonical["id"] in seen:
            raise ValueError(f"Duplicate post ID: {canonical['id']}")
        seen.add(canonical["id"])
        if not is_published(canonical):
            continue
        meta = metadata_view(canonical)
        if meta["id"] != source.parent.name:
            raise ValueError(f"Post ID does not match its package: {source}")
        meta["_path"] = source.relative_to(root).as_posix()
        meta["_dir"] = source.parent.relative_to(root).as_posix()
        meta["_published"] = published_datetime(canonical)
        items.append((meta, body.strip()))
    return sorted(items, key=lambda item: (item[0]["_published"], item[0]["id"]), reverse=True)


def navigation_script(items, root=ROOT):
    # Old feed bookmarks may place an anchor on a different page after pagination changes.
    pages = {meta["id"]: feed_url(index // PER_PAGE + 1) for index, (meta, _) in enumerate(items)}
    return ("const fluxPostPages = " + json.dumps(pages, ensure_ascii=False, separators=(",", ":"))
            + ";\n" + (Path(root) / "site-assets/navigation.js").read_text(encoding="utf-8"))


def make_receipt(root, output, items):
    state_path = root / ".publishing/state.json"
    sources = json.loads(state_path.read_text())["sources"] if state_path.exists() else {}
    receipt = {
        "version": 1,
        "sources": {kind: {key: source[key] for key in ("repository", "path", "cursor")}
                    for kind, source in sources.items()},
        "files": {"index.html": hashlib.sha256((output / "index.html").read_bytes()).hexdigest()},
    }
    for meta, _ in items:
        if any(meta.get("source_repository") == source["repository"]
               and meta.get("source_commit") in source.get("verification_commits", [source["cursor"]])
               for source in sources.values()):
            page = Path(page_rel_dir(meta)) / "index.html"
            receipt["files"][page.as_posix()] = hashlib.sha256((output / page).read_bytes()).hexdigest()
            for asset in (root / meta["_dir"] / "assets").rglob("*"):
                if asset.is_file():
                    relative = asset.relative_to(root)
                    receipt["files"][relative.as_posix()] = hashlib.sha256((output / relative).read_bytes()).hexdigest()
    if sources.get("images"):
        for _, archived, page in candidates(root):
            for public in (archived, page):
                receipt["files"][public.as_posix()] = hashlib.sha256((output / public).read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for path in sorted(output.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(output).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
    digest.update(json.dumps(receipt, sort_keys=True).encode())
    receipt["site_sha256"] = digest.hexdigest()
    (output / "deployment.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    return receipt


def build(root=ROOT, output=None):
    root = Path(root).resolve()
    output = Path(output or root / "_site").resolve()
    if output == root or root.is_relative_to(output) or output.is_relative_to(root / "flux"):
        raise ValueError("Unsafe build output path")
    items = read_posts(root)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in ("style.css", "CNAME"):
        if (root / name).is_file():
            shutil.copy2(root / name, output / name)
    if (root / "site-assets").exists():
        shutil.copytree(root / "site-assets", output / "site-assets")
    (output / "site-assets").mkdir(exist_ok=True)
    navigation = navigation_script(items, root)
    (output / "site-assets/navigation.js").write_text(navigation, encoding="utf-8")
    navigation_version = hashlib.sha256(navigation.encode()).hexdigest()[:12]
    (output / ".nojekyll").touch()
    total_pages = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
    for number in range(1, total_pages + 1):
        document = render_feed_page(items[(number - 1) * PER_PAGE:number * PER_PAGE], number, total_pages, navigation_version)
        relative = Path("index.html") if number == 1 else Path("feed", str(number), "index.html")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
    for index, (meta, body) in enumerate(items):
        destination = output / page_rel_dir(meta)
        destination.mkdir(parents=True, exist_ok=True)
        title = str(meta.get("title") or meta["id"])
        return_url = feed_url(index // PER_PAGE + 1) + "#" + meta["id"]
        document = f"""{render_head(f"{title} · flux.fivsevn", title)}
{render_return_bubble(return_url)}
<section class="feed" aria-label="single flux">
{render_entry(meta, body, title_href=page_url(meta))}
</section>
{render_close(render_license_bubble(), navigation_version)}"""
        (destination / "index.html").write_text(document, encoding="utf-8")
        assets = root / meta["_dir"] / "assets"
        if assets.exists():
            if any(path.is_symlink() for path in assets.rglob("*")):
                raise ValueError(f"Package assets must not follow symlinks: {assets}")
            shutil.copytree(assets, output / assets.relative_to(root))
    receipt = make_receipt(root, output, items)
    print(f"Built {len(items)} published posts / {total_pages} feed pages → {output}")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Flux directly into its Git-ignored Pages artifact.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    build(arguments.root, arguments.output)
