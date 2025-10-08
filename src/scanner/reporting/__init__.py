"""Reporting module for a11y_scanner.

This module provides functionality to generate HTML reports from accessibility
scan results. The reports are generated using Jinja2 templates and include:
- Summary statistics
- Grouped violations by rule
- Screenshots of violations
- Links to raw JSON data

Main function:
- build_report: Generate HTML report from JSON scan results
"""

from .jinja_report import ReportModel, build_report, validate_report_json

__all__ = ["build_report", "validate_report_json", "ReportModel"]
