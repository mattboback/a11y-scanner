from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.pipeline import Pipeline
from scanner.reporting.jinja_report import ReportModel, build_report
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"

# Configuration
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-zip",
}

app = FastAPI(title="a11y-scanner API", version="0.1.0")
setup_logging()
settings = Settings()

# Ensure data folders exist
for d in (
    settings.data_dir,
    settings.unzip_dir,
    settings.results_dir,
    settings.scan_dir,
):
    d.mkdir(parents=True, exist_ok=True)

reports_dir = settings.data_dir / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)

# Serve static artifacts
app.mount("/results", StaticFiles(directory=settings.results_dir), name="results")
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


class UrlsIn(BaseModel):
    urls: List[HttpUrl]

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        if not v:
            raise ValueError("At least one URL must be provided")
        if len(v) > 50:
            raise ValueError("Maximum 50 URLs allowed per request")
        return v


def _require_container():
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        raise HTTPException(status_code=400, detail="Must run inside container")


def _clean_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    for child in p.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink(missing_ok=True)  # py310+
            except Exception:
                pass


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <h1>a11y‑scanner API</h1>
    <ul>
      <li>POST <code>/api/scan/zip</code> with form field <code>file</code> (.zip of a static site)</li>
      <li>POST <code>/api/scan/url</code> with JSON like <code>{"urls":["https://example.com/"]}</code></li>
    </ul>
    <p>Artifacts: <a href="/reports" target="_blank">/reports</a> and <a href="/results" target="_blank">/results</a>.</p>
    <p>For report format documentation, see: <a href="https://github.com/dequelabs/axe-core" target="_blank">axe-core documentation</a></p>
    """


@app.post("/api/scan/zip")
async def scan_zip(file: UploadFile = File(...)):
    _require_container()

    # Validate content type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only ZIP files are allowed.",
        )

    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must have a .zip extension")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE / (1024 * 1024):.0f} MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Reset previous run artifacts
    _clean_dir(settings.scan_dir)
    _clean_dir(settings.results_dir)

    # Save uploaded zip as data/unzip/site.zip
    target = settings.unzip_dir / "site.zip"
    try:
        target.write_bytes(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
        )
    # Run pipeline (unzip -> index -> serve -> run playwright -> write reports)
    try:
        zip_service = ZipService(
            unzip_dir=settings.unzip_dir, scan_dir=settings.scan_dir
        )
        html_service = HtmlDiscoveryService(scan_dir=settings.scan_dir)
        http_service = HttpService()
        axe_service = PlaywrightAxeService()
        pipeline = Pipeline(
            settings=settings,
            zip_service=zip_service,
            html_service=html_service,
            http_service=http_service,
            axe_service=axe_service,
        )
        violations = pipeline.run()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

    # Build consolidated HTML report
    output_html = reports_dir / "latest.html"
    try:
        build_report(
            settings.results_dir, output_html, title="Accessibility Report (ZIP)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )

    return JSONResponse(
        {
            "violations": len(violations),
            "pages_scanned": len(list(settings.results_dir.glob("*.json"))),
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
            "message": f"Scan complete. Found {len(violations)} violations.",
        }
    )


@app.post("/api/scan/url")
async def scan_url(payload: UrlsIn):
    _require_container()

    # Validate URLs (Pydantic HttpUrl already validates format, but we double-check)
    for url in payload.urls:
        url_str = str(url)
        if not url_str.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL: {url_str}. URLs must start with http:// or https://",
            )

    # Reset previous run artifacts
    _clean_dir(settings.results_dir)

    try:
        axe = PlaywrightAxeService()
        count = 0
        scanned_urls = []

        for url in payload.urls:
            url_str = str(url)
            safe_name = (
                url_str.replace("https://", "")
                .replace("http://", "")
                .replace("/", "_")
                .replace("?", "_")
            )
            report_path = settings.results_dir / f"{safe_name}.json"

            try:
                v = axe.scan_url(url_str, report_path, source_file=safe_name)
                count += len(v)
                scanned_urls.append(url_str)
            except Exception as e:
                # Log error but continue with other URLs
                scanned_urls.append(f"{url_str} (failed: {str(e)})")
                continue

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

    output_html = reports_dir / "latest.html"
    try:
        build_report(
            settings.results_dir, output_html, title="Accessibility Report (Live URLs)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )

    return JSONResponse(
        {
            "violations": count,
            "urls_scanned": len(payload.urls),
            "scanned_urls": scanned_urls,
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
            "message": f"Scanned {len(scanned_urls)} URLs. Found {count} violations.",
        }
    )


def run():
    import uvicorn

    # Uvicorn listens on 8008 (published by the container runner)
    uvicorn.run(app, host="0.0.0.0", port=8008)


if __name__ == "__main__":
    run()
