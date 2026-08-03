from datetime import date, datetime

from sqlalchemy import (
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
    """A reusable food item with macros per serving."""

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    serving_label: Mapped[str] = mapped_column(String(100), default="1 serving")
    calories: Mapped[float] = mapped_column(Float, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, default=0.0)
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
