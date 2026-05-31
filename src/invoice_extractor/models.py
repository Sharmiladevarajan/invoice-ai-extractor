from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
    "filename",
    "Seller Name",
    "Seller Tax ID",
    "Client Name",
    "Client Tax ID",
    "Invoice Number",
    "Invoice Date",
    "Net Worth",
    "VAT",
    "Gross Worth",
]

FIELD_KEYS = [
    "seller_name",
    "seller_tax_id",
    "client_name",
    "client_tax_id",
    "invoice_number",
    "invoice_date",
    "net_worth",
    "vat",
    "gross_worth",
]


@dataclass
class OcrBlock:
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = 1.0

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass
class TextLine:
    blocks: list[OcrBlock] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(b.text for b in self.blocks)

    @property
    def y_center(self) -> float:
        if not self.blocks:
            return 0.0
        return sum(b.center_y for b in self.blocks) / len(self.blocks)

    @property
    def x_min(self) -> float:
        return min(b.x_min for b in self.blocks) if self.blocks else 0.0

    @property
    def x_max(self) -> float:
        return max(b.x_max for b in self.blocks) if self.blocks else 0.0


@dataclass
class InvoiceFields:
    filename: str = ""
    seller_name: str = ""
    seller_tax_id: str = ""
    client_name: str = ""
    client_tax_id: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    net_worth: str = ""
    vat: str = ""
    gross_worth: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "Seller Name": self.seller_name,
            "Seller Tax ID": self.seller_tax_id,
            "Client Name": self.client_name,
            "Client Tax ID": self.client_tax_id,
            "Invoice Number": self.invoice_number,
            "Invoice Date": self.invoice_date,
            "Net Worth": self.net_worth,
            "VAT": self.vat,
            "Gross Worth": self.gross_worth,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessingResult:
    image_path: Path
    fields: InvoiceFields
    raw_text: str = ""
    success: bool = True
    error: str | None = None
