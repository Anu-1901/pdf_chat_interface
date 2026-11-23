---
name: pdf-upload-validation
description: validate one or multiple uploaded PDFs before processing. use when implementing or modifying multi-file Streamlit upload handling, per-file and aggregate limits, signature checks, hashing, duplicate detection, or safe rejection behavior.
---
# PDF Upload Validation

## Procedure
1. Accept 1–10 files using `st.file_uploader(type=["pdf"], accept_multiple_files=True)`.
2. Reject empty files and enforce a configurable per-file limit (25 MB by default) and combined limit (100 MB by default).
3. Verify each file starts with `%PDF-`; do not trust its extension or MIME type.
4. Parse each PDF from in-memory bytes. Never build a filesystem path from an uploaded filename.
5. Compute a SHA-256 ID per file. Derive a stable set ID from the unique file hashes and sanitized display names for session-state invalidation and index caching.
6. Deduplicate identical file bytes in one upload set; do not create duplicate chunks or ambiguous citations.
7. Process the selected set atomically: a rejected member must not leave the previous or a partial set chat-ready.

## Rules
- Sanitize the filename for display and logs.
- Do not persist uploads unless the product explicitly requires it.
- Clear previous index, sources, and chat state whenever the selected PDF set changes or is removed.
- Handle encrypted, malformed, and parser-rejected PDFs without exposing stack traces.

## Acceptance checks
- A renamed non-PDF is rejected.
- A zero-byte or oversized file is rejected.
- Uploading the same unique file set in another order produces the same set ID.
- Identical bytes under another name are deduplicated and reported.
- Changing any PDF's bytes or display name invalidates the active set.
