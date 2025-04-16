import base64
import os

import requests
import random
from pathlib import Path


test_dir = Path().joinpath("documents")


def get_file_data():
    filename = random.choice(["demo.docx",
                              "file-sample_1MB.docx",
                              "hebrew_word_document.docx",
                              "sample-files.com-basic-text.docx",
                              "sample1.docx",
                              "sample3.docx",
                              "sample4.docx",])
    test_file = test_dir.joinpath(filename)
    content = test_file.read_bytes()
    b64_content = base64.b64encode(content)

    data = {
        "filename": "hebrew_word_document.docx",
        "file-content": b64_content.decode("utf-8"),
    }
    return data


while True:
    data = get_file_data()
    response = requests.post("http://127.0.0.1:5000/convert-to-pdf", json=data)
    if response.status_code == 200:
        json_data = response.json()
        pdf_content = json_data['pdfcontent']
        with open(Path().joinpath("documents", "converted_document.pdf"), "wb") as f:
            f.write(base64.b64decode(pdf_content))
    else:
        print(f"Server returned error {response.status_code}")


