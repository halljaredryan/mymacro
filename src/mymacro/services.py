from datetime import date

from sqlalchemy.orm import Session

from mymacro import crud, models, schemas


def entry_macros(entry: models.FoodEntry) -> schemas.Macros:
    food = entry.food
    servings = entry.servings
    return schemas.Macros(
        calories=round(food.calories * servings, 2),
        protein_g=round(food.protein_g * servings, 2),
        carbs_g=round(food.carbs_g * servings, 2),
        fat_g=round(food.fat_g * servings, 2),
    )


def to_entry_read(entry: models.FoodEntry) -> schemas.FoodEntryRead:
    return schemas.FoodEntryRead(
        id=entry.id,
        food_id=entry.food_id,
        day=entry.day,
        servings=entry.servings,
        meal=entry.meal,
        notes=entry.notes,
        created_at=entry.created_at,
        food=schemas.FoodRead.model_validate(entry.food),
        macros=entry_macros(entry),
    )


def sum_macros(entries: list[models.FoodEntry]) -> schemas.Macros:
    totals = schemas.Macros(calories=0, protein_g=0, carbs_g=0, fat_g=0)
    for entry in entries:
        macros = entry_macros(entry)
        totals.calories = round(totals.calories + macros.calories, 2)
        totals.protein_g = round(totals.protein_g + macros.protein_g, 2)
        totals.carbs_g = round(totals.carbs_g + macros.carbs_g, 2)
        totals.fat_g = round(totals.fat_g + macros.fat_g, 2)
    return totals


def remaining_macros(goal: models.DailyGoal, consumed: schemas.Macros) -> schemas.Macros:
    return schemas.Macros(
        calories=round(goal.calories - consumed.calories, 2),
        protein_g=round(goal.protein_g - consumed.protein_g, 2),
        carbs_g=round(goal.carbs_g - consumed.carbs_g, 2),
        fat_g=round(goal.fat_g - consumed.fat_g, 2),
    )


def day_summary(db: Session, day: date) -> schemas.DaySummary:
    entries = crud.list_entries_for_day(db, day)
    goal = crud.get_goal_for_day(db, day)
    consumed = sum_macros(entries)
    remaining = remaining_macros(goal, consumed) if goal else None
    return schemas.DaySummary(
        day=day,
        goal=schemas.DailyGoalRead.model_validate(goal) if goal else None,
        consumed=consumed,
        remaining=remaining,
        entries=[to_entry_read(entry) for entry in entries],
    )
