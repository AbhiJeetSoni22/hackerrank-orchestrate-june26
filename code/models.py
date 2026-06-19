"""
Domain models for the multi-modal evidence review system.

All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class ClaimObject(str, Enum):
    CAR = "car"
    LAPTOP = "laptop"
    PACKAGE = "package"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NOT_ENOUGH_INFORMATION = "not_enough_information"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class IssueType(str, Enum):
    DENT = "dent"
    SCRATCH = "scratch"
    CRACK = "crack"
    GLASS_SHATTER = "glass_shatter"
    BROKEN_PART = "broken_part"
    MISSING_PART = "missing_part"
    TORN_PACKAGING = "torn_packaging"
    CRUSHED_PACKAGING = "crushed_packaging"
    WATER_DAMAGE = "water_damage"
    STAIN = "stain"
    NONE = "none"
    UNKNOWN = "unknown"


class CarPart(str, Enum):
    FRONT_BUMPER = "front_bumper"
    REAR_BUMPER = "rear_bumper"
    DOOR = "door"
    HOOD = "hood"
    WINDSHIELD = "windshield"
    SIDE_MIRROR = "side_mirror"
    HEADLIGHT = "headlight"
    TAILLIGHT = "taillight"
    FENDER = "fender"
    QUARTER_PANEL = "quarter_panel"
    BODY = "body"
    UNKNOWN = "unknown"


class LaptopPart(str, Enum):
    SCREEN = "screen"
    KEYBOARD = "keyboard"
    TRACKPAD = "trackpad"
    HINGE = "hinge"
    LID = "lid"
    CORNER = "corner"
    PORT = "port"
    BASE = "base"
    BODY = "body"
    UNKNOWN = "unknown"


class PackagePart(str, Enum):
    BOX = "box"
    PACKAGE_CORNER = "package_corner"
    PACKAGE_SIDE = "package_side"
    SEAL = "seal"
    LABEL = "label"
    CONTENTS = "contents"
    ITEM = "item"
    UNKNOWN = "unknown"


class RiskFlag(str, Enum):
    NONE = "none"
    BLURRY_IMAGE = "blurry_image"
    CROPPED_OR_OBSTRUCTED = "cropped_or_obstructed"
    LOW_LIGHT_OR_GLARE = "low_light_or_glare"
    WRONG_ANGLE = "wrong_angle"
    WRONG_OBJECT = "wrong_object"
    WRONG_OBJECT_PART = "wrong_object_part"
    DAMAGE_NOT_VISIBLE = "damage_not_visible"
    CLAIM_MISMATCH = "claim_mismatch"
    POSSIBLE_MANIPULATION = "possible_manipulation"
    NON_ORIGINAL_IMAGE = "non_original_image"
    TEXT_INSTRUCTION_PRESENT = "text_instruction_present"
    USER_HISTORY_RISK = "user_history_risk"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


# ── Input models ─────────────────────────────────────────────────────────────

class Claim(BaseModel):
    """Single damage claim row from claims.csv or sample_claims.csv."""

    user_id: str = Field(..., description="User submitting the claim")
    image_paths: list[str] = Field(..., description="Parsed list of image paths")
    user_claim: str = Field(..., description="Raw chat transcript describing the issue")
    claim_object: ClaimObject = Field(..., description="Object type: car, laptop, or package")

    @property
    def image_ids(self) -> list[str]:
        """Derive image IDs from paths (filename without extension)."""
        import os
        return [os.path.splitext(os.path.basename(p))[0] for p in self.image_paths]


class UserHistory(BaseModel):
    """User claim history row from user_history.csv."""

    user_id: str
    past_claim_count: int = Field(default=0)
    accept_claim: int = Field(default=0)
    manual_review_claim: int = Field(default=0)
    rejected_claim: int = Field(default=0)
    last_90_days_claim_count: int = Field(default=0)
    history_flags: list[str] = Field(default_factory=list, description="Raw flag strings from CSV")
    history_summary: str = Field(default="")


class EvidenceRequirement(BaseModel):
    """Single row from evidence_requirements.csv."""

    requirement_id: str
    claim_object: str = Field(..., description="car, laptop, package, or all")
    applies_to: str = Field(..., description="Issue family this requirement covers")
    minimum_image_evidence: str = Field(..., description="Human-readable minimum evidence description")


# ── Gemini perception output ──────────────────────────────────────────────────

class ImageAssessment(BaseModel):
    """Per-image perception result returned by Gemini."""

    image_id: str
    valid: bool = Field(..., description="Whether image is usable for automated review")
    quality_flags: list[str] = Field(
        default_factory=list,
        description="Perception-layer image quality issues"
    )
    shows_claimed_object: bool = Field(..., description="Image shows the claimed object type")
    shows_claimed_part: bool = Field(..., description="Image shows the claimed object part")
    visible_issue: Optional[str] = Field(None, description="Issue type visible in image, or null")
    visible_part: Optional[str] = Field(None, description="Object part visible in image, or null")
    wrong_object_detected: bool = Field(default=False)
    text_instruction_present: bool = Field(default=False)
    notes: Optional[str] = Field(None, description="Brief observation from Gemini")


class ExtractedClaim(BaseModel):
    """Claim intent extracted from the conversation by Gemini."""

    object_type: str
    claimed_part: str
    claimed_issue: str
    claim_summary: str
    prompt_injection_detected: bool = Field(default=False)
    injection_evidence: Optional[str] = Field(None)


class PerceptionSummary(BaseModel):
    """Cross-image summary produced by Gemini."""

    any_image_shows_claimed_part: bool
    any_image_shows_claimed_issue: bool
    issue_matches_claim: bool
    part_matches_claim: bool
    supporting_image_ids: list[str] = Field(default_factory=list)


class GeminiPerception(BaseModel):
    """Full structured output from a single Gemini call."""

    extracted_claim: ExtractedClaim
    image_assessments: list[ImageAssessment]
    perception_summary: PerceptionSummary


# ── Final output model ────────────────────────────────────────────────────────

class ClaimResult(BaseModel):
    """
    One output row written to output.csv.

    Column order matches the required schema exactly.
    """

    user_id: str
    image_paths: str = Field(..., description="Original semicolon-joined image_paths string")
    user_claim: str
    claim_object: str

    evidence_standard_met: bool
    evidence_standard_met_reason: str
    risk_flags: str = Field(..., description="Semicolon-separated risk flags, or 'none'")
    issue_type: str
    object_part: str
    claim_status: str
    claim_status_justification: str
    supporting_image_ids: str = Field(..., description="Semicolon-separated image IDs, or 'none'")
    valid_image: bool
    severity: str