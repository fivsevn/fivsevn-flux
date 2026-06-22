#!/usr/bin/env python3
from pathlib import Path
import re, html, yaml, mistune

ROOT = Path(__file__).resolve().parents[1]
FLUX = ROOT / 'flux'

def split_frontmatter(text):
    if not text.startswith('---'):
        return {}, text
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)

items=[]
for p in FLUX.glob('**/index.md'):
    fm, body = split_frontmatter(p.read_text(encoding='utf-8'))
    if fm.get('status','published') in ['draft','hidden']:
        continue
    fm['_path'] = p.relative_to(ROOT).as_posix()
    fm['_dir'] = p.parent.relative_to(ROOT).as_posix()
    items.append((fm, body.strip()))
items.sort(key=lambda x: x[0].get('date',''), reverse=True)

markdown = mistune.create_markdown(escape=False, plugins=['strikethrough','table','url'])
entries=[]
for fm, body in items:
    ident = fm.get('id') or fm['_dir'].split('/')[-1]
    title = fm.get('title') or ident
    html_body = markdown(body) if body else ''
    meta = f".\n\ntags: {', '.join(fm.get('tags') or [])}\n\ncomment:\n\n{fm.get('comments', 0)}\n\n{fm.get('date','')}"
    entries.append(f'''<article class="entry" id="{html.escape(str(ident))}">
  <h2 class="entry-title"><a href="#{html.escape(str(ident))}">{html.escape(str(title))}</a></h2>
  <div class="entry-body">{html_body}</div>
  <div class="meta">{html.escape(meta)}</div>
</article>''')

doc = f'''<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>fivsevn flux</title>
  <meta name="description" content="Static flux mirror for fivsevn posts.">
  <link rel="stylesheet" href="./style.css">
</head>
<body>
  <main class="site">
    <header class="topline">
      <a class="brand" href="./">typing…</a>
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
(ROOT / 'index.html').write_text(doc, encoding='utf-8')
print(f'built index.html with {len(items)} posts')
