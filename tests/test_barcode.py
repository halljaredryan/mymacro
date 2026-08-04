from datetime import date

from mymacro.fatsecret import FatSecretError, set_fatsecret_client
from mymacro.schemas import NutritionFacts


class FakeFatSecretClient:
    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts:
        if barcode == "missing":
            raise FatSecretError("No FatSecret food found for barcode")
        return NutritionFacts(
            product_name="Barcode Peanut Butter",
            serving_size_g=32,
            calories=190,
            protein_g=8,
            carbs_g=6,
            fat_g=16,
            micronutrients={"sodium_mg": 140},
            raw_text=f"barcode={barcode}",
        )


def setup_function(_):
    set_fatsecret_client(None)


def teardown_function(_):
    set_fatsecret_client(None)


def test_barcode_lookup_logs_intake(client):
    set_fatsecret_client(FakeFatSecretClient())
    today = date.today().isoformat()
    response = client.post(
        "/barcode/lookup",
        json={
            "barcode": "012345678905",
            "grams": 16,
            "day": today,
            "meal": "snack",
            "label": "PB jar",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["barcode"] == "012345678905"
    assert body["source"] == "barcode"
    assert body["label"] == "PB jar"
    assert body["scaled_macros"]["calories"] == 95.0
    assert body["scaled_micronutrients"]["sodium_mg"] == 70.0


def test_barcode_error_passthrough(client):
    set_fatsecret_client(FakeFatSecretClient())
    response = client.post(
        "/barcode/lookup",
        json={"barcode": "missing", "grams": 10},
    )
    assert response.status_code == 502
    assert "No FatSecret food" in response.json()["detail"]


def test_barcode_page(client):
    response = client.get("/barcode")
    assert response.status_code == 200
    assert "Barcode lookup" in response.text
    assert "BarcodeDetector" in response.text
    assert "/barcode/lookup" in response.text
