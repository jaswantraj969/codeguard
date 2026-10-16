"""SRS acceptance tests TC-01 to TC-12, end to end (SRS §9.1, addendum §10.1).

Each test goes through HTTP, the FastAPI app and a real worker process, exactly
as a deployed request would. TC-13 to TC-39 are covered by the stage-level
suites; see the traceability table in docs/SRS_ADDENDUM.md §10.4.
"""

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from codeguard.api.config import DEFAULT_MAX_SOURCE_BYTES as MAX_SOURCE_BYTES
from tests.api_helpers import ANALYZE, analyze_body, api_client, error_of


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with api_client() as test_client:
        yield test_client


def analyze(client: TestClient, source: str) -> dict[str, Any]:
    response = client.post(ANALYZE, json=analyze_body(source))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def stages(body: dict[str, Any]) -> dict[str, str]:
    return {s["stage"]: s["status"] for s in body["status"]}


def findings(body: dict[str, Any]) -> list[tuple[str, str]]:
    return [(d["rule_id"], d["severity"]) for d in body["diagnostics"]]


def in_main(body: str) -> str:
    return "int main(void) {\n" + body + "\n}\n"


def test_tc01_valid_declaration_passes_lexical_and_syntax(client: TestClient) -> None:
    body = analyze(client, "int x = 10;")
    assert stages(body)["lexical"] == "passed"
    assert stages(body)["syntax"] == "passed"
    assert body["diagnostics"] == []


def test_tc02_unused_variable_warning(client: TestClient) -> None:
    body = analyze(client, in_main("int unused = 50;\nreturn 0;"))
    assert findings(body) == [("SEM-UNUSED", "warning")]


def test_tc03_duplicate_variable_error(client: TestClient) -> None:
    body = analyze(client, in_main("int x = 1;\nint x = 2;\nreturn x;"))
    assert findings(body) == [("SEM-DUP", "error")]


def test_tc04_undeclared_variable_error(client: TestClient) -> None:
    body = analyze(client, in_main("y = 5;\nreturn 0;"))
    assert findings(body) == [("SEM-UNDECL", "error")]


def test_tc05_division_by_zero_error_only(client: TestClient) -> None:
    body = analyze(client, in_main("int y = 10 / 0;\nreturn y;"))
    assert findings(body) == [("SEM-DIV0", "error")]


def test_tc06_statement_after_return_is_unreachable(client: TestClient) -> None:
    body = analyze(client, in_main("int x = 1;\nreturn x;\nx = 2;"))
    assert findings(body) == [("SEM-UNREACH", "warning")]


def test_tc07_constant_condition_warning_only(client: TestClient) -> None:
    body = analyze(client, in_main("int x = 0;\nif (10 > 5) {\n  x = 1;\n}\nreturn x;"))
    assert findings(body) == [("SEM-CONSTCOND", "warning")]


def test_tc08_constant_expression_suggestion(client: TestClient) -> None:
    body = analyze(client, in_main("int x = 10 + 20;\nreturn x;"))
    assert findings(body) == [("OPT-CONSTEXPR", "suggestion")]
    assert body["diagnostics"][0]["message"] == "'10 + 20' can be written as 30."


def exact_size_source(total_bytes: int) -> str:
    head, tail = "int main(void) { return 0; }\n/*", "*/\n"
    source = head + "x" * (total_bytes - len(head) - len(tail)) + tail
    assert len(source.encode()) == total_bytes
    return source


def test_tc09_source_at_the_size_limit_is_accepted(client: TestClient) -> None:
    analyze(client, exact_size_source(MAX_SOURCE_BYTES))


def test_tc10_source_over_the_size_limit_is_rejected(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body(exact_size_source(MAX_SOURCE_BYTES + 1)))
    assert response.status_code == 413
    assert error_of(response)["code"] == "INPUT_TOO_LARGE"


def test_tc11_malformed_json_is_http_400(client: TestClient) -> None:
    response = client.post(
        ANALYZE,
        content=b'{"language": "c", "source": ',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert error_of(response)["code"] == "INVALID_REQUEST"


def test_tc12_twenty_concurrent_small_analyses_all_succeed(client: TestClient) -> None:
    source = in_main("int x = 1;\nreturn x;")

    def timed_post(_: int) -> tuple[int, float]:
        started = time.perf_counter()
        status = client.post(ANALYZE, json=analyze_body(source)).status_code
        return status, time.perf_counter() - started

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(timed_post, range(20)))
    assert [status for status, _ in results] == [200] * 20
    # Latency targets (P95 <= 2 s, P99 <= 5 s) are measured by loadtest/load_test.py
    # against a warm server; here only a generous ceiling guards against hangs.
    assert max(seconds for _, seconds in results) < 10


def test_srs_demonstration_result(client: TestClient) -> None:
    # SRS §3.13: lexical and syntax pass, an unused-variable warning, a
    # constant-condition warning, and statistics.
    source = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        "    int x = 10;\n"
        "    int unused = 50;\n"
        "    if (10 > 5) {\n"
        '        printf("%d\\n", x);\n'
        "    }\n"
        "    return 0;\n"
        "}\n"
    )
    body = analyze(client, source)
    assert stages(body) == {
        "lexical": "passed",
        "syntax": "passed",
        "semantic": "passed",
        "optimizer": "passed",
    }
    assert findings(body) == [("SEM-UNUSED", "warning"), ("SEM-CONSTCOND", "warning")]
    statistics = body["statistics"]
    assert (statistics["variables"], statistics["warnings"], statistics["errors"]) == (2, 2, 0)
