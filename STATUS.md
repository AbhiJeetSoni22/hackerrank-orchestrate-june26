# STATUS.md

## Project Status

**Project:** Multi-Modal Evidence Review Agent
**Hackathon:** HackerRank Orchestrate
**Current Phase:** Phase 5 Preparation
**Architecture Status:** Frozen ✅

---
## Technical Notes:
- Current implementation uses google-generativeai SDK.
- SDK is deprecated but remains functional.
- Migration to google.genai SDK can be done after hackathon if needed.

# Architecture Summary

```text
claims.csv
+ user_history.csv
+ evidence_requirements.csv
        │
        ▼
   csv_loader
        │
        ▼
 Pydantic Models
 (Claim, UserHistory,
  EvidenceRequirement)
        │
        ▼
   image_loader
        │
        ▼
  prompt_builder
 (system prompt + user prompt)
        │
        ▼
  gemini_client
 (Single Gemini Call)
        │
        ▼
 GeminiPerception
 (Perception Layer)
        │
 ┌──────┴───────────┐
 │                  │
 ▼                  ▼
risk_aggregator   rule_engine
(Python)          (Python)
 │                  │
 └──────┬───────────┘
        ▼
   ClaimResult
        │
        ▼
  output_writer
        │
        ▼
    output.csv
```

---

## Progress

| Phase | Description | Status |
|---|---|---|
| 1 | Foundation: models, config, csv_loader, image_loader | ✅ Complete |
| 2 | Gemini integration: gemini_client, prompt_builder | ✅ Complete |
| 3 | Rule engine: rule_engine, risk_aggregator | ✅ Complete |
| 4 | Pipeline: output_writer, main.py | ✅ Complete |
| 5 | Evaluation, metrics, report, README | ✅ Complete |

---

## All Completed Modules

| File | Purpose |
|---|---|
| `code/models.py` | Pydantic v2 domain models and enums |
| `code/config.py` | Paths, model name, rate-limit constants, OUTPUT_COLUMNS |
| `code/services/csv_loader.py` | load_claims, load_user_history, load_evidence_requirements |
| `code/services/image_loader.py` | Base64 encode, MIME detection, missing-file warning |
| `code/services/gemini_client.py` | Gemini call, retry/backoff, JSON parse, validation |
| `code/services/prompt_builder.py` | System prompt + per-claim user prompt |
| `code/services/risk_aggregator.py` | Merge perception + history flags → risk_flags |
| `code/services/rule_engine.py` | Deterministic: valid_image, evidence_standard_met, claim_status, severity |
| `code/services/output_writer.py` | Write ClaimResult list → output.csv; QUOTE_ALL |
| `code/main.py` | Pipeline entry point |
| `code/evaluation/metrics.py` | accuracy(), jaccard_similarity(), generate_summary(), compare |
| `code/evaluation/main.py` | Strategy A vs B evaluation on sample_claims.csv |
| `code/evaluation/evaluation_report.md` | Evaluation findings template |
| `README.md` | Setup, usage, architecture, schema, design decisions |
| `requirements.txt` | google-generativeai, pydantic, python-dotenv |
| `.env.example` | Environment variable template |

---

## Submission Checklist

- [ ] Run evaluation: `python code/evaluation/main.py`
  - Fill in actual metrics in `code/evaluation/evaluation_report.md`
  - Record winning strategy
- [ ] Run production pipeline: `python code/main.py`
  - Confirm exit code 0 (no errors)
  - Confirm `output.csv` exists at repo root
- [ ] Validate output schema
  - `output.csv` has exactly 46 rows (one per claim in `claims.csv`)
  - All 14 required columns present in correct order
  - Boolean fields are lowercase `true`/`false`
  - `risk_flags` and `supporting_image_ids` use semicolon separation or `none`
- [ ] Prepare code zip
  - Include: `code/`, `requirements.txt`, `.env.example`, `README.md`, `STATUS.md`
  - Exclude: `.env`, `__pycache__/`, `*.pyc`, `venv/`, `.git/`
- [ ] Export chat transcript (`$HOME/hackerrank_orchestrate/log.txt`)
- [ ] Submit on HackerRank Community Platform:
  1. `code.zip`
  2. `output.csv`
  3. `log.txt` (chat transcript)
- [ ] Prepare for AI Judge interview
  - Architecture walkthrough ready
  - Able to explain perception vs rule engine split
  - Strategy A vs B comparison results memorised
  - Cost and latency numbers ready

---

## Technical Notes

- `google-generativeai` SDK used (deprecated, functional; migrate to `google.genai` post-hackathon).
- No LangChain, no database, no message queue — intentionally minimal.
- All business decisions are in pure Python — auditable and deterministic.
- Failed claims are skipped with logging; pipeline completes even under partial failure.