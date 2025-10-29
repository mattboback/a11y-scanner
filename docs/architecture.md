# Architecture Guide

This document provides a deep dive into the a11y-scanner architecture, including component design, data flow, orchestration patterns, and extension points.

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture Principles](#core-architecture-principles)
3. [Component Layers](#component-layers)
4. [Data Flow](#data-flow)
5. [Container Orchestration](#container-orchestration)
6. [Configuration & Settings](#configuration--settings)
7. [Error Handling & Resilience](#error-handling--resilience)
8. [Performance Considerations](#performance-considerations)
9. [Extending the Scanner](#extending-the-scanner)
10. [Testing Architecture](#testing-architecture)
11. [Security Considerations](#security-considerations)
12. [Debugging & Troubleshooting](#debugging--troubleshooting)
13. [Future Enhancements](#future-enhancements)

---

## System Overview

The a11y-scanner is a **containerized, multi-layer Python application** that automates accessibility auditing of static websites using:

- **Playwright** — Headless browser automation and page navigation
- **axe-core** — Accessibility rule engine (via `axe-playwright-python`)
- **Docker** — Reproducible, isolated execution environment
- **FastAPI** — Optional REST API for remote scanning and result retrieval
- **Jinja2** — HTML report generation and templating

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Docker Container Orchestration             │
│              (Container Manager + Runner)               │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
   ┌────▼────────┐                  ┌────────▼─────┐
   │  One-off    │                  │  Long-lived  │
   │   Scanner   │                  │   API Server │
   │  (pipeline) │                  │  (FastAPI)   │
   └────┬────────┘                  └────────┬─────┘
        │                                   │
        └───────────────┬─────────────────────┘
                        │
        ┌───────────────▼─────────────────┐
        │    Scanning Pipeline Layer      │
        │  (Dependency Injection Pattern) │
        │                                 │
        │  Services:                      │
        │  • ZipService                   │
        │  • HtmlDiscoveryService         │
        │  • HttpService                  │
        │  • PlaywrightAxeService         │
        └───────────────┬─────────────────┘
                        │
        ┌───────────────▼─────────────────┐
        │  Reporting & Configuration      │
        │  • Jinja Report Builder         │
        │  • Settings Manager             │
        │  • Logging Setup                │
        └─────────────────────────────────┘
```

---

## Core Architecture Principles

### 1. Container-First Design

**Why:** Playwright dependencies, Python versions, and OS packages must be consistent across all environments.

- All scans execute inside Docker containers (hard guard: `A11Y_SCANNER_IN_CONTAINER=1`)
- Host machine only needs Python 3.10+ and Docker
- Container image is cached by content hash for fast iteration
- Supports both Docker and Podman (rootless-compatible)

### 2. Service-Oriented Architecture

**Why:** Separation of concerns, testability, and composability.

- Each service handles a single responsibility (ZIP extraction, HTML discovery, HTTP serving, scanning)
- Services are dependency-injected into the `Pipeline` orchestrator
- No global state; all services are instantiable and mockable
- Easy to swap implementations or add new services

### 3. Dependency Injection

**Why:** Loose coupling, testability, and flexibility.

- Pipeline receives all services in constructor
- Settings object centralizes path/port configuration
- Tests mock services without modifying application code
- New services can be added without changing existing code

### 4. Fail-Safe Error Handling

**Why:** Robustness and graceful degradation.

- HTTP server always shut down in `finally` block (even on scan errors)
- Individual page failures don't stop the pipeline
- Meaningful logging at all critical junctures
- Clear error messages guide troubleshooting

### 5. Immutable & Portable Paths

**Why:** Cross-platform compatibility and CI/CD portability.

- Paths are relative to working directory by default (not absolute)
- Environment variables override defaults in Docker
- Settings object as single source of truth for paths

---

## Component Layers

### Layer 1: Container Orchestration (Outermost)

**Files:**
- `src/scanner/container/manager.py` — Docker SDK integration, caching, image building
- `src/scanner/container/runner.py` — CLI entry point with prepare/run/serve commands
- `src/scanner/container/integration.py` — End-to-end integration test harness
- `docker/Dockerfile` — Base image with Playwright browsers pre-installed

**Responsibilities:**
- Build and cache Docker images with content hash keys
- Detect Podman engine and apply appropriate mount options
- Volume binding (read-only repo, read-write data)
- Environment variable injection (`A11Y_SCANNER_IN_CONTAINER=1`)
- Stream container logs to host stdout

**Key Features:**
- **Smart Caching:** Cache key = SHA256(pyproject.toml + src/ tree)
- **Podman Support:** Detects rootless Podman and applies `:Z` SELinux labels
- **Graceful Fallback:** Can disable cache and run slow path (apt-get + pip each time)

**Usage Examples:**

```python
# Prepare cache image
mgr = ContainerManager()
image_ref = mgr.prepare_cached_image()

# Run scanner one-off
mgr.run_scanner(use_cache=True, rebuild_cache=False, stream_logs=True)

# Serve API server
mgr.serve_api(port=8008, use_cache=True)
```

### Layer 2: Pipeline Orchestration

**Files:**
- `src/scanner/pipeline.py` — Main orchestration engine

**The Pipeline Class:**

```python
class Pipeline:
    """
    Orchestrates:
    1. Unzip → extract site archive
    2. Discover → find all HTML files
    3. Serve → start local HTTP server
    4. Scan → iterate pages with Playwright + axe
    5. Report → aggregate results into JSON
    """
```

**Execution Flow:**

```
Start
  │
  ├─→ ZipService.run()
  │   ├─ Detect zip in unzip_dir
  │   ├─ Validate & extract (Zip Slip protection)
  │   └─ Populate scan_dir/
  │
  ├─→ HtmlDiscoveryService.discover_html_files()
  │   └─ Recursive rglob("*.html", "*.htm")
  │       Return sorted list with absolute + relative paths
  │
  ├─→ HttpService.start(scan_dir)
  │   ├─ Bind to localhost:0 (OS picks free port)
  │   ├─ Start SimpleHTTPServer in background thread
  │   └─ Set self.base_url = "http://localhost:NNNN"
  │
  ├─→ FOR each HTML file:
  │   ├─ Construct URL: base_url + relative_path
  │   ├─ PlaywrightAxeService.scan_url(url, report_path)
  │   │   ├─ Navigate to page with reusable browser
  │   │   ├─ Inject axe-core and run scan
  │   │   ├─ Capture element screenshots for violations
  │   │   ├─ Write JSON artifact to results_dir/
  │   │   └─ Return violation list
  │   └─ Append results with context (scanned_url, source_file)
  │
  ├─→ Finally: HttpService.stop()
  │   └─ Shutdown server & join thread
  │
  └─→ Return all_results
```

**Error Handling:**

- If ZIP not found: raise `FileNotFoundError` (fail fast)
- If no HTML files: log warning, return empty list (not fatal)
- If page scan fails: log error, continue to next page
- If reporting fails: log error, don't fail the scan
- HTTP server **always** stopped in `finally` block

### Layer 3: Service Layer

#### 3.1 ZipService

**Path:** `src/scanner/services/zip_service.py`

**Responsibility:** Safely extract ZIP archives with Zip Slip protection.

**Key Methods:**

```python
detect_zip() → Path
    # Find first .zip in unzip_dir
    # Raises FileNotFoundError if none found

_sanitize_archive_member(member_name: str) → str | None
    # Reject absolute paths, ".." references
    # Normalize path
    # Return safe name or None

_is_safe_path(base: Path, target: Path) → bool
    # Verify target is within base directory
    # Prevents directory traversal attacks

unzip(zip_path, destination)
    # Extract with path validation
    # Log extraction stats

run()
    # Main entry: detect → unzip → log extracted items
```

**Security Features:**

- **Zip Slip Protection:** Validates all paths before extraction
- **Absolute Path Rejection:** Rejects any `../` sequences
- **Double-Check:** Verifies resolved paths are within destination
- **Granular Logging:** Logs skipped dangerous files

**Example Attack & Prevention:**

```
Archive contains: "../../../etc/passwd"
  ↓
_sanitize_archive_member() detects ".." → returns None
  ↓
File skipped, security breach prevented
```

#### 3.2 HtmlDiscoveryService

**Path:** `src/scanner/services/html_discovery_service.py`

**Responsibility:** Recursively enumerate HTML files (.html, .htm extensions).

**Key Methods:**

```python
discover_html_files() → list[dict[str, Path]]
    # Recursively find all *.html and *.htm files
    # Return list of dicts with:
    #   {
    #     "absolute": Path(...),  # Full resolved path
    #     "relative": Path(...)   # Relative to scan_dir
    #   }
```

**Features:**

- Searches recursively with `rglob(pattern)`
- Handles both `.html` and `.htm` extensions
- Preserves relative paths for URL construction
- Logs warnings if paths can't be relativized
- Returns empty list if scan_dir doesn't exist

**Example Output:**

```python
[
    {"absolute": Path("/worksrc/data/scan/index.html"),
     "relative": Path("index.html")},
    {"absolute": Path("/worksrc/data/scan/blog/post-1.html"),
     "relative": Path("blog/post-1.html")},
    {"absolute": Path("/worksrc/data/scan/nested/deep/page.htm"),
     "relative": Path("nested/deep/page.htm")},
]
```

#### 3.3 HttpService

**Path:** `src/scanner/services/http_service.py`

**Responsibility:** Host extracted files over HTTP for Playwright to access.

**Key Methods:**

```python
start(directory: Path)
    # Find free port (socket bind to 0)
    # Create ThreadingHTTPServer with handler factory
    # Start server in background daemon thread
    # Set self.base_url = "http://localhost:PORT"

stop()
    # Gracefully shutdown server
    # Join thread with 5-second timeout
    # Log if cleanup incomplete
```

**Features:**

- Uses OS-assigned port (port 0) for automatic free port selection
- `ThreadingHTTPServer` handles concurrent requests
- Daemon thread ensures no zombie processes
- Handler uses `functools.partial` to pass `directory` to handler constructor
- Timeout on thread join prevents indefinite hangs

**Why ThreadingHTTPServer?**

- Per-request threads don't block page scanning loops
- Single requests never interfere with other scans
- Simpler than async/await for this use case

#### 3.4 PlaywrightAxeService

**Path:** `src/scanner/services/playwright_axe_service.py`

**Responsibility:** Launch browser, navigate pages, run axe-core audits, capture screenshots.

**Key Methods:**

```python
__enter__() / __exit__()
    # Context manager for reusable browser lifecycle
    # start() initializes Playwright + browser
    # stop() cleans up all resources

start()
    # Launch Chromium in headless mode
    # Set viewport to 1280x720
    # Create browser context

stop()
    # Close context, browser, Playwright
    # Log completion

scan_url(url, report_path, source_file) → list[dict]
    # Navigate to URL with reusable browser
    # Run axe.run() to get violations
    # Capture element screenshots for each violation
    # Write JSON artifact with full axe report
    # Return violations list
```

**Browser Lifecycle Management:**

```python
# Single-use mode (automatic):
service = PlaywrightAxeService()
violations = service.scan_url(url1, report1)
# Browser created & destroyed per call

# Reusable mode (efficient):
with PlaywrightAxeService() as service:
    v1 = service.scan_url(url1, report1)
    v2 = service.scan_url(url2, report2)  # Reuses browser
# Browser cleaned up once at context exit
```

**Performance Optimization:**

- **Context manager pattern** = Single browser for all pages
- **Reusable context** = No browser restart overhead
- **Viewport fixed** = 1280x720 for consistent rendering

**Violation Screenshot Capture:**

```python
_capture_violation_screenshot(page, violation, results_dir)
    # Extract CSS selector from violation.nodes[0].target[0]
    # Try element-level screenshot first
    #   - Add red border outline for visibility
    #   - Capture locator.first bounded area
    # Fall back to full-page if element capture fails
    # UUID filename: violation-{rule_id}-{uuid}.png
    # Return relative path
```

**JSON Artifact Schema:**

```json
{
  "url": "http://localhost:8000/index.html",
  "scanned_url": "http://localhost:8000/index.html",
  "source_file": "index.html",
  "violations": [
    {
      "id": "color-contrast",
      "impact": "serious",
      "description": "Elements must have sufficient color contrast...",
      "help": "Ensure the contrast ratio is 4.5:1 for normal text",
      "helpUrl": "https://dequeuniversity.com/rules/axe/4.8/color-contrast",
      "nodes": [
        {
          "target": ["p.low-contrast"],
          "html": "<p class=\"low-contrast-text\">Low contrast</p>",
          "screenshot": "violation-color-contrast-{uuid}.png"
        }
      ]
    }
  ],
  "passes": [...],
  "inapplicable": [...],
  "incomplete": [...],
  "timestamp": "2025-10-22T14:30:15Z"
}
```

### Layer 4: Reporting & Configuration

#### 4.1 Jinja Report Builder

**Path:** `src/scanner/reporting/jinja_report.py`

**Responsibility:** Aggregate JSON artifacts and generate consolidated HTML report.

**Key Classes:**

```python
@dataclass
class Occurrence:
    """Single violation instance on a page."""
    url: str
    source_file: str | None
    selector: str | None
    html_snippet: str | None
    screenshot_path: str | Path | None

@dataclass
class RuleGroup:
    """Aggregated violations for a single rule across all pages."""
    id: str
    impact: str | None
    description: str | None
    helpUrl: str | None
    count: int
    occurrences: List[Occurrence]

@dataclass
class ReportModel:
    """Top-level report structure."""
    title: str
    generated_at: str
    pages_scanned: int
    total_violations: int
    violations_by_impact: dict[str, int]
    rule_groups: dict[str, RuleGroup]

def build_report(results_dir, output_path, title):
    # Read all *.json in results_dir
    # Parse and aggregate violations by rule ID
    # Build ReportModel with counts & summaries
    # Render a11y_report.html.j2 template
    # Write to output_path
```

**Report Template:**

- **Path:** `src/scanner/templates/a11y_report.html.j2`
- **Features:**
  - Rule grouping with impact-based styling (critical/serious/moderate/minor)
  - Per-rule occurrence list with URL, selector, HTML snippet, screenshot
  - Direct links to remediation guidance (helpUrl)
  - Summary statistics (pages scanned, total violations, breakdown by impact)
  - Responsive design for viewing on desktop/tablet

**Template Loading:**

```python
loader = ChoiceLoader([
    FileSystemLoader("src/scanner/templates"),  # Dev: source tree
    PackageLoader("scanner", "templates"),       # Prod: installed package
])
```

#### 4.2 Settings Manager

**Path:** `src/scanner/core/settings.py`

**Responsibility:** Centralize configuration, paths, and environment defaults.

**Key Properties:**

```python
class Settings:
    base_path: Path        # Root for relative paths (default: CWD)
    data_dir: Path         # data/
    scan_dir: Path         # data/scan/ (extracted site files)
    unzip_dir: Path        # data/unzip/ (input archives)
    results_dir: Path      # data/results/ (JSON + screenshots)
    port: int              # Default 8000 (unused currently)
```

**Initialization:**

```python
# Default: relative paths from CWD
settings = Settings()
# settings.data_dir = Path("data")

# With explicit root (testing):
settings = Settings(root_path=Path("/tmp/test"))
# settings.data_dir = Path("/tmp/test/data")
```

**Why Relative Paths?**

- Works in any directory without environment setup
- Container-friendly (workdir is `/worksrc`)
- Portable across CI/CD systems
- No assumptions about project layout

### Layer 5: API Server (Optional)

**Path:** `src/scanner/web/server.py`

**FastAPI Endpoints:**

```
POST /api/scan/zip
    • Upload ZIP archive
    • Trigger full scan pipeline
    • Return JSON results

POST /api/scan/url
    • Request: {"urls": ["https://example.com", ...]}
    • Scan live URLs (no extraction)
    • Return JSON results

GET /reports/latest.html
    • Serve consolidated HTML report
    • StaticFiles mount to data/reports/

GET /healthz
    • Health check endpoint
    • Returns 200 OK

GET /results (static mount)
    • Serve raw artifacts (JSON, PNG)
    • StaticFiles mount to data/results/
```

**Security:**

- Container guard: `A11Y_SCANNER_IN_CONTAINER=1` check
- Upload size limit: 100 MB
- MIME type validation: only `application/zip` variants
- URL count limit: max 50 per request

---

## Data Flow

### Scenario 1: ZIP Scan (One-Off)

```
Host                              Container
  │
  ├─→ Prepare: docker build       Docker builds image with cache
  │                               Cache key: SHA256(pyproject.toml+src/)
  │
  ├─→ Run: docker run             ├─→ main.py runs
  │   └─ data/:rw                 │   ├─→ Pipeline()
  │   └─ src/:ro                  │   ├─→ ZipService.run()
  │                               │   │   └─ Find/extract data/unzip/site.zip → data/scan/
  │                               │   ├─→ HtmlDiscoveryService.discover_html_files()
  │                               │   │   └─ Recursive rglob() → list of Path dicts
  │                               │   ├─→ HttpService.start(data/scan)
  │                               │   │   └─ ThreadingHTTPServer at localhost:RANDOM
  │                               │   ├─→ FOR each HTML:
  │                               │   │   ├─ PlaywrightAxeService.scan_url(url)
  │                               │   │   │   ├─ Navigate page
  │                               │   │   │   ├─ Run axe.run()
  │                               │   │   │   ├─ Capture screenshots
  │                               │   │   │   └─ Write JSON to data/results/
  │                               │   │   └─ Append to results
  │                               │   ├─→ HttpService.stop()
  │                               │   └─→ build_report(data/results → data/reports/latest.html)
  │
  └─→ View: open data/reports/latest.html
```

### Scenario 2: API Scan (Streaming)

```
Client                            Container (FastAPI)
  │
  ├─→ POST /api/scan/zip          ├─→ Validate MIME type & size
  │   file=site.zip               ├─→ Save to data/unzip/UPLOAD_ID.zip
  │                               ├─→ Same as Scenario 1 pipeline
  │                               ├─→ build_report()
  │                               └─→ Return JSON metadata
  │
  └─→ GET /reports/latest.html    └─→ Serve data/reports/latest.html
```

### Scenario 3: Live URL Scan

```
Container                         Target Site
  │
  ├─→ scan_live_site.py
  │   ├─→ PlaywrightAxeService.scan_url("https://example.com")
  │   │   ├─→ Navigate directly (no extraction)
  │   │   ├─→ Run axe.run()
  │   │   ├─→ Capture screenshots
  │   │   └─→ Write JSON
  │   ├─→ (repeat for each URL)
  │   └─→ build_report(live_results → reports/latest.html)
```

---

## Container Orchestration

### Cache Key Generation

```python
def _compute_cache_key(self) -> str:
    """
    Cache key = SHA256(
        pyproject.toml content +
        hash of all .py files in src/
    )
    """
    h = hashlib.sha256()
    
    # Hash pyproject.toml
    h.update((project_root / "pyproject.toml").read_bytes())
    
    # Hash all src/scanner/**/*.py
    for py_file in sorted((project_root / "src").rglob("*.py")):
        _hash_file(py_file, h)
    
    return h.hexdigest()[:8]  # 8-char prefix
```

### Image Naming

```
Cache image: a11y-scanner-cache:{cache_key}
Example:    a11y-scanner-cache:a1b2c3d4

Base image: mcr.microsoft.com/playwright/python:v1.54.0-jammy
```

### Dockerfile Strategy

```dockerfile
FROM mcr.microsoft.com/playwright:v1.54.0-jammy  # Pre-installed browsers

# Setup venv
RUN python3 -m venv /opt/a11y/venv

# Install package
COPY . .
RUN /opt/a11y/venv/bin/pip install .

ENTRYPOINT ["python", "-m", "scanner.main"]
```

### Volume Mounts

```
Host                          Container
data/ ──────(rw)────────→ /worksrc/data/
src/ ───────(ro)────────→ /worksrc/src/

Podman adds `:Z` for SELinux relabeling:
  data/ ──────(rw,Z)────────→ /worksrc/data/
  src/ ───────(ro,Z)────────→ /worksrc/src/
```

### Environment Variables

```
PYTHONUNBUFFERED=1             # Unbuffered output
DEBIAN_FRONTEND=noninteractive # Non-interactive apt
A11Y_SCANNER_IN_CONTAINER=1    # Hard guard for main.py
```

---

## Configuration & Settings

### Paths Overview

```
project_root/
├── data/
│   ├── unzip/       ← ZIP inputs go here
│   ├── scan/        ← Extracted site files
│   ├── results/     ← JSON artifacts & screenshots
│   ├── reports/     ← Generated HTML reports
│   └── live_results/← For scan_live_site.py
├── src/scanner/     ← Source code (read-only in container)
├── tests/
└── pyproject.toml
```

### Environment Overrides

Inside container, paths respect these env vars:
- `DATA_DIR` — override data/ location
- `SCAN_DIR` — override data/scan/ location
- etc.

(Currently implemented in Settings via property decorators)

---

## Error Handling & Resilience

### Pipeline-Level Error Handling

```python
try:
    zip_service.run()           # Fail-fast if no zip
    html_files = html_service.discover_html_files()
    if not html_files:
        log.warning("No HTML files found")
        return []
    
    http_service.start()
    with axe_service:           # Context manager for cleanup
        for file_info in html_files:
            try:
                violations = axe_service.scan_url(...)
            except RuntimeError as e:
                log.error("Failed to scan %s: %s", url, e)
                continue        # Continue to next page

except FileNotFoundError:
    log.error("Input zip file not found")
    raise

finally:
    log.info("Shutting down HTTP server")
    http_service.stop()         # Always stops, even on error
```

### Service-Level Error Handling

**ZipService:**
- `FileNotFoundError` — No zip file found
- `RuntimeError` — Extraction failed
- Gracefully skips files with unsafe paths

**HttpService:**
- Port binding failure → RuntimeError
- Thread join timeout → log error (but continue)

**PlaywrightAxeService:**
- Navigation timeout → RuntimeError
- Screenshot capture fails → log, skip screenshot (don't fail page)
- Axe run fails → RuntimeError

**Jinja Report:**
- Missing results dir → log error, continue
- JSON parse error → skip file, continue
- Template not found → RuntimeError

### Failure Modes & Recovery

| Failure | Response | Recovery |
|---------|----------|----------|
| No input zip | Fail pipeline early | User provides ZIP |
| No HTML files | Return empty results | Valid success (no violations) |
| Page scan timeout | Log error, skip page | Continue to next page |
| Screenshot capture fails | Log error, skip screenshot | Continue with violation record |
| Port binding fails | RuntimeError | Retry with different port (OS will assign) |
| Report generation fails | Log error, don't fail scan | User can manually inspect JSON artifacts |

---

## Performance Considerations

### Browser Reuse (Major Win)

```python
# Slow: browser restart per page
for page_url in pages:
    browser = launch_chromium()     # ← 3-5 seconds per page
    page = browser.new_page()
    results = scan(page)
    browser.close()
# Total: N pages × 5 sec = slow

# Fast: single browser, many pages
with PlaywrightAxeService() as service:  # Launch once
    for page_url in pages:
        results = service.scan_url(page_url)  # Reuse browser ← milliseconds
# Total: 5 sec startup + (N × 50ms) = fast
```

**Savings:** ~40-80% runtime reduction for multi-page sites.

### Viewport & Rendering

- Fixed viewport (1280×720) ensures consistent rendering
- Avoids responsive design reflows between scans
- Element screenshots use bounded captures (not full-page)

### Caching Strategy

- Base Playwright image cached locally (pulled once)
- Derived image cached by content hash (rebuilt only on code changes)
- No full rebuild on each run (huge speedup for iteration)

### Concurrency Opportunities

Currently sequential:
```
Page 1 scan (50ms) → Page 2 scan (50ms) → Page 3 scan (50ms) = 150ms
```

Future parallel opportunity:
```
Page 1, 2, 3 scans in parallel (worker pool) = ~50ms
```

(Currently not implemented; would require async Playwright + semaphore for resource limits)

---

## Extending the Scanner

### Adding a New Service

**Example:** Add a `CSSAuditService` for CSS best practices.

1. **Create the service:**

```python
# src/scanner/services/css_audit_service.py
class CSSAuditService:
    def audit(self, page: Page, url: str) -> dict[str, any]:
        # Extract and analyze CSS
        return {"unused_rules": [...], "performance_issues": [...]}
```

2. **Integrate into pipeline:**

```python
# src/scanner/pipeline.py
css_service = CSSAuditService()

class Pipeline:
    def __init__(self, ..., css_service):
        self.css_service = css_service
    
    def run(self):
        # ... existing code ...
        with self.axe_service:
            for file_info in html_files:
                violations = self.axe_service.scan_url(...)
                css_audit = self.css_service.audit(page, url)  # ← New
                all_results.append({
                    "violations": violations,
                    "css_audit": css_audit,
                })
```

3. **Update reporting:**

```python
# src/scanner/reporting/jinja_report.py
# Add new section to ReportModel to include CSS findings
# Update template to render CSS audit results
```

### Adding a New Report Format

**Example:** Add SARIF export for GitHub Code Scanning.

```python
# src/scanner/reporting/sarif_export.py
def export_sarif(rule_groups: dict, output_path: Path):
    sarif_document = {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "a11y-scanner", ...}},
            "results": [
                # Convert rule_groups to SARIF results
            ]
        }]
    }
    output_path.write_text(json.dumps(sarif_document, indent=2))
```

### Adding a New API Endpoint

**Example:** Add batch export endpoint.

```python
# src/scanner/web/server.py
@app.get("/api/export/sarif")
def export_sarif():
    """Export all results as SARIF."""
    report = build_report(...)
    return export_sarif(report)
```

### Adding Configuration Options

**Example:** Add headless toggle.

```python
# src/scanner/core/settings.py
class Settings:
    headless: bool = True  # Add property
    
    def __init__(self, headless: bool = True):
        self.headless = headless
```

```python
# src/scanner/services/playwright_axe_service.py
self._browser = self._playwright.chromium.launch(
    headless=self.settings.headless
)
```

### Adding Logging & Observability

- Use `logging` module (already integrated via `logging_setup.py`)
- Log at appropriate levels: DEBUG (details), INFO (progress), ERROR (failures)
- Structured logging for machine parsing (JSON format optional)

---

## Testing Architecture

### Unit Tests

**Location:** `tests/`

- **test_zip_service.py** — ZipService path validation, Zip Slip prevention
- **test_html_discovery_service.py** — HTML file discovery
- **test_http_service.py** — HTTP server startup/shutdown
- **test_pipeline.py** — Pipeline orchestration with mocked services
- **test_api.py** — FastAPI endpoints, validation, security
- **test_reporting.py** — Report generation, aggregation
- **test_settings.py** — Settings path resolution

**Approach:**
- Mock Docker client
- Mock Playwright browser (no actual browser launches)
- Mock filesystem (pyfakefs)
- Verify service contracts & error handling

### Integration Tests

**Location:** `src/scanner/container/integration.py`

- End-to-end tests inside Docker container
- Uses real Playwright browser
- Scans test site HTML sets (`tests/assets/html_sets/`)
- Compares output JSON against golden files (`golden_results/`)
- Validates report generation

**Run:** `python -m scanner.container.integration`

### Golden File Validation

Test sites include expected results:
```
tests/assets/html_sets/1/
├── index.html
├── about.html
└── golden_results/
    └── report.json  ← Expected violations
```

Integration suite compares actual vs. expected, fails on mismatch.

---

## Security Considerations

### Zip Slip Prevention

✓ Validates all paths before extraction
✓ Rejects absolute paths and `../` sequences
✓ Double-checks extracted paths are within destination

### API Input Validation

✓ MIME type validation (only `application/zip`)
✓ Upload size limit (100 MB)
✓ URL count limit (50 URLs max)
✓ URL format validation (Pydantic HttpUrl)

### Container Isolation

✓ Read-only source tree mount
✓ Read-write data directory (controlled blast radius)
✓ No network access outside container (by default)
✓ Rootless Podman support (no root required)

### Secrets & Credentials

⚠️ Current recommendation: Scrub sensitive URLs from `data/results/` before sharing artifacts

Future considerations:
- Environment variable masking in logs
- Webhook callback URL validation
- OAuth/API key rotation policies

---

## Debugging & Troubleshooting

### Enable Debug Logging

```python
# In src/scanner/core/logging_setup.py
setup_logging(level=logging.DEBUG)  # Verbose output
```

### Check Container Logs

```bash
docker run --rm -v data:rw ... python -m scanner.main 2>&1 | tail -50
```

### Inspect Artifacts

```bash
# JSON results
ls -lah data/results/
cat data/results/index_html.json | jq '.violations[0]'

# Screenshots
open data/results/violation-*.png

# Report
open data/reports/latest.html
```

### Validate ZipService Extraction

```bash
# Check extraction
ls -R data/scan/
```

### Test HttpService Port Binding

```bash
# Verify server is reachable
curl -I http://localhost:NNNN/index.html
```

### Restart Container

```bash
# Force rebuild
python -m scanner.container.runner prepare --rebuild-cache
```

---

## Future Enhancements

1. **Parallel Scanning** — Worker pool for multi-page concurrency
2. **Advanced Configuration** — Include/exclude patterns, timeouts, custom rules
3. **CI/CD Integration** — SARIF export, GitHub Actions template
4. **Background Jobs** — Async queue, job status polling
5. **Database Storage** — Persist results for historical trends
6. **WebSocket API** — Real-time progress updates
7. **Custom Rules** — User-defined accessibility checks
8. **Performance Profiling** — Automated performance regression detection

