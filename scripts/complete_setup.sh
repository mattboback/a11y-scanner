#!/usr/bin/env bash
# complete_setup.sh - Full project setup and validation

set -e

echo "🚀 a11y-scanner Setup Script"
echo "=============================="
echo ""

# 1. Check Python version
echo "1️⃣  Checking Python version..."
if ! command -v python3.11 &> /dev/null; then
    echo "❌ Python 3.11 not found. Install with: sudo pacman -S python311"
    exit 1
fi
echo "✓ Python 3.11 found"

# 2. Create virtual environment
echo ""
echo "2️⃣  Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  Removing existing .venv..."
    rm -rf .venv
fi
python3.11 -m venv .venv
source .venv/bin/activate
echo "✓ Virtual environment created"

# 3. Install dependencies
echo ""
echo "3️⃣  Installing dependencies..."
pip install --upgrade pip > /dev/null
pip install -e ".[dev]"
echo "✓ Dependencies installed"

# 4. Create missing scripts
echo ""
echo "4️⃣  Creating missing scripts..."
if [ ! -f "scripts/create_test_site.sh" ]; then
    cat > scripts/create_test_site.sh <<'SCRIPT'
#!/usr/bin/env bash
set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
UNZIP_DIR="$DATA_DIR/unzip"
SITE_DIR="$DATA_DIR/site_tmp"
mkdir -p "$UNZIP_DIR" "$SITE_DIR"
cat > "$SITE_DIR/index.html" <<'EOF'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Test</title></head>
<body><h1>Test</h1><img src="logo.png"><p>Content</p></body>
</html>
EOF
cd "$SITE_DIR"
zip -r "$UNZIP_DIR/site.zip" . -q
echo "✓ Created: $UNZIP_DIR/site.zip"
SCRIPT
    chmod +x scripts/create_test_site.sh
    echo "✓ Created scripts/create_test_site.sh"
else
    echo "✓ scripts/create_test_site.sh already exists"
fi

# 5. Fix linting issues
echo ""
echo "5️⃣  Fixing code style..."
black src tests > /dev/null 2>&1
ruff check src tests --fix --quiet || true
echo "✓ Code formatted"

# 6. Run tests
echo ""
echo "6️⃣  Running tests..."
pytest -q -k "not test_playwright_axe_service"
echo "✓ Tests passed"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run: ./update_user_info.sh"
echo "  2. Review and commit changes"
echo "  3. Test Docker: python -m scanner.container.runner prepare"
