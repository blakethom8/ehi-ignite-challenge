# uploads — PDF Lab dropbox

The dropbox the PDF Lab and the notebook use to land arbitrary PDFs that aren't yet a "real" corpus source. Uploads are durable across sessions but **gitignored** — treat anything under here as potentially PHI.

## Layout

```
uploads/
├── README.md                 ← this file (committed)
├── manifest.json             ← chronological index of all uploads (gitignored)
├── <12-hex-prefix>/          ← one directory per upload, named by SHA-256 prefix
│   ├── data.pdf              ← original bytes, byte-identical
│   └── upload_meta.json      ← {hash_prefix, sha256, original_filename, label,
│                                uploaded_at, size_bytes}
```

## How uploads land here

- **From the Streamlit PDF Lab** (`app/pages/02b_PDF_Lab.py`): the file uploader calls `ehi_atlas.extract.uploads.store_upload()` with the bytes.
- **From the notebook** (`notebooks/03_layer2b_vision_extraction.ipynb`): the cell that lets you point at any PDF calls `store_upload_from_path()`.

Both paths are idempotent — uploading the same PDF twice returns the same `UploadRecord` and does not duplicate the bytes on disk.

## Promotion path

If an upload turns out to be a recurring fixture (e.g. you'll keep extracting against it during dev), promote it to a proper source:

1. Pick a source-tag (`my-portal`, `cedars-discharge`, etc.)
2. Move the PDF to `corpus/_sources/<source-tag>/raw/`
3. Add a `README.md` describing where it came from and the consent posture
4. Update `corpus/README.md`'s reproduction recipe

The upload directory then becomes safe to clear with `remove_upload(hash_prefix)`.
