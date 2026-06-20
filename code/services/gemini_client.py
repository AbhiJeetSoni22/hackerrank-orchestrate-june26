"""
Gemini 2.5 Flash client — perception only.

One call per claim. Returns a validated GeminiPerception instance.
Handles retries, rate-limit backoff, and JSON parsing.
No business logic.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from config import (
    GEMINI_API_KEY,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_RETRY_BASE_BACKOFF,
    INTER_CALL_SLEEP_SECONDS,
)
from models import GeminiPerception
from services.image_loader import EncodedImage

logger = logging.getLogger(__name__)

# ── Retryable HTTP status substrings ─────────────────────────────────────────
_RETRYABLE = ("429", "500", "502", "503", "504", "quota", "rate limit", "resource exhausted")


def _configure() -> None:
    """Configure the Gemini SDK. Raises if key is absent."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Export it or add it to .env before running."
        )
    genai.configure(api_key=GEMINI_API_KEY)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in _RETRYABLE)


def _image_parts(images: list[EncodedImage]) -> list[dict[str, Any]]:
    """Convert EncodedImage list to Gemini inline_data parts."""
    return [
        {"inline_data": {"mime_type": img.mime_type, "data": img.b64_data}}
        for img in images
    ]


def _parse(raw: str) -> GeminiPerception:
    """
    Strip optional markdown fences and parse JSON into GeminiPerception.

    Raises:
        ValueError: on invalid JSON or schema mismatch.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            ln for ln in lines if not ln.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        with open("failed_response.json", "w", encoding="utf-8") as f:
         f.write(text)
        raise ValueError(
            f"Gemini returned invalid JSON: {exc}\nRaw (first 500 chars): {raw[:500]}"
        ) from exc

    try:
        return GeminiPerception.model_validate(data)
    except Exception as exc:
        raise ValueError(f"GeminiPerception validation failed: {exc}") from exc


def _repair_parse(
    model: genai.GenerativeModel,
    raw: str,
) -> GeminiPerception:
    """
    Ask Gemini to repair a malformed or truncated JSON response.

    This is only used after the first parse attempt fails. The repair prompt
    is intentionally short so the model can focus on returning a complete,
    valid JSON object matching the same schema.
    """
    repair_prompt = f"""\
The previous response was invalid or truncated JSON.
Return a complete valid JSON object only.
Preserve the same meaning and schema.
If a field is missing, use null, false, unknown, or an empty list as appropriate.
Do not add markdown, commentary, or extra keys.

INVALID_JSON:
{raw}
"""

    response = model.generate_content(
        contents=[
            {
                "role": "user",
                "parts": [{"text": repair_prompt}],
            }
        ]
    )
    return _parse(response.text)


# ── Public entry point ────────────────────────────────────────────────────────

def call_gemini(
    system_prompt: str,
    user_prompt: str,
    images: list[EncodedImage],
) -> GeminiPerception:
    """
    Make one Gemini 2.5 Flash call for a single claim.

    Sends system_instruction + user text + inline image parts.
    Parses the JSON response into a validated GeminiPerception.

    Args:
        system_prompt: Static perception instructions and JSON schema.
        user_prompt:   Claim-specific context (conversation, image IDs, history).
        images:        Encoded images for this claim, in submission order.

    Returns:
        Validated GeminiPerception instance.

    Raises:
        EnvironmentError: GEMINI_API_KEY not set.
        ValueError:       Response cannot be parsed or validated.
        RuntimeError:     All retry attempts exhausted.
    """
    _configure()

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
            temperature=0.0,
        ),
    )

    contents = [
        {
            "role": "user",
            "parts": [{"text": user_prompt}, *_image_parts(images)],
        }
    ]

    last_exc: Exception | None = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = model.generate_content(contents=contents)
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise

            backoff = GEMINI_RETRY_BASE_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "Gemini attempt %d/%d failed (%s). Retrying in %.1fs.",
                attempt,
                GEMINI_MAX_RETRIES,
                exc,
                backoff,
            )
            time.sleep(backoff)
            continue

        try:
            result = _parse(response.text)
            time.sleep(INTER_CALL_SLEEP_SECONDS)
            return result
        except ValueError as exc:
            logger.warning("JSON parse failed, attempting JSON repair...")

            try:
                result = _repair_parse(model, response.text)
                time.sleep(INTER_CALL_SLEEP_SECONDS)
                return result
            except Exception as repair_exc:
                last_exc = repair_exc
                logger.warning(
                    "JSON repair failed (%s). Retrying original request.",
                    repair_exc,
                )

    raise RuntimeError(
        f"Gemini call failed after {GEMINI_MAX_RETRIES} attempts. "
        f"Last error: {last_exc}"
    )