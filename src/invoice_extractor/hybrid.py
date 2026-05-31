from __future__ import annotations

import logging
import os

import yaml

from invoice_extractor.constants import LLM_ENABLED, TEMPLATE_PATH
from invoice_extractor.llm_extractor import extract_from_text, merge_fields
from invoice_extractor.models import FIELD_KEYS, InvoiceFields, OcrBlock
from invoice_extractor.parser import TemplateParser

logger = logging.getLogger(__name__)


def load_template(path=None) -> dict:
    with open(path or TEMPLATE_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def fields_complete(fields: InvoiceFields) -> bool:
    data = fields.to_dict()
    return all(str(data.get(key, "")).strip() for key in FIELD_KEYS)


def extract_fields(
    blocks: list[OcrBlock],
    raw_text: str,
    image_size: tuple[int, int],
    filename: str,
    template: dict | None = None,
    use_llm: bool = True,
) -> InvoiceFields:
    template = template or load_template()
    fields = TemplateParser(template, image_size).parse(blocks, filename)

    if not use_llm or not LLM_ENABLED or fields_complete(fields):
        return fields
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return fields

    try:
        logger.info("Missing fields on %s — calling LLM", filename)
        llm_data = extract_from_text(raw_text)
        return merge_fields(fields, llm_data) if llm_data else fields
    except Exception as exc:
        logger.warning("LLM skipped: %s", exc)
        return fields
