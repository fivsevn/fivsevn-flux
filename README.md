# fivsevn-flux

Static flux archive for `flux.fivsevn.com`.

Content packages live under:

```text
flux/YYYY/MM/{id}/index.md
flux/YYYY/MM/{id}/assets/
```

Edit `index.md` for a single item. Put item-specific media in that item’s `assets/` folder.

## Sync behavior

- `sync: auto` means the package may be updated from WordPress when the source changes.
- `sync: manual` means the package is owned by this repo and will not be overwritten by WordPress sync.

## GitHub Actions

- `Sync live WordPress posts`: pulls new/changed items from `https://fivsevn.com/posts/`, localizes images, rebuilds `index.html`, and commits changes.
- `Hydrate media`: re-downloads remote images and refreshes already-localized assets from their original sources. Use this once after upload, or whenever images look like cached/thumbnails instead of original files.
