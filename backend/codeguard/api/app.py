"""FastAPI application: routes, validation, error envelope (SRS addendum §8).

Checks on POST /api/v1/analyze run in this order, cheapest first (§8.3):
rate limit, body size, JSON and schema, language, source size, empty source,
then the queue for an analysis slot.

Problems in the submitted code are a 200 response with diagnostics; only
problems with the request itself are HTTP errors.
"""

import hashlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, ValidationError

from codeguard.api.config import Settings
from codeguard.api.ratelimit import RateLimiter, retry_after_header
from codeguard.api.worker import (
    AnalysisPool,
    AnalysisTask,
    AnalysisTimeout,
    PoolBusy,
    analyze_to_json,
)
from codeguard.errors import HTTP_STATUS, ErrorCode
from codeguard.report import TOGGLEABLE_RULES

API_PREFIX = "/api/v1"

logger = logging.getLogger("codeguard.api")


class AnalyzeRequest(BaseModel):
    """Body of POST /api/v1/analyze. Unknown extra fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    language: StrictStr
    source: StrictStr
    rules: dict[str, StrictBool] | None = None


class ApiError(Exception):
    def __init__(
        self, code: ErrorCode, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_response(
    code: ErrorCode, message: str, analysis_id: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code.value, "message": message, "analysis_id": analysis_id}},
        status_code=HTTP_STATUS[code],
        headers=headers,
    )


def describe_validation_error(error: ValidationError | RequestValidationError) -> str:
    """A short message that never echoes the submitted input back."""
    first: Any = error.errors()[0]
    if first.get("type") == "json_invalid":
        return "The request body is not valid JSON."
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = str(first.get("msg", "Invalid value"))
    return f"Invalid request: {location}: {message}" if location else f"Invalid request: {message}"


async def read_body_limited(request: Request, max_body_bytes: int) -> bytes:
    """Read the body, refusing anything over `max_body_bytes` before parsing it."""
    too_large = ApiError(
        ErrorCode.INPUT_TOO_LARGE, f"The request body is larger than {max_body_bytes:,} bytes."
    )
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_body_bytes:
        raise too_large
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_body_bytes:
            raise too_large
        chunks.append(chunk)
    return b"".join(chunks)


def validate_request(body: bytes, max_source_bytes: int) -> tuple[str, dict[str, bool]]:
    """Steps 3-6 of §8.3. Returns (source, rule toggles) or raises ApiError."""
    try:
        request = AnalyzeRequest.model_validate_json(body)
    except ValidationError as error:
        raise ApiError(ErrorCode.INVALID_REQUEST, describe_validation_error(error)) from None
    toggles = request.rules or {}
    unknown = sorted(rule for rule in toggles if rule not in TOGGLEABLE_RULES)
    if unknown:
        raise ApiError(
            ErrorCode.INVALID_REQUEST,
            f"Unknown or non-toggleable rule IDs in 'rules': {', '.join(unknown)}.",
        )
    if request.language != "c":
        raise ApiError(
            ErrorCode.UNSUPPORTED_LANGUAGE,
            'Only "c" is supported as the language.',
        )
    try:
        size = len(request.source.encode("utf-8"))
    except UnicodeEncodeError:
        raise ApiError(ErrorCode.INVALID_REQUEST, "The source is not valid Unicode text.") from None
    if size > max_source_bytes:
        raise ApiError(
            ErrorCode.INPUT_TOO_LARGE,
            f"Source is {size:,} bytes; the limit is {max_source_bytes:,}.",
        )
    if not request.source.strip():
        raise ApiError(ErrorCode.INPUT_EMPTY, "The source is empty.")
    return request.source, toggles


def client_ip(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        # The right-most entry was added by our own proxy; earlier ones can be spoofed.
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def create_app(settings: Settings | None = None, task: AnalysisTask = analyze_to_json) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = AnalysisPool(settings, task)
        app.state.pool = pool
        try:
            # Runs before uvicorn opens its socket: the server only starts
            # accepting requests (including Render's health check) once every
            # worker has completed a real analysis.
            await pool.warm_up()
            yield
        finally:
            app.state.pool.close()

    app = FastAPI(title="CodeGuard API", version="0.1.0", lifespan=lifespan)
    limiter = RateLimiter(settings.rate_limit_per_minute)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        # FastAPI's default is 422; the API contract says 400 (addendum §8.3, TC-11).
        return error_response(
            ErrorCode.INVALID_REQUEST, describe_validation_error(error), str(uuid.uuid4())
        )

    @app.exception_handler(Exception)
    async def on_unexpected_error(_: Request, error: Exception) -> JSONResponse:
        analysis_id = str(uuid.uuid4())
        logger.error("unhandled error analysis_id=%s", analysis_id, exc_info=error)
        return error_response(
            ErrorCode.INTERNAL_ERROR, internal_error_message(analysis_id), analysis_id
        )

    @app.get(f"{API_PREFIX}/health")
    def health(request: Request) -> JSONResponse:
        # 200 only when the worker pool is warm; 503 makes Render keep waiting.
        pool: AnalysisPool | None = getattr(request.app.state, "pool", None)
        if pool is None or not pool.ready:
            return JSONResponse({"status": "starting"}, status_code=503)
        return JSONResponse({"status": "ok"})

    @app.get(f"{API_PREFIX}/config")
    def config() -> dict[str, int]:
        # Limits the frontend enforces before sending, so both sides always agree.
        return {"max_source_bytes": settings.max_source_bytes}

    @app.post(
        f"{API_PREFIX}/analyze",
        response_class=Response,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": AnalyzeRequest.model_json_schema()}},
            }
        },
    )
    async def analyze(request: Request) -> Response:
        analysis_id = str(uuid.uuid4())
        started = time.perf_counter()
        source: str | None = None  # set once the request has been validated
        try:
            wait = limiter.check(client_ip(request, settings.trust_proxy_headers))
            if wait > 0:
                raise ApiError(
                    ErrorCode.RATE_LIMITED,
                    "Too many analyses from this address. Please wait and try again.",
                    {"Retry-After": retry_after_header(wait)},
                )
            body = await read_body_limited(request, settings.max_body_bytes)
            source, toggles = validate_request(body, settings.max_source_bytes)
            text = await request.app.state.pool.run(source, toggles, analysis_id)
        except ApiError as error:
            log_request(analysis_id, source, error.code.value, started)
            return error_response(error.code, error.message, analysis_id, error.headers)
        except AnalysisTimeout:
            log_request(analysis_id, source, ErrorCode.ANALYSIS_TIMEOUT.value, started)
            return error_response(
                ErrorCode.ANALYSIS_TIMEOUT,
                f"The analysis took longer than {settings.analysis_timeout_seconds:g} seconds "
                "and was stopped. Try a smaller program.",
                analysis_id,
            )
        except PoolBusy:
            log_request(analysis_id, source, ErrorCode.SERVICE_UNAVAILABLE.value, started)
            return error_response(
                ErrorCode.SERVICE_UNAVAILABLE,
                "The server is busy with other analyses. Please try again in a few seconds.",
                analysis_id,
                {"Retry-After": retry_after_header(settings.queue_wait_seconds)},
            )
        except Exception as error:  # includes WorkerCrashed
            logger.error(
                "analysis failed analysis_id=%s %s",
                analysis_id,
                source_fingerprint(source),
                exc_info=error,
            )
            return error_response(
                ErrorCode.INTERNAL_ERROR, internal_error_message(analysis_id), analysis_id
            )
        log_request(analysis_id, source, "ok", started)
        return Response(content=text, media_type="application/json")

    return app


def internal_error_message(analysis_id: str) -> str:
    return f"An unexpected error occurred. Reference: {analysis_id}."


def source_fingerprint(source: str | None) -> str:
    """Length and hash only: full source code is never logged (§7)."""
    if source is None:
        return "source=unread"
    data = source.encode("utf-8", errors="replace")
    return f"source_bytes={len(data)} source_sha256={hashlib.sha256(data).hexdigest()}"


def log_request(analysis_id: str, source: str | None, outcome: str, started: float) -> None:
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "analyze analysis_id=%s outcome=%s %s duration_ms=%.1f",
        analysis_id,
        outcome,
        source_fingerprint(source),
        elapsed_ms,
    )


def configure_logging() -> None:
    root = logging.getLogger("codeguard")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)


app = create_app()

__all__ = ["AnalyzeRequest", "app", "create_app"]
