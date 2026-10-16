"""Runtime configuration read from environment variables (SRS addendum §8.4)."""

import os
from dataclasses import dataclass

DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def _parse_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            cors_origins=_parse_origins(os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)),
        )
