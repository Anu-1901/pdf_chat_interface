from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import openai
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

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
    document_bundle_id,
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
    st.session_state.upload_widget_version += 1


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


def process_upload(documents: tuple[tuple[str, bytes], ...], document_id: str) -> None:
    st.session_state.status = "validating"
    with st.status("Validating uploaded PDF...", expanded=True) as progress:
        try:
            max_upload_mb = float(os.getenv("PDF_MAX_UPLOAD_MB", "25"))
            max_total_upload_mb = float(
                os.getenv(
                    "PDF_MAX_TOTAL_UPLOAD_MB",
                    str(DEFAULT_MAX_TOTAL_UPLOAD_BYTES / (1024 * 1024)),
                )
            )
            if not 0 < max_upload_mb <= 200 or not 0 < max_total_upload_mb <= 1024:
                raise ValueError(
                    "Upload limits must be greater than 0; each PDF is limited to "
                    "200 MB and the combined upload to 1024 MB."
                )
            max_upload_bytes = int(max_upload_mb * 1024 * 1024)
            bundle_id, document_names, pages, duplicate_count = prepare_documents(
                documents,
                max_upload_bytes,
                int(max_total_upload_mb * 1024 * 1024),
                MAX_DOCUMENTS_PER_UPLOAD,
            )
            if bundle_id != document_id:
                raise PDFChatError(
                    "The uploaded file changed while it was being processed."
                )

            st.session_state.document_names = document_names
            st.session_state.document_name = ", ".join(document_names)
            st.session_state.status = "extracting"
            st.session_state.pages = pages

            st.session_state.status = "indexing"
            progress.update(
                label=f"Extracted {len(pages)} pages; building the semantic index...",
                state="running",
            )
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
            progress.update(label="PDFs ready", state="complete", expanded=False)
        except (PDFChatError, ModelConfigurationError, ValueError) as exc:
            show_processing_error(exc)
            progress.update(label="PDF processing failed", state="error", expanded=True)
        except openai.RateLimitError:
            show_processing_error(
                PDFChatError(
                    "Bosch LLM Farm rate limit reached while building the index. "
                    "Wait briefly, then reset and upload the PDF again."
                )
            )
            progress.update(label="PDF processing failed", state="error", expanded=True)
        except (httpx.HTTPError, openai.APIError):
            show_processing_error(
                PDFChatError(
                    "Bosch LLM Farm could not build the PDF index. Check the network, "
                    "deployment settings, and service access, then reset and upload again."
                )
            )
            progress.update(label="PDF processing failed", state="error", expanded=True)


st.set_page_config(page_title="PDF chat", page_icon=":material/description:", layout="centered")
initialize_state()
st.title("Chat with PDFs")
st.caption("Upload text-based PDFs and ask questions with exact file and page references.")

with st.sidebar:
    st.header("Your document")
    st.info(
        "PDF text and your questions are sent to the configured Bosch LLM Farm "
        "for search and answer generation. Upload only documents you are permitted "
        "to share with that service."
    )
    missing_settings = missing_farm_settings()
    if missing_settings:
        st.warning(
            "Bosch LLM Farm is not ready. Configure the required settings in your "
            "local .env file before processing a PDF."
        )
    if st.session_state.document_names:
        st.caption("Selected PDFs")
        for document_name in st.session_state.document_names:
            st.text(document_name)
    st.button(
        "Reset PDFs",
        icon=":material/delete:",
        on_click=reset_document,
        width="stretch",
    )

    upload_key = f"pdf_upload_{st.session_state.upload_widget_version}"
    uploaded_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=upload_key,
        help=(
            f"Choose up to {MAX_DOCUMENTS_PER_UPLOAD} PDFs. Each file can be up to "
            "25 MB by default; the combined default limit is 100 MB."
        ),
    )

uploaded_documents = (
    tuple((uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in uploaded_files)
    if uploaded_files
    else ()
)

if uploaded_documents:
    uploaded_id = document_bundle_id(uploaded_documents)
    if st.session_state.document_id != uploaded_id:
        clear_document_state()
        st.session_state.document_id = uploaded_id
        process_upload(uploaded_documents, uploaded_id)
elif st.session_state.document_id is not None:
    clear_document_state()

if st.session_state.status == "ready":
    st.success(
        f"{len(st.session_state.document_names)} PDF(s) ready: "
        f"{st.session_state.document_name} "
        f"({len(st.session_state.pages)} pages, {len(st.session_state.chunks)} chunks)."
    )
    if st.session_state.get("duplicate_document_count", 0):
        st.caption(
            f"Ignored {st.session_state.duplicate_document_count} duplicate upload(s)."
        )
elif st.session_state.status == "error":
    st.error(st.session_state.error_message or "The PDF could not be processed.")
elif st.session_state.status in {"validating", "extracting", "indexing"}:
    st.info(f"Document status: {st.session_state.status}.")
elif not uploaded_files:
    st.info("Upload one or more PDFs in the sidebar to get started.")

for chat_message in st.session_state.messages:
    render_message(chat_message)

question = st.chat_input(
    "Ask a question about the uploaded PDF",
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
                with st.spinner("Searching the PDF and checking its evidence..."):
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
