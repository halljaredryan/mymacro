# mymacro

Nutrition macro tracking API built with FastAPI, SQLAlchemy, and SQLite.

Track foods, set daily macro goals, log what you eat, and see remaining calories / protein / carbs / fat for the day.

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run (development)

```bash
uvicorn mymacro.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

Optional env vars (prefix `MYMACRO_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MYMACRO_DATABASE_URL` | `sqlite:///./mymacro.db` | SQLAlchemy database URL |
| `MYMACRO_DEBUG` | `false` | Debug flag |

## Lint & test

```bash
ruff check src tests
pytest
```

## Core API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/foods` | Create a food with macros per serving |
| `GET` | `/foods` | List foods |
| `PUT` | `/goals` | Set / update daily macro goals |
| `POST` | `/entries` | Log a food entry for a day |
| `GET` | `/days/{day}/summary` | Consumed vs remaining macros |
| `DELETE` | `/entries/{id}` | Remove a logged entry |

### Quick example

```bash
# Create a food
curl -s -X POST http://127.0.0.1:8000/foods \
  -H 'Content-Type: application/json' \
  -d '{"name":"Chicken Breast","serving_label":"100g","calories":165,"protein_g":31,"carbs_g":0,"fat_g":3.6}'

# Set today's goals
curl -s -X PUT http://127.0.0.1:8000/goals \
  -H 'Content-Type: application/json' \
  -d "{\"day\":\"$(date +%F)\",\"calories\":2000,\"protein_g\":150,\"carbs_g\":200,\"fat_g\":65}"

# Log 2 servings
curl -s -X POST http://127.0.0.1:8000/entries \
  -H 'Content-Type: application/json' \
  -d "{\"food_id\":1,\"day\":\"$(date +%F)\",\"servings\":2,\"meal\":\"lunch\"}"

# Day summary
curl -s "http://127.0.0.1:8000/days/$(date +%F)/summary"
```

## Project layout

```
src/mymacro/     # Application package
tests/           # pytest suite
pyproject.toml   # Dependencies & tooling
```
