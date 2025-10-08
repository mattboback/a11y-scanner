# src/scanner/services/playwright_axe_service.py
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, sync_playwright

logger = logging.getLogger(__name__)


class PlaywrightAxeService:
    """
    Run accessibility scans using the native `axe-playwright-python` library.

    This approach is self-contained within Python and does not require
    Node.js subprocesses.
    """

    def _capture_violation_screenshot(
        self, page: Page, violation: dict[str, Any], results_dir: Path
    ) -> str | None:
        """Highlight the first node for a violation and take a screenshot."""
        node = violation["nodes"][0]
        selector = node["target"][0]  # CSS selector for the element

        try:
            highlight_style = "{ border: 5px solid red !important; }"
            page.add_style_tag(content=f"{selector} {highlight_style}")

            screenshot_filename = f"violation-{violation['id']}-{uuid.uuid4()}.png"
            screenshot_path = results_dir / screenshot_filename

            page.screenshot(path=str(screenshot_path))
            logger.info(
                "Captured screenshot for violation '%s' at %s",
                violation["id"],
                screenshot_path,
            )
            return str(screenshot_path)

        except Exception as e:
            logger.error(
                "Failed to capture screenshot for selector '%s': %s", selector, e
            )
            return None

    def scan_url(self, url: str, output_path: Path) -> list[dict[str, Any]]:
        """
        Scan a URL for accessibility issues, take screenshots of violations,
        and save the report.
        """
        logger.info("Scanning %s with axe-playwright-python", url)
        axe = Axe()
        results_dir = output_path.parent
        # Ensure the results directory exists before attempting screenshots
        # so that page.screenshot() does not fail on first run.
        results_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="networkidle")
                results = axe.run(page)

                violations = results.response.get("violations", [])

                if violations:
                    logger.warning(
                        "Found %d accessibility violations at %s",
                        len(violations),
                        url,
                    )
                    for violation in violations:
                        screenshot_path = self._capture_violation_screenshot(
                            page, violation, results_dir
                        )
                        violation["screenshot_path"] = screenshot_path
                else:
                    logger.info("No accessibility violations found at %s", url)

                # Save the full, augmented report for debugging and artifacts.
                # Important: add 'scanned_url' so integr. tests can sort like before.
                full_report = dict(results.response)
                full_report["scanned_url"] = url

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(full_report, f, indent=2)
                logger.info("Full scan report saved to %s", output_path)

            finally:
                browser.close()

        return violations
