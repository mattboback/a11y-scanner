from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
    urls: List[str]


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
    # Reset previous run artifacts
    _clean_dir(settings.scan_dir)
    _clean_dir(settings.results_dir)
    # Save uploaded zip as data/unzip/site.zip
    target = settings.unzip_dir / "site.zip"
    content = await file.read()
    target.write_bytes(content)
    # Run pipeline (unzip -> index -> serve -> run playwright -> write reports)
    zip_service = ZipService(unzip_dir=settings.unzip_dir, scan_dir=settings.scan_dir)
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
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
        }
    )


@app.post("/api/scan/url")
async def scan_url(payload: UrlsIn):
    _require_container()
    # Reset previous run artifacts
    _clean_dir(settings.results_dir)
    axe = PlaywrightAxeService()
    count = 0
    for url in payload.urls:
        safe_name = (
            url.replace("https://", "")
            .replace("http://", "")
            .replace("/", "_")
            .replace("?", "_")
        )
        report_path = settings.results_dir / f"{safe_name}.json"
        v = axe.scan_url(url, report_path)
        count += len(v)
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
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
        }
    )


def run():
    import uvicorn

    # Uvicorn listens on 8008 (published by the container runner)
    uvicorn.run(app, host="0.0.0.0", port=8008)


if __name__ == "__main__":
    run()
