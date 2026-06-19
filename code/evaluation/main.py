"""
Evaluation entry point.

Runs the full pipeline on sample_claims.csv (which has ground-truth labels),
compares Strategy A vs Strategy B, prints metrics, and saves results.

Strategy A: Production prompt (build_system_prompt as-is).
Strategy B: Refined prompt with stricter output constraints and
            explicit few-shot guidance on edge cases.

Usage:
    python code/evaluation/main.py
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Allow imports from code/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DATASET_DIR,
    EVIDENCE_REQUIREMENTS_CSV,
    SAMPLE_CLAIMS_CSV,
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
from evaluation.metrics import (
    EvaluationSummary,
    compare_summaries,
    generate_summary,
    print_summary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("evaluation")

# ── Ground-truth columns present in sample_claims.csv ────────────────────────
_GT_FIELDS = [
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

# ── Strategy B: refined system prompt ────────────────────────────────────────

def build_strategy_b_prompt() -> str:
    """
    Strategy B: production prompt + stricter instructions + edge-case guidance.

    Adds:
    - Explicit instruction to prefer "not_enough_information" when part
      visibility is ambiguous rather than guessing.
    - Reminder that wrong_object overrides all other signals.
    - Stricter null handling: visible_issue must be null, not omitted.
    """
    base = build_system_prompt()
    addendum = """

ADDITIONAL CONSTRAINTS (Strategy B):
- If you cannot clearly confirm the claimed part is visible, set
  shows_claimed_part=false. Do not guess from partial context.
- If the image shows a completely different object (e.g. a shoe instead of a
  car), set wrong_object_detected=true and shows_claimed_object=false.
  This takes priority over all other assessments for that image.
- visible_issue must always be present: use null if nothing is visible,
  never omit the field.
- supporting_image_ids must be an empty list [], not omitted, when no image
  clearly supports the claim.
- When the claim conversation contains multiple parts mentioned, extract only
  the FINAL explicitly confirmed claim, not intermediate mentions.
"""
    return base + addendum


# ── CSV ground-truth loader ───────────────────────────────────────────────────

def load_ground_truth(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """
    Load ground-truth labels from sample_claims.csv.

    Returns a dict keyed by (user_id, image_paths_raw) → field dict.
    """
    gt: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row["user_id"].strip(), row["image_paths"].strip())
            gt[key] = {f: row.get(f, "").strip() for f in _GT_FIELDS}
    return gt


# ── Single claim processor ────────────────────────────────────────────────────

def run_claim(claim, history_lookup, all_requirements, system_prompt) -> ClaimResult:
    """Process one claim through the full pipeline."""
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
    perception = call_gemini(system_prompt, user_prompt, images)
    risk_flags = aggregate_risk_flags(perception, user_history)
    engine_result = decide(perception, risk_flags, claim.claim_object)

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


# ── Strategy runner ───────────────────────────────────────────────────────────

def run_strategy(
    strategy_name: str,
    system_prompt: str,
    claims: list,
    history_lookup: dict,
    all_requirements: list,
    ground_truth: dict,
) -> tuple[EvaluationSummary, list[ClaimResult]]:
    """
    Run all sample claims through the pipeline with a given system prompt.

    Returns evaluation summary and list of ClaimResult objects.
    """
    logger.info("Running %s on %d claims ...", strategy_name, len(claims))
    records = []
    results = []
    errors = 0

    for idx, claim in enumerate(claims, start=1):
        logger.info("[%d/%d] %s user_id=%s", idx, len(claims), strategy_name, claim.user_id)
        try:
            result = run_claim(claim, history_lookup, all_requirements, system_prompt)
            results.append(result)

            key = (claim.user_id, ";".join(claim.image_paths))
            gt = ground_truth.get(key, {})

            predicted = {
                "evidence_standard_met": str(result.evidence_standard_met).lower(),
                "risk_flags": result.risk_flags,
                "issue_type": result.issue_type,
                "object_part": result.object_part,
                "claim_status": result.claim_status,
                "valid_image": str(result.valid_image).lower(),
                "severity": result.severity,
            }
            records.append({
                "user_id": claim.user_id,
                "predicted": predicted,
                "expected": gt,
            })

        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.error("FAILED %s user_id=%s: %s", strategy_name, claim.user_id, exc)

    logger.info("%s complete. errors=%d", strategy_name, errors)
    summary = generate_summary(records, strategy_name)
    return summary, results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=== Evaluation Pipeline Starting ===")

    claims = load_claims(SAMPLE_CLAIMS_CSV)
    history_lookup = load_user_history(USER_HISTORY_CSV)
    all_requirements = load_evidence_requirements(EVIDENCE_REQUIREMENTS_CSV)
    ground_truth = load_ground_truth(SAMPLE_CLAIMS_CSV)

    logger.info("Loaded %d sample claims with ground truth", len(claims))

    prompt_a = build_system_prompt()
    prompt_b = build_strategy_b_prompt()

    t0 = time.time()
    summary_a, results_a = run_strategy(
        "Strategy A", prompt_a, claims, history_lookup, all_requirements, ground_truth
    )
    time_a = time.time() - t0

    t0 = time.time()
    summary_b, results_b = run_strategy(
        "Strategy B", prompt_b, claims, history_lookup, all_requirements, ground_truth
    )
    time_b = time.time() - t0

    # Print results.
    print_summary(summary_a)
    print_summary(summary_b)
    compare_summaries(summary_a, summary_b)

    logger.info("Strategy A runtime: %.1fs", time_a)
    logger.info("Strategy B runtime: %.1fs", time_b)

    # Save winning strategy results for inspection.
    winner = summary_a if summary_a.mean_accuracy >= summary_b.mean_accuracy else summary_b
    winning_results = results_a if winner.strategy_name == "Strategy A" else results_b
    out_path = Path(__file__).resolve().parent / "sample_predictions.csv"
    write_output(winning_results, path=out_path)
    logger.info("Winning strategy predictions saved to %s", out_path)
    logger.info("=== Evaluation Complete ===")


if __name__ == "__main__":
    main()