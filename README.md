# lean-horizons

This repository stores source learning materials in archival formats and their converted, AI-friendly derivatives.

## Repository Contract

- `originals/` contains source materials as received.
- `originals/sources/` groups source materials by curriculum section.
- `originals/metadata/` contains manifests that describe source documents.
- `processed/markdown/` contains the canonical AI-readable conversions.
- `processed/html/` contains the mobile-friendly browser versions.

Original files should not be edited in place. When a source document changes, regenerate the matching files under `processed/`.

## Current Structure

```text
originals/
	metadata/
	sources/
		03-prereads/
processed/
	markdown/
		03-prereads/
	html/
		03-prereads/
```

## Naming Guidance

- Keep source folders grouped by topic or curriculum section.
- Prefer slugged names for derived folders and files, such as `03-prereads`.
- Treat Markdown as the canonical text format for agents.
- Treat HTML as the primary mobile-reading format.

## Next Step

As documents are converted, add each source file to the manifest in `originals/metadata/documents-manifest.json` and create matching Markdown and HTML outputs in the mirrored section folders.