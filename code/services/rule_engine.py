"""
Rule engine — all business decisions.

Consumes GeminiPerception (perception) + aggregated risk flags + claim context
and produces the business-decision fields for ClaimResult.

Deterministic. No API calls. No randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from models import (
    ClaimObject,
    ClaimStatus,
    GeminiPerception,
    IssueType,
    RiskFlag,
    Severity,
)


# ── Output container ──────────────────────────────────────────────────────────

@dataclass
class RuleEngineResult:
    """
    Business-decision fields produced by the rule engine.

    Consumed by the pipeline to build the final ClaimResult.
    """
    valid_image: bool
    evidence_standard_met: bool
    evidence_standard_met_reason: str
    claim_status: ClaimStatus
    claim_status_justification: str
    issue_type: str
    object_part: str
    supporting_image_ids: str   # semicolon-joined or "none"
    severity: Severity


# ── Severity mapping ──────────────────────────────────────────────────────────

_HIGH_SEVERITY_ISSUES: frozenset[str] = frozenset({
    IssueType.CRACK.value,
    IssueType.GLASS_SHATTER.value,
    IssueType.BROKEN_PART.value,
    IssueType.MISSING_PART.value,
})

_MEDIUM_SEVERITY_ISSUES: frozenset[str] = frozenset({
    IssueType.DENT.value,
    IssueType.STAIN.value,
    IssueType.WATER_DAMAGE.value,
    IssueType.TORN_PACKAGING.value,
    IssueType.CRUSHED_PACKAGING.value,
})

_LOW_SEVERITY_ISSUES: frozenset[str] = frozenset({
    IssueType.SCRATCH.value,
})


def _resolve_severity(
    claim_status: ClaimStatus,
    visible_issue: str | None,
) -> Severity:
    """
    Map claim_status + visible issue type to a Severity value.

    Rules (in priority order):
    - not_enough_information → unknown
    - contradicted with no visible issue → none
    - contradicted with a visible issue → low (minor incidental damage seen)
    - supported: severity by issue type
    """
    if claim_status == ClaimStatus.NOT_ENOUGH_INFORMATION:
        return Severity.UNKNOWN

    if claim_status == ClaimStatus.CONTRADICTED:
        if not visible_issue or visible_issue in (
            IssueType.NONE.value, IssueType.UNKNOWN.value
        ):
            return Severity.NONE
        return Severity.LOW

    # claim_status == SUPPORTED
    if not visible_issue or visible_issue == IssueType.UNKNOWN.value:
        return Severity.UNKNOWN
    if visible_issue == IssueType.NONE.value:
        return Severity.NONE
    if visible_issue in _HIGH_SEVERITY_ISSUES:
        return Severity.HIGH
    if visible_issue in _MEDIUM_SEVERITY_ISSUES:
        return Severity.MEDIUM
    if visible_issue in _LOW_SEVERITY_ISSUES:
        return Severity.LOW
    return Severity.UNKNOWN


# ── Supporting image ID helpers ───────────────────────────────────────────────

def _format_ids(ids: list[str]) -> str:
    return ";".join(ids) if ids else RiskFlag.NONE.value


# ── Best visible fields across all assessments ────────────────────────────────

def _best_visible_issue(perception: GeminiPerception) -> str | None:
    """Return the first non-null, non-unknown visible_issue across assessments."""
    for a in perception.image_assessments:
        if a.visible_issue and a.visible_issue not in (
            IssueType.UNKNOWN.value, IssueType.NONE.value
        ):
            return a.visible_issue
    # Fall back to any non-null value (including "none").
    for a in perception.image_assessments:
        if a.visible_issue:
            return a.visible_issue
    return None


def _best_visible_part(perception: GeminiPerception) -> str | None:
    """Return the first non-null, non-unknown visible_part across assessments."""
    for a in perception.image_assessments:
        if a.visible_part and a.visible_part != "unknown":
            return a.visible_part
    return None


# ── Main decision function ────────────────────────────────────────────────────

def decide(
    perception: GeminiPerception,
    risk_flags: str,
    claim_object: ClaimObject,  # noqa: ARG001  (reserved for future object-specific rules)
) -> RuleEngineResult:
    """
    Apply the deterministic decision matrix to produce all business fields.

    Decision matrix (applied in order):

    STEP 1 — valid_image
      ALL image_assessments[].valid == False → valid_image = False
      Otherwise → valid_image = True

    STEP 2 — evidence_standard_met
      No images loaded (assessments empty)          → False
      valid_image == False                          → False
      any_image_shows_claimed_part == False         → False
      Otherwise                                     → True

    STEP 3 — claim_status
      evidence_standard_met == False
        → not_enough_information
      evidence_standard_met == True AND issue_matches_claim == False
        → contradicted
      evidence_standard_met == True AND part_matches_claim == False
        → contradicted
      evidence_standard_met == True AND both match
        → supported

    STEP 4 — severity
      See _resolve_severity().

    Args:
        perception:   Validated GeminiPerception from Gemini.
        risk_flags:   Pre-aggregated semicolon string from risk_aggregator.
        claim_object: ClaimObject enum (reserved for future object-specific rules).

    Returns:
        RuleEngineResult with all business-decision fields populated.
    """
    summary = perception.perception_summary
    extracted = perception.extracted_claim
    assessments = perception.image_assessments

    # ── STEP 1: valid_image ───────────────────────────────────────────────────
    valid_image = any(a.valid for a in assessments) if assessments else False

    # ── STEP 2: evidence_standard_met ────────────────────────────────────────
    if not assessments:
        evidence_met = False
        evidence_reason = "No images were submitted or could be loaded."
    elif not valid_image:
        evidence_met = False
        evidence_reason = "All submitted images are invalid or unusable for automated review."
    elif not summary.any_image_shows_claimed_part:
        evidence_met = False
        evidence_reason = (
            f"No image shows the claimed {extracted.claimed_part}; "
            "the claimed part cannot be assessed."
        )
    else:
        evidence_met = True
        evidence_reason = (
            f"At least one image shows the claimed {extracted.claimed_part} "
            "with sufficient clarity to evaluate the claim."
        )

    # ── STEP 3: claim_status ─────────────────────────────────────────────────
    if not evidence_met:
        status = ClaimStatus.NOT_ENOUGH_INFORMATION
        justification = _justify_not_enough(evidence_reason, assessments)

    elif not summary.issue_matches_claim and not summary.part_matches_claim:
        status = ClaimStatus.CONTRADICTED
        justification = (
            f"Images show neither the claimed part ({extracted.claimed_part}) "
            f"nor the claimed issue ({extracted.claimed_issue}). "
            f"Visible: part={_best_visible_part(perception) or 'unknown'}, "
            f"issue={_best_visible_issue(perception) or 'unknown'}."
        )

    elif not summary.issue_matches_claim:
        status = ClaimStatus.CONTRADICTED
        visible_issue = _best_visible_issue(perception) or "unknown"
        justification = (
            f"The claimed issue ({extracted.claimed_issue}) is not visible. "
            f"Images show '{visible_issue}' instead. "
            f"Claim is contradicted by visual evidence."
        )

    elif not summary.part_matches_claim:
        status = ClaimStatus.CONTRADICTED
        visible_part = _best_visible_part(perception) or "unknown"
        justification = (
            f"The claimed part ({extracted.claimed_part}) is not confirmed by images. "
            f"Visible part is '{visible_part}'. "
            f"Claim is contradicted by visual evidence."
        )

    else:
        status = ClaimStatus.SUPPORTED
        ids = _format_ids(summary.supporting_image_ids)
        justification = (
            f"Images confirm the claimed {extracted.claimed_part} "
            f"with visible {extracted.claimed_issue}. "
            f"Supporting images: {ids}."
        )

    # ── STEP 4: issue_type and object_part ───────────────────────────────────
    # Prefer extracted_claim values (Gemini parsed from conversation).
    # Fall back to best visible values if extracted values are unknown.
    issue_type = extracted.claimed_issue or IssueType.UNKNOWN.value
    if issue_type == IssueType.UNKNOWN.value:
        issue_type = _best_visible_issue(perception) or IssueType.UNKNOWN.value

    object_part = extracted.claimed_part or "unknown"
    if object_part == "unknown":
        object_part = _best_visible_part(perception) or "unknown"

    # ── STEP 5: severity ─────────────────────────────────────────────────────
    visible_issue_for_severity = _best_visible_issue(perception)
    severity = _resolve_severity(status, visible_issue_for_severity)

    # ── Supporting image IDs ──────────────────────────────────────────────────
    supporting_ids = _format_ids(summary.supporting_image_ids)

    return RuleEngineResult(
        valid_image=valid_image,
        evidence_standard_met=evidence_met,
        evidence_standard_met_reason=evidence_reason,
        claim_status=status,
        claim_status_justification=justification,
        issue_type=issue_type,
        object_part=object_part,
        supporting_image_ids=supporting_ids,
        severity=severity,
    )


# ── Justification helpers ─────────────────────────────────────────────────────

def _justify_not_enough(
    evidence_reason: str,
    assessments: list,
) -> str:
    """Build a justification string for not_enough_information status."""
    if not assessments:
        return "No images available to evaluate the claim."
    invalid_count = sum(1 for a in assessments if not a.valid)
    total = len(assessments)
    if invalid_count == total:
        return f"All {total} submitted image(s) are unusable. {evidence_reason}"
    return (
        f"Image evidence is insufficient to evaluate the claim. {evidence_reason}"
    )