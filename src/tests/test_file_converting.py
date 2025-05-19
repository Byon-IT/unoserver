import pytest
from pdfminer.high_level import extract_text
from rest_server import create_restful_app
import tempfile
from pathlib import Path
from io import BytesIO
import base64

TEST_FILES_DIR = Path(__file__).parent / "test_documents"

class TestFileConverting:
    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app = create_restful_app(self.tmpdir.name)
        self.client = self.app.test_client()

    def teardown_method(self):
        self.tmpdir.cleanup()

    def _post_file(self, filename):
        file_path = TEST_FILES_DIR / filename
        with open(file_path, "rb") as f:
            data = {'file': (BytesIO(f.read()), filename)}
            return self.client.post("/convert-to-pdf", data=data, content_type='multipart/form-data')

    def _convert_and_verify(self, filename, expected_strings=None):
        response = self._post_file(filename)
        assert response.status_code == 200, f"Failed to convert {filename}"
        assert 'pdfcontent' in response.json

        # Decode and save PDF
        pdf_content = base64.b64decode(response.json['pdfcontent'])
        output_path = TEST_FILES_DIR / "output" / f"{filename}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_content)

        # Extract text and validate expected strings
        text = extract_text(output_path)
        assert text.strip(), f"{filename} PDF text should not be empty"
        if expected_strings:
            for expected in expected_strings:
                assert expected in text, f"'{expected}' not found in {filename} PDF"


    def test_heartbeat(self):
        response = self.client.get("/heartbeat")
        assert response.status_code == 200

    def test_convert_valid_docx(self):
        self._convert_and_verify("hebrew_word_document.docx", ["תעודת זהות"[::-1]])

    def test_convert_valid_xlsx(self):
        self._convert_and_verify("simple.xlsx", ["Simple"])

    def test_filename_with_special_characters(self):
        response = self._post_file("weird name 😅.docx")
        assert response.status_code == 200
        assert 'pdfcontent' in response.json

    def test_repeat_same_file_conversion(self):
        for _ in range(3):
            response = self._post_file("hebrew_word_document.docx")
            assert response.status_code == 200
            assert 'pdfcontent' in response.json
    
    def test_empty_file_docx(self):
        response = self._post_file("empty.docx")
        assert response.status_code == 200

    def test_corrupt_docx(self):
        response = self._post_file("corrupt.docx")
        assert "Conversion failed" in response.json['error']
        assert response.status_code == 500

        response = self._post_file("demo.docx")
        assert response.status_code == 200
        assert 'pdfcontent' in response.json
