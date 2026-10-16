"""Analysis worker pool (SRS addendum §7).

Analyses run in a small pool of long-lived worker processes (pebble), sized to
the concurrency limit. A worker that exceeds the timeout is killed and replaced:
a CPU-bound thread cannot be killed, so a thread pool would not be enough.

A semaphore with the same size bounds the analyses in flight. A request waits
up to `queue_wait_seconds` for a free slot before being refused.

Workers only ever receive the source as a string and run the pure-Python
analyzer on it. Nothing here executes or compiles the submitted code.
"""

import asyncio
import logging
import multiprocessing
import os
import time
from collections.abc import Callable, Mapping
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, cast

from pebble import ProcessExpired, ProcessPool

from codeguard.api.config import Settings
from codeguard.report import build_report

# (source, rule toggles, analysis_id) -> 200 response body as JSON text.
AnalysisTask = Callable[[str, dict[str, bool], str], str]

logger = logging.getLogger("codeguard.api")

WARM_UP_SOURCE = "int main(void) { int x = 1 + 2; return x; }"
WARM_UP_HOLD_SECONDS = 0.3  # keeps a worker busy so the next ping lands on another
WARM_UP_TIMEOUT_SECONDS = 120.0


def analyze_to_json(source: str, toggles: dict[str, bool], analysis_id: str) -> str:
    """Runs inside a worker process. Returns JSON text, which pickles cheaply."""
    return build_report(source, toggles).to_json(analysis_id)


def warm_up_task(hold_seconds: float) -> int:
    """Runs inside a worker: a real analysis (imports and all), then a short hold."""
    build_report(WARM_UP_SOURCE)
    time.sleep(hold_seconds)
    return os.getpid()


class PoolNotReady(Exception):
    """The workers did not all answer within the warm-up timeout."""


class AnalysisTimeout(Exception):
    """The analysis exceeded the timeout; its worker was killed and replaced."""


class PoolBusy(Exception):
    """No analysis slot became free within the queue wait."""


class WorkerCrashed(Exception):
    """The worker process died unexpectedly."""


class AnalysisPool:
    def __init__(self, settings: Settings, task: AnalysisTask = analyze_to_json) -> None:
        self.settings = settings
        self.task = task
        # "spawn" behaves the same on Windows (development) and Linux (Render),
        # and never forks a process that has server threads running.
        self.pool = ProcessPool(
            max_workers=settings.max_concurrent_analyses,
            context=cast(Any, multiprocessing.get_context("spawn")),  # pebble stub is narrow
        )
        self.slots = asyncio.Semaphore(settings.max_concurrent_analyses)
        self.ready = False
        self.worker_pids: set[int] = set()

    async def warm_up(
        self,
        timeout: float = WARM_UP_TIMEOUT_SECONDS,
        hold_seconds: float = WARM_UP_HOLD_SECONDS,
    ) -> None:
        """Return only once every worker process has completed a real analysis.

        Called during startup, before the server accepts connections, so a cold
        start never routes requests (or the health check) to a pool that is not
        ready. Pings are sent in rounds until each worker has answered one.
        """
        size = self.settings.max_concurrent_analyses
        deadline = time.monotonic() + timeout
        while len(self.worker_pids) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PoolNotReady(
                    f"only {len(self.worker_pids)} of {size} workers answered within {timeout:g} s"
                )
            futures = [
                asyncio.wrap_future(self.pool.submit(warm_up_task, remaining, hold_seconds))
                for _ in range(size)
            ]
            try:
                pids = await asyncio.wait_for(asyncio.gather(*futures), remaining)
            except (TimeoutError, FutureTimeoutError):
                continue  # the deadline check above reports it
            self.worker_pids.update(pids)
        self.ready = True
        logger.info("worker pool ready: %d workers %s", size, sorted(self.worker_pids))

    async def run(self, source: str, toggles: Mapping[str, bool], analysis_id: str) -> str:
        try:
            await asyncio.wait_for(self.slots.acquire(), self.settings.queue_wait_seconds)
        except TimeoutError:
            raise PoolBusy from None
        try:
            future = self.pool.submit(
                self.task,
                self.settings.analysis_timeout_seconds,
                source,
                dict(toggles),
                analysis_id,
            )
            try:
                return await asyncio.wrap_future(future)
            except FutureTimeoutError:
                raise AnalysisTimeout from None
            except ProcessExpired as error:
                raise WorkerCrashed(str(error)) from error
        finally:
            self.slots.release()

    def close(self) -> None:
        self.pool.stop()  # type: ignore[no-untyped-call]
        self.pool.join()
