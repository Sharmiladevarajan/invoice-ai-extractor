from __future__ import annotations

from pathlib import Path

import cv2
import easyocr

from invoice_extractor.constants import OCR_GPU, OCR_LANGUAGES, OCR_MAX_WIDTH
from invoice_extractor.models import OcrBlock


class EasyOcrEngine:
    def __init__(self, gpu: bool | None = None) -> None:
        self._gpu = OCR_GPU if gpu is None else gpu
        self._reader: easyocr.Reader | None = None

    @property
    def reader(self) -> easyocr.Reader:
        if self._reader is None:
            self._reader = easyocr.Reader(OCR_LANGUAGES, gpu=self._gpu, verbose=False)
        return self._reader

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
        enhanced = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)
        detections = self.reader.readtext(enhanced)

        blocks: list[OcrBlock] = []
        lines: list[str] = []
        for bbox, text, confidence in detections:
            cleaned = text.strip()
            if not cleaned:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            blocks.append(
                OcrBlock(
                    text=cleaned,
                    x_min=float(min(xs)),
                    y_min=float(min(ys)),
                    x_max=float(max(xs)),
                    y_max=float(max(ys)),
                    confidence=float(confidence),
                )
            )
            lines.append(cleaned)

        return blocks, "\n".join(lines), (width, height)
