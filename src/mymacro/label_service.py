from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mymacro import crud, models, schemas, services
from mymacro.label_parse import scale_macros_for_grams
from mymacro.label_reader import LabelReader


def _same_macros(food: models.Food, facts: schemas.NutritionFacts) -> bool:
    return (
        abs(food.calories - facts.calories) < 0.05
        and abs(food.protein_g - facts.protein_g) < 0.05
        and abs(food.carbs_g - facts.carbs_g) < 0.05
        and abs(food.fat_g - facts.fat_g) < 0.05
    )


def get_or_create_food_from_facts(db: Session, facts: schemas.NutritionFacts) -> models.Food:
    """Reuse an existing food with the same name/macros, otherwise create one."""
    serving_label = f"{facts.serving_size_g:g}g serving"
    existing = crud.get_food_by_name(db, facts.product_name)
    if existing and _same_macros(existing, facts):
        return existing

    name = facts.product_name
    if existing:
        name = f"{facts.product_name} ({serving_label})"
        existing_alt = crud.get_food_by_name(db, name)
        if existing_alt and _same_macros(existing_alt, facts):
            return existing_alt

    payload = schemas.FoodCreate(
        name=name[:200],
        serving_label=serving_label,
        calories=facts.calories,
        protein_g=facts.protein_g,
        carbs_g=facts.carbs_g,
        fat_g=facts.fat_g,
    )
    try:
        return crud.create_food(db, payload)
    except IntegrityError:
        db.rollback()
        found = crud.get_food_by_name(db, payload.name)
        if found:
            return found
        raise


def scan_and_log(
    db: Session,
    reader: LabelReader,
    *,
    image_bytes: bytes,
    content_type: str,
    grams: float,
    day: date,
    meal: str = "snack",
    notes: str | None = None,
) -> schemas.LabelScanResult:
    facts = reader.read(image_bytes, content_type=content_type)
    servings, scaled = scale_macros_for_grams(facts, grams)
    food = get_or_create_food_from_facts(db, facts)
    entry = crud.create_entry(
        db,
        schemas.FoodEntryCreate(
            food_id=food.id,
            day=day,
            servings=servings,
            meal=meal,
            notes=notes or f"Scanned label · {grams:g}g",
        ),
    )
    return schemas.LabelScanResult(
        facts=facts,
        grams=grams,
        servings=round(servings, 4),
        scaled_macros=schemas.Macros(**scaled),
        food=schemas.FoodRead.model_validate(food),
        entry=services.to_entry_read(entry),
        summary=services.day_summary(db, day),
    )
