# Evaluation Report — Multi-Modal Evidence Review

## Executive Summary

| Item | Value |
|---|---|
| Evaluation date | June 2026 |
| Sample records evaluated | 20 (dataset/sample_claims.csv) |
| Test records (production) | 44 (dataset/claims.csv) |
| Evaluation strategy comparison | Strategy A vs Strategy B |
| Winning strategy | Not measured during final submission run. |
| Mean accuracy (winner) | Not measured during final submission run. |
| Primary metric (claim_status accuracy) | Not measured during final submission run. |

The production pipeline successfully processed all 44 test claims with zero
failures. `output.csv` was generated with the exact required schema and column
order.

---

## Evaluation Methodology

### Dataset
- `dataset/sample_claims.csv`: 20 rows with ground-truth labels across all output fields.
- Claims span three object types: car, laptop, package.
- Images loaded from `dataset/images/sample/`.

### Process
1. Load all 20 sample claims with ground-truth labels.
2. Run Strategy A through the full pipeline (Gemini perception → rule engine).
3. Run Strategy B through the full pipeline.
4. Compare predicted values against ground-truth for all evaluable fields.
5. Select winning strategy for production run.

To reproduce this evaluation:

```bash
python code/evaluation/main.py
```

### Metrics
- **Exact-match accuracy:** `claim_status`, `evidence_standard_met`, `valid_image`, `severity`, `issue_type`, `object_part`
- **Jaccard similarity:** `risk_flags` (set overlap between predicted and expected flag sets)
- **Mean accuracy:** unweighted average across all accuracy fields

---

## Strategy Definitions

### Strategy A — Production Prompt
Base perception prompt as defined in `services/prompt_builder.py`.
Instructs Gemini to report only what is visually present.
No additional guidance on edge cases.
Used for the final production run that generated `output.csv`.

### Strategy B — Refined Prompt
Strategy A plus:
- Explicit instruction to prefer `shows_claimed_part=false` when visibility is ambiguous.
- Priority rule: `wrong_object_detected=true` overrides all other signals for that image.
- Strict null handling: `visible_issue` must be `null`, never omitted.
- Multi-part conversation resolution: extract only the final confirmed claim.

---

## Strategy Comparison

Not measured during final submission run.

Run `python code/evaluation/main.py` to generate actual values.

| Field | Strategy A | Strategy B | Winner |
|---|---|---|---|
| claim_status | — | — | — |
| evidence_standard_met | — | — | — |
| valid_image | — | — | — |
| severity | — | — | — |
| issue_type | — | — | — |
| object_part | — | — | — |
| risk_flags (Jaccard) | — | — | — |
| **Mean accuracy** | **—** | **—** | **—** |

---

## Final Strategy Selected

**Selected:** Strategy A

**Rationale:** Strategy A (the base production prompt) was used to generate
the final `output.csv` for all 44 test claims. A formal head-to-head comparison
against Strategy B was not completed before the submission deadline.
Strategy B remains available in `code/evaluation/main.py` for post-submission
analysis.

---

## Operational Analysis

### Model Calls — Final Production Run

| Phase | Claims | Gemini Calls | Cache Hits | Notes |
|---|---|---|---|---|
| Production (final run) | 44 | 8 | 36 | Resumed from checkpoint |
| Evaluation (if run) | 20 | up to 40 | depends on cache | 2 strategies × 20 claims |
| **Total actual API calls** | | **8** | | |

The low Gemini call count in the final run reflects the checkpoint/cache system.
36 of 44 claims were already processed in earlier runs and loaded from local cache.

### Token Usage (Estimates per Call)

| Component | Tokens (approx.) |
|---|---|
| System prompt | ~600 |
| User prompt | ~300 |
| Images (avg 2 per claim × ~500 tokens) | ~1000 |
| Output JSON | ~400 |
| **Total per call** | **~2300** |

Full cold run equivalent (44 claims):
- Input: ~44 × 1900 = ~83,600 tokens
- Output: ~44 × 400 = ~17,600 tokens

Actual final run (8 Gemini calls):
- Input: ~8 × 1900 = ~15,200 tokens
- Output: ~8 × 400 = ~3,200 tokens

### Image Processing

| Phase | Images (approx.) |
|---|---|
| Production test set (full) | ~101 (avg 2.3/claim × 44) |
| Actually sent to Gemini (final run) | ~18 (8 calls × avg 2.3 images) |
| Sample evaluation (if run) | ~46 (avg 2.3/claim × 20) |

### Cost Estimate

Gemini 2.5 Flash pricing (June 2026 — verify current pricing):
- Input: ~$0.075 per 1M tokens
- Output: ~$0.30 per 1M tokens

| Scenario | Input cost | Output cost | Total |
|---|---|---|---|
| Full cold run (44 calls) | ~$0.006 | ~$0.005 | ~$0.011 |
| Final cached run (8 calls) | ~$0.001 | ~$0.001 | ~$0.002 |
| Sample evaluation (40 calls) | ~$0.006 | ~$0.004 | ~$0.010 |

The cache system reduced final run cost by approximately 82% compared to a
full cold run.

> Costs are approximate. Image token counts vary by image size and resolution.

### Runtime

| Phase | Calls | Avg latency | Inter-call sleep | Estimated total |
|---|---|---|---|---|
| Full cold run (44 calls) | 44 | ~3s | 1s | ~176s (~3 min) |
| Final cached run (8 calls) | 8 | ~3s | 1s | ~32s |
| Sample evaluation (40 calls) | 40 | ~3s | 1s | ~160s (~2.7 min) |

Cache hits add negligible latency (JSON file read < 5ms per claim).

### TPM / RPM Considerations

- Inter-call sleep: 1.0 s (configurable via `INTER_CALL_SLEEP_SECONDS` in `config.py`)
- Retry: exponential backoff, base 2 s, doubles per attempt, max 3 attempts
- Gemini 2.5 Flash free tier: 10 RPM / 250,000 TPM
- At 1 call/s with ~2300 tokens/call: within TPM limits
- If 429 errors occur: increase `INTER_CALL_SLEEP_SECONDS` to 6.0 (= 10 RPM)
- Cache means quota pressure is minimal on repeated or resumed runs

### Caching Strategy

- System prompt built once per run, reused across all claims.
- User history and evidence requirements loaded once, looked up via dict.
- Per-claim JSON cache keyed by `user_id + image_paths` — stable across runs.
- Checkpoint written immediately after each successful claim.
- Corrupt cache files detected at load time; affected claim is re-processed.
- Separate cache namespaces for production and each evaluation strategy:
  - `.cache/claims/` — production
  - `.cache/eval_strategy_a/claims/` — Strategy A evaluation
  - `.cache/eval_strategy_b/claims/` — Strategy B evaluation

---

## Failure Modes Observed

| Failure Mode | Observed | Notes |
|---|---|---|
| Gemini quota exceeded mid-run | Yes | Resolved by checkpoint/resume; pipeline continued on next run |
| JSON parse failure | Not observed in final run | Retry logic handles transient malformed responses |
| Missing image files | Not observed in final run | image_loader warns and skips gracefully |
| Corrupt cache file | Not observed in final run | Detected at load; claim re-processed automatically |
| wrong_object_detected missed | Not measured | Formal evaluation not run before submission |
| Severity underestimated | Not measured | Depends on Gemini visible_issue accuracy |
| Multi-part claim extraction error | Not measured | Depends on Gemini conversation parsing |
| risk_flags incomplete | Not measured | Formal Jaccard evaluation not run before submission |
| evidence_standard_met false positive | Not measured | Formal evaluation not run before submission |

---

## Final Recommendation

The production system successfully generated `output.csv` for all 44 claims
with zero final processing failures.

**Strategy A** (base production prompt) was used for the final output.

The checkpoint and cache system proved essential during development: the pipeline
was interrupted multiple times due to API quota limits, and the resume capability
allowed completion without reprocessing already-successful claims. In the final
run, 36 of 44 claims were served from cache with 8 Gemini API calls made.

Key strengths of the final system:
- Deterministic output for the same perception input
- Prompt injection resistance via explicit detection and flag-only response
- Graceful handling of multi-image claims with per-image independent assessment
- Cost-efficient execution through aggressive local caching
- Zero-reconfiguration resume from any point of interruption

Known limitations:
- Severity accuracy depends entirely on Gemini's visible_issue classification.
- Multi-language conversations (Spanish, Hindi) rely on Gemini multilingual capability.
- Rule engine cannot self-correct a wrong visible_issue from Gemini.
- Formal accuracy measurement against sample_claims.csv ground truth was not
  completed before the submission deadline.

Post-hackathon improvements:
- Run formal evaluation and fill in Strategy A vs B comparison table.
- Add few-shot examples per object type to the system prompt.
- Implement a confidence threshold to escalate ambiguous cases to `not_enough_information`.
- Migrate from deprecated `google-generativeai` SDK to `google.genai`.
- Add image hash-based deduplication to avoid re-encoding identical images.