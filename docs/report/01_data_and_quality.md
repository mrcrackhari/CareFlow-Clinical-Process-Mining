\# 01. Data \& Quality



\*\*Author:\*\* Member 1 (Data)

\*\*Module:\*\* CareFlow Data Pipeline



\## 1. Data Generation Strategy

We engineered a synthetic EHR (Electronic Health Record) generator (`src/data/generate\_events.py`) to simulate realistic Emergency Room workflows. 

\- \*\*Volume:\*\* 500 unique patient journeys (2,741 total events).

\- \*\*Determinism:\*\* The generation uses a fixed random seed (`42`), ensuring byte-identical reproducibility across all environments. The MD5 hash of the clean log is `f8eb402a9cc4220f9c874a3f05a9602e`.

\- \*\*The Hidden Bottleneck:\*\* Per the project brief, the generator deliberately plants a 40% loop-back rate from X-Ray to Triage to simulate a missing paperwork bottleneck.



\## 2. Validation \& Quality Counts

To ensure data integrity before analysis, we built a 10-check CI-friendly validation suite (`src/data/validate\_events.py`). It validates against the frozen 5-column contract defined in `src/common/schema.py`.



The official quality counts (from `data/quality\_report.csv`) are:



| Check | Rows Checked | Rows Failed | Status |

|-------|--------------|-------------|--------|

| required\_columns\_present | 2741 | 0 | PASS |

| non\_empty\_case\_id | 2741 | 0 | PASS |

| non\_empty\_activity | 2741 | 0 | PASS |

| activity\_in\_valid\_activities | 2741 | 0 | PASS |

| shift\_in\_valid\_shifts | 2741 | 0 | PASS |

| timestamp\_format\_valid | 2741 | 0 | PASS |

| timestamp\_monotonic\_within\_case | 500 | 0 | PASS |

| no\_duplicate\_timestamps\_in\_case | 500 | 0 | PASS |

| non\_empty\_resource | 2741 | 0 | PASS |

| non\_empty\_timestamp | 2741 | 0 | PASS |



\*\*Result:\*\* 100% Pass. 0 failures across 2,741 events.



\## 3. Error Handling Verification

To prove the validation suite actually catches bad data, we created a "dirty" mode in the generator (`--mode dirty`). This injects 7 deliberate defects (e.g., missing IDs, invalid timestamps). 

When running the validator against the dirty file, the system correctly flagged 7/7 failures and exited with a non-zero code.



\## 4. Hand-Check Fixtures

For Member 2 to verify their analysis logic, we provided `tests/fixtures/hand\_checked\_journeys.csv`. This contains 5 specific cases covering every process shape (baseline, loop-back, deep loop-back, ideal path) so manual calculations can be matched against the script outputs.

