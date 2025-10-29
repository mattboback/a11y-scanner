# Golden Testing Guide

A11y Scanner includes a golden testing framework for regression testing across multiple website themes. This document explains how to use the automated testing system.

## Overview

Golden tests are baseline snapshots of accessibility scan results. They allow you to:

- **Detect Regressions**: Automatically identify when scanner behavior changes
- **Version Control Results**: Track how accessibility findings evolve
- **Compare Sites**: See how different themes perform
- **Generate Reports**: Create HTML accessibility reports for review

## Test Sites

Three example websites are included for testing:

1. **Charitize** (Charity theme) - 1.8 MB
2. **Flat** (Flat design theme) - 841 KB
3. **play-tailwind** (Tailwind CSS theme) - 1.9 MB

These are stored as ZIP files in the `tests/` directory (not committed to git).

## Quick Start

### 1. Initial Setup

```bash
# Install dependencies
make install

# Prepare Docker image (one-time setup)
make docker-prepare
```

### 2. Generate Golden Test Files

Generate baseline golden files from the test websites:

```bash
# Generate golden test files for all sites
make golden-generate

# Or run specific sites
uv run python scripts/run_golden_tests.py --generate --sites Charitize,Flat
```

This will:
- Extract each ZIP file to `tests/assets/html_sets/SiteName/`
- Run the accessibility scanner on each
- Save baseline results to `tests/assets/html_sets/SiteName/golden_results/report.json`
- Generate HTML reports in `data/reports/`

### 3. Run Regression Tests

After making changes to the scanner, verify nothing broke:

```bash
# Run regression tests (compare with golden files)
make golden-test

# Or compare only (skip HTML report generation)
make golden-compare
```

This will:
- Rescan all sites
- Compare results with golden files
- Show any differences
- Report overall pass/fail status

## Usage

### Command Line Options

```bash
# Generate new golden files
python scripts/run_golden_tests.py --generate

# Run regression tests (default)
python scripts/run_golden_tests.py

# Compare only (don't generate reports)
python scripts/run_golden_tests.py --compare-only

# Test specific sites
python scripts/run_golden_tests.py --sites Charitize,Flat

# Without Docker (local Python)
python scripts/run_golden_tests.py --no-docker
```

### Make Targets

```bash
# Generate golden files
make golden-generate

# Run regression tests
make golden-test

# Compare only
make golden-compare

# Show all available targets
make help
```

## Output

### Golden Test Files

Located at: `tests/assets/html_sets/SiteName/golden_results/report.json`

Contains a JSON array of accessibility scan results for each page, sorted by URL.

### HTML Reports

Located at: `data/reports/`

- `latest.html` - Most recent scan report
- `SiteName_YYYYMMDD_HHMMSS.html` - Timestamped reports for each site

Example:
```
data/reports/
├── latest.html
├── Charitize_20241029_143000.html
├── Flat_20241029_143500.html
└── play-tailwind_20241029_144000.html
```

## Workflow

### Initial Setup

```bash
# 1. Install and prepare
make install
make docker-prepare

# 2. Generate golden baseline
make golden-generate

# 3. Review reports
open data/reports/latest.html
```

### After Code Changes

```bash
# 1. Run regression tests
make golden-test

# 2. If tests fail:
#    - Review the diff output
#    - Verify if it's expected
#    - Update golden files if intentional:
make golden-generate
```

### Continuous Integration

Add to CI/CD pipeline:

```bash
# Run regression tests
make golden-test

# Exits with 0 if all tests pass, 1 if any fail
```

## Understanding Results

### Test Output

```
--- Processing: Charitize ---
✓ Extracted Charitize-1.0.0.zip to tests/assets/html_sets/Charitize
✓ Running scan for Charitize in Docker...
✓ Scan completed for Charitize
✓ Generated golden file: tests/assets/html_sets/Charitize/golden_results/report.json
  - 42 page(s) scanned
```

### Golden File Format

```json
[
  {
    "scanned_url": "http://localhost:3000/index.html",
    "violations": [...],
    "passes": [...],
    ...
  },
  ...
]
```

### Comparing Results

If scan results differ from golden:

```
✗ Charitize differs from golden file
Diff (first 50 lines):
  --- golden
  +++ actual
  @ violations.0.id @
  - "color-contrast"
  + "color-contrast-enhanced"
```

If differences are expected, regenerate golden files:

```bash
make golden-generate
```

## Troubleshooting

### Problem: "No test sites found"

**Cause**: ZIP files not in `tests/` directory

**Solution**: Ensure the following exist:
```bash
ls -l tests/*.zip
# Should show:
# Charitize-1.0.0.zip
# Flat-1.0.0.zip
# play-tailwind-1.0.0.zip
```

### Problem: Scan timeout

**Cause**: Docker container taking too long

**Solution**:
```bash
# Run with longer timeout
python scripts/run_golden_tests.py --no-docker
```

### Problem: Golden files not updating

**Cause**: Using `--compare-only` flag

**Solution**:
```bash
# Remove --compare-only and use --generate
make golden-generate
```

## Integration with Existing Tests

The golden testing framework works alongside unit/integration tests:

```bash
# Run all tests
make test                    # Unit + integration (Docker)
make golden-test            # Golden regression tests
make test && make golden-test  # Both
```

## File Structure

```
project_root/
├── tests/
│   ├── Charitize-1.0.0.zip          # Test site ZIP
│   ├── Flat-1.0.0.zip               # Test site ZIP
│   ├── play-tailwind-1.0.0.zip      # Test site ZIP
│   └── assets/
│       └── html_sets/               # Extracted test sites
│           ├── Charitize/
│           │   ├── [extracted files]
│           │   └── golden_results/
│           │       └── report.json   # Golden baseline
│           ├── Flat/
│           │   ├── [extracted files]
│           │   └── golden_results/
│           │       └── report.json
│           └── play-tailwind/
│               ├── [extracted files]
│               └── golden_results/
│                   └── report.json
├── data/
│   ├── unzip/               # Temp extraction location
│   ├── results/             # Raw scan results
│   ├── reports/             # HTML reports
│   └── scan/                # Scan data
└── scripts/
    └── run_golden_tests.py  # Test runner script
```

## Notes

- Test ZIPs are in `.gitignore` - they are for local testing only
- Golden files are committed to git for regression detection
- HTML reports are generated at `data/reports/` (not committed)
- Tests run in Docker by default (Docker and Docker SDK required)
- Tests take 5-15 minutes per site depending on size

## Contributing

When adding new test sites:

1. Add ZIP file to `tests/` directory
2. Run golden generation: `make golden-generate`
3. Commit golden files: `git add tests/assets/html_sets/*/golden_results/`
4. Add to this documentation

## See Also

- [Integration Test Suite](src/scanner/container/integration.py)
- [Jinja Report Generator](src/scanner/reporting/jinja_report.py)
- [Main Scanning Pipeline](src/scanner/container/main.py)
