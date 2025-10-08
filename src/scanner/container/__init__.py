"""
Lightweight container management utilities using the Docker SDK for Python.

This package removes the need for docker-compose and Dockerfiles by:
- pulling a Playwright Python base image,
- mounting the repository and data directories,
- installing the project into a virtualenv inside the container,
- running the scanner as `python -m scanner.main`.

Public entrypoints:
- scanner.container.runner: CLI to run a one-off scan in a container.
- scanner.container.integration: Integration test harness using the container.
"""
