"""
Central configuration for the evidence review system.

All paths, model identifiers, and tuneable constants live here.
Read secrets from environment variables only — never hardcode.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Repository root ───────────────────────────────────────────────────────────

# Resolved to the repo root regardless of where the script is invoked from.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

# ── Dataset paths ─────────────────────────────────────────────────────────────

DATASET_DIR: Path = REPO_ROOT / "dataset"

CLAIMS_CSV: Path = DATASET_DIR / "claims.csv"
SAMPLE_CLAIMS_CSV: Path = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_CSV: Path = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_CSV: Path = DATASET_DIR / "evidence_requirements.csv"

IMAGES_DIR: Path = DATASET_DIR / "images"
SAMPLE_IMAGES_DIR: Path = IMAGES_DIR / "sample"
TEST_IMAGES_DIR: Path = IMAGES_DIR / "test"

# ── Output ────────────────────────────────────────────────────────────────────

OUTPUT_CSV: Path = REPO_ROOT / "output.csv"

# ── Gemini ────────────────────────────────────────────────────────────────────

GEMINI_MODEL: str = "gemini-2.5-flash"

# Read API key from environment; raise early if missing.
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# Maximum tokens Gemini may return per call.
GEMINI_MAX_OUTPUT_TOKENS: int = 2048

# ── Rate limiting & retry ─────────────────────────────────────────────────────

# Seconds to sleep between consecutive Gemini calls (basic throttle).
INTER_CALL_SLEEP_SECONDS: float = 1.0

# Number of retry attempts on transient errors (429, 5xx).
GEMINI_MAX_RETRIES: int = 3

# Base backoff in seconds; doubles on each retry.
GEMINI_RETRY_BASE_BACKOFF: float = 2.0

# ── Image encoding ────────────────────────────────────────────────────────────

# MIME type used when sending images inline to Gemini.
IMAGE_MIME_TYPE: str = "image/jpeg"

# ── Output CSV column order ───────────────────────────────────────────────────
# Must match the required output schema exactly.

OUTPUT_COLUMNS: list[str] = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]