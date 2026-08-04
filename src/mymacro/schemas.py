from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Macros(BaseModel):
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class FoodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    serving_label: str = Field(default="1 serving", max_length=100)
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    micronutrients: dict[str, float] = Field(default_factory=dict)


class FoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    serving_label: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: dict[str, float] = Field(default_factory=dict)
    created_at: datetime


class DailyGoalCreate(BaseModel):
    day: date
    calories: float = Field(gt=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    notes: str | None = None


class DailyGoalRead(DailyGoalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class IdealTargetsUpdate(BaseModel):
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    calories: float | None = Field(default=None, gt=0)
    sync_calories_from_macros: bool = True


class IdealTargetsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    calories_from_macros: float
    updated_at: datetime | None = None


class DayListItem(BaseModel):
    day: date
    entry_count: int
    consumed: Macros


class FoodEntryCreate(BaseModel):
    food_id: int
    day: date
    servings: float = Field(default=1.0, gt=0)
    meal: str = Field(default="snack", max_length=50)
    notes: str | None = None


class FoodEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    food_id: int
    day: date
    servings: float
    meal: str
    notes: str | None
    created_at: datetime
    food: FoodRead
    macros: Macros
    micronutrients: dict[str, float] = Field(default_factory=dict)


class MicronutrientDayStat(BaseModel):
    key: str
    label: str
    unit: str
    consumed: float
    rdv: float | None
    percent_dv: float | None


class DaySummary(BaseModel):
    day: date
    goal: DailyGoalRead | None
    consumed: Macros
    remaining: Macros | None
    entries: list[FoodEntryRead]
    micronutrients: list[MicronutrientDayStat] = Field(default_factory=list)


class NutritionFacts(BaseModel):
    product_name: str = "Scanned food"
    serving_size_g: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    micronutrients: dict[str, float] = Field(default_factory=dict)
    raw_text: str | None = None


class SavedLabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    serving_size_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micronutrients: dict[str, float] = Field(default_factory=dict)
    ocr_product_name: str | None
    raw_text: str | None
    food_id: int | None
    created_at: datetime


class SavedLabelUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class ReuseSavedLabel(BaseModel):
    """Log a new intake amount using an existing saved label's nutrition facts."""

    grams: float = Field(gt=0)
    day: date | None = None
    meal: str = Field(default="snack", max_length=50)
    notes: str | None = None


class ManualNutritionFacts(BaseModel):
    """User-supplied nutrition facts when OCR cannot read the label."""

    label: str = Field(min_length=1, max_length=200)
    serving_size_g: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    grams: float = Field(gt=0)
    day: date | None = None
    meal: str = Field(default="snack", max_length=50)
    notes: str | None = None
    product_name: str | None = None
    raw_text: str | None = None
    micronutrients: dict[str, float] = Field(default_factory=dict)


class LabelScanResult(BaseModel):
    facts: NutritionFacts
    label: str
    grams: float
    servings: float
    scaled_macros: Macros
    scaled_micronutrients: dict[str, float] = Field(default_factory=dict)
    saved_label: SavedLabelRead
    food: FoodRead
    entry: FoodEntryRead
    summary: DaySummary
    source: str = "scan"


class DailyValuesInfo(BaseModel):
    nutrients: list[dict[str, Any]]
