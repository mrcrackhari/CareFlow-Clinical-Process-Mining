# CareFlow — Member 1 Data Progress Log (Days 1–20)

**Role:** Member 1 — Data Engineering & Quality
**Branch:** `member1-data`
**Project:** CareFlow Clinical Pathway Process Mining

---

## Week 1: Foundation & Data Generation (Days 1–6)

### Day 1: Data Dictionary & Contract
- Created `data/README.md` to document the synthetic nature of the data, column definitions, and the frozen 5-column contract.
- **Planted Ground Truth:** Documented the required 40% X-Ray → Triage bottleneck that the data generator must produce.

### Day 2: Hand-Crafted Sample Data
- Built `data/sample_event_log.csv`: 10 manually crafted patient journeys that cover every possible process shape (baseline, single loop, double loop).
- This served as the "golden test fixture" for the analysis and dashboard teams.

### Days 3–4: The Synthetic Generator Engine
- Built `src/data/generate_events.py`.
- **Determinism:** Implemented `random.seed(42)` so the generator produces byte-identical output on every run (MD5: `f8eb402a...`).
- **Planted Inefficiency:** Programmed the 40% loop-back logic (X-Ray → Triage) to simulate missing paperwork.
- **CLI Flags:** Added `--mode clean` (for analysis) and `--mode dirty` (injecting 7 deliberate data defects for testing).

### Day 5: Quality Validation Suite
- Built `src/data/validate_events.py`.
- Created 10 strict validation checks (schema columns, non-empty IDs, valid activities, valid timestamps, chronological order).
- Guarantees the clean data passes 10/10, while the dirty data correctly flags 7/7 defects.
- Outputs `data/quality_report.csv`.

### Day 6: Sync 1 & Schema Alignment
- Resolved a mid-project blocker: Member 2's analysis crashed because they were using an older, deprecated CSV schema.
- Synced `src/common/schema.py` across branches, proving the data had 0 defects. Restored full team integration.

---

## Week 2: Testing, Quality, & Mid-Review (Days 7–10)

### Day 7: Hand-Checked Fixtures
- Pre-delivered `tests/fixtures/hand_checked_journeys.csv` to Member 2 (5 cases covering all shapes) so they could manually verify their process-mining metrics.

### Day 8: Data Generation Documentation
- Authored `docs/data_generation.md`, detailing the config settings, journey builder logic, and how to regenerate the data.

### Day 9: Quality Counts & Report Draft
- Generated the official `data/quality_report.csv` (10/10 PASS).
- Drafted the official report section: `docs/report/01_data_and_quality.md`.

### Day 10: Mid-Review Freeze (Sync 2)
- Locked the data module. Verified MD5 hashes to ensure the demo file would not change.
- Added a "Freeze Status" to the report and notified the team that the data foundation was stable for the mid-review.

---

## Week 3: Pytest, Privacy Audits, & Integration (Days 11–14)

### Day 11: Automated Pytest Suite
- Formalized validation by building `tests/test_data_validation.py`.
- **Bug Caught:** The pytest suite actually caught a bug in our dirty-data injection logic. Fixed the generator to guarantee all 7 defects were reliably produced.
- Tests: 3 passed (clean data passes, dirty data fails correctly, schema enforces contract).

### Day 12: Realism & Privacy Audit
- Authored `docs/data_realism_audit.md`.
- Proved 100% compliance with privacy rules (no real patient PHI).
- Documented why the synthetic data is structurally realistic (stochastic wait times, 3 shifts, 12 fictional staff members).

### Day 13: Integration Check
- Fetched M2 and M3's latest code and re-ran the validation suite. The data integrated perfectly with their process-mining algorithms.

### Day 14: Final Report Findings
- Finalized `docs/report/01_data_and_quality.md` with the "Data Findings" section (summarizing the 40% bottleneck) and "Integration Status."

---

## Week 4: Final Polish & Viva Prep (Days 15–20)

### Day 15: Pipeline Orchestrator (Sync 4)
- Merged the latest `main` branch and closed the merge.
- Validated that the data module integrates cleanly with the team's final scripts.

### Day 16: Workload Analytics Support
- Verified the data structure (shifts: Morning/Evening/Night, 12 staff members) provides the exact schema needed for M2's workload analytics.

### Day 17: Viva Preparation
- Created `docs/viva_prep.md` with clear answers for the mentor regarding data architecture, determinism (seed 42), and privacy.

### Day 18: Quality Assurance
- Ran the daily health check. Confirmed 10/10 validator checks passed and 3/3 Pytest tests passed.
- Cleaned up the repository by adding `data/event_log_dirty.csv` to `.gitignore` so auto-generated test files do not dirty the commit history.

### Day 19 & 20: Final Freeze & Handoff
- Updated `docs/report/01_data_and_quality.md` with the Final Project Status.
- Confirmed all Member 1 deliverables (generator, validator, docs, tests, fixtures) are complete and pushed to `member1-data`.
- Ready for the final team merge and live viva demonstration.