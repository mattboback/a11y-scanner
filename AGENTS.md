# Repository Guidelines

## Project Structure & Module Organization
The source code lives under `src/scanner`, with FastAPI endpoints, container orchestration, and reporting utilities grouped by subpackages. Tests mirror this hierarchy in `tests`, and sample inputs plus golden reports sit in `test_data`. Generated artifacts (zips, JSON, screenshots, HTML) land in `data` and can be wiped with `make clean`. Supporting assets are in `docker/` for image builds, `scripts/` for one-off helpers, and `docs/` for extended architecture and workflow references. Use the `Makefile` as the index of common workflows.

## Build, Test, and Development Commands
- `python -m scanner.container.runner prepare` (or `make docker-prepare`) builds the Playwright-ready Docker image.
- `python -m scanner.container.runner run` runs an end-to-end scan using whatever archive is under `data/unzip/site.zip`.
- `python -m scanner.container.runner serve --port 8008` (or `make serve`) hosts the API for uploads and live URLs.
- `make install` bootstraps the local virtualenv and installs dev extras; prefer this before editing code.

## Coding Style & Naming Conventions
Code targets Python 3.10+, four-space indentation, and type-annotated functions. Run `black src tests` for formatting and `ruff check src tests` for linting or `ruff check ... --fix` for quick cleanups. Module names stay lowercase with underscores (`scanner/reporting`), classes use PascalCase, and Playwright fixtures or services follow `verb_noun` naming for clarity (e.g., `scan_site`). HTML templates live under `src/scanner/templates` and should follow Jinja2 block naming already in place.

## Testing Guidelines
Use `pytest -k "not test_playwright_axe_service"` for the fast unit suite when iterating locally. For container-dependent coverage, run `python -m scanner.container.integration` or `make integration`; expect it to download browsers inside the image. Reporting scripts have a smoke test at `./scripts/test_reporting.sh` that writes HTML into `htmlcov/` for inspection. Name new tests after the unit under test (`test_report_builder_handles_missing_alt`) and keep fixtures under `tests/conftest.py`.

## Commit & Pull Request Guidelines
Commit messages should stay imperative and scoped; `chore: reset data artifacts` is preferable to `fixed stuff`. Group related changes per commit to simplify blame. Pull requests should link any tracked issues, summarize behavioral impacts, and attach screenshots or sample JSON when altering reports. Before opening a PR, verify formatting, linting, fast unit tests, and the Docker integration suite if container logic changed. Outline manual validation steps in the PR description so reviewers can reproduce them quickly.

## Operational Notes
Always interact with the scanner through the Docker-backed runners; direct `python -m scanner.main` calls will abort. Clean up bulky artifacts after local scans with `make clean` to avoid bloating the repo. When sharing reports, strip sensitive URLs from `data/results` before committing or uploading.
