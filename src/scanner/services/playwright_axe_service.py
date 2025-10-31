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
        # Tunables for screenshot sizing
        try:
            self._shot_scale = float(os.environ.get("A11Y_SCREENSHOT_SCALE", "2"))
        except ValueError:
            self._shot_scale = 2.0
        self._shot_min_w = int(os.environ.get("A11Y_SCREENSHOT_MIN_WIDTH", "300"))
        self._shot_min_h = int(os.environ.get("A11Y_SCREENSHOT_MIN_HEIGHT", "200"))

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
                avg_brightness = locator.evaluate(r"""
                    (el) => {
                        const styles = window.getComputedStyle(el);
                        const bgColor = styles.backgroundColor;
                        const match = bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
                        if (!match) return 255; // assume light background
                        const r = parseInt(match[1]);
                        const g = parseInt(match[2]);
                        const b = parseInt(match[3]);
                        return (r * 0.299 + g * 0.587 + b * 0.114);
                    }
                """)

                # Vibrant contrasting color for strong visibility
                highlight_color = "#00ffff" if avg_brightness <= 128 else "#ff00ff"
            except Exception:
                highlight_color = "#ff00ff"

            # Compute a visible rectangle in viewport coordinates (fallback to nearest sized ancestor)
            rect = locator.evaluate(
                """
                (el) => {
                    let n = el;
                    for (let i = 0; i < 5 && n; i++) {
                        const r = n.getBoundingClientRect();
                        if (r && r.width >= 4 && r.height >= 4) {
                            return { left: r.left, top: r.top, width: r.width, height: r.height };
                        }
                        n = n.parentElement;
                    }
                    const r = el.getBoundingClientRect();
                    return { left: r.left, top: r.top, width: Math.max(4, r.width), height: Math.max(4, r.height) };
                }
                """
            )

            # Add an overlay outside clipping contexts so it's always visible
            page.evaluate(
                """
                ({ rect, color, label }) => {
                    const id = 'a11y-highlight-overlay';
                    const bid = 'a11y-highlight-badge';
                    const mk = (tag, id) => { let el = document.getElementById(id); if (!el) { el = document.createElement(tag); el.id = id; document.body.appendChild(el);} return el; };
                    const el = mk('div', id);
                    Object.assign(el.style, {
                        position: 'fixed',
                        left: `${rect.left}px`,
                        top: `${rect.top}px`,
                        width: `${rect.width}px`,
                        height: `${rect.height}px`,
                        outline: `8px solid ${color}`,
                        boxShadow: `0 0 0 14px ${color}40, 0 0 28px 10px ${color}80`,
                        borderRadius: '6px',
                        pointerEvents: 'none',
                        zIndex: '2147483647',
                        transition: 'none'
                    });
                    const badge = mk('div', bid);
                    badge.textContent = label || '';
                    Object.assign(badge.style, {
                        position: 'fixed',
                        left: `${rect.left}px`,
                        top: `${Math.max(0, rect.top - 24)}px`,
                        background: color,
                        color: '#000',
                        font: '12px/1.2 -apple-system, system-ui, Segoe UI, Roboto, Arial',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        pointerEvents: 'none',
                        zIndex: '2147483647',
                        boxShadow: `0 2px 8px ${color}80`
                    });
                }
                """,
                {"rect": rect, "color": highlight_color, "label": violation.get("id")},
            )

            # Wait for styling to apply and animation to start
            page.wait_for_timeout(300)

            # Intelligent screenshot sizing
            try:
                # Get element bounding box in viewport coordinates
                box = locator.bounding_box()
                if box:
                    vw = page.viewport_size["width"] if page.viewport_size else 1280
                    vh = page.viewport_size["height"] if page.viewport_size else 720

                    # Desired capture is element size times configured scale
                    desired_w = max(self._shot_min_w, box["width"] * self._shot_scale)
                    desired_h = max(self._shot_min_h, box["height"] * self._shot_scale)

                    # Clamp to viewport
                    width = min(desired_w, vw - 2)
                    height = min(desired_h, vh - 2)

                    # Center around element
                    cx = box["x"] + box["width"] / 2
                    cy = box["y"] + box["height"] / 2
                    x = max(0, min(cx - width / 2, vw - width))
                    y = max(0, min(cy - height / 2, vh - height))

                    page.screenshot(
                        path=str(screenshot_path),
                        clip={
                            "x": float(x),
                            "y": float(y),
                            "width": float(width),
                            "height": float(height),
                        },
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
            finally:
                # Clean up overlays regardless of capture path
                try:
                    page.evaluate(
                        "() => { ['a11y-highlight-overlay','a11y-highlight-badge'].forEach(id => { const n = document.getElementById(id); if (n) n.remove(); }); }"
                    )
                except Exception:
                    pass

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

        full_report = sanitize_for_json(dict(results.response))
        full_report["scanned_url"] = url
        if source_file:
            full_report["source_file"] = source_file

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        logger.info("Full scan report saved to %s", output_path)
        return violations
