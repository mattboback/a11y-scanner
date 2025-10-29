
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

USER root
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN rm -rf /var/lib/apt/lists/*

USER pwuser
WORKDIR /home/pwuser

# Copy project files
COPY --chown=pwuser:pwuser pyproject.toml uv.lock ./
COPY --chown=pwuser:pwuser src ./src

# Install dependencies with uv
RUN uv sync --frozen --no-dev

# Add uv-managed bin directory to PATH
ENV PATH="/home/pwuser/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "scanner.main"]
