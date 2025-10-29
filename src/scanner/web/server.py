from __future__ import annotations

import ipaddress
import os
import shutil
import socket
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.pipeline import Pipeline
from scanner.reporting.jinja_report import build_report
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"

# Optional auth: set A11Y_API_TOKEN to require X-API-Key or Bearer <token>
API_TOKEN_ENV = "A11Y_API_TOKEN"

MAX_UPLOAD_SIZE = 100 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-zip",
}

app = FastAPI(title="a11y-scanner API", version="0.1.0")
setup_logging()
settings = Settings()

for d in (
    settings.data_dir,
    settings.unzip_dir,
    settings.results_dir,
    settings.scan_dir,
):
    d.mkdir(parents=True, exist_ok=True)

reports_dir = settings.data_dir / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)

app.mount("/results", StaticFiles(directory=settings.results_dir), name="results")
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


class UrlsIn(BaseModel):
    urls: list[HttpUrl]

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


def _require_auth(request: Request):
    """
    If A11Y_API_TOKEN is set, require X-API-Key or Authorization: Bearer <token>.
    If not set, auth is not enforced (use only on trusted networks).
    """
    expected = os.environ.get(API_TOKEN_ENV)
    if not expected:
        return
    header_val = request.headers.get("x-api-key")
    if not header_val:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            header_val = auth[7:].strip()
    if header_val != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _clean_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    for child in p.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink(missing_ok=True)
            except Exception:
                pass


def _validate_public_http_url(url_str: str) -> None:
    """
    Best-effort SSRF mitigation:
      - Only http/https (already enforced by HttpUrl).
      - Resolve host → IP(s); require ALL resolved IPs to be global (public).
      - Block obvious loopback hostnames.
    Note: Redirects at runtime may still point to private nets; additional
    network-level egress controls are recommended for defense in depth.
    """
    parsed = urlparse(url_str)
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail=f"Invalid URL host: {url_str}")

    lower = host.lower()
    if lower in {"localhost"}:
        raise HTTPException(status_code=400, detail=f"Blocked host: {host}")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"DNS resolution failed for {host}")

    if not infos:
        raise HTTPException(status_code=400, detail=f"Could not resolve host: {host}")

    for _family, _socktype, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid resolved IP for {host}: {ip}"
            )

        # Strict: every resolved address must be globally routable.
        if not ip_obj.is_global:
            raise HTTPException(
                status_code=400,
                detail=f"Blocked non-public address for {host}: {ip}",
            )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <h1>a11y-scanner API</h1>
    <ul>
      <li>POST <code>/api/scan/zip</code> with form field <code>file</code> (.zip of a static site)</li>
      <li>POST <code>/api/scan/url</code> with JSON like <code>{"urls":["https://example.com/"]}</code></li>
    </ul>
    <p><strong>Security:</strong> For private networks only by default. Set <code>A11Y_API_TOKEN</code> to require an API key. The server denies non-public destinations for URL scans.</p>
    <p>Artifacts: <a href="/reports" target="_blank">/reports</a> and <a href="/results" target="_blank">/results</a>.</p>
    """


@app.post("/api/scan/zip")
async def scan_zip(request: Request, file: UploadFile = File(...)):
    _require_container()
    _require_auth(request)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only ZIP files are allowed.",
        )
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must have a .zip extension")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE / (1024 * 1024):.0f} MB",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    _clean_dir(settings.scan_dir)
    _clean_dir(settings.results_dir)

    target = settings.unzip_dir / "site.zip"
    try:
        target.write_bytes(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
        )

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
async def scan_url(request: Request, payload: UrlsIn):
    _require_container()
    _require_auth(request)

    # Additional SSRF guardrails beyond HttpUrl validation
    for url in payload.urls:
        url_str = str(url)
        if not url_str.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL: {url_str}. URLs must start with http:// or https://",
            )
        _validate_public_http_url(url_str)

    _clean_dir(settings.results_dir)

    try:
        count = 0
        scanned_urls: list[str] = []
        # Reuse a single browser for all URLs (faster, less resource use)
        with PlaywrightAxeService() as axe:
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
                    scanned_urls.append(f"{url_str} (failed: {str(e)})")
                    continue
    except HTTPException:
        raise
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

    uvicorn.run(app, host="0.0.0.0", port=8008)


if __name__ == "__main__":
    run()
