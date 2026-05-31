"""CLI entry point for invoice extraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from invoice_extractor.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
