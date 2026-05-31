from __future__ import annotations

import re
from typing import Any

from invoice_extractor.models import InvoiceFields, OcrBlock, TextLine
from invoice_extractor.parser.layout import LayoutAnalyzer


class TemplateParser:
    """Extracts invoice fields by matching template labels and spatial structure."""

    TAX_ID_PATTERN = re.compile(r"\b[A-Z0-9]{2,4}-[A-Z0-9]{2,4}-[A-Z0-9]{2,6}\b", re.I)
    DATE_PATTERN = re.compile(r"\b\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}\b")
    # US: 1,612.50  |  European: 1 612,50 or 1612,50
    AMOUNT_PATTERN = re.compile(
        r"[\$€£]?\s*(?:\d{1,3}(?:[ \u00a0,]\d{3})+[.,]\d{2}|\d+[.,]\d{2})",
        re.IGNORECASE,
    )
    PERCENT_PATTERN = re.compile(r"\d+\s*%")
    INVOICE_NO_PATTERN = re.compile(r"\b[A-Z0-9][A-Z0-9\-]{2,}\b", re.I)

    def __init__(self, template: dict[str, Any], image_size: tuple[int, int]) -> None:
        self.template = template
        self.layout = LayoutAnalyzer(image_size)

    def parse(self, blocks: list[OcrBlock], filename: str) -> InvoiceFields:
        lines = self.layout.group_lines(blocks)
        sections = self.layout.split_sections(blocks)
        field_defs: dict[str, Any] = self.template.get("fields", {})

        return InvoiceFields(
            filename=filename,
            seller_name=self._extract_party_name(sections["seller"], field_defs.get("seller_name", {})),
            seller_tax_id=self._extract_tax_id(sections["seller"]),
            client_name=self._extract_party_name(sections["client"], field_defs.get("client_name", {})),
            client_tax_id=self._extract_tax_id(sections["client"]),
            invoice_number=self._extract_labeled_value(
                lines, field_defs.get("invoice_number", {}), fallback=self._find_invoice_number(lines)
            ),
            invoice_date=self._extract_labeled_value(
                lines, field_defs.get("invoice_date", {}), fallback=self._find_date(lines)
            ),
            net_worth=self._extract_summary_field(lines, field_defs.get("net_worth", {}), "net_worth"),
            vat=self._extract_summary_field(lines, field_defs.get("vat", {}), "vat"),
            gross_worth=self._extract_summary_field(lines, field_defs.get("gross_worth", {}), "gross_worth"),
        )

    def _extract_summary_field(
        self,
        lines: list[TextLine],
        field_def: dict[str, Any],
        field_key: str,
    ) -> str:
        table_totals = self._extract_summary_table_totals(lines)
        if table_totals.get(field_key):
            return table_totals[field_key]

        if field_key == "net_worth":
            kind = "net"
        elif field_key == "gross_worth":
            kind = "gross"
        else:
            kind = "vat"

        return self._extract_summary_amount(lines, field_def, kind)

    def _extract_party_name(self, section_blocks: list[OcrBlock], field_def: dict[str, Any]) -> str:
        labels = field_def.get("labels", ["seller", "client"])
        skip = field_def.get("skip_labels", [])
        section_lines = self.layout.group_lines(section_blocks)

        for idx, line in enumerate(section_lines):
            if not self.layout.contains_label(line.text, labels):
                continue
            remainder = self._value_after_label(line.text, labels)
            if remainder and not self.layout.is_noise(remainder, skip):
                return self.layout.clean_name(remainder)

            for next_line in section_lines[idx + 1 : idx + 4]:
                if self.layout.is_noise(next_line.text, skip):
                    continue
                if self.TAX_ID_PATTERN.search(next_line.text):
                    continue
                return self.layout.clean_name(next_line.text)

        for line in section_lines[:5]:
            if self.layout.is_noise(line.text, skip):
                continue
            if self.TAX_ID_PATTERN.search(line.text):
                continue
            if self.layout.contains_label(line.text, labels):
                continue
            return self.layout.clean_name(line.text)

        return ""

    def _extract_tax_id(self, section_blocks: list[OcrBlock]) -> str:
        section_lines = self.layout.group_lines(section_blocks)
        tax_labels = ["tax id", "vat id", "tax id:"]

        for idx, line in enumerate(section_lines):
            if not self.layout.contains_label(line.text, tax_labels):
                continue
            inline = self._value_after_label(line.text, tax_labels)
            match = self.TAX_ID_PATTERN.search(inline) or self.TAX_ID_PATTERN.search(line.text)
            if match:
                return match.group(0)

            for next_line in section_lines[idx + 1 : idx + 3]:
                match = self.TAX_ID_PATTERN.search(next_line.text)
                if match:
                    return match.group(0)

        for line in section_lines:
            match = self.TAX_ID_PATTERN.search(line.text)
            if match:
                return match.group(0)

        return ""

    def _extract_labeled_value(
        self,
        lines: list[TextLine],
        field_def: dict[str, Any],
        fallback: str = "",
    ) -> str:
        labels = field_def.get("labels", [])
        pattern = field_def.get("value_pattern")

        for idx, line in enumerate(lines):
            if not self.layout.contains_label(line.text, labels):
                continue

            inline = self._value_after_label(line.text, labels)
            if pattern:
                match = self.layout.extract_pattern(inline, pattern)
                if match:
                    return match
            if inline:
                return inline.strip()

            for next_line in lines[idx + 1 : idx + 3]:
                candidate = next_line.text.strip()
                if pattern:
                    match = self.layout.extract_pattern(candidate, pattern)
                    if match:
                        return match
                if candidate:
                    return candidate

        return fallback

    def _extract_summary_table_totals(
        self,
        lines: list[TextLine],
    ) -> dict[str, str]:
        """Parse SUMMARY table: column headers + totals row (structure-based)."""
        summary_start = self._find_summary_index(lines)
        if summary_start is None:
            region_lines = self.layout.summary_region(lines)
        else:
            region_lines = lines[summary_start : summary_start + 10]

        header_line: TextLine | None = None
        header_map: dict[str, float] = {}

        for line in region_lines:
            normalized = self.layout.normalize(line.text)
            if "net worth" in normalized and ("vat" in normalized or "gross" in normalized):
                header_line = line
                header_map = self._map_summary_headers(line)
                break

        if header_line and header_map:
            header_idx = region_lines.index(header_line)
            for line in region_lines[header_idx + 1 : header_idx + 4]:
                if self.PERCENT_PATTERN.search(line.text) and len(self._all_amounts(line.text)) < 2:
                    continue
                row_values = self._amounts_by_columns(line, header_map)
                if len(row_values) >= 2:
                    return row_values

        return self._extract_summary_row_amounts(region_lines)

    def _find_summary_index(self, lines: list[TextLine]) -> int | None:
        for idx, line in enumerate(lines):
            if self.layout.normalize(line.text) == "summary" or line.text.strip().upper() == "SUMMARY":
                return idx
            if "summary" in self.layout.normalize(line.text) and len(line.text) < 20:
                return idx
        return None

    def _map_summary_headers(self, line: TextLine) -> dict[str, float]:
        headers: dict[str, float] = {}
        for block in line.blocks:
            text = self.layout.normalize(block.text)
            if "%" in text:
                continue
            if "net worth" in text and "gross" not in text:
                headers["net_worth"] = block.center_x
            elif text == "vat" or (text.startswith("vat") and "worth" not in text):
                headers["vat"] = block.center_x
            elif "gross worth" in text:
                headers["gross_worth"] = block.center_x
        return headers

    def _amounts_by_columns(
        self,
        line: TextLine,
        header_map: dict[str, float],
    ) -> dict[str, str]:
        values: dict[str, str] = {}
        amount_blocks: list[tuple[float, str]] = []

        for block in line.blocks:
            amount = self._first_amount(block.text)
            if amount and not self.PERCENT_PATTERN.search(block.text):
                amount_blocks.append((block.center_x, amount))

        if not amount_blocks:
            return values

        for field, header_x in header_map.items():
            if not amount_blocks:
                break
            closest = min(amount_blocks, key=lambda item: abs(item[0] - header_x))
            values[field] = self.layout.clean_amount(closest[1])
            amount_blocks = [item for item in amount_blocks if item != closest]

        return values

    def _extract_summary_row_amounts(self, region_lines: list[TextLine]) -> dict[str, str]:
        """Fallback: one SUMMARY row with net, vat, gross amounts left-to-right."""
        for line in region_lines:
            amounts = self._all_amounts(line.text)
            amounts = [a for a in amounts if not self.PERCENT_PATTERN.search(a)]
            if len(amounts) >= 3:
                ordered = sorted(
                    [(block.center_x, self._first_amount(block.text)) for block in line.blocks if self._first_amount(block.text)],
                    key=lambda item: item[0],
                )
                values = [a for _, a in ordered if a and not self.PERCENT_PATTERN.search(a or "")]
                if len(values) >= 3:
                    return {
                        "net_worth": self.layout.clean_amount(values[0]),
                        "vat": self.layout.clean_amount(values[1]),
                        "gross_worth": self.layout.clean_amount(values[2]),
                    }
        return {}

    def _extract_summary_amount(
        self,
        summary_lines: list[TextLine],
        field_def: dict[str, Any],
        kind: str,
    ) -> str:
        labels = field_def.get("labels", [])
        pattern = field_def.get("value_pattern", r"[\$€£]?\s*[\d\s,\.]+\.?\d*")

        for idx, line in enumerate(summary_lines):
            normalized = self.layout.normalize(line.text)
            if not self.layout.contains_label(line.text, labels):
                continue

            inline = self._value_after_label(line.text, labels)
            amount = (
                self._amount_on_same_line_right(line, labels)
                or self._first_amount(inline)
                or self._first_amount(line.text)
            )
            if amount:
                return self.layout.clean_amount(amount)

            for next_line in summary_lines[idx + 1 : idx + 3]:
                amount = self._first_amount(next_line.text)
                if amount:
                    return self.layout.clean_amount(amount)

        return self._fallback_summary_amount(summary_lines, kind)

    def _fallback_summary_amount(self, summary_lines: list[TextLine], kind: str) -> str:
        keyword_map = {
            "net": ["net worth", "total net"],
            "vat": ["vat", "tax"],
            "gross": ["gross worth", "total gross", "amount due"],
        }
        keywords = keyword_map.get(kind, [])

        for line in summary_lines:
            normalized = self.layout.normalize(line.text)
            if any(keyword in normalized for keyword in keywords):
                amount = self._first_amount(line.text)
                if amount:
                    return self.layout.clean_amount(amount)

        amounts = [self._first_amount(line.text) for line in summary_lines]
        amounts = [a for a in amounts if a]
        if not amounts:
            return ""

        if kind == "gross":
            return self.layout.clean_amount(max(amounts, key=self._amount_key))
        if kind == "net":
            return self.layout.clean_amount(min(amounts, key=self._amount_key))
        if kind == "vat" and len(amounts) >= 2:
            sorted_amounts = sorted(amounts, key=self._amount_key)
            return self.layout.clean_amount(sorted_amounts[1] if len(sorted_amounts) > 1 else sorted_amounts[0])

        return ""

    def _find_invoice_number(self, lines: list[TextLine]) -> str:
        for line in lines[:12]:
            normalized = self.layout.normalize(line.text)
            if "invoice" in normalized:
                match = self.INVOICE_NO_PATTERN.search(line.text)
                if match:
                    return match.group(0)
        for line in lines[:8]:
            match = self.INVOICE_NO_PATTERN.search(line.text)
            if match and not self.DATE_PATTERN.search(match.group(0)):
                return match.group(0)
        return ""

    def _find_date(self, lines: list[TextLine]) -> str:
        for line in lines[:15]:
            match = self.DATE_PATTERN.search(line.text)
            if match:
                return match.group(0)
        return ""

    @staticmethod
    def _value_after_label(text: str, labels: list[str]) -> str:
        lowered = text.lower()
        for label in sorted(labels, key=len, reverse=True):
            idx = lowered.find(label)
            if idx >= 0:
                return text[idx + len(label) :].strip(" :.-")
        return text.strip()

    def _amount_on_same_line_right(self, line: TextLine, labels: list[str]) -> str | None:
        label_block: OcrBlock | None = None
        for block in line.blocks:
            if self.layout.contains_label(block.text, labels):
                label_block = block
                break
        if label_block is None:
            return None

        candidates: list[tuple[float, str]] = []
        for block in line.blocks:
            if block.x_min <= label_block.x_max:
                continue
            amount = self._first_amount(block.text)
            if amount and not self.PERCENT_PATTERN.search(block.text):
                candidates.append((block.center_x, amount))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    @staticmethod
    def _all_amounts(text: str) -> list[str]:
        return [match.group(0).strip() for match in TemplateParser.AMOUNT_PATTERN.finditer(text)]

    @staticmethod
    def _first_amount(text: str) -> str | None:
        match = TemplateParser.AMOUNT_PATTERN.search(text)
        return match.group(0).strip() if match else None

    @staticmethod
    def _amount_key(value: str) -> float:
        normalized = value.replace("\u00a0", " ").strip()
        normalized = re.sub(r"[\$€£]", "", normalized).strip()
        if "," in normalized and "." not in normalized:
            normalized = normalized.replace(" ", "").replace(",", ".")
        else:
            normalized = normalized.replace(" ", "").replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return 0.0
