"""
Output writer.

Writes a list of ClaimResult objects to output.csv in the exact
column order defined by OUTPUT_COLUMNS in config.py.

Pure I/O. No business logic.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from config import OUTPUT_COLUMNS, OUTPUT_CSV
from models import ClaimResult

logger = logging.getLogger(__name__)


def _bool_str(value: bool) -> str:
    """Convert Python bool to lowercase string required by output schema."""
    return "true" if value else "false"


def _result_to_row(result: ClaimResult) -> dict[str, str]:
    """
    Serialise a ClaimResult to a flat string dict matching OUTPUT_COLUMNS.

    Booleans become lowercase "true"/"false".
    All other fields are cast to str (already strings in ClaimResult).
    """
    return {
        "user_id": result.user_id,
        "image_paths": result.image_paths,
        "user_claim": result.user_claim,
        "claim_object": result.claim_object,
        "evidence_standard_met": _bool_str(result.evidence_standard_met),
        "evidence_standard_met_reason": result.evidence_standard_met_reason,
        "risk_flags": result.risk_flags,
        "issue_type": result.issue_type,
        "object_part": result.object_part,
        "claim_status": result.claim_status,
        "claim_status_justification": result.claim_status_justification,
        "supporting_image_ids": result.supporting_image_ids,
        "valid_image": _bool_str(result.valid_image),
        "severity": result.severity,
    }


def write_output(
    results: list[ClaimResult],
    path: Path = OUTPUT_CSV,
) -> None:
    """
    Write ClaimResult list to a CSV file.

    Columns are written in the order defined by OUTPUT_COLUMNS.
    All fields are quoted (csv.QUOTE_ALL) for maximum compatibility.
    Creates parent directories if missing.
    Writes an empty file with headers if results is empty.

    Args:
        results: List of ClaimResult objects to write.
        path:    Destination path. Defaults to OUTPUT_CSV from config.

    Raises:
        OSError: If the file cannot be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=OUTPUT_COLUMNS,
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
        )
        writer.writeheader()

        for result in results:
            writer.writerow(_result_to_row(result))

    logger.info("Wrote %d row(s) to %s", len(results), path)