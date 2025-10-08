#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
UNZIP_DIR="$ROOT_DIR/data/unzip"
TMP_DIR="$UNZIP_DIR/site_tmp"
ZIP_PATH="$UNZIP_DIR/site.zip"

mkdir -p "$TMP_DIR"

cat >"$TMP_DIR/index.html" <<'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Sample A11y Site</title>
    <style>
      .low-contrast-text { color: #999; background: #888; }
    </style>
  </head>
  <body>
    <h1>Sample Page</h1>
    <img src="logo.png">
    <p class="low-contrast-text">Low contrast text</p>
  </body>
</html>
HTML

echo "Zipping sample site to $ZIP_PATH"
rm -f "$ZIP_PATH"
(cd "$TMP_DIR" && zip -r "$ZIP_PATH" . >/dev/null)

echo "✅ Created $ZIP_PATH"
