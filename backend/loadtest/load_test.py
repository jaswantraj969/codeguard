"""Load test for a running CodeGuard API (SRS addendum §10.3). Not part of CI.

Usage, from backend/ with the server running:

    python loadtest/load_test.py                      # http://localhost:8000
    python loadtest/load_test.py --url https://codeguard-api.onrender.com

It warms the server up, then measures:
  * 20 concurrent small analyses, repeated --rounds times (TC-12);
  * analyses of about 1 KB, 10 KB, 100 KB and 500 KB of realistic C.

It reports P50, P95, P99 and max latency, plus any non-200 responses. The SRS
targets (P95 <= 2 s, P99 <= 5 s on a warm server) are checked for "normal"
analyses: the small, 1 KB and 10 KB scenarios. The larger inputs are reported
for information. The exit code is 1 if a normal scenario misses a target.
"""

import argparse
import asyncio
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

P95_TARGET_S = 2.0
P99_TARGET_S = 5.0

SMALL_SOURCE = "int main(void) {\n    int x = 1;\n    return x;\n}\n"

CHUNK = """/* helper {n} */
int add_{n}(int a, int b) {{
    int total = a + b * 2;
    if (total >= 10 && a != 0) {{ printf("big %d\\n", total); }}
    for (int i = 0; i < 3; i++) {{ total += 'x' - 1; }}
    return total;
}}
"""


def c_source(target_bytes: int) -> str:
    """Valid C of roughly `target_bytes` (never over 512,000 bytes)."""
    parts, size, n = [], 0, 0
    while size < target_bytes:
        chunk = CHUNK.format(n=n)
        if size + len(chunk) > min(target_bytes, 512_000):
            break
        parts.append(chunk)
        size += len(chunk)
        n += 1
    return "".join(parts) or SMALL_SOURCE


@dataclass
class Scenario:
    name: str
    normal: bool  # subject to the SRS latency targets
    latencies: list[float] = field(default_factory=list)
    statuses: Counter[int] = field(default_factory=Counter)

    def percentile(self, p: float) -> float:
        """Nearest-rank percentile over successful requests."""
        if not self.latencies:
            return math.nan
        ordered = sorted(self.latencies)
        return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]

    @property
    def meets_targets(self) -> bool:
        return (
            set(self.statuses) == {200}
            and self.percentile(95) <= P95_TARGET_S
            and self.percentile(99) <= P99_TARGET_S
        )


async def analyze(client: httpx.AsyncClient, source: str, scenario: Scenario) -> None:
    started = time.perf_counter()
    response = await client.post("/api/v1/analyze", json={"language": "c", "source": source})
    elapsed = time.perf_counter() - started
    scenario.statuses[response.status_code] += 1
    if response.status_code == 200:
        scenario.latencies.append(elapsed)


async def warm_up(client: httpx.AsyncClient) -> None:
    started = time.perf_counter()
    response = await client.get("/api/v1/health", timeout=120)
    response.raise_for_status()
    await analyze(client, SMALL_SOURCE, Scenario("warm-up", normal=False))
    print(f"Server warm after {time.perf_counter() - started:.1f} s")


async def run(url: str, rounds: int, repeats: int) -> list[Scenario]:
    async with httpx.AsyncClient(base_url=url, timeout=60) as client:
        await warm_up(client)
        concurrent = Scenario("20 concurrent small", normal=True)
        for _ in range(rounds):
            await asyncio.gather(*(analyze(client, SMALL_SOURCE, concurrent) for _ in range(20)))
        scenarios = [concurrent]
        for label, size, normal in (
            ("1 KB", 1_000, True),
            ("10 KB", 10_000, True),
            ("100 KB", 100_000, False),
            ("500 KB", 500_000, False),
        ):
            source = c_source(size)
            scenario = Scenario(f"{label} ({len(source.encode()):,} B)", normal=normal)
            for _ in range(repeats):
                await analyze(client, source, scenario)
            scenarios.append(scenario)
        return scenarios


def report(scenarios: list[Scenario]) -> bool:
    header = f"{'scenario':<26}{'ok':>6}{'p50 s':>8}{'p95 s':>8}{'p99 s':>8}{'max s':>8}  other"
    print(header)
    print("-" * len(header))
    all_ok = True
    for s in scenarios:
        other = ", ".join(f"{code}x{n}" for code, n in sorted(s.statuses.items()) if code != 200)
        verdict = ""
        if s.normal:
            verdict = "  meets targets" if s.meets_targets else "  MISSES targets"
            all_ok &= s.meets_targets
        print(
            f"{s.name:<26}{len(s.latencies):>6}{s.percentile(50):>8.2f}{s.percentile(95):>8.2f}"
            f"{s.percentile(99):>8.2f}{max(s.latencies, default=math.nan):>8.2f}"
            f"  {other or '-'}{verdict}"
        )
    print(f"\nTargets for normal analyses: P95 <= {P95_TARGET_S} s, P99 <= {P99_TARGET_S} s.")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--rounds", type=int, default=5, help="rounds of 20 concurrent requests")
    parser.add_argument("--repeats", type=int, default=5, help="requests per input size")
    args = parser.parse_args()
    scenarios = asyncio.run(run(args.url.rstrip("/"), args.rounds, args.repeats))
    return 0 if report(scenarios) else 1


if __name__ == "__main__":
    sys.exit(main())
