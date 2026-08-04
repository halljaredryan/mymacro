from datetime import date

from mymacro.macro_math import calories_from_macros, macros_match_calories


def test_calories_from_macros():
    assert calories_from_macros(150, 200, 66.67) == 2000.03
    assert macros_match_calories(2000.03, 150, 200, 66.67)


def test_settings_targets_sync_calories(client):
    response = client.put(
        "/settings/targets",
        json={
            "protein_g": 160,
            "carbs_g": 180,
            "fat_g": 70,
            "sync_calories_from_macros": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    expected = calories_from_macros(160, 180, 70)
    assert body["calories"] == expected
    assert body["calories_from_macros"] == expected

    loaded = client.get("/settings/targets")
    assert loaded.json()["protein_g"] == 160

    # Today's goal should be synced
    today = date.today().isoformat()
    goal = client.get(f"/goals/{today}")
    assert goal.status_code == 200
    assert goal.json()["calories"] == expected


def test_settings_rejects_mismatched_calories(client):
    response = client.put(
        "/settings/targets",
        json={
            "protein_g": 100,
            "carbs_g": 100,
            "fat_g": 100,
            "calories": 9999,
            "sync_calories_from_macros": False,
        },
    )
    assert response.status_code == 400
    assert "must equal" in response.json()["detail"]


def test_pages_exist(client):
    for path in ["/", "/barcode", "/logs", "/micros", "/settings"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "nav" in response.text
        assert "/static/app.css" in response.text


def test_logs_page_and_days_endpoint(client):
    today = date.today().isoformat()
    client.post(
        "/labels/manual",
        json={
            "label": "Logs yogurt",
            "serving_size_g": 170,
            "calories": 100,
            "protein_g": 17,
            "carbs_g": 6,
            "fat_g": 0,
            "grams": 170,
            "day": today,
        },
    )
    days = client.get("/days")
    assert days.status_code == 200
    assert any(item["day"] == today for item in days.json())

    page = client.get("/logs")
    assert "Daily logs" in page.text
    assert "/days/" in page.text


def test_micros_page_moved_off_home(client):
    home = client.get("/")
    assert "Daily micronutrients" not in home.text
    assert "Scan label" in home.text or "Scan" in home.text
    micros = client.get("/micros")
    assert micros.status_code == 200
    assert "Micronutrients" in micros.text


def test_settings_page(client):
    page = client.get("/settings")
    assert page.status_code == 200
    assert "protein×4" in page.text or "protein" in page.text
    assert "/settings/targets" in page.text
