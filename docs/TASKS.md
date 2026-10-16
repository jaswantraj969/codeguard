# CodeGuard task list

The spec is [SRS_ADDENDUM.md](SRS_ADDENDUM.md). Each phase ends with all tests passing, a commit and a review stop.

## Phase 0: SRS addendum
- [x] Repo initialised; SRS copied to `docs/`
- [x] `docs/SRS_ADDENDUM.md`: subset, EBNF, rules, pipeline, limits, API, tests, limitations, change log
- [x] `CONTRIBUTING.md`: ownership and workflow
- [x] Review amendments 1–6 applied (change log rows 52–57)
- [ ] Supervisor approval of the addendum

## Phase 1: scaffold
- [x] Backend package skeleton, `pyproject.toml`, ruff, mypy, pytest
- [x] FastAPI app with `GET /api/v1/health`, CORS from `CORS_ORIGINS`
- [x] Vite + React + TS app that calls `/health` (`VITE_API_URL`), with ESLint and Vitest
- [x] GitHub Actions CI (backend on Python 3.12 and 3.13; frontend lint, test, build)
- [x] `.gitattributes` (LF), `.python-version` (3.13.5)

## Phase 2: lexer
- [x] Shared diagnostic model (`codeguard/diagnostics.py`)
- [x] Token model
- [x] Lexer: keywords, operators, literals, escapes, comments, preprocessor skip, `#define`
- [x] LEX-* errors and tests (147 lexer tests; 512,000-byte file lexes in ~0.3 s)

## Phase 3: parser
- [x] AST nodes with iterative `walk` / `walk_postorder` / `depth`
- [x] Recursive-descent parser: iterative operator precedence and chains; panic-mode recovery (max 20)
- [x] UNSUPPORTED_CONSTRUCT and NESTING_TOO_DEEP
- [x] Parser tests (161), including the TC-38 worst case under a 500-frame budget (uses ~460)
- [x] TC-38 in the real worker process (Phase 6)

## Phase 4: semantics
- [x] Symbol table and scopes; iterative resolver with read/write counts
- [x] Constant folding (iterative, C semantics)
- [x] SEM-DUP, SEM-UNDECL, SEM-UNUSED, SEM-DIV0, SEM-UNREACH, SEM-CONSTCOND, SEM-SHADOW, SEM-BREAK-CONTEXT
- [x] One diagnostic per declaration (SEM-DUP › SEM-SHADOW › SEM-UNUSED); rule toggles
- [x] Known-library list (`backend/data/known_library_functions.json`)
- [x] Positive and negative tests per rule (203 semantic tests)
- [x] Deployment uses an editable install so `backend/data/` is found (`render.yaml`)

## Phase 5: optimizer and report
- [x] OPT-CONSTEXPR (maximal literal-only expressions; skips SEM-CONSTCOND conditions and division by zero)
- [x] Report builder: statuses, statistics, sorting, toggles (`build_report`)
- [x] Token, AST and symbol serialization; `Report.to_json()` returns JSON text
- [x] AST serialized iteratively; the worker returns a flat string, so `pickle` never recurses

## Phase 6: API
- [x] Validation in the §8.3 order, error envelope, 400 handler (no input echoed)
- [x] pebble worker pool (spawn) with timeout kill/replace, semaphore and queue
- [x] CORS, logging (length + SHA-256 only), per-IP token-bucket rate limiting
- [x] API tests (64): every error row, size boundaries, TC-11/12/31/33/34/38, crash recovery
- [ ] Confirm on Render which `X-Forwarded-For` entry is the real client (Phase 8 checklist)

## Phase 7: frontend
- [x] Monaco bundled locally (lazy chunk, C language only), toolbar, upload checks, examples incl. SRS demo
- [x] Stage bar, diagnostics tabs (syntax errors grouped separately), click-to-line, statistics
- [x] Token table (paged), collapsible AST tree, symbol table by scope
- [x] Accessibility (ARIA tabs, labels, focus, aria-live, Tab-trap hint), wake-up message
- [x] Vitest tests (52) against real API fixtures (`backend/scripts/export_frontend_fixtures.py`)
- [ ] Check the real Monaco editor in a browser: the automated browser could not open localhost here

## Phase 8: acceptance and deploy prep
- [x] TC-01–TC-12 end to end through the API and real workers (`tests/test_acceptance.py`); TC-13–TC-39 in the stage suites
- [x] Load-test script (`backend/loadtest/load_test.py`); local run meets the targets
- [x] `render.yaml` (Render Blueprint), `frontend/vercel.json`
- [x] README (setup, tests, configuration, deploy, limitations) and Mermaid diagrams in `docs/architecture.md`
- [x] No-execution check: no subprocess/exec/eval/compiler calls; no parser libraries
- [ ] Deploy (needs your go-ahead): follow the deployment checklist
