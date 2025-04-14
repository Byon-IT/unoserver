from __future__ import annotations

import sys

from exceptions import UnoServerException

sys.path.append("/usr/lib/python3/dist-packages")
sys.path.append("/usr/lib/libreoffice/program")

import argparse
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import platform
from pathlib import Path
from flask import Flask, request, jsonify
import base64

from unoserver import converter
from com.sun.star.uno import Exception as UnoException

API_VERSION = "3"
__version__ = "Byon"
logger = logging.getLogger("unoserver")


class UnoServer:
    def __init__(
        self,
        uno_interface="127.0.0.1",
        uno_port="2002",
        user_installation=None,
        conversion_timeout=None,
        stop_after=None,
        executable="libreoffice",
    ):
        self.uno_interface = uno_interface
        self.uno_port = uno_port
        self.user_installation = user_installation
        self.conversion_timeout = conversion_timeout
        self.stop_after = stop_after
        self.libreoffice_process = None
        self.intentional_exit = False
        self.converter_instance = None
        self._libreoffice_lock = threading.Lock()
        self.is_libreoffice_started = False
        self.is_server_stopped = True
        self.heartbeat_thread : threading.Thread = None
        self.executable = executable

        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        # Signal SIGHUP is available only in Unix systems
        if platform.system() != "Windows":
            signal.signal(signal.SIGHUP, self.signal_handler)


    def start(self, executable="libreoffice"):
        self.start_libreoffice(executable)
        self.start_unoconverter()
        self.is_libreoffice_started = True
        self.is_server_stopped = False
        self.heartbeat_thread = threading.Thread(target=self.heartbeat)
        self.heartbeat_thread.start()

    def signal_handler(self, signum, frame):
        self.intentional_exit = True
        logger.info("Sending signal to LibreOffice")
        try:
            if self.is_libreoffice_started:
                self.libreoffice_process.send_signal(signum)
        except ProcessLookupError as e:
            # 3 means the process is already dead
            if e.errno != 3:
                raise

    def start_libreoffice(self, executable="libreoffice"):
        logger.info(f"Starting unoserver {__version__}.")

        connection = (
            "socket,host=%s,port=%s,tcpNoDelay=1;urp;StarOffice.ComponentContext"
            % (self.uno_interface, self.uno_port)
        )

        # I think only --headless and --norestore are needed for
        # command line usage, but let's add everything to be safe.
        cmd = [
            executable,
            "--headless",
            "--invisible",
            "--nocrashreport",
            "--nodefault",
            "--nologo",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation={self.user_installation}",
            f"--accept={connection}",
        ]

        logger.info("Command: " + " ".join(cmd))
        self.libreoffice_process = subprocess.Popen(cmd)

        time.sleep(5)

        return self.libreoffice_process

    def start_unoconverter(self):
        logger.info(f"Starting UnoConverter instance.")
        attempts = 20
        while attempts > 0:
            try:
                self.converter_instance = converter.UnoConverter(
                    interface=self.uno_interface, port=self.uno_port
                )
                break
            except UnoException as e:
                # A connection refused just means it hasn't started yet:
                if "Connection refused" in str(e):
                    logger.debug("Libreoffice is not yet started")
                    time.sleep(2)
                    attempts -= 1
                    continue
                # This is a different error
                logger.warning("Error when starting UnoConverter, retrying: %s", e)
                # These kinds of errors can be retried fewer times
                attempts -= 4
                time.sleep(5)
                continue
        else:
            # We ran out of attempts
            logger.critical("Could not start Libreoffice, exiting.")
            # Make sure it's really dead
            self.libreoffice_process.terminate()
            raise UnoServerException("Could not start Libreoffice, exiting.")

        logger.info("UnoConverter started")

    def kill_libreoffice(self):
        if self.libreoffice_process is not None:
            logger.info("Sending SIGTERM to libreoffice")
            self.libreoffice_process.terminate()
            try:
                self.libreoffice_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.info("Sending SIGKILL to libreoffice")
                self.libreoffice_process.kill()
            self.is_libreoffice_started = False

    def test_convert(self, document_name):
        if not self.is_libreoffice_started:
            self.start()

        try:
            with self._libreoffice_lock:
                with open(f"/opt/project/tests/documents/{document_name}", "rb") as fo:
                    data = fo.read()
                if os.path.exists("/opt/project/tests/documents/out.pdf"):
                    os.unlink("/opt/project/tests/documents/out.pdf")
                self.converter_instance.convert(indata=data, outpath="/opt/project/tests/documents/out.pdf")
        except:
            logger.exception("Conversion failed")

    def convert_to_pdf(self, filename: str, file_content: bytes) -> bytes:
        if not self.is_libreoffice_started:
            self.start()

        try:
            with self._libreoffice_lock:
                return self.converter_instance.convert(indata=file_content, convert_to="pdf")
        except:
            logger.exception("Conversion failed")

    def heartbeat(self):
        while not self.is_server_stopped:
            is_acquired = self._libreoffice_lock.acquire(timeout=self.conversion_timeout)
            if not is_acquired:
                logger.info("Heartbeat failed, killing libreoffice")
                self.kill_libreoffice()
                self.is_server_stopped = True
            else:
                self._libreoffice_lock.release()
                time.sleep(5)

    def serve(self):
        self.heartbeat()



def main():
    logging.basicConfig()
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser("unoserver")

    parser.add_argument(
        "--interface",
        default="127.0.0.1",
        help="The interface used by the XMLRPC server",
    )
    parser.add_argument(
        "--uno-interface",
        default="127.0.0.1",
        help="The interface used by the Libreoffice UNO server",
    )
    parser.add_argument(
        "--port", default="2003", help="The port used by the XMLRPC server"
    )
    parser.add_argument(
        "--uno-port", default="2002", help="The port used by the Libreoffice UNO server"
    )
    parser.add_argument("--daemon", action="store_true", help="Deamonize the server")
    parser.add_argument(
        "--conversion-timeout",
        type=int,
        help="Terminate Libreoffice and exit if a conversion does not complete in the "
        "given time (in seconds).",
        default=30
    )
    args = parser.parse_args()

    logger.setLevel(logging.DEBUG)

    with tempfile.TemporaryDirectory() as tmpuserdir:
        user_installation = Path(tmpuserdir).as_uri()

        for name in ("soffice", "libreoffice", "ooffice"):
            if (executable := shutil.which(name)) is not None:
                break

        server = UnoServer(
            args.uno_interface,
            args.uno_port,
            user_installation,
            args.conversion_timeout,
            executable=executable
        )

        app = Flask(__name__)

        @app.route('/convert-to-pdf', methods=['POST'])
        def convert_to_pdf_endpoint():
            data = request.get_json()

            if not data or 'filename' not in data or 'file-content' not in data:
                return jsonify({'error': 'Missing filename or file-content'}), 400

            filename = data['filename']
            try:
                file_bytes = base64.b64decode(data['file-content'])
            except Exception as e:
                return jsonify({'error': 'Invalid base64 content'}), 400

            pdf_bytes = server.convert_to_pdf(filename, file_bytes)
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            return jsonify({
                'pdfcontent': pdf_base64
            })

        app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
