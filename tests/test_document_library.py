import hashlib
import tempfile
import unittest
from pathlib import Path

import pymupdf

from document_library import get_documents, list_documents, save_documents
from pdf_chat import PDFValidationError


def make_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


class DocumentLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.directory.name) / "library.sqlite3"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_only_admins_can_publish_and_upload_is_atomic(self) -> None:
        pdf_bytes = make_pdf(
            "This is enough text for a valid searchable shared library document."
        )
        with self.assertRaises(PermissionError):
            save_documents(
                self.database_path,
                (("first.pdf", pdf_bytes),),
                "user@example.com",
                is_admin=False,
                max_file_bytes=1_000_000,
            )
        self.assertEqual(list_documents(self.database_path), ())

        with self.assertRaises(PDFValidationError):
            save_documents(
                self.database_path,
                (
                    ("first.pdf", pdf_bytes),
                    ("renamed.txt", b"not a pdf"),
                ),
                "admin@example.com",
                is_admin=True,
                max_file_bytes=1_000_000,
            )
        self.assertEqual(list_documents(self.database_path), ())

    def test_admin_uploads_are_shared_and_users_can_read_only_selected_files(self) -> None:
        first_pdf = make_pdf(
            "First document contains enough text to be a useful shared search source."
        )
        second_pdf = make_pdf(
            "Second document contains distinct searchable text for another user."
        )
        inserted, existing, duplicates = save_documents(
            self.database_path,
            (("first.pdf", first_pdf), ("second.pdf", second_pdf)),
            "admin@example.com",
            is_admin=True,
            max_file_bytes=1_000_000,
        )
        self.assertEqual(len(inserted), 2)
        self.assertEqual(existing, ())
        self.assertEqual(duplicates, 0)

        library = list_documents(self.database_path)
        self.assertEqual({document.document_id for document in library}, set(inserted))
        selected_id = inserted[0]
        selected = get_documents(self.database_path, (selected_id,))
        self.assertEqual(len(selected), 1)
        self.assertEqual(hashlib.sha256(selected[0][2]).hexdigest(), selected_id)

        new_ids, existing_ids, _ = save_documents(
            self.database_path,
            (("renamed-first.pdf", first_pdf),),
            "another-admin@example.com",
            is_admin=True,
            max_file_bytes=1_000_000,
        )
        self.assertEqual(new_ids, ())
        self.assertEqual(existing_ids, (selected_id,))
        self.assertEqual(len(list_documents(self.database_path)), 2)

    def test_nonexistent_selected_document_fails_closed(self) -> None:
        with self.assertRaises(LookupError):
            get_documents(self.database_path, ("missing-id",))


if __name__ == "__main__":
    unittest.main()
