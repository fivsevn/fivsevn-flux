# flux image inbox

Save phone images to **`fivsevn/fivsevn-flux/trigger_imgs/`**, then commit and push to `main`. Automation converts each image, saves its entry package, publishes the website, verifies the public files, and clears the processed inbox original.

## Set up the phone shortcut

1. Open the shortcut's flux branch and choose **fivsevn-flux** as its Working Copy repository.
2. Before saving images, have Working Copy pull the latest `main` from this repository.
3. Set the Save File action's destination to **`trigger_imgs/`**. Keep the original phone filename; no timestamp or manual renaming step is needed.
4. After saving, commit and push to **fivsevn-flux → main**. Update any existing commit/push action that still points to the old repository.
5. If a caption is needed, put it in the commit's **extended description**, below the summary line. Markdown is supported.

> **Daily operation:** Once configured, publishing remains one shortcut invocation. The phone does not need to convert images or create entry folders. Pulling first receives the publishing bot's commits and previous inbox cleanup.
>
> **Destination:** All new flux images go to this directory. The assets repository's old flux image folder and old shortcut folder bindings are retired.

## Publish images

1. Select one or more images and run the shortcut.
2. Add a caption in the extended commit description, or leave it empty for image-only posts.
3. Let the shortcut finish committing and pushing.
4. Wait for [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) to succeed.
5. Open [flux](https://flux.fivsevn.com/), inspect the image and caption, and open the entry title to check its individual page.

> **Accepted formats:** JPG/JPEG, PNG, WebP, GIF, HEIC, and HEIF are supported. Extensions are case-insensitive. Original phone names, Unicode filenames, and nested folders are accepted.
>
> **One image per entry:** Multiple images in one commit create separate entries with the same caption. The commit summary is not used as the caption. With no extended description, each post contains only its image.
>
> **Reusing filenames:** After an upload has been processed and its inbox original cleared, the same filename may be uploaded again, even with identical bytes. Each new upload commit and path creates a new entry; retries of that same commit and path cannot duplicate it. Saving identical bytes over an unchanged inbox file does not create a Git change.

## Automatic processing

1. Validate each newly committed image.
2. Convert it to WebP and generate its name from the upload commit time in `Asia/Shanghai`.
3. Save a complete entry package under `flux/YYYY/MM/{id}/`:

   ```text
   flux/YYYY/MM/{id}/
     index.md                              Image link, caption, and metadata
     assets/YYYYMMDD-HHMMSS-NN.webp         Saved image
   ```

4. Build the timeline and individual page, then deploy them with the entry's saved image.
5. Fetch the public page and image and check their bytes against the deployment artifact.
6. Delete the inbox original only after successful verification, provided it still matches the imported checksum.

> **Automatic names:** A name such as `20261018-103012-01.webp` uses the committed upload's Beijing time. Images in the same commit receive stable sequence numbers in sorted path order. The time does not come from EXIF or the workflow start, so retries retain the same name.
>
> **Photo conversion:** JPEG and HEIC/HEIF photos use WebP quality 85 at their original display dimensions, with orientation corrected and ICC color profiles retained. Auxiliary MPO/HEIF images such as HDR gain maps are not treated as animation; the primary display photo is published.
>
> **Graphics and animation:** PNG and GIF use lossless WebP. Transparency, animated frames, timing, and loop behavior are retained. Existing WebP files are validated without another lossy encode. Historical package images are not recompressed in bulk; WebP is not guaranteed to be smaller for every input.
>
> **Temporary inbox:** Successful cleanup removes only the current inbox copy. Original uploads remain recoverable from Git history. Failed conversions, deployments, or verification retain the originals. A newer inbox file with different bytes is retained.
>
> **This README:** Documentation is ignored by the image importer and is never converted into a post. Updating it can start Publish flux because it is inside the inbox path filter.

## Recover from a failed upload

1. Open the failed step in Publish flux and identify the affected file or deployment error.
2. For a damaged or unsupported image, replace it with a valid file at the same input path, or delete the rejected file; commit and push the correction.
3. For a deployment or public-verification failure, fix the reported cause and rerun Publish flux.
4. Confirm the public page and image, then pull the latest `main` before another upload.

> **Retries and queued uploads:** Saved source identities prevent duplicates. A rejected older snapshot is skipped only when a later committed replacement or deletion exists; valid queued uploads are still imported. Do not delete valid pending originals just to clear an error.

## Edit an already published image entry

1. Open the entry's title on the timeline and read its `/page/YYYY/MM/{id}/` URL.
2. Open the corresponding `flux/YYYY/MM/{id}/index.md` in this repository.
3. Edit the caption there. To replace the image, add the desired file to that package's `assets/` and update its relative Markdown image link.
4. Preserve the ID, date, directory, and source identity fields; commit and push the package changes together.
5. Wait for Publish flux to succeed and inspect the updated page.

> **Existing entry versus new upload:** Editing or deleting an inbox original does not revise a saved package. A new upload commit creates a new entry. Direct replacements inside a saved package are not run through the inbox converter; prepare them in the desired format first.
>
> **Text input:** New text uses [`trigger_text.md`](../trigger_text.md). Full English instructions for editing, hiding, restoring, deleting, and deployment are in the [repository README](../README.md). The [devlog posts guide](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/README.md#1-短内容flux) provides the concise Chinese version.
