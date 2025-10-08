#!/usr/bin/env bash
set -euo pipefail

# Rebuild all golden files to match the current raw per-page reports contract:
# equivalent to: jq -s 'sort_by(.scanned_url)' data/results/*.json

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
ASSETS_DIR="$ROOT/tests/assets/html_sets"
DATA_DIR="$ROOT/data"
UNZIP_DIR="$DATA_DIR/unzip"
RESULTS_DIR="$DATA_DIR/results"

echo "--- Updating golden files ---"

# Make sure the Playwright image is present at least once
python - <<'PY'
from scanner.container.manager import ContainerManager, find_project_root
root = find_project_root()
m = ContainerManager(project_root=root)
if hasattr(m, "ensure_image"):
    m.ensure_image()
else:
    m.ensure_base_image()
print("[prep] Base image ensured.")
PY

for case_dir in "$ASSETS_DIR"/*; do
    [ -d "$case_dir" ] || continue
    name="$(basename "$case_dir")"
    echo -e "\n--- Case: $name ---"

    # Clean data dirs
    rm -rf "$UNZIP_DIR" "$RESULTS_DIR" "$DATA_DIR/scan"
    mkdir -p "$UNZIP_DIR" "$RESULTS_DIR" "$DATA_DIR/scan"

    # Zip inputs (exclude golden_results)
    (cd "$case_dir" && zip -r "$UNZIP_DIR/site.zip" . -x "golden_results/*" >/dev/null)

    # Run scanner container
    python -m scanner.container.runner run >/dev/null

    # Aggregate raw reports and write golden
    GOLDEN_DIR="$case_dir/golden_results"
    mkdir -p "$GOLDEN_DIR"

    if ls "$RESULTS_DIR"/*.json >/dev/null 2>&1; then
        # requires jq
        jq -s 'sort_by(.scanned_url)' "$RESULTS_DIR"/*.json >"$GOLDEN_DIR/report.json"
    else
        echo "[]" >"$GOLDEN_DIR/report.json"
    fi

    echo "Updated: $GOLDEN_DIR/report.json"
done

echo -e "\n--- ✅ Golden files updated ---"
