# Project Status

## Completed Modules

| Module | File | Notes |
|---|---|---|
| Domain models | `code/models.py` | Pydantic v2; enums, Claim, UserHistory, EvidenceRequirement, GeminiPerception, ClaimResult |
| Config | `code/config.py` | Paths, model name, rate-limit constants, output column order |
| CSV loader | `code/services/csv_loader.py` | load_claims, load_user_history, load_evidence_requirements, helpers |
| Image loader | `code/services/image_loader.py` | base64 encode, mime detection, missing-file warning |
| Gemini client | `code/services/gemini_client.py` | Single call per claim, retry/backoff, JSON parse, GeminiPerception validation |
| Prompt builder | `code/services/prompt_builder.py` | Static system prompt + dynamic user prompt; allowed values inline |

## Pending Modules

| Module | File | Priority |
|---|---|---|
| Rule engine | `code/services/rule_engine.py` | **Next — Phase 3** |
| Risk aggregator | `code/services/risk_aggregator.py` | Phase 3 |
| Output writer | `code/services/output_writer.py` | Phase 4 |
| Main pipeline | `code/main.py` | Phase 4 |
| Evaluation runner | `code/evaluation/main.py` | Phase 5 |
| Metrics | `code/evaluation/metrics.py` | Phase 5 |
| Evaluation report | `code/evaluation/evaluation_report.md` | Phase 5 |
| Code README | `code/README.md` | Phase 5 |

## Technical Notes:
- Current implementation uses google-generativeai SDK.
- SDK is deprecated but remains functional.
- Migration to google.genai SDK can be done after hackathon if needed.

## Architecture Summary
claims.csv + user_history.csv + evidence_requirements.csv

│

▼ csv_loader

Claim + UserHistory + EvidenceRequirement (Pydantic models)

│

▼ image_loader

EncodedImage list (base64, per claim)

│

▼ prompt_builder

system_prompt (static) + user_prompt (per claim)

│

▼ gemini_client  ← ONE call per claim

GeminiPerception JSON  (perception only: what is visible)

│

▼ rule_engine + risk_aggregator  (pure Python, no API calls)

ClaimResult

│

▼ output_writer

output.csv

**Key decisions:**
- Gemini does perception only: visible damage, image quality, part detection, injection detection.
- All business decisions (claim_status, evidence_standard_met, severity) are made in the Python rule engine.
- Images sent as inline_data parts, not embedded in text.
- `response_mime_type=application/json` + `temperature=0.0` for deterministic output.
- 1 s inter-call sleep; exponential backoff (base 2 s, doubles per retry) on 429/5xx.

---

## Completed Modules

| File | Purpose |
|---|---|
| `code/models.py` | Pydantic v2 domain models: enums, Claim, UserHistory, EvidenceRequirement, GeminiPerception, ClaimResult |
| `code/config.py` | Paths, model name, rate-limit constants, output column order |
| `code/services/csv_loader.py` | load_claims, load_user_history, load_evidence_requirements, filter helpers |
| `code/services/image_loader.py` | Base64 encode, MIME detection, missing-file warning, image_ids_from_paths |
| `code/services/gemini_client.py` | Single Gemini call, retry/backoff, JSON parse, GeminiPerception validation |
| `code/services/prompt_builder.py` | Static system prompt + dynamic user prompt; allowed values from enums |
| `requirements.txt` | google-generativeai, pydantic, python-dotenv |
| `.env.example` | Environment variable template |

---

## Pending Modules

| File | Purpose | Phase |
|---|---|---|
| `code/services/risk_aggregator.py` | Merge perception flags + history flags → risk_flags string | 3 |
| `code/services/rule_engine.py` | valid_image, evidence_standard_met, claim_status, severity, object_part, issue_type | 3 |
| `code/services/output_writer.py` | Write ClaimResult list → output.csv in exact column order | 4 |
| `code/main.py` | Pipeline entry point: load → encode → prompt → Gemini → rules → write | 4 |
| `code/evaluation/main.py` | Run pipeline on sample_claims.csv, compare strategies, print metrics | 5 |
| `code/evaluation/metrics.py` | Field-level accuracy, Jaccard for risk_flags, summary report | 5 |
| `code/evaluation/evaluation_report.md` | Operational analysis: cost, latency, token usage, strategy comparison | 5 |
| `code/README.md` | Setup, usage, env vars, run instructions | 5 |

---

## Next Phase — Phase 3: Rule Engine

Implement `code/services/risk_aggregator.py`:
- Collect quality_flags and image-level risk flags from all ImageAssessment objects
- Merge with user history_flags (user_history_risk, manual_review_required)
- Add text_instruction_present if any image flagged it
- Deduplicate, sort, return semicolon-joined string or "none"

Implement `code/services/rule_engine.py` with the decision matrix:
valid_image

└─ false if ALL image_assessments[].valid == false
evidence_standard_met

└─ false if any_image_shows_claimed_part == false

└─ false if all images invalid

└─ true otherwise
claim_status

└─ not_enough_information  if evidence_standard_met == false

└─ contradicted            if evidence_standard_met == true AND issue_matches_claim == false

└─ supported               if evidence_standard_met == true AND issue_matches_claim == true AND part_matches_claim == true

└─ contradicted            if evidence_standard_met == true AND part_matches_claim == false
severity

└─ unknown  if claim_status == not_enough_information

└─ none     if claim_status == contradicted (no visible issue)

└─ low      if contradicted but minor visible issue present

└─ medium   dent, stain, water_damage, torn_packaging, crushed_packaging (supported)

└─ high     crack, glass_shatter, broken_part, missing_part (supported)

└─ low      scratch (supported)