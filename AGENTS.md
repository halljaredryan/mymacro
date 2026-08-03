# AGENTS.md

## Cursor Cloud specific instructions

### Product

**mymacro** is a FastAPI nutrition macro-tracking app (SQLite by default).

- Scan UI: `http://127.0.0.1:8000/` (live webcam via `getUserMedia`, or file upload)
- API docs: `/docs`
- Core scan endpoint: `POST /labels/scan` (multipart: `image`, **`label`**, `grams`, optional `day`/`meal`/`notes`)
- Every scan persists a `SavedLabel` (`GET /labels`, rename via `PATCH /labels/{id}`)

### Run / lint / test

Standard commands are in `README.md` and `pyproject.toml`. After `pip install -e ".[dev]"` (or the VM update script):

- Dev server: `uvicorn mymacro.main:app --reload --host 0.0.0.0 --port 8000`
- Lint: `ruff check src tests`
- Tests: `pytest`

### Label scanning

- Prefer OpenAI vision when `MYMACRO_OPENAI_API_KEY` or `OPENAI_API_KEY` is set.
- Otherwise uses Tesseract OCR. The binary is a **system** package (`tesseract-ocr`); install once on the VM if missing — it is not part of the pip update script.
- Scaling math: `servings = grams_eaten / label_serving_size_g`, then multiply label macros by servings.
- `label` is required on scan — user-facing name stored on `saved_labels` (OCR product name kept separately as `ocr_product_name`).
- If OCR cannot read fields, `POST /labels/scan` returns HTTP 422 with `detail.manual_entry_required`, `missing`, and `partial`; the UI shows manual inputs and submits `POST /labels/manual`.
- Webcam needs a secure context (localhost/https) and browser permission; file upload remains as fallback.
- Tests mock the label reader except `test_tesseract_reader_on_synthetic_label`, which skips if Tesseract is absent.

### Gotchas

- Activate `.venv` before running uvicorn; the editable install puts the package on the path.
- Default DB file is `./mymacro.db` in the process cwd. Tests use in-memory SQLite via `tests/conftest.py`.
- Override DB with `MYMACRO_DATABASE_URL` if needed.
- `PUT /goals` upserts by day. `GET /goals/{day}` falls back to the most recent prior goal when the exact day has none.
- No auth yet — the API is open for local development.
