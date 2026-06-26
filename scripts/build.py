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
<body>'''


def render_return_bubble():
    return '<a class="brand return-brand" href="/" data-return-home aria-label="return to flux">still typing...</a>'


def render_return_script():
    return '<script>\n(function () {\n  document.addEventListener("click", function (event) {\n    var link = event.target.closest("[data-return-home]");\n    if (!link) return;\n\n    try {\n      var ref = document.referrer ? new URL(document.referrer) : null;\n      if (ref && ref.origin === window.location.origin && window.history.length > 1) {\n        event.preventDefault();\n        window.history.back();\n      }\n    } catch (error) {}\n  });\n})();\n</script>'


items = []

for p in FLUX.glob("**/index.md"):
    fm, body = split_frontmatter(p.read_text(encoding="utf-8"))

    if fm.get("status", "published") in ["draft", "hidden"]:
        continue

    fm["_path"] = p.relative_to(ROOT).as_posix()
    fm["_dir"] = p.parent.relative_to(ROOT).as_posix()

    items.append((fm, body.strip()))

items.sort(key=lambda x: x[0].get("date", ""), reverse=True)

markdown = mistune.create_markdown(
    escape=False,
    plugins=["strikethrough", "table", "url"],
)

if PAGE.exists():
    shutil.rmtree(PAGE)

# Home page: all bubbles.
entries = []

for fm, body in items:
    entries.append(render_entry(fm, body, title_href=page_url(fm)))

home_doc = f'''{render_head("fivsevn flux", "Static flux mirror for fivsevn posts.")}
 <main class="site">
 <header class="topline">
 <a class="brand" href="/">typing</a>
 <nav class="nav" aria-label="links">
 <a href="https://fivsevn.com/posts/">source</a>
 <a href="https://github.com/fivsevn/fivsevn-flux">repo</a>
 </nav>
 </header>
 <section class="feed" aria-label="flux">
{chr(10).join(entries)}
 </section>
 <footer class="footer">generated from flux packages · {len(items)} posts</footer>
 </main>
</body>
</html>
'''

(ROOT / "index.html").write_text(home_doc, encoding="utf-8")

# Single pages: same bubble, one post per page.
for fm, body in items:
    out_dir = ROOT / page_rel_dir(fm)
    out_dir.mkdir(parents=True, exist_ok=True)

    ident = fm.get("id") or fm["_dir"].split("/")[-1]
    title = str(fm.get("title") or ident)

    post_doc = f'''{render_head(f"{title} · fivsevn flux", title)}
 <main class="site">
 {render_return_bubble()}
 <section class="feed" aria-label="flux">
{render_entry(fm, body, title_href=page_url(fm))}
 </section>
 </main>
{render_return_script()}
</body>
</html>
'''

    (out_dir / "index.html").write_text(post_doc, encoding="utf-8")

print(f"built index.html and {len(items)} page files")
