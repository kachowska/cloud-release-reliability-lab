from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness_returns_live(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_readiness_returns_ready(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_operational_headers_include_request_and_release(client: TestClient) -> None:
    response = client.get("/health/live", headers={"x-request-id": "drill-123"})

    assert response.headers["x-request-id"] == "drill-123"
    assert response.headers["x-release-version"] == "2026.09.16-test"

