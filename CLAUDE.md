# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a containerized accessibility scanner that uses Playwright and axe-core to detect WCAG violations in static websites. The project follows a Docker-first architecture with intelligent caching and comprehensive security hardening.

## Essential Commands

### Environment Setup
```bash
make install               # Create venv and install dev dependencies
# OR:
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Core Development Workflow
```bash
# Build cached Docker image (run after dependency changes)
make docker-prepare
python -m scanner.container.runner prepare

# Run end-to-end scan
make scan-local
python -m scanner.container.runner run

# Start API server for manual testing
make serve
python -m scanner.container.runner serve --port 8008
```

### Testing
```bash
# Fast unit tests (skip browser tests)
pytest -q -k "not test_playwright_axe_service"

# Full integration tests in Docker
make integration
python -m scanner.container.integration

# Reporting system smoke test
make test-reporting
./scripts/test_reporting.sh
```

### Code Quality
```bash
black src tests           # Format code
ruff check src tests      # Lint code
ruff check src tests --fix  # Auto-fix lint issues
```

### Cleanup
```bash
make clean               # Remove all data artifacts
rm -rf data/scan data/results data/unzip data/reports
```

## Architecture Overview

The system follows a **three-tier containerized architecture**:

### 1. Container Orchestration Layer
- **ContainerManager** (`src/scanner/container/manager.py`) - Docker SDK integration with intelligent caching
- **Container Runner** (`src/scanner/container/runner.py`) - CLI interface for prepare/run/serve commands
- Uses cached images `a11y-scanner-cache:<hash>` for fast iteration

### 2. Scanning Pipeline Layer
- **Pipeline** (`src/scanner/pipeline.py`) - Orchestrates the complete scanning workflow
- **Services Layer** - Modular services:
  - `ZipService` - Secure archive extraction with Zip Slip protection
  - `HtmlDiscoveryService` - HTML file enumeration
  - `HttpService` - Local HTTP server for extracted content
  - `PlaywrightAxeService` - Browser automation with axe-core

### 3. Reporting & API Layer
- **FastAPI Server** (`src/scanner/web/server.py`) - REST API endpoints
- **Jinja Reporting** (`src/scanner/reporting/jinja_report.py`) - HTML report generation
- **Settings** (`src/scanner/core/settings.py`) - Centralized configuration

## Key Architectural Patterns

### Container-Only Execution
- **CRITICAL**: All scans must run inside Docker containers
- Container guard: `A11Y_SCANNER_IN_CONTAINER=1` environment check
- Direct `python -m scanner.main` calls will abort

### Service Layer Pattern
- Business logic separated into modular services in `src/scanner/services/`
- Pipeline orchestrates services via dependency injection
- Settings centralized in `src/scanner/core/settings.py`

### Performance Optimizations
- **Browser Reuse**: Single Playwright browser instance across all scans using context managers
- **Element Screenshots**: Focused violation capture vs full-page
- **Smart Caching**: Container images cached by content hash

### Security Features
- **Zip Slip Protection**: Path validation preventing directory traversal
- **API Hardening**: Upload limits (100MB), MIME validation, proper error codes
- **Rootless Compatible**: Works with Podman user namespace remapping

## Project Structure

```
src/scanner/              # Main application code
├── container/           # Docker orchestration and caching
├── services/            # Core business logic services
├── web/                # FastAPI server and endpoints
├── reporting/          # HTML report generation
├── core/               # Settings and logging utilities
└── templates/          # Jinja2 report templates

tests/                  # Unit and integration tests
data/                   # Runtime artifacts (gitignored)
├── unzip/             # Input ZIP archives
├── scan/              # Temporary working directory
├── results/           # JSON artifacts and screenshots
└── reports/           # Generated HTML reports
```

## Important Implementation Details

### Browser Lifecycle Management
- Use `with PlaywrightAxeService():` for browser reuse across scans
- Pipeline implements context manager pattern for performance
- Backward compatible with single-use mode

### Settings and Configuration
- All paths relative to current working directory
- Environment variables override defaults in Docker
- Settings object centralizes filesystem paths, ports, and feature flags

### Container Permissions
- System supports rootless Podman with user namespace remapping
- Data directories pre-created with 777 permissions for compatibility
- Container files may have remapped UIDs on host (e.g., 100999)

### JSON Artifact Schema
- Core fields: `scanned_url`, `source_file`, `violations`, `timestamp`
- Maintain backward compatibility for downstream consumers
- Screenshots linked relative to `data/results/`

## Testing Strategy

### Unit Tests (`tests/`)
- 30+ tests covering all core services and utilities
- Mock external dependencies (Docker, Playwright)
- Coverage reports in `htmlcov/`

### Integration Tests
- Golden file validation using `tests/assets/html_sets/`
- End-to-end container testing via `scanner.container.integration`
- API testing with FastAPI TestClient

### Test Categories
- Service layer tests (zip, HTTP, HTML discovery, Playwright)
- Pipeline orchestration tests
- API endpoint tests (validation, error handling, security)

## Development Guidelines

### Code Style
- Python 3.10+ with comprehensive type hints
- Four-space indentation with `black` formatting
- Lowercase modules with underscores, PascalCase classes
- Logging via `scanner.core.logging_setup`

### When Adding Features
- Place reusable behavior in `scanner/services/`
- Keep `Pipeline` focused on orchestration
- Thread new configuration through `Settings`
- Ensure JSON artifacts stay backward compatible

### Before Submitting PRs
- Ensure unit tests pass locally
- Run Docker integration suite if scanning/container code changed
- Format with `black` and lint with `ruff`
- Update documentation and CHANGELOG as needed

## API Endpoints

- `POST /api/scan/zip` - Upload and scan ZIP archives
- `POST /api/scan/url` - Scan live URLs
- `GET /reports/latest.html` - View consolidated report
- `GET /healthz` - Health check

## Debugging Tips

- **Playwright failures**: Ensure `docker-prepare` run after dependency updates
- **Missing artifacts**: Check `data/results` directory for JSON/screenshots
- **Permission issues**: Use `make clean` to reset data directories
- **Container issues**: Verify Docker access with `docker ps` outside repo

## Scripts and Helpers

- `./scripts/create_test_site.sh` - Create sample site for testing
- `./scripts/test_reporting.sh` - Reporting system smoke test
- `scan_live_site.py` - Standalone script for live site scanning