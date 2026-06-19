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


---

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

# Key Design Decisions

* Gemini performs perception only.
* Business decisions are deterministic and handled by Python.
* Single Gemini call per claim.
* Images are sent using inline image parts.
* JSON-only responses enforced.
* Temperature set to `0.0` for deterministic outputs.
* Retry and exponential backoff implemented.
* Prompt injection detection handled in perception layer.
* Risk aggregation handled separately from claim decisions.
* Architecture intentionally avoids LangChain, databases, queues, and unnecessary frameworks.

---

# Completed Modules

| File                             | Status | Purpose                                |
| -------------------------------- | ------ | -------------------------------------- |
| code/models.py                   | ✅      | Pydantic models and enums              |
| code/config.py                   | ✅      | Constants, paths, model configuration  |
| code/services/csv_loader.py      | ✅      | CSV loading and parsing                |
| code/services/image_loader.py    | ✅      | Image encoding and metadata extraction |
| code/services/gemini_client.py   | ✅      | Gemini API integration                 |
| code/services/prompt_builder.py  | ✅      | Prompt generation                      |
| code/services/risk_aggregator.py | ✅      | Risk flag aggregation                  |
| code/services/rule_engine.py     | ✅      | Deterministic business rules           |
| requirements.txt                 | ✅      | Project dependencies                   |
| .env.example                     | ✅      | Environment template                   |
| .gitignore                       | ✅      | Git exclusions                         |

---

# Pending Modules

| File                                 | Priority | Purpose                       |
| ------------------------------------ | -------- | ----------------------------- |
| code/services/output_writer.py       | High     | Generate output.csv           |
| code/main.py                         | High     | Main processing pipeline      |
| code/evaluation/main.py              | Medium   | Evaluation workflow           |
| code/evaluation/metrics.py           | Medium   | Metrics calculation           |
| code/evaluation/evaluation_report.md | Medium   | Evaluation findings           |
| README.md                            | Medium   | Setup and usage documentation |

---

# Next Phase (Phase 4)

## output_writer.py

Responsibilities:

* Accept `list[ClaimResult]`
* Write `output.csv`
* Preserve exact schema order
* Convert booleans to lowercase:

  * true
  * false
* Use consistent CSV quoting

---

## main.py

Responsibilities:

* Load environment variables
* Load datasets
* Load evidence requirements
* Process claims one-by-one
* Build prompts
* Call Gemini
* Aggregate risks
* Execute rule engine
* Collect ClaimResult objects
* Generate output.csv
* Log progress and errors
* Print final summary

---

# Evaluation Plan

## Strategy A

Single perception prompt.

## Strategy B

Refined perception prompt with stricter output constraints.

Metrics:

* Claim Status Accuracy
* Evidence Standard Accuracy
* Severity Accuracy
* Valid Image Accuracy
* Issue Type Accuracy
* Object Part Accuracy
* Risk Flag Similarity (Jaccard)

Final submission strategy will be selected based on evaluation results.

---

# Technical Notes

* Current implementation uses `google-generativeai`.
* SDK is deprecated but remains functional.
* Migration to `google.genai` can be performed after hackathon completion.
* Priority is stability and successful submission.

---

# Current Progress

Phase 1 — Foundation ✅

Phase 2 — Gemini Integration ✅

Phase 3 — Rule Engine & Risk Aggregation ✅

Phase 4 — Pipeline & Output Generation ⏳

Phase 5 — Evaluation & Documentation ⏳

---

# Next Claude Task

Generate:

* code/services/output_writer.py
* code/main.py
* Updated STATUS.md

Constraints:

* No command execution
* No script execution
* Return file contents only
* Follow existing architecture

```
```
