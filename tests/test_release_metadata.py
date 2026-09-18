from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.settings import Settings


def test_version_uses_configured_release_metadata(client: TestClient) -> None:
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "service": "release-status-test",
        "version": "2026.09.16-test",
        "commit_sha": "abc1234",
        "environment": "test",
    }
    assert response.headers["cache-control"] == "no-store"


def test_environment_variables_drive_release_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RELEASE_VERSION", "env-release")
    monkeypatch.setenv("RELEASE_COMMIT_SHA", "feed123")
    monkeypatch.setenv("RELEASE_ENVIRONMENT", "staging")

    settings = Settings()

    assert settings.version == "env-release"
    assert settings.commit_sha == "feed123"
    assert settings.environment == "staging"


def test_blank_release_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        Settings(version="   ")


def test_metrics_are_prometheus_compatible(client: TestClient) -> None:
    client.get("/health/live")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert '# TYPE release_service_info gauge' in response.text
    assert 'version="2026.09.16-test"' in response.text
    assert "release_service_ready 1" in response.text
    assert 'release_http_requests_total{path="/health/live",status="200"} 1' in response.text


def test_openapi_contains_all_operational_endpoints(client: TestClient) -> None:
    paths = set(client.get("/openapi.json").json()["paths"])

    assert {"/health/live", "/health/ready", "/version", "/metrics"} <= paths

