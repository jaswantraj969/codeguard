# CodeGuard task list

The spec is [SRS_ADDENDUM.md](SRS_ADDENDUM.md). Each phase ends with all tests passing, a commit and a review stop.

## Phase 0: SRS addendum
- [x] Repo initialised; SRS copied to `docs/`
- [x] `docs/SRS_ADDENDUM.md`: subset, EBNF, rules, pipeline, limits, API, tests, limitations, change log
- [x] `CONTRIBUTING.md`: ownership and workflow
- [ ] Supervisor approval of the addendum

## Phase 1: scaffold
- [ ] Backend package skeleton, `pyproject.toml`, ruff, mypy, pytest
- [ ] FastAPI app with `GET /api/v1/health`
- [ ] Vite + React + TS app that calls `/health` (`VITE_API_URL`), with ESLint and Vitest
- [ ] GitHub Actions CI (backend and frontend)

## Phase 2: lexer
- [ ] Token model
- [ ] Lexer: keywords, operators, literals, escapes, comments, preprocessor skip, `#define`
- [ ] LEX-* errors and tests

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
