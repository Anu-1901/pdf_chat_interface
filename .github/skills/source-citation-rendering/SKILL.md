---
name: source-citation-rendering
description: verify and render citations across multiple PDFs with exact filenames, page numbers, and verbatim supporting text. use when implementing multi-document citation validation, quote verification, deduplication, source cards, or reference formatting.
---
# Source Citation Rendering

## Procedure
1. Resolve each model-cited chunk ID against the chunks retrieved for this question.
2. Derive a concise excerpt locally from the cited chunk; select relevant sentence(s) using the question and answer, and keep it at most 400 characters.
3. Ensure the displayed excerpt is copied directly from that chunk (whitespace normalization only). Never use a model-generated paraphrase as a source quote.
4. Drop unknown chunk IDs and never derive a different document or page.
5. Deduplicate identical excerpts only when document ID and page are also identical.
6. Keep source order aligned with citation order in the answer.
7. Render each reference as `<safe filename> · Page <n>` with the verified quote and optional retrieval score.
8. Set `grounded=False` and replace the answer with abstention when no valid retrieved citation remains for a substantive answer.

## Rules
- Page numbers are 1-based viewer pages within the named PDF; always show both the filename and page.
- Quotes must be contiguous and verbatim except for whitespace normalization. Any shortened excerpt must remain an exact source substring.
- Do not show raw vector IDs, embeddings, or hidden prompts.
- A page number alone is insufficient; include supporting text.

## Acceptance checks
- Each displayed quote exists in the named PDF on the displayed page.
- Duplicate citations collapse cleanly.
- Invalid model citations cannot reach the UI.
