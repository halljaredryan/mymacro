"""Read nutrition facts from a product-label image."""

from __future__ import annotations

import base64
import json
import logging
from typing import Protocol

import httpx

from mymacro.config import settings
from mymacro.label_parse import LabelParseError, parse_nutrition_text
from mymacro.micronutrients import normalize_micronutrients
from mymacro.schemas import NutritionFacts

logger = logging.getLogger(__name__)

_VISION_PROMPT = """
Extract nutrition facts from this product label image.
Return ONLY valid JSON with these keys:
{
  "product_name": string or null,
  "serving_size_g": number (grams for one serving),
  "calories": number,
  "protein_g": number,
  "carbs_g": number,
  "fat_g": number,
  "micronutrients": {
    "saturated_fat_g": number|null,
    "cholesterol_mg": number|null,
    "sodium_mg": number|null,
    "fiber_g": number|null,
    "total_sugars_g": number|null,
    "added_sugars_g": number|null,
    "vitamin_d_mcg": number|null,
    "calcium_mg": number|null,
    "iron_mg": number|null,
    "potassium_mg": number|null,
    "vitamin_c_mg": number|null,
    "vitamin_a_mcg": number|null
  }
}
Use the labeled serving size in grams. If the label is per 100g, set serving_size_g to 100.
Omit micronutrient keys that are not present on the label.
""".strip()


class LabelReader(Protocol):
    def read(self, image_bytes: bytes, content_type: str = "image/jpeg") -> NutritionFacts: ...


class OpenAIVisionLabelReader:
    """Use an OpenAI-compatible vision chat model to extract structured facts."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.openai_vision_model

    def read(self, image_bytes: bytes, content_type: str = "image/jpeg") -> NutritionFacts:
        mime = content_type or "image/jpeg"
        if mime == "image/jpg":
            mime = "image/jpeg"
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            raise LabelParseError(
                f"Vision API error ({response.status_code}): {response.text[:300]}"
            )
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        key_map = {
            "serving_size_g": "serving size (g)",
            "calories": "calories",
            "protein_g": "protein",
            "carbs_g": "carbohydrates",
            "fat_g": "fat",
        }
        partial: dict = {"product_name": data.get("product_name") or "Scanned food"}
        missing: list[str] = []
        parsed: dict[str, float] = {}
        for key, label in key_map.items():
            raw = data.get(key)
            if raw is None or raw == "":
                missing.append(label)
                continue
            try:
                parsed[key] = float(raw)
                partial[key] = parsed[key]
            except (TypeError, ValueError):
                missing.append(label)
        micros = normalize_micronutrients(data.get("micronutrients") or {})
        partial["micronutrients"] = micros
        if missing:
            raise LabelParseError(
                "Could not read nutrition facts. Missing: " + ", ".join(missing),
                missing=missing,
                partial=partial,
                raw_text=content,
            )
        return NutritionFacts(
            product_name=partial["product_name"],
            serving_size_g=parsed["serving_size_g"],
            calories=parsed["calories"],
            protein_g=parsed["protein_g"],
            carbs_g=parsed["carbs_g"],
            fat_g=parsed["fat_g"],
            micronutrients=micros,
            raw_text=content,
        )


class TesseractLabelReader:
    """Offline OCR fallback using Tesseract + regex parsing."""

    def read(self, image_bytes: bytes, content_type: str = "image/jpeg") -> NutritionFacts:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise LabelParseError(
                "Tesseract OCR dependencies are not installed "
                "(pip install pillow pytesseract, and apt install tesseract-ocr)."
            ) from exc

        from io import BytesIO

        from PIL import ImageOps

        image = Image.open(BytesIO(image_bytes)).convert("L")
        # Upscale small phone photos / screenshots for stabler OCR.
        min_width = 900
        if image.width < min_width:
            scale = min_width / image.width
            image = image.resize(
                (int(image.width * scale), int(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        image = ImageOps.autocontrast(image)
        text = pytesseract.image_to_string(image, config="--psm 6")
        if not text.strip():
            raise LabelParseError("OCR returned no text from the image")
        return parse_nutrition_text(text)


class CompositeLabelReader:
    """Prefer OpenAI vision when configured; otherwise use Tesseract."""

    def __init__(self, primary: LabelReader | None, fallback: LabelReader) -> None:
        self.primary = primary
        self.fallback = fallback

    def read(self, image_bytes: bytes, content_type: str = "image/jpeg") -> NutritionFacts:
        if self.primary is not None:
            try:
                return self.primary.read(image_bytes, content_type)
            except Exception:
                logger.exception("Primary label reader failed; trying fallback")
        return self.fallback.read(image_bytes, content_type)


def build_label_reader() -> LabelReader:
    api_key = settings.resolved_openai_api_key()
    primary = OpenAIVisionLabelReader(api_key=api_key) if api_key else None
    return CompositeLabelReader(primary=primary, fallback=TesseractLabelReader())


_reader: LabelReader | None = None


def get_label_reader() -> LabelReader:
    global _reader
    if _reader is None:
        _reader = build_label_reader()
    return _reader


def set_label_reader(reader: LabelReader | None) -> None:
    """Override the process-wide reader (used by tests)."""
    global _reader
    _reader = reader
