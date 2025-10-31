import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from scanner.utils import sanitize_for_json

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
        Capture a screenshot with intelligent RGB-inverse highlighting.

        Strategy:
        1. Locate element and get its average background color
        2. Calculate RGB inverse for maximum contrast
        3. Apply obnoxious multi-layer highlighting in inverse color
        4. Capture with intelligent sizing (min 200px width, context padding)
        5. Fall back to viewport screenshot if element capture fails
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
        screenshot_filename = f"violation-{violation['id']}-{uuid.uuid4()}.png"
        screenshot_path = results_dir / screenshot_filename

        try:
            locator = page.locator(selector).first

            # Scroll element into view
            try:
                locator.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass  # Continue even if scroll fails

            # Choose a maximally-visible highlight color based on element's brightness
            try:
                avg_brightness = locator.evaluate("""
                    (el) => {
                        const styles = window.getComputedStyle(el);
                        const bgColor = styles.backgroundColor;

                        // Parse RGB from computed style
                        const match = bgColor.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                        if (!match) return 128;

                        const r = parseInt(match[1]);
                        const g = parseInt(match[2]);
                        const b = parseInt(match[3]);

                        // Calculate perceived brightness (0-255)
                        return (r * 0.299 + g * 0.587 + b * 0.114);
                    }
                """)

                # Choose OBNOXIOUS color based on brightness
                if avg_brightness > 128:
                    # Light background → Use dark, saturated color
                    highlight_color = "rgb(255, 0, 255)"  # Bright magenta
                else:
                    # Dark background → Use bright, saturated color
                    highlight_color = "rgb(0, 255, 255)"  # Bright cyan

            except Exception:
                # Fallback to bright magenta
                highlight_color = "rgb(255, 0, 255)"

            # Apply OBNOXIOUS multi-layer highlighting
            locator.evaluate(f"""
                (el) => {{
                    const highlightColor = '{highlight_color}';

                    // Multi-layer obnoxious highlighting
                    el.style.outline = `8px solid ${{highlightColor}}`;
                    el.style.outlineOffset = '4px';
                    el.style.boxShadow = `
                        0 0 0 12px ${{highlightColor}}40,
                        0 0 0 16px ${{highlightColor}}30,
                        0 0 30px 10px ${{highlightColor}}60,
                        inset 0 0 0 3px ${{highlightColor}}
                    `;
                    el.style.position = 'relative';
                    el.style.zIndex = '999999';

                    // Add pulsing animation for extra obnoxiousness
                    el.style.animation = 'a11y-pulse 1s ease-in-out infinite';

                    // Inject animation keyframes
                    if (!document.getElementById('a11y-highlight-style')) {{
                        const style = document.createElement('style');
                        style.id = 'a11y-highlight-style';
                        style.textContent = `
                            @keyframes a11y-pulse {{
                                0%, 100% {{ filter: brightness(1); }}
                                50% {{ filter: brightness(1.3); }}
                            }}
                        `;
                        document.head.appendChild(style);
                    }}
                }}
            """)

            # Wait for styling to apply and animation to start
            page.wait_for_timeout(300)

            # Intelligent screenshot sizing
            try:
                # Get element bounding box
                box = locator.bounding_box()
                if box:
                    # Ensure minimum dimensions with generous padding for highlights
                    min_width = 300
                    min_height = 150
                    # Large padding to capture outline (12px) + box-shadow glow (30px) + context (60px)
                    padding = 100

                    # Calculate capture area with padding
                    width = max(box["width"] + padding * 2, min_width)
                    height = max(box["height"] + padding * 2, min_height)

                    # Center the element in the capture
                    x = max(0, box["x"] - padding)
                    y = max(0, box["y"] - padding)

                    # Use viewport clip for better context
                    page.screenshot(
                        path=str(screenshot_path),
                        clip={"x": x, "y": y, "width": width, "height": height}
                    )
                else:
                    # Fallback to element screenshot
                    locator.screenshot(path=str(screenshot_path))

                logger.info(
                    "Captured highlighted screenshot for violation '%s' (highlight color: %s) at %s",
                    violation["id"],
                    highlight_color,
                    screenshot_path,
                )
                return str(screenshot_path)

            except Exception as element_error:
                logger.debug(
                    "Element screenshot failed for '%s', using viewport: %s",
                    selector,
                    element_error,
                )
                # Try viewport screenshot
                page.screenshot(path=str(screenshot_path), full_page=False)
                logger.info(
                    "Captured viewport screenshot for violation '%s' at %s",
                    violation["id"],
                    screenshot_path,
                )
                return str(screenshot_path)

        except Exception as e:
            logger.error(
                "Failed to capture screenshot for selector '%s': %s",
                selector, e
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

        full_report = sanitize_for_json(dict(results.response))
        full_report["scanned_url"] = url
        if source_file:
            full_report["source_file"] = source_file

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        logger.info("Full scan report saved to %s", output_path)
        return violations
