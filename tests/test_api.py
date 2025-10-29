import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from scanner.web.server import app


@pytest.fixture
def client():
    """Fixture to provide a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def mock_container_env(monkeypatch):
    """Mock the container environment variable."""
    monkeypatch.setenv("A11Y_SCANNER_IN_CONTAINER", "1")


@pytest.fixture
def sample_zip():
    """Create a sample ZIP file in memory."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", "<html><body><h1>Test</h1></body></html>")
        zf.writestr("about.html", "<html><body><h1>About</h1></body></html>")
    buffer.seek(0)
    return buffer


def test_healthz(client):
    """Test the health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index(client):
    """Test the index endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "a11y-scanner API" in response.text
    assert "/api/scan/zip" in response.text
    assert "/api/scan/url" in response.text


def test_scan_zip_requires_container(client):
    """Test that scan_zip endpoint requires container environment."""
    response = client.post(
        "/api/scan/zip",
        files={"file": ("test.zip", b"dummy content", "application/zip")},
    )
    assert response.status_code == 400
    assert "Must run inside container" in response.json()["detail"]


def test_scan_zip_invalid_mime_type(client, mock_container_env, sample_zip):
    """Test that scan_zip rejects non-ZIP MIME types."""
    with patch("scanner.web.server.Pipeline"):
        response = client.post(
            "/api/scan/zip",
            files={"file": ("test.txt", sample_zip.getvalue(), "text/plain")},
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]


def test_scan_zip_invalid_extension(client, mock_container_env, sample_zip):
    """Test that scan_zip rejects files without .zip extension."""
    with patch("scanner.web.server.Pipeline"):
        response = client.post(
            "/api/scan/zip",
            files={"file": ("test.txt", sample_zip.getvalue(), "application/zip")},
        )
        assert response.status_code == 400
        assert ".zip extension" in response.json()["detail"]


def test_scan_zip_empty_file(client, mock_container_env):
    """Test that scan_zip rejects empty files."""
    with patch("scanner.web.server.Pipeline"):
        response = client.post(
            "/api/scan/zip",
            files={"file": ("test.zip", b"", "application/zip")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"]


def test_scan_zip_too_large(client, mock_container_env):
    """Test that scan_zip rejects files exceeding size limit."""
    # Create a file larger than MAX_UPLOAD_SIZE (100 MB)
    large_content = b"x" * (101 * 1024 * 1024)
    with patch("scanner.web.server.Pipeline"):
        response = client.post(
            "/api/scan/zip",
            files={"file": ("test.zip", large_content, "application/zip")},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"]


def test_scan_zip_success(client, mock_container_env, sample_zip, tmp_path):
    """Test successful ZIP scan."""
    with patch("scanner.web.server.settings") as mock_settings:
        # Configure mock settings
        mock_settings.unzip_dir = tmp_path / "unzip"
        mock_settings.scan_dir = tmp_path / "scan"
        mock_settings.results_dir = tmp_path / "results"
        mock_settings.data_dir = tmp_path / "data"
        for d in [
            mock_settings.unzip_dir,
            mock_settings.scan_dir,
            mock_settings.results_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        with patch("scanner.web.server.Pipeline") as mock_pipeline_class:
            # Mock pipeline run
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = [{"id": "image-alt", "impact": "critical"}]
            mock_pipeline_class.return_value = mock_pipeline

            with patch("scanner.web.server.build_report"):
                response = client.post(
                    "/api/scan/zip",
                    files={
                        "file": ("test.zip", sample_zip.getvalue(), "application/zip")
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "violations" in data
                assert "report_url" in data
                assert data["report_url"] == "/reports/latest.html"


def test_scan_url_requires_container(client):
    """Test that scan_url endpoint requires container environment."""
    response = client.post("/api/scan/url", json={"urls": ["https://example.com"]})
    assert response.status_code == 400
    assert "Must run inside container" in response.json()["detail"]


def test_scan_url_invalid_url(client, mock_container_env):
    """Test that scan_url rejects invalid URLs."""
    with patch("scanner.web.server.PlaywrightAxeService"):
        response = client.post(
            "/api/scan/url", json={"urls": ["not-a-url", "ftp://example.com"]}
        )
        # Pydantic validation returns 422 for invalid URL format
        assert response.status_code == 422
        assert "detail" in response.json()


def test_scan_url_success(client, mock_container_env, tmp_path):
    """Test successful URL scan."""
    # Mock the entire settings module reference
    with (
        patch("scanner.web.server.settings") as mock_settings,
        patch("scanner.web.server._clean_dir"),
    ):
        mock_settings.results_dir = tmp_path / "results"
        mock_settings.data_dir = tmp_path / "data"
        mock_settings.results_dir.mkdir(parents=True, exist_ok=True)

        with patch("scanner.web.server.PlaywrightAxeService") as mock_axe_class:
            # Mock axe service
            mock_axe = MagicMock()
            mock_axe.scan_url.return_value = [
                {"id": "color-contrast", "impact": "serious"}
            ]
            mock_axe_class.return_value = mock_axe

            with (
                patch("scanner.web.server.build_report"),
                patch("scanner.web.server.reports_dir", tmp_path / "reports"),
            ):
                (tmp_path / "reports").mkdir(parents=True, exist_ok=True)

                response = client.post(
                    "/api/scan/url",
                    json={"urls": ["https://example.com", "https://test.com"]},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "violations" in data
                assert "urls_scanned" in data
                assert data["urls_scanned"] == 2
                assert "scanned_urls" in data
                assert len(data["scanned_urls"]) == 2


def test_scan_url_partial_failure(client, mock_container_env, tmp_path):
    """Test URL scan with some URLs failing."""
    with (
        patch("scanner.web.server.settings") as mock_settings,
        patch("scanner.web.server._clean_dir"),
    ):
        mock_settings.results_dir = tmp_path / "results"
        mock_settings.data_dir = tmp_path / "data"
        mock_settings.results_dir.mkdir(parents=True, exist_ok=True)

        with patch("scanner.web.server.PlaywrightAxeService") as mock_axe_class:
            # Mock axe service - first succeeds, second fails
            mock_axe = MagicMock()
            mock_axe.scan_url.side_effect = [
                [{"id": "color-contrast", "impact": "serious"}],
                Exception("Network error"),
            ]
            mock_axe_class.return_value = mock_axe

            with (
                patch("scanner.web.server.build_report"),
                patch("scanner.web.server.reports_dir", tmp_path / "reports"),
            ):
                (tmp_path / "reports").mkdir(parents=True, exist_ok=True)

                response = client.post(
                    "/api/scan/url",
                    json={"urls": ["https://example.com", "https://bad.com"]},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                # Should have scanned both URLs (one succeeded, one failed)
                assert data["urls_scanned"] == 2
                assert len(data["scanned_urls"]) == 2
                # Second URL should show failure
                assert "bad.com" in data["scanned_urls"][1]
