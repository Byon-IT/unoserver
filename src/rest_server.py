import logging
import os
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify
import base64

from unoserver.libreoffice_uno_server import UnoServer

logger = logging.getLogger("unoserver")

logging.basicConfig()
logger.setLevel(logging.DEBUG)

LISTEN_INTERFACE = os.environ.get('LISTEN_INTERFACE', '0.0.0.0')
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', '5000'))
CONVERSION_TIMEOUT = int(os.environ.get('CONVERSION_TIMEOUT', '30'))
MEMORY_USAGE_RATIO_LIMIT = float(os.environ.get('MEMORY_USAGE_RATIO_LIMIT', '8.0'))


def main():
    with tempfile.TemporaryDirectory() as tmpuserdir:
        user_installation = Path(tmpuserdir).as_uri()

        libreoffice_server = UnoServer(
            user_installation=user_installation,
            conversion_timeout=CONVERSION_TIMEOUT,
            memory_usage_ratio_limit=MEMORY_USAGE_RATIO_LIMIT
        )

        libreoffice_server.start()

        app = Flask(__name__)

        @app.route('/convert-to-pdf', methods=['POST'])
        def convert_to_pdf_endpoint():
            uploaded_file = request.files.get('file')

            if not uploaded_file:
                return jsonify({'error': 'Missing file'}), 400

            try:
                file_bytes = uploaded_file.read()
                pdf_bytes = libreoffice_server.convert_to_pdf(file_bytes)
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            except Exception as e:
                return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

            return jsonify({'pdfcontent': pdf_base64})

        @app.route('/heartbeat', methods=['GET'])
        def heartbeat():
            if libreoffice_server.is_server_stopped:
                return jsonify({'success': False, 'details': 'Server is stopped'}), 500
            else:
                return jsonify({'success': True, 'details': 'Server is running'}), 200

        app.run(host=LISTEN_INTERFACE, port=LISTEN_PORT, debug=True, threaded=False, use_reloader=False)


if __name__ == '__main__':
    main()