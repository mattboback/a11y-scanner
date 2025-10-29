import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

logger = logging.getLogger(__name__)


class PlaywrightAxeService:
    """
    Runs axe-core audits against pages using Playwright.
    Now safer against selector injection and supports disabling screenshots via env:
      - Set A11Y_NO_SCREENSHOTS=1 to skip screenshot capture.
    """

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._managed = False
        # Feature flag: allow disabling screenshots in sensitive environments
        self._screenshots_enabled = os.environ.get("A11Y_NO_SCREENSHOTS", "0") != "1"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._browser is not None:
            logger.warning("Browser already started, ignoring start() call")
            return
        logger.info("Starting managed Playwright browser (reusable mode)")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        self._managed = True
        logger.info("Playwright browser started successfully")

    def stop(self):
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._managed = False
        logger.info("Playwright browser stopped")

    def _capture_violation_screenshot(
        self, page: Page, violation: dict[str, Any], results_dir: Path
    ) -> str | None:
        """
        Safely capture a screenshot for a violation.
        - Uses locator.evaluate with a function to avoid selector string injection.
        - Falls back to a plain full-page screenshot without injecting CSS.
        """
        if not self._screenshots_enabled:
            return None

        nodes = violation.get("nodes", [])
        if not nodes:
            return None
        node = nodes[0]
        targets = node.get("target", [])
        if not targets:
            return None

        selector = targets[0]
        try:
            screenshot_filename = f"violation-{violation['id']}-{uuid.uuid4()}.png"
            screenshot_path = results_dir / screenshot_filename
            try:
                locator = page.locator(selector).first
                # Use a function body, not a string, to avoid injection vulnerabilities.
                locator.evaluate(
                    "(el) => { el.style.outline = '3px solid red'; el.style.outlineOffset = '2px'; }"
                )
                locator.screenshot(path=str(screenshot_path))
                logger.info(
                    "Captured element screenshot for violation '%s' at %s",
                    violation["id"],
                    screenshot_path,
                )
            except Exception as element_error:
                logger.debug(
                    "Element screenshot failed for '%s', using full-page: %s",
                    selector,
                    element_error,
                )
                # No selector/CSS injection here; just capture the current page.
                page.screenshot(path=str(screenshot_path))
                logger.info(
                    "Captured full-page screenshot for violation '%s' at %s",
                    violation["id"],
                    screenshot_path,
                )
            return str(screenshot_path)
        except Exception as e:
            logger.error(
                "Failed to capture screenshot for selector '%s': %s", selector, e
            )
            return None

    def scan_url(
        self, url: str, output_path: Path, source_file: str | None = None
    ) -> list[dict[str, Any]]:
        logger.info("Scanning %s with axe-playwright-python", url)
        axe = Axe()
        results_dir = output_path.parent
        results_dir.mkdir(parents=True, exist_ok=True)

        if self._managed and self._context:
            page = self._context.new_page()
            try:
                violations = self._scan_page(
                    page, url, output_path, source_file, axe, results_dir
                )
            finally:
                page.close()
        else:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()
                try:
                    violations = self._scan_page(
                        page, url, output_path, source_file, axe, results_dir
                    )
                finally:
                    browser.close()

        return violations

    def _scan_page(
        self,
        page: Page,
        url: str,
        output_path: Path,
        source_file: str | None,
        axe: Axe,
        results_dir: Path,
    ) -> list[dict[str, Any]]:
        page.goto(url, wait_until="networkidle")
        results = axe.run(page)
        violations = results.response.get("violations", [])
        if violations:
            logger.warning(
                "Found %d accessibility violations at %s", len(violations), url
            )
            for violation in violations:
                screenshot_path = self._capture_violation_screenshot(
                    page, violation, results_dir
                )
                violation["screenshot_path"] = screenshot_path
        else:
            logger.info("No accessibility violations found at %s", url)

        full_report = dict(results.response)
        full_report["scanned_url"] = url
        if source_file:
            full_report["source_file"] = source_file

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        logger.info("Full scan report saved to %s", output_path)
        return violations
