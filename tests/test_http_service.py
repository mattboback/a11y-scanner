import time
from pathlib import Path

import pytest
import requests

from scanner.services.http_service import HttpService


@pytest.fixture
def http_service():
    """Fixture to create and automatically clean up an HttpService instance."""
    service = HttpService()
    yield service
    # Teardown: ensure the server is stopped after the test runs
    service.stop()


def test_http_server_serves_files(http_service: HttpService, tmp_path: Path):
    """
    Verify that the HttpService can start, serve a file, and stop.
    """
    content = "<html><body>Test Page</body></html>"
    test_file = tmp_path / "index.html"
    test_file.write_text(content)

    http_service.start(directory=tmp_path)
    assert http_service.base_url, "Server should have a base_url after starting"
    time.sleep(0.1)  # Give the server a moment to start up in the background

    url_to_test = f"{http_service.base_url}/index.html"

    try:
        response = requests.get(url_to_test, timeout=5)
        response.raise_for_status()

        assert response.text == content
        assert response.headers["Content-Type"] == "text/html"

    except requests.RequestException as e:
        pytest.fail(f"HTTP request failed: {e}")

    http_service.stop()

    with pytest.raises(requests.ConnectionError):
        requests.get(url_to_test, timeout=1)
