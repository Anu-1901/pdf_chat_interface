---
name: streamlit-chat-ui
description: implement a Streamlit chat experience for one or multiple PDFs. use when building multi-file upload, automatic indexing, readiness indicators, chat state, reset behavior, filename-and-page citations, or user-facing errors.
---
# Streamlit Chat UI

## Layout
- Title and one-sentence instruction.
- Sidebar uploader that accepts a bounded set of PDFs, processing status, selected filenames, and reset button.
- Main chat history using `st.chat_message`.
- Question input using `st.chat_input`, disabled until indexing succeeds.

## State
Maintain a stable selected-set ID, selected filenames, `status`, page/chunk provenance, `index`, and `messages` in `st.session_state`. Keep large derived objects in `st.cache_resource` keyed by the unique PDF hashes, selected filenames, model ID, and chunking configuration.

## Procedure
1. Require an authenticated OIDC identity before loading the library or rendering protected controls.
2. Resolve authorization from server-side allowlists: admins may publish, while permitted users may only select library PDFs and chat.
3. Detect additions, removals, renames, replacements, and reordering in the selected PDF set; a set's identity is order-independent.
4. Validate every admin upload before atomically saving the set to shared storage.
5. Automatically extract, chunk, and index the selected library documents atomically.
6. Update status through `validating`, `extracting`, `indexing`, `ready`, or `error`.
7. On each question, append the user message, search the combined index, run QA, append the assistant answer, and render each verified source as `<filename> · Page <n>` with its exact quote.
8. On logout, account change, reset, or selection change, clear stale document and chat state.

## Rules
- Never require a separate Process button.
- Never trust a browser-supplied role or expose admin upload controls to users.
- Do not load or reveal library contents before authentication and authorization succeed.
- Avoid reprocessing on every Streamlit rerun.
- Show concise recovery-oriented errors without stack traces.
- Disable chat for scanned PDFs when OCR is unavailable.
- Keep answers and filename/page/quote references together in chat history.

## Acceptance checks
- A valid multi-PDF set becomes ready automatically, and every PDF starts page numbering at 1.
- Sending a question does not rebuild the index.
- Changing one selected PDF clears all stale references and messages; reset clears the whole set.
- Logged-out and unauthorized visitors cannot see library files, upload controls, or chat history.
