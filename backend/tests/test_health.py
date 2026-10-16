import pytest
from fastapi.testclient import TestClient

from codeguard.api.app import create_app
from codeguard.api.config import Settings


def make_client(origins: tuple[str, ...] = ("http://localhost:5173",)) -> TestClient:
    return TestClient(create_app(Settings(cors_origins=origins)))


def test_health_returns_ok() -> None:
    response = make_client().get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_configured_origin() -> None:
    response = make_client().get("/api/v1/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unlisted_origin() -> None:
    response = make_client().get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_parsed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example , ,https://b.example ")

    assert Settings.from_env().cors_origins == ("https://a.example", "https://b.example")
