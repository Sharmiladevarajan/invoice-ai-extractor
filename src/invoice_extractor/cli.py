import argparse
import logging
import sys
from pathlib import Path

from invoice_extractor.constants import IMAGE_LIMIT, IMAGE_MAX_RECORDS, INPUT_DIR, OCR_ENGINE_DEFAULT
from invoice_extractor.pipeline import InvoicePipeline


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Invoice extractor")
    p.add_argument("--serve", action="store_true", help="Web UI + API")
    p.add_argument("--excel", action="store_true", help="Write Excel")
    p.add_argument("--ocr", choices=["easyocr", "tesseract"], default=OCR_ENGINE_DEFAULT)
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("-i", "--input-dir", type=Path, default=INPUT_DIR)
    p.add_argument("--limit", "-n", type=int, default=None,
                   help=f"Number of images (1–{IMAGE_MAX_RECORDS}, 0=all in range)")
    p.add_argument("-v", action="store_true")
    args = p.parse_args(argv)

    if args.limit is not None and (args.limit < 0 or args.limit > IMAGE_MAX_RECORDS):
        logging.error("limit must be 0–%d", IMAGE_MAX_RECORDS)
        return 1

    logging.basicConfig(level=logging.DEBUG if args.v else logging.INFO, format="%(message)s")

    if args.serve:
        import uvicorn
        from invoice_extractor.constants import API_HOST, API_PORT

        uvicorn.run("invoice_extractor.api.app:app", host=API_HOST, port=API_PORT)
        return 0

    if not args.input_dir.exists():
        logging.error("Folder not found: %s", args.input_dir)
        return 1

    results, warning = InvoicePipeline(ocr_engine=args.ocr, use_llm=not args.no_llm).run_batch(
        args.input_dir, write_xlsx=args.excel, limit=args.limit
    )
    if warning:
        logging.warning(warning)
    if not results:
        logging.error("No images found")
        return 1
    return 0 if any(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
