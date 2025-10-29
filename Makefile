# Makefile — uv + Docker workflow
.PHONY: help install docker-prepare scan-local integration live-scan clean serve test test-unit test-integration test-coverage golden-generate golden-test golden-compare

help:
	@echo "Targets:"
	@echo "  install         Install project dependencies with uv"
	@echo "  docker-prepare  Build/rebuild the cached Docker image"
	@echo "  scan-local      Package sample site and run scanner in Docker"
	@echo "  integration     Run integration suite in Docker"
	@echo "  live-scan       Run scan_live_site.py in Docker (uses container entrypoint)"
	@echo "  serve           Run the long-lived FastAPI server in Docker (port 8008)"
	@echo "  test            Run all tests in Docker (recommended)"
	@echo "  test-unit       Run unit tests only in Docker"
	@echo "  test-integration Run integration tests only in Docker"
	@echo "  test-coverage   Run tests with coverage report in Docker"
	@echo "  golden-generate Generate/update golden test files from test ZIPs"
	@echo "  golden-test     Run regression tests against golden files"
	@echo "  golden-compare  Compare current results with golden files only"
	@echo "  clean           Remove data artifacts"

install:
	@echo "Installing dependencies with uv..."
	uv sync --all-extras

docker-prepare: install
	uv run python -m scanner.container.runner prepare

scan-local: install
	./scripts/create_test_site.sh
	uv run python -m scanner.container.runner run

integration: install
	uv run python -m scanner.container.integration

# Note: live-scan uses the same container entrypoint (scanner.main).
# To run scan_live_site.py specifically inside the container, you can
# temporarily switch the container ENTRYPOINT, or keep scan_live_site
# as a separate command you exec inside. For simplicity we keep main.
live-scan: install
	@echo "Running main pipeline (see scan_live_site.py for a live variant)"
	uv run python -m scanner.container.runner run

serve: install
	@echo "Starting FastAPI server at http://127.0.0.1:8008 (Ctrl+C to stop)"
	uv run python -m scanner.container.runner serve --port 8008

# Test targets (Docker-based, recommended)
test:
	@echo "Running all tests in Docker..."
	./scripts/test_in_docker.sh all

test-unit:
	@echo "Running unit tests in Docker..."
	./scripts/test_in_docker.sh unit

test-integration:
	@echo "Running integration tests in Docker..."
	./scripts/test_in_docker.sh integration

test-coverage:
	@echo "Running tests with coverage in Docker..."
	./scripts/test_in_docker.sh coverage

golden-generate: install
	@echo "Generating golden test files from test ZIPs..."
	uv run python scripts/run_golden_tests.py --generate

golden-test: install
	@echo "Running regression tests against golden files..."
	uv run python scripts/run_golden_tests.py

golden-compare: install
	@echo "Comparing results with golden files (scan only)..."
	uv run python scripts/run_golden_tests.py --compare-only

clean:
	rm -rf data/scan data/results data/unzip data/live_results data/reports
	mkdir -p data/unzip data/results data/scan data/live_results data/reports
