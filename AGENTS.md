# AGENTS.md

## Cursor Cloud specific instructions

### Product

**mymacro** is a FastAPI nutrition macro-tracking app (SQLite by default).

- Scan UI: `http://127.0.0.1:8000/` (camera/file upload + grams → logs intake)
- API docs: `/docs`
- Core scan endpoint: `POST /labels/scan` (multipart: `image`, `grams`, optional `day`/`meal`/`notes`)

### Run / lint / test

Standard commands are in `README.md` and `pyproject.toml`. After `pip install -e ".[dev]"` (or the VM update script):

- Dev server: `uvicorn mymacro.main:app --reload --host 0.0.0.0 --port 8000`
- Lint: `ruff check src tests`
- Tests: `pytest`

### Label scanning

- Prefer OpenAI vision when `MYMACRO_OPENAI_API_KEY` or `OPENAI_API_KEY` is set.
- Otherwise uses Tesseract OCR. The binary is a **system** package (`tesseract-ocr`); install once on the VM if missing — it is not part of the pip update script.
- Scaling math: `servings = grams_eaten / label_serving_size_g`, then multiply label macros by servings.
- Tests mock the label reader except `test_tesseract_reader_on_synthetic_label`, which skips if Tesseract is absent.

### Gotchas

- Activate `.venv` before running uvicorn; the editable install puts the package on the path.
- Default DB file is `./mymacro.db` in the process cwd. Tests use in-memory SQLite via `tests/conftest.py`.
- Override DB with `MYMACRO_DATABASE_URL` if needed.
- `PUT /goals` upserts by day. `GET /goals/{day}` falls back to the most recent prior goal when the exact day has none.
- No auth yet — the API is open for local development.
