from datetime import date

from sqlalchemy.orm import Session

from mymacro import crud, models, schemas
from mymacro.macro_math import calories_from_macros
from mymacro.micronutrients import (
    daily_value_rows,
    normalize_micronutrients,
    scale_micronutrients,
    sum_micronutrients,
)


def food_to_read(food: models.Food) -> schemas.FoodRead:
    return schemas.FoodRead(
        id=food.id,
        name=food.name,
        serving_label=food.serving_label,
        calories=food.calories,
        protein_g=food.protein_g,
        carbs_g=food.carbs_g,
        fat_g=food.fat_g,
        micronutrients=normalize_micronutrients(food.micronutrients_json),
        created_at=food.created_at,
    )


def saved_label_to_read(saved: models.SavedLabel) -> schemas.SavedLabelRead:
    return schemas.SavedLabelRead(
        id=saved.id,
        label=saved.label,
        serving_size_g=saved.serving_size_g,
        calories=saved.calories,
        protein_g=saved.protein_g,
        carbs_g=saved.carbs_g,
        fat_g=saved.fat_g,
        micronutrients=normalize_micronutrients(saved.micronutrients_json),
        ocr_product_name=saved.ocr_product_name,
        raw_text=saved.raw_text,
        food_id=saved.food_id,
        created_at=saved.created_at,
    )


def entry_macros(entry: models.FoodEntry) -> schemas.Macros:
    food = entry.food
    servings = entry.servings
    return schemas.Macros(
        calories=round(food.calories * servings, 2),
        protein_g=round(food.protein_g * servings, 2),
        carbs_g=round(food.carbs_g * servings, 2),
        fat_g=round(food.fat_g * servings, 2),
    )


def entry_micronutrients(entry: models.FoodEntry) -> dict[str, float]:
    return scale_micronutrients(entry.food.micronutrients_json, entry.servings)


def to_entry_read(entry: models.FoodEntry) -> schemas.FoodEntryRead:
    return schemas.FoodEntryRead(
        id=entry.id,
        food_id=entry.food_id,
        day=entry.day,
        servings=entry.servings,
        meal=entry.meal,
        notes=entry.notes,
        created_at=entry.created_at,
        food=food_to_read(entry.food),
        macros=entry_macros(entry),
        micronutrients=entry_micronutrients(entry),
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


def _goal_read_from_ideal(ideal: models.IdealTargets, day: date) -> schemas.DailyGoalRead:
    return schemas.DailyGoalRead(
        id=0,
        day=day,
        calories=ideal.calories,
        protein_g=ideal.protein_g,
        carbs_g=ideal.carbs_g,
        fat_g=ideal.fat_g,
        notes="ideal targets",
        created_at=ideal.updated_at,
    )


def resolve_day_goal(
    db: Session, day: date
) -> tuple[schemas.DailyGoalRead | None, models.DailyGoal | None]:
    """Return (goal_read, orm_goal_or_none). Falls back to ideal targets for display."""
    goal = crud.get_goal_for_day(db, day)
    if goal:
        return schemas.DailyGoalRead.model_validate(goal), goal
    ideal = crud.get_or_create_ideal_targets(db)
    return _goal_read_from_ideal(ideal, day), None


def day_summary(db: Session, day: date) -> schemas.DaySummary:
    entries = crud.list_entries_for_day(db, day)
    goal_read, orm_goal = resolve_day_goal(db, day)
    consumed = sum_macros(entries)
    remaining = None
    if orm_goal:
        remaining = remaining_macros(orm_goal, consumed)
    elif goal_read:
        remaining = schemas.Macros(
            calories=round(goal_read.calories - consumed.calories, 2),
            protein_g=round(goal_read.protein_g - consumed.protein_g, 2),
            carbs_g=round(goal_read.carbs_g - consumed.carbs_g, 2),
            fat_g=round(goal_read.fat_g - consumed.fat_g, 2),
        )
    micros_consumed = sum_micronutrients([entry_micronutrients(entry) for entry in entries])
    micro_rows = [schemas.MicronutrientDayStat(**row) for row in daily_value_rows(micros_consumed)]
    return schemas.DaySummary(
        day=day,
        goal=goal_read,
        consumed=consumed,
        remaining=remaining,
        entries=[to_entry_read(entry) for entry in entries],
        micronutrients=micro_rows,
    )


def ideal_targets_to_read(row: models.IdealTargets) -> schemas.IdealTargetsRead:
    return schemas.IdealTargetsRead(
        calories=row.calories,
        protein_g=row.protein_g,
        carbs_g=row.carbs_g,
        fat_g=row.fat_g,
        calories_from_macros=calories_from_macros(row.protein_g, row.carbs_g, row.fat_g),
        updated_at=row.updated_at,
    )


def list_day_summaries(db: Session, limit: int = 60) -> list[schemas.DayListItem]:
    items: list[schemas.DayListItem] = []
    for day, count in crud.list_logged_days(db, limit=limit):
        entries = crud.list_entries_for_day(db, day)
        items.append(
            schemas.DayListItem(
                day=day,
                entry_count=count,
                consumed=sum_macros(entries),
            )
        )
    return items
