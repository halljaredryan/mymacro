from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from mymacro import models, schemas


def create_food(db: Session, payload: schemas.FoodCreate) -> models.Food:
    food = models.Food(**payload.model_dump())
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


def list_foods(db: Session) -> list[models.Food]:
    return list(db.scalars(select(models.Food).order_by(models.Food.name)).all())


def get_food(db: Session, food_id: int) -> models.Food | None:
    return db.get(models.Food, food_id)


def get_food_by_name(db: Session, name: str) -> models.Food | None:
    return db.scalar(select(models.Food).where(models.Food.name == name))


def upsert_daily_goal(db: Session, payload: schemas.DailyGoalCreate) -> models.DailyGoal:
    existing = db.scalar(select(models.DailyGoal).where(models.DailyGoal.day == payload.day))
    if existing:
        for key, value in payload.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing

    goal = models.DailyGoal(**payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_goal_for_day(db: Session, day: date) -> models.DailyGoal | None:
    exact = db.scalar(select(models.DailyGoal).where(models.DailyGoal.day == day))
    if exact:
        return exact
    return db.scalar(
        select(models.DailyGoal)
        .where(models.DailyGoal.day <= day)
        .order_by(models.DailyGoal.day.desc())
        .limit(1)
    )


def create_entry(db: Session, payload: schemas.FoodEntryCreate) -> models.FoodEntry:
    entry = models.FoodEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return db.scalar(
        select(models.FoodEntry)
        .options(joinedload(models.FoodEntry.food))
        .where(models.FoodEntry.id == entry.id)
    )


def list_entries_for_day(db: Session, day: date) -> list[models.FoodEntry]:
    return list(
        db.scalars(
            select(models.FoodEntry)
            .options(joinedload(models.FoodEntry.food))
            .where(models.FoodEntry.day == day)
            .order_by(models.FoodEntry.created_at)
        ).all()
    )


def delete_entry(db: Session, entry_id: int) -> bool:
    entry = db.get(models.FoodEntry, entry_id)
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True
