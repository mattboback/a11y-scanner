# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Zip Slip Protection**: Added comprehensive path validation in `ZipService` to prevent directory traversal attacks
  - Validates all archive members before extraction
  - Rejects absolute paths and `..` traversal attempts
  - Added test coverage for malicious zip files
- **API Hardening**: Enhanced security and validation for API endpoints
  - Upload size limit (100 MB) for ZIP file uploads
  - MIME type validation (only accepts application/zip variants)
  - Filename extension validation
  - Empty file detection
  - Better error messages and HTTP status codes (400, 413, 422, 500)
- **API Test Suite**: Comprehensive test coverage for FastAPI endpoints
  - 12 new tests covering health checks, validation, error cases, and success paths
  - Uses FastAPI TestClient for proper integration testing
- **Source File Tracking**: Persists `source_file` field in JSON artifacts
  - Added optional parameter to `PlaywrightAxeService.scan_url()`
  - Pipeline now threads source file path through to saved JSON
  - Improves report context and traceability
- **Features Section**: Added comprehensive features list to README
- **Security Documentation**: Documented security improvements in README

### Changed

- **Browser Reuse**: Refactored `PlaywrightAxeService` for performance
  - Supports context manager pattern (`with PlaywrightAxeService():`)
  - Reuses single browser instance across all scans in a pipeline run
  - Maintains backward compatibility with single-use mode
  - Reduces scan time by eliminating repeated browser startup
- **Element-Level Screenshots**: Improved screenshot capture for violations
  - Now captures focused element screenshots using `locator.screenshot()`
  - Adds visual highlight (red outline) to violating elements
  - Falls back to full-page screenshot if element capture fails
  - Screenshots are clearer and more actionable
- **Pipeline Optimization**: Updated pipeline to use browser reuse via context manager
- **Datetime Handling**: Fixed deprecated `datetime.utcnow()` in reporting module
  - Now uses `datetime.now(timezone.utc)` for timezone-aware timestamps
  - Eliminates deprecation warnings in Python 3.13+
- **API Response Format**: Enhanced API responses with more metadata
  - Added `pages_scanned`, `urls_scanned`, `scanned_urls` fields
  - Added descriptive `message` field for user-friendly feedback
  - Better error handling with try-catch blocks and specific exceptions

### Fixed

- **Duplicate Configuration**: Removed duplicate imports and configuration constants in `server.py`
- **HttpUrl Handling**: Fixed Pydantic HttpUrl object handling in URL scan endpoint
  - Properly converts HttpUrl objects to strings before processing
- **Import Cleanup**: Fixed duplicate and missing imports across modules

### Removed

- **Build Artifacts**: Removed tracked egg-info directories from repository
  - Deleted `src/python_scanner.egg-info/`
  - Deleted `src/a11y_scanner.egg-info/`
  - These are now properly ignored via `.gitignore`

### Security

- **CVE Prevention**: Zip Slip vulnerability (CWE-22) prevention in archive extraction
- **Input Validation**: Comprehensive validation of user uploads and URL inputs
- **Size Limits**: Protection against resource exhaustion via oversized uploads

## [0.4.0] - Previous Release

### Added

- Docker SDK-based container runner with cached image support
- FastAPI server for long-running API mode
- Consolidated HTML reporting with Jinja2 templates
- Integration test suite with golden file validation
- GitHub Actions CI with linting and testing

### Changed

- Migrated from subprocess-based Playwright to native Python API
- Improved logging and error handling throughout codebase

---

## Contributing

When adding entries to this changelog:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Write in imperative mood ("Add feature" not "Added feature")
- Link to relevant issues/PRs when applicable
- Keep entries concise but descriptive
- Update the Unreleased section with each PR