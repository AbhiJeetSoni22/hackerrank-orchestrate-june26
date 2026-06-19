"""
Gemini 2.5 Flash client for perception-only claims analysis.

Single call per claim. Returns GeminiPerception JSON.
Handles retries, rate limiting, and response parsing.
"""

from __future__ import annotations

import json
import time
import logging
from typing import Any

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MAX_RETRIES,
    GEMINI_RETRY_BASE_BACKOFF,
    INTER_CALL_SLEEP_SECONDS,
)
from models import GeminiPerception
from services.image_loader import EncodedImage

logger = logging.getLogger(__name__)


# ── Client init ───────────────────────────────────────────────────────────────

def _get_model() -> genai.GenerativeModel:
    """Configure and return a Gemini GenerativeModel instance."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Export it before running."
        )
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            temperature=0.0,  # deterministic
        ),
    )


# ── Image part builder ────────────────────────────────────────────────────────

def _build_image_parts(images: list[EncodedImage]) -> list[dict[str, Any]]:
    """
    Convert EncodedImage objects into Gemini inline_data parts.

    Uses the SDK's inline_data format so large base64 strings go
    into structured parts, not into the text prompt body.
    """
    parts = []
    for img in images:
        parts.append({
            "inline_data": {
                "mime_type": img.mime_type,
                "data": img.b64_data,
            }
        })
    return parts


# ── Response parsing ──────────────────────────────────────────────────────────

def _parse_response(raw_text: str) -> GeminiPerception:
    """
    Parse Gemini's JSON response into a GeminiPerception model.

    Strips markdown fences if the model wraps output despite mime_type setting.

    Raises:
        ValueError: If JSON is invalid or schema validation fails.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Strip opening fence (```json or ```) and closing ```
        text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned invalid JSON: {exc}\nRaw: {raw_text[:500]}") from exc

    try:
        return GeminiPerception.model_validate(data)
    except Exception as exc:
        raise ValueError(f"GeminiPerception schema validation failed: {exc}") from exc


# ── Retry logic ───────────────────────────────────────────────────────────────

def _is_retryable(exc: Exception) -> bool:
    """Return True for transient errors worth retrying (429, 5xx)."""
    msg = str(exc).lower()
    return any(code in msg for code in ("429", "500", "502", "503", "504", "quota", "rate"))


# ── Public API ────────────────────────────────────────────────────────────────

def call_gemini(
    system_prompt: str,
    user_prompt: str,
    images: list[EncodedImage],
) -> GeminiPerception:
    """
    Make a single Gemini 2.5 Flash call for one claim.

    Sends system prompt, user prompt, and all images as inline_data parts.
    Parses and validates the JSON response into GeminiPerception.

    Args:
        system_prompt: Perception instructions and JSON schema definition.
        user_prompt:   Claim-specific context (conversation, image IDs, history).
        images:        Encoded images for this claim.

    Returns:
        Validated GeminiPerception instance.

    Raises:
        RuntimeError: If all retries are exhausted.
        ValueError:   If the response cannot be parsed or validated.
    """
    model = _get_model()

    # Build content parts: text prompt + image inline_data parts
    image_parts = _build_image_parts(images)

    # Gemini SDK content format: list of parts
    contents = [
        {"role": "user", "parts": [
            {"text": user_prompt},
            *image_parts,
        ]}
    ]

    last_exc: Exception | None = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = model.generate_content(
                contents=contents,
                # Pass system prompt via system_instruction
            )
            raw = response.text
            perception = _parse_response(raw)
            # Throttle before returning so caller loop stays within RPM
            time.sleep(INTER_CALL_SLEEP_SECONDS)
            return perception

        except (ValueError,) as exc:
            # Non-retryable: bad JSON or schema mismatch
            raise

        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise

            backoff = GEMINI_RETRY_BASE_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "Gemini call failed (attempt %d/%d): %s. Retrying in %.1fs",
                attempt, GEMINI_MAX_RETRIES, exc, backoff,
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"Gemini call failed after {GEMINI_MAX_RETRIES} attempts: {last_exc}"
    )


def call_gemini_with_system(
    system_prompt: str,
    user_prompt: str,
    images: list[EncodedImage],
) -> GeminiPerception:
    """
    Variant that passes system_instruction via model kwargs for Gemini 2.5 Flash.

    Gemini 2.5 Flash supports system_instruction at model init time.
    Re-initialises the model per call to inject the system prompt.

    Args:
        system_prompt: Perception instructions and JSON schema.
        user_prompt:   Claim-specific context.
        images:        Encoded images for this claim.

    Returns:
        Validated GeminiPerception instance.
    """
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            temperature=0.0,
        ),
    )

    image_parts = _build_image_parts(images)
    contents = [
        {"role": "user", "parts": [
            {"text": user_prompt},
            *image_parts,
        ]}
    ]

    last_exc: Exception | None = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = model.generate_content(contents=contents)
            raw = response.text
            perception = _parse_response(raw)
            time.sleep(INTER_CALL_SLEEP_SECONDS)
            return perception

        except ValueError:
            raise

        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise

            backoff = GEMINI_RETRY_BASE_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "Gemini call failed (attempt %d/%d): %s. Retrying in %.1fs",
                attempt, GEMINI_MAX_RETRIES, exc, backoff,
            )
            time.sleep(backoff)

    raise RuntimeError(
        f"Gemini call failed after {GEMINI_MAX_RETRIES} attempts: {last_exc}"
    )