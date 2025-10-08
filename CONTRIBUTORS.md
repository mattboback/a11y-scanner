# Contributors

Thanks to everyone investing time in `a11y-scanner`. Add yourself in a pull
request after your first contribution so the list stays up to date.

## Core Team

- Matt — project creator and maintainer (`pyproject.toml` author).

## How to Contribute

1. Discuss substantial changes in an issue before opening a pull request.
2. Fork the repository and work from a feature branch.
3. Follow the workflow documented in `docs/development-guide.md`:
   - create/activate the local virtual environment
   - run `pip install -e ".[dev]"`
   - execute unit tests and linting locally
4. Run Docker-backed integration tests (`python -m scanner.container.integration`)
   when changing the container, scanning pipeline, or Playwright services.
5. Update documentation and this file as part of your PR when applicable.

## Pull Request Expectations

- Include focused commits with descriptive messages.
- Link related issues in the PR description.
- Provide context for UI-facing changes (screenshots of `data/reports/latest.html`
  or sample JSON artifacts).
- Ensure CI passes (GitHub Actions run linting and tests automatically).

## Code of Conduct

Treat all contributors and users with respect. Be patient with questions and
assume positive intent. If a situation escalates, contact the maintainer directly
before continuing the discussion in public threads.
