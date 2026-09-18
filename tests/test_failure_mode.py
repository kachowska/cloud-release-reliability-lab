from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_forced_readiness_failure_keeps_liveness_healthy() -> None:
    settings = Settings(
        version="failed-candidate",
        commit_sha="badcafe",
        environment="test",
        force_not_ready=True,
        failure_reason="injected dependency failure",
    )

    with TestClient(create_app(settings)) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert ready.status_code == 503
    assert ready.json() == {
        "status": "not_ready",
        "reason": "injected dependency failure",
    }


def test_metrics_reflect_forced_not_ready_state() -> None:
    settings = Settings(force_not_ready=True)

    with TestClient(create_app(settings)) as client:
        metrics = client.get("/metrics")

    assert "release_service_ready 0" in metrics.text

