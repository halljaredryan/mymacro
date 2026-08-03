from datetime import date, datetime

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


class FoodRead(FoodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
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


class DaySummary(BaseModel):
    day: date
    goal: DailyGoalRead | None
    consumed: Macros
    remaining: Macros | None
    entries: list[FoodEntryRead]
