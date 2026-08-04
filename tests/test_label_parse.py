import pytest

from mymacro.label_parse import LabelParseError, parse_nutrition_text, scale_macros_for_grams

SAMPLE_LABEL = """
Product: Greek Yogurt
Nutrition Facts
Serving Size 1 container (170g)
Calories 100
Total Fat 0g
Total Carbohydrate 6g
Protein 17g
"""


def test_parse_nutrition_text():
    facts = parse_nutrition_text(SAMPLE_LABEL)
    assert facts.product_name == "Greek Yogurt"
    assert facts.serving_size_g == 170
    assert facts.calories == 100
    assert facts.protein_g == 17
    assert facts.carbs_g == 6
    assert facts.fat_g == 0


def test_scale_macros_for_partial_serving():
    facts = parse_nutrition_text(SAMPLE_LABEL)
    servings, scaled = scale_macros_for_grams(facts, 85)
    assert servings == 0.5
    assert scaled == {
        "calories": 50.0,
        "protein_g": 8.5,
        "carbs_g": 3.0,
        "fat_g": 0.0,
    }


def test_parse_missing_fields():
    with pytest.raises(LabelParseError, match="Missing") as exc_info:
        parse_nutrition_text("Calories 100\nProtein 10g")
    err = exc_info.value
    assert "serving size (g)" in err.missing
    assert err.partial["calories"] == 100
    assert err.partial["protein_g"] == 10
    detail = err.as_detail()
    assert detail["manual_entry_required"] is True
