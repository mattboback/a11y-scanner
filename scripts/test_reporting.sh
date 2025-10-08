#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"

PYTHON="${PYTHON:-python}"

echo "Building local report from test_data/results -> test_data/reports/test_report.html"

$PYTHON - <<'PY'
from pathlib import Path
from scanner.reporting.jinja_report import build_report
base = Path('test_data')
results = base / 'results'
out = base / 'reports' / 'test_report.html'
out.parent.mkdir(parents=True, exist_ok=True)
res = build_report(results, out, title='Test Accessibility Report')
print('✅ Wrote', res.resolve())
PY

