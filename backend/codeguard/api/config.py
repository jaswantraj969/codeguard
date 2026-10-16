"""Runtime configuration read from environment variables (SRS addendum §8.4)."""

import os
from dataclasses import dataclass

DEFAULT_CORS_ORIGINS = "http://localhost:5173"

DEFAULT_MAX_SOURCE_BYTES = 512_000

# JSON can escape one source byte as a six-character unicode escape, so a body
# this large can always carry a source at the limit; 64 KiB covers the rest.
JSON_ESCAPE_FACTOR = 6
ENVELOPE_ALLOWANCE_BYTES = 65_536


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
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES  # UTF-8 bytes of the `source` field

    @property
    def max_body_bytes(self) -> int:
        """Request bodies above this are refused before JSON parsing (addendum §7)."""
        return self.max_source_bytes * JSON_ESCAPE_FACTOR + ENVELOPE_ALLOWANCE_BYTES

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            cors_origins=_parse_origins(os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
            analysis_timeout_seconds=_env_number("ANALYSIS_TIMEOUT_SECONDS", 5.0, float, 0.01),
            max_concurrent_analyses=_env_number("MAX_CONCURRENT_ANALYSES", 2, int, 1),
            queue_wait_seconds=_env_number("QUEUE_WAIT_SECONDS", 3.0, float, 0.0),
            rate_limit_per_minute=_env_number("RATE_LIMIT_PER_MINUTE", 30, int, 0),
            trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
            max_source_bytes=_env_number("MAX_SOURCE_BYTES", DEFAULT_MAX_SOURCE_BYTES, int, 1),
        )
