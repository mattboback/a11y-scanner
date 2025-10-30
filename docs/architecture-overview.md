# Architecture Overview

> **Quick Navigation**: This is a high-level overview for new contributors. For an in-depth architectural analysis, see [Architecture Guide](./architecture.md).

The accessibility scanner is split into three major layers: orchestration (Docker
and CLI tooling), the scanning pipeline, and reporting/web delivery. This
document highlights the key modules so new contributors can navigate the codebase
quickly.

## High-Level Flow

1. **Container orchestration** uses `scanner.container.runner` to build a Docker
   image with Playwright browsers and execute commands inside it via the Docker SDK.
2. The **pipeline** (`scanner.pipeline.Pipeline`) prepares the workspace, hosts
   the extracted site locally, and iterates over each HTML page.
3. **Services** underneath the pipeline perform specialized work:
   - `ZipService` unpacks `data/unzip/site.zip` into `data/scan`.
   - `HtmlDiscoveryService` enumerates HTML files and relative paths.
   - `HttpService` serves `data/scan` over HTTP so Playwright can access
     `http://127.0.0.1:<port>/...` URLs.
   - `PlaywrightAxeService` launches Chromium via `playwright.sync_api`, runs
     `axe-playwright-python`, captures screenshots, and writes JSON artifacts.
4. **Reporting** composes Jinja templates into consolidated HTML under
   `data/reports/` and is reused by the FastAPI server (`scanner.web.server`).

The diagram below summarizes the relationships:

```
┌────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌────────────┐
│ CLI / Make │──▶──│ container.runner │──▶──│ pipeline.Pipeline│──▶──│ report HTML │
└────────────┘     └────────┬─────────┘     └──────┬──────────┘     └──────┬─────┘
                            │                    ┌──▼────────┐             │
                            │                    │ZipService │             │
                            │                    ├───────────┤             │
                            │                    │HtmlDiscovery           │
                            │                    ├───────────┤             │
                            │                    │HttpService │             │
                            │                    ├───────────┤             │
                            │                    │Playwright  │             │
                            │                    │AxeService  │             │
                            │                    └─────▲──────┘             │
                            │                          │                    │
                            │                    ┌─────┴──────┐             │
                            └────────────────────│ JSON + PNG │◀────────────┘
                                                 └────────────┘
```

## Key Entry Points

- `scan_live_site.py`: standalone script that proxies to the same container runner.
- `scanner/main.py`: ensures the process only runs inside Docker (`A11Y_SCANNER_IN_CONTAINER`).
- `scanner/web/server.py`: FastAPI app exposing `/api/scan/zip`, `/api/scan/url`,
  and `/reports/latest.html`.
- `scanner/container/integration.py`: convenience harness for running end-to-end
  tests inside the prepared container.

## Configuration & Settings

The `Settings` object (`scanner.core.settings.Settings`) is the central place for
filesystem paths, ports, and feature flags. Values default to directories under
`data/` but respect environment variables when running inside Docker.

## Reporting Stack

- Template source lives in `scanner/templates/`.
- `scanner.reporting.jinja_report.build_report` renders aggregated results into
  `data/reports/latest.html`.
- Static assets (screenshots, JSON) are linked relative to `data/results/`.

## Extending the Pipeline

When adding new capabilities:
- Place reusable behavior in `scanner/services/` and keep `Pipeline` focused on
  orchestration.
- Thread new configuration through `Settings` rather than hard-coding paths.
- Ensure JSON artifacts stay backward compatible; downstream consumers rely on
  keys like `scanned_url` and `source_file`.

If the pipeline shape changes, update the integration suite and documentation in
`README.md` and `docs/development-guide.md`.
