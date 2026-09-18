# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade "pip==25.2" \
    && /opt/venv/bin/pip install --requirement requirements.txt

FROM python:3.12.11-slim-bookworm AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RELEASE_SERVICE_NAME=release-status-service \
    RELEASE_VERSION=container-dev \
    RELEASE_COMMIT_SHA=unknown \
    RELEASE_ENVIRONMENT=container \
    RELEASE_FORCE_NOT_READY=false

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app app ./app

USER app:app
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2).read()"]

ENTRYPOINT ["uvicorn"]
CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

