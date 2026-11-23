---
name: pdf-chat-quality-checks
description: test and review a multi-document Streamlit PDF chat implementation for cross-file retrieval, exact citations, security, state management, and failure handling. use before merging or releasing changes.
---
# PDF Chat Quality Checks

## Test set
Run at least these cases:
1. One native-text PDF with a direct factual answer.
2. Multiple PDFs, including the same page number in different files; ask a question whose answer spans files.
3. Answer spanning two pages, preserving each source PDF's independent page numbering.
4. Unsupported question requiring abstention.
5. Scanned or image-only PDF within a multi-file set.
6. Empty, malformed, encrypted, renamed non-PDF, individually oversized, aggregate-oversized, and too-many-file uploads.
7. Same filename with changed bytes, same bytes with changed filename, identical duplicate files, and reordering the same selected set.
8. Prompt injection text inside any selected PDF.
9. Citation IDs not retrieved, incorrect filenames/pages, and excerpts derived from the wrong source chunk.
10. Model paraphrases a supporting quote; verify that citation acceptance uses the valid chunk ID and that the displayed quote is still copied from source text.
11. Repeated questions, Streamlit reruns, removing a file, and reset behavior.

## Verify
- Each citation shows the correct safe filename and 1-based page in that PDF's viewer; each quote is verbatim and exists on that page.
- Every substantive answer has supporting text.
- No unsupported claim is added from model memory.
- Index construction occurs once per cache key.
- Any selected-set change clears stale history and retrieval state; reordering does not trigger a false change.
- Secrets and document text are absent from logs.
- Errors are understandable and recoverable.

## Output format
Return a checklist with `PASS`, `FAIL`, or `BLOCKED`, evidence, and the smallest recommended fix. Do not mark the feature complete while citation validation, prompt-injection resistance, or stale-index isolation fails.
