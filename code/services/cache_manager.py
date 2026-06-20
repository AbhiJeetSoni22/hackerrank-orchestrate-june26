"""
Cache and checkpoint manager.

Stores one JSON file per successfully processed claim and maintains
a checkpoint file tracking completed claim identifiers.

On resume, completed claims are loaded from cache — no Gemini call made.

Pure I/O. No business logic. No Gemini calls.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from models import ClaimResult, GeminiPerception

logger = logging.getLogger(__name__)


# ── Claim identifier ──────────────────────────────────────────────────────────

def claim_id(user_id: str, image_paths_raw: str) -> str:
    """
    Stable, filesystem-safe identifier for a claim.

    Built from user_id + semicolon-joined image paths.
    Colons, slashes, and semicolons are replaced so the ID is usable
    as a filename stem without escaping.

    Args:
        user_id:         user_id field from the claim row.
        image_paths_raw: Semicolon-joined image_paths string.

    Returns:
        ASCII-safe string, e.g. "user_002__images-test-case_001-img_1".
    """
    safe_paths = (
        image_paths_raw
        .replace(";", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace(" ", "_")
    )
    return f"{user_id}__{safe_paths}"


# ── Cache manager ─────────────────────────────────────────────────────────────

class CacheManager:
    """
    Manages per-claim JSON cache files and a checkpoint file.

    Directory layout::

        <cache_dir>/
            checkpoint.json          # set of completed claim IDs
            claims/
                <claim_id>.json      # GeminiPerception + ClaimResult per claim

    All writes are atomic at the Python level (write then fsync not
    guaranteed, but acceptable for a hackathon resume-on-failure use case).
    """

    def __init__(self, cache_dir: Path, checkpoint_file: Path) -> None:
        self._cache_dir = cache_dir
        self._claims_dir = cache_dir / "claims"
        self._checkpoint_file = checkpoint_file
        self._completed: set[str] = set()

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._claims_dir.mkdir(parents=True, exist_ok=True)
        self._load_checkpoint()

    # ── Checkpoint ────────────────────────────────────────────────────────────

    def _load_checkpoint(self) -> None:
        """Load the set of completed claim IDs from the checkpoint file."""
        if self._checkpoint_file.exists():
            try:
                data = json.loads(self._checkpoint_file.read_text(encoding="utf-8"))
                self._completed = set(data.get("completed", []))
                logger.info(
                    "Checkpoint loaded: %d completed claim(s)", len(self._completed)
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read checkpoint file: %s. Starting fresh.", exc)
                self._completed = set()
        else:
            logger.info("No checkpoint file found. Starting fresh.")
            self._completed = set()

    def _save_checkpoint(self) -> None:
        """Persist the current set of completed claim IDs."""
        try:
            payload = {"completed": sorted(self._completed)}
            self._checkpoint_file.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("Failed to write checkpoint: %s", exc)

    def is_completed(self, cid: str) -> bool:
        """Return True if this claim ID is already in the checkpoint."""
        return cid in self._completed

    def mark_completed(self, cid: str) -> None:
        """Add a claim ID to the checkpoint and persist immediately."""
        self._completed.add(cid)
        self._save_checkpoint()

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    # ── Per-claim cache ───────────────────────────────────────────────────────

    def _cache_path(self, cid: str) -> Path:
        return self._claims_dir / f"{cid}.json"

    def save(
        self,
        cid: str,
        perception: GeminiPerception,
        result: ClaimResult,
    ) -> None:
        """
        Serialize and write GeminiPerception + ClaimResult to a JSON cache file.

        Also updates the checkpoint. Called immediately after a successful
        Gemini call + rule engine run.

        Args:
            cid:        Claim identifier from claim_id().
            perception: Validated GeminiPerception from Gemini.
            result:     Final ClaimResult from the rule engine.
        """
        payload: dict[str, Any] = {
            "claim_id": cid,
            "perception": perception.model_dump(),
            "result": result.model_dump(),
        }
        path = self._cache_path(cid)
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.debug("Cache written: %s", path.name)
        except OSError as exc:
            # Non-fatal: log and continue. Claim will be reprocessed on next run.
            logger.warning("Failed to write cache for %s: %s", cid, exc)
            return

        self.mark_completed(cid)

    def load(self, cid: str) -> tuple[GeminiPerception, ClaimResult] | None:
        """
        Load a cached GeminiPerception and ClaimResult for a completed claim.

        Args:
            cid: Claim identifier.

        Returns:
            (GeminiPerception, ClaimResult) tuple, or None if cache is missing
            or corrupt (caller should re-process the claim).
        """
        path = self._cache_path(cid)
        if not path.exists():
            logger.warning("Cache file missing for completed claim %s. Will reprocess.", cid)
            self._completed.discard(cid)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            perception = GeminiPerception.model_validate(data["perception"])
            result = ClaimResult.model_validate(data["result"])
            logger.debug("Cache hit: %s", cid)
            return perception, result
        except (json.JSONDecodeError, KeyError, Exception) as exc:
            logger.warning("Corrupt cache for %s (%s). Will reprocess.", cid, exc)
            self._completed.discard(cid)
            return None

    def summary(self) -> str:
        """Return a one-line human-readable cache summary."""
        files = list(self._claims_dir.glob("*.json"))
        return (
            f"cache_dir={self._cache_dir} "
            f"completed={len(self._completed)} "
            f"files={len(files)}"
        )