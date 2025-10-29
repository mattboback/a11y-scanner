#!/usr/bin/env bash
# Script to create a sample test site for scanning

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
UNZIP_DIR="$DATA_DIR/unzip"
SITE_DIR="$DATA_DIR/site_tmp"

echo "Creating test site..."

# Create directories
mkdir -p "$UNZIP_DIR"
mkdir -p "$SITE_DIR"

# Create sample HTML with accessibility issues
cat > "$SITE_DIR/index.html" <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sample Test Site</title>
  <style>
    .low-contrast { color: #999; background: #f0f0f0; }
  </style>
</head>
<body>
  <h1>Sample Page</h1>
  <img src="logo.png">
  <p class="low-contrast">Low contrast text</p>
  <button>Click me</button>
</body>
</html>
EOF

cat > "$SITE_DIR/about.html" <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>About Page</title>
</head>
<body>
  <h1>About</h1>
  <img src="team.jpg">
  <p>Information about us</p>
</body>
</html>
EOF

# Create ZIP file
cd "$SITE_DIR"
zip -r "$UNZIP_DIR/site.zip" . -q

echo "✓ Created: $UNZIP_DIR/site.zip"
echo "✓ Test site ready for scanning"
