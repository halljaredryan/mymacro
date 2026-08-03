from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mymacro import crud, schemas, services
from mymacro.config import settings
from mymacro.database import get_db, init_db

DbSession = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title=settings.app_title, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mymacro"}


@app.post("/foods", response_model=schemas.FoodRead, status_code=status.HTTP_201_CREATED)
def create_food(payload: schemas.FoodCreate, db: DbSession) -> schemas.FoodRead:
    try:
        food = crud.create_food(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Food already exists: {payload.name}",
        ) from exc
    return schemas.FoodRead.model_validate(food)


@app.get("/foods", response_model=list[schemas.FoodRead])
def list_foods(db: DbSession) -> list[schemas.FoodRead]:
    return [schemas.FoodRead.model_validate(food) for food in crud.list_foods(db)]


@app.get("/foods/{food_id}", response_model=schemas.FoodRead)
def get_food(food_id: int, db: DbSession) -> schemas.FoodRead:
    food = crud.get_food(db, food_id)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return schemas.FoodRead.model_validate(food)


@app.put("/goals", response_model=schemas.DailyGoalRead)
def upsert_goal(payload: schemas.DailyGoalCreate, db: DbSession) -> schemas.DailyGoalRead:
    goal = crud.upsert_daily_goal(db, payload)
    return schemas.DailyGoalRead.model_validate(goal)


@app.get("/goals/{day}", response_model=schemas.DailyGoalRead)
def get_goal(day: date, db: DbSession) -> schemas.DailyGoalRead:
    goal = crud.get_goal_for_day(db, day)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No goal set")
    return schemas.DailyGoalRead.model_validate(goal)


@app.post("/entries", response_model=schemas.FoodEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: schemas.FoodEntryCreate, db: DbSession) -> schemas.FoodEntryRead:
    if not crud.get_food(db, payload.food_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    entry = crud.create_entry(db, payload)
    return services.to_entry_read(entry)


@app.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: DbSession) -> None:
    if not crud.delete_entry(db, entry_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")


@app.get("/days/{day}/summary", response_model=schemas.DaySummary)
def day_summary(day: date, db: DbSession) -> schemas.DaySummary:
    return services.day_summary(db, day)


def run() -> None:
    import uvicorn

    uvicorn.run("mymacro.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
