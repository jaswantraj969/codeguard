"""Runtime configuration read from environment variables (SRS addendum §8.4)."""

import os
from dataclasses import dataclass

DEFAULT_CORS_ORIGINS = "http://localhost:5173"

MAX_SOURCE_BYTES = 512_000
MAX_BODY_BYTES = 3_200_000


def _parse_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def _env_number[N: (int, float)](name: str, default: N, kind: type[N], minimum: N) -> N:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = kind(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    if raw.strip().lower() in ("1", "true", "yes", "on"):
        return True
    if raw.strip().lower() in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...] = (DEFAULT_CORS_ORIGINS,)
    analysis_timeout_seconds: float = 5.0
    max_concurrent_analyses: int = 2
    queue_wait_seconds: float = 3.0
    rate_limit_per_minute: int = 30  # 0 disables rate limiting
    trust_proxy_headers: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            cors_origins=_parse_origins(os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
            analysis_timeout_seconds=_env_number("ANALYSIS_TIMEOUT_SECONDS", 5.0, float, 0.01),
            max_concurrent_analyses=_env_number("MAX_CONCURRENT_ANALYSES", 2, int, 1),
            queue_wait_seconds=_env_number("QUEUE_WAIT_SECONDS", 3.0, float, 0.0),
            rate_limit_per_minute=_env_number("RATE_LIMIT_PER_MINUTE", 30, int, 0),
            trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
        )
