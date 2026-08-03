# AGENTS.md

## Cursor Cloud specific instructions

### Product

**mymacro** is a FastAPI nutrition macro-tracking API (SQLite by default). There is no separate frontend; use `/docs` or curl against the API.

### Run / lint / test

Standard commands are in `README.md` and `pyproject.toml`. After `pip install -e ".[dev]"` (or the VM update script):

- Dev server: `uvicorn mymacro.main:app --reload --host 0.0.0.0 --port 8000` (from repo root with the venv activated, or `PYTHONPATH=src`)
- Lint: `ruff check src tests`
- Tests: `pytest`

### Gotchas

- Activate `.venv` (or ensure `src` is on `PYTHONPATH`) before running uvicorn; the editable install puts the package on the path.
- Default DB file is `./mymacro.db` in the process cwd. Tests use an in-memory SQLite DB via `tests/conftest.py` and do not touch that file.
- Override DB with `MYMACRO_DATABASE_URL` if needed (e.g. a temp path in cloud sessions).
- `PUT /goals` upserts by day. `GET /goals/{day}` falls back to the most recent prior goal when the exact day has none.
- No auth yet — the API is open for local development.
