"""Project settings — edit image batch, OCR engine, paths here."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Image batch (batch1-0331 … batch1-0381)
IMAGE_FROM_ID = 331
IMAGE_TO_ID = 381
IMAGE_LIMIT = 5  # 0 = all in range (CLI default; UI can override)
IMAGE_MAX_RECORDS = 50  # max selectable in UI (batch1-0331 … batch1-0380)
IMAGE_PATTERN = "batch1-*.jpg"

INPUT_DIR = ROOT / "data" / "images"
OUTPUT_DIR = ROOT / "output"
OUTPUT_CSV = OUTPUT_DIR / "output.csv"
OUTPUT_XLSX = OUTPUT_DIR / "output.xlsx"
TEMPLATE_PATH = ROOT / "config" / "template.yaml"
STATIC_DIR = ROOT / "static"

# OCR: "easyocr" (accurate, slower) | "tesseract" (faster, needs Tesseract installed)
OCR_ENGINE_DEFAULT = "easyocr"
OCR_LANGUAGES = ["en"]
OCR_GPU = False
OCR_MAX_WIDTH = 1400

# LLM — only called when parser leaves fields empty (needs OPENAI_API_KEY)
LLM_ENABLED = True
LLM_MODEL = "gpt-4o-mini"

API_HOST = "127.0.0.1"
API_PORT = 8000

# Windows: set path if Tesseract not on PATH (leave "" to auto-detect)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
