"""FatSecret barcode lookup client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from mymacro.config import settings
from mymacro.micronutrients import normalize_micronutrients
from mymacro.schemas import NutritionFacts


class FatSecretError(RuntimeError):
    pass


@dataclass
class _Token:
    value: str
    expires_at: float


class FatSecretClient(Protocol):
    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts: ...


_MICRO_MAP = {
    "saturated_fat": "saturated_fat_g",
    "cholesterol": "cholesterol_mg",
    "sodium": "sodium_mg",
    "fiber": "fiber_g",
    "sugar": "total_sugars_g",
    "added_sugars": "added_sugars_g",
    "vitamin_d": "vitamin_d_mcg",
    "calcium": "calcium_mg",
    "iron": "iron_mg",
    "potassium": "potassium_mg",
    "vitamin_c": "vitamin_c_mg",
    "vitamin_a": "vitamin_a_mcg",
}


class HttpFatSecretClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: _Token | None = None

    def _access_token(self) -> str:
        now = time.time()
        if self._token and self._token.expires_at > now + 30:
            return self._token.value
        with httpx.Client(timeout=30) as client:
            response = client.post(
                settings.fatsecret_token_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": "basic",
                },
                auth=(self.client_id, self.client_secret),
            )
        if response.status_code >= 400:
            raise FatSecretError(f"FatSecret token error: {response.status_code}")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise FatSecretError("FatSecret token missing access_token")
        expires_in = int(payload.get("expires_in", 3600))
        self._token = _Token(token, now + expires_in)
        return token

    def _api_get(self, params: dict[str, str]) -> dict:
        token = self._access_token()
        all_params = {
            "format": "json",
            **params,
        }
        with httpx.Client(timeout=30) as client:
            response = client.get(
                settings.fatsecret_api_url,
                params=all_params,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise FatSecretError(f"FatSecret API error: {response.status_code}")
        payload = response.json()
        err = payload.get("error")
        if err:
            message = err.get("message") if isinstance(err, dict) else str(err)
            code = err.get("code") if isinstance(err, dict) else "unknown"
            raise FatSecretError(f"FatSecret API error ({code}): {message}")
        return payload

    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts:
        barcode = barcode.strip()
        if not barcode:
            raise FatSecretError("barcode is required")

        lookup = self._api_get(
            {
                "method": "food.find_id_for_barcode",
                "barcode": barcode,
            }
        )
        food_id = (
            lookup.get("food_id")
            or lookup.get("food", {}).get("food_id")
            or lookup.get("foods", {}).get("food", {}).get("food_id")
        )
        if not food_id:
            raise FatSecretError("No FatSecret food found for barcode")

        data = self._api_get(
            {
                "method": "food.get.v4",
                "food_id": str(food_id),
                "include_food_images": "false",
            }
        )
        food = data.get("food") or data
        food_name = food.get("food_name") or f"Barcode {barcode}"

        servings_block = (food.get("servings") or {}).get("serving")
        if isinstance(servings_block, list):
            serving = servings_block[0]
        else:
            serving = servings_block or {}

        metric_amount = serving.get("metric_serving_amount") or serving.get("number_of_units")
        metric_unit = (serving.get("metric_serving_unit") or "g").lower()
        if metric_unit in {"g", "gram", "grams"}:
            serving_size_g = float(metric_amount or 100)
        else:
            serving_size_g = 100.0

        facts = NutritionFacts(
            product_name=food_name,
            serving_size_g=max(serving_size_g, 1.0),
            calories=float(serving.get("calories") or 0),
            protein_g=float(serving.get("protein") or 0),
            carbs_g=float(serving.get("carbohydrate") or 0),
            fat_g=float(serving.get("fat") or 0),
            micronutrients=normalize_micronutrients(
                {
                    key_out: serving.get(key_in)
                    for key_in, key_out in _MICRO_MAP.items()
                    if serving.get(key_in) not in (None, "")
                }
            ),
            raw_text=f"fatsecret:barcode={barcode};food_id={food_id}",
        )
        if facts.calories <= 0 and facts.protein_g == 0 and facts.carbs_g == 0 and facts.fat_g == 0:
            raise FatSecretError("FatSecret response missing nutrition data")
        return facts


_client: FatSecretClient | None = None


def build_fatsecret_client() -> FatSecretClient:
    cid = settings.resolved_fatsecret_client_id()
    secret = settings.resolved_fatsecret_client_secret()
    if not cid or not secret:
        raise FatSecretError(
            "FatSecret credentials not configured. Set MYMACRO_FATSECRET_CLIENT_ID and "
            "MYMACRO_FATSECRET_CLIENT_SECRET."
        )
    return HttpFatSecretClient(cid, secret)


def get_fatsecret_client() -> FatSecretClient:
    global _client
    if _client is None:
        _client = build_fatsecret_client()
    return _client


def set_fatsecret_client(client: FatSecretClient | None) -> None:
    global _client
    _client = client
