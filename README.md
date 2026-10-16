# CodeGuard

CodeGuard is a mini static analyzer for a subset of C, built as a Compiler Design course project. It shows each stage a compiler goes through (the tokens, the syntax tree and the symbol table) and explains every problem it finds in plain language for students.

Submitted code is analyzed as data only: it is never compiled or run.

- **Specification:** [`docs/SRS_ADDENDUM.md`](docs/SRS_ADDENDUM.md), which amends the original SRS in `docs/`.
- **Architecture:** [`docs/architecture.md`](docs/architecture.md), with pipeline and deployment diagrams.
- **Team ownership and workflow:** [`CONTRIBUTING.md`](CONTRIBUTING.md).

## What it does

- **Lexical analysis:** a token table, plus errors for invalid characters, unterminated strings, character literals and comments, bad escapes and malformed numbers.
- **Syntax analysis:** a hand-written recursive-descent parser with error recovery (up to 20 errors) and a collapsible syntax tree. Constructs outside the V1 subset, such as arrays, pointers and `switch`, get a clear "not supported in CodeGuard V1" message.
- **Semantic analysis:** a symbol table grouped by scope, and these checks:
  - duplicate declarations, undeclared names and unused variables
  - division by zero and unreachable code
  - constant conditions, shadowing, and `break`/`continue` outside a loop
- **Suggestions:** constant arithmetic such as `10 + 20` that can be written as `30`.
- **Explanations:** every diagnostic has a one- or two-sentence explanation for a student, and clicking it highlights its line in the editor.

The supported C subset, the exact rule definitions and the limits are in the [addendum](docs/SRS_ADDENDUM.md).

## Run it locally

You need **Python 3.12 or newer** and **Node.js 22.13 or newer**. Allow about 5 minutes, mostly for downloads.

```bash
git clone <repository-url> codeguard
cd codeguard
```

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn codeguard.api.app:app --reload
```

The API runs at <http://localhost:8000>. To check it, open <http://localhost:8000/api/v1/health>, which should show `{"status":"ok"}`. Interactive API docs are at <http://localhost:8000/docs>.

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, choose **Examples → SRS demo**, then **Analyze**.

The frontend calls `http://localhost:8000` unless `VITE_API_URL` says otherwise (see `frontend/.env.example`). The backend accepts requests from `http://localhost:5173` by default. The Monaco editor is bundled, so the app works without Internet access, which is useful for lab demos.

## Tests and checks

| What | Where | Command |
|---|---|---|
| Backend lint, format, types | `backend/` | `ruff check .` · `ruff format --check .` · `mypy` |
| Backend tests | `backend/` | `pytest` |
| Acceptance tests TC-01 to TC-12 only | `backend/` | `pytest tests/test_acceptance.py` |
| Frontend lint and types | `frontend/` | `npm run lint` · `npm run typecheck` |
| Frontend tests | `frontend/` | `npm test` |
| Production build | `frontend/` | `npm run build` |

What the suites cover:
- **Backend:** the lexer, parser, every rule (with cases that must fire and cases that must not), the report, and the API with real worker processes.
- **Frontend:** the tests run against real API responses. If you change the response format, regenerate them with `python scripts/export_frontend_fixtures.py` from `backend/`.

GitHub Actions runs all of these on every push and pull request (`.github/workflows/ci.yml`).

**Load test** (not part of CI). Start the backend, then run this from `backend/`:

```bash
python loadtest/load_test.py                          # local server
python loadtest/load_test.py --url https://<your-api>.onrender.com
```

It reports P50, P95 and P99 latency for 20 concurrent small requests and for 1 KB, 10 KB, 100 KB and 500 KB inputs. It then checks the targets for normal analyses: P95 ≤ 2 s and P99 ≤ 5 s on a warm server.

## Configuration

**Backend** (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins allowed to call the API |
| `ANALYSIS_TIMEOUT_SECONDS` | `5` | Per-analysis time limit; a slow worker is killed and replaced |
| `MAX_CONCURRENT_ANALYSES` | `2` | Number of worker processes and concurrent analyses |
| `QUEUE_WAIT_SECONDS` | `3` | How long a request waits for a free worker before a 503 |
| `RATE_LIMIT_PER_MINUTE` | `30` | Analyses per minute per client IP (`0` turns it off) |
| `TRUST_PROXY_HEADERS` | `false` | Take the client IP from `X-Forwarded-For` (set `true` behind Render's proxy) |
| `MAX_SOURCE_BYTES` | `512000` | Maximum source size in UTF-8 bytes. The frontend reads it from `GET /api/v1/config`, so changing it on the server is enough |
| `CODEGUARD_DATA_DIR` | `backend/data` | Where `known_library_functions.json` lives |

**Frontend** (set at build time):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | The API's base URL |

## Deploy

The backend runs on the Render free tier and the frontend on Vercel, both at no cost. Deploy the backend first, because the frontend needs its URL.

**1. Backend on Render**
1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository. Render reads [`render.yaml`](render.yaml): a free Python web service rooted at `backend/`.
   - Python version: `.python-version`.
   - Build command: `pip install -e .`
   - Start command: `uvicorn codeguard.api.app:app --host 0.0.0.0 --port $PORT`
   - Health check: `/api/v1/health`
3. When asked for `CORS_ORIGINS`, enter a placeholder such as `https://example.com`. You'll set the real value in step 3 below.
4. After the first deploy, open `https://<service>.onrender.com/api/v1/health` and check it returns `{"status":"ok"}`.

**2. Frontend on Vercel**
1. In Vercel, import the same repository and set **Root Directory** to `frontend`. [`frontend/vercel.json`](frontend/vercel.json) supplies the Vite build settings and security headers.
2. Add the environment variable `VITE_API_URL=https://<service>.onrender.com`, then deploy.

**3. Connect them**
1. In Render, set `CORS_ORIGINS` to the Vercel URL, for example `https://codeguard.vercel.app`. Separate several origins with commas, and leave no trailing slash.
2. Redeploy the backend, open the Vercel URL, and analyze the SRS demo.

The free Render service sleeps after 15 minutes without traffic and takes about a minute to wake. The frontend pings `/health` on load and shows "Waking up the server, this can take about a minute." while it waits.

## Limitations

CodeGuard V1 analyzes a teaching subset of C. These are known limits; the full list is in addendum §11.

- **No preprocessor:**
  - `#include` files aren't read. Common library names (`printf`, `scanf`, `EOF`, …) come from `backend/data/known_library_functions.json`.
  - `#define` values are neither expanded nor folded, so `while (TRUE)` isn't reported.
  - Function-like macros are ignored.
  - Every branch of `#if`/`#ifdef` is analyzed.
- **Unsupported constructs:** pointers, arrays, `struct`/`union`/`enum`, `typedef`, `switch`, `do`/`while`, `goto`, `?:`, casts, `sizeof`, `unsigned`/`long`/`short`, storage classes, bitwise operators and the comma operator. Each gets an `UNSUPPORTED_CONSTRUCT` diagnostic, and semantic analysis is then skipped for that file. `&x` is allowed only as a function argument, for `scanf`.
- **No type checking:** mismatched types, wrong argument counts and return types aren't checked.
- **No flow analysis:** unreachable code is detected only after `return`/`break`/`continue` in the same block, and uninitialized variables aren't detected.
- **Size and nesting limits:**
  - 512,000 bytes of source by default (configurable with `MAX_SOURCE_BYTES`).
  - 64 levels of nested statements, and 64 levels of parentheses.
  - 256 links in an `else if`, unary or assignment chain.
  - The token view shows at most 10,000 tokens. The syntax-tree view is hidden above 20,000 nodes or 400 levels.
- **Performance on the free tier:** Render's free tier has little CPU, so very large inputs may hit the 5 s timeout there. Run the load test against the deployed API to measure this, and lower `MAX_SOURCE_BYTES` if needed.
- **One file at a time.** Identifiers must be ASCII.

## Who owns what

Each member owns their modules (see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow). For the viva, each member should be able to explain these four functions: what they do, why they're written that way, and how they're tested.

**Member 1: lexer, tokens, parser, AST** (`backend/codeguard/lexer/`, `parser/`, `ast/`)
- [`_Lexer.run`](backend/codeguard/lexer/lexer.py#L196): the scanning loop. It classifies each character, skips comments and `#` lines, and keeps going after an error, up to 20 errors.
- [`_Lexer.scan_number`](backend/codeguard/lexer/lexer.py#L312): reads a whole C number greedily, then validates it, so `08` or `123abc` becomes one clear error.
- [`_Parser.parse_binary`](backend/codeguard/parser/parser.py#L759): operator-precedence parsing with an operand stack and an operator stack instead of one function per level, and why that keeps recursion bounded (addendum §4.1).
- [`_Parser.synchronize`](backend/codeguard/parser/parser.py#L331) with [`parse_items`](backend/codeguard/parser/parser.py#L361): panic-mode recovery. It skips to the next `;` or `}`, skips `{ … }` groups whole, and stops after 20 errors.

**Member 2: symbol table and semantic rules** (`backend/codeguard/semantic/`)
- [`_Resolver.visit`](backend/codeguard/semantic/model.py#L276): one iterative walk that opens scopes, declares names and counts reads and writes. Be ready to explain why `x++;` is a write but `y = x++;` is also a read.
- [`_Resolver.lookup`](backend/codeguard/semantic/model.py#L153): name resolution. It searches the scope chain, then file-wide functions, then `#define`s (visible from their line onward), then the library list.
- [`fold`](backend/codeguard/semantic/folding.py#L115) and [`apply_binary`](backend/codeguard/semantic/folding.py#L64): constant folding with C semantics: truncating `/`, the sign of `%`, 32-bit overflow, and short-circuit `&&`/`||`.
- [`constant_condition.check`](backend/codeguard/semantic/rules/constant_condition.py#L49) and [`apply_declaration_policy`](backend/codeguard/semantic/analyzer.py#L55): the merged SEM-CONSTCOND rule with its `while (1)` and `for (;;)` exemptions, and how one diagnostic per declaration is chosen.

**Member 3: optimizer, report, API and frontend** (`backend/codeguard/optimizer/`, `report/`, `api/`, `frontend/`)
- [`constexpr.check`](backend/codeguard/optimizer/constexpr.py#L81): finds maximal literal-only expressions, and skips conditions SEM-CONSTCOND already reported and divisions by zero.
- [`build_report`](backend/codeguard/report/builder.py#L137): stage gating (a lexical error stops everything; a syntax error skips semantic analysis and the optimizer), plus sorting and statistics.
- [`AnalysisPool.run`](backend/codeguard/api/worker.py#L111) and [`warm_up`](backend/codeguard/api/worker.py#L80): the semaphore and queue, killing and replacing a worker process on timeout, and the warm-up the health check waits for.
- [`ast_to_json`](backend/codeguard/report/serialize.py#L140) and [`runAnalysis`](frontend/src/App.tsx#L50): serializing deep trees to JSON without recursion, and how the browser checks input and gets results into the panels.

## Project layout

```
codeguard/
  docs/           SRS, SRS addendum, architecture diagrams, task list
  backend/
    codeguard/    lexer/, parser/, ast/, semantic/ (rules/), optimizer/, report/, api/
    data/         known_library_functions.json
    tests/        unit, API and acceptance tests
    loadtest/     load_test.py (not run in CI)
    scripts/      export_frontend_fixtures.py
  frontend/       Vite + React + TypeScript app
  render.yaml     Render Blueprint for the backend
```
