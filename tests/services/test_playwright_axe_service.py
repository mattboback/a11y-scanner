import tempfile
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService


@pytest.fixture
def http_service():
    """Fixture to create and automatically clean up an HttpService instance."""
    service = HttpService()
    yield service
    service.stop()


def test_scan_url_captures_screenshot_of_violation(
    http_service: HttpService, tmp_path: Path
):
    """
    Verify that when a violation is found, a screenshot is taken,
    and the path to it is added to the violation dictionary.
    """
    # 1. SETUP
    scan_dir = tmp_path / "scan"
    results_dir = tmp_path / "results"
    scan_dir.mkdir()
    results_dir.mkdir()

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <main>
            <h1>Missing Alt Text</h1>
            <img src="test.jpg">
        </main>
    </body>
    </html>
    """
    test_html_file = scan_dir / "index.html"
    test_html_file.write_text(html_content)

    http_service.start(directory=scan_dir)
    url_to_scan = f"{http_service.base_url}/index.html"
    report_path = results_dir / "report.json"

    # 2. ACTION
    service = PlaywrightAxeService()
    violations = service.scan_url(url_to_scan, report_path)

    # 3. VERIFICATION
    # Find the specific violation we are interested in.
    image_alt_violation = next((v for v in violations if v["id"] == "image-alt"), None)
    assert image_alt_violation is not None, "The 'image-alt' violation was not found."

    # **THE KEY CHECK**: Assert that a screenshot path has been added
    assert "screenshot_path" in image_alt_violation
    screenshot_path_str = image_alt_violation["screenshot_path"]
    assert screenshot_path_str is not None

    # Assert that the screenshot file actually exists
    screenshot_path = Path(screenshot_path_str)
    assert screenshot_path.exists()
    assert screenshot_path.is_file()

    # Assert the screenshot is saved in the correct directory
    assert results_dir in screenshot_path.parents
