"""Write real API responses as JSON fixtures for the frontend tests.

Run from backend/ after changing the response format:

    python scripts/export_frontend_fixtures.py

The frontend tests then exercise the actual API contract, not hand-written data.
"""

import json
from pathlib import Path

from codeguard.report import build_report

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "fixtures"

SAMPLES = {
    # The SRS demo (SRS §3.13): one unused variable, one constant condition.
    "srs-demo": (
        "#include <stdio.h>\n"
        "\n"
        "int main(void) {\n"
        "    int x = 10;\n"
        "    int unused = 50;\n"
        "\n"
        "    if (10 > 5) {\n"
        '        printf("x is %d\\n", x);\n'
        "    }\n"
        "    return 0;\n"
        "}\n"
    ),
    # One of each severity, a semantic error, and a nested scope.
    "mixed": (
        "int total;\n"
        "int main(void) {\n"
        "    int total = 1 + 2;\n"
        "    for (int i = 0; i < 3; i++) { total += i; }\n"
        "    return total / 0;\n"
        "}\n"
    ),
    # Syntax errors: later stages skipped, no AST or symbols.
    "syntax-errors": "int main(void) {\n    int x = 5\n    int y = (x + 2;\n    return 0;\n}\n",
    # A diagnostic message that contains markup-like text.
    "markup": 'int main(void) {\n    int img = 1;\n    return "<img src=x onerror=alert(1)>";\n}\n',
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source in SAMPLES.items():
        body = json.loads(build_report(source).to_json(f"fixture-{name}"))
        body["statistics"]["duration_ms"] = 1.0  # stable across runs
        (OUT / f"{name}.json").write_text(
            json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {name}.json")


if __name__ == "__main__":
    main()
