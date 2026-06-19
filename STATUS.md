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

# Key Design Decisions

* Gemini performs perception only:

  * claim extraction
  * visible damage detection
  * object part detection
  * image quality assessment
  * supporting image identification
  * prompt injection detection

* Rule Engine performs all business decisions:

  * valid_image
  * evidence_standard_met
  * claim_status
  * severity
  * issue_type
  * object_part

* One Gemini call per claim.

* Images sent as inline image parts.

* JSON-only responses enforced.

* `temperature=0.0` for deterministic outputs.

* Exponential backoff for transient API failures.

* Failed claims are logged and skipped without stopping the pipeline.

* Output uses `csv.QUOTE_ALL` for maximum compatibility.

* No LangChain, database, queues, or unnecessary frameworks.

---

# Completed Modules

| File                             | Status | Purpose                                    |
| -------------------------------- | ------ | ------------------------------------------ |
| code/models.py                   | ✅      | Pydantic models and enums                  |
| code/config.py                   | ✅      | Configuration, constants, output schema    |
| code/services/csv_loader.py      | ✅      | CSV loading and parsing                    |
| code/services/image_loader.py    | ✅      | Image encoding and metadata extraction     |
| code/services/gemini_client.py   | ✅      | Gemini API integration and JSON validation |
| code/services/prompt_builder.py  | ✅      | Prompt generation                          |
| code/services/risk_aggregator.py | ✅      | Risk flag aggregation                      |
| code/services/rule_engine.py     | ✅      | Deterministic decision engine              |
| code/services/output_writer.py   | ✅      | Output CSV generation                      |
| code/main.py                     | ✅      | End-to-end processing pipeline             |
| requirements.txt                 | ✅      | Project dependencies                       |
| .env.example                     | ✅      | Environment variable template              |
| .gitignore                       | ✅      | Git exclusions                             |

---

# Pending Modules

| File                                 | Priority | Purpose                       |
| ------------------------------------ | -------- | ----------------------------- |
| code/evaluation/main.py              | High     | Evaluation workflow           |
| code/evaluation/metrics.py           | High     | Metrics calculation           |
| code/evaluation/evaluation_report.md | Medium   | Evaluation findings           |
| README.md                            | Medium   | Setup and usage documentation |

---

# Progress

| Phase   | Description                          | Status        |
| ------- | ------------------------------------ | ------------- |
| Phase 1 | Foundation (Models, Config, Loaders) | ✅ Complete    |
| Phase 2 | Gemini Integration                   | ✅ Complete    |
| Phase 3 | Rule Engine & Risk Aggregation       | ✅ Complete    |
| Phase 4 | Pipeline & Output Generation         | ✅ Complete    |
| Phase 5 | Evaluation & Documentation           | ⏳ In Progress |

---

# Next Phase — Evaluation Framework

## metrics.py

Responsibilities:

* Exact-match accuracy calculation
* Jaccard similarity for risk flags
* Per-field accuracy reporting
* Aggregate evaluation summary

Metrics:

* claim_status accuracy
* evidence_standard_met accuracy
* valid_image accuracy
* severity accuracy
* issue_type accuracy
* object_part accuracy
* risk_flags Jaccard similarity

---

## evaluation/main.py

Responsibilities:

* Load sample_claims.csv
* Run Strategy A
* Run Strategy B
* Compare metrics
* Generate evaluation summary
* Select best-performing strategy

Strategies:

### Strategy A

Current production prompt.

### Strategy B

Refined prompt with stricter output constraints and examples.

---

## evaluation_report.md

Must include:

* Strategy comparison table
* Winning strategy
* Rationale
* Estimated API calls
* Estimated runtime
* Token usage estimate
* Cost estimate
* Retry/backoff behavior
* Operational considerations

---

## README.md

Must include:

* Project overview
* Architecture summary
* Installation steps
* Environment setup
* Running the pipeline
* Running evaluation
* Output format
* Repository structure

---

# Technical Notes

* Current implementation uses `google-generativeai`.
* SDK is deprecated but fully functional.
* Migration to `google.genai` can be performed after hackathon completion.
* Priority is correctness, reproducibility, and submission reliability.

---

# Current Completion Estimate

Core System: 90% Complete ✅

Remaining Work:

* Evaluation Framework
* Metrics
* Evaluation Report
* README
* Final Submission Validation

Estimated Remaining Effort:
~1 development phase

```
```

