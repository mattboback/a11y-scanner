import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scanner.core.settings import Settings
from scanner.pipeline import Pipeline


def create_test_zip(zip_path: Path, files: dict[str, str]):
    """Helper to create a zip file for testing."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_name, content in files.items():
            zf.writestr(file_name, content)


@pytest.fixture
def mock_services() -> dict:
    """Provides a dictionary of mocked services for injection."""
    return {
        "zip_service": MagicMock(),
        "html_service": MagicMock(),
        "http_service": MagicMock(),
        "axe_service": MagicMock(),
    }


def test_pipeline_happy_path(tmp_path: Path, mock_services: dict):
    """
    Tests the full pipeline orchestration on a happy path using mocked services.
    """
    # 1. Setup
    # Configure the return values of our mocks
    mock_services["html_service"].discover_html_files.return_value = [
        {"relative": Path("index.html")}
    ]
    mock_services["http_service"].base_url = "http://localhost:8000"

    # --- THE FIX IS HERE ---
    # We now mock the return value of `scan_url` because that's what the pipeline
    # uses to get the results directly.
    mock_violations = [{"id": "image-alt", "impact": "critical"}]
    mock_services["axe_service"].scan_url.return_value = mock_violations

    # Create fake directory structure
    settings = Settings(root_path=tmp_path)
    settings.scan_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)

    # 2. Action
    # Instantiate the pipeline with our temporary settings and MOCKED services
    pipeline = Pipeline(settings=settings, **mock_services)
    final_results = pipeline.run()

    # 3. Verification
    # Verify that the services were called as expected
    mock_services["zip_service"].run.assert_called_once()
    mock_services["html_service"].discover_html_files.assert_called_once()
    mock_services["http_service"].start.assert_called_once_with(
        directory=settings.scan_dir
    )

    # Verify AxeService.scan_url was called correctly
    mock_services["axe_service"].scan_url.assert_called_once()
    call_args, _ = mock_services["axe_service"].scan_url.call_args
    scanned_url = call_args[0]
    report_path = call_args[1]
    assert scanned_url == "http://localhost:8000/index.html"
    assert report_path == settings.results_dir / "index.html.json"

    # Verify the final result is what the mocked scan_url returned,
    # but with the added context from the pipeline.
    expected_result = [
        {
            "id": "image-alt",
            "impact": "critical",
            "scanned_url": "http://localhost:8000/index.html",
            "source_file": "index.html",
        }
    ]
    assert final_results == expected_result

    # Verify the HTTP server was stopped
    mock_services["http_service"].stop.assert_called_once()


def test_pipeline_no_html_files_found(tmp_path: Path, mock_services: dict):
    """
    Verify the pipeline exits gracefully if no HTML files are discovered.
    """
    # 1. Setup
    mock_services["html_service"].discover_html_files.return_value = []
    settings = Settings(root_path=tmp_path)

    # 2. Action
    pipeline = Pipeline(settings=settings, **mock_services)
    result = pipeline.run()

    # 3. Verification
    assert result == []
    mock_services["zip_service"].run.assert_called_once()
    mock_services["http_service"].start.assert_not_called()
    mock_services["axe_service"].scan_url.assert_not_called()
    mock_services[
        "http_service"
    ].stop.assert_called_once()  # Should still be called in finally
