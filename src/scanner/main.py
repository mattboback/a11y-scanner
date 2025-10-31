# src/scanner/main.py
import json
import logging
import os
import sys

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.pipeline import Pipeline
from scanner.reporting.jinja_report import build_report
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

log = logging.getLogger(__name__)

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"


def _assert_docker_context() -> None:
    """Ensure we are running inside the Docker container."""
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        print(
            "\n[ERROR] This CLI is Docker-only.\n"
            "Run via the container runner instead:\n"
            "  python -m scanner.container.runner prepare\n"
            "  python -m scanner.container.runner run\n",
            file=sys.stderr,
        )
        sys.exit(2)


def main():
    """Main entry point for the scanner application using Playwright."""
    _assert_docker_context()  # hard guard: no bare-metal runs
    setup_logging(level=logging.INFO)
    log.info("--- Starting A11y Scanner with Playwright ---")

    try:
        # 1. Create all dependencies (the "composition root")
        settings = Settings()
        zip_service = ZipService(
            unzip_dir=settings.unzip_dir, scan_dir=settings.scan_dir
        )
        html_service = HtmlDiscoveryService(scan_dir=settings.scan_dir)
        http_service = HttpService()
        axe_service = PlaywrightAxeService()
        # 2. Orchestrate
        pipeline = Pipeline(
            settings=settings,
            zip_service=zip_service,
            html_service=html_service,
            http_service=http_service,
            axe_service=axe_service,
        )
        # 3. Run the pipeline
        results = pipeline.run()
        # 4. Generate consolidated HTML report
        reports_dir = settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_html = reports_dir / "latest.html"

        try:
            report_path = build_report(
                settings.results_dir, output_html, title="Accessibility Report"
            )
            summary_path = report_path.with_suffix(".json")
            log.info("Consolidated HTML report generated at: %s", report_path)
            log.info("Summary JSON generated at: %s", summary_path)
        except Exception as e:
            report_path = output_html.resolve()
            summary_path = report_path.with_suffix(".json")
            log.error("Failed to generate HTML report: %s", e)
            # Continue with the rest of the execution, don't fail the entire scan

        # 5. Process results
        log.info("--- Pipeline run finished ---")
        if results:
            print("\n--- Accessibility Scan Results ---")
            print(f"Found {len(results)} accessibility violations:")
            print(json.dumps(results, indent=2))
            print(f"\n✅ Full HTML report available at: {report_path}")
            print(f"📄 Consolidated JSON summary at: {summary_path}")
        else:
            print("\n✅ No accessibility violations found!")
            print(f"Full report available at: {report_path}")
            print(f"JSON summary available at: {summary_path}")

        sys.exit(0)

    except FileNotFoundError:
        log.error("Execution failed: Could not find the input zip file.")
        sys.exit(1)
    except RuntimeError as e:
        log.error("Execution failed: %s", e)
        sys.exit(1)
    except Exception:
        log.exception("An unexpected error occurred during pipeline execution.")
        sys.exit(1)


if __name__ == "__main__":
    main()
