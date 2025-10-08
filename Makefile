# Makefile — Docker-only workflow
PY := .venv/bin/python
.PHONY: help venv install docker-prepare scan-local integration live-scan clean serve test-reporting

help:
	@echo "Targets:"
	@echo "  venv            Create local virtualenv (.venv)"
	@echo "  install         Install project in editable mode with dev deps into .venv"
	@echo "  docker-prepare  Build/rebuild the cached Docker image"
	@echo "  scan-local      Package sample site and run scanner in Docker"
	@echo "  integration     Run integration suite in Docker"
	@echo "  live-scan       Run scan_live_site.py in Docker (uses container entrypoint)"
	@echo "  serve           Run the long-lived FastAPI server in Docker (port 8008)"
	@echo "  clean           Remove data artifacts"
	@echo "  test-reporting  Test the reporting system locally"

venv:
	python3 -m venv .venv

install: venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"

docker-prepare: install
	$(PY) -m scanner.container.runner prepare

scan-local: install
	./scripts/create_test_site.sh
	$(PY) -m scanner.container.runner run

integration: install
	$(PY) -m scanner.container.integration

# Note: live-scan uses the same container entrypoint (scanner.main).
# To run scan_live_site.py specifically inside the container, you can
# temporarily switch the container ENTRYPOINT, or keep scan_live_site
# as a separate command you exec inside. For simplicity we keep main.
live-scan: install
	@echo "Running main pipeline (see scan_live_site.py for a live variant)"
	$(PY) -m scanner.container.runner run

serve: install
	@echo "Starting FastAPI server at http://127.0.0.1:8008 (Ctrl+C to stop)"
	$(PY) -m scanner.container.runner serve --port 8008

clean:
	rm -rf data/scan data/results data/unzip data/live_results data/reports
	mkdir -p data/unzip data/results data/scan data/live_results data/reports

test-reporting: install
	@echo "Testing reporting system..."
	./scripts/test_reporting.sh
