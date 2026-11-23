---
name: document-chunking
description: split pages from one or multiple PDFs into retrieval-ready chunks while preserving document and page provenance. use when changing chunk size, overlap, boundaries, metadata, or stable chunk identifiers.
---
# Document Chunking

## Procedure
1. Chunk each page of each document independently so one chunk never claims the wrong document or page.
2. Prefer paragraph boundaries, then sentence boundaries, then character boundaries.
3. Start with 900 characters and 150-character overlap; make both configurable.
4. Remove empty chunks and avoid chunks made only of headers, footers, or whitespace when confidently detected.
5. Create stable IDs such as `<document_sha256>:p<page>:c<ordinal>`, unique across the uploaded set.
6. Emit `Chunk` records with document ID, safe display name, text, page number, and offsets into that document's normalized page text.

## Rules
- Never merge text across documents or pages. The default implementation must not merge.
- Keep overlap smaller than chunk size.
- Preserve tables and lists as coherent blocks where practical.
- Rebuild chunks when chunking configuration changes.

## Acceptance checks
- Every chunk maps to existing source text on exactly one named document and one page.
- IDs are deterministic for identical input and configuration.
- No chunk is empty or larger than the configured hard limit.
