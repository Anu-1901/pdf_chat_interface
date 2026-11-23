import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from streamlit.testing.v1 import AppTest


def make_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


class AppStartupTests(unittest.TestCase):
    def test_app_starts_with_upload_and_disabled_chat(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Chat with PDFs")
        self.assertEqual(len(app.file_uploader), 1)
        self.assertTrue(app.chat_input[0].proto.disabled)

    def test_new_upload_clears_history_and_reset_clears_document(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch.dict(os.environ, {"FARM_API_KEY": ""}):
            app = AppTest.from_file(str(app_path)).run(timeout=30)
            app.session_state["messages"] = [
                {"role": "user", "content": "This belongs to the old document."}
            ]

            app.file_uploader[0].upload(
                "scan.pdf",
                make_pdf("Short scan"),
            ).run(timeout=30)
            self.assertFalse(app.exception)
            first_document_id = app.session_state["document_id"]
            self.assertEqual(app.session_state["messages"], [])
            self.assertEqual(app.session_state["status"], "error")
            self.assertIn("OCR is not configured", app.session_state["error_message"])

            app.file_uploader[0].set_value(
                ("scan.pdf", make_pdf("A different short scan."), "application/pdf")
            ).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertNotEqual(app.session_state["document_id"], first_document_id)
            self.assertEqual(app.session_state["messages"], [])

            app.button[0].click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state["document_id"])
            self.assertEqual(app.session_state["status"], "empty")
            self.assertEqual(app.session_state["messages"], [])

    def test_multiple_uploads_are_processed_together_and_reset_as_a_set(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch.dict(os.environ, {"FARM_API_KEY": ""}):
            app = AppTest.from_file(str(app_path)).run(timeout=30)
            uploads = [
                (
                    "first.pdf",
                    make_pdf(
                        "First PDF contains enough native text to check its page reference "
                        "and verify that this file is preserved in the selected document set."
                    ),
                    "application/pdf",
                ),
                (
                    "second.pdf",
                    make_pdf(
                        "Second PDF contains separate native text and provenance so the "
                        "application can identify its exact source page independently."
                    ),
                    "application/pdf",
                ),
            ]
            app.file_uploader[0].set_value(uploads).run(timeout=30)

            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["status"], "error")
            self.assertEqual(
                set(app.session_state["document_names"]),
                {"first.pdf", "second.pdf"},
            )
            self.assertIn("FARM_API_KEY", app.session_state["error_message"])
            self.assertIsNotNone(app.session_state["document_id"])

            app.button[0].click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state["document_id"])
            self.assertEqual(app.session_state["document_names"], ())
            self.assertEqual(app.session_state["status"], "empty")


if __name__ == "__main__":
    unittest.main()
