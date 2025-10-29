import logging
import os
import sys

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.reporting.jinja_report import build_report
from scanner.services.playwright_axe_service import PlaywrightAxeService

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"

# Configure target via environment to avoid hardcoding third-party sites.
# e.g. A11Y_BASE_URL="https://example.com" A11Y_PAGES="/,/about,/contact"
BASE_URL = os.environ.get("A11Y_BASE_URL", "").strip()
PAGES_TO_SCAN = [
    p.strip() for p in os.environ.get("A11Y_PAGES", "/").split(",") if p.strip()
]

log = logging.getLogger(__name__)


def _assert_docker_context() -> None:
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        print(
            "\n[ERROR] This CLI is Docker-only.\nRun via the container runner instead:\n"
            "  python -m scanner.container.runner prepare\n"
            "  python -m scanner.container.runner run\n",
            file=sys.stderr,
        )
        sys.exit(2)


def create_safe_filename(base_url: str, page_path: str) -> str:
    domain = base_url.replace("https://", "").replace("http://", "")
    path_part = "root" if page_path == "/" else page_path.strip("/").replace("/", "_")
    return f"{domain}_{path_part}.json"


def main():
    _assert_docker_context()
    setup_logging(level=logging.INFO)

    if not BASE_URL:
        log.error(
            "BASE_URL is not set. Set A11Y_BASE_URL environment variable (e.g. https://example.com)."
        )
        sys.exit(2)

    log.info("--- Starting Live A11y Site Scanner ---")
    log.info("Target site: %s", BASE_URL)

    settings = Settings()
    live_results_dir = settings.data_dir / "live_results"
    live_results_dir.mkdir(parents=True, exist_ok=True)
    log.info("Results will be saved in: %s", live_results_dir.resolve())
    reports_dir = settings.data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    total_violations_count = 0
    try:
        with PlaywrightAxeService() as axe_service:
            for page_path in PAGES_TO_SCAN:
                url_to_scan = f"{BASE_URL}{page_path}"
                report_filename = create_safe_filename(BASE_URL, page_path)
                report_path = live_results_dir / report_filename
                log.info("--- Scanning page: %s ---", url_to_scan)
                try:
                    violations = axe_service.scan_url(url_to_scan, report_path)
                    if violations:
                        log.warning(
                            "Found %d violation(s) on %s", len(violations), url_to_scan
                        )
                        total_violations_count += len(violations)
                    else:
                        log.info("✅ No violations found on %s", url_to_scan)
                except Exception as e:
                    log.error("Failed to scan %s: %s", url_to_scan, e, exc_info=True)
                    continue

        output_html = reports_dir / "latest.html"
        build_report(
            live_results_dir, output_html, title="Accessibility Report (Live Site)"
        )
        log.info("Consolidated HTML report generated at: %s", output_html)
        log.info("--- Live Scan Finished ---")

        pages_count = len(PAGES_TO_SCAN)
        if total_violations_count > 0:
            print("\n--- Accessibility Scan Summary ---")
            print(
                f"Found a total of {total_violations_count} accessibility violation(s)."
            )
            print(f"Scanned {pages_count} page(s).")
            print(f"Detailed JSON reports: {live_results_dir.resolve()}")
            print(f"HTML report available at: {output_html}")
        else:
            print(
                "\n✅ Excellent! No accessibility violations were found on the scanned pages."
            )
            print(f"Full report available at: {output_html}")
        sys.exit(0)
    except Exception:
        log.exception("An unexpected error occurred during the live scan.")
        sys.exit(1)


if __name__ == "__main__":
    main()
