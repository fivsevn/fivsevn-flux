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

## GitHub Pages

Set the repository Pages source to the `main` branch root, or use the generated `index.html` directly. `CNAME` is already set to:

```text
flux.fivsevn.com
```
