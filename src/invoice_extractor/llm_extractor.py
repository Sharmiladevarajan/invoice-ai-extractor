from __future__ import annotations

import json
import logging
import os

from invoice_extractor.constants import LLM_MODEL
from invoice_extractor.models import FIELD_KEYS, InvoiceFields

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Extract invoice fields from OCR text. Return JSON only with keys: "
    + ", ".join(FIELD_KEYS)
    + ". Use empty string if unknown."
)


def extract_from_text(ocr_text: str) -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {}

    try:
        from openai import OpenAI
    except ImportError:
        return {}

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ocr_text[:12000]},
        ],
    )
    data = json.loads(response.choices[0].message.content or "{}")
    return {key: str(data.get(key, "") or "").strip() for key in FIELD_KEYS}


def merge_fields(parser_fields: InvoiceFields, llm_data: dict[str, str]) -> InvoiceFields:
    merged = parser_fields.to_dict()
    for key in FIELD_KEYS:
        if not str(merged.get(key, "")).strip() and llm_data.get(key):
            merged[key] = llm_data[key]
    merged["filename"] = parser_fields.filename
    return InvoiceFields(**merged)
