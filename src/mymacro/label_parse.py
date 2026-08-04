"""Parse nutrition-facts text (from OCR or vision) into structured values."""

from __future__ import annotations

import re
from typing import Any

from mymacro.micronutrients import MICRO_SPECS, normalize_micronutrients
from mymacro.schemas import NutritionFacts

_SERVING_PATTERNS = [
    re.compile(
        r"serving\s*size[^0-9]{0,40}?(\d+(?:\.\d+)?)\s*(?:g|grams)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\((\d+(?:\.\d+)?)\s*(?:g|grams)\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:per|/)\s*(\d+(?:\.\d+)?)\s*(?:g|grams)\b",
        re.IGNORECASE,
    ),
]

_CALORIES = re.compile(
    r"(?:calories|energy)\s*[^\d]{0,12}(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_PROTEIN = re.compile(
    r"protein\s*[^\d]{0,12}(\d+(?:\.\d+)?)\s*(?:g|grams)?",
    re.IGNORECASE,
)
_CARBS = re.compile(
    r"(?:total\s*)?(?:carbohydrate|carbohydrates|carbs?)\s*[^\d]{0,12}(\d+(?:\.\d+)?)\s*(?:g|grams)?",
    re.IGNORECASE,
)
_FAT = re.compile(
    r"(?:total\s*)?fat\s*[^\d]{0,12}(\d+(?:\.\d+)?)\s*(?:g|grams)?",
    re.IGNORECASE,
)
_PRODUCT = re.compile(
    r"(?:product|food|item)\s*(?:name)?\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)

FIELD_KEYS = (
    ("serving_size_g", "serving size (g)"),
    ("calories", "calories"),
    ("protein_g", "protein"),
    ("carbs_g", "carbohydrates"),
    ("fat_g", "fat"),
)


class LabelParseError(ValueError):
    """Raised when required nutrition fields cannot be extracted."""

    def __init__(
        self,
        message: str,
        *,
        missing: list[str] | None = None,
        partial: dict[str, Any] | None = None,
        raw_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.missing = missing or []
        self.partial = partial or {}
        self.raw_text = raw_text

    def as_detail(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "missing": self.missing,
            "partial": self.partial,
            "raw_text": self.raw_text,
            "manual_entry_required": True,
        }


def _first_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    return float(match.group(1))


def _serving_size_g(text: str) -> float | None:
    for pattern in _SERVING_PATTERNS:
        match = pattern.search(text)
        if match:
            value = float(match.group(1))
            if value > 0:
                return value
    return None


def _product_name(text: str) -> str | None:
    match = _PRODUCT.search(text)
    if match:
        name = match.group(1).strip().splitlines()[0].strip()
        return name[:200] if name else None
    return None


def _parse_micronutrients(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for spec in MICRO_SPECS:
        unit = re.escape(spec.unit)
        for alias in spec.aliases:
            pattern = re.compile(
                rf"{re.escape(alias)}\s*[^\d]{{0,16}}(\d+(?:\.\d+)?)\s*(?:{unit})?\b",
                re.IGNORECASE,
            )
            value = _first_float(pattern, text)
            if value is not None:
                found[spec.key] = value
                break
    return normalize_micronutrients(found)


def parse_nutrition_text(text: str, default_name: str = "Scanned food") -> NutritionFacts:
    """Extract serving size, macros, and optional micronutrients from label text."""
    cleaned = text.replace("\u00a0", " ")
    values: dict[str, float | None] = {
        "serving_size_g": _serving_size_g(cleaned),
        "calories": _first_float(_CALORIES, cleaned),
        "protein_g": _first_float(_PROTEIN, cleaned),
        "carbs_g": _first_float(_CARBS, cleaned),
        "fat_g": _first_float(_FAT, cleaned),
    }
    product_name = _product_name(cleaned) or default_name
    micros = _parse_micronutrients(cleaned)
    missing_labels = [label for key, label in FIELD_KEYS if values[key] is None]
    partial = {
        "product_name": product_name,
        **{key: values[key] for key, _ in FIELD_KEYS if values[key] is not None},
        "micronutrients": micros,
    }

    if missing_labels:
        raise LabelParseError(
            "Could not read nutrition facts. Missing: " + ", ".join(missing_labels),
            missing=missing_labels,
            partial=partial,
            raw_text=cleaned.strip(),
        )

    return NutritionFacts(
        product_name=product_name,
        serving_size_g=float(values["serving_size_g"]),  # type: ignore[arg-type]
        calories=float(values["calories"]),  # type: ignore[arg-type]
        protein_g=float(values["protein_g"]),  # type: ignore[arg-type]
        carbs_g=float(values["carbs_g"]),  # type: ignore[arg-type]
        fat_g=float(values["fat_g"]),  # type: ignore[arg-type]
        micronutrients=micros,
        raw_text=cleaned.strip(),
    )


def scale_macros_for_grams(facts: NutritionFacts, grams: float) -> tuple[float, dict[str, float]]:
    """Return (servings_factor, scaled_macros) for an eaten gram amount."""
    if grams <= 0:
        raise ValueError("grams must be greater than 0")
    if facts.serving_size_g <= 0:
        raise ValueError("serving_size_g must be greater than 0")

    servings = grams / facts.serving_size_g
    scaled = {
        "calories": round(facts.calories * servings, 2),
        "protein_g": round(facts.protein_g * servings, 2),
        "carbs_g": round(facts.carbs_g * servings, 2),
        "fat_g": round(facts.fat_g * servings, 2),
    }
    return servings, scaled
