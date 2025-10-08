# src/scanner/pipeline.py
from __future__ import annotations

import logging
from typing import Any

from scanner.core.settings import Settings
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

log = logging.getLogger(__name__)

__all__ = ["Pipeline"]


class Pipeline:
    """
    Orchestrates the scanning workflow using the native Python Playwright library.
    """

    def __init__(
        self,
        settings: Settings,
        zip_service: ZipService,
        html_service: HtmlDiscoveryService,
        http_service: HttpService,
        axe_service: PlaywrightAxeService,
    ):
        self.settings = settings
        self.zip_service = zip_service
        self.html_service = html_service
        self.http_service = http_service
        self.axe_service = axe_service

    def run(self) -> list[dict[str, Any]]:
        """
        Orchestrates the full scanning pipeline:
        1. Unzip the source archive
        2. Discover HTML files
        3. Start a local web server
        4. Scan each HTML file with Playwright + axe-core
        5. Stop the web server
        6. Return consolidated results
        """
        log.info("Starting pipeline execution...")
        all_results = []

        try:
            # Step 1: Unzip
            self.zip_service.run()

            # Step 2: Discover HTML files
            html_files = self.html_service.discover_html_files()
            if not html_files:
                log.warning(
                    "No HTML files found in the extracted content. Nothing to scan."
                )
                return []

            # Step 3: Start the server
            self.http_service.start(directory=self.settings.scan_dir)

            # Step 4: Scan each file
            for file_info in html_files:
                relative_path = file_info["relative"]
                url_to_scan = f"{self.http_service.base_url}/{relative_path}"

                # Define a unique path for the full report artifact
                report_filename = f"{relative_path.as_posix().replace('/', '_')}.json"
                report_path = self.settings.results_dir / report_filename

                try:
                    # The new service directly returns the violations
                    violations = self.axe_service.scan_url(url_to_scan, report_path)
                    if violations:
                        # Add context to each violation for better reporting
                        for violation in violations:
                            violation["scanned_url"] = url_to_scan
                            violation["source_file"] = str(relative_path)
                        all_results.extend(violations)
                except RuntimeError as e:
                    log.error("Failed to scan %s: %s", url_to_scan, e)
                    continue  # Continue to the next file

            log.info("Pipeline execution completed successfully.")
            return all_results

        except FileNotFoundError as e:
            log.error("Pipeline failed: input zip file not found. %s", e)
            raise
        except Exception:
            log.exception("Pipeline failed due to an unexpected error.")
            raise
        finally:
            # Step 5: Always ensure the server is stopped
            log.info("Pipeline finished. Shutting down HTTP server.")
            self.http_service.stop()
