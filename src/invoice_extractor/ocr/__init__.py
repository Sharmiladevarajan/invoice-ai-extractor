from __future__ import annotations

from invoice_extractor.constants import OCR_ENGINE_DEFAULT
from invoice_extractor.ocr.easyocr_engine import EasyOcrEngine
from invoice_extractor.ocr.tesseract_engine import TesseractEngine, tesseract_available

ENGINES = ("easyocr", "tesseract")


def create_ocr(engine: str | None = None):
    name = (engine or OCR_ENGINE_DEFAULT).lower().strip()
    if name == "easyocr":
        return EasyOcrEngine()
    if name == "tesseract":
        return TesseractEngine()
    raise ValueError(f"Unknown OCR '{name}'. Use: {', '.join(ENGINES)}")


def check_ocr_engine(engine: str) -> str | None:
    """Return error message if engine cannot run, else None."""
    name = engine.lower().strip()
    if name == "tesseract" and not tesseract_available():
        return (
            "Tesseract not found. Install it and add to PATH, or set TESSERACT_CMD in constants.py. "
            "Use EasyOCR instead."
        )
    if name not in ENGINES:
        return f"Unknown OCR '{engine}'."
    return None
