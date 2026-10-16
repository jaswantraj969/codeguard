"""Worker tasks injected into the API in tests (test hooks, addendum TC-31/TC-33).

They must live in an importable module: workers are separate processes, and
the task is sent to them by reference.
"""

import os
import time

from codeguard.api.worker import analyze_to_json


def task_with_hooks(source: str, toggles: dict[str, bool], analysis_id: str) -> str:
    """The real analysis, unless the source contains a marker word."""
    if "HOOK_SLOW" in source:
        time.sleep(60)  # always exceeds the test timeout; the worker is killed
    if "HOOK_NAP" in source:
        time.sleep(1.5)  # holds a slot long enough to fill the queue
    if "HOOK_FAIL" in source:
        raise RuntimeError("secret internal detail")
    if "HOOK_CRASH" in source:
        os._exit(1)  # the worker process dies
    return analyze_to_json(source, toggles, analysis_id)
