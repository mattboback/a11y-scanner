#!/usr/bin/env bash
set -euo pipefail

# This wrapper now delegates to the Python-based integration runner,
# which uses the Docker SDK for Python (no docker-compose or Dockerfiles).
python -m scanner.container.integration
