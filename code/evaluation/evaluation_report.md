# Evaluation Report — Multi-Modal Evidence Review

## Executive Summary

This report documents the evaluation of the damage claim verification system
on `dataset/sample_claims.csv` (20 labeled records). Two prompt strategies
were compared. The winning strategy is used to produce the final `output.csv`.

> **Fill in after running `python code/evaluation/main.py`**

| Item | Value |
|---|---|
| Evaluation date | YYYY-MM-DD |
| Sample records | 20 |
| Test records | 46 |
| Winning strategy | Strategy A / Strategy B |
| Mean accuracy (winner) | XX.X% |
| Primary metric (claim_status accuracy) | XX.X% |

---

## Evaluation Methodology

### Dataset
- `dataset/sample_claims.csv`: 20 rows with ground-truth labels across all output fields.
- Claims span three object types: car (10), laptop (6), package (6) — approximate.
- Images loaded from `dataset/images/sample/`.

### Process
1. Load all 20 sample claims.
2. Run Strategy A through full pipeline (Gemini perception → rule engine).
3. Run Strategy B through full pipeline.
4. Compare predicted values against ground-truth for all evaluable fields.
5. Select winning strategy.

### Metrics
- **Exact-match accuracy**: `claim_status`, `evidence_standard_met`, `valid_image`, `severity`, `issue_type`, `object_part`
- **Jaccard similarity**: `risk_flags` (set overlap between predicted and expected flag sets)
- **Mean accuracy**: unweighted average across all accuracy fields

---

## Strategy Definitions

### Strategy A — Production Prompt
Base perception prompt as defined in `services/prompt_builder.py`.
Instructs Gemini to report only what is visually present.
No additional guidance on edge cases.

### Strategy B — Refined Prompt
Strategy A plus:
- Explicit instruction to prefer `shows_claimed_part=false` when visibility is ambiguous.
- Priority rule: `wrong_object_detected=true` overrides all other signals for that image.
- Strict null handling: `visible_issue` must be `null`, never omitted.
- Multi-part conversation resolution: extract only the final confirmed claim.

---

## Strategy Comparison

> **Fill in after running evaluation**

| Field | Strategy A | Strategy B | Winner |
|---|---|---|---|
| claim_status | XX.X% | XX.X% | — |
| evidence_standard_met | XX.X% | XX.X% | — |
| valid_image | XX.X% | XX.X% | — |
| severity | XX.X% | XX.X% | — |
| issue_type | XX.X% | XX.X% | — |
| object_part | XX.X% | XX.X% | — |
| risk_flags (Jaccard) | XX.X% | XX.X% | — |
| **Mean accuracy** | **XX.X%** | **XX.X%** | **—** |

---

## Final Strategy Selected

> **Fill in after running evaluation**

**Selected:** Strategy A / Strategy B

**Rationale:** [Insert rationale — e.g. Strategy B improved claim_status accuracy
by X points primarily by reducing false positives on multi-part conversations.]

---

## Operational Analysis

### Model Calls

| Phase | Claims | Calls | Note |
|---|---|---|---|
| Evaluation (sample) | 20 | 40 | 2 strategies × 20 claims |
| Production (test) | 46 | 46 | 1 call per claim |
| **Total** | — | **~86** | |

### Token Usage (Estimates)

Gemini 2.5 Flash token estimates per call:

| Component | Tokens (approx.) |
|---|---|
| System prompt | ~600 |
| User prompt | ~300 |
| Images (1–3 × ~500) | ~500–1500 |
| Output JSON | ~400 |
| **Total per call** | **~1800–2800** |

Full test run (46 calls, avg 2 images):
- Input: ~46 × 1600 = ~73,600 tokens
- Output: ~46 × 400 = ~18,400 tokens

### Image Processing

| Phase | Images (approx.) |
|---|---|
| Sample evaluation | ~45 (avg 2.3/claim × 20) |
| Test production | ~106 (avg 2.3/claim × 46) |

### Cost Estimate

Gemini 2.5 Flash pricing (as of June 2026 — verify current pricing):
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

| Phase | Input cost | Output cost | Total |
|---|---|---|---|
| Evaluation (40 calls) | ~$0.006 | ~$0.002 | ~$0.008 |
| Production (46 calls) | ~$0.006 | ~$0.002 | ~$0.008 |
| **Total** | | | **~$0.016** |

> Costs are approximate. Image tokens may vary significantly by image size.
> Adjust based on actual token counts from Gemini response metadata.

### Runtime

| Phase | Calls | Avg latency | Sleep | Estimated total |
|---|---|---|---|---|
| Evaluation | 40 | ~3s | 1s/call | ~160s (~2.7 min) |
| Production | 46 | ~3s | 1s/call | ~184s (~3.1 min) |

### TPM / RPM Considerations

- Inter-call sleep: 1.0 s (configurable via `INTER_CALL_SLEEP_SECONDS` in `config.py`)
- Retry: exponential backoff starting at 2 s, max 3 attempts
- Gemini 2.5 Flash free tier: 10 RPM / 250,000 TPM
- At 1 call/s with avg ~2200 tokens: well within TPM limits
- If 429 errors appear, increase `INTER_CALL_SLEEP_SECONDS` to 6.0 (10 RPM = 1 call/6s)

### Caching Strategy

- System prompt is built once per run and reused across all claims.
- User history and evidence requirements are loaded once and looked up via dict.
- Images are loaded per-claim (not cached) — acceptable at this scale.
- No result caching implemented — each run re-calls Gemini for all claims.

---

## Failure Modes Observed

> **Fill in after running evaluation**

| Failure Mode | Frequency | Impact | Notes |
|---|---|---|---|
| wrong_object_detected missed | X/20 | claim_status error | Gemini sometimes describes wrong object without flagging it |
| Severity underestimated | X/20 | severity mismatch | Rule engine maps from visible_issue; if Gemini misses issue, severity is wrong |
| Multi-part claim extraction | X/20 | object_part error | Gemini extracts first mentioned part rather than final confirmed part |
| risk_flags incomplete | X/20 | Jaccard < 1.0 | History flags not flagged when claim seems clean |
| evidence_standard_met false positive | X/20 | status error | Gemini marks shows_claimed_part=true on low-clarity images |

---

## Final Recommendation

> **Fill in after running evaluation**

Use **Strategy [A/B]** for the production run on `dataset/claims.csv`.

Key strengths:
- [Insert observed strengths]

Known limitations:
- Severity accuracy depends entirely on Gemini's visible_issue classification.
- Multi-language claim conversations (Spanish, Hindi) rely on Gemini's multilingual capability.
- Rule engine cannot correct a wrong visible_issue from Gemini.

To improve further (post-hackathon):
- Add few-shot examples to the system prompt for each object type.
- Implement a confidence threshold and escalate low-confidence cases to `not_enough_information`.
- Cache Gemini responses by image hash to avoid reprocessing duplicate images.