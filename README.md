# fivsevn-flux

Static archive for `flux.fivsevn.com`.

Content is stored as flux packages under the `flux/` directory. Each package represents one post.

```text
flux/YYYY/MM/{id}/index.md
flux/YYYY/MM/{id}/assets/
```

## Content

Each post package contains:

- `index.md` for the post content and metadata
- `assets/` for images and other media used by that post

The `index.md` file is the editable source for each post.

## Sync

Published WordPress posts from `https://fivsevn.com/posts/` can be synchronized into this repository.

Packages marked as:

```yaml
sync: auto
```

may be updated by the WordPress sync process.

Packages marked as:

```yaml
sync: manual
```

are treated as repository-owned content and are not overwritten by normal sync.

## Media

Post media is stored locally in each package’s `assets/` directory when possible.

This keeps each post self-contained and reduces reliance on remote WordPress media URLs.

## Build

The site index is generated from the packages under `flux/`.

```bash
python scripts/build.py
```

The generated output is written to:

```text
index.html
```

## Scripts

```text
scripts/sync-from-live.py   Sync published WordPress posts
scripts/localize-media.py   Download and rewrite post media
scripts/build.py            Generate the static index
scripts/media_utils.py      Shared media helpers
scripts/import-wxr.py       Import posts from a WordPress export file
```

## GitHub Actions

GitHub Actions handle regular WordPress sync, full rescans, media localization, and index rebuilding.

Manual editing can be done directly in the post package files under `flux/`.

## Domain

The site is served from:

```text
flux.fivsevn.com
```
