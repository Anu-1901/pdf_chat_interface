---
name: vector-indexing
description: create and cache a semantic index across one or multiple PDFs. use when implementing embeddings, multi-document retrieval, FAISS indexing, cache keys, or index lifecycle behavior.
---
# Vector Indexing

## Procedure
1. Embed only nonempty `Chunk.text` values from every selected PDF through a small provider-neutral embedding interface.
2. Normalize vectors when the selected FAISS similarity metric requires it.
3. Store document ID, safe filename, page number, and chunk metadata separately; maintain a deterministic vector-to-chunk mapping.
4. Cache the combined index using the stable uploaded-set ID, embedding model ID, and chunking configuration.
5. Expose `search(query, k)` returning chunks with similarity scores. Start with `k=5`.
6. Delete or replace the active index when any file is added, removed, renamed, or changed.

## Rules
- Batch embedding calls and surface rate-limit failures clearly.
- Never place API keys in source code or serialized indexes.
- Do not reuse an index built with another embedding model or changed chunk settings.
- Prefer in-memory FAISS for the simple single-user prototype.

## Acceptance checks
- Repeated questions do not re-embed the PDF.
- Retrieval across files returns metadata aligned with the correct chunk text, filename, and 1-based page.
- Cache keys change when model or chunk settings change.
