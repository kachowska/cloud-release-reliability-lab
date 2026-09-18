from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        service_name="release-status-test",
        version="2026.09.16-test",
        commit_sha="abc1234",
        environment="test",
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client

