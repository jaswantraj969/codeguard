# Contributing to CodeGuard

CodeGuard is built by three students. Each module has one owner, who reviews every change to it. The specification is the SRS (`docs/CodeGuard_SRS_15_Pages.docx`) as amended by `docs/SRS_ADDENDUM.md`. Where they disagree, the addendum wins.

## Ownership

| Member | Owns | Paths |
|---|---|---|
| Member 1 | Lexer, tokens, parser, AST | `backend/codeguard/lexer/`, `backend/codeguard/parser/`, `backend/codeguard/ast/` |
| Member 2 | Symbol table, constant folding, all semantic rules (including the merged SEM-CONSTCOND rule), known-library list | `backend/codeguard/semantic/`, `backend/data/known_library_functions.json` |
| Member 3 | Optimizer suggestions, report builder and serialization, API, frontend | `backend/codeguard/optimizer/`, `backend/codeguard/report/`, `backend/codeguard/api/`, `frontend/` |

**Shared contracts.** These modules define the types every stage exchanges, so a change to any of them needs approval from all three members:
- `backend/codeguard/diagnostics.py`: the diagnostic model
- `backend/codeguard/errors.py`: error and rule-ID constants
- the API response schema

## Module boundaries

Dependencies flow one way:

```
lexer → parser/ast → semantic → optimizer → report → api → (HTTP) → frontend
```

- A module may import only from modules to its left, plus the shared contracts.
- The optimizer reads SEM-CONSTCOND results and folding helpers from `semantic`. It never re-implements them.
- The frontend depends only on the HTTP API schema, never on backend internals.

## Hard rules

- **Submitted code is data.** Never run, compile or pass it to gcc, clang or any other tool, and never use `subprocess` on user input.
- **The lexer and parser are hand-written.** No pycparser, Lark, PLY, ANTLR, tree-sitter or other parser generators.
- **Every rule gets tests.** Each rule is one module with at least one positive test (it fires) and one negative test (a similar construct that must not fire).
- **Never log full source code.** Log only its length and SHA-256 hash.
- **Render all diagnostic text as plain text** in the frontend. No `dangerouslySetInnerHTML`.

## Workflow

1. Branch from `main`: `feat/<area>-<short-name>` or `fix/<area>-<short-name>`.
2. Write commits in Conventional Commits style, e.g. `feat(lexer): report unterminated block comments`.
3. Before opening a pull request, run the checks locally:
   - backend: `ruff check`, `mypy`, `pytest`
   - frontend: `npm run lint`, `npm test`
4. Each pull request needs a review from the module owner. Changes to a shared contract need all three members.
5. CI must pass before merging. Use squash merges into `main`.
6. When behaviour changes, update `docs/SRS_ADDENDUM.md` in the same pull request.
