from datetime import date
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont

from mymacro.label_reader import set_label_reader
from mymacro.schemas import NutritionFacts


class FakeLabelReader:
    def __init__(self, facts: NutritionFacts) -> None:
        self.facts = facts
        self.calls = 0

    def read(self, image_bytes: bytes, content_type: str = "image/jpeg") -> NutritionFacts:
        self.calls += 1
        assert image_bytes
        return self.facts


@pytest.fixture()
def fake_reader():
    reader = FakeLabelReader(
        NutritionFacts(
            product_name="Peanut Butter",
            serving_size_g=32,
            calories=190,
            protein_g=8,
            carbs_g=6,
            fat_g=16,
            raw_text="fake",
        )
    )
    set_label_reader(reader)
    yield reader
    set_label_reader(None)


def _tiny_png() -> bytes:
    image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_scan_label_scales_grams_saves_and_logs(client, fake_reader):
    today = date.today().isoformat()
    client.put(
        "/goals",
        json={
            "day": today,
            "calories": 2000,
            "protein_g": 150,
            "carbs_g": 200,
            "fat_g": 65,
        },
    )

    response = client.post(
        "/labels/scan",
        data={
            "grams": "16",
            "day": today,
            "meal": "breakfast",
            "label": "Costco peanut butter",
        },
        files={"image": ("label.png", _tiny_png(), "image/png")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert fake_reader.calls == 1
    assert body["label"] == "Costco peanut butter"
    assert body["facts"]["product_name"] == "Peanut Butter"
    assert body["saved_label"]["label"] == "Costco peanut butter"
    assert body["saved_label"]["serving_size_g"] == 32
    assert body["saved_label"]["ocr_product_name"] == "Peanut Butter"
    assert body["food"]["name"] == "Costco peanut butter"
    assert body["grams"] == 16
    assert body["servings"] == 0.5
    assert body["scaled_macros"] == {
        "calories": 95.0,
        "protein_g": 4.0,
        "carbs_g": 3.0,
        "fat_g": 8.0,
    }
    assert body["summary"]["consumed"]["calories"] == 95.0
    assert len(body["summary"]["entries"]) == 1

    listed = client.get("/labels")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["label"] == "Costco peanut butter"
    assert items[0]["calories"] == 190


def test_rename_saved_label(client, fake_reader):
    response = client.post(
        "/labels/scan",
        data={"grams": "32", "label": "Temp name"},
        files={"image": ("label.png", _tiny_png(), "image/png")},
    )
    label_id = response.json()["saved_label"]["id"]
    renamed = client.patch(f"/labels/{label_id}", json={"label": "Pantry peanut butter"})
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Pantry peanut butter"


def test_scan_requires_label(client, fake_reader):
    response = client.post(
        "/labels/scan",
        data={"grams": "10", "label": "   "},
        files={"image": ("label.png", _tiny_png(), "image/png")},
    )
    assert response.status_code in {400, 422}


def test_scan_rejects_non_image(client, fake_reader):
    response = client.post(
        "/labels/scan",
        data={"grams": "10", "label": "Something"},
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_ui_has_webcam_controls(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "mymacro" in response.text
    assert "getUserMedia" in response.text
    assert "Start webcam" in response.text
    assert 'name="label"' in response.text or 'id="label"' in response.text
    assert "manual-panel" in response.text
    assert "/labels/manual" in response.text


def test_scan_parse_error_returns_manual_entry_payload(client):
    class BrokenReader:
        def read(self, image_bytes: bytes, content_type: str = "image/jpeg"):
            from mymacro.label_parse import LabelParseError

            raise LabelParseError(
                "Could not read nutrition facts. Missing: serving size (g)",
                missing=["serving size (g)"],
                partial={"calories": 120, "protein_g": 5, "carbs_g": 10, "fat_g": 2},
                raw_text="Calories 120",
            )

    set_label_reader(BrokenReader())
    try:
        response = client.post(
            "/labels/scan",
            data={"grams": "40", "label": "Mystery bar"},
            files={"image": ("label.png", _tiny_png(), "image/png")},
        )
    finally:
        set_label_reader(None)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["manual_entry_required"] is True
    assert "serving size (g)" in detail["missing"]
    assert detail["partial"]["calories"] == 120


def test_manual_label_logs_intake(client):
    today = date.today().isoformat()
    response = client.post(
        "/labels/manual",
        json={
            "label": "Manual granola",
            "serving_size_g": 40,
            "calories": 180,
            "protein_g": 4,
            "carbs_g": 30,
            "fat_g": 6,
            "grams": 20,
            "day": today,
            "meal": "breakfast",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "manual"
    assert body["label"] == "Manual granola"
    assert body["servings"] == 0.5
    assert body["scaled_macros"]["calories"] == 90.0
    assert body["saved_label"]["serving_size_g"] == 40

    listed = client.get("/labels")
    assert any(item["label"] == "Manual granola" for item in listed.json())


def test_tesseract_reader_on_synthetic_label():
    """End-to-end offline OCR against a rendered nutrition label (needs tesseract)."""
    pytesseract = pytest.importorskip("pytesseract")
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("tesseract binary not installed")

    from mymacro.label_reader import TesseractLabelReader

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    image = Image.new("RGB", (1000, 700), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    lines = [
        "Product: Oat Crackers",
        "Nutrition Facts",
        "Serving Size 30 grams",
        "Calories 140",
        "Total Fat 5 grams",
        "Total Carbohydrate 20 grams",
        "Protein 3 grams",
    ]
    y = 40
    for line in lines:
        draw.text((40, y), line, fill=(0, 0, 0), font=font)
        y += 70
    buf = BytesIO()
    image.save(buf, format="PNG")

    facts = TesseractLabelReader().read(buf.getvalue(), content_type="image/png")
    assert facts.serving_size_g == 30
    assert facts.calories == 140
    assert facts.protein_g == 3
    assert facts.carbs_g == 20
    assert facts.fat_g == 5
