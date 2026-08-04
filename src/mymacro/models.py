from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mymacro.database import Base


class Food(Base):
    """A reusable food item with macros (and optional micros) per serving."""

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    serving_label: Mapped[str] = mapped_column(String(100), default="1 serving")
    calories: Mapped[float] = mapped_column(Float, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, default=0.0)
    micronutrients_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entries: Mapped[list["FoodEntry"]] = relationship(back_populates="food")


class DailyGoal(Base):
    """Target macros for a calendar day (falls back to latest prior goal)."""

    __tablename__ = "daily_goals"
    __table_args__ = (UniqueConstraint("day", name="uq_daily_goals_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IdealTargets(Base):
    """User's default / ideal daily macro targets (singleton row id=1)."""

    __tablename__ = "ideal_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calories: Mapped[float] = mapped_column(Float, default=2000.0)
    protein_g: Mapped[float] = mapped_column(Float, default=150.0)
    carbs_g: Mapped[float] = mapped_column(Float, default=200.0)
    fat_g: Mapped[float] = mapped_column(Float, default=66.67)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FoodEntry(Base):
    """A logged consumption of a food on a given day."""

    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    meal: Mapped[str] = mapped_column(String(50), default="snack")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    food: Mapped[Food] = relationship(back_populates="entries")


class SavedLabel(Base):
    """A scanned nutrition label saved with a user-chosen name."""

    __tablename__ = "saved_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(200), index=True)
    serving_size_g: Mapped[float] = mapped_column(Float)
    calories: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    micronutrients_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ocr_product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    food: Mapped[Food | None] = relationship()
