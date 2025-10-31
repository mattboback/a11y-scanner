#!/usr/bin/env python3
"""
Golden Test Runner for A11y Scanner
======================================
This script automates the process of:
1. Extracting test site ZIPs from tests/ directory
2. Running accessibility scans on each site
3. Generating golden test files for regression testing
4. Producing HTML reports for review

Usage:
    python scripts/run_golden_tests.py [--generate] [--sites SITE1,SITE2,...]

    --generate   : Generate new golden files (overwrites existing)
    --sites      : Run specific sites (comma-separated, defaults to all)
    --no-docker  : Run scans without Docker (local mode)
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_project_root() -> Path:
    """Find the project root directory."""
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


def extract_test_zip(zip_path: Path, extract_to: Path) -> bool:
    """Extract a ZIP file to the target directory."""
    try:
        extract_to.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
        logger.info(f"✓ Extracted {zip_path.name} to {extract_to}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to extract {zip_path}: {e}")
        return False


def prepare_test_assets(
    project_root: Path, test_zips: list[Path] | None = None
) -> dict[str, Path]:
    """
    Prepare test assets by extracting ZIPs to tests/assets/html_sets/

    Returns:
        Dict mapping site names to their test directories
    """
    test_assets_dir = project_root / "tests" / "assets" / "html_sets"
    test_assets_dir.mkdir(parents=True, exist_ok=True)

    # Find all ZIPs in tests directory
    tests_dir = project_root / "tests"
    if test_zips is None:
        test_zips = sorted(tests_dir.glob("*.zip"))

    test_sites = {}

    for zip_path in test_zips:
        # Extract site name from ZIP (e.g., "Charitize-1.0.0.zip" -> "Charitize")
        site_name = zip_path.stem.rsplit("-", 1)[0]
        test_dir = test_assets_dir / site_name

        # Clean existing directory
        if test_dir.exists():
            logger.info(f"Cleaning existing test directory: {test_dir}")
            shutil.rmtree(test_dir)

        # Extract ZIP
        if extract_test_zip(zip_path, test_dir):
            test_sites[site_name] = test_dir
        else:
            logger.warning(f"Skipping {site_name} due to extraction error")

    return test_sites


def run_scan_for_site(
    project_root: Path, site_name: str, use_docker: bool = True
) -> bool:
    """
    Run an accessibility scan for a specific site.

    Assumes the site ZIP has been extracted to data/unzip/site.zip
    """
    try:
        if use_docker:
            logger.info(f"Running scan for {site_name} in Docker...")
            result = subprocess.run(
                ["make", "scan-local"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
        else:
            logger.info(f"Running scan for {site_name} locally...")
            result = subprocess.run(
                ["uv", "run", "python", "-m", "scanner.container.runner", "run"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

        if result.returncode != 0:
            logger.error(f"Scan failed for {site_name}")
            logger.error(f"STDOUT:\n{result.stdout}")
            logger.error(f"STDERR:\n{result.stderr}")
            return False

        logger.info(f"✓ Scan completed for {site_name}")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Scan timeout for {site_name}")
        return False
    except Exception as e:
        logger.error(f"Error running scan for {site_name}: {e}")
        return False


def generate_golden_file(site_name: str, project_root: Path) -> bool:
    """
    Generate golden test file from scan results.

    Collects all JSON reports from data/results/ and saves to golden_results/
    """
    try:
        test_assets_dir = project_root / "tests" / "assets" / "html_sets" / site_name
        results_dir = project_root / "data" / "results"
        golden_dir = test_assets_dir / "golden_results"

        # Create golden_results directory
        golden_dir.mkdir(parents=True, exist_ok=True)

        # Collect and merge all result JSON files
        items = []
        for json_file in sorted(results_dir.glob("*.json")):
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "scanned_url" not in data:
                        data["scanned_url"] = data.get("url", "")
                    items.append(data)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {json_file}: {e}")
                continue

        # Sort by scanned_url for consistency
        items.sort(key=lambda d: d.get("scanned_url", ""))

        # Write golden file
        golden_file = golden_dir / "report.json"
        with golden_file.open("w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, sort_keys=True)

        logger.info(f"✓ Generated golden file: {golden_file}")
        logger.info(f"  - {len(items)} page(s) scanned")
        return True

    except Exception as e:
        logger.error(f"Error generating golden file for {site_name}: {e}")
        return False


def generate_html_report(site_name: str, project_root: Path) -> bool:
    """Generate a consolidated HTML (and JSON) report using the in-repo API."""
    try:
        sys.path.insert(0, str(project_root / "src"))
        from scanner.reporting.jinja_report import build_report

        reports_dir = project_root / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        results_dir = project_root / "data" / "results"
        latest_report = reports_dir / "latest.html"

        logger.info(f"Generating HTML report for {site_name}...")
        build_report(results_dir, latest_report, "Accessibility Scan Report")
        logger.info("✓ HTML report generated")

        summary_report = latest_report.with_suffix(".json")

        if latest_report.exists():
            site_report = (
                project_root
                / "data"
                / "reports"
                / f"{site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            )
            shutil.copy(latest_report, site_report)
            logger.info(f"✓ Saved report: {site_report}")

            if summary_report.exists():
                site_summary = site_report.with_suffix(".json")
                shutil.copy(summary_report, site_summary)
                logger.info(f"✓ Saved summary: {site_summary}")
            return True
        logger.warning(f"No report generated for {site_name}")
        return False
    except Exception as e:
        logger.error(f"Error generating HTML report for {site_name}: {e}")
        return False


def clean_data_dirs(data_dir: Path) -> None:
    """Clean out data directories before scanning."""
    for name in ("unzip", "results", "scan"):
        d = data_dir / name
        if d.exists():
            try:
                shutil.rmtree(d)
            except Exception:
                pass
        d.mkdir(parents=True, exist_ok=True)


def copy_site_to_unzip(site_dir: Path, project_root: Path) -> bool:
    """Copy a test site to data/unzip/site.zip for scanning."""
    try:
        unzip_dir = project_root / "data" / "unzip"
        unzip_dir.mkdir(parents=True, exist_ok=True)

        # Create site.zip from the extracted directory
        zip_path = unzip_dir / "site.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", site_dir)
        logger.info(f"✓ Created {zip_path}")
        return True

    except Exception as e:
        logger.error(f"Error copying site: {e}")
        return False


def compare_golden_files(site_name: str, project_root: Path) -> bool:
    """
    Compare current scan results with golden file.

    Returns True if they match, False if they differ.
    """
    try:
        test_assets_dir = project_root / "tests" / "assets" / "html_sets" / site_name
        results_dir = project_root / "data" / "results"
        golden_file = test_assets_dir / "golden_results" / "report.json"

        if not golden_file.exists():
            logger.warning(f"No golden file found for {site_name}")
            return False

        # Collect current results
        items = []
        for json_file in sorted(results_dir.glob("*.json")):
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "scanned_url" not in data:
                        data["scanned_url"] = data.get("url", "")
                    items.append(data)
            except json.JSONDecodeError:
                continue

        items.sort(key=lambda d: d.get("scanned_url", ""))

        # Compare with golden
        actual_str = json.dumps(items, indent=2, sort_keys=True)
        with golden_file.open("r", encoding="utf-8") as f:
            golden_str = f.read()

        if actual_str.strip() == golden_str.strip():
            logger.info(f"✓ {site_name} matches golden file")
            return True
        else:
            logger.warning(f"✗ {site_name} differs from golden file")
            # Show diff
            diff = list(
                difflib.unified_diff(
                    golden_str.splitlines(),
                    actual_str.splitlines(),
                    fromfile="golden",
                    tofile="actual",
                    lineterm="",
                )
            )
            if diff:
                logger.info("Diff (first 50 lines):")
                for line in diff[:50]:
                    logger.info(f"  {line}")
                if len(diff) > 50:
                    logger.info(f"  ... and {len(diff) - 50} more lines")
            return False

    except Exception as e:
        logger.error(f"Error comparing golden files for {site_name}: {e}")
        return False


def run_integration_tests(project_root: Path) -> bool:
    """Run the integration test suite."""
    try:
        logger.info("\nRunning integration test suite...")
        result = subprocess.run(
            ["make", "integration"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode == 0:
            logger.info("✓ Integration tests passed")
            return True
        else:
            logger.warning("✗ Integration tests failed")
            logger.info(f"Output:\n{result.stdout}")
            return False

    except Exception as e:
        logger.error(f"Error running integration tests: {e}")
        return False


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate golden test files for A11y Scanner",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new golden files (default: compare with existing)",
    )
    parser.add_argument(
        "--sites",
        help="Comma-separated list of sites to process (default: all)",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Run scans without Docker",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Only compare results with golden files (skip scanning)",
    )

    args = parser.parse_args(argv)

    project_root = find_project_root()
    logger.info(f"Project root: {project_root}")

    # Determine which sites to process
    if args.sites:
        selected_sites = args.sites.split(",")
        test_zips = [
            project_root / "tests" / f"{site.strip()}-*.zip"
            for site in selected_sites
        ]
        # Expand glob patterns
        test_zips = []
        for pattern in [
            project_root / "tests" / f"{site.strip()}*.zip"
            for site in selected_sites
        ]:
            test_zips.extend(sorted(pattern.parent.glob(pattern.name)))
    else:
        test_zips = None

    # Step 1: Prepare test assets (extract ZIPs)
    logger.info("\n=== Step 1: Preparing test assets ===")
    test_sites = prepare_test_assets(project_root, test_zips)

    if not test_sites:
        logger.error("No test sites found. Please ensure ZIP files are in tests/")
        return 1

    logger.info(f"Found {len(test_sites)} test site(s): {', '.join(test_sites.keys())}")

    # Step 2: Run scans and generate results
    success_count = 0

    if not args.compare_only:
        logger.info("\n=== Step 2: Running accessibility scans ===")

        for site_name, site_dir in test_sites.items():
            logger.info(f"\n--- Processing: {site_name} ---")

            # Clean data directories
            clean_data_dirs(project_root / "data")

            # Copy site to scanning location
            if not copy_site_to_unzip(site_dir, project_root):
                logger.error(f"Failed to prepare {site_name} for scanning")
                continue

            # Run scan
            if not run_scan_for_site(project_root, site_name, use_docker=not args.no_docker):
                logger.error(f"Failed to scan {site_name}")
                continue

            # Generate golden file if requested
            if args.generate:
                if generate_golden_file(site_name, project_root):
                    success_count += 1
                else:
                    logger.error(f"Failed to generate golden file for {site_name}")
            else:
                # Compare with existing golden
                if compare_golden_files(site_name, project_root):
                    success_count += 1

            # Generate HTML report
            generate_html_report(site_name, project_root)

    else:
        # Just compare mode
        logger.info("\n=== Comparing with golden files ===")
        for site_name, _ in test_sites.items():
            if compare_golden_files(site_name, project_root):
                success_count += 1

    # Step 3: Run integration tests
    logger.info("\n=== Step 3: Running integration tests ===")
    if run_integration_tests(project_root):
        logger.info("\n✓ All integration tests passed")
    else:
        logger.warning("\n✗ Some integration tests failed (see details above)")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total sites processed: {len(test_sites)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(test_sites) - success_count}")

    if args.generate:
        logger.info("\n✓ Golden test files have been generated/updated")
        logger.info(f"  Location: tests/assets/html_sets/*/golden_results/report.json")

    logger.info("\n✓ HTML reports available at: data/reports/")

    if success_count == len(test_sites):
        logger.info("\n✓ All tests completed successfully!")
        return 0
    else:
        logger.warning(f"\n✗ {len(test_sites) - success_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
