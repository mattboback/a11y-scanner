# Repository Guidelines

## Project Structure & Module Organization
Source lives in `src/scanner`, grouped by feature domains such as FastAPI endpoints, container orchestration, and reporting utilities. Tests mirror that tree under `tests`, with fixtures in `tests/conftest.py`. Sample inputs and golden outputs reside in `test_data`, while generated artifacts (unzipped sites, reports, screenshots) land in `data` and should be cleaned with `make clean`. Docker assets sit in `docker/`, ad hoc helpers in `scripts/`, and extended design notes in `docs/`. Treat the `Makefile` as the entry point for common workflows.

## Build, Test, and Development Commands
Run `make install` to bootstrap the virtualenv with dev extras before editing. Build the Playwright-ready container via `python -m scanner.container.runner prepare` (or `make docker-prepare`). Execute a full scan using `python -m scanner.container.runner run`, which reads `data/unzip/site.zip`. Serve the API locally with `python -m scanner.container.runner serve --port 8008` or `make serve`. Use `make clean` after scans to delete bulky artifacts.

## Coding Style & Naming Conventions
Target Python 3.10+ with four-space indentation and comprehensive type hints. Keep module names lowercase with underscores (e.g., `scanner/reporting`), classes in PascalCase, and Playwright fixtures following `verb_noun`. Format code with `black src tests` and lint using `ruff check src tests` (add `--fix` for quick cleanups). HTML templates under `src/scanner/templates` should follow the existing Jinja2 block structure.

## Testing Guidelines
Use `pytest -k "not test_playwright_axe_service"` for the fast unit suite while iterating. Container-dependent checks run via `python -m scanner.container.integration` or `make integration`, which download browsers inside the image. Reporting scripts have a smoke test at `./scripts/test_reporting.sh`, writing HTML into `htmlcov/` for inspection. Name tests after the unit under test, such as `test_report_builder_handles_missing_alt`, and keep shared fixtures centralized.

## Commit & Pull Request Guidelines
Write imperative, scoped commit messages (e.g., `chore: reset data artifacts`) and bundle related changes together. Before opening a PR, verify formatting, linting, unit tests, and the Docker integration suite if container logic changed. PR descriptions should summarize behavioral impact, link tracked issues, and attach relevant screenshots or sample JSON when reports change. Include manual validation steps so reviewers can reproduce your checks quickly.

## Operational Notes
Always interact with the scanner through the Docker-backed runners; direct `python -m scanner.main` calls will abort. Scrub sensitive URLs from `data/results` before sharing artifacts, and prefer `make clean` to keep the repository light. When adding new workflows, update the `Makefile` so contributors can discover them easily.
