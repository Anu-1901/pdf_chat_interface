# PDF chat

A Streamlit app that validates multiple PDFs, extracts page-aware text, builds a
combined in-memory semantic index, and answers questions with exact filename,
page, and supporting-quote references. PDF processing starts automatically
after selection; there is no separate process button.

## Run locally

Use Python 3.10 or newer. From this folder, install the dependencies and start
the app:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

The app uses the existing local `.env` file for Bosch LLM Farm settings. Set
`FARM_API_KEY` using the approved Bosch credential source. The chat and
embedding deployments and API versions are read from:

- `FARM_BASE_URL`
- `FARM_API_KEY`
- `FARM_DEPLOYMENT_NAME`
- `FARM_API_VERSION`
- `EMBEDDING_DEPLOYMENT_NAME`
- `EMBEDDING_API_VERSION`

`PDF_MAX_UPLOAD_MB` optionally changes the per-file upload limit (default:
25 MB). `PDF_MAX_TOTAL_UPLOAD_MB` sets the combined limit (default: 100 MB).
Choose up to 10 PDFs per upload. Keep `.env` out of source control. The app
does not save uploaded PDFs to disk.

## Privacy and limitations

Extracted PDF text and questions are sent to the configured Bosch LLM Farm for
embeddings and answer generation. Do not upload documents you are not permitted
to share with that service. Scanned/image-only PDFs are rejected with an
OCR-required message; OCR is not configured.

The index is kept in process memory and cached by the selected PDF set,
embedding configuration, and chunk settings. Identical PDF bytes within a set
are indexed only once. Retrieval uses normalized embedding vectors and cosine
similarity. Citations show the sanitized filename and that PDF's 1-based viewer
page; each displayed quote must match retrieved source text verbatim (apart
from whitespace normalization). Invalid or unsupported citations are rejected,
and answers with no valid sources abstain.

## Checks

```powershell
python -m unittest discover -s tests -v
```
