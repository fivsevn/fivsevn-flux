# flux.fivsevn

Flux is the short-form section of [fivsevn.com](https://fivsevn.com/): quick thoughts, photos, and links. Its public page is [flux.fivsevn.com](https://flux.fivsevn.com/). This repository holds its content archive and static-site backend.

Publish new text through [`trigger_text.md`](trigger_text.md) and new images through [`trigger_imgs/`](trigger_imgs/). This repository saves each entry with its media, builds the website, and deploys it through GitHub Pages. The [devlog posts guide](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/README.md) provides concise everyday instructions in Chinese; this guide covers publishing and maintenance in English.

## Repository layout

```text
trigger_text.md                 New-text publishing input
trigger_imgs/                   Temporary image inbox for the phone shortcut
  README.md                     Chinese image-upload guide
flux/YYYY/MM/{id}/
  index.md                      Editable source for one saved entry
  assets/                       Media owned by that entry, when present
scripts/
  ingest_github.py               Import new GitHub source commits
  build.py                      Render the timeline and individual pages
  package_site.py               Assemble the public Pages artifact
  verify_live.py                Check the public deployment and media bytes
  image_inbox.py                Clear originals after verified publication
site-assets/                    Avatars and the pocket image
style.css                       Shared presentation
.publishing/
  state.json                    Source paths and processed commit cursors
  site.sha256                   Fingerprint of the current public artifact
  deployed.sha256               Fingerprint of the last successful deployment
.github/workflows/build.yml     Publish flux workflow
index.html                      Generated first timeline page
feed/                           Generated timeline pagination
page/                           Generated individual entry pages
_site/                          Local deployment artifact; ignored by Git
```

> **Source files:** Edit saved packages under `flux/`. Generated HTML in `index.html`, `page/`, `feed/`, and `_site/` is rebuilt from source.
>
> **Publishing scope:** This repository owns both publishing inputs and the saved entries with their media.

## Publish a new text entry

1. Pull the latest `main` from this repository.
2. Open [`trigger_text.md`](trigger_text.md). Keep its frontmatter and instruction comments. Set the status and optional title at the top:

   ```yaml
   status: published
   title: ""
   ```

3. Replace the body after the closing `---` with the new entry. Use Markdown for links, lists, quotes, tables, and images. For example, write a named link as `[link text](https://example.com/)`.
4. Commit and push the changed file to this repository's `main` branch.
5. Wait for [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) to succeed. Check the timeline and open the entry's title to inspect its individual page.

> **Title:** Leave `title: ""` empty for a heading generated from the source commit time in `Asia/Shanghai`. Set `title: "Your title"` for a custom heading. Clear it again before the next post if you want to return to a time-based heading.
>
> **Publication time:** The lower timestamp is saved separately as `date`, using the source commit time in `Asia/Shanghai`. It determines the entry's chronological position and stays fixed when its title is edited.
>
> **Drafts:** Use `status: draft` to save a package without publishing it on the website. The repository and its Git history are public, including draft text. Publish an imported draft by changing the saved package to `status: published`.
>
> **New entry versus edit:** Each changed trigger commit with a nonempty body is a new publishing event. Revise an existing entry through its saved package under `flux/`.
>
> **Instruction comments:** Keep frontmatter instruction comments above the closing `---`; the body supplies the post content. The importer creates a package from a nonempty body. Updating only instruction comments still counts as changing the trigger, so maintenance must account for that commit before running the importer.
>
> **Advanced compatibility:** Omit `slug` for normal posting. An explicit slug has create-once behavior, so reusing it can prevent a later trigger from creating a new entry. Historical `wp_status` values remain supported for compatibility.

<a id="publish-images-from-the-phone-shortcut"></a>

## Publish images

### Configure the shortcut once

1. Open the shortcut's flux branch and select **fivsevn-flux** as the Working Copy repository.
2. Add or retain a pull/sync action before saving, so Working Copy first pulls the latest `main`.
3. Set the Save File destination to this repository's [`trigger_imgs/`](trigger_imgs/) folder. Keep the original phone filename.
4. Set the commit and push actions to the same repository and its `main` branch.
5. If the shortcut offers a caption, put it in the commit's **extended description**, below the summary line.

### Use the shortcut each day

1. Select the image or images and run the shortcut. Let it pull, save, commit, and push.
2. Enter a caption in the extended commit description if needed; leave it empty for an image-only post.
3. Wait for [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) to succeed, then check the timeline, individual page, and displayed image.
4. On the next upload, let the shortcut pull again so it receives the publishing bot's commits and inbox cleanup.

> **Accepted files:** JPG/JPEG, PNG, WebP, GIF, HEIC, and HEIF are supported, with case-insensitive extensions. Unicode filenames and nested folders are supported. The repository handles timestamps, format conversion, and entry folders.
>
> **Batch behavior:** Each image upload commit and path creates one separate entry. Multiple images in one commit receive the same Markdown caption from its extended description. Leave the extended description empty for image-only entries.
>
> **Automatic filenames:** Saved media uses `assets/YYYYMMDD-HHMMSS-NN.webp` inside the entry package, for example `20261018-103012-01.webp`. The time comes from the upload commit in `Asia/Shanghai`. Paths are sorted to assign stable batch numbers, so retries keep the same names.
>
> **Reusing a phone filename:** After the previous upload is processed and its inbox original is cleared, the same filename can be uploaded again, including with identical bytes. A new upload commit is a new entry; each commit and path is processed once. Replace an existing entry's image through its saved package.
>
> **Originals:** `trigger_imgs/` is temporary. Automation removes a matching original after the saved package has been committed, deployed, and verified at the public domain. Failed runs and newer files with different bytes retain their inbox copies. Uploaded originals remain recoverable from Git history.
>
> **Quick reference:** The [image inbox guide](trigger_imgs/README.md) is a concise Chinese upload checklist. This root README contains the detailed English publishing and maintenance instructions.

### Image conversion

| Input | Saved WebP behavior |
| --- | --- |
| JPEG and HEIC/HEIF photos | Quality 85, original display dimensions, corrected orientation, retained ICC color profile |
| PNG graphics | Lossless WebP, retaining transparency; animated PNG frames and timing are retained |
| GIF animations | Lossless animated WebP, retaining frames, timing, transparency, and loop behavior |
| Existing WebP | Validated and retained byte-for-byte |

> **Auxiliary images:** Phone MPO/HEIF uploads publish the primary display photo, with auxiliary data such as HDR gain maps handled as still-photo data.
>
> **File size:** Encoded size depends on the input. Existing package images retain their saved format, and original uploads remain recoverable from Git history.

## Locate an existing entry

1. Open the entry's title on the live timeline.
2. Read its individual URL. A URL in this form:

   ```text
   https://flux.fivsevn.com/page/YYYY/MM/{id}/
   ```

   maps to this source file:

   ```text
   flux/YYYY/MM/{id}/index.md
   ```

3. Replace the URL's `page/` with `flux/` and append `index.md` to find the saved package in this repository.

> **Stable identity:** Use the URL and package ID to find an entry. Its displayed title may have been customized.

## Edit an existing entry

1. Pull the latest `main`; the publishing workflow also commits to this branch.
2. Locate the entry's `flux/YYYY/MM/{id}/index.md` using the URL mapping above.
3. Edit the Markdown after the closing `---` to change the body, links, or caption. Edit the top-level `title` to change the clickable heading.
4. Commit and push the saved-package changes to `main`.
5. Wait for Publish flux to succeed, then check both the timeline and individual page.

> **Preserve identity:** Keep the directory, `id`, `date`, and source identity fields unchanged during ordinary edits. Saved identity fields include `source_key`, `source_commit`, `source_repository`, and `publish_slug`; image entries also include `source_asset_path` and an `upload` checksum record. Older packages may contain `wp_id`, `wp_slug`, and other provenance fields. These support origin tracking and deduplication.
>
> **Saved titles:** An imported entry stores its title explicitly. To give an existing entry a different time-style heading, edit that stored string. The time-based default applies when importing a new trigger.
>
> **Publishing input:** Resubmitting the trigger creates a new publishing event. Edit saved packages to revise the generated `page/` and `feed/` output.

### Replace or remove an image

1. Locate the saved entry package and inspect its image links.
2. Add a replacement file to that package's `assets/` directory and update the relative Markdown link, for example `![](assets/replacement.webp)`. To remove an image, remove its Markdown reference.
3. Check whether any other entry references an obsolete file before deleting it.
4. Commit the Markdown and media changes together, push to `main`, and check the deployed page and image.

> **Saved media:** Edit the copy owned by the saved package. Files placed directly in a saved package keep their supplied format, so prepare them in the desired format before adding them there.

## Hide, restore, or delete an entry

### Hide an entry while retaining its package

1. Open the saved entry's `index.md` and set its frontmatter to `status: hidden`.
2. Commit and push to `main`, then wait for Publish flux to finish.
3. Confirm the entry is absent from the timeline and its individual page is no longer published.

> **Visibility:** Only `published` entries are included in the site; historical packages without a `status` field are also treated as published. Draft and hidden packages are excluded from the deployment artifact. Hiding is a website setting; the repository and Git history remain public.
>
> **Retained identity:** A hidden package keeps its source identity, preventing normal source retries from recreating it. Use this method when you want to keep an entry off the website and retain its archive.

### Restore a hidden entry or publish a saved draft

1. Change the saved package's status to `status: published`.
2. Commit and push to `main`.
3. Wait for Publish flux to succeed and check the original individual URL and timeline.

> **Original date and URL:** Restoring a package retains its ID, URL, and stored publication timestamp.

### Delete the saved package

1. Locate the package using the URL mapping above.
2. Check that its media is not referenced by another entry.
3. Delete the entire `flux/YYYY/MM/{id}/` directory, including `index.md` and its owned `assets/`, then commit and push the deletion.
4. Wait for Publish flux to succeed. Confirm the timeline no longer lists it and the former individual URL returns a missing-page response.

> **Delete the source:** Delete the saved package to remove an entry. Generated `page/` output is rebuilt from that Markdown source.
>
> **Git history:** Deletion removes the package from the current branch and website. Earlier commits still contain it. Restore an accidental deletion by recovering the whole package from Git history and pushing it again, while preserving `.publishing/state.json`.
>
> **Later uploads:** Processed commits stay behind the import cursor. Deleting a package also removes its stored deduplication keys; a new upload commit or reuse of a previously stored explicit text slug can create an entry again.

## Build and deployment

The maintained workflow is [**Publish flux**](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml), defined in [`.github/workflows/build.yml`](.github/workflows/build.yml).

### Check a publication

1. Push the text, images, saved-package changes, or build changes to this repository's `main`.
2. Open Publish flux and locate the run for that input commit.
3. Check that importing, building, deployment, public verification, and inbox cleanup finish successfully.
4. Open the public timeline and the relevant individual page. For an image entry, check the actual displayed image too.

> **Direct trigger:** Changes to `trigger_text.md` or `trigger_imgs/**` start the workflow directly, as do saved-entry and build-file changes listed in the workflow. Manual dispatch is also available. Root README-only edits stay outside the deployment path filter. `trigger_imgs/README.md` matches that filter and can start a run; the importer treats it as documentation.
>
> **Recovery:** Use the workflow's manual dispatch to run it again when needed.

### What the workflow does

1. Check out current `main` and run the publishing tests.
2. Read new source commits in chronological order, convert uploaded images to WebP, and save complete entry packages.
3. Build the timeline, pagination, and individual pages.
4. Package public HTML, styles, site assets, and published-entry media into `_site/`.
5. Commit source cursors, new content, and generated pages together.
6. Deploy the artifact through GitHub Pages when its fingerprint differs from the last successful deployment.
7. Fetch the public deployment receipt, timeline, latest imported published pages, and their actual image files; compare their bytes with the artifact.
8. Record the deployed fingerprint only after public verification succeeds. If no new deployment is needed, verify the existing public deployment instead.
9. Remove a processed inbox original only when its saved page and image passed public verification and the original still matches the imported checksum.

> **Success signal:** A green run includes verification of the public artifact. The public `deployment.json` receipt contains source positions and checksums. Failed runs retain the inbox originals; the workflow completes cleanup in the same run.
>
> **Timeline:** Each page contains 17 entries, newest first by `date`. The visual order is typing bubble → pocket image → content-library link → entries → pagination → license bubble. Every entry title links to its individual page; long links wrap within the bubble.
>
> **Generated output:** `build.py` recreates `page/` and `feed/`, removing obsolete pages after an entry is hidden or deleted. `package_site.py` excludes scripts and non-published packages. GitHub Pages serves the Actions artifact rather than the repository root.

### Local verification

1. Install the dependencies:

   ```sh
   python -m pip install -r requirements.txt
   ```

2. Run the publishing and rendering tests:

   ```sh
   python -m unittest discover -s tests -v
   ```

3. Build and package the existing saved entries:

   ```sh
   python scripts/build.py
   python scripts/package_site.py
   ```

4. Serve the artifact locally and open `http://localhost:8000/`:

   ```sh
   python -m http.server 8000 --directory _site
   ```

> **Local effects:** Building renders the saved entries locally. `scripts/ingest_github.py` reads GitHub and writes local packages and cursors; run it when intentionally importing. The workflow commits and deploys those changes.

## Troubleshooting

### No run after a text or image upload

1. Confirm the commit was pushed to `main` in **fivsevn/fivsevn-flux**.
2. Check that the changed path is `trigger_text.md` or a file under `trigger_imgs/`.
3. Open Publish flux and find the input commit's run. If the input is committed but no run is available, start the workflow manually and inspect its result.

### An image upload was rejected

1. Open the failed import step and identify the rejected path.
2. Replace the damaged or unsupported image with a valid JPG/JPEG, PNG, WebP, GIF, HEIC, or HEIF at that input path, or delete the rejected file.
3. Commit and push the correction, then check the new run.

> **Queued snapshots:** A rejected older snapshot is skipped when a later committed replacement or deletion exists. Valid queued snapshots are imported normally. Failed downloads leave packages and the source cursor at the last completed import.

### A run failed during import, push, or deployment

1. Open the failed step in Publish flux and read the specific error.
2. Correct invalid input or the reported source problem. If a push was rejected after a concurrent edit, pull the latest `main` and resolve the edit before retrying.
3. Rerun Publish flux and check both the public page and any image after it succeeds.

> **Retries:** Committed source identities prevent duplicate imports. If content was committed but deployment failed, the successful-deployment fingerprint remains unchanged so deployment is retried. Preserve concurrent edits when resolving a rejected push.

### A source cursor is missing

1. Stop retrying the import and inspect the recent repository history for a rewrite or missing commit.
2. Compare the configured cursor in `.publishing/state.json` with the reachable source history before preparing a repair.

> **Cursor repair:** A cursor records processing progress. Restore content from its saved package history; repair a cursor against the reachable source history. An arbitrary cursor can replay published content or skip unprocessed entries.

<a id="import-records-and-migration-history"></a>

## Import records

| Source | Input | Saved result |
| --- | --- | --- |
| Text | `trigger_text.md` in this repository | One package per new trigger commit with a nonempty body |
| Images | `trigger_imgs/` in this repository | One package per image upload commit and path; the extended commit description supplies its caption |

> **History scanning:** `.publishing/state.json` stores input paths and processed commit positions. `history_path: ""` scans repository history so input renames retain a reachable cursor; changes to the configured input supply new publishing events.
>
> **Saved identity:** Historical packages retain their original IDs, dates, content, and URLs. Legacy path identities use `previous_sources` and `previous_paths`; current image uploads use `identity: commit-path` so a later upload of the same phone filename can create a new entry.

Content license: CC BY-NC-SA 4.0. Quoted and third-party material retains its original rights and licenses.
