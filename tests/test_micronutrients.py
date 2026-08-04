from datetime import date

from mymacro.label_parse import parse_nutrition_text
from mymacro.micronutrients import daily_value_rows, percent_dv, scale_micronutrients


def test_scale_and_percent_dv():
    scaled = scale_micronutrients({"sodium_mg": 230, "fiber_g": 7}, 2)
    assert scaled == {"sodium_mg": 460.0, "fiber_g": 14.0}
    assert percent_dv(1150, 2300) == 50.0
    assert percent_dv(10, None) is None


def test_parse_micronutrients_from_label_text():
    text = """
    Product: Trail Mix
    Serving Size 40 grams
    Calories 200
    Total Fat 12 grams
    Total Carbohydrate 18 grams
    Protein 6 grams
    Sodium 150 mg
    Dietary Fiber 4 grams
    Potassium 250 mg
    Calcium 40 mg
    Iron 2 mg
    """
    facts = parse_nutrition_text(text)
    assert facts.micronutrients["sodium_mg"] == 150
    assert facts.micronutrients["fiber_g"] == 4
    assert facts.micronutrients["potassium_mg"] == 250
    assert facts.micronutrients["calcium_mg"] == 40
    assert facts.micronutrients["iron_mg"] == 2


def test_day_summary_includes_percent_dv(client):
    today = date.today().isoformat()
    response = client.post(
        "/labels/manual",
        json={
            "label": "Trail mix",
            "serving_size_g": 40,
            "calories": 200,
            "protein_g": 6,
            "carbs_g": 18,
            "fat_g": 12,
            "grams": 40,
            "day": today,
            "micronutrients": {
                "sodium_mg": 230,
                "fiber_g": 7,
                "iron_mg": 1.8,
            },
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scaled_micronutrients"]["sodium_mg"] == 230
    assert body["saved_label"]["micronutrients"]["fiber_g"] == 7

    summary = client.get(f"/days/{today}/summary").json()
    by_key = {row["key"]: row for row in summary["micronutrients"]}
    assert by_key["sodium_mg"]["percent_dv"] == 10.0  # 230 / 2300
    assert by_key["fiber_g"]["percent_dv"] == 25.0  # 7 / 28
    assert by_key["iron_mg"]["percent_dv"] == 10.0  # 1.8 / 18

    # Half serving next log via reuse
    label_id = body["saved_label"]["id"]
    reused = client.post(
        f"/labels/{label_id}/log",
        json={"grams": 20, "day": today},
    )
    assert reused.status_code == 201
    summary2 = client.get(f"/days/{today}/summary").json()
    by_key2 = {row["key"]: row for row in summary2["micronutrients"]}
    assert by_key2["sodium_mg"]["consumed"] == 345.0
    assert by_key2["sodium_mg"]["percent_dv"] == 15.0


def test_daily_values_endpoint(client):
    response = client.get("/micronutrients/daily-values")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["nutrients"]}
    assert "sodium_mg" in keys
    assert "vitamin_d_mcg" in keys


def test_daily_value_rows_sorts_consumed_first():
    rows = daily_value_rows({"sodium_mg": 100})
    assert rows[0]["key"] == "sodium_mg"
    assert any(row["key"] == "fiber_g" for row in rows)
