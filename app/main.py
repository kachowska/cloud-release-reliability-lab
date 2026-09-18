"""Operational API used by the release reliability lab."""

from __future__ import annotations

import logging
import time
from collections import Counter
from threading import Lock
from typing import Final
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.logging_config import configure_logging
from app.settings import Settings, get_settings

METRICS_MEDIA_TYPE: Final = "text/plain; version=0.0.4; charset=utf-8"
logger = logging.getLogger("release_service")


def _prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class RequestMetrics:
    """Thread-safe request totals sufficient for a small diagnostic service."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: Counter[tuple[str, int]] = Counter()

    def observe(self, path: str, status_code: int) -> None:
        with self._lock:
            self._counts[(path, status_code)] += 1

    def snapshot(self) -> list[tuple[str, int, int]]:
        with self._lock:
            return sorted((path, code, count) for (path, code), count in self._counts.items())


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated app instance, allowing deterministic failure-mode tests."""
    configure_logging()
    runtime_settings = settings or get_settings()
    metrics = RequestMetrics()

    app = FastAPI(
        title="Cloud Release Reliability Lab",
        version=runtime_settings.version,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = runtime_settings
    app.state.metrics = metrics

    @app.middleware("http")
    async def observe_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id", str(uuid4()))
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"path": request.url.path, "request_id": request_id},
            )
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        metrics.observe(request.url.path, response.status_code)
        response.headers["x-request-id"] = request_id
        response.headers["x-release-version"] = runtime_settings.version
        logger.info(
            "request_completed",
            extra={
                "duration_ms": duration_ms,
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
                "status_code": response.status_code,
                "version": runtime_settings.version,
            },
        )
        return response

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> Response:
        if runtime_settings.force_not_ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "reason": runtime_settings.failure_reason},
            )
        return JSONResponse(content={"status": "ready"})

    @app.get("/version", tags=["release"])
    async def version() -> Response:
        return JSONResponse(
            content=runtime_settings.release_metadata(),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/metrics", tags=["observability"])
    async def prometheus_metrics() -> PlainTextResponse:
        labels = ",".join(
            f'{key}="{_prometheus_escape(value)}"'
            for key, value in runtime_settings.release_metadata().items()
        )
        ready_value = 0 if runtime_settings.force_not_ready else 1
        lines = [
            "# HELP release_service_info Immutable release metadata.",
            "# TYPE release_service_info gauge",
            f"release_service_info{{{labels}}} 1",
            "# HELP release_service_ready Whether the instance accepts traffic.",
            "# TYPE release_service_ready gauge",
            f"release_service_ready {ready_value}",
            "# HELP release_http_requests_total HTTP requests observed by path and status.",
            "# TYPE release_http_requests_total counter",
        ]
        lines.extend(
            "release_http_requests_total"
            f'{{path="{_prometheus_escape(path)}",status="{code}"}} {count}'
            for path, code, count in metrics.snapshot()
        )
        return PlainTextResponse("\n".join(lines) + "\n", media_type=METRICS_MEDIA_TYPE)

    return app


app = create_app()
