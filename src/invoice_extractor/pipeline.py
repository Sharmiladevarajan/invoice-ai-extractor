from __future__ import annotations

import logging
from pathlib import Path

from invoice_extractor.constants import (
    IMAGE_FROM_ID,
    IMAGE_LIMIT,
    IMAGE_PATTERN,
    IMAGE_TO_ID,
    INPUT_DIR,
    OCR_ENGINE_DEFAULT,
    TEMPLATE_PATH,
)
from invoice_extractor.export import write_csv, write_excel
from invoice_extractor.hybrid import extract_fields, load_template
from invoice_extractor.image_selection import select_images
from invoice_extractor.models import InvoiceFields, ProcessingResult
from invoice_extractor.ocr import check_ocr_engine, create_ocr

logger = logging.getLogger(__name__)


class InvoicePipeline:
    def __init__(self, ocr_engine: str | None = None, use_llm: bool = True) -> None:
        name = (ocr_engine or OCR_ENGINE_DEFAULT).lower()
        err = check_ocr_engine(name)
        if err:
            raise ValueError(err)
        self.ocr = create_ocr(name)
        self.ocr_name = name
        self.template = load_template(TEMPLATE_PATH)
        self.use_llm = use_llm

    def process_image(self, image_path: Path) -> ProcessingResult:
        try:
            blocks, raw_text, size = self.ocr.read_image(image_path)
            fields = extract_fields(
                blocks, raw_text, size, image_path.name, self.template, use_llm=self.use_llm
            )
            return ProcessingResult(image_path=image_path, fields=fields, raw_text=raw_text)
        except Exception as exc:
            logger.exception("Failed: %s", image_path.name)
            return ProcessingResult(
                image_path=image_path,
                fields=InvoiceFields(filename=image_path.name),
                success=False,
                error=str(exc),
            )

    def process_directory(self, input_dir: Path | None = None) -> list[ProcessingResult]:
        folder = input_dir or INPUT_DIR
        images = sorted(folder.glob(IMAGE_PATTERN))
        if not images:
            images = sorted(
                p for p in folder.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
        images = select_images(
            images, start_id=IMAGE_FROM_ID, end_id=IMAGE_TO_ID, limit=IMAGE_LIMIT
        )
        if not images:
            return []

        logger.info("[%s] %d image(s): %s → %s", self.ocr_name, len(images), images[0].name, images[-1].name)
        return [self.process_image(p) for p in images]

    def run_batch(
        self, input_dir: Path | None = None, write_xlsx: bool = True
    ) -> tuple[list[ProcessingResult], str | None]:
        results = self.process_directory(input_dir)
        warning = None
        if not results:
            return [], warning

        ok = [r for r in results if r.success]
        if not ok:
            return results, "All images failed — check OCR engine and logs."

        write_csv(ok)
        if write_xlsx:
            _, excel_warn = write_excel(ok)
            warning = excel_warn
        return results, warning
