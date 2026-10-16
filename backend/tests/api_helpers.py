"""Helpers for API tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from codeguard.api.app import create_app
from codeguard.api.config import Settings
from tests.api_tasks import task_with_hooks

ANALYZE = "/api/v1/analyze"

# Real worker processes; a short timeout keeps the timeout test fast.
TEST_SETTINGS = Settings(
    cors_origins=("http://localhost:5173",),
    analysis_timeout_seconds=3.0,
    max_concurrent_analyses=2,
    queue_wait_seconds=3.0,
    rate_limit_per_minute=0,
)


@contextmanager
def api_client(settings: Settings = TEST_SETTINGS) -> Iterator[TestClient]:
    """A client whose app runs its lifespan, so the worker pool really starts."""
    app = create_app(settings, task=task_with_hooks)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def analyze_body(source: str, **extra: Any) -> dict[str, Any]:
    return {"language": "c", "source": source, **extra}


def error_of(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message", "analysis_id"}
    return dict(body["error"])
