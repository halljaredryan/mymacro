from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mymacro import crud, label_service, schemas, services
from mymacro.config import settings
from mymacro.database import get_db, init_db
from mymacro.label_parse import LabelParseError
from mymacro.label_reader import LabelReader, get_label_reader
from mymacro.micronutrients import MICRO_SPECS

DbSession = Annotated[Session, Depends(get_db)]
LabelReaderDep = Annotated[LabelReader, Depends(get_label_reader)]

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title=settings.app_title, version="0.1.0", lifespan=lifespan)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index)


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
    return services.food_to_read(food)


@app.get("/foods", response_model=list[schemas.FoodRead])
def list_foods(db: DbSession) -> list[schemas.FoodRead]:
    return [services.food_to_read(food) for food in crud.list_foods(db)]


@app.get("/foods/{food_id}", response_model=schemas.FoodRead)
def get_food(food_id: int, db: DbSession) -> schemas.FoodRead:
    food = crud.get_food(db, food_id)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return services.food_to_read(food)


@app.get("/micronutrients/daily-values", response_model=schemas.DailyValuesInfo)
def daily_values() -> schemas.DailyValuesInfo:
    return schemas.DailyValuesInfo(
        nutrients=[
            {
                "key": spec.key,
                "label": spec.label,
                "unit": spec.unit,
                "rdv": spec.rdv,
            }
            for spec in MICRO_SPECS
        ]
    )


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


@app.get("/labels", response_model=list[schemas.SavedLabelRead])
def list_saved_labels(db: DbSession, q: str | None = None) -> list[schemas.SavedLabelRead]:
    return [services.saved_label_to_read(item) for item in crud.list_saved_labels(db, q=q)]


@app.patch("/labels/{label_id}", response_model=schemas.SavedLabelRead)
def rename_saved_label(
    label_id: int, payload: schemas.SavedLabelUpdate, db: DbSession
) -> schemas.SavedLabelRead:
    saved = crud.update_saved_label(db, label_id, payload)
    if not saved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved label not found")
    return services.saved_label_to_read(saved)


@app.post(
    "/labels/{label_id}/log",
    response_model=schemas.LabelScanResult,
    status_code=status.HTTP_201_CREATED,
)
def reuse_saved_label(
    label_id: int, payload: schemas.ReuseSavedLabel, db: DbSession
) -> schemas.LabelScanResult:
    """Reuse a saved label's nutrition facts with a new gram amount."""
    try:
        result = label_service.reuse_and_log(db, label_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved label not found")
    return result


@app.post(
    "/labels/scan",
    response_model=schemas.LabelScanResult,
    status_code=status.HTTP_201_CREATED,
)
async def scan_label(
    db: DbSession,
    reader: LabelReaderDep,
    image: Annotated[UploadFile, File(description="Photo of the nutrition facts label")],
    grams: Annotated[float, Form(gt=0, description="How many grams you ate")],
    label: Annotated[str, Form(min_length=1, max_length=200, description="Name for this label")],
    day: Annotated[date | None, Form()] = None,
    meal: Annotated[str, Form()] = "snack",
    notes: Annotated[str | None, Form()] = None,
) -> schemas.LabelScanResult:
    """Read a nutrition label image, save it under a name, scale by grams, and log intake."""
    content_type = image.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload must be an image",
        )
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image upload")
    if grams <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="grams must be > 0")
    if not label.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="label is required")

    try:
        return label_service.scan_and_log(
            db,
            reader,
            image_bytes=image_bytes,
            content_type=content_type,
            grams=grams,
            day=day or date.today(),
            label=label,
            meal=meal,
            notes=notes,
        )
    except LabelParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.as_detail(),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post(
    "/labels/manual",
    response_model=schemas.LabelScanResult,
    status_code=status.HTTP_201_CREATED,
)
def manual_label(payload: schemas.ManualNutritionFacts, db: DbSession) -> schemas.LabelScanResult:
    """Save nutrition facts entered manually (OCR fallback) and log grams eaten."""
    try:
        return label_service.manual_and_log(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def run() -> None:
    import uvicorn

    uvicorn.run("mymacro.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
