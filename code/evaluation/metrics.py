"""
Evaluation metrics for the evidence review system.

Compares predicted ClaimResult fields against ground-truth
labels from sample_claims.csv.

Pure Python. No API calls. No side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class FieldMetric:
    """Accuracy result for a single output field."""
    field_name: str
    correct: int
    total: int
    accuracy: float
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationSummary:
    """Full evaluation summary across all fields and all records."""
    strategy_name: str
    total_records: int
    field_metrics: list[FieldMetric]
    mean_accuracy: float
    mean_jaccard: float
    risk_flags_jaccard: float


# ── Core metrics ──────────────────────────────────────────────────────────────

def accuracy(predicted: str, expected: str) -> bool:
    """
    Exact-match accuracy for a single field value.

    Case-insensitive, whitespace-stripped comparison.

    Args:
        predicted: Value produced by the system.
        expected:  Ground-truth value from sample_claims.csv.

    Returns:
        True if values match.
    """
    return predicted.strip().lower() == expected.strip().lower()


def jaccard_similarity(predicted_flags: str, expected_flags: str) -> float:
    """
    Jaccard similarity between two semicolon-separated flag strings.

    Handles "none" as an empty set.
    Returns 1.0 if both sides are empty.

    Args:
        predicted_flags: Semicolon-joined flags from system output.
        expected_flags:  Semicolon-joined flags from ground truth.

    Returns:
        Jaccard score in [0.0, 1.0].
    """
    def _parse(s: str) -> set[str]:
        stripped = s.strip().lower()
        if not stripped or stripped == "none":
            return set()
        return {f.strip() for f in stripped.split(";") if f.strip()}

    pred = _parse(predicted_flags)
    exp = _parse(expected_flags)

    if not pred and not exp:
        return 1.0

    intersection = pred & exp
    union = pred | exp
    return len(intersection) / len(union) if union else 1.0


def field_accuracy(
    records: list[dict[str, str]],
    field_name: str,
    predicted_key: str = "predicted",
    expected_key: str = "expected",
) -> FieldMetric:
    """
    Compute exact-match accuracy for one field across all records.

    Each record dict must have keys:
        {predicted_key}_{field_name} and {expected_key}_{field_name}

    Alternatively, pass records as dicts with "predicted" and "expected"
    sub-dicts — see generate_summary for the calling convention.

    Args:
        records:       List of comparison dicts produced by compare_records.
        field_name:    Output column name to evaluate.
        predicted_key: Key prefix for predicted value.
        expected_key:  Key prefix for expected value.

    Returns:
        FieldMetric with correct count, total, and accuracy.
    """
    correct = 0
    total = 0
    errors: list[dict[str, Any]] = []

    for rec in records:
        pred_val = rec.get(predicted_key, {}).get(field_name, "")
        exp_val = rec.get(expected_key, {}).get(field_name, "")
        total += 1
        if accuracy(pred_val, exp_val):
            correct += 1
        else:
            errors.append({
                "user_id": rec.get("user_id", "unknown"),
                "predicted": pred_val,
                "expected": exp_val,
            })

    acc = correct / total if total > 0 else 0.0
    return FieldMetric(
        field_name=field_name,
        correct=correct,
        total=total,
        accuracy=acc,
        errors=errors,
    )


# ── Summary builder ───────────────────────────────────────────────────────────

# Fields evaluated with exact-match accuracy.
_ACCURACY_FIELDS: list[str] = [
    "claim_status",
    "evidence_standard_met",
    "valid_image",
    "severity",
    "issue_type",
    "object_part",
]


def generate_summary(
    records: list[dict[str, Any]],
    strategy_name: str,
) -> EvaluationSummary:
    """
    Generate a full evaluation summary for one strategy.

    Args:
        records:       List of dicts, each with keys:
                         "user_id", "predicted" (dict), "expected" (dict)
        strategy_name: Label for this strategy (e.g. "Strategy A").

    Returns:
        EvaluationSummary with per-field metrics and aggregate scores.
    """
    field_metrics: list[FieldMetric] = []

    for fname in _ACCURACY_FIELDS:
        metric = field_accuracy(records, fname)
        field_metrics.append(metric)

    # Jaccard for risk_flags across all records.
    jaccard_scores: list[float] = []
    for rec in records:
        pred_flags = rec.get("predicted", {}).get("risk_flags", "none")
        exp_flags = rec.get("expected", {}).get("risk_flags", "none")
        jaccard_scores.append(jaccard_similarity(pred_flags, exp_flags))

    risk_jaccard = sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 0.0

    accuracy_values = [m.accuracy for m in field_metrics]
    mean_acc = sum(accuracy_values) / len(accuracy_values) if accuracy_values else 0.0
    mean_jac = (sum(accuracy_values) + risk_jaccard) / (len(accuracy_values) + 1) if accuracy_values else 0.0

    return EvaluationSummary(
        strategy_name=strategy_name,
        total_records=len(records),
        field_metrics=field_metrics,
        mean_accuracy=mean_acc,
        mean_jaccard=risk_jaccard,
        risk_flags_jaccard=risk_jaccard,
    )


def print_summary(summary: EvaluationSummary) -> None:
    """Print a formatted evaluation summary table to stdout."""
    print(f"\n{'='*60}")
    print(f"  {summary.strategy_name}  ({summary.total_records} records)")
    print(f"{'='*60}")
    print(f"  {'Field':<30} {'Correct':>7} {'Total':>7} {'Accuracy':>9}")
    print(f"  {'-'*57}")
    for m in summary.field_metrics:
        print(
            f"  {m.field_name:<30} {m.correct:>7} {m.total:>7} {m.accuracy:>8.1%}"
        )
    print(f"  {'-'*57}")
    print(f"  {'risk_flags (Jaccard)':<30} {'':>7} {'':>7} {summary.risk_flags_jaccard:>8.1%}")
    print(f"  {'Mean accuracy (excl. Jaccard)':<30} {'':>7} {'':>7} {summary.mean_accuracy:>8.1%}")
    print(f"{'='*60}\n")


def compare_summaries(a: EvaluationSummary, b: EvaluationSummary) -> None:
    """Print a side-by-side comparison table for two strategies."""
    print(f"\n{'='*72}")
    print(f"  STRATEGY COMPARISON")
    print(f"{'='*72}")
    print(f"  {'Field':<30} {a.strategy_name:>18} {b.strategy_name:>18}")
    print(f"  {'-'*69}")

    field_map_a = {m.field_name: m for m in a.field_metrics}
    field_map_b = {m.field_name: m for m in b.field_metrics}

    all_fields = _ACCURACY_FIELDS + ["risk_flags"]
    for fname in all_fields:
        if fname == "risk_flags":
            acc_a = a.risk_flags_jaccard
            acc_b = b.risk_flags_jaccard
            label = "risk_flags (Jaccard)"
        else:
            acc_a = field_map_a.get(fname, FieldMetric(fname, 0, 0, 0.0)).accuracy
            acc_b = field_map_b.get(fname, FieldMetric(fname, 0, 0, 0.0)).accuracy
            label = fname

        winner = "◀" if acc_a > acc_b else ("▶" if acc_b > acc_a else "=")
        print(f"  {label:<30} {acc_a:>17.1%} {acc_b:>17.1%}  {winner}")

    print(f"  {'-'*69}")
    print(
        f"  {'Mean accuracy':<30} {a.mean_accuracy:>17.1%} {b.mean_accuracy:>17.1%}"
    )
    print(f"{'='*72}\n")

    if a.mean_accuracy >= b.mean_accuracy:
        print(f"  Winner: {a.strategy_name} (mean accuracy {a.mean_accuracy:.1%})")
    else:
        print(f"  Winner: {b.strategy_name} (mean accuracy {b.mean_accuracy:.1%})")
    print()