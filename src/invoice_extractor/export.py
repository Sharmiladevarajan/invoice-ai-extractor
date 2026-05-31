from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from invoice_extractor.constants import OUTPUT_CSV, OUTPUT_DIR, OUTPUT_XLSX
from invoice_extractor.models import CSV_COLUMNS, ProcessingResult

logger = logging.getLogger(__name__)


def _dataframe(results: list[ProcessingResult]) -> pd.DataFrame:
    ok = [r for r in results if r.success]
    rows = (ok or results)
    return pd.DataFrame([r.fields.to_csv_row() for r in rows], columns=CSV_COLUMNS)


def write_csv(results: list[ProcessingResult], path: Path | None = None) -> Path:
    out = path or OUTPUT_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    _dataframe(results).to_csv(out, index=False)
    return out


def write_excel(results: list[ProcessingResult], path: Path | None = None) -> tuple[Path, str | None]:
    """Write Excel. Returns (path, warning) — uses alternate file if output.xlsx is locked."""
    out = path or OUTPUT_XLSX
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = _dataframe(results)
    tmp = out.with_suffix(".tmp.xlsx")

    try:
        frame.to_excel(tmp, index=False, sheet_name="Invoices", engine="openpyxl")
        try:
            tmp.replace(out)
            return out, None
        except PermissionError:
            alt = OUTPUT_DIR / "output_latest.xlsx"
            tmp.replace(alt)
            warn = "output.xlsx is open in Excel — saved as output/output_latest.xlsx"
            logger.warning(warn)
            return alt, warn
    except PermissionError:
        alt = OUTPUT_DIR / "output_latest.xlsx"
        frame.to_excel(alt, index=False, sheet_name="Invoices", engine="openpyxl")
        warn = "output.xlsx is locked — saved as output/output_latest.xlsx"
        logger.warning(warn)
        return alt, warn
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
