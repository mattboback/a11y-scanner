#!/usr/bin/env bash
# Script to run tests inside Docker with Playwright browsers

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== A11y Scanner: Docker Test Runner ===${NC}\n"

# Parse command line arguments
TEST_TARGET="${1:-all}"
PYTEST_ARGS="${2:-}"

# Build test image with custom dockerignore
echo -e "${YELLOW}[1/3] Building test Docker image...${NC}"

# Temporarily rename dockerignore files to use test version
if [ -f .dockerignore ]; then
  mv .dockerignore .dockerignore.bak
fi
if [ -f .dockerignore.test ]; then
  cp .dockerignore.test .dockerignore
fi

docker build \
  -f docker/Dockerfile.test \
  -t a11y-scanner-test:latest \
  .

BUILD_RESULT=$?

# Restore original dockerignore
rm -f .dockerignore
if [ -f .dockerignore.bak ]; then
  mv .dockerignore.bak .dockerignore
fi

if [ $BUILD_RESULT -ne 0 ]; then
  echo -e "${RED}Failed to build test image${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Test image built${NC}\n"

# Run tests based on target
echo -e "${YELLOW}[2/3] Running tests...${NC}"

case "$TEST_TARGET" in
  unit)
    echo "Running unit tests only (no integration)"
    docker run --rm \
      -v "$PROJECT_ROOT/data:/home/pwuser/data" \
      a11y-scanner-test:latest \
      pytest -v tests/ -k "not integration" $PYTEST_ARGS
    ;;

  integration)
    echo "Running integration tests only"
    docker run --rm \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$PROJECT_ROOT/data:/home/pwuser/data" \
      --user root \
      a11y-scanner-test:latest \
      pytest -v tests/ -k "integration" $PYTEST_ARGS
    ;;

  all)
    echo "Running all tests"
    docker run --rm \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$PROJECT_ROOT/data:/home/pwuser/data" \
      --user root \
      a11y-scanner-test:latest \
      pytest -v $PYTEST_ARGS
    ;;

  coverage)
    echo "Running tests with coverage report"
    docker run --rm \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "$PROJECT_ROOT/data:/home/pwuser/data" \
      -v "$PROJECT_ROOT/htmlcov:/home/pwuser/htmlcov" \
      --user root \
      a11y-scanner-test:latest \
      pytest -v --cov=src --cov-report=html --cov-report=term $PYTEST_ARGS
    ;;

  *)
    echo -e "${RED}Unknown test target: $TEST_TARGET${NC}"
    echo "Usage: $0 [unit|integration|all|coverage] [additional pytest args]"
    exit 1
    ;;
esac

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
  echo -e "\n${GREEN}[3/3] ✓ All tests passed!${NC}"
else
  echo -e "\n${RED}[3/3] ✗ Tests failed with exit code $TEST_EXIT_CODE${NC}"
  exit $TEST_EXIT_CODE
fi
