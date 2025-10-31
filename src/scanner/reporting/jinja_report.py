from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    TemplateNotFound,
    select_autoescape,
)

logger = logging.getLogger(__name__)

IMPACT_LEVELS = ("critical", "serious", "moderate", "minor", "unknown")


@dataclass
class Occurrence:
    url: str

    source_file: str | None

    selector: str | None

    html_snippet: str | None

    screenshot_path: str | Path | None

    screenshot_filename: str | None = None

    failure_summary: str | None = None

    def __post_init__(self):
        """Extract filename from screenshot_path for template use"""

        if self.screenshot_path:
            try:
                self.screenshot_filename = Path(self.screenshot_path).name

            except Exception:
                self.screenshot_filename = str(self.screenshot_path)

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable representation of this occurrence"""

        path_str = None

        if self.screenshot_path:
            try:
                path_str = str(self.screenshot_path)

            except Exception:
                path_str = self.screenshot_path  # already str / fallback

        return {
            "url": self.url,
            "source_file": self.source_file,
            "selector": self.selector,
            "html_snippet": self.html_snippet,
            "screenshot_path": path_str,
            "screenshot_filename": self.screenshot_filename,
            "failure_summary": self.failure_summary,
        }


@dataclass
class RuleGroup:
    id: str

    impact: str | None = None

    description: str | None = None

    help: str | None = None

    helpUrl: str | None = None

    count: int = 0

    occurrences: list[Occurrence] = field(default_factory=list)

    @property
    def impact_class(self) -> str:
        """Return CSS class based on impact level"""

        if not self.impact:
            return "impact-unknown"

        return f"impact-{self.impact.lower()}"

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of this rule group"""

        return {
            "id": self.id,
            "impact": self.impact,
            "description": self.description,
            "help": self.help,
            "helpUrl": self.helpUrl,
            "count": self.count,
            "occurrences": [occ.to_dict() for occ in self.occurrences],
        }


@dataclass
class PageSummary:
    """Aggregated view of violations per page."""

    label: str

    url: str

    total_violations: int

    impact_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of this page summary"""

        return {
            "label": self.label,
            "url": self.url,
            "total_violations": self.total_violations,
            "impact_counts": dict(self.impact_counts),
        }


@dataclass
class ReportModel:
    title: str

    generated_at: str

    pages_scanned: int

    total_violations: int

    by_rule: list[RuleGroup]

    raw_files: list[str]

    impact_summary: dict[str, int] = field(default_factory=dict)

    page_summaries: list[PageSummary] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate the report model has reasonable values"""

        if self.pages_scanned < 0:
            return False

        if self.total_violations < 0:
            return False

        if len(self.by_rule) > 0 and self.total_violations == 0:
            return False

        return True

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of the report model"""

        page_payload = [page.to_dict() for page in self.page_summaries]

        return {
            "title": self.title,
            "generated_at": self.generated_at,
            "pages_scanned": self.pages_scanned,
            "total_violations": self.total_violations,
            "raw_files": list(self.raw_files),
            "impact_summary": dict(self.impact_summary),
            "rules": [rule.to_dict() for rule in self.by_rule],
            "page_summaries": page_payload,
            "pages": page_payload,
        }


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


def _impact_sort_key(impact: str | None, rule_id: str) -> tuple:
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

    groups: dict[str, RuleGroup] = {}

    pages_scanned = 0

    total_violations = 0

    raw_files: list[str] = []

    impact_summary: defaultdict[str, int] = defaultdict(int)

    page_buckets: dict[str, dict] = {}

    for fname, report in _iter_reports(results_dir):
        raw_files.append(fname)

        pages_scanned += 1

        report = report or {}

        scanned_url = report.get("scanned_url") or report.get("url") or ""

        source_file = None

        if "source_file" in report:
            source_file = report["source_file"]

        elif scanned_url and str(scanned_url).startswith("file://"):
            # Try to extract filename from file:// URL
            try:
                url_parts = str(scanned_url).split("file://")[-1]
                source_file = Path(url_parts).name
            except Exception:
                source_file = None

        violations = report.get("violations") or []

        for violation in violations:
            rid = violation.get("id") or "unknown"

            if rid not in groups:
                groups[rid] = RuleGroup(
                    id=rid,
                    impact=violation.get("impact"),
                    description=violation.get("description"),
                    help=violation.get("help"),
                    helpUrl=violation.get("helpUrl"),
                )

            grp = groups[rid]

            nodes = violation.get("nodes") or []

            if not nodes:
                nodes = [None]

            impact_value = violation.get("impact") or "unknown"

            impact_key = str(impact_value).lower()

            screenshot_path = violation.get("screenshot_path")

            for node in nodes:
                selector = None
                html_snippet = None
                failure_summary = None

                if isinstance(node, dict):
                    target = node.get("target") or []
                    if target:
                        selector = ", ".join(str(t) for t in target)

                    html_snippet = node.get("html")
                    failure_summary = node.get("failureSummary")

                occ = Occurrence(
                    url=scanned_url,
                    source_file=source_file,
                    selector=selector,
                    html_snippet=html_snippet,
                    screenshot_path=screenshot_path,
                    failure_summary=failure_summary,
                )

                grp.count += 1
                grp.occurrences.append(occ)

                total_violations += 1
                impact_summary[impact_key] += 1

                page_key = source_file or scanned_url or fname

                bucket = page_buckets.setdefault(
                    page_key,
                    {
                        "label": source_file or scanned_url or fname,
                        "url": scanned_url,
                        "total": 0,
                        "impact_counts": defaultdict(int),
                    },
                )

                bucket["total"] += 1
                bucket["impact_counts"][impact_key] += 1

    # Sort rule groups by impact (critical first) then by ID

    for grp in groups.values():
        grp.occurrences.sort(
            key=lambda occ: (
                occ.source_file or occ.url or "",
                occ.selector or "",
            )
        )

    sorted_groups = sorted(
        groups.values(), key=lambda g: _impact_sort_key(g.impact, g.id)
    )

    ordered_impact_summary = {
        level: impact_summary.get(level, 0) for level in IMPACT_LEVELS
    }

    page_summaries = sorted(
        (
            PageSummary(
                label=bucket["label"],
                url=bucket["url"],
                total_violations=bucket["total"],
                impact_counts={
                    level: count
                    for level in IMPACT_LEVELS
                    if (count := bucket["impact_counts"].get(level, 0)) > 0
                },
            )
            for bucket in page_buckets.values()
        ),
        key=lambda p: p.total_violations,
        reverse=True,
    )

    model = ReportModel(
        title=title,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        pages_scanned=pages_scanned,
        total_violations=total_violations,
        by_rule=sorted_groups,
        raw_files=raw_files,
        impact_summary=ordered_impact_summary,
        page_summaries=page_summaries,
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
    save_json: bool = True,
    output_json: Path | None = None,
) -> Path:
    """Aggregate JSON artifacts in ``results_dir`` and render a single HTML report.


    Args:

        results_dir: Directory containing JSON scan results

        output_html: Path where HTML report will be saved

        title: Title for the report

        overwrite: Whether to overwrite existing report (default: True)

        save_json: Whether to save a consolidated JSON summary alongside the HTML

        output_json: Optional explicit path for the consolidated JSON summary

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

    output_html = output_html.resolve()

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
        # Compute a relative web path from the report file location
        # to the results directory
        # so screenshots work when opening the report directly from the filesystem
        # (e.g., file:///.../data/reports/latest.html -> ../results/*).
        base_dir = output_html.parent.resolve()
        rel = os.path.relpath(results_dir, base_dir)
        # Normalize to POSIX-style separators for browsers
        results_web_base = rel.replace(os.sep, "/")

        summary_path: Path | None = None
        summary_web_path: str | None = None

        if save_json:
            summary_path = (output_json or output_html.with_suffix(".json")).resolve()
            try:
                summary_rel = os.path.relpath(summary_path, base_dir)
                summary_web_path = summary_rel.replace(os.sep, "/")
            except ValueError:
                # If relpath cannot be computed (different drives),
                # fall back to filename
                summary_web_path = summary_path.name

        model_payload = model.to_dict()
        model_payload["results_dir"] = str(results_dir)
        model_payload["report_path"] = str(output_html)
        if summary_path:
            model_payload["summary_json_path"] = str(summary_path)

        html = tpl.render(
            model=model,
            results_web_base=results_web_base,
            summary_json=summary_web_path,
        )

        # Write to file

        try:
            output_html.write_text(html, encoding="utf-8")

            logger.info("HTML report generated: %s", output_html)

        except PermissionError as e:
            raise PermissionError(f"Cannot write to {output_html}: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Failed to write report: {e}") from e

        if save_json and summary_path:
            try:
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(
                    json.dumps(model_payload, indent=2), encoding="utf-8"
                )
                logger.info("Summary JSON generated: %s", summary_path)

            except PermissionError as e:
                raise PermissionError(f"Cannot write to {summary_path}: {e}") from e

            except Exception as e:
                raise RuntimeError(f"Failed to write summary JSON: {e}") from e

        return output_html

    except Exception as e:
        logger.error("Failed to build report: %s", e)

        raise RuntimeError(f"Report generation failed: {e}") from e


def validate_report_json(json_path: Path) -> bool:
    """Validate that a JSON file has the expected structure for reporting"""

    try:
        with open(json_path, encoding="utf-8") as f:
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
