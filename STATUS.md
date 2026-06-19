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

## Architecture Summary