from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import openai
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from streamlit.errors import StreamlitSecretNotFoundError

from access_control import parse_csv_values, resolve_role
from document_library import (
    LibraryDocument,
    get_documents,
    list_documents,
    save_documents,
)
from pdf_chat import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_TOTAL_UPLOAD_BYTES,
    MAX_DOCUMENTS_PER_UPLOAD,
    Answer,
    PDFChatError,
    PageRecord,
    VectorIndex,
    answer_question,
    build_vector_index,
    document_set_id,
    prepare_documents,
)

load_dotenv()


@dataclass(frozen=True)
class FarmSettings:
    base_url: str
    api_key: str
    chat_deployment: str
    chat_api_version: str
    embedding_deployment: str
    embedding_api_version: str


class ModelConfigurationError(Exception):
    """The required Bosch LLM Farm configuration is incomplete."""


def missing_farm_settings() -> list[str]:
    required = (
        "FARM_BASE_URL",
        "FARM_API_KEY",
        "FARM_DEPLOYMENT_NAME",
        "FARM_API_VERSION",
        "EMBEDDING_DEPLOYMENT_NAME",
        "EMBEDDING_API_VERSION",
    )
    return [name for name in required if not os.getenv(name)]


def get_farm_settings() -> FarmSettings:
    missing = missing_farm_settings()
    if missing:
        raise ModelConfigurationError(
            "Bosch LLM Farm configuration is incomplete. Add these settings to "
            f"your local .env file: {', '.join(missing)}."
        )

    return FarmSettings(
        base_url=os.environ["FARM_BASE_URL"],
        api_key=os.environ["FARM_API_KEY"],
        chat_deployment=os.environ["FARM_DEPLOYMENT_NAME"],
        chat_api_version=os.environ["FARM_API_VERSION"],
        embedding_deployment=os.environ["EMBEDDING_DEPLOYMENT_NAME"],
        embedding_api_version=os.environ["EMBEDDING_API_VERSION"],
    )


@st.cache_resource(max_entries=4)
def get_embeddings(
    base_url: str,
    deployment: str,
    api_version: str,
    _api_key: str,
) -> AzureOpenAIEmbeddings:
    http_client = httpx.Client(
        headers={"genaiplatform-farm-subscription-key": _api_key},
        timeout=60.0,
    )
    return AzureOpenAIEmbeddings(
        api_key=_api_key,
        azure_endpoint=base_url,
        azure_deployment=deployment,
        api_version=api_version,
        http_client=http_client,
    )


@st.cache_resource(max_entries=4)
def get_chat_model(
    base_url: str,
    deployment: str,
    api_version: str,
    _api_key: str,
) -> AzureChatOpenAI:
    http_client = httpx.Client(
        headers={"genaiplatform-farm-subscription-key": _api_key},
        timeout=60.0,
    )
    return AzureChatOpenAI(
        api_key=_api_key,
        azure_endpoint=base_url,
        azure_deployment=deployment,
        api_version=api_version,
        http_client=http_client,
        temperature=0,
    )


@st.cache_resource(max_entries=8)
def get_document_index(
    document_id: str,
    page_data: tuple[tuple[str, str, int, str], ...],
    base_url: str,
    embedding_deployment: str,
    embedding_api_version: str,
    chunk_size: int,
    overlap: int,
    _api_key: str,
) -> VectorIndex:
    settings = get_embeddings(
        base_url,
        embedding_deployment,
        embedding_api_version,
        _api_key,
    )
    pages = tuple(
        PageRecord(
            page_number=page_number,
            text=text,
            document_id=source_id,
            document_name=source_name,
        )
        for source_id, source_name, page_number, text in page_data
    )
    model_id = f"{base_url}:{embedding_deployment}:{embedding_api_version}"
    return build_vector_index(
        document_id,
        pages,
        settings,
        model_id=model_id,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def initialize_state() -> None:
    defaults: dict[str, Any] = {
        "document_id": None,
        "document_name": None,
        "document_names": (),
        "duplicate_document_count": 0,
        "status": "empty",
        "pages": (),
        "chunks": (),
        "index": None,
        "messages": [],
        "error_message": None,
        "upload_widget_version": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_document_state() -> None:
    st.session_state.document_id = None
    st.session_state.document_name = None
    st.session_state.document_names = ()
    st.session_state.duplicate_document_count = 0
    st.session_state.status = "empty"
    st.session_state.pages = ()
    st.session_state.chunks = ()
    st.session_state.index = None
    st.session_state.messages = []
    st.session_state.error_message = None


def reset_document() -> None:
    clear_document_state()
    st.session_state.selected_document_ids = []


def sign_out() -> None:
    clear_document_state()
    st.session_state.selected_document_ids = []
    st.session_state.authenticated_user_email = None
    st.logout()


def configured_oidc_auth() -> bool:
    try:
        auth_settings = st.secrets.get("auth", {})
    except StreamlitSecretNotFoundError:
        return False
    required = (
        "redirect_uri",
        "cookie_secret",
        "client_id",
        "client_secret",
        "server_metadata_url",
    )
    return isinstance(auth_settings, Mapping) and all(
        isinstance(auth_settings.get(key), str) and auth_settings[key].strip()
        for key in required
    )


def authenticate_user() -> tuple[str, str, str] | None:
    if not configured_oidc_auth():
        st.title("PDF chat sign-in is not configured")
        st.error(
            "Configure an OpenID Connect provider in "
            "`.streamlit/secrets.toml` before users can sign in. See "
            "`.streamlit/secrets.toml.example`."
        )
        return None

    if not st.user.is_logged_in:
        st.title("Sign in to PDF chat")
        st.caption("Use your organization account to access the shared PDF library.")
        if st.button("Sign in", icon=":material/login:", type="primary"):
            st.login()
        return None

    email = st.user.get("email")
    email_verified = st.user.get("email_verified") is True
    if not email_verified:
        st.error(
            "The identity provider must supply a verified email address to access "
            "the PDF library."
        )
        st.button("Sign out", on_click=sign_out)
        return None

    role = resolve_role(
        email,
        parse_csv_values(os.getenv("PDF_CHAT_ADMIN_EMAILS")),
        parse_csv_values(os.getenv("PDF_CHAT_ALLOWED_EMAILS")),
        parse_csv_values(os.getenv("PDF_CHAT_ALLOWED_EMAIL_DOMAINS")),
        email_verified=email_verified,
    )
    if role is None:
        st.title("You are not authorized to use PDF chat")
        st.error(
            "Your account is not on the permitted user list. Ask an administrator "
            "to add your email or organization domain."
        )
        st.button("Sign out", on_click=sign_out)
        return None

    normalized_email = str(email).strip().casefold()
    display_name = st.user.get("name") or normalized_email
    return normalized_email, str(display_name), role


def render_sources(answer: Answer) -> None:
    for source in answer.sources:
        with st.expander(f"{source.document_name} · Page {source.page_number}"):
            st.text(source.quote)
            st.caption(f"Retrieval similarity: {source.score:.3f}")


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(message["content"])
        else:
            st.markdown(message["content"])
            for source in message.get("sources", []):
                with st.expander(
                    f"{source['document_name']} · Page {source['page_number']}"
                ):
                    st.text(source["quote"])
                    st.caption(f"Retrieval similarity: {source['score']:.3f}")


def show_processing_error(error: Exception) -> None:
    st.session_state.status = "error"
    st.session_state.error_message = str(error)
    st.session_state.pages = ()
    st.session_state.chunks = ()
    st.session_state.index = None


def database_path() -> Path:
    configured_path = os.getenv("PDF_CHAT_LIBRARY_DB")
    path = Path(configured_path) if configured_path else Path("data/pdf_chat_library.sqlite3")
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def configured_upload_limits() -> tuple[int, int]:
    try:
        max_file_mb = float(os.getenv("PDF_MAX_UPLOAD_MB", "25"))
        max_total_mb = float(
            os.getenv(
                "PDF_MAX_TOTAL_UPLOAD_MB",
                str(DEFAULT_MAX_TOTAL_UPLOAD_BYTES / (1024 * 1024)),
            )
        )
    except ValueError as exc:
        raise ValueError("PDF upload limits must be valid numbers.") from exc
    if not 0 < max_file_mb <= 200 or not 0 < max_total_mb <= 1024:
        raise ValueError(
            "Upload limits must be greater than 0; each PDF is limited to "
            "200 MB and the combined upload to 1024 MB."
        )
    return int(max_file_mb * 1024 * 1024), int(max_total_mb * 1024 * 1024)


def process_selected_documents(
    selected_documents: tuple[tuple[str, str, bytes], ...],
    expected_set_id: str,
) -> None:
    st.session_state.status = "extracting"
    try:
        max_file_bytes, max_total_bytes = configured_upload_limits()
        uploads = tuple((name, pdf_bytes) for _, name, pdf_bytes in selected_documents)
        document_id, document_names, pages, duplicate_count = prepare_documents(
            uploads,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            max_documents=MAX_DOCUMENTS_PER_UPLOAD,
        )
        if document_id != expected_set_id:
            raise PDFChatError(
                "A selected PDF changed in the shared library. Refresh and select it again."
            )

        st.session_state.document_names = document_names
        st.session_state.document_name = ", ".join(document_names)
        st.session_state.pages = pages
        st.session_state.status = "indexing"

        farm = get_farm_settings()
        page_data = tuple(
            (
                page.document_id,
                page.document_name,
                page.page_number,
                page.text,
            )
            for page in pages
        )
        index = get_document_index(
            document_id,
            page_data,
            farm.base_url,
            farm.embedding_deployment,
            farm.embedding_api_version,
            DEFAULT_CHUNK_SIZE,
            DEFAULT_CHUNK_OVERLAP,
            farm.api_key,
        )
        st.session_state.index = index
        st.session_state.chunks = index.chunks
        st.session_state.status = "ready"
        st.session_state.error_message = None
        st.session_state.duplicate_document_count = duplicate_count
    except (PDFChatError, ModelConfigurationError, ValueError) as exc:
        show_processing_error(exc)
    except openai.RateLimitError:
        show_processing_error(
            PDFChatError(
                "Bosch LLM Farm rate limit reached while building the index. "
                "Wait briefly, then try selecting the PDFs again."
            )
        )
    except (httpx.HTTPError, openai.APIError):
        show_processing_error(
            PDFChatError(
                "Bosch LLM Farm could not build the PDF index. Check the network, "
                "deployment settings, and service access, then try again."
            )
        )
    except (OSError, sqlite3.Error, LookupError) as exc:
        show_processing_error(
            PDFChatError(f"The shared PDF library could not load the selection: {exc}")
        )


st.set_page_config(page_title="PDF chat", page_icon=":material/description:", layout="centered")
initialize_state()
identity = authenticate_user()
if identity is None:
    st.stop()

user_email, display_name, role = identity
if st.session_state.get("authenticated_user_email") != user_email:
    clear_document_state()
    st.session_state.authenticated_user_email = user_email
st.session_state.setdefault("selected_document_ids", [])

st.title("Chat with shared PDFs")
st.caption("Select PDFs from your organization library and ask questions with exact source references.")

with st.sidebar:
    st.header("Your account")
    st.text(display_name)
    st.caption(f"{user_email} · {role}")
    st.button(
        "Sign out",
        icon=":material/logout:",
        on_click=sign_out,
        width="stretch",
    )
    st.button(
        "Clear selection and chat",
        icon=":material/refresh:",
        on_click=reset_document,
        width="stretch",
    )
    st.divider()
    st.header("Shared PDF library")
    st.info(
        "PDF text and questions are sent to the configured Bosch LLM Farm. "
        "Upload only documents approved for this service."
    )

    try:
        max_file_bytes, max_total_bytes = configured_upload_limits()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    if role == "admin":
        with st.form("admin_pdf_upload_form", clear_on_submit=True):
            uploaded_files = st.file_uploader(
                "Add PDFs to the shared library",
                type=["pdf"],
                accept_multiple_files=True,
                max_upload_size=max(1, max_file_bytes // (1024 * 1024)),
                help=(
                    f"Up to {MAX_DOCUMENTS_PER_UPLOAD} PDFs; "
                    f"{max_file_bytes // (1024 * 1024)} MB per file and "
                    f"{max_total_bytes // (1024 * 1024)} MB total."
                ),
            )
            publish_documents = st.form_submit_button(
                "Publish to library",
                icon=":material/library_add:",
                type="primary",
                width="stretch",
            )
        if publish_documents:
            if not uploaded_files:
                st.error("Choose at least one PDF to publish.")
            else:
                try:
                    uploads = tuple(
                        (uploaded_file.name, uploaded_file.getvalue())
                        for uploaded_file in uploaded_files
                    )
                    inserted_ids, existing_ids, duplicate_count = save_documents(
                        database_path(),
                        uploads,
                        user_email,
                        is_admin=(role == "admin"),
                        max_file_bytes=max_file_bytes,
                        max_total_bytes=max_total_bytes,
                        max_documents=MAX_DOCUMENTS_PER_UPLOAD,
                    )
                    st.session_state.selected_document_ids = list(
                        dict.fromkeys(inserted_ids + existing_ids)
                    )
                    if inserted_ids:
                        st.success(f"Published {len(inserted_ids)} PDF(s).")
                    if existing_ids:
                        st.info(f"{len(existing_ids)} PDF(s) were already in the library.")
                    if duplicate_count:
                        st.caption(
                            f"Ignored {duplicate_count} duplicate file(s) in this upload."
                        )
                    st.rerun()
                except (PDFChatError, ValueError, PermissionError) as exc:
                    st.error(str(exc))
                except (OSError, sqlite3.Error):
                    st.error(
                        "The shared library could not save the PDFs. Check the "
                        "configured storage path and permissions, then try again."
                    )
    elif not parse_csv_values(os.getenv("PDF_CHAT_ADMIN_EMAILS")):
        st.warning("No administrators are configured; PDF uploads are disabled.")

try:
    library_documents = list_documents(database_path())
except (OSError, sqlite3.Error):
    st.error(
        "The shared PDF library is unavailable. Check the configured storage "
        "path and permissions."
    )
    st.stop()

document_by_id: dict[str, LibraryDocument] = {
    document.document_id: document for document in library_documents
}
valid_document_ids = set(document_by_id)
st.session_state.selected_document_ids = [
    document_id
    for document_id in st.session_state.selected_document_ids
    if document_id in valid_document_ids
]

if not library_documents:
    st.info("The shared PDF library is empty. An administrator must publish PDFs first.")
    selected_ids: tuple[str, ...] = ()
else:
    selected_ids = tuple(
        st.multiselect(
            "Choose PDFs to chat with",
            options=tuple(document_by_id),
            key="selected_document_ids",
            format_func=lambda document_id: (
                f"{document_by_id[document_id].document_name} · {document_id[:8]}"
            ),
            max_selections=MAX_DOCUMENTS_PER_UPLOAD,
            help="All selected PDFs are searched together. Page numbers restart for each file.",
        )
    )

selected_set_id = (
    document_set_id(
        tuple(
            (document_id, document_by_id[document_id].document_name)
            for document_id in selected_ids
        )
    )
    if selected_ids
    else None
)

if selected_set_id is None:
    clear_document_state()
    st.info("Select one or more library PDFs to start a chat.")
elif st.session_state.document_id != selected_set_id:
    clear_document_state()
    st.session_state.document_id = selected_set_id
    try:
        selected_documents = get_documents(database_path(), selected_ids)
        with st.status("Preparing the selected PDFs...", expanded=False) as progress:
            progress.update(label="Extracting and indexing selected PDFs...")
            process_selected_documents(selected_documents, selected_set_id)
            if st.session_state.status == "ready":
                progress.update(label="PDFs ready", state="complete")
            else:
                progress.update(label="PDF processing failed", state="error", expanded=True)
    except (OSError, sqlite3.Error, LookupError, ValueError) as exc:
        show_processing_error(exc)

if st.session_state.status == "ready":
    st.success(
        f"{len(st.session_state.document_names)} PDF(s) ready: "
        f"{st.session_state.document_name} "
        f"({len(st.session_state.pages)} pages, {len(st.session_state.chunks)} chunks)."
    )
elif st.session_state.status == "error":
    st.error(st.session_state.error_message or "The selected PDFs could not be processed.")

for chat_message in st.session_state.messages:
    render_message(chat_message)

question = st.chat_input(
    "Ask a question about the selected PDFs",
    disabled=st.session_state.status != "ready",
)
if question:
    question = question.strip()
    if question:
        previous_messages = list(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        try:
            farm = get_farm_settings()
            chat_model = get_chat_model(
                farm.base_url,
                farm.chat_deployment,
                farm.chat_api_version,
                farm.api_key,
            )
            with st.chat_message("assistant"):
                with st.spinner("Searching the selected PDFs and checking evidence..."):
                    answer = answer_question(
                        question,
                        previous_messages,
                        st.session_state.index,
                        chat_model,
                    )
                st.markdown(answer.answer)
                render_sources(answer)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer.answer,
                    "sources": [
                        {
                            "document_name": source.document_name,
                            "document_id": source.document_id,
                            "page_number": source.page_number,
                            "quote": source.quote,
                            "score": source.score,
                        }
                        for source in answer.sources
                    ],
                    "grounded": answer.grounded,
                }
            )
        except ModelConfigurationError as exc:
            error_message = str(exc)
            with st.chat_message("assistant"):
                st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message, "error": True}
            )
        except PDFChatError as exc:
            error_message = str(exc)
            with st.chat_message("assistant"):
                st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message, "error": True}
            )
        except openai.RateLimitError:
            error_message = (
                "Bosch LLM Farm rate limit reached. Wait briefly, then ask again."
            )
            with st.chat_message("assistant"):
                st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message, "error": True}
            )
        except (httpx.HTTPError, openai.APIError):
            error_message = (
                "Bosch LLM Farm could not answer this question. Check the network, "
                "deployment settings, and service access, then try again."
            )
            with st.chat_message("assistant"):
                st.error(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message, "error": True}
            )
