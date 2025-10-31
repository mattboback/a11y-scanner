#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${ROOT_DIR}/.uv-cache}"

echo "==> Working directory: ${ROOT_DIR}"
cd "${ROOT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is not installed. Install it from https://github.com/astral-sh/uv and re-run." >&2
  exit 1
fi

echo "==> Regenerating lockfile"
uv lock

echo "==> Syncing dependencies (respecting lockfile)"
uv sync --frozen --all-extras

echo "==> Running Ruff lint checks"
uv run ruff check src tests

echo "==> Verifying Black formatting"
uv run black --check src tests

echo "==> Running unit tests"
uv run pytest -q

REPORT_HTML="${ROOT_DIR}/data/reports/latest.html"
REPORT_JSON="${ROOT_DIR}/data/reports/latest.json"

if [[ -d "${ROOT_DIR}/data/results" ]]; then
  echo "==> Rebuilding consolidated accessibility report"
  uv run python - <<'PY'
from pathlib import Path
from scanner.reporting.jinja_report import build_report

root = Path(".").resolve()
results = root / "data" / "results"
output = root / "data" / "reports" / "latest.html"
build_report(results, output)
print(f"Report rebuilt at {output}")
PY
else
  echo "==> Skipping report rebuild (no data/results directory)"
fi

if [[ ! -f "${REPORT_HTML}" ]]; then
  echo "==> No HTML report generated. Cleaning stale artifacts."
  rm -f "${REPORT_HTML}" "${REPORT_JSON}"
fi

echo "==> git status"
git -C "${ROOT_DIR}" status -sb

echo "All checks passed. Review the status above before pushing."
