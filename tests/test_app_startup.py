import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class AppStartupTests(unittest.TestCase):
    def test_unconfigured_oidc_fails_closed_without_exposing_library_or_upload(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with TemporaryDirectory() as temporary_directory:
            library_path = Path(temporary_directory) / "library.sqlite3"
            with patch.dict(
                "os.environ",
                {"PDF_CHAT_LIBRARY_DB": str(library_path)},
            ):
                app = AppTest.from_file(str(app_path)).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "PDF chat sign-in is not configured")
            self.assertEqual(len(app.file_uploader), 0)
            self.assertEqual(len(app.chat_input), 0)
            self.assertFalse(library_path.exists())
            self.assertTrue(
                any("OpenID Connect provider" in element.value for element in app.error)
            )


if __name__ == "__main__":
    unittest.main()
