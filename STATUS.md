# STATUS.md

## Project Status

**Project:** HackerRank Orchestrate — Multi-Modal Evidence Review

**Current Status:** ✅ Feature Complete

**Last Updated:** June 2026

---

# Architecture Summary

```text
claims.csv
user_history.csv
evidence_requirements.csv
        │
        ▼
   csv_loader
        │
        ▼
Pydantic Models
(Claim, UserHistory, EvidenceRequirement)
        │
        ▼
   image_loader
        │
        ▼
EncodedImage List
(Base64 Images)
        │
        ▼
  prompt_builder
(system + user prompt)
        │
        ▼
┌────────────────────────────────────┐
│ cache_manager.is_completed()?      │
└─────────────┬───────────────┬──────┘
              │               │
            YES              NO
              │               │
              ▼               ▼
       cache_manager      gemini_client
          .load()       (1 Gemini Call)
              │               │
              │       GeminiPerception
              │               │
              │               ▼
              │    risk_aggregator
              │           +
              │      rule_engine
              │               │
              │               ▼
              │   cache_manager.save()
              │
              └───────┬───────┘
                      │
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

# Cache Architecture

```text
.cache/
│
├── checkpoint.json
│
└── claims/
    ├── claim_001.json
    ├── claim_002.json
    └── ...
```

## Purpose

The cache system prevents duplicate Gemini API calls and allows interrupted runs to resume safely.

---

## Per-Claim Cache File

```json
{
  "claim_id": "user_002__images-test-case_001-img_1_img_2_img_3",
  "perception": {},
  "result": {}
}
```

### Contents

| Field      | Description                 |
| ---------- | --------------------------- |
| claim_id   | Unique claim identifier     |
| perception | Serialized GeminiPerception |
| result     | Serialized ClaimResult      |

---

## Checkpoint File

```json
{
  "completed": [
    "user_002__images-test-case_001-img_1_img_2_img_3",
    "user_005__images-test-case_003-img_1"
  ]
}
```

### Purpose

Stores all successfully processed claim IDs.

Used for:

* Crash recovery
* Resume support
* Quota recovery
* Incremental execution

---

## Claim ID Generation

Format:

```text
<user_id>__<image_paths>
```

Filesystem-unsafe characters:

```text
/
\
:
;
```

are automatically converted into safe separators.

Example:

```text
user_002__images-test-case_001-img_1_img_2_img_3
```

---

# Checkpoint Architecture

### Write Behavior

Checkpoint is updated immediately after every successful claim.

```text
Claim Processed
      │
      ▼
Write Cache File
      │
      ▼
Update checkpoint.json
      │
      ▼
Continue
```

---

### Crash Recovery

If the pipeline crashes:

```text
Claims 1–20 → Completed
Claim 21    → Failed
```

The first 20 claims remain persisted.

On restart:

```text
Load checkpoint
      │
      ▼
Skip completed claims
      │
      ▼
Continue from claim 21
```

No re-processing required.

---

# Resume Workflow Example

## Run 1

```text
Claims 1–20  → Success
Claim 21     → Gemini quota exceeded
Pipeline     → Stops
```

Checkpoint contains:

```text
Claims 1–20
```

---

## Run 2

After quota reset:

```text
Load checkpoint
```

Result:

```text
Claims 1–20  → Cache Hit
Claims 21–46 → Gemini Call
```

Final:

```text
output.csv
```

contains all 46 claims.

---

# Evaluation Cache Architecture

Each evaluation strategy uses its own isolated cache.

```text
.cache/
│
├── checkpoint.json
├── claims/
│
├── eval_strategy_a/
│   ├── checkpoint.json
│   └── claims/
│
└── eval_strategy_b/
    ├── checkpoint.json
    └── claims/
```

Benefits:

* No cache contamination
* Fair strategy comparison
* Reproducible evaluation

---

# Configuration

| Variable        | Default                | Description              |
| --------------- | ---------------------- | ------------------------ |
| ENABLE_CACHE    | true                   | Enable / disable caching |
| CACHE_DIR       | .cache/                | Cache directory          |
| CHECKPOINT_FILE | .cache/checkpoint.json | Checkpoint path          |

Configuration sources:

1. Environment Variables
2. `.env`
3. Application Defaults

---

# Completed Modules

| File                 | Purpose                           |
| -------------------- | --------------------------------- |
| models.py            | Pydantic domain models            |
| config.py            | Paths, constants, cache config    |
| csv_loader.py        | CSV ingestion                     |
| image_loader.py      | Base64 encoding and image loading |
| prompt_builder.py    | Gemini prompt generation          |
| gemini_client.py     | Gemini API integration            |
| risk_aggregator.py   | Risk flag generation              |
| rule_engine.py       | Deterministic business logic      |
| cache_manager.py     | Cache and checkpoint management   |
| output_writer.py     | CSV export                        |
| main.py              | Main processing pipeline          |
| metrics.py           | Evaluation metrics                |
| evaluation/main.py   | Strategy evaluation               |
| evaluation_report.md | Evaluation reporting              |
| README.md            | Documentation                     |
| requirements.txt     | Python dependencies               |
| .env.example         | Environment template              |

---

# Progress

| Phase | Description               | Status     |
| ----- | ------------------------- | ---------- |
| 1     | Foundation Layer          | ✅ Complete |
| 2     | Gemini Integration        | ✅ Complete |
| 3     | Rule Engine               | ✅ Complete |
| 4     | Pipeline Integration      | ✅ Complete |
| 5     | Evaluation Framework      | ✅ Complete |
| 6     | Cache & Checkpoint System | ✅ Complete |

---

# Submission Checklist

## Evaluation

* [ ] Run evaluation

```bash
python code/evaluation/main.py
```

* [ ] Fill evaluation report with actual metrics

```text
code/evaluation/evaluation_report.md
```

---

## Production Run

* [ ] Run pipeline

```bash
python code/main.py
```

* [ ] Verify output contains:

  * 46 rows
  * 14 columns
  * Correct ordering

* [ ] Validate boolean fields:

  * `true`
  * `false`

---

## Submission Package

* [ ] Prepare `code.zip`
* [ ] Include source code
* [ ] Include `output.csv`
* [ ] Export AI transcript

```text
$HOME/hackerrank_orchestrate/log.txt
```

---

## Final Submission

Submit:

```text
code.zip
output.csv
log.txt
```

on the HackerRank Community Platform.

---

# AI Judge Interview Preparation

Be prepared to explain:

* System architecture
* Gemini integration
* Rule engine design
* Cache strategy
* Checkpoint recovery
* Risk detection logic
* Tradeoffs and limitations

Status: ✅ Ready for Final Evaluation and Submission
