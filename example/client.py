

import base64
import requests
from pathlib import Path
from io import BytesIO

test_dir = Path("documents")


def get_file_object():
    # filename = random.choice(["demo.docx",
    #                           "file-sample_1MB.docx",
    #                           "hebrew_word_document.docx",
    #                           "sample-files.com-basic-text.docx",
    #                           "sample1.docx",
    #                           "sample3.docx",
    #                           "sample4.docx",])
    filename = "hebrew_word_document.docx"
    test_file = test_dir / filename
    file_bytes = test_file.read_bytes()
    return BytesIO(file_bytes), filename


while True:
    file_obj, filename = get_file_object()

    response = requests.post(
        "http://127.0.0.1:5000/convert-to-pdf",
        files={'file': (filename, file_obj)},
    )

    if response.status_code == 200:
        json_data = response.json()
        pdf_content = json_data['pdfcontent']
        result_path = test_dir / "converted_document.pdf"
        with open(result_path, "wb") as f:
            f.write(base64.b64decode(pdf_content))
        print(f"Document converted and saved to {result_path}")
    else:
        print(f"Server returned error {response.status_code}")