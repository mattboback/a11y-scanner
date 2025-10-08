from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import (ChoiceLoader, Environment, FileSystemLoader, PackageLoader,
                    TemplateNotFound, select_autoescape)

logger = logging.getLogger(__name__)


@dataclass
class Occurrence:
    url: str

    source_file: str | None

    selector: str | None

    html_snippet: str | None

    screenshot_path: str | Path | None

    screenshot_filename: str | None = None

    def __post_init__(self):
        """Extract filename from screenshot_path for template use"""

        if self.screenshot_path:
            try:
                self.screenshot_filename = Path(self.screenshot_path).name

            except Exception:
                self.screenshot_filename = str(self.screenshot_path)


@dataclass
class RuleGroup:
    id: str

    impact: str | None = None

    description: str | None = None

    help: str | None = None

    helpUrl: str | None = None

    count: int = 0

    occurrences: List[Occurrence] = field(default_factory=list)

    @property
    def impact_class(self) -> str:
        """Return CSS class based on impact level"""

        if not self.impact:
            return "impact-unknown"

        return f"impact-{self.impact.lower()}"


@dataclass
class ReportModel:
    title: str

    generated_at: str

    pages_scanned: int

    total_violations: int

    by_rule: List[RuleGroup]

    raw_files: List[str]

    def validate(self) -> bool:
        """Validate the report model has reasonable values"""

        if self.pages_scanned < 0:
            return False

        if self.total_violations < 0:
            return False

        if len(self.by_rule) > 0 and self.total_violations == 0:
            return False

        return True


def _iter_reports(results_dir: Path):
    """Generator that yields filename and parsed JSON for each report file"""

    if not results_dir.exists():
        logger.warning("Results directory does not exist: %s", results_dir)

        return

    for p in sorted(results_dir.glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)

                yield p.name, data

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", p, e)

            continue

        except Exception as e:
            logger.error("Error reading %s: %s", p, e)

            continue


def _impact_sort_key(impact: Optional[str], rule_id: str) -> tuple:
    """Sort key for rule groups: critical > serious > moderate > minor > unknown"""

    impact_order = {
        "critical": 0,
        "serious": 1,
        "moderate": 2,
        "minor": 3,
        "unknown": 4,
        None: 5,
    }

    return (impact_order.get(impact.lower() if impact else None, 5), rule_id)


def _build_model(results_dir: Path, title: str) -> ReportModel:
    """Build the report model from JSON files in the results directory"""

    groups: Dict[str, RuleGroup] = {}

    pages_scanned = 0

    total_violations = 0

    raw_files: List[str] = []

    for fname, report in _iter_reports(results_dir):
        raw_files.append(fname)

        pages_scanned += 1

        violations = (report or {}).get("violations", [])

        for v in violations:
            total_violations += 1

            rid = v.get("id") or "unknown"

            # Create or get existing rule group

            if rid not in groups:
                groups[rid] = RuleGroup(
                    id=rid,
                    impact=v.get("impact"),
                    description=v.get("description"),
                    help=v.get("help"),
                    helpUrl=v.get("helpUrl"),
                )

            grp = groups[rid]

            # Extract violation details

            selector = None

            html_snippet = None

            nodes = v.get("nodes") or []

            if nodes:
                n0 = nodes[0]

                target = n0.get("target") or []

                selector = target[0] if len(target) > 0 else None

                html_snippet = n0.get("html")

            # Get source_file from report if available

            source_file = None

            if "source_file" in report:
                source_file = report["source_file"]

            elif "scanned_url" in report and "file://" in str(report["scanned_url"]):
                # Try to extract filename from file:// URL

                try:
                    url_parts = str(report["scanned_url"]).split("file://")[-1]

                    source_file = Path(url_parts).name

                except Exception:
                    source_file = None

            # Create occurrence with screenshot handling

            screenshot_path = v.get("screenshot_path")

            occ = Occurrence(
                url=report.get("scanned_url") or report.get("url") or "",
                source_file=source_file,
                selector=selector,
                html_snippet=html_snippet,
                screenshot_path=screenshot_path,
            )

            grp.count += 1

            grp.occurrences.append(occ)

    # Sort rule groups by impact (critical first) then by ID

    sorted_groups = sorted(
        groups.values(), key=lambda g: _impact_sort_key(g.impact, g.id)
    )

    model = ReportModel(
        title=title,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
        pages_scanned=pages_scanned,
        total_violations=total_violations,
        by_rule=sorted_groups,
        raw_files=raw_files,
    )

    return model


def _get_jinja_env() -> Environment:
    """

    Create a Jinja environment that works both when installed as a package

    and when running from a source checkout.

    """

    # Source-tree templates path: scanner/templates

    src_templates_dir = Path(__file__).resolve().parent.parent / "templates"

    loader = ChoiceLoader(
        [
            # Prefer installed package resources (editable or built installs)
            PackageLoader("scanner", "templates"),
            # Fallback to filesystem loader in a source tree
            FileSystemLoader(str(src_templates_dir)),
        ]
    )

    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    return env


def build_report(
    results_dir: Path,
    output_html: Path,
    title: str = "Accessibility Report",
    overwrite: bool = True,
) -> Path:
    """Aggregate JSON artifacts in ``results_dir`` and render a single HTML report.


    Args:

        results_dir: Directory containing JSON scan results

        output_html: Path where HTML report will be saved

        title: Title for the report

        overwrite: Whether to overwrite existing report (default: True)


    Returns:

        Path to the generated HTML report


    Raises:

        FileNotFoundError: If template cannot be found

        PermissionError: If cannot write to output path

        RuntimeError: If report generation fails

    """

    if not overwrite and output_html.exists():
        logger.info(
            "Report already exists and overwrite=False, skipping: %s", output_html
        )

        return output_html

    results_dir = results_dir.resolve()

    output_html.parent.mkdir(parents=True, exist_ok=True)

    try:
        model = _build_model(results_dir, title)

        # Validate model

        if not model.validate():
            logger.warning("Generated report model failed validation")

        # Set up Jinja2 environment

        env = _get_jinja_env()

        # Load template

        try:
            tpl = env.get_template("a11y_report.html.j2")

        except TemplateNotFound as e:
            raise FileNotFoundError(f"Template not found: {e}") from e

        # Render template
        # Compute a relative web path from the report file location to the results directory
        # so screenshots work when opening the report directly from the filesystem
        # (e.g., file:///.../data/reports/latest.html -> ../results/*).
        base_dir = output_html.parent.resolve()
        rel = os.path.relpath(results_dir, base_dir)
        # Normalize to POSIX-style separators for browsers
        results_web_base = rel.replace(os.sep, "/")

        html = tpl.render(model=model, results_web_base=results_web_base)

        # Write to file

        try:
            output_html.write_text(html, encoding="utf-8")

            logger.info("HTML report generated: %s", output_html)

        except PermissionError as e:
            raise PermissionError(f"Cannot write to {output_html}: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Failed to write report: {e}") from e

        return output_html

    except Exception as e:
        logger.error("Failed to build report: %s", e)

        raise RuntimeError(f"Report generation failed: {e}") from e


def validate_report_json(json_path: Path) -> bool:
    """Validate that a JSON file has the expected structure for reporting"""

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for required fields

        if not isinstance(data, dict):
            return False

        # Should have either violations array or be empty

        if "violations" in data and not isinstance(data["violations"], list):
            return False

        # Should have URL info

        if "scanned_url" not in data and "url" not in data:
            return False

        return True

    except Exception:
        return False


if __name__ == "__main__":
    # Manual debug: build a report from ./data/results into ./data/reports/latest.html

    logging.basicConfig(level=logging.INFO)

    base = Path(".")

    results_dir = base / "data" / "results"

    out = base / "data" / "reports" / "latest.html"

    if not results_dir.exists() or not any(results_dir.glob("*.json")):
        print(f"Warning: No JSON files found in {results_dir}")

    try:
        result_path = build_report(results_dir, out)

        print(f"✅ Report successfully generated: {result_path}")

    except Exception as e:
        print(f"❌ Report generation failed: {e}")

        sys.exit(1)
