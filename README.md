# mymacro

Nutrition macro tracking API built with FastAPI, SQLAlchemy, and SQLite.

Track foods, set daily macro goals, log what you eat, and see remaining calories / protein / carbs / fat for the day. Photograph a nutrition label, enter grams eaten, and the app scales the label macros into your daily intake.

## Requirements

- Python 3.11+
- Optional offline OCR: [Tesseract](https://github.com/tesseract-ocr/tesseract) (`tesseract-ocr` on Debian/Ubuntu)
- Optional high-accuracy OCR: OpenAI-compatible vision API key

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Offline label scanning (recommended for local/dev without an API key)
sudo apt-get install -y tesseract-ocr
```

## Run (development)

```bash
uvicorn mymacro.main:app --reload --host 0.0.0.0 --port 8000
```

- Scan UI (live webcam + file upload): http://127.0.0.1:8000/
- Interactive docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

Optional env vars (prefix `MYMACRO_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MYMACRO_DATABASE_URL` | `sqlite:///./mymacro.db` | SQLAlchemy database URL |
| `MYMACRO_DEBUG` | `false` | Debug flag |
| `MYMACRO_OPENAI_API_KEY` | _(unset)_ | Enables vision-model label reading (also accepts `OPENAI_API_KEY`) |
| `MYMACRO_OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base |
| `MYMACRO_OPENAI_VISION_MODEL` | `gpt-4o-mini` | Vision chat model |

When an OpenAI key is set, label photos are read with the vision model first; otherwise Tesseract OCR + text parsing is used.

## Lint & test

```bash
ruff check src tests
pytest
```

## Core API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/labels/scan` | Webcam/photo + **label name** + grams → parse, **save**, scale, log |
| `POST` | `/labels/manual` | Manual nutrition facts fallback when OCR misses fields |
| `POST` | `/labels/{id}/log` | Reuse a saved label with a new gram amount |
| `GET` | `/labels` | List saved labels (`?q=` searches name / OCR name) |
| `PATCH` | `/labels/{id}` | Rename a saved label |
| `POST` | `/foods` | Create a food with macros per serving |
| `GET` | `/foods` | List foods |
| `PUT` | `/goals` | Set / update daily macro goals |
| `POST` | `/entries` | Log a food entry for a day |
| `GET` | `/days/{day}/summary` | Consumed vs remaining macros |
| `DELETE` | `/entries/{id}` | Remove a logged entry |

### Label scan math

If a label lists macros **per serving of Sg grams**, and you ate **Gg grams**:

```
servings = G / S
logged macros = label macros × servings
```

Example: label serving 32g / 190 kcal → eating 16g logs 0.5 serving → 95 kcal.

### Quick example

```bash
# Scan a nutrition label photo, save it as a named label, and log 50g
curl -s -X POST http://127.0.0.1:8000/labels/scan \
  -F "image=@./label.jpg" \
  -F "label=Oat crackers" \
  -F "grams=50" \
  -F "meal=snack"

# Search saved labels
curl -s 'http://127.0.0.1:8000/labels?q=peanut'

# Reuse a saved label with a different gram amount
curl -s -X POST http://127.0.0.1:8000/labels/1/log \
  -H 'Content-Type: application/json' \
  -d '{"grams":40,"day":"2026-08-04","meal":"snack"}'

# Create a food manually
curl -s -X POST http://127.0.0.1:8000/foods \
  -H 'Content-Type: application/json' \
  -d '{"name":"Chicken Breast","serving_label":"100g","calories":165,"protein_g":31,"carbs_g":0,"fat_g":3.6}'

# Set today's goals
curl -s -X PUT http://127.0.0.1:8000/goals \
  -H 'Content-Type: application/json' \
  -d "{\"day\":\"$(date +%F)\",\"calories\":2000,\"protein_g\":150,\"carbs_g\":200,\"fat_g\":65}"

# Day summary
curl -s "http://127.0.0.1:8000/days/$(date +%F)/summary"
```

## Project layout

```
src/mymacro/           # Application package
src/mymacro/static/    # Simple scan UI
tests/                 # pytest suite
pyproject.toml         # Dependencies & tooling
```
