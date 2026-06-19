"""
CSV loading service.

Loads all three dataset CSVs and returns typed domain objects.
No business logic; pure I/O and parsing.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from models import (
    Claim,
    ClaimObject,
    EvidenceRequirement,
    UserHistory,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file and return rows as a list of dicts."""
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _parse_semicolon_list(value: str) -> list[str]:
    """Split a semicolon-separated string into a stripped list, ignoring empties."""
    return [item.strip() for item in value.split(";") if item.strip()]


def _parse_int(value: str, default: int = 0) -> int:
    """Parse an integer field, falling back to default on blank/invalid input."""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return default


# ── Public loaders ────────────────────────────────────────────────────────────

def load_claims(path: Path) -> list[Claim]:
    """
    Load claims from a CSV file (claims.csv or sample_claims.csv).

    Parses `image_paths` from semicolon-separated strings into a list.
    Extra columns present in sample_claims.csv (ground-truth fields) are
    silently ignored — only the four input fields are consumed.

    Args:
        path: Absolute path to the claims CSV file.

    Returns:
        Ordered list of Claim objects, one per CSV row.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If a required field is missing or has an invalid value.
    """
    rows = _read_csv(path)
    claims: list[Claim] = []

    for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        try:
            claim = Claim(
                user_id=row["user_id"].strip(),
                image_paths=_parse_semicolon_list(row["image_paths"]),
                user_claim=row["user_claim"].strip(),
                claim_object=ClaimObject(row["claim_object"].strip().lower()),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Row {i} in {path.name} is invalid: {exc}") from exc

        claims.append(claim)

    return claims


def load_user_history(path: Path) -> dict[str, UserHistory]:
    """
    Load user history from user_history.csv into a lookup dict keyed by user_id.

    Args:
        path: Absolute path to user_history.csv.

    Returns:
        Dict mapping user_id → UserHistory.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    rows = _read_csv(path)
    history: dict[str, UserHistory] = {}

    for row in rows:
        user_id = row["user_id"].strip()
        history[user_id] = UserHistory(
            user_id=user_id,
            past_claim_count=_parse_int(row.get("past_claim_count", "")),
            accept_claim=_parse_int(row.get("accept_claim", "")),
            manual_review_claim=_parse_int(row.get("manual_review_claim", "")),
            rejected_claim=_parse_int(row.get("rejected_claim", "")),
            last_90_days_claim_count=_parse_int(row.get("last_90_days_claim_count", "")),
            history_flags=_parse_semicolon_list(row.get("history_flags", "")),
            history_summary=row.get("history_summary", "").strip(),
        )

    return history


def load_evidence_requirements(path: Path) -> list[EvidenceRequirement]:
    """
    Load evidence requirements from evidence_requirements.csv.

    Args:
        path: Absolute path to evidence_requirements.csv.

    Returns:
        List of EvidenceRequirement objects.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    rows = _read_csv(path)
    requirements: list[EvidenceRequirement] = []

    for row in rows:
        requirements.append(
            EvidenceRequirement(
                requirement_id=row["requirement_id"].strip(),
                claim_object=row["claim_object"].strip().lower(),
                applies_to=row["applies_to"].strip(),
                minimum_image_evidence=row["minimum_image_evidence"].strip(),
            )
        )

    return requirements


def get_applicable_requirements(
    requirements: list[EvidenceRequirement],
    claim_object: ClaimObject,
) -> list[EvidenceRequirement]:
    """
    Filter evidence requirements to those applicable to a specific claim object.

    Returns requirements where claim_object matches or is "all".

    Args:
        requirements: Full list loaded from evidence_requirements.csv.
        claim_object: The object type of the current claim.

    Returns:
        Filtered list of EvidenceRequirement objects.
    """
    target = claim_object.value
    return [
        req for req in requirements
        if req.claim_object in (target, "all")
    ]


def get_user_history(
    history: dict[str, UserHistory],
    user_id: str,
) -> Optional[UserHistory]:
    """
    Retrieve history for a user, returning None if user has no history record.

    Args:
        history: Dict returned by load_user_history.
        user_id: User to look up.

    Returns:
        UserHistory or None.
    """
    return history.get(user_id)