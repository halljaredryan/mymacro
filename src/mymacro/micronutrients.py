"""Micronutrient definitions, FDA Daily Values, and scaling helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MicroSpec:
    key: str
    label: str
    unit: str
    rdv: float | None  # None => tracked but no % DV
    aliases: tuple[str, ...] = ()


# FDA Daily Values for adults (current US Nutrition Facts label basis).
MICRO_SPECS: tuple[MicroSpec, ...] = (
    MicroSpec("saturated_fat_g", "Saturated fat", "g", 20.0, ("saturated fat", "sat fat")),
    MicroSpec("cholesterol_mg", "Cholesterol", "mg", 300.0, ("cholesterol",)),
    MicroSpec("sodium_mg", "Sodium", "mg", 2300.0, ("sodium",)),
    MicroSpec("fiber_g", "Dietary fiber", "g", 28.0, ("dietary fiber", "fiber")),
    MicroSpec("total_sugars_g", "Total sugars", "g", None, ("total sugars", "sugars")),
    MicroSpec(
        "added_sugars_g",
        "Added sugars",
        "g",
        50.0,
        ("added sugars", "includes added sugars"),
    ),
    MicroSpec("vitamin_d_mcg", "Vitamin D", "mcg", 20.0, ("vitamin d", "vit d")),
    MicroSpec("calcium_mg", "Calcium", "mg", 1300.0, ("calcium",)),
    MicroSpec("iron_mg", "Iron", "mg", 18.0, ("iron",)),
    MicroSpec("potassium_mg", "Potassium", "mg", 4700.0, ("potassium",)),
    MicroSpec("vitamin_c_mg", "Vitamin C", "mg", 90.0, ("vitamin c", "vit c", "ascorbic acid")),
    MicroSpec("vitamin_a_mcg", "Vitamin A", "mcg", 900.0, ("vitamin a", "vit a")),
)

MICRO_KEYS = tuple(spec.key for spec in MICRO_SPECS)
MICRO_BY_KEY = {spec.key: spec for spec in MICRO_SPECS}


def normalize_micronutrients(raw: dict[str, Any] | None) -> dict[str, float]:
    """Keep only known micro keys with non-negative numeric values."""
    if not raw:
        return {}
    cleaned: dict[str, float] = {}
    for key in MICRO_KEYS:
        if key not in raw or raw[key] is None or raw[key] == "":
            continue
        try:
            value = float(raw[key])
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue
        cleaned[key] = round(value, 4)
    return cleaned


def scale_micronutrients(per_serving: dict[str, float] | None, servings: float) -> dict[str, float]:
    base = normalize_micronutrients(per_serving)
    return {key: round(value * servings, 4) for key, value in base.items()}


def sum_micronutrients(items: list[dict[str, float]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in items:
        for key, value in normalize_micronutrients(item).items():
            totals[key] = round(totals.get(key, 0.0) + value, 4)
    return totals


def percent_dv(consumed: float, rdv: float | None) -> float | None:
    if rdv is None or rdv <= 0:
        return None
    return round((consumed / rdv) * 100.0, 1)


def daily_value_rows(consumed: dict[str, float]) -> list[dict[str, Any]]:
    """Build display rows for all known micros that were consumed or have an RDV."""
    rows: list[dict[str, Any]] = []
    for spec in MICRO_SPECS:
        amount = consumed.get(spec.key)
        if amount is None and spec.rdv is None:
            continue
        amount = float(amount or 0.0)
        rows.append(
            {
                "key": spec.key,
                "label": spec.label,
                "unit": spec.unit,
                "consumed": round(amount, 2),
                "rdv": spec.rdv,
                "percent_dv": percent_dv(amount, spec.rdv),
            }
        )
    # Prefer showing nutrients that were actually logged first, then the rest with RDV.
    rows.sort(key=lambda row: (0 if row["consumed"] > 0 else 1, row["label"]))
    return rows
