from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from invoice_extractor.constants import OUTPUT_CSV, OUTPUT_DIR, OUTPUT_XLSX, STATIC_DIR
from invoice_extractor.models import CSV_COLUMNS
from invoice_extractor.ocr import check_ocr_engine, tesseract_available
from invoice_extractor.pipeline import InvoicePipeline

app = FastAPI(title="Invoice Extractor")
_last_results: list[dict] = []
_last_excel_path = OUTPUT_XLSX


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ProcessRequest(BaseModel):
    ocr_engine: str = "easyocr"
    use_llm: bool = True


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/")
async def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(404, "static/index.html missing")
    return FileResponse(index_file)


@app.get("/health")
def health():
    return {"status": "ok", "tesseract_installed": tesseract_available()}


@app.post("/api/process")
def process(req: ProcessRequest):
    global _last_results, _last_excel_path

    err = check_ocr_engine(req.ocr_engine)
    if err:
        raise HTTPException(400, err)

    try:
        pipeline = InvoicePipeline(ocr_engine=req.ocr_engine, use_llm=req.use_llm)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    results, warning = pipeline.run_batch(write_xlsx=True)
    ok = [r for r in results if r.success]
    if not ok:
        detail = warning or "No images processed. Add files to data/images."
        raise HTTPException(400, detail)

    _last_results = [r.fields.to_csv_row() for r in ok]
    if OUTPUT_XLSX.exists():
        _last_excel_path = OUTPUT_XLSX
    elif (OUTPUT_DIR / "output_latest.xlsx").exists():
        _last_excel_path = OUTPUT_DIR / "output_latest.xlsx"

    return {
        "count": len(ok),
        "failed": len(results) - len(ok),
        "ocr_engine": req.ocr_engine,
        "rows": _last_results,
        "csv": str(OUTPUT_CSV),
        "excel": str(_last_excel_path),
        "warning": warning,
    }


@app.get("/api/results")
def results():
    return {"columns": CSV_COLUMNS, "rows": _last_results}


@app.get("/api/download/csv")
def download_csv():
    if not OUTPUT_CSV.exists():
        raise HTTPException(404, "Run process first")
    return FileResponse(OUTPUT_CSV, filename="output.csv")


@app.get("/api/download/excel")
def download_excel():
    path = _last_excel_path if _last_excel_path.exists() else OUTPUT_XLSX
    if not path.exists():
        alt = OUTPUT_DIR / "output_latest.xlsx"
        if alt.exists():
            path = alt
        else:
            raise HTTPException(404, "Run process first")
    return FileResponse(path, filename=path.name)


@app.get("/api/ocr-status")
def ocr_status():
    return {"easyocr": True, "tesseract": tesseract_available()}
