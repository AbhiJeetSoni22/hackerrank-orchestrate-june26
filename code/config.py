"""
Central configuration for the evidence review system.

All paths, model identifiers, and tuneable constants live here.
Read secrets from environment variables only — never hardcode.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Repository root ───────────────────────────────────────────────────────────

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

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

GEMINI_MAX_OUTPUT_TOKENS: int = 4096

# ── Rate limiting & retry ─────────────────────────────────────────────────────

INTER_CALL_SLEEP_SECONDS: float = 1.0

GEMINI_MAX_RETRIES: int = 3

GEMINI_RETRY_BASE_BACKOFF: float = 2.0

# ── Image encoding ────────────────────────────────────────────────────────────

IMAGE_MIME_TYPE: str = "image/jpeg"

# ── Output CSV column order ───────────────────────────────────────────────────

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

# ── Cache & checkpoint ────────────────────────────────────────────────────────

# Set to False to disable caching and always call Gemini.
ENABLE_CACHE: bool = os.environ.get("ENABLE_CACHE", "true").lower() != "false"

# Directory where per-claim JSON cache files are stored.
# Resolved relative to repo root; override via CACHE_DIR env var.
CACHE_DIR: Path = Path(
    os.environ.get("CACHE_DIR", str(REPO_ROOT / ".cache"))
)

# Path to the checkpoint JSON file tracking completed claim IDs.
# Defaults to <CACHE_DIR>/checkpoint.json; override via CHECKPOINT_FILE env var.
CHECKPOINT_FILE: Path = Path(
    os.environ.get("CHECKPOINT_FILE", str(CACHE_DIR / "checkpoint.json"))
)