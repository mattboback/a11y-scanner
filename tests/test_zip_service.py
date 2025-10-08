import zipfile
from pathlib import Path

import pytest

from scanner.services.zip_service import ZipService


def create_test_zip(zip_path: Path, files: dict[str, str]):
    """
    Creates a zip file at `zip_path` with a dictionary of filename -> contents.
    """
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_name, content in files.items():
            zf.writestr(file_name, content)


def test_zip_extraction(tmp_path: Path):
    # Setup: directories for unzip input and scan output
    unzip_dir = tmp_path / "unzip"
    scan_dir = tmp_path / "scan"
    unzip_dir.mkdir()
    scan_dir.mkdir()

    # Create a zip file in the unzip_dir
    zip_file = unzip_dir / "test.zip"
    create_test_zip(
        zip_file,
        {
            "index.html": "<html><body>Hello</body></html>",
            "about.html": "<html><body>About</body></html>",
        },
    )

    # Run ZipService
    service = ZipService(unzip_dir=unzip_dir, scan_dir=scan_dir)
    service.run()

    # Assert: files are extracted into scan_dir
    extracted_files = list(scan_dir.glob("*.html"))
    extracted_names = {f.name for f in extracted_files}

    assert "index.html" in extracted_names
    assert "about.html" in extracted_names
    assert len(extracted_files) == 2


def test_missing_zip_file(tmp_path: Path):
    unzip_dir = tmp_path / "unzip"
    scan_dir = tmp_path / "scan"
    unzip_dir.mkdir()
    scan_dir.mkdir()

    service = ZipService(unzip_dir=unzip_dir, scan_dir=scan_dir)

    with pytest.raises(FileNotFoundError):
        service.run()
