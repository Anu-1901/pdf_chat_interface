"""Persistent shared PDF library backed by a local SQLite database."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pdf_chat import (
    DEFAULT_MAX_TOTAL_UPLOAD_BYTES,
    MAX_DOCUMENTS_PER_UPLOAD,
    prepare_documents,
)


@dataclass(frozen=True)
class LibraryDocument:
    document_id: str
    document_name: str
    uploaded_at: str
    uploaded_by: str
    size_bytes: int


def connect_library(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    try:
        if os.name == "posix":
            path.chmod(0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                document_name TEXT NOT NULL,
                pdf_bytes BLOB NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                uploaded_by TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK (size_bytes > 0)
            )
            """
        )
        connection.commit()
        if os.name == "posix":
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{path}{suffix}")
                if sidecar.exists():
                    sidecar.chmod(0o600)
    except (OSError, sqlite3.Error):
        connection.close()
        raise
    return connection


def list_documents(database_path: str | Path) -> tuple[LibraryDocument, ...]:
    connection = connect_library(database_path)
    try:
        rows = connection.execute(
            """
            SELECT document_id, document_name, uploaded_at, uploaded_by, size_bytes
            FROM documents
            ORDER BY document_name COLLATE NOCASE, document_id
            """
        ).fetchall()
    finally:
        connection.close()
    return tuple(
        LibraryDocument(
            document_id=row["document_id"],
            document_name=row["document_name"],
            uploaded_at=row["uploaded_at"],
            uploaded_by=row["uploaded_by"],
            size_bytes=row["size_bytes"],
        )
        for row in rows
    )


def save_documents(
    database_path: str | Path,
    uploads: tuple[tuple[str, bytes], ...],
    uploaded_by: str,
    *,
    is_admin: bool,
    max_file_bytes: int,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_UPLOAD_BYTES,
    max_documents: int = MAX_DOCUMENTS_PER_UPLOAD,
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    if not is_admin:
        raise PermissionError("Only administrators can add PDFs to the shared library.")
    if not uploaded_by.strip():
        raise ValueError("An authenticated uploader identity is required.")

    _, _, pages, duplicate_count = prepare_documents(
        uploads,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        max_documents=max_documents,
    )
    display_names = {
        page.document_id: page.document_name
        for page in pages
    }
    unique_uploads: dict[str, tuple[str, bytes]] = {}
    for filename, pdf_bytes in uploads:
        document_id = hashlib.sha256(pdf_bytes).hexdigest()
        if document_id not in unique_uploads:
            unique_uploads[document_id] = (
                display_names[document_id],
                pdf_bytes,
            )

    inserted_ids: list[str] = []
    existing_ids: list[str] = []
    connection = connect_library(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for document_id, (document_name, pdf_bytes) in unique_uploads.items():
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO documents
                    (document_id, document_name, pdf_bytes, uploaded_by, size_bytes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    document_name,
                    sqlite3.Binary(pdf_bytes),
                    uploaded_by.strip(),
                    len(pdf_bytes),
                ),
            )
            (inserted_ids if cursor.rowcount else existing_ids).append(document_id)
        connection.commit()
    finally:
        connection.close()

    return tuple(inserted_ids), tuple(existing_ids), duplicate_count


def get_documents(
    database_path: str | Path,
    document_ids: Iterable[str],
) -> tuple[tuple[str, str, bytes], ...]:
    requested_ids = tuple(dict.fromkeys(document_ids))
    if not requested_ids:
        return ()

    placeholders = ",".join("?" for _ in requested_ids)
    connection = connect_library(database_path)
    try:
        rows = connection.execute(
            f"""
            SELECT document_id, document_name, pdf_bytes
            FROM documents
            WHERE document_id IN ({placeholders})
            """,
            requested_ids,
        ).fetchall()
    finally:
        connection.close()

    documents_by_id = {
        row["document_id"]: (
            row["document_name"],
            bytes(row["pdf_bytes"]),
        )
        for row in rows
    }
    missing_ids = set(requested_ids) - documents_by_id.keys()
    if missing_ids:
        raise LookupError("One or more selected PDFs are no longer in the library.")

    result: list[tuple[str, str, bytes]] = []
    for document_id in requested_ids:
        document_name, pdf_bytes = documents_by_id[document_id]
        if hashlib.sha256(pdf_bytes).hexdigest() != document_id:
            raise ValueError(
                f"The stored PDF '{document_name}' failed its integrity check."
            )
        result.append((document_id, document_name, pdf_bytes))
    return tuple(result)
