import base64
import requests
from pathlib import Path


test_file = Path().joinpath("documents", "hebrew_word_document.docx")
content = test_file.read_bytes()
b64_content = base64.b64encode(content)

data = {
    "filename": "hebrew_word_document.docx",
    "file-content": b64_content.decode("utf-8"),
}


response = requests.post("http://127.0.0.1:5000/convert-to-pdf", json=data)
if response.status_code == 200:
    json_data = response.json()
    pdf_content = json_data['pdfcontent']
    with open(Path().joinpath("documents", "converted_document.pdf"), "wb") as f:
        f.write(base64.b64decode(pdf_content))
else:
    print(f"Server returned error {response.status_code}")


