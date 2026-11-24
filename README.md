# Shared PDF chat

A Streamlit app that validates multiple PDFs, extracts page-aware text, builds a
combined in-memory semantic index, and answers questions with exact filename,
page, and supporting-quote references. PDF processing starts automatically
after selection; there is no separate process button.

## Authentication and roles

The app requires a trusted OpenID Connect (OIDC) provider through Streamlit's
`st.login` / `st.user` / `st.logout` authentication. It does not use a shared
password or accept role values from browser input.

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Register the app with your OIDC provider and set its client ID, client
   secret, discovery URL, and the app's absolute `/oauth2callback` redirect URI.
      Generate a long random `cookie_secret` and register the matching redirect
      URI with the identity provider. Ensure the provider returns a verified
      `email_verified=true` claim.
3. Configure server-side role policy in `.env` or the deployment environment:
   - `PDF_CHAT_ADMIN_EMAILS`: comma-separated admin email addresses. Admins can
     publish PDFs and chat with library PDFs.
   - `PDF_CHAT_ALLOWED_EMAILS`: additional user email addresses.
   - `PDF_CHAT_ALLOWED_EMAIL_DOMAINS`: permitted user email domains.
   Admins are automatically permitted. All other identities are denied unless
   allowlisted. Use only domains controlled by your organization.

An authenticated user can select and chat with PDFs in the shared library but
cannot publish files. Only administrators see the publishing form.

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
Choose up to 10 PDFs per upload. `PDF_CHAT_LIBRARY_DB` sets the SQLite library
path (default: `data/pdf_chat_library.sqlite3`). The database contains uploaded
PDF bytes and is ignored by Git; protect and back up its storage.

## Privacy and limitations

Extracted PDF text and questions are sent to the configured Bosch LLM Farm for
embeddings and answer generation. Do not upload documents you are not permitted
to share with that service. Scanned/image-only PDFs are rejected with an
OCR-required message; OCR is not configured.

The shared library persists PDFs in SQLite. The index is kept in process
memory and cached by the selected PDF set, embedding configuration, and chunk
settings. Identical PDF bytes within a set
are indexed only once. Retrieval uses normalized embedding vectors and cosine
similarity. Citations show the sanitized filename and that PDF's 1-based viewer
page; each displayed quote must match retrieved source text verbatim (apart
from whitespace normalization). Invalid or unsupported citations are rejected,
and answers with no valid sources abstain.

SQLite is intended for a single-host deployment on protected persistent
storage. It does not encrypt PDF bytes at rest. For production or multiple app
instances, deploy a shared database/object store with appropriate encryption,
access controls, backups, and retention policies. OIDC provider setup and
Bosch LLM Farm credentials must be configured by the deployment administrator.

## Checks

```powershell
python -m unittest discover -s tests -v
```
