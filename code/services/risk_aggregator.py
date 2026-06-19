"""
Risk aggregator.

Merges perception-layer image flags with user history flags
into a single semicolon-joined risk_flags string for output.

Pure Python. No API calls. No business decisions beyond flag collection.
"""

from __future__ import annotations

from models import GeminiPerception, RiskFlag, UserHistory


# Flags that Gemini reports per-image and must be promoted to claim-level.
_IMAGE_QUALITY_FLAGS: frozenset[str] = frozenset({
    RiskFlag.BLURRY_IMAGE.value,
    RiskFlag.CROPPED_OR_OBSTRUCTED.value,
    RiskFlag.LOW_LIGHT_OR_GLARE.value,
    RiskFlag.WRONG_ANGLE.value,
})

_IMAGE_RISK_FLAGS: frozenset[str] = frozenset({
    RiskFlag.WRONG_OBJECT.value,
    RiskFlag.WRONG_OBJECT_PART.value,
    RiskFlag.DAMAGE_NOT_VISIBLE.value,
    RiskFlag.CLAIM_MISMATCH.value,
    RiskFlag.POSSIBLE_MANIPULATION.value,
    RiskFlag.NON_ORIGINAL_IMAGE.value,
    RiskFlag.TEXT_INSTRUCTION_PRESENT.value,
})

# History flags passed through verbatim from user_history.csv.
_HISTORY_FLAGS: frozenset[str] = frozenset({
    RiskFlag.USER_HISTORY_RISK.value,
    RiskFlag.MANUAL_REVIEW_REQUIRED.value,
})

# Canonical output order for determinism.
_FLAG_ORDER: list[str] = [
    RiskFlag.BLURRY_IMAGE.value,
    RiskFlag.CROPPED_OR_OBSTRUCTED.value,
    RiskFlag.LOW_LIGHT_OR_GLARE.value,
    RiskFlag.WRONG_ANGLE.value,
    RiskFlag.WRONG_OBJECT.value,
    RiskFlag.WRONG_OBJECT_PART.value,
    RiskFlag.DAMAGE_NOT_VISIBLE.value,
    RiskFlag.CLAIM_MISMATCH.value,
    RiskFlag.POSSIBLE_MANIPULATION.value,
    RiskFlag.NON_ORIGINAL_IMAGE.value,
    RiskFlag.TEXT_INSTRUCTION_PRESENT.value,
    RiskFlag.USER_HISTORY_RISK.value,
    RiskFlag.MANUAL_REVIEW_REQUIRED.value,
]
_FLAG_RANK: dict[str, int] = {flag: i for i, flag in enumerate(_FLAG_ORDER)}


def aggregate_risk_flags(
    perception: GeminiPerception,
    user_history: UserHistory | None,
) -> str:
    """
    Collect and merge all risk signals into a semicolon-joined string.

    Sources:
    - Per-image quality_flags from every ImageAssessment.
    - Per-image structural flags (wrong_object_detected, text_instruction_present).
    - Global injection flag from extracted_claim.
    - User history_flags filtered to known RiskFlag values.

    Args:
        perception:   Full GeminiPerception returned by Gemini.
        user_history: UserHistory for the claim's user, or None.

    Returns:
        Semicolon-separated risk flag string, or "none".
    """
    collected: set[str] = set()

    # ── Perception: per-image flags ───────────────────────────────────────────
    for assessment in perception.image_assessments:
        # Quality flags reported as strings by Gemini.
        for flag in assessment.quality_flags:
            normalised = flag.strip().lower()
            if normalised in (_IMAGE_QUALITY_FLAGS | _IMAGE_RISK_FLAGS):
                collected.add(normalised)

        # Structured boolean fields Gemini sets directly.
        if assessment.wrong_object_detected:
            collected.add(RiskFlag.WRONG_OBJECT.value)

        if assessment.text_instruction_present:
            collected.add(RiskFlag.TEXT_INSTRUCTION_PRESENT.value)

    # ── Perception: claim-level injection flag ────────────────────────────────
    if perception.extracted_claim.prompt_injection_detected:
        collected.add(RiskFlag.TEXT_INSTRUCTION_PRESENT.value)

    # ── User history flags ────────────────────────────────────────────────────
    if user_history:
        for flag in user_history.history_flags:
            normalised = flag.strip().lower()
            if normalised in _HISTORY_FLAGS:
                collected.add(normalised)

    if not collected:
        return RiskFlag.NONE.value

    # Sort by canonical order for deterministic output.
    ordered = sorted(collected, key=lambda f: _FLAG_RANK.get(f, 999))
    return ";".join(ordered)