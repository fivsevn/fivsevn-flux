# fivsevn-flux

Static flux source for `flux.fivsevn.com`.

## Structure

Each update is one package:

```text
flux/YYYY/MM/YYYY-MM-DD-HHMMSS/
├─ index.md
└─ assets/
```

Edit `index.md`. Put images or other files for that update in the same package's `assets/` folder.

Example:

```markdown
---
id: 2026-06-22-190045
date: 2026-06-22T19:00:45+08:00
title: "22 Jun, 2026 19:00"
source: wordpress-live
sync: auto
source_hash: abcdef1234567890
status: published
---

正文。

![image](./assets/image-01.webp)
```

## Sync modes

`sync` controls whether the live WordPress page is still allowed to update this package.

```yaml
sync: auto
```

The package still follows WordPress. If the same WordPress post changes, the scheduled action updates this package.

```yaml
sync: manual
```

The package is now owned by this repository. The scheduled action will not overwrite it.

Use `manual` before editing an old post directly in GitHub.

## Build

```bash
pip install -r requirements.txt
python scripts/build.py
```

This regenerates `index.html` from every `flux/**/index.md` file.

## Import from WordPress export

```bash
python scripts/import-wxr.py WordPress.2026-06-22.xml
python scripts/build.py
```

The importer is safe by default: it skips packages that already exist. Use `--force` only when you intentionally want to overwrite existing imported packages.

By default, the importer downloads remote images into each package's `assets/` folder and rewrites image paths to local package paths.

To import without downloading images:

```bash
python scripts/import-wxr.py WordPress.2026-06-22.xml --no-media
```

## Sync live WordPress posts

The repository includes a scheduled GitHub Action:

```text
.github/workflows/sync-live.yml
```

It runs every 6 hours and can also be run manually from GitHub Actions. The workflow runs:

```bash
python scripts/sync-from-live.py --limit 80
python scripts/build.py
```

The sync script now handles both new and changed WordPress posts:

```text
new WordPress post → create flux/YYYY/MM/{id}/index.md
existing package + sync:auto + changed source_hash → update package
existing package + sync:manual → skip, never overwrite
```

It tries the WordPress REST API first, then falls back to parsing `https://fivsevn.com/posts/`.

## Localize images in existing packages

If `index.md` files already contain remote image links, run:

```bash
python scripts/localize-media.py
python scripts/build.py
```

This scans `flux/**/index.md`, downloads remote Markdown images into each package's own `assets/` folder, and rewrites links like:

```markdown
![image](https://raw.githubusercontent.com/fivsevn/fivsevn-assets/main/example.webp)
```

into:

```markdown
![image](./assets/image-01.webp)
```

It also understands GitHub blob URLs and converts them to raw download URLs automatically.

## GitHub Pages

Set the repository Pages source to the `main` branch root, or use the generated `index.html` directly. `CNAME` is already set to:

```text
flux.fivsevn.com
```
## Media hydration

This package may contain remote image links in existing `flux/**/index.md` files. To copy those images into each post package:

1. Push this repo to GitHub.
2. Open **Actions → Hydrate media → Run workflow**.
3. The workflow runs `scripts/localize-media.py`, downloads remote Markdown images into each package's `assets/` folder, rewrites links to `./assets/...`, rebuilds `index.html`, and commits the result.

The normal live sync workflow also runs media localization after importing new WordPress items.

