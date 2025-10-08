from pathlib import Path

import pytest

from scanner.services.html_discovery_service import HtmlDiscoveryService


@pytest.mark.parametrize(
    "test_dir, expected_rel_paths",
    [
        ("1", {"index.html", "about.html"}),
        (
            "2",
            {
                "hehe.htm",
                "lol.html",
                "test.html",
                "nest/ll.html",
                "nest/ll.htm",
                "nest/tl.htm",
            },
        ),
        ("3", {"mor_test.html", "test.html"}),
    ],
)
def test_discover_html_files_absolute_and_relative(test_dir, expected_rel_paths):
    base_dir = Path(__file__).parent / "assets" / "html_sets" / test_dir
    assert base_dir.exists(), f"Test directory does not exist: {base_dir}"

    service = HtmlDiscoveryService(scan_dir=base_dir)
    discovered = service.discover_html_files()

    found_rel = {str(entry["relative"]) for entry in discovered}
    assert found_rel == expected_rel_paths, f"Relative paths mismatch in {test_dir}"

    for entry in discovered:
        rel = entry["relative"]
        abs_path = entry["absolute"]

        # Assert absolute path is correct
        expected_abs = base_dir / rel
        assert abs_path == expected_abs.resolve(), f"Absolute path mismatch for {rel}"
        assert abs_path.exists(), f"Absolute path doesn't exist: {abs_path}"
        assert abs_path.is_file(), f"Path is not a file: {abs_path}"
