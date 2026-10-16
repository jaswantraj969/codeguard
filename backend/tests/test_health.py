"""GET /api/v1/health: readiness and CORS."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from codeguard.api.app import create_app
from codeguard.api.config import Settings
from codeguard.api.worker import AnalysisPool, PoolNotReady
from tests.api_helpers import api_client

HEALTH = "/api/v1/health"


def client_without_startup(origins: tuple[str, ...] = ("http://localhost:5173",)) -> TestClient:
    """The app as it is before startup has run: no worker pool yet."""
    return TestClient(create_app(Settings(cors_origins=origins)))


def test_health_is_503_until_the_worker_pool_is_ready() -> None:
    response = client_without_startup().get(HEALTH)

    assert response.status_code == 503
    assert response.json() == {"status": "starting"}


def test_health_is_ok_once_every_worker_has_run_an_analysis() -> None:
    settings = Settings(max_concurrent_analyses=2, rate_limit_per_minute=0)
    with api_client(settings) as client:
        response = client.get(HEALTH)
        pool = client.app.state.pool  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert pool.ready
    assert len(pool.worker_pids) == 2  # both workers answered a warm-up analysis


def test_warm_up_that_cannot_finish_raises() -> None:
    async def attempt() -> None:
        pool = AnalysisPool(Settings(max_concurrent_analyses=1))
        try:
            await pool.warm_up(timeout=0.001)
        finally:
            pool.close()
        assert not pool.ready

    with pytest.raises(PoolNotReady):
        asyncio.run(attempt())


def test_cors_allows_configured_origin() -> None:
    response = client_without_startup().get(HEALTH, headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unlisted_origin() -> None:
    response = client_without_startup().get(HEALTH, headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example , ,https://b.example ")

    assert Settings.from_env().cors_origins == ("https://a.example", "https://b.example")
