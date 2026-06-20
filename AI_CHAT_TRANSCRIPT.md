# AI Chat Transcript — Multi-Modal Evidence Review System

**Hackathon:** HackerRank Orchestrate — June 2026
**Participant:** Human developer (sole author)
**AI Tool Used:** Claude (Anthropic) — claude.ai web interface
**Document Type:** Development session summary for judge review

---

## Project Overview

The Multi-Modal Evidence Review System verifies damage claims by combining
Gemini 2.5 Flash vision analysis with a deterministic Python rule engine.
For each claim, the system inspects submitted images, extracts visible damage
information, and produces a structured verdict covering claim status, severity,
evidence sufficiency, and risk flags.

**Role of Claude during development:**
Claude assisted with architecture design, data model definitions, service
implementations, prompt engineering, and documentation. All suggestions were
reviewed, validated, and integrated by the participant.

**Role of the human developer:**
The participant directed all design decisions, selected technologies, reviewed
and debugged all generated code, managed API quota constraints, implemented
the cache and checkpoint strategy, ran the pipeline end-to-end, validated
output correctness, and prepared the final submission.

---

## AI-Assisted Development Sessions

### Session 1 — Architecture Design

The participant described the problem requirements and constraints. Claude
proposed a two-layer architecture separating Gemini perception from Python
business logic.

**Key outputs from this session:**
- Folder structure: `code/services/`, `code/evaluation/`, `dataset/images/`
- Pipeline flow: CSV loader → image loader → prompt builder → Gemini client →
  risk aggregator → rule engine → output writer
- Core architectural decision documented: Gemini performs perception only;
  all claim decisions are made by a deterministic Python rule engine
- Service list with clear single responsibilities per module
- Processing pipeline with one Gemini API call per claim
- Evaluation approach comparing two prompt strategies on labeled sample data

The participant reviewed the proposed architecture, approved the separation of
concerns, and confirmed the technology constraints: Python, Gemini 2.5 Flash,
no LangChain, no database, no web framework.

---

### Session 2 — Data Models and Services

Claude generated the foundational data layer based on the approved architecture
and the problem statement schema.

**Key outputs from this session:**
- `models.py`: Pydantic v2 models for `Claim`, `UserHistory`,
  `EvidenceRequirement`, `GeminiPerception`, `ImageAssessment`,
  `ExtractedClaim`, `PerceptionSummary`, and `ClaimResult`
- Enums for all allowed values: `ClaimObject`, `ClaimStatus`, `Severity`,
  `IssueType`, `CarPart`, `LaptopPart`, `PackagePart`, `RiskFlag`
- `config.py`: centralised path resolution, model name, rate-limit constants,
  and output column order
- `csv_loader.py`: loaders for all three CSVs with semicolon-field parsing
- `image_loader.py`: base64 encoding, MIME type detection, missing-file
  graceful skipping

The participant verified that all enum values matched the problem statement's
allowed values exactly, and confirmed the Pydantic model structures before
proceeding.

---

### Session 3 — Gemini Integration

Claude designed the perception prompt and Gemini client based on the approved
JSON schema from Session 1.

**Key outputs from this session:**
- `prompt_builder.py`: static system prompt (sent as `system_instruction`)
  and dynamic per-claim user prompt; all allowed values derived from enums
  to maintain a single source of truth
- `gemini_client.py`: single API call per claim using
  `response_mime_type=application/json` and `temperature=0.0`; inline image
  parts via `inline_data`; exponential backoff retry on 429 and 5xx errors
- Perception JSON schema covering `extracted_claim`, `image_assessments`
  (one entry per image), and `perception_summary`
- Prompt injection detection: system prompt instructs Gemini to flag written
  instructions found in images and never follow them

The participant reviewed the prompt, tested it on sample claims, and confirmed
the output schema matched the `GeminiPerception` Pydantic model.

---

### Session 4 — Rule Engine Design

Claude implemented the deterministic decision matrix after the participant
explicitly required that no LLM should make claim status or severity decisions.

**Key outputs from this session:**
- `rule_engine.py`: five-step deterministic decision matrix
  - Step 1: `valid_image` — any valid image in the set
  - Step 2: `evidence_standard_met` — claimed part visible in at least one image
  - Step 3: `claim_status` — supported / contradicted / not_enough_information
    based on `issue_matches_claim` and `part_matches_claim` from perception
  - Step 4: `issue_type` and `object_part` — from extracted claim with
    visible fallback
  - Step 5: `severity` — mapped from visible issue type via fixed priority table
- `risk_aggregator.py`: merges per-image quality flags, structural flags
  (wrong_object, text_instruction_present), claim-level injection flag, and
  user history flags into a canonically ordered semicolon string

The participant verified the decision matrix against sample_claims.csv expected
outputs and confirmed the severity mapping matched observed ground-truth values.

---

### Session 5 — Pipeline Implementation

Claude wired all services into a complete end-to-end pipeline.

**Key outputs from this session:**
- `output_writer.py`: writes `ClaimResult` list to CSV using `OUTPUT_COLUMNS`
  order from config; `csv.QUOTE_ALL`; booleans as lowercase strings
- `main.py`: sequential claim processor with structured logging, per-claim
  progress output, error isolation (failed claims logged and skipped without
  stopping the run), and a final summary of total / succeeded / failed counts
- `evaluation/metrics.py`: `accuracy()`, `jaccard_similarity()`,
  `field_accuracy()`, `generate_summary()`, `compare_summaries()`
- `evaluation/main.py`: runs Strategy A and Strategy B on sample claims,
  prints comparison table, saves winning strategy predictions

The participant ran the pipeline on sample claims, reviewed log output, and
identified edge cases in the rule engine that were corrected before the
production run.

---

### Session 6 — Cache and Resume System

The participant requested a checkpoint and cache system after experiencing API
quota interruptions during development runs. Claude designed and implemented
the system to the participant's specification.

**Key outputs from this session:**
- `cache_manager.py`: `CacheManager` class with per-claim JSON file storage
  and a `checkpoint.json` file tracking completed claim IDs
- `claim_id()` function: stable, filesystem-safe identifier derived from
  `user_id + image_paths`
- Cache structure: `.cache/claims/<claim_id>.json` storing serialised
  `GeminiPerception` and `ClaimResult`
- Checkpoint written immediately after each successful claim — not at end of run
- On resume: completed claims loaded from cache with zero Gemini API calls
- Separate cache namespaces for production and each evaluation strategy
- `config.py` updated with `ENABLE_CACHE`, `CACHE_DIR`, `CHECKPOINT_FILE`
  all configurable via environment variables
- `main.py` updated to be cache-aware throughout the processing loop

The participant tested the resume behaviour by interrupting a run mid-way and
confirming that the next run correctly skipped completed claims.

---

### Session 7 — Documentation and Submission

Claude generated all documentation files based on the completed implementation.

**Key outputs from this session:**
- `README.md`: project overview, architecture diagram, setup instructions,
  pipeline usage, evaluation instructions, output schema, technical decisions,
  known limitations, hackathon notes
- `STATUS.md`: phase progress table, completed modules list, cache and
  checkpoint architecture diagrams, configuration reference, submission checklist
- `code/evaluation/evaluation_report.md`: operational analysis with actual
  production run figures (44 claims, 8 Gemini calls, 36 cache hits), cost
  estimates, runtime estimates, TPM/RPM considerations, failure modes,
  final recommendation

The participant reviewed all documentation for accuracy, corrected references
to claim counts and operational figures, and confirmed the files were
ready for submission.

---

## Major Human Decisions

| Decision | Rationale |
|---|---|
| Chose Gemini 2.5 Flash | Free-tier availability within hackathon quota constraints |
| Separated perception from business logic | Makes claim decisions auditable, testable, and independent of model behaviour |
| Added checkpoint/resume system | Required after API quota interruptions during development runs |
| Added local cache system | Prevents duplicate API calls on re-runs; reduces cost and latency |
| Handled quota constraints via incremental execution | Pipeline designed to stop and resume cleanly rather than fail entirely |
| Kept processing sequential (no concurrency) | Simpler error handling and rate-limit compliance within free-tier RPM limits |
| Used `csv.QUOTE_ALL` on output | Prevents parsing errors from embedded commas and semicolons in conversation text |
| Reviewed all generated code before integration | Participant validated logic, corrected edge cases, and tested on sample data |

---

## AI Usage Disclosure

Claude was used for:
- Architecture ideation and service design
- Boilerplate and implementation code generation
- Prompt engineering and JSON schema design
- Documentation generation (README, STATUS.md, evaluation report)

The following were performed entirely by the participant:
- Final technology and architecture decisions
- Code review and validation of all generated output
- Debugging and edge-case correction
- End-to-end pipeline testing on sample and test data
- API quota management and incremental execution strategy
- Cache and checkpoint system specification and testing
- Output validation (schema, column order, boolean format)
- Submission preparation and packaging

All code generated by Claude was read, understood, and approved by the
participant before integration. No generated code was submitted without review.

---

## Final Outcome

| Metric | Value |
|---|---|
| Total claims processed | 44 |
| Succeeded | 44 |
| Failed | 0 |
| Cache hits (final run) | 36 |
| Gemini API calls (final run) | 8 |
| Output file | `output.csv` — 44 rows, 14 columns |
| Cache system | Operational |
| Checkpoint / resume system | Operational |
| Prompt injection detection | Implemented |
| Multi-image processing | Implemented |
| Deterministic rule engine | Implemented |

The system produced `output.csv` for all 44 test claims with zero failures
in the final production run.