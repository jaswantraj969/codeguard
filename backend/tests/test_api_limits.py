"""API: concurrency slots and queue, rate limiting and configuration (addendum §7)."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from codeguard.api.config import Settings
from codeguard.api.ratelimit import RateLimiter, retry_after_header
from tests.api_helpers import ANALYZE, TEST_SETTINGS, analyze_body, api_client, error_of

SMALL = "int main(void) { int x = 1; return x; }"


def test_twenty_concurrent_small_analyses_all_succeed() -> None:
    # TC-12: 2 slots plus the queue absorb 20 simultaneous small requests.
    with api_client() as client, ThreadPoolExecutor(max_workers=20) as executor:
        responses = list(
            executor.map(lambda _: client.post(ANALYZE, json=analyze_body(SMALL)), range(20))
        )
    assert [r.status_code for r in responses] == [200] * 20


def test_requests_beyond_the_queue_wait_get_service_unavailable() -> None:
    settings = Settings(
        analysis_timeout_seconds=5.0,
        max_concurrent_analyses=1,
        queue_wait_seconds=0.2,
        rate_limit_per_minute=0,
    )
    with api_client(settings) as client, ThreadPoolExecutor(max_workers=2) as executor:
        assert client.post(ANALYZE, json=analyze_body(SMALL)).status_code == 200  # warm up
        busy = executor.submit(client.post, ANALYZE, json=analyze_body("int x; // HOOK_NAP"))
        refused = None
        for _ in range(50):  # until the nap holds the only slot
            response = client.post(ANALYZE, json=analyze_body(SMALL))
            if response.status_code == 503:
                refused = response
                break
        assert busy.result().status_code == 200
    assert refused is not None
    assert error_of(refused)["code"] == "SERVICE_UNAVAILABLE"
    assert refused.headers["retry-after"] == "1"


# --- rate limiting ------------------------------------------------------------------


def test_rate_limit_returns_429_with_retry_after() -> None:
    settings = Settings(
        analysis_timeout_seconds=TEST_SETTINGS.analysis_timeout_seconds,
        max_concurrent_analyses=1,
        rate_limit_per_minute=3,
    )
    with api_client(settings) as client:
        codes = [client.post(ANALYZE, json=analyze_body(SMALL)).status_code for _ in range(4)]
        limited = client.post(ANALYZE, json=analyze_body(SMALL))
        health = client.get("/api/v1/health")
    assert codes == [200, 200, 200, 429]
    assert error_of(limited)["code"] == "RATE_LIMITED"
    assert int(limited.headers["retry-after"]) >= 1
    assert health.status_code == 200  # /health is exempt


def test_rate_limit_runs_before_validation() -> None:
    settings = Settings(max_concurrent_analyses=1, rate_limit_per_minute=1)
    with api_client(settings) as client:
        first = client.post(ANALYZE, content=b"{bad json")
        second = client.post(ANALYZE, content=b"{bad json")
    assert (first.status_code, second.status_code) == (400, 429)


def test_forwarded_client_ip_is_used_only_when_trusted() -> None:
    def limited_ips(trust: bool) -> list[int]:
        settings = Settings(
            max_concurrent_analyses=1, rate_limit_per_minute=1, trust_proxy_headers=trust
        )
        with api_client(settings) as client:
            return [
                client.post(
                    ANALYZE,
                    json=analyze_body(SMALL),
                    headers={"x-forwarded-for": f"spoofed, 10.0.0.{n}"},
                ).status_code
                for n in (1, 2)
            ]

    assert limited_ips(trust=True) == [200, 200]  # two different clients
    assert limited_ips(trust=False) == [200, 429]  # the header is ignored


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_token_bucket_refills_over_time() -> None:
    clock = FakeClock()
    limiter = RateLimiter(per_minute=2, clock=clock)
    assert [limiter.check("a"), limiter.check("a")] == [0.0, 0.0]
    wait = limiter.check("a")
    assert wait == pytest.approx(30.0)
    assert limiter.check("b") == 0.0  # clients are independent
    clock.now += 30
    assert limiter.check("a") == 0.0


def test_rate_limit_zero_disables_it() -> None:
    limiter = RateLimiter(per_minute=0)
    assert not limiter.enabled
    assert all(limiter.check("a") == 0.0 for _ in range(100))


@pytest.mark.parametrize(("seconds", "header"), [(0.1, "1"), (1.0, "1"), (29.2, "30")])
def test_retry_after_header(seconds: float, header: str) -> None:
    assert retry_after_header(seconds) == header


# --- configuration ------------------------------------------------------------------


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CORS_ORIGINS",
        "ANALYSIS_TIMEOUT_SECONDS",
        "MAX_CONCURRENT_ANALYSES",
        "QUEUE_WAIT_SECONDS",
        "RATE_LIMIT_PER_MINUTE",
        "TRUST_PROXY_HEADERS",
    ):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env() == Settings()
    assert Settings() == Settings(
        cors_origins=("http://localhost:5173",),
        analysis_timeout_seconds=5.0,
        max_concurrent_analyses=2,
        queue_wait_seconds=3.0,
        rate_limit_per_minute=30,
        trust_proxy_headers=False,
    )


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANALYSIS_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("MAX_CONCURRENT_ANALYSES", "4")
    monkeypatch.setenv("QUEUE_WAIT_SECONDS", "0")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    settings = Settings.from_env()
    assert (
        settings.analysis_timeout_seconds,
        settings.max_concurrent_analyses,
        settings.queue_wait_seconds,
        settings.rate_limit_per_minute,
        settings.trust_proxy_headers,
    ) == (2.5, 4, 0.0, 0, True)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ANALYSIS_TIMEOUT_SECONDS", "soon"),
        ("ANALYSIS_TIMEOUT_SECONDS", "0"),
        ("MAX_CONCURRENT_ANALYSES", "0"),
        ("MAX_CONCURRENT_ANALYSES", "1.5"),
        ("RATE_LIMIT_PER_MINUTE", "-1"),
        ("TRUST_PROXY_HEADERS", "maybe"),
    ],
)
def test_invalid_settings_fail_at_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()


def test_cors_preflight_for_the_frontend_origin() -> None:
    with api_client() as client:
        response = client.options(
            ANALYZE,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
