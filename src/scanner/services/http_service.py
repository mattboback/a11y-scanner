# src/scanner/services/http_service.py
import http.server
import logging
import socket
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class Handler(http.server.SimpleHTTPRequestHandler):
    """A request handler that serves files from a specific directory."""

    def __init__(self, *args, directory: Path, **kwargs) -> None:
        # The directory argument is mandatory for our use case
        super().__init__(*args, directory=str(directory), **kwargs)


class HttpService:
    """A service to manage a simple, local HTTP server in a background thread."""

    def __init__(self):
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.host = "localhost"
        self.port = 0  # Port 0 means the OS will pick an available port
        self.base_url = ""

    def start(self, directory: Path):
        """Starts the HTTP server in a background thread."""
        if self._server:
            logger.warning("Server is already running. Ignoring start request.")
            return

        # Use a context manager to find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            self.port = s.getsockname()[1]  # Get the port assigned by the OS
            logger.info("Found available port: %d", self.port)

        self.base_url = f"http://{self.host}:{self.port}"

        # The handler needs the directory to serve from. functools.partial is
        # a clean way to pass the 'directory' argument to the Handler's constructor.
        def handler_factory(*args, **kwargs):
            return Handler(*args, directory=directory, **kwargs)

        self._server = http.server.ThreadingHTTPServer(
            (self.host, self.port), handler_factory
        )

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(
            "HTTP server started at %s, serving files from %s",
            self.base_url,
            directory,
        )

    def stop(self):
        """Stops the HTTP server and waits for the thread to join."""
        if self._server and self._thread:
            logger.info("Shutting down HTTP server...")
            self._server.shutdown()
            self._thread.join(timeout=5)  # Wait for the thread to finish
            if self._thread.is_alive():
                logger.error("Server thread did not shut down cleanly.")
            self._server.server_close()
            logger.info("HTTP server shut down.")
        self._server = None
        self._thread = None
        self.base_url = ""
