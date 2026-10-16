"""API: validation, error envelope, responses, logging and security (addendum §8)."""

import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from codeguard.api.config import DEFAULT_MAX_SOURCE_BYTES as MAX_SOURCE_BYTES
from codeguard.api.config import Settings
from tests.api_helpers import ANALYZE, TEST_SETTINGS, analyze_body, api_client, error_of
from tests.c_samples import worst_case

MAX_BODY_BYTES = TEST_SETTINGS.max_body_bytes

VALID = "int main(void) {\n    int x = 10;\n    return x;\n}\n"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with api_client() as test_client:
        yield test_client


def sized_source(total_bytes: int, filler: str = "x") -> str:
    """A cheap-to-analyze source of exactly `total_bytes` UTF-8 bytes."""
    head, tail = "int main(void) { return 0; }\n/*", "*/\n"
    fixed = len((head + tail).encode())
    count, remainder = divmod(total_bytes - fixed, len(filler.encode()))
    source = head + filler * count + " " * remainder + tail
    assert len(source.encode()) == total_bytes
    return source


# --- success --------------------------------------------------------------------


def test_analyze_returns_the_report(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body(VALID))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert list(body) == [
        "analysis_id",
        "status",
        "diagnostics",
        "statistics",
        "tokens",
        "ast",
        "symbols",
        "truncated",
    ]
    uuid.UUID(body["analysis_id"])
    assert [s["status"] for s in body["status"]] == ["passed"] * 4


def test_each_request_gets_its_own_analysis_id(client: TestClient) -> None:
    ids = {client.post(ANALYZE, json=analyze_body(VALID)).json()["analysis_id"] for _ in range(3)}
    assert len(ids) == 3


def test_code_problems_are_a_200_with_diagnostics(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body("int main(void) { x = ; @ }"))
    assert response.status_code == 200
    assert response.json()["diagnostics"][0]["rule_id"] == "LEX-INVALID-CHAR"


def test_rules_toggle_through_the_api(client: TestClient) -> None:
    source = "int main(void) { int unused = 1; return 0; }"
    on = client.post(ANALYZE, json=analyze_body(source)).json()
    off = client.post(ANALYZE, json=analyze_body(source, rules={"SEM-UNUSED": False})).json()
    assert [d["rule_id"] for d in on["diagnostics"]] == ["SEM-UNUSED"]
    assert off["diagnostics"] == []


def test_unknown_extra_fields_are_ignored(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body(VALID, editor="monaco"))
    assert response.status_code == 200


def test_worst_case_in_the_real_worker_process(client: TestClient) -> None:
    # TC-38: the deepest allowed input runs in a pebble worker with no RecursionError.
    response = client.post(ANALYZE, json=analyze_body(worst_case()))
    assert response.status_code == 200
    body = response.json()
    assert [s["status"] for s in body["status"]] == ["passed"] * 4
    assert body["diagnostics"] == []


# --- size limits (TC-09, TC-10) ----------------------------------------------------


def test_source_of_exactly_the_limit_is_accepted(client: TestClient) -> None:
    # TC-09
    response = client.post(ANALYZE, json=analyze_body(sized_source(MAX_SOURCE_BYTES)))
    assert response.status_code == 200


def test_source_one_byte_over_the_limit_is_rejected(client: TestClient) -> None:
    # TC-10
    response = client.post(ANALYZE, json=analyze_body(sized_source(MAX_SOURCE_BYTES + 1)))
    assert response.status_code == 413
    error = error_of(response)
    assert error["code"] == "INPUT_TOO_LARGE"
    assert "512,001" in error["message"]


def test_size_is_measured_in_utf8_bytes_not_characters(client: TestClient) -> None:
    exact = sized_source(MAX_SOURCE_BYTES, filler="é")
    assert len(exact) < MAX_SOURCE_BYTES
    assert client.post(ANALYZE, json=analyze_body(exact)).status_code == 200
    over = sized_source(MAX_SOURCE_BYTES + 2, filler="é")
    assert client.post(ANALYZE, json=analyze_body(over)).status_code == 413


def test_oversized_body_is_rejected_before_parsing(client: TestClient) -> None:
    response = client.post(
        ANALYZE,
        content=b"{" + b" " * MAX_BODY_BYTES + b"}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert error_of(response)["code"] == "INPUT_TOO_LARGE"


def test_escaped_source_under_the_limit_is_never_blocked_by_the_body_cap(
    client: TestClient,
) -> None:
    # Every character JSON-escaped as \u00XX: 6 bytes each on the wire.
    source = sized_source(MAX_SOURCE_BYTES, filler="\x01")
    body = json.dumps(analyze_body(source)).encode()
    assert len(body) <= MAX_BODY_BYTES
    response = client.post(ANALYZE, content=body, headers={"content-type": "application/json"})
    assert response.status_code == 200


# --- request errors ------------------------------------------------------------------


def post_raw(client: TestClient, content: bytes | str) -> Any:
    return client.post(ANALYZE, content=content, headers={"content-type": "application/json"})


@pytest.mark.parametrize(
    "content",
    [
        "{not json",  # TC-11
        "",
        "[1, 2]",
        '"just a string"',
        '{"language": "c"}',
        '{"source": "int x;"}',
        '{"language": "c", "source": 42}',
        '{"language": 7, "source": "int x;"}',
        '{"language": "c", "source": null}',
        '{"language": "c", "source": "int x;", "rules": []}',
        '{"language": "c", "source": "int x;", "rules": {"SEM-UNUSED": "no"}}',
        '{"language": "c", "source": "int x;", "rules": {"SEM-UNUSED": 0}}',
        '{"language": "c", "source": "int x;", "rules": {"SEM-NOPE": false}}',
        '{"language": "c", "source": "int x;", "rules": {"SYN-MISSING-SEMICOLON": false}}',
        '{"language": "c", "source": "int x;", "rules": {"SEM-BREAK-CONTEXT": false}}',
        '{"language": "c", "source": "int x; \\ud800"}',  # lone surrogate
    ],
)
def test_malformed_requests_are_400_invalid_request(client: TestClient, content: str) -> None:
    response = post_raw(client, content)
    assert response.status_code == 400, response.text
    assert error_of(response)["code"] == "INVALID_REQUEST"


def test_validation_messages_do_not_echo_the_input(client: TestClient) -> None:
    secret = "TOP-SECRET-SOURCE"
    response = post_raw(client, json.dumps({"language": "c", "source": [secret]}))
    assert response.status_code == 400
    assert secret not in response.text


@pytest.mark.parametrize("source", ["", "   ", "\n\t\r\n "])
def test_empty_source_is_400_input_empty(client: TestClient, source: str) -> None:
    # TC-29
    response = client.post(ANALYZE, json=analyze_body(source))
    assert response.status_code == 400
    assert error_of(response)["code"] == "INPUT_EMPTY"


@pytest.mark.parametrize("language", ["python", "C", "cpp", ""])
def test_unsupported_language_is_422(client: TestClient, language: str) -> None:
    # TC-30
    response = client.post(ANALYZE, json={"language": language, "source": VALID})
    assert response.status_code == 422
    assert error_of(response)["code"] == "UNSUPPORTED_LANGUAGE"


def test_language_is_checked_before_size_and_emptiness(client: TestClient) -> None:
    response = client.post(ANALYZE, json={"language": "python", "source": ""})
    assert error_of(response)["code"] == "UNSUPPORTED_LANGUAGE"


def test_size_is_checked_before_emptiness(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body(" " * (MAX_SOURCE_BYTES + 1)))
    assert error_of(response)["code"] == "INPUT_TOO_LARGE"


def test_error_envelope_carries_an_analysis_id(client: TestClient) -> None:
    error = error_of(client.post(ANALYZE, json=analyze_body("")))
    uuid.UUID(error["analysis_id"])


def test_get_on_analyze_is_not_allowed(client: TestClient) -> None:
    assert client.get(ANALYZE).status_code == 405


# --- failures, timeout and security ---------------------------------------------------


def test_slow_analysis_times_out_with_503_and_the_service_recovers(client: TestClient) -> None:
    # TC-31, via the HOOK_SLOW test hook rather than a real slow input.
    response = client.post(ANALYZE, json=analyze_body("int x; // HOOK_SLOW"))
    assert response.status_code == 503
    error = error_of(response)
    assert error["code"] == "ANALYSIS_TIMEOUT"
    assert "3 seconds" in error["message"]
    # The timed-out worker was killed and replaced; analyses still work.
    assert client.post(ANALYZE, json=analyze_body(VALID)).status_code == 200


def test_internal_failure_is_a_500_without_details(client: TestClient) -> None:
    # TC-33
    response = client.post(ANALYZE, json=analyze_body("int x; // HOOK_FAIL"))
    assert response.status_code == 500
    error = error_of(response)
    assert error["code"] == "INTERNAL_ERROR"
    assert error["analysis_id"] in error["message"]
    assert "Traceback" not in response.text
    assert "secret internal detail" not in response.text
    assert "RuntimeError" not in response.text


def test_crashed_worker_is_a_500_and_does_not_take_the_service_down(client: TestClient) -> None:
    response = client.post(ANALYZE, json=analyze_body("int x; // HOOK_CRASH"))
    assert response.status_code == 500
    assert error_of(response)["code"] == "INTERNAL_ERROR"
    assert client.post(ANALYZE, json=analyze_body(VALID)).status_code == 200


def test_script_payload_comes_back_as_inert_json_text(client: TestClient) -> None:
    # TC-34 (API part): the payload is data inside a JSON string, never markup.
    source = 'int main(void) { puts("<script>alert(1)</script>"); return 0; }'
    response = client.post(ANALYZE, json=analyze_body(source))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    lexemes = [t["lexeme"] for t in response.json()["tokens"]]
    assert '"<script>alert(1)</script>"' in lexemes


def test_logs_have_length_and_hash_but_never_the_source(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="codeguard.api")
    marker = "int this_is_private_code_42 = 1;"
    client.post(ANALYZE, json=analyze_body(marker))
    client.post(ANALYZE, json=analyze_body(marker + " // HOOK_FAIL"))
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "source_sha256=" in text and f"source_bytes={len(marker)}" in text
    assert "this_is_private_code_42" not in text
    assert "outcome=ok" in text
    failure = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert failure and failure[0].exc_info is not None  # details stay server-side


def test_rejected_requests_log_no_fake_source_size(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="codeguard.api")
    client.post(ANALYZE, json={"language": "python", "source": "x"})
    (record,) = [r for r in caplog.records if "outcome=UNSUPPORTED_LANGUAGE" in r.getMessage()]
    assert "source=unread" in record.getMessage()


# --- configurable size limit (MAX_SOURCE_BYTES) ----------------------------------------


def test_config_endpoint_reports_the_limit(client: TestClient) -> None:
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    assert response.json() == {"max_source_bytes": MAX_SOURCE_BYTES}


def test_a_lowered_limit_is_enforced_and_reported() -> None:
    settings = Settings(max_concurrent_analyses=1, rate_limit_per_minute=0, max_source_bytes=1_000)
    with api_client(settings) as client:
        config = client.get("/api/v1/config").json()
        at_limit = client.post(ANALYZE, json=analyze_body(sized_source(1_000)))
        over = client.post(ANALYZE, json=analyze_body(sized_source(1_001)))
        body_over = client.post(
            ANALYZE,
            content=b"{" + b" " * settings.max_body_bytes + b"}",
            headers={"content-type": "application/json"},
        )
    assert config == {"max_source_bytes": 1_000}
    assert at_limit.status_code == 200
    assert over.status_code == 413
    assert error_of(over)["message"] == "Source is 1,001 bytes; the limit is 1,000."
    assert body_over.status_code == 413
    assert settings.max_body_bytes == 1_000 * 6 + 65_536
