---
name: document-pipeline
description: Handling rules for documents as both structured data and rendered artifacts, preserving the original, choosing extraction by content type, and inspecting rendered pages before calling any output complete. Use when reading, extracting, transforming, generating, validating, or visually reviewing PDFs and document deliverables.
---

# Document Pipeline

Treat documents as both structured data and rendered artifacts.

## Intake

- Identify the source format, page count, intended output, audience, and privacy
  level before processing.
- Preserve the original. Write derived files to a separate explicit output path.
- Validate file type and size before invoking a parser or converter.

## Extraction and transformation

- Use text extraction for searchable content and rendering for layout-dependent
  content. Use table extraction only after inspecting the page structure.
- Keep page numbers, headings, tables, and source references where they matter.
- Use `pdfplumber`, `pypdf`, `qpdf`, or `pdfcpu` according to the operation and
  the tools already available in the project.
- Use `uv` for Python execution and dependencies. Do not write secrets into
  generated metadata, temporary files, or output documents.

## Verification

- Validate the output file and confirm page count, readable text, links, tables,
  metadata, and permissions as relevant.
- Render representative pages to images and inspect them after meaningful edits.
- Check clipping, missing fonts, broken tables, overlapping elements, blank pages,
  incorrect page order, and accidental private data.
- Keep intermediate files out of the repository unless they are intentional test
  fixtures.

## Handoff

Provide the output path, source and transformation summary, validation performed,
and any known limitations. Do not describe an uninspected document as complete.

