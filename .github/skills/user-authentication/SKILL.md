---
name: user-authentication
description: authenticate PDF chat users with OpenID Connect and enforce admin/user access to the shared PDF library. use when implementing login, roles, authorization, admin-only uploads, or protected shared documents.
---
# User Authentication and Roles

## Procedure
1. Use Streamlit's `st.login`, `st.user`, and `st.logout` with a configured trusted OIDC provider. Never build a password-only login form.
2. Require the OIDC provider to return `email_verified=true`; fail closed when OIDC configuration or identity claims are missing.
3. Resolve roles only on the server from `PDF_CHAT_ADMIN_EMAILS`, `PDF_CHAT_ALLOWED_EMAILS`, and/or `PDF_CHAT_ALLOWED_EMAIL_DOMAINS`.
4. Permit admins to publish validated PDFs; permit authorized users to select and chat with PDFs already in the shared library.
5. Gate every library read and write behind authenticated authorization. Do not rely on hiding UI controls as the only admin restriction.
6. Clear chat, selections, and indexes on logout or account changes.
7. Keep provider credentials in `.streamlit/secrets.toml`, keep that file out of source control, and document provider-specific redirect URI setup.

## Rules
- Never trust role claims from widget state, query parameters, uploaded files, or model output.
- Admin identities are explicitly allowlisted and are also allowed to use the library.
- Deny identities not explicitly allowed; do not make an empty allowlist mean public access.
- Persist shared PDFs only in configured protected storage, and disclose storage persistence, encryption, and deployment limitations.
- Do not expose uploaded document content or metadata before authentication and authorization succeed.

## Acceptance checks
- Logged-out users cannot view the library or chat controls.
- An unlisted authenticated identity is denied.
- Admins can publish; regular users cannot publish, including through the storage write API.
- Authorized users can select and chat with admin-published documents.
- Logout and user changes clear stale document and chat state.
