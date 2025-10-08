from pathlib import Path

import pytest

from scanner.core.settings import Settings


def test_settings_default_uses_relative_paths():
    """
    Verify that by default, Settings uses relative paths from the current directory.
    This is important for portability and interaction with CLI tools.
    """
    settings = Settings()

    # The base path should be a relative representation of the current directory.
    assert settings.base_path == Path(".")

    # All other paths should be built relative to that.
    assert settings.data_dir == Path("data")
    assert settings.scan_dir == Path("data/scan")
    assert settings.unzip_dir == Path("data/unzip")
    assert settings.results_dir == Path("data/results")
    assert settings.port == 8000


def test_settings_with_custom_base_path_uses_absolute_path(tmp_path: Path):
    """
    Verify that when a root_path is provided (common in tests), it is
    resolved to an absolute path.
    """
    settings = Settings(root_path=tmp_path)

    assert settings.base_path == tmp_path.resolve()
    assert settings.data_dir == tmp_path.resolve() / "data"
    assert settings.scan_dir == tmp_path.resolve() / "data" / "scan"
    assert settings.unzip_dir == tmp_path.resolve() / "data" / "unzip"
    assert settings.results_dir == tmp_path.resolve() / "data" / "results"
