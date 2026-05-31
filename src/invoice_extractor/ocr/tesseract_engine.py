from __future__ import annotations

import os
from pathlib import Path

import cv2
import pytesseract
from pytesseract import Output, TesseractNotFoundError

from invoice_extractor.constants import OCR_MAX_WIDTH, TESSERACT_CMD
from invoice_extractor.models import OcrBlock


def _configure_tesseract() -> None:
    if TESSERACT_CMD and Path(TESSERACT_CMD).is_file():
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def tesseract_available() -> bool:
    try:
        _configure_tesseract()
        pytesseract.get_tesseract_version()
        return True
    except (TesseractNotFoundError, FileNotFoundError, OSError):
        return False


class TesseractEngine:
    def __init__(self) -> None:
        if not tesseract_available():
            raise RuntimeError(
                "Tesseract is not installed or not on PATH. "
                "Install from https://github.com/UB-Mannheim/tesseract/wiki "
                "or set TESSERACT_CMD in constants.py (e.g. "
                r'C:\Program Files\Tesseract-OCR\tesseract.exe). '
                "Or use EasyOCR in the UI."
            )
        _configure_tesseract()

    def read_image(self, image_path: Path) -> tuple[list[OcrBlock], str, tuple[int, int]]:
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")

        height, width = image.shape[:2]
        if width > OCR_MAX_WIDTH:
            scale = OCR_MAX_WIDTH / width
            image = cv2.resize(image, None, fx=scale, fy=scale)
            height, width = image.shape[:2]

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, output_type=Output.DICT)

        blocks: list[OcrBlock] = []
        lines: list[str] = []
        for i, text in enumerate(data["text"]):
            cleaned = (text or "").strip()
            if not cleaned or float(data["conf"][i]) < 0:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            blocks.append(
                OcrBlock(
                    text=cleaned,
                    x_min=float(x),
                    y_min=float(y),
                    x_max=float(x + w),
                    y_max=float(y + h),
                    confidence=float(data["conf"][i]) / 100.0,
                )
            )
            lines.append(cleaned)

        return blocks, "\n".join(lines), (width, height)
