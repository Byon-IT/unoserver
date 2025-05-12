from __future__ import annotations

import sys


sys.path.append("/usr/lib/python3/dist-packages")
sys.path.append("/usr/lib/libreoffice/program")

import logging
import os
import shutil
import psutil
import signal
import subprocess
import threading
import time
import platform


from unoserver import converter
from unoserver.exceptions import UnoServerException

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
        memory_usage_ratio_limit=6.0,
    ):
        self.uno_interface = uno_interface
        self.uno_port = uno_port
        self.user_installation = user_installation
        self.conversion_timeout = conversion_timeout
        self.libreoffice_process = None
        self.intentional_exit = False
        self.converter_instance = None
        self._start_lock = threading.Lock()
        self._libreoffice_lock = threading.Lock()
        self._libreoffice_initial_ram_usage = 0
        self.is_libreoffice_started = False
        self.is_server_stopped = True
        self.heartbeat_thread: threading.Thread = None

        self.executable = None
        for name in ("soffice", "libreoffice", "ooffice"):
            if (executable := shutil.which(name)) is not None:
                break

        if not executable:
            raise UnoServerException("Could not find libreoffice executable")
        else:
            self.executable = executable

        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        # Signal SIGHUP is available only in Unix systems
        if platform.system() != "Windows":
            signal.signal(signal.SIGHUP, self.signal_handler)

        # The memory usage ratio limit makes sure that if the libreoffice process exceeds
        # its initial memory usage by that multiplier it will be killed.
        if memory_usage_ratio_limit <= 1.0:
            raise ValueError("The memory usage ratio limit cannot be 1.0 or less")
        self.memory_usage_ratio_limit = memory_usage_ratio_limit

    def start(self, executable="libreoffice"):
        with self._start_lock:
            if not self.is_server_stopped:
                logger.debug("The UnoServer is already started")
                return

            self.start_libreoffice(executable)
            self.start_unoconverter()
            self.is_server_stopped = False

            self._libreoffice_initial_ram_usage = self.get_libreoffice_ram_usage()
            logger.info(f"Initial Libreoffice RAM usage: {int(self._libreoffice_initial_ram_usage / (1024**2))}mb")

            if not self.heartbeat_thread or not self.heartbeat_thread.is_alive():
                self.heartbeat_thread = threading.Thread(target=self.heartbeat)
                self.heartbeat_thread.start()

    def signal_handler(self, signum, frame):
        self.intentional_exit = True
        logger.info("Sending signal to LibreOffice")
        try:
            if self.is_libreoffice_started:
                self.libreoffice_process.send_signal(signum)
                self.is_libreoffice_started = False
                self.is_server_stopped = True
        except ProcessLookupError as e:
            # 3 means the process is already dead
            if e.errno != 3:
                raise
        exit()

    def start_libreoffice(self, executable="libreoffice"):
        if self.is_libreoffice_started:
            logger.debug("Libreoffice is already started")
            return

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
        self.is_libreoffice_started = True

        return self.libreoffice_process

    def get_libreoffice_ram_usage(self):
        if not self.is_libreoffice_started:
            raise RuntimeError("Cannot check memory of unstarted process")
        libreoffice_pid = self.libreoffice_process.pid

        parent = psutil.Process(libreoffice_pid)
        children = parent.children(recursive=True)

        total_rss = parent.memory_info().rss  # bytes
        for child in children:
            try:
                total_rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                continue  # Child exited during iteration?

        return total_rss

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

    def convert_to_pdf(self, file_content: bytes) -> bytes:
        if not self.is_libreoffice_started:
            self.start()

        try:
            with self._libreoffice_lock:
                return self.converter_instance.convert(indata=file_content, convert_to="pdf")
        except:
            logger.exception("Conversion failed")

    def heartbeat(self):
        logger.debug(f"Heartbeat thread #{threading.get_ident()} started")
        while not self.is_server_stopped:
            is_acquired = self._libreoffice_lock.acquire(timeout=self.conversion_timeout)
            if not is_acquired:
                logger.info("Heartbeat failed, killing libreoffice")
                self.kill_libreoffice()
                self.is_server_stopped = True
            else:
                memory_usage_threshold = self._libreoffice_initial_ram_usage * self.memory_usage_ratio_limit
                if self.get_libreoffice_ram_usage() > memory_usage_threshold:
                    memory_usage_threshold_mb = int(memory_usage_threshold / (1024 ** 2))
                    logger.info(f"Libreoffice uses more than {memory_usage_threshold_mb}mb of RAM, killing it.")
                    self.kill_libreoffice()
                    self.is_server_stopped = True

                self._libreoffice_lock.release()
                time.sleep(5)
