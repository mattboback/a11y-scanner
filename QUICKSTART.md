# A11y Scanner - Quick Start Guide

## Installation

```bash
# Clone the repo
git clone https://github.com/mattboback/a11y-scanner.git
cd a11y-scanner

# Install dependencies
make install

# Build Docker image
make docker-prepare
```

## Scanning Your Site

### Option 1: Scan Static Site (ZIP file)

1. **Prepare your site** - Create a ZIP file of your HTML files:
   ```bash
   # Put your HTML files in a folder, then zip it
   zip -r my-site.zip my-site/
   ```

2. **Place the ZIP in the input directory**:
   ```bash
   cp my-site.zip data/unzip/site.zip
   ```

3. **Run the scan**:
   ```bash
   make scan-local
   ```

4. **View results**:
   - Open `data/reports/latest.html` in your browser
   - Screenshots and violations are in `data/results/`

### Option 2: Scan Live Website

```bash
# Set environment variables
export A11Y_BASE_URL="https://example.com"
export A11Y_PAGES="/,/about,/contact,/services"

# Run scan
make live-scan
```

Results go to `data/live_results/`

### Option 3: API Server (Programmatic)

```bash
# Start the server (runs in Docker)
make serve

# Upload a ZIP to scan
curl -X POST http://localhost:8008/api/scan/zip \
  -F "file=@my-site.zip"

# View results at
# http://localhost:8008/reports/latest.html
```

## Output Structure

```
data/
├── reports/
│   └── latest.html          ← Open this in your browser
├── results/
│   ├── page1.html.json      ← Raw JSON report
│   ├── page2.html.json
│   ├── violation-*.png      ← Screenshots of violations
│   └── ...
├── unzip/                   ← Your input ZIP goes here
└── scan/                    ← Extracted HTML files
```

## Understanding the Report

**Summary Section:**
- Pages Scanned: Number of HTML files found
- Total Violations: Count of all accessibility issues
- Raw Artifacts: Links to JSON reports

**Violations by Rule:**
- **Critical** (red) - Must fix (WCAG Level A)
- **Serious** (orange) - Should fix (WCAG Level AA)
- **Moderate** (gold) - Nice to fix (best practices)
- **Minor** (yellow) - Low impact items

Each violation shows:
- **Page**: Which file the issue is in
- **Selector**: CSS selector to find the element
- **HTML Snippet**: The problematic code
- **Visual Reference**: Screenshot highlighting the issue

## Docker Requirements

- Docker or Podman installed
- ~2GB RAM
- ~2GB disk space

## Common Issues

**"Must run inside container"**
- API endpoints only work via Docker. Use `make serve` instead of direct curl.

**Missing images in report**
- Screenshots are generated automatically. If missing, check `data/results/` directory.

**Port already in use**
- Edit Makefile or use: `make serve PORT=8080`

## Next Steps

- Fix violations based on the report
- Re-run scans to verify fixes
- Integrate into CI/CD pipeline
- Check axe-core docs via "Documentation →" link in report

---

For detailed documentation, see [README.md](README.md)
