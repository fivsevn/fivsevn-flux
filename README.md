---
id: flux-readme
title: Flux publishing and maintenance

module: posts
submodule: root
topic: guide

type: note
status: active
canonical: true

summary: Publishing, validation, and maintenance for flux.

parents: []
related: []

tags:
- flux

audience:
- self
- internal
languages:
- en

maturity: evolving
confidence: null

visibility: public
source_of_truth: site

filename_policy: entrypoint

created: null
updated: '2026-10-30'
metadata_updated: '2026-10-30'
---
# flux.fivsevn

Flux is the short-form section of [fivsevn.com](https://fivsevn.com/): thoughts, photographs, and links. Its public address is [flux.fivsevn.com](https://flux.fivsevn.com/). This repository owns the publishing inputs, editable post packages, and GitHub Pages workflow.

Publish text through [`trigger_text.md`](trigger_text.md) and photos through [`trigger_imgs/`](trigger_imgs/). The image inbox has a [short Chinese guide](trigger_imgs/README.md). This README describes the complete publishing and maintenance contract in English.

## Repository layout

```text
trigger_text.md                  Text publishing input
trigger_imgs/                    Temporary photo-upload inbox
  README.md                      Short Chinese upload instructions
flux/YYYY/MM/{id}/
  index.md                       Canonical metadata and Markdown body
  assets/                        Media owned by this post
scripts/
  site_post_metadata.py          Shared offline metadata helper
  ingest_github.py               Read committed trigger snapshots
  build.py                       Build the complete Pages artifact once
  verify_live.py                 Compare public pages and media bytes
  image_inbox.py                 Clear verified matching inbox originals
schemas/
  content-metadata.schema.json   Shared fivsevn core schema
  site-post.schema.json          Site-post profile
site-assets/                     Shared images and interface assets
style.css                        Flux presentation
.publishing/
  state.json                     Input cursors and verification batches
  deployed.sha256                Last verified public artifact fingerprint
tests/                           Publishing, metadata, rendering, and cleanup checks
.github/workflows/build.yml      The single Build and deploy Flux workflow
_site/                           Generated Pages artifact; ignored by Git
```

Saved Markdown and package media are the editable source. HTML, navigation data, deployment receipts, and copied public media are generated only inside `_site/`. Build output is never committed alongside source posts.

## Publish a text entry

1. Pull the latest `main`.
2. Open [`trigger_text.md`](trigger_text.md). Keep its frontmatter and set the optional controls:

   ```yaml
   status: published
   title: ""
   ```

3. Replace the body after the closing `---` with the new entry. Markdown links, lists, quotes, tables, and images are supported.
4. Commit and push the changed trigger to `main`.
5. Wait for [Build and deploy Flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) to finish, then check the list and individual post.

An empty title uses the source commit's committer time in `Asia/Shanghai`, such as `30 Oct, 2026 18:00`. A nonempty title supplies the displayed heading. The exact publication timestamp is stored separately and controls chronological order. The commit summary is an operation label, not the post title.

Use `status: draft`, `hidden`, or `private` to keep a trigger-created package out of the public artifact. Explicit visibility and status controls are retained when metadata is completed. Additional shared core controls, such as `tags`, may be supplied in the trigger; ordinary posting needs only status, optional title, and body.

Each committed change to a nonempty text trigger is a new publishing event. Edit an existing saved package to revise a post. Maintenance edits to the trigger's instruction comments can also create an event if its body remains nonempty; keep documentation changes in the README when possible.

## Publish images

### Configure a phone shortcut

1. Select **fivsevn-flux** as the Working Copy repository.
2. Pull or sync `main` before saving each upload.
3. Save photos into [`trigger_imgs/`](trigger_imgs/) with their original filenames.
4. Commit and push to this repository's `main` branch.
5. If the shortcut collects a caption, write it to the commit's **extended description**, below the summary line.

### Upload through GitHub

1. Open the [image upload page](https://github.com/fivsevn/fivsevn-flux/upload/main/trigger_imgs).
2. Select the images and retain their original filenames.
3. Write an optional Markdown caption in the commit's extended description; leave it empty for image-only posts.
4. Commit to `main`, wait for Build and deploy Flux, and check the public list, individual page, and displayed image.

Each image path in an upload commit creates one independent post. A batch shares its optional caption. Publication time comes from the upload commit's committer timestamp, converted to `Asia/Shanghai`. The default heading uses that time; edit the saved `title` to customize it later.

Package IDs combine the timestamp with a stable digest of the upload commit and path. New saved media uses `assets/YYYYMMDD-HHMMSS-NN.webp`, with stable batch numbers assigned from sorted paths. A retry reuses the saved event and preserves later edits. A new upload commit creates a new post, including when a phone filename is reused. After inbox cleanup, the same filename and identical bytes can be uploaded again.

The Git history is the publishing queue. Removing an inbox file does not cancel an earlier committed upload event. Hide or edit the saved post instead.

### Formats and conversion

Supported inputs are JPG/JPEG, PNG, WebP, GIF, HEIC, and HEIF. Extensions are case insensitive; Unicode names and nested inbox folders are supported.

| Input | Saved image behavior |
| --- | --- |
| JPEG, HEIC, and HEIF | WebP quality 85, original display dimensions, corrected orientation, retained ICC color profile |
| PNG | Lossless WebP with transparency and animation timing when applicable |
| GIF | Lossless animated WebP retaining frames, timing, transparency, and loop behavior |
| Existing WebP | Validated and retained byte for byte |

Phone MPO and HEIF files publish the primary display photograph; auxiliary gain maps are not treated as animation frames. Existing saved package media retains its supplied format and bytes. Builds copy that media without recompression.

Inbox originals are removed only after their saved packages have been committed, deployed, and verified at the public domain. Cleanup checks both the original upload checksum and the saved media checksum. Failed runs, newer uploads, changed archives, and unpublished posts retain their inbox originals. Uploaded originals also remain recoverable from Git history.

Pull `main` before the next phone upload so it receives the publishing bot's saved packages and inbox cleanup.

## Shared metadata

Flux, Savour, and Fieldlog use the [shared fivsevn core schema](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/content-metadata.schema.json) and [site-post profile](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/site-post.schema.json). The helper and schemas in this repository are local copies, so normalizing, checking, and building need no network access.

Saved posts use the shared core fields at the top level. Precise publication time and site-specific values live in `extra`; unrecognized input metadata is retained under `legacy.metadata`. The compatibility view used by the renderer and importer is never written back as a saved frontmatter format.

A text package can look like this:

```yaml
---
id: 2026-10-30-180000-example
title: A short field note

module: posts
submodule: flux
topic: null

type: log
status: published
canonical: true

summary: null
parents: []
related: []
tags: []
audience: [public]
languages: [zh]
maturity: evolving
confidence: null
visibility: public
source_of_truth: site
filename_policy: entrypoint

created: '2026-10-30'
updated: '2026-10-30'
metadata_updated: '2026-10-30'

extra:
  profile: site-post-v1
  published_at: '2026-10-30T18:00:00+08:00'
  author: 五月七日
  alt: A short field note
---

Write the post body here.
```

Automatic imports fill missing core fields and save canonical frontmatter immediately. The workflow also normalizes manually edited packages before validation. Completion preserves an existing ID, exact publication time, content dates, and explicit draft, hidden, private, or internal controls. It does not infer a publication timestamp from the file modification time. A manually created package must supply its fixed `extra.published_at` timestamp or an input `date` that the helper can normalize.

| Field | Maintenance rule |
| --- | --- |
| `id` and package path | Stable identity; do not change during ordinary edits |
| `title` | Editable display heading; normalization fills an empty value from publication time |
| `extra.published_at` | Fixed timestamp with a timezone; determines ordering and default heading |
| `created` / `updated` | Content dates; preserve creation date and update the latter when revising content |
| `metadata_updated` | Metadata bookkeeping date; unchanged normalization leaves it stable |
| `module` / `submodule` / `type` | Flux posts use `posts` / `flux` / `log` |
| `status` / `visibility` | Only public posts with status `active`, `publish`, or `published` enter the artifact |
| `extra` source and upload records | Preserve machine identities and checksums used for retries and cleanup |

Draft, hidden, private, and internal packages are excluded from all generated pages and copied package media. These settings control the website artifact; saved source and prior commits remain in the repository.

## Find and edit an existing post

An individual URL maps directly to its source package:

```text
https://flux.fivsevn.com/page/YYYY/MM/{id}/
                                      ↓
flux/YYYY/MM/{id}/index.md
```

1. Pull the latest `main` and locate that `index.md`.
2. Edit the Markdown body or the top-level `title`.
3. Preserve the package path, `id`, `extra.published_at`, source identities, and upload checksums.
4. Commit and push, wait for Build and deploy Flux, then check both list and detail views.

Titles and timestamps are independent. Changing the title keeps the post's chronological position and individual URL.

### Replace an image

Put the replacement into the post's own `assets/` directory and update its relative Markdown link, such as `![](assets/replacement.webp)`. Check for references before deleting an old file. Saved-package media keeps its supplied format; prepare the desired format before adding it there. A deliberate archive replacement causes original-inbox cleanup to retain that upload until its record is reviewed.

### Hide or remove a post

Set `status: hidden` or `draft` to retain its package while excluding it from the artifact. Restore `status: published` with `visibility: public` to publish it at its original address. To remove the source, delete the complete package directory after checking media references. The next build removes its generated detail page and list entry. Recover accidental deletion from Git history, including the package's media.

## Pages and navigation

Each list page contains **11 published posts**, newest first by the fixed publication instant, then stable ID. Introductory bubbles, links, and the license bubble do not count toward that limit. The interface keeps this order:

```text
typing bubble → pocket image → content-library link → posts → pagination → license bubble
```

Public post URLs remain `/page/YYYY/MM/{id}/`, list URLs remain `/feed/N/` after the first page, and package media stays at `/flux/YYYY/MM/{id}/assets/`. These routes are independent of `_site/` on disk.

List bookmarks with a post hash follow that post to its current page when pagination changes. A detail page's return bubble uses browser history when available and otherwise links to the post's current list page and anchor.

## Build and deployment

[Build and deploy Flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) is the only deployment workflow. Relevant pushes to `main` and manual dispatch start it. Runs are serialized, and it uses this sequence:

1. Check out current `main` and install dependencies.
2. Normalize saved frontmatter, run tests, and validate the shared core/profile schemas.
3. Read new committed text and image snapshots from GitHub, preserving processed-event identities.
4. Validate imported packages and build the complete `_site/` artifact once.
5. Confirm the branch has not changed, then commit source packages and input cursors together.
6. Upload `_site/` and deploy it with GitHub Pages.
7. Compare the public deployment receipt, required pages, and image bytes against the artifact.
8. Confirm the branch still matches, record the verified fingerprint, and clear matching inbox originals.

A successful run includes verification of the public artifact. No cross-repository credentials are required for routine publishing. The workflow's repository token saves source and state; GitHub Pages handles the public deployment.

`_site/deployment.json` contains the artifact fingerprint, source positions, and required public file checksums. `.publishing/deployed.sha256` records a verified publication; cleanup requires a matching local verification marker inside `_site/` as well.

The single build renders lists and detail pages, copies only published package media, generates bookmark navigation, and writes the receipt. There is no second packaging pass and no generated HTML in source directories.

### Local commands

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/site_post_metadata.py normalize --site flux --root flux --schema-dir schemas
python scripts/site_post_metadata.py check --site flux --root flux --schema-dir schemas
python -m unittest discover -s tests -v
python scripts/build.py
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000/`. `build.py` is offline and reads only saved packages. `ingest_github.py` intentionally reads GitHub and writes new packages and cursors; use it when importing queued triggers. `verify_live.py` checks the current public domain, so it belongs after deploying the matching artifact.

### Recovery

| Failure | What to do |
| --- | --- |
| No run after an upload | Check the repository, branch, and input path, then dispatch Build and deploy Flux manually if needed |
| Invalid shared metadata | Read the reported path and field, fix the source, run normalize/check locally, and push |
| Invalid or unsupported image | Replace or remove the bad inbox file and push; a later committed correction can supersede an invalid queued snapshot |
| Missing source cursor | Review reachable Git history and restore the correct cursor; an arbitrary reset can replay or skip events |
| Branch changed during publication | Pull current `main` and let the latest queued run continue, or rerun from the new branch head |
| Public page or media verification failed | Check Pages and rerun; matching inbox originals remain intact |
| Saved archive changed intentionally | Review the saved upload record before allowing cleanup; do not overwrite checksums to conceal an accidental change |

Retrying an existing committed event preserves its saved package and later edits. Uploading again is a new event. Keep `.publishing/state.json` during ordinary maintenance.

Content license: CC BY-NC-SA 4.0. Quoted and third-party material retains its original rights and licenses.
