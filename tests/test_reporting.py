import json
import tempfile
from pathlib import Path

import pytest

from scanner.reporting.jinja_report import (
    Occurrence,
    ReportModel,
    RuleGroup,
    build_report,
    validate_report_json,
)


@pytest.fixture
def sample_report_data():
    """Sample report data for testing"""

    return {
        "scanned_url": "http://localhost:8000/index.html",
        "source_file": "index.html",
        "violations": [
            {
                "id": "image-alt",
                "impact": "critical",
                "description": "Images must have alternate text",
                "help": "Provide appropriate alt text for images",
                "helpUrl": "https://example.com/help",
                "nodes": [
                    {"target": ["img[src='logo.png']"], "html": "<img src='logo.png'>"}
                ],
                "screenshot_path": "screenshot1.png",
            }
        ],
    }


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        results_dir = temp_path / "results"

        reports_dir = temp_path / "reports"

        results_dir.mkdir()

        reports_dir.mkdir()

        yield results_dir, reports_dir


def test_occurrence_post_init():
    """Test that Occurrence.__post_init__ correctly extracts filename"""

    # Test with string path

    occ = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path="/path/to/screenshot.png",
    )

    assert occ.screenshot_filename == "screenshot.png"

    # Test with None

    occ2 = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path=None,
    )

    assert occ2.screenshot_filename is None

    # Test with Path object

    occ3 = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path=Path("/path/to/another.png"),
    )

    assert occ3.screenshot_filename == "another.png"


def test_rule_group_impact_class():
    """Test RuleGroup.impact_class property"""

    # Test with different impact levels

    assert RuleGroup(id="test", impact="critical").impact_class == "impact-critical"

    assert RuleGroup(id="test", impact="serious").impact_class == "impact-serious"

    assert RuleGroup(id="test", impact="moderate").impact_class == "impact-moderate"

    assert RuleGroup(id="test", impact="minor").impact_class == "impact-minor"

    assert RuleGroup(id="test", impact="unknown").impact_class == "impact-unknown"

    assert RuleGroup(id="test", impact=None).impact_class == "impact-unknown"


def test_report_model_validation():
    """Test ReportModel.validate() method"""

    # Valid model

    model = ReportModel(
        title="Test",
        generated_at="2023-01-01T00:00:00Z",
        pages_scanned=1,
        total_violations=1,
        by_rule=[],
        raw_files=[],
    )

    assert model.validate() is True

    # Invalid: negative pages

    model.pages_scanned = -1

    assert model.validate() is False

    # Invalid: negative violations

    model.pages_scanned = 1

    model.total_violations = -1

    assert model.validate() is False

    # Edge case: zero violations with rule groups

    model.total_violations = 0

    model.by_rule = [RuleGroup(id="test", impact="critical")]

    assert model.validate() is False  # Should be False if rules exist but 0 violations

    # Valid: zero violations with no rule groups

    model.by_rule = []

    assert model.validate() is True


def test_validate_report_json(temp_dirs, sample_report_data):
    """Test validate_report_json function"""

    results_dir, _ = temp_dirs

    # Test valid JSON

    valid_file = results_dir / "valid.json"

    with open(valid_file, "w") as f:

        json.dump(sample_report_data, f)

    assert validate_report_json(valid_file) is True

    # Test invalid JSON (not a dict)

    invalid_file = results_dir / "invalid.json"

    with open(invalid_file, "w") as f:

        f.write('["not", "a", "dict"]')

    assert validate_report_json(invalid_file) is False

    # Test missing URL info

    invalid_data = {"violations": []}  # No URL info

    invalid_file2 = results_dir / "invalid2.json"

    with open(invalid_file2, "w") as f:

        json.dump(invalid_data, f)

    assert validate_report_json(invalid_file2) is False


def test_build_report_success(temp_dirs, sample_report_data):
    """Test successful report generation"""

    results_dir, reports_dir = temp_dirs

    # Create sample report file

    report_file = results_dir / "sample.json"

    with open(report_file, "w") as f:

        json.dump(sample_report_data, f)

    # Generate report

    output_file = reports_dir / "report.html"

    result = build_report(results_dir, output_file, title="Test Report")

    # Verify result

    assert result == output_file

    assert output_file.exists()

    assert output_file.stat().st_size > 0

    summary_file = result.with_suffix(".json")

    assert summary_file.exists()

    summary_data = json.loads(summary_file.read_text())

    assert summary_data["total_violations"] == 1
    assert summary_data["impact_summary"]["critical"] == 1
    assert summary_data["rules"][0]["id"] == "image-alt"
    assert summary_data["rules"][0]["count"] == 1
    assert len(summary_data["rules"][0]["occurrences"]) == 1
    assert summary_data["pages"][0]["total_violations"] == 1

    # Check content

    content = output_file.read_text()

    assert "Test Report" in content

    assert "image-alt" in content

    assert "Pages Scanned" in content

    assert "Total Violations" in content
    assert "Consolidated summary (JSON)" in content


def test_build_report_no_results_dir(temp_dirs):
    """Test build_report with non-existent results directory"""

    _, reports_dir = temp_dirs

    non_existent_dir = Path("/non/existent/directory")

    output_file = reports_dir / "report.html"

    # Should not raise an error, but generate an empty report

    result = build_report(non_existent_dir, output_file)

    assert result == output_file

    assert output_file.exists()

    summary_file = result.with_suffix(".json")
    assert summary_file.exists()
    summary_data = json.loads(summary_file.read_text())
    assert summary_data["total_violations"] == 0


def test_build_report_no_json_files(temp_dirs):
    """Test build_report with no JSON files in results directory"""

    results_dir, reports_dir = temp_dirs

    output_file = reports_dir / "report.html"

    # Generate report with empty results directory

    result = build_report(results_dir, output_file, title="Empty Report")

    assert result == output_file

    assert output_file.exists()

    summary_file = result.with_suffix(".json")
    assert summary_file.exists()
    summary_data = json.loads(summary_file.read_text())
    assert summary_data["total_violations"] == 0

    # Check that it's a valid HTML file with "No accessibility violations"

    content = output_file.read_text()

    assert "Empty Report" in content

    assert "No accessibility violations" in content


def test_build_report_counts_multiple_nodes(temp_dirs):
    """Ensure violations with multiple nodes are counted accurately."""

    results_dir, reports_dir = temp_dirs

    report_file = results_dir / "sample.json"
    report_payload = {
        "scanned_url": "http://localhost:8000/about.html",
        "source_file": "about.html",
        "violations": [
            {
                "id": "color-contrast",
                "impact": "serious",
                "description": "Elements must have sufficient color contrast",
                "help": "Fix contrast",
                "nodes": [
                    {"target": [".btn-primary"], "html": "<a class='btn-primary'>"},
                    {"target": [".link-secondary"], "html": "<a class='link-secondary'>"},
                ],
            }
        ],
    }

    report_file.write_text(json.dumps(report_payload))

    output_file = reports_dir / "report.html"
    result = build_report(results_dir, output_file)

    summary_file = result.with_suffix(".json")
    summary_data = json.loads(summary_file.read_text())

    assert summary_data["total_violations"] == 2
    assert summary_data["impact_summary"]["serious"] == 2
    rule = summary_data["rules"][0]
    assert rule["count"] == 2
    assert len(rule["occurrences"]) == 2

    content = output_file.read_text()
    assert "2 occurrences" in content
