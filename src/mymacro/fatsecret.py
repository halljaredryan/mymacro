"""FatSecret barcode lookup client (OAuth 1.0 + OAuth 2.0 fallback)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx
from requests_oauthlib import OAuth1Session

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


def _normalize_barcode(barcode: str) -> str:
    digits = "".join(ch for ch in barcode.strip() if ch.isdigit())
    if not digits:
        raise FatSecretError("barcode is required")
    # FatSecret expects GTIN-13 (left-pad with zeros).
    if len(digits) < 13:
        digits = digits.zfill(13)
    return digits


def _facts_from_food_payload(food: dict, *, barcode: str, food_id: str) -> NutritionFacts:
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
    # Zero-calorie items (e.g. water) are valid when FatSecret returned a product.
    return facts


def _extract_food_id(lookup: dict) -> str | None:
    food_id = (
        lookup.get("food_id")
        or lookup.get("food", {}).get("food_id")
        or lookup.get("foods", {}).get("food", {}).get("food_id")
    )
    if isinstance(food_id, dict):
        food_id = food_id.get("value")
    if food_id is None or food_id == "":
        return None
    food_id_str = str(food_id).strip()
    if food_id_str in {"0", "None"}:
        return None
    return food_id_str


def _raise_if_error(payload: dict) -> None:
    err = payload.get("error")
    if not err:
        return
    message = err.get("message") if isinstance(err, dict) else str(err)
    code = err.get("code") if isinstance(err, dict) else "unknown"
    raise FatSecretError(f"FatSecret API error ({code}): {message}")


class OAuth1FatSecretClient:
    """Consumer key/secret auth (FatSecret OAuth 1.0)."""

    def __init__(self, consumer_key: str, consumer_secret: str) -> None:
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def _api_get(self, params: dict[str, str]) -> dict:
        oauth = OAuth1Session(self.consumer_key, client_secret=self.consumer_secret)
        response = oauth.get(
            settings.fatsecret_api_url,
            params={"format": "json", **params},
            timeout=30,
        )
        if response.status_code >= 400:
            raise FatSecretError(f"FatSecret API error: {response.status_code}")
        payload = response.json()
        _raise_if_error(payload)
        return payload

    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts:
        barcode = _normalize_barcode(barcode)
        lookup = None
        last_error: Exception | None = None
        for method in ("food.find_id_for_barcode", "food.find_id_for_barcode.v2"):
            try:
                lookup = self._api_get({"method": method, "barcode": barcode})
                break
            except FatSecretError as exc:
                last_error = exc
        if lookup is None:
            raise FatSecretError(
                str(last_error) if last_error else "FatSecret barcode lookup failed"
            )

        food_id = _extract_food_id(lookup)
        if not food_id:
            raise FatSecretError("No FatSecret food found for barcode")

        data = self._api_get(
            {
                "method": "food.get.v4",
                "food_id": food_id,
                "include_food_images": "false",
            }
        )
        food = data.get("food") or data
        return _facts_from_food_payload(food, barcode=barcode, food_id=food_id)


class OAuth2FatSecretClient:
    """Client ID/secret auth (FatSecret OAuth 2.0 client credentials)."""

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
        with httpx.Client(timeout=30) as client:
            response = client.get(
                settings.fatsecret_api_url,
                params={"format": "json", **params},
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise FatSecretError(f"FatSecret API error: {response.status_code}")
        payload = response.json()
        _raise_if_error(payload)
        return payload

    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts:
        barcode = _normalize_barcode(barcode)
        lookup = self._api_get(
            {
                "method": "food.find_id_for_barcode",
                "barcode": barcode,
            }
        )
        food_id = _extract_food_id(lookup)
        if not food_id:
            raise FatSecretError("No FatSecret food found for barcode")

        data = self._api_get(
            {
                "method": "food.get.v4",
                "food_id": food_id,
                "include_food_images": "false",
            }
        )
        food = data.get("food") or data
        return _facts_from_food_payload(food, barcode=barcode, food_id=food_id)


class HttpFatSecretClient:
    """Prefer OAuth1 consumer credentials; fall back to OAuth2 if needed."""

    def __init__(self, consumer_key: str, consumer_secret: str) -> None:
        self.oauth1 = OAuth1FatSecretClient(consumer_key, consumer_secret)
        self.oauth2 = OAuth2FatSecretClient(consumer_key, consumer_secret)

    def nutrition_for_barcode(self, barcode: str) -> NutritionFacts:
        try:
            return self.oauth1.nutrition_for_barcode(barcode)
        except FatSecretError as oauth1_error:
            try:
                return self.oauth2.nutrition_for_barcode(barcode)
            except FatSecretError as oauth2_error:
                raise FatSecretError(
                    f"{oauth1_error}; OAuth2 fallback: {oauth2_error}"
                ) from oauth2_error


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
