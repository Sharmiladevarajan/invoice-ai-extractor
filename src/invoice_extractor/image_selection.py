from __future__ import annotations

import re
from pathlib import Path

BATCH_NUMBER_PATTERN = re.compile(r"batch1-(\d+)", re.IGNORECASE)


def extract_batch_number(path: Path) -> int | None:
    match = BATCH_NUMBER_PATTERN.search(path.stem)
    return int(match.group(1)) if match else None


def select_images(
    images: list[Path],
    *,
    start_id: int | None = None,
    end_id: int | None = None,
    limit: int = 5,
) -> list[Path]:
    """Filter by batch1-XXXX numeric range, then apply limit (0 = no limit)."""
    filtered = images

    if start_id is not None:
        filtered = [
            path
            for path in filtered
            if (num := extract_batch_number(path)) is not None and num >= start_id
        ]

    if end_id is not None:
        filtered = [
            path
            for path in filtered
            if (num := extract_batch_number(path)) is not None and num <= end_id
        ]

    if limit > 0:
        filtered = filtered[:limit]

    return filtered
