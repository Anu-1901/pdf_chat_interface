# Reusable Skills Index

Each feature is isolated under `skills/<skill-name>/SKILL.md`. Coding assistants should load only the skill needed for the current task, while following `agents.md` for the end-to-end sequence and shared contracts.

| Skill | Responsibility | Primary output |
|---|---|---|
| `pdf-upload-validation` | Accept and validate a bounded set of PDFs safely | Validated file records and stable set ID |
| `pdf-text-extraction` | Extract per-file, page-aware text and detect unusable scans | `PageRecord[]` with document provenance |
| `document-chunking` | Create retrieval chunks without losing document or page provenance | `Chunk[]` |
| `vector-indexing` | Build and cache a combined multi-PDF semantic index | Retriever/index handle |
| `pdf-question-answering` | Retrieve evidence across files and produce context-only answers | Draft answer with chunk citations |
| `source-citation-rendering` | Verify exact filename, page, and verbatim quote references | Final grounded `Answer` |
| `streamlit-chat-ui` | Manage multiple uploads, readiness, chat history, reset, sources, and errors | Streamlit interaction flow |
| `pdf-chat-quality-checks` | Validate cross-document retrieval, security, citation fidelity, and UX | Pass/fail report |
| `bosch-llm-farm` | Configure Bosch chat and embedding clients securely | Reusable authenticated model clients |

## Cross-assistant conventions
- `SKILL.md` is the entry point for each skill.
- Follow imperative rules and shared contracts exactly.
- Keep libraries replaceable behind small interfaces; do not couple every skill to one LLM vendor.
- Make the smallest scoped change possible and run the relevant checks afterward.
- If a requested behavior crosses skills, update each affected skill rather than hiding responsibilities in one folder.
