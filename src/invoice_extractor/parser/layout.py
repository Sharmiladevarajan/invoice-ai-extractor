from __future__ import annotations

import re
from typing import Any

from invoice_extractor.models import OcrBlock, TextLine


class LayoutAnalyzer:
    """Groups OCR blocks into lines and document sections using relative layout."""

    LINE_Y_TOLERANCE_RATIO = 0.012

    def __init__(self, image_size: tuple[int, int]) -> None:
        self.width, self.height = image_size

    def group_lines(self, blocks: list[OcrBlock]) -> list[TextLine]:
        if not blocks:
            return []

        tolerance = max(8.0, self.height * self.LINE_Y_TOLERANCE_RATIO)
        sorted_blocks = sorted(blocks, key=lambda b: (b.center_y, b.x_min))
        lines: list[TextLine] = []
        current: list[OcrBlock] = [sorted_blocks[0]]

        for block in sorted_blocks[1:]:
            if abs(block.center_y - current[-1].center_y) <= tolerance:
                current.append(block)
            else:
                lines.append(TextLine(blocks=sorted(current, key=lambda b: b.x_min)))
                current = [block]

        lines.append(TextLine(blocks=sorted(current, key=lambda b: b.x_min)))
        return lines

    def split_sections(self, blocks: list[OcrBlock]) -> dict[str, list[OcrBlock]]:
        mid_x = self.width / 2
        seller: list[OcrBlock] = []
        client: list[OcrBlock] = []
        center: list[OcrBlock] = []

        for block in blocks:
            if block.center_x < mid_x * 0.95:
                seller.append(block)
            elif block.center_x > mid_x * 1.05:
                client.append(block)
            else:
                center.append(block)

        return {"seller": seller, "client": client, "center": center, "all": blocks}

    def summary_region(self, lines: list[TextLine]) -> list[TextLine]:
        """Bottom portion of the document where totals typically appear."""
        cutoff = self.height * 0.55
        return [line for line in lines if line.y_center >= cutoff]

    @staticmethod
    def normalize(text: str) -> str:
        lowered = text.lower().strip()
        return re.sub(r"\s+", " ", lowered)

    @staticmethod
    def contains_label(text: str, labels: list[str]) -> bool:
        normalized = LayoutAnalyzer.normalize(text)
        return any(label in normalized for label in labels)

    @staticmethod
    def extract_pattern(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(0).strip() if match else None

    @staticmethod
    def clean_amount(value: str) -> str:
        """Normalize money: strip duplicate currency symbols, then prefix with $."""
        cleaned = value.strip()
        if not cleaned:
            return ""
        cleaned = re.sub(r"^[\$€£]\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""
        return f"${cleaned}"

    @staticmethod
    def clean_name(value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip())
        for prefix in ("seller", "client", "buyer", "bill to"):
            if value.lower().startswith(prefix):
                value = value[len(prefix) :].strip(" :.-")
        return value

    @staticmethod
    def is_noise(text: str, skip_labels: list[str] | None = None) -> bool:
        normalized = LayoutAnalyzer.normalize(text)
        noise = {"iban", "address", "phone", "email", "www", "payment", "bank"}
        if skip_labels:
            noise.update(skip_labels)
        return any(token in normalized for token in noise)
