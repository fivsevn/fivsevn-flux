# fivsevn flux

The content archive and static-site backend for [flux.fivsevn.com](https://flux.fivsevn.com/).

**Everyday publishing instructions live in the [devlog posts guide](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/README.md).** This repository owns saved entries, their media, rendering, and deployment. The guide in devlog is the concise Chinese entry point; this README documents backend maintenance in English.

## Repository layout

```text
trigger.md                 The only new-text publishing entry point
uploads/                   Image originals saved by the phone shortcut
flux/YYYY/MM/{id}/
  index.md                 Editable source for one saved entry
  assets/                  Media owned by that entry, when present
scripts/
  ingest_github.py          Import new GitHub source commits
  build.py                 Render the timeline and individual pages
  package_site.py           Assemble the public Pages artifact
site-assets/               Avatars and the pocket image
style.css                  Shared presentation
.publishing/
  state.json               Source paths and processed commit cursors
  site.sha256              Fingerprint of the current public artifact
  deployed.sha256          Fingerprint of the last successful deployment
.github/workflows/build.yml
index.html                 Generated first timeline page
feed/                      Generated timeline pagination
page/                      Generated individual entry pages
_site/                     Local deployment artifact; ignored by Git
```

Edit source packages under `flux/`. Generated HTML and `_site/` are rebuilt and must not be edited as source content.

## Locate an existing entry

Open its title on the live timeline. An individual URL such as:

```text
https://flux.fivsevn.com/page/2026/10/2026-10-18-064929-e4ec7f5cb277/
```

corresponds to:

```text
flux/2026/10/2026-10-18-064929-e4ec7f5cb277/index.md
```

Replace the URL's `page/` with `flux/` and append `index.md`. Use this mapping rather than the displayed title, which may have been customized. The example above is the retained `test` entry.

## Edit an existing entry

1. Pull the latest `main` before editing: the publishing workflow also commits to this branch.
2. Open the matching `flux/YYYY/MM/{id}/index.md`.
3. Change the Markdown after the closing `---` to edit the body, links, or image caption. Change the top-level `title` to edit the clickable heading.
4. Keep the directory, `id`, and `date` unchanged. Keep source identity fields as well.
5. Commit and push to `main`. Wait for [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) to finish, then check both the timeline and the individual page.

The upper heading is `title`; the lower publication timestamp is `date`. They are independent. Editing `title` changes the heading in both views without changing the URL, lower timestamp, or chronological position. The timestamp retains its existing ISO format, for example `2026-10-18T06:49:29+08:00`.

A blank title in the **new-post trigger** is filled with a time-based heading during import. An already saved entry has its title stored explicitly; to give it a different time-style heading later, edit that stored string. Do not clear a saved title expecting the trigger's defaulting behavior to run again.

Do not edit or resubmit the trigger to revise an old entry: a new trigger commit is a new publishing event. Do not edit generated files under `page/` or `feed/`.

### Replace or remove an image

Place replacement files in that entry's `assets/` directory and update its relative Markdown link, for example `![](assets/replacement.webp)`. Remove an obsolete file only after checking that no other entry references it. Commit the Markdown and media changes together.

The saved media belongs to this repository. Editing or deleting its original file in `uploads/` does not edit an existing flux entry; edit the saved package here.

## Hide, restore, or delete an entry

### Hide from the website while retaining the archive

Set the saved entry's frontmatter to:

```yaml
status: hidden
```

Commit and push. After deployment, the entry is absent from the timeline and its individual page is no longer published. Its package and source identity remain in the repository, which also prevents normal source retries from recreating it. To restore it, change the value to `status: published` and push again; its original URL and publication timestamp are retained.

Only `published` entries are included in the site; historical entries without a `status` field are also treated as published. Draft and hidden packages are excluded from the deployment artifact. The GitHub repository and its history remain public: hiding is a site-presentation setting, not private storage.

### Delete the saved package

1. Locate the package using the URL mapping above.
2. Delete the entire `flux/YYYY/MM/{id}/` directory, including `index.md` and its owned `assets/`. Check for cross-entry references before removing media.
3. Commit and push the deletion to `main`.
4. Confirm Publish flux succeeds. The timeline is rebuilt, obsolete individual pages are removed, and the new Pages artifact omits the deleted package's media. Refresh the timeline and verify that the former individual URL returns a missing-page response.

Do not delete just the generated `page/` directory: it would be recreated from the Markdown. Deleting the trigger or the original WordPress post does not delete a saved flux entry either.

Deletion removes the package from the current branch and website; earlier Git commits still contain it. To undo an accidental deletion, restore that package from Git history and push it again. Do not rewind `.publishing/state.json` to restore content.

The importer normally advances past already processed source commits, so a deletion is not undone by the next run. However, removing a package also removes its stored deduplication keys. A later commit modifying the same source image path, or reusing an explicit text slug, can create it again. Use `hidden` when you want to retain the identity and reliably keep an entry off the site.

## Import sources and metadata

| Source | Input | Saved result |
| --- | --- | --- |
| Text | This repository, `trigger.md` | One Markdown package per new trigger commit; push starts publication directly |
| Images | This repository, `uploads/` | One package per new image path; push starts publication directly; extended commit description supplies the caption |

The importer reads committed snapshots on `main`, in chronological order. Source paths and processed commit positions are in `.publishing/state.json`. Both text and images are authored here. No WordPress access or cross-repository write token is needed. The former devlog trigger was retired after its last pending post was imported; its existing entry identities and URLs are retained.

The text trigger accepts `status: published` or `status: draft` and an optional `title`. Missing or empty titles receive a heading derived from the source commit time. The lower `date` is recorded separately from that same commit time, using `Asia/Shanghai`. It is not recomputed when an existing package is edited. Scheduled publication dates are not supported.

Ordinary Markdown, named links, lists, quotes, tables, images, and line breaks are preserved. An explicit `slug` retains create-once behavior; omit it for normal new posts. Legacy `wp_status` values are still understood for historical compatibility.

Saved identity fields include `source_key`, `source_commit`, `source_repository`, and `publish_slug`; image entries also have `source_asset_path`. Older packages may contain `wp_id`, `wp_slug`, and other provenance fields. Preserve these fields during normal editing. They record origin and support deduplication; they do not activate WordPress synchronization.

## Build and deployment

The only maintained workflow is **Publish flux**, defined in `.github/workflows/build.yml`. A push changing `trigger.md` or `uploads/**` starts it directly, as do changes to saved entries and build files. There is no schedule and no polling of another repository. Manual dispatch is available for recovery. README-only edits do not require a site deployment.

The workflow:

1. Checks out current `main` and runs the publishing tests.
2. Reads new source commits and saves complete entry packages.
3. Builds the timeline, pagination, and individual pages.
4. Packages public HTML, styles, site assets, and published-entry media into `_site/`.
5. Commits source cursors, new content, and generated pages together.
6. Deploys the artifact through GitHub Pages when its fingerprint differs from the last successful deployment.
7. Fetches the public deployment receipt, timeline, latest imported published pages, and their actual image files and checks their bytes against the artifact.
8. Records the deployed fingerprint only after these public checks pass. A green Publish flux run therefore confirms the deployed artifact, rather than just Markdown validation. The public `deployment.json` receipt contains source positions and checksums, never draft bodies.

The timeline uses 17 entries per page, ordered by `date`, newest first. Its visual order is typing bubble → pocket image → content-library link → entries → pagination → license bubble. Every entry title links to its individual page. Long links wrap within the message bubble.

`build.py` recreates `page/` and `feed/` on every build; hiding or deleting a source entry therefore removes obsolete generated pages. `package_site.py` excludes scripts and non-published packages from the Pages artifact. GitHub Pages uses the Actions artifact rather than serving the repository root.

### Local verification

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python scripts/package_site.py
python -m http.server 8000 --directory _site
```

Building locally does not import or publish anything. Run `scripts/ingest_github.py` only when intentionally importing: it reads GitHub and writes local packages and cursors. The workflow is responsible for committing and deploying those changes.

### Troubleshooting

- **No run after adding text or images:** confirm the change was pushed to `main` in this repository, under `trigger.md` or `uploads/`. The old devlog trigger and assets image folder are retired. The input commit must have a Publish flux run; no schedule is required.
- **An image upload was rejected:** use a new filename and a valid JPG/JPEG, PNG, WebP, or GIF. Convert HEIC before uploading. Unsupported or damaged uploads fail visibly instead of advancing silently.
- **A Publish flux run failed:** open its failed step. Invalid input, import errors, failed pushes, deployment errors, and public verification errors produce a failed run. Fix the cause and rerun; committed source identities prevent duplicate imports.
- **Missing source cursor:** stop and inspect source history. Do not reset the cursor to an arbitrary commit, which could replay content or skip posts.
- **Failed image download:** the importer does not save a partial package or advance past the failed import. Fix the source problem and rerun.
- **Push rejected after a concurrent edit:** pull current `main` and rerun the workflow. Do not force-push over user edits.
- **Deployment failed after content was committed:** rerun Publish flux. The successful-deployment fingerprint remains unchanged, so the artifact is retried.

## WordPress migration

Since 2026-10-18, flux publishes directly from GitHub. The 150 migrated packages retain their original URLs and dates. Subsequent posts, including the retained `test`, use the same archive structure. Old WordPress sync workflows and retired importer stubs have been removed. Changes or deletions in WordPress do not affect these saved packages.

Content license: CC BY-NC-SA 4.0. Quoted and third-party material retains its original rights and licenses.

## Image uploads and phone shortcut

The image inbox is [`uploads/`](uploads/) in **this repository**. The phone shortcut’s flux branch must select the `fivsevn-flux` repository and its `uploads/` folder in the Save File action. Pull the latest `main` in Working Copy first. Any existing commit/push actions in that branch must also target `fivsevn-flux`.

Use a new filename for each new image post. Nested folders and Unicode filenames are supported. Supported extensions are `.jpg`, `.jpeg`, `.png`, `.webp`, and `.gif`, case-insensitively. Convert HEIC to JPEG first. Image bytes are checked without recompression; animations and transparency are preserved. Unsupported files and damaged images fail the run.

A commit may contain multiple images. Each new image path creates a separate post; all images in that commit receive the same Markdown caption from the extended commit description (the part after the summary line). With no extended description, the post contains only the image. Modifying an already imported upload path does not republish or edit its saved post; edit the saved package under `flux/` instead.

On 2026-10-18, the 19 originals previously in `fivsevn-assets/post/flux/` were moved byte-for-byte to `uploads/`. Every original was checked against its existing package media. The migration commit is the initial image cursor, so moving these originals does not create new posts. `previous_sources` retains both retired assets prefixes solely for historical duplicate detection. Existing post IDs, titles, dates, URLs, bodies, and package media are retained; mutable original-source links now point here.

The retired `post/flux/` folder has been removed from assets after verifying this migration. No flux runtime input or image request depends on assets. The old signed shortcut export in assets `docs/` remains a historical backup; do not reinstall its old folder binding. Other shortcut branches are unchanged.
