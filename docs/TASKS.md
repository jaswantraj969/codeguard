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
- [ ] AST nodes
- [ ] Recursive-descent parser, panic-mode recovery (max 20)
- [ ] UNSUPPORTED_CONSTRUCT and NESTING_TOO_DEEP
- [ ] Parser tests

## Phase 4: semantics
- [ ] Symbol table and scopes; resolver
- [ ] Constant folding
- [ ] SEM-DUP, SEM-UNDECL, SEM-UNUSED, SEM-DIV0, SEM-UNREACH, SEM-CONSTCOND, SEM-SHADOW
- [ ] Known-library list
- [ ] Positive and negative tests per rule

## Phase 5: optimizer and report
- [ ] OPT-CONSTEXPR
- [ ] Report builder: statuses, statistics, policy, sorting, toggles
- [ ] Token, AST and symbol serialization; `analyze()` entry point

## Phase 6: API
- [ ] Validation, error envelope, 400 handler
- [ ] Worker-process timeout, semaphore and queue
- [ ] CORS, logging, rate limiting
- [ ] API tests

## Phase 7: frontend
- [ ] Editor, toolbar, upload, examples
- [ ] Stage bar, diagnostics tabs, statistics
- [ ] Token, AST and symbol views
- [ ] Accessibility, wake-up message
- [ ] Vitest tests

## Phase 8: acceptance and deploy prep
- [ ] TC-01–TC-36 end to end
- [ ] Load-test script
- [ ] `render.yaml`, Vercel config
- [ ] README and Mermaid diagram
- [ ] Deployment checklist (no deploy)
