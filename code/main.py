"""
Main pipeline entry point.

Reads claims.csv, processes each claim through the full pipeline,
and writes output.csv.

Pipeline per claim:
  Claim → image_loader → prompt_builder → gemini_client
        → risk_aggregator → rule_engine → ClaimResult

Usage:
    python main.py

Requires GEMINI_API_KEY in environment or .env file.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Load .env before any config import so env vars are available.
from dotenv import load_dotenv
load_dotenv()

from config import (
    CLAIMS_CSV,
    DATASET_DIR,
    EVIDENCE_REQUIREMENTS_CSV,
    OUTPUT_CSV,
    USER_HISTORY_CSV,
)
from models import ClaimResult
from services.csv_loader import (
    get_applicable_requirements,
    get_user_history,
    load_claims,
    load_evidence_requirements,
    load_user_history,
)
from services.gemini_client import call_gemini
from services.image_loader import load_images
from services.output_writer import write_output
from services.prompt_builder import build_system_prompt, build_user_prompt
from services.risk_aggregator import aggregate_risk_flags
from services.rule_engine import decide

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("main")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def process_claim(
    claim,
    history_lookup: dict,
    all_requirements: list,
    system_prompt: str,
) -> ClaimResult:
    """
    Run one claim through the full pipeline.

    Args:
        claim:             Claim object from csv_loader.
        history_lookup:    Dict of user_id → UserHistory.
        all_requirements:  Full list of EvidenceRequirement objects.
        system_prompt:     Static Gemini system prompt (built once).

    Returns:
        ClaimResult ready for output.

    Raises:
        Any exception from downstream services (caught by caller).
    """
    user_history = get_user_history(history_lookup, claim.user_id)
    requirements = get_applicable_requirements(all_requirements, claim.claim_object)

    # Load and encode images.
    images = load_images(claim.image_paths, dataset_dir=DATASET_DIR)

    # Build per-claim user prompt.
    user_prompt = build_user_prompt(
        claim_conversation=claim.user_claim,
        claim_object=claim.claim_object,
        image_paths=claim.image_paths,
        user_history=user_history,
        evidence_requirements=requirements,
    )

    # Single Gemini call — perception only.
    perception = call_gemini(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        images=images,
    )

    # Aggregate risk flags (perception + history).
    risk_flags = aggregate_risk_flags(perception, user_history)

    # Deterministic business decisions.
    engine_result = decide(
        perception=perception,
        risk_flags=risk_flags,
        claim_object=claim.claim_object,
    )

    # Assemble final output row.
    return ClaimResult(
        user_id=claim.user_id,
        image_paths=";".join(claim.image_paths),
        user_claim=claim.user_claim,
        claim_object=claim.claim_object.value,
        evidence_standard_met=engine_result.evidence_standard_met,
        evidence_standard_met_reason=engine_result.evidence_standard_met_reason,
        risk_flags=risk_flags,
        issue_type=engine_result.issue_type,
        object_part=engine_result.object_part,
        claim_status=engine_result.claim_status.value,
        claim_status_justification=engine_result.claim_status_justification,
        supporting_image_ids=engine_result.supporting_image_ids,
        valid_image=engine_result.valid_image,
        severity=engine_result.severity.value,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=== Evidence Review Pipeline Starting ===")

    # ── Load datasets ─────────────────────────────────────────────────────────
    logger.info("Loading claims from %s", CLAIMS_CSV)
    claims = load_claims(CLAIMS_CSV)
    logger.info("Loaded %d claim(s)", len(claims))

    logger.info("Loading user history from %s", USER_HISTORY_CSV)
    history_lookup = load_user_history(USER_HISTORY_CSV)
    logger.info("Loaded history for %d user(s)", len(history_lookup))

    logger.info("Loading evidence requirements from %s", EVIDENCE_REQUIREMENTS_CSV)
    all_requirements = load_evidence_requirements(EVIDENCE_REQUIREMENTS_CSV)
    logger.info("Loaded %d requirement(s)", len(all_requirements))

    # ── Build system prompt once ──────────────────────────────────────────────
    system_prompt = build_system_prompt()
    logger.info("System prompt built (%d chars)", len(system_prompt))

    # ── Process claims sequentially ───────────────────────────────────────────
    results: list[ClaimResult] = []
    success_count = 0
    error_count = 0
    total = len(claims)

    for idx, claim in enumerate(claims, start=1):
        logger.info(
            "[%d/%d] Processing claim user_id=%s object=%s images=%d",
            idx,
            total,
            claim.user_id,
            claim.claim_object.value,
            len(claim.image_paths),
        )

        try:
            result = process_claim(
                claim=claim,
                history_lookup=history_lookup,
                all_requirements=all_requirements,
                system_prompt=system_prompt,
            )
            results.append(result)
            success_count += 1
            logger.info(
                "[%d/%d] Done — status=%s severity=%s flags=%s",
                idx,
                total,
                result.claim_status,
                result.severity,
                result.risk_flags,
            )

        except Exception as exc:  # noqa: BLE001
            error_count += 1
            logger.error(
                "[%d/%d] FAILED user_id=%s: %s",
                idx,
                total,
                claim.user_id,
                exc,
                exc_info=True,
            )
            # Continue processing remaining claims.

    # ── Write output ──────────────────────────────────────────────────────────
    logger.info("Writing %d result(s) to %s", len(results), OUTPUT_CSV)
    write_output(results, path=OUTPUT_CSV)

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=== Pipeline Complete ===")
    logger.info("Total claims : %d", total)
    logger.info("Succeeded    : %d", success_count)
    logger.info("Failed       : %d", error_count)
    logger.info("Output file  : %s", OUTPUT_CSV)

    if error_count > 0:
        logger.warning(
            "%d claim(s) failed and were excluded from output.csv. "
            "Review logs above for details.",
            error_count,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()