# CodeGuard

A mini static analyzer for a subset of C, built for a Compiler Design course. It shows each compiler stage (tokens, AST, symbol table) and explains every diagnostic in plain language. Submitted code is analyzed as data only; it is never compiled or run.

The specification is [`docs/SRS_ADDENDUM.md`](docs/SRS_ADDENDUM.md), which amends the original SRS in `docs/`. Team ownership and workflow are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

> This README covers local development. Deployment steps and the full limitations list are added at the end of the project.

## Requirements

- Python 3.12 or newer (3.13.5 is pinned for deployment in `.python-version`)
- Node.js 22.13 or newer

## Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn codeguard.api.app:app --reload        # http://localhost:8000/api/v1/health
```

Checks: `ruff check .`, `ruff format --check .`, `mypy`, `pytest`.

## Frontend

```bash
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

The API URL comes from `VITE_API_URL` (default `http://localhost:8000`); see `frontend/.env.example`.

Checks: `npm run lint`, `npm test`, `npm run build`.
