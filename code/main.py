"""
Main pipeline entry point.

Reads claims.csv, processes each claim through the full pipeline,
and writes output.csv.

Pipeline per claim (cache miss):
  Claim → image_loader → prompt_builder → gemini_client
        → risk_aggregator → rule_engine → ClaimResult → cache → output

Pipeline per claim (cache hit):
  Claim → cache_manager.load() → ClaimResult → output

Usage:
    python main.py

Requires GEMINI_API_KEY in environment or .env file.
Set ENABLE_CACHE=false to disable caching.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import (
    CACHE_DIR,
    CHECKPOINT_FILE,
    CLAIMS_CSV,
    DATASET_DIR,
    ENABLE_CACHE,
    EVIDENCE_REQUIREMENTS_CSV,
    OUTPUT_CSV,
    USER_HISTORY_CSV,
)
from models import ClaimResult
from services.cache_manager import CacheManager, claim_id
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

# ── Logging ───────────────────────────────────────────────────────────────────

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
    cache: CacheManager | None,
) -> ClaimResult:
    """
    Process one claim. Returns cached result if available, otherwise runs
    the full Gemini + rule engine pipeline and caches the result.

    Args:
        claim:             Claim object from csv_loader.
        history_lookup:    Dict of user_id → UserHistory.
        all_requirements:  Full list of EvidenceRequirement objects.
        system_prompt:     Static Gemini system prompt (built once).
        cache:             CacheManager instance, or None if caching disabled.

    Returns:
        ClaimResult ready for output.
    """
    image_paths_raw = ";".join(claim.image_paths)
    cid = claim_id(claim.user_id, image_paths_raw)

    # ── Cache hit ─────────────────────────────────────────────────────────────
    if cache is not None and cache.is_completed(cid):
        cached = cache.load(cid)
        if cached is not None:
            _perception, result = cached
            logger.info("  Cache hit — skipping Gemini")
            return result
        # Cache corrupt or missing — fall through to re-process.
        logger.info("  Cache miss (corrupt) — reprocessing")

    # ── Full pipeline ─────────────────────────────────────────────────────────
    user_history = get_user_history(history_lookup, claim.user_id)
    requirements = get_applicable_requirements(all_requirements, claim.claim_object)
    images = load_images(claim.image_paths, dataset_dir=DATASET_DIR)

    user_prompt = build_user_prompt(
        claim_conversation=claim.user_claim,
        claim_object=claim.claim_object,
        image_paths=claim.image_paths,
        user_history=user_history,
        evidence_requirements=requirements,
    )

    perception = call_gemini(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        images=images,
    )

    risk_flags = aggregate_risk_flags(perception, user_history)

    engine_result = decide(
        perception=perception,
        risk_flags=risk_flags,
        claim_object=claim.claim_object,
    )

    result = ClaimResult(
        user_id=claim.user_id,
        image_paths=image_paths_raw,
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

    # ── Write cache immediately after success ─────────────────────────────────
    if cache is not None:
        cache.save(cid, perception, result)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=== Evidence Review Pipeline Starting ===")
    logger.info("Cache enabled: %s", ENABLE_CACHE)

    # ── Cache setup ───────────────────────────────────────────────────────────
    cache: CacheManager | None = None
    if ENABLE_CACHE:
        cache = CacheManager(cache_dir=CACHE_DIR, checkpoint_file=CHECKPOINT_FILE)
        logger.info("Cache: %s", cache.summary())

    # ── Load datasets ─────────────────────────────────────────────────────────
    logger.info("Loading claims from %s", CLAIMS_CSV)
    claims = load_claims(CLAIMS_CSV)
    logger.info("Loaded %d claim(s)", len(claims))

    logger.info("Loading user history from %s", USER_HISTORY_CSV)
    history_lookup = load_user_history(USER_HISTORY_CSV)

    logger.info("Loading evidence requirements from %s", EVIDENCE_REQUIREMENTS_CSV)
    all_requirements = load_evidence_requirements(EVIDENCE_REQUIREMENTS_CSV)

    system_prompt = build_system_prompt()
    logger.info("System prompt built (%d chars)", len(system_prompt))

    # ── Process claims ────────────────────────────────────────────────────────
    results: list[ClaimResult] = []
    success_count = 0
    cache_hit_count = 0
    error_count = 0
    total = len(claims)

    for idx, claim in enumerate(claims, start=1):
        image_paths_raw = ";".join(claim.image_paths)
        cid = claim_id(claim.user_id, image_paths_raw)
        is_cached = cache is not None and cache.is_completed(cid)

        logger.info(
            "[%d/%d] user_id=%s object=%s images=%d%s",
            idx,
            total,
            claim.user_id,
            claim.claim_object.value,
            len(claim.image_paths),
            " [cached]" if is_cached else "",
        )

        try:
            result = process_claim(
                claim=claim,
                history_lookup=history_lookup,
                all_requirements=all_requirements,
                system_prompt=system_prompt,
                cache=cache,
            )
            results.append(result)
            success_count += 1
            if is_cached:
                cache_hit_count += 1

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

    # ── Write output ──────────────────────────────────────────────────────────
    logger.info("Writing %d result(s) to %s", len(results), OUTPUT_CSV)
    write_output(results, path=OUTPUT_CSV)

    # ── Summary ───────────────────────────────────────────────────────────────
    gemini_calls = success_count - cache_hit_count
    logger.info("=== Pipeline Complete ===")
    logger.info("Total claims    : %d", total)
    logger.info("Succeeded       : %d", success_count)
    logger.info("  Cache hits    : %d  (no Gemini call)", cache_hit_count)
    logger.info("  Gemini calls  : %d", gemini_calls)
    logger.info("Failed          : %d", error_count)
    logger.info("Output file     : %s", OUTPUT_CSV)

    if ENABLE_CACHE and cache:
        logger.info("Cache summary   : %s", cache.summary())

    if error_count > 0:
        logger.warning(
            "%d claim(s) failed. Re-run to resume — completed claims will be loaded from cache.",
            error_count,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()