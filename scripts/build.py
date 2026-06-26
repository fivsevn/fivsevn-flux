#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlparse
import html
import re
import shutil

import mistune
import yaml


ROOT = Path(__file__).resolve().parents[1]
FLUX = ROOT / "flux"
PAGE = ROOT / "page"
FEED = ROOT / "feed"
PER_PAGE = 17


markdown = mistune.create_markdown(
    escape=False,
    plugins=["strikethrough", "table", "url"],
)


def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text

    return yaml.safe_load(m.group(1)) or {}, m.group(2)


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

    html_body = markdown(body) if body else ""
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


def render_close(extra=""):
    return f'''{extra}
</main>
</body>
</html>
'''


def render_brand():
    return '<a class="brand" href="/" aria-label="typing">typing...</a>'


def render_return_bubble():
    return '<a class="brand return-brand" href="/" onclick="return goBackHome(event)" aria-label="still typing">still typing...</a>'


def render_return_script():
    return '''<script>
function goBackHome(event) {
  try {
    const ref = document.referrer ? new URL(document.referrer) : null;
    const sameSite = ref && ref.origin === window.location.origin;
    if (sameSite && window.history.length > 1) {
      event.preventDefault();
      window.history.back();
      return false;
    }
  } catch (e) {}
  return true;
}
</script>'''


def render_nav_bubble():
    return '''<div class="nav">??? 分享了一条链接：[ <a href="https://devlog.fivsevn.com/posts/">内容仓库</a> ]</div>'''

def render_pager(current_page, total_pages):
    if total_pages <= 1:
        return ""

    parts = ['<span class="pager-label">Zzz...</span>']
    for page_number in range(1, total_pages + 1):
        label = str(page_number)
        if page_number == current_page:
            parts.append(f'<span class="pager-current" aria-current="page">{label}</span>')
        else:
            parts.append(f'<a href="{feed_url(page_number)}">{label}</a>')

    if current_page < total_pages:
        parts.append(f'<a href="{feed_url(current_page + 1)}" aria-label="older">»</a>')

    return f'<nav class="pager" aria-label="pagination">{" ".join(parts)}</nav>'


def render_feed_page(page_items, current_page, total_pages):
    entries = [render_entry(fm, body, title_href=page_url(fm)) for fm, body in page_items]
    pager = render_pager(current_page, total_pages)
    return f'''{render_head("fivsevn flux", "Static flux mirror for fivsevn posts.")}
{render_brand()}
{render_nav_bubble()}
<section class="feed" aria-label="flux">
{chr(10).join(entries)}
{pager}
</section>
{render_close()}'''


items = []

for p in FLUX.glob("**/index.md"):
    fm, body = split_frontmatter(p.read_text(encoding="utf-8"))

    if fm.get("status", "published") in ["draft", "hidden"]:
        continue

    fm["_path"] = p.relative_to(ROOT).as_posix()
    fm["_dir"] = p.parent.relative_to(ROOT).as_posix()

    items.append((fm, body.strip()))

items.sort(key=lambda x: x[0].get("date", ""), reverse=True)

if PAGE.exists():
    shutil.rmtree(PAGE)

if FEED.exists():
    shutil.rmtree(FEED)

# Feed pages.
total_pages = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)

for page_number in range(1, total_pages + 1):
    start = (page_number - 1) * PER_PAGE
    end = start + PER_PAGE
    page_items = items[start:end]
    doc = render_feed_page(page_items, page_number, total_pages)

    if page_number == 1:
        (ROOT / "index.html").write_text(doc, encoding="utf-8")
    else:
        out_dir = FEED / str(page_number)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(doc, encoding="utf-8")

# Single pages: same bubble, one post per page.
for fm, body in items:
    out_dir = ROOT / page_rel_dir(fm)
    out_dir.mkdir(parents=True, exist_ok=True)

    ident = fm.get("id") or fm["_dir"].split("/")[-1]
    title = str(fm.get("title") or ident)

    post_doc = f'''{render_head(f"{title} · fivsevn flux", title)}
{render_return_bubble()}
<section class="feed" aria-label="single flux">
{render_entry(fm, body, title_href=page_url(fm))}
</section>
{render_close(render_return_script())}'''

    (out_dir / "index.html").write_text(post_doc, encoding="utf-8")

print(f"built index.html, {total_pages - 1} feed pages, and {len(items)} page files")
