"""Parse nutrition-facts text (from OCR or vision) into structured values."""

from __future__ import annotations

import re

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


class LabelParseError(ValueError):
    """Raised when required nutrition fields cannot be extracted."""


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


def parse_nutrition_text(text: str, default_name: str = "Scanned food") -> NutritionFacts:
    """Extract serving size and macros from raw nutrition-label text."""
    cleaned = text.replace("\u00a0", " ")
    serving_size_g = _serving_size_g(cleaned)
    calories = _first_float(_CALORIES, cleaned)
    protein_g = _first_float(_PROTEIN, cleaned)
    carbs_g = _first_float(_CARBS, cleaned)
    fat_g = _first_float(_FAT, cleaned)

    missing = [
        name
        for name, value in [
            ("serving size (g)", serving_size_g),
            ("calories", calories),
            ("protein", protein_g),
            ("carbohydrates", carbs_g),
            ("fat", fat_g),
        ]
        if value is None
    ]
    if missing:
        raise LabelParseError("Could not read nutrition facts. Missing: " + ", ".join(missing))

    assert serving_size_g is not None
    assert calories is not None
    assert protein_g is not None
    assert carbs_g is not None
    assert fat_g is not None

    return NutritionFacts(
        product_name=_product_name(cleaned) or default_name,
        serving_size_g=serving_size_g,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
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
