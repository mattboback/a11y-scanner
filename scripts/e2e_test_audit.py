#!/usr/bin/env python3
"""
E2E Test & Report Audit Script for a11y-scanner.

- Runs scanner on each test set in tests/assets/html_sets/N
- Zips site files, scans, generates report
- Compares aggregate JSON to golden files
- Audits HTML report: structure, content, screenshots, self-a11y

Requires: pip install -e ".[dev,test]" (includes beautifulsoup4, lxml)
Assumes: Docker running, golden files up-to-date.
"""

import argparse
import json
import logging
import subprocess
import subprocess as sp  # For jq fallback check
import sys
from difflib import unified_diff
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

# External deps for auditing
from bs4 import BeautifulSoup

# Import your project modules
from scanner.container.integration import (
    _clean_data_dirs,
    _slurp_raw_reports,
    _unified_diff_str,
    find_project_root,
)
from scanner.container.manager import ContainerManager
from scanner.core.logging_setup import setup_logging
from scanner.reporting.jinja_report import build_report

# Setup logging (reuse your setup)
setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TESTS_DIR = Path(__file__).parent.parent / "tests/assets/html_sets"
DATA_DIR = Path(__file__).parent.parent / "data"
GOLDEN_SUFFIX = "golden_results/report.json"
REPORT_PATH = DATA_DIR / "reports/latest.html"
ZIP_PATH = DATA_DIR / "unzip/site.zip"
RESULTS_DIR = DATA_DIR / "results"


def has_jq() -> bool:
    """Check if jq is available for JSON diffing."""
    try:
        sp.run(["jq", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning(
            "jq not found; using Python difflib for JSON comparison (slower but functional)"
        )
        return False


def zip_test_set(test_dir: Path, zip_path: Path) -> None:
    """Create ZIP from test set files (exclude golden_results)."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for p in test_dir.rglob("*"):
            if "golden_results" in p.parts:
                continue
            if p.is_file():
                arcname = p.relative_to(test_dir)
                zf.write(p, arcname)
                logger.debug(f"Zipped: {arcname}")
    logger.info(
        f"ZIP created: {zip_path} ({len([p for p in test_dir.rglob('*') if p.is_file() and 'golden_results' not in p.parts])} files)"
    )


def run_scanner() -> int:
    """Run the scanner via container runner."""
    logger.info("Running scanner: python -m scanner.container.runner run")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scanner.container.runner", "run"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Scanner output: {result.stdout}")
        return 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Scanner failed: {e.stderr}")
        return e.returncode


def aggregate_and_compare_results(test_name: str, golden_path: Path) -> bool:
    """Aggregate JSON results and compare to golden."""
    actual_list = _slurp_raw_reports(RESULTS_DIR)
    actual_str = json.dumps(actual_list, indent=2, sort_keys=True)

    try:
        with open(golden_path, encoding="utf-8") as f:
            golden_str = f.read()
    except FileNotFoundError:
        logger.error(f"Golden file missing: {golden_path}")
        return False

    if actual_str.strip() == golden_str.strip():
        logger.info(f"JSON Comparison for {test_name}: PASS")
        return True

    # Diff
    if has_jq():
        # Use jq for pretty diff (optional)
        diff_cmd = ["jq", "-S", "."]  # Sort keys for diff
        actual_sorted = sp.run(
            diff_cmd + [str(RESULTS_DIR / "*.json")],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        ).stdout
        golden_sorted = sp.run(
            ["jq", "-S", "."], input=golden_str, capture_output=True, text=True
        ).stdout
        diff = "\n".join(
            unified_diff(
                golden_sorted.splitlines(),
                actual_sorted.splitlines(),
                fromfile="golden",
                tofile="actual",
            )
        )
    else:
        diff = _unified_diff_str(golden_str, actual_str, "golden", "actual")

    logger.error(f"JSON Mismatch for {test_name}:\n{diff}")
    return False


def count_violations_by_impact(results_dir: Path) -> dict[str, int]:
    """Count violations by impact from JSON files."""
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0, "unknown": 0}
    pages_scanned = 0
    total_violations = 0
    screenshot_count = 0

    for json_file in results_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            pages_scanned += 1
            for v in data.get("violations", []):
                impact = v.get("impact", "unknown").lower()
                counts[impact] = counts.get(impact, 0) + 1
                total_violations += 1
                if v.get("screenshot_path"):
                    screenshot_count += 1
        except Exception as e:
            logger.warning(f"Skipping invalid JSON {json_file}: {e}")

    logger.info(
        f"Stats: Pages={pages_scanned}, Total Violations={total_violations}, Screenshots={screenshot_count}"
    )
    logger.info(f"By Impact: {counts}")
    return {
        "pages_scanned": pages_scanned,
        "total_violations": total_violations,
        "screenshots": screenshot_count,
        "by_impact": counts,
    }


def audit_report(report_path: Path, expected_stats: dict) -> bool:
    """Audit the generated HTML report."""
    if not report_path.exists():
        logger.error("Report not generated!")
        return False

    with open(report_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "lxml")

    audit_issues = []
    score = 100  # Start perfect, deduct for issues

    # 1. Basic Structure
    title = soup.find("title")
    if not title or "Accessibility Report" not in title.text:
        audit_issues.append("Invalid/missing title")
        score -= 10

    generated_at = soup.find("time", {"datetime": True})
    if not generated_at:
        audit_issues.append("Missing generated_at timestamp")
        score -= 5

    # 2. Stats Match JSON
    pages_elem = soup.find("span", {"id": "pages-scanned"})
    violations_elem = soup.find("span", {"id": "total-violations"})
    if pages_elem:
        try:
            parsed_pages = int(pages_elem.text.strip())
            if parsed_pages != expected_stats["pages_scanned"]:
                audit_issues.append(
                    f"Pages mismatch: report={parsed_pages}, expected={expected_stats['pages_scanned']}"
                )
                score -= 10
        except ValueError:
            audit_issues.append("Invalid pages count in report")
            score -= 5

    if violations_elem:
        try:
            parsed_violations = int(violations_elem.text.strip())
            if parsed_violations != expected_stats["total_violations"]:
                audit_issues.append(
                    f"Violations mismatch: report={parsed_violations}, expected={expected_stats['total_violations']}"
                )
                score -= 10
        except ValueError:
            audit_issues.append("Invalid violations count in report")
            score -= 5

    # 3. Rule Groups & Impacts
    rule_groups = soup.find_all("div", {"class": lambda x: x and "rule-group" in x})
    if expected_stats["total_violations"] > 0:
        if len(rule_groups) == 0:
            audit_issues.append("No rule groups found (expected violations)")
            score -= 20
        else:
            impacts_in_report = {}
            for group in rule_groups:
                impact_class = group.get("class")
                impact = next(
                    (
                        c.replace("impact-", "")
                        for c in impact_class
                        if c.startswith("impact-")
                    ),
                    "unknown",
                )
                count_elem = group.find("span", {"class": "violation-count"})
                count = int(count_elem.text.strip()) if count_elem else 0
                impacts_in_report[impact] = impacts_in_report.get(impact, 0) + count
            # Loose match (allow for grouping diffs)
            for impact, exp_count in expected_stats["by_impact"].items():
                rep_count = impacts_in_report.get(impact, 0)
                if abs(rep_count - exp_count) > 1:  # Tolerance for minor diffs
                    audit_issues.append(
                        f"Impact {impact} mismatch: report={rep_count}, expected={exp_count}"
                    )
                    score -= 5
    else:
        no_violations = soup.find("div", {"id": "no-violations"})
        if not no_violations:
            audit_issues.append("No 'no violations' message in empty report")
            score -= 10

    # 4. Screenshots
    img_tags = soup.find_all("img", {"src": lambda x: x and x.endswith(".png")})
    linked_screenshots = len(img_tags)
    if linked_screenshots != expected_stats["screenshots"]:
        audit_issues.append(
            f"Screenshot count mismatch: report={linked_screenshots}, expected={expected_stats['screenshots']}"
        )
        score -= 10

    # Verify screenshot files exist and are linked correctly (relative paths)
    base_dir = report_path.parent
    for img in img_tags:
        src = img.get("src")
        if src:
            full_path = (base_dir / ".." / src).resolve()  # Relative to results/
            if not full_path.exists():
                audit_issues.append(f"Missing screenshot file: {full_path}")
                score -= 5
            # Basic a11y: Alt text?
            if not img.get("alt"):
                audit_issues.append(f"Missing alt text on screenshot: {src}")
                score -= 2

    # 5. Self-A11y Audit of Report (Basic)
    headings = soup.find_all(["h1", "h2", "h3"])
    if len(headings) < 3:  # Expect at least summary, rules, etc.
        audit_issues.append("Insufficient headings for structure")
        score -= 5
    links = soup.find_all("a", href=True)
    broken_links = [
        link
        for link in links
        if link["href"].startswith("http") and "dequeuniversity" not in link["href"]
    ]  # Spot-check WCAG links
    if broken_links:
        audit_issues.append(f"Potential broken links: {len(broken_links)}")
        score -= 5

    # Output
    logger.info(f"Report Audit for {report_path.name}: Score={score}%")
    if audit_issues:
        logger.error(f"Audit Issues: {audit_issues}")
        return False
    logger.info("Report Audit: PASS")
    return True


def run_single_test(test_dir: Path) -> bool:
    """Run e2e for one test set."""
    test_name = test_dir.name
    logger.info(f"--- E2E Test & Audit: Test Set {test_name} ---")

    # Clean & Prep
    _clean_data_dirs(DATA_DIR)
    project_root = find_project_root()
    manager = ContainerManager(project_root=project_root)
    manager.ensure_image()  # Build if needed

    # ZIP
    zip_test_set(test_dir, ZIP_PATH)

    # Scan
    exit_code = run_scanner()
    if exit_code != 0:
        logger.error(f"Scanner failed for {test_name}: Exit {exit_code}")
        return False

    # Generate Report
    try:
        build_report(RESULTS_DIR, REPORT_PATH, title=f"Test Report - {test_name}")
    except Exception as e:
        logger.error(f"Report generation failed for {test_name}: {e}")
        return False

    # Stats from JSON
    expected_stats = count_violations_by_impact(RESULTS_DIR)

    # Compare JSON
    golden_path = test_dir / GOLDEN_SUFFIX
    json_pass = aggregate_and_compare_results(test_name, golden_path)

    # Audit Report
    report_pass = audit_report(REPORT_PATH, expected_stats)

    # Cleanup (optional: keep for manual inspection)
    # shutil.rmtree(RESULTS_DIR)
    # shutil.rmtree(DATA_DIR / "reports")
    # shutil.rmtree(DATA_DIR / "scan")
    # os.unlink(ZIP_PATH)

    overall_pass = json_pass and report_pass
    status = "✅ PASSED" if overall_pass else "❌ FAILED"
    logger.info(f"Test Set {test_name}: {status}")
    return overall_pass


def main():
    parser = argparse.ArgumentParser(description="E2E Test & Audit Script")
    parser.add_argument("--test-set", type=str, help="Run single test set (e.g., '1')")
    args = parser.parse_args()

    test_dirs = [d for d in TESTS_DIR.iterdir() if d.is_dir() and d.name.isdigit()]
    if args.test_set:
        test_dirs = [TESTS_DIR / args.test_set]
        if not test_dirs[0].exists():
            logger.error(f"Test set {args.test_set} not found!")
            sys.exit(1)

    if not test_dirs:
        logger.error("No test sets found in tests/assets/html_sets/")
        sys.exit(1)

    failures = []
    overall_stats = {
        "total_tests": len(test_dirs),
        "total_violations": 0,
        "total_screenshots": 0,
    }

    for test_dir in sorted(test_dirs, key=lambda p: int(p.name)):
        pass_test = run_single_test(test_dir)
        if not pass_test:
            failures.append(test_dir.name)
        # Accumulate stats (from count_violations_by_impact)
        # Note: You'd need to capture and sum from each run; for simplicity, log per test

    logger.info("\n--- Summary ---")
    logger.info(f"Tests Run: {overall_stats['total_tests']}")
    if failures:
        logger.error(f"Failures: {', '.join(failures)}")
        sys.exit(1)
    logger.info("All e2e tests & audits passed! 🎉")


if __name__ == "__main__":
    main()
