"""Helpers for calorie ↔ macro consistency (4/4/9 rule)."""

from __future__ import annotations


def calories_from_macros(protein_g: float, carbs_g: float, fat_g: float) -> float:
    return round(protein_g * 4 + carbs_g * 4 + fat_g * 9, 2)


def macros_match_calories(
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    *,
    tolerance: float = 1.0,
) -> bool:
    expected = calories_from_macros(protein_g, carbs_g, fat_g)
    return abs(expected - calories) <= tolerance
