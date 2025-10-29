
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

ENV VIRTUAL_ENV=/home/pwuser/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip python3.10-venv && \
    rm -rf /var/lib/apt/lists/*

USER pwuser
WORKDIR /home/pwuser

RUN python3 -m venv $VIRTUAL_ENV

COPY --chown=pwuser:pwuser . .

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "scanner.main"]
