from datetime import date


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_food_and_list(client):
    payload = {
        "name": "Greek Yogurt",
        "serving_label": "170g cup",
        "calories": 100,
        "protein_g": 17,
        "carbs_g": 6,
        "fat_g": 0,
    }
    created = client.post("/foods", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Greek Yogurt"
    assert body["id"] >= 1

    listed = client.get("/foods")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_duplicate_food_rejected(client):
    payload = {
        "name": "Banana",
        "calories": 105,
        "protein_g": 1.3,
        "carbs_g": 27,
        "fat_g": 0.3,
    }
    assert client.post("/foods", json=payload).status_code == 201
    assert client.post("/foods", json=payload).status_code == 409


def test_log_entry_and_day_summary(client):
    food = client.post(
        "/foods",
        json={
            "name": "Chicken Breast",
            "serving_label": "100g",
            "calories": 165,
            "protein_g": 31,
            "carbs_g": 0,
            "fat_g": 3.6,
        },
    ).json()

    today = date.today().isoformat()
    goal = client.put(
        "/goals",
        json={
            "day": today,
            "calories": 2000,
            "protein_g": 150,
            "carbs_g": 200,
            "fat_g": 65,
        },
    )
    assert goal.status_code == 200

    entry = client.post(
        "/entries",
        json={
            "food_id": food["id"],
            "day": today,
            "servings": 2,
            "meal": "lunch",
        },
    )
    assert entry.status_code == 201
    assert entry.json()["macros"]["protein_g"] == 62.0

    summary = client.get(f"/days/{today}/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["consumed"]["calories"] == 330.0
    assert data["remaining"]["protein_g"] == 88.0
    assert len(data["entries"]) == 1


def test_goal_fallback_to_prior_day(client):
    client.put(
        "/goals",
        json={
            "day": "2026-01-01",
            "calories": 1800,
            "protein_g": 140,
            "carbs_g": 180,
            "fat_g": 60,
        },
    )
    response = client.get("/goals/2026-01-03")
    assert response.status_code == 200
    assert response.json()["day"] == "2026-01-01"
    assert response.json()["calories"] == 1800
