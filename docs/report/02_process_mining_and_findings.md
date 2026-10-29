# Section 2: Clinical Process Mining Analysis and Operational Findings

> **Synthetic Data Disclaimer:** All patient records, timestamps, staff resources, shifts, and clinical pathways analyzed in this section are **100% computer-generated (simulated)**. No Protected Health Information (PHI) or real hospital data was used. All findings represent analytical discoveries on simulated clinical event logs for process mining demonstration.

---

## 1. Executive Summary

Using the CareFlow analytical pipeline, we extracted, chronologically sorted, and mined 2,741 clinical events across 500 patient cases (`outputs/event_transitions.csv`). The analysis investigated process bottlenecks, pathway variations, rework loops, and protocol conformance against the hospital's agreed 6-step clinical protocol (`IDEAL_PATH` in `src/common/schema.py`):

Registration -> Triage -> Doctor Consultation -> X-Ray -> Doctor Review -> Discharge

### Core Operational Key Performance Indicators (KPIs)

| Metric | Measured Value | Clinical Interpretation |
| :--- | :--- | :--- |
| **Total Analyzed Patient Cohort** | 500 cases (2,741 events, 2,241 transitions) | 100% complete trajectories running from `Registration` to `Discharge` (Rule R8). |
| **Overall Mean Throughput (R7)** | 123.91 minutes (~2.07 hours) | Average total time a patient spends in the hospital system from entry to discharge. |
| **Primary Process Bottleneck (R5)** | `Doctor Consultation -> X-Ray` (28.15 min avg, 45.0 min max) | Longest average handoff queue in the workflow across 275 transitions. |
| **Hospital Rework Rate (R12)** | 22.40% (112 of 500 cases) | Nearly 1 in 4 patients requires a loop-back to an earlier stage (`X-Ray -> Triage`). |
| **Protocol Conformance Rate** | 13.00% (65 of 500 cases) | 65 patients followed the exact 6-step sequence without skipped steps or rework. |
| **Rework Delay Impact** | +89.15 minutes (+90.2% longer duration) | Patients experiencing rework averaged 188.03 min vs. 98.88 min for non-rework deviations. |

---

## 2. Analysis Methodology and Governance (Rules R1–R12)

All calculations were executed in Python/Pandas (`src/analysis/`) and verified against 16 automated unit and integration tests (`tests/test_metrics.py`):

1. **Chronological Sorting (R1):** Events are sorted by `case_id`, then `timestamp` (stable sort preserves recorded order on identical timestamps).
2. **Case Boundary Isolation (R2):** Transition times are never computed across different `case_id` values.
3. **Pairwise Transition Math (R3 & R5):** Transition time is the minute difference (`t_current - t_previous`) attributed to the directed pair (`from_activity -> to_activity`).
4. **First-Event NaN Exclusion (R4):** First events (`Registration`) have no preceding step and remain `NaN` (empty, never `0`) so averages are never skewed downward.
5. **Throughput Duration (R7):** Total case duration equals `t_Discharge - t_Registration`, matching the sum of transition times within each case.
6. **Data Contract Integrity (R8 & R9):** Incomplete cases (not starting with `Registration` and ending with `Discharge`) or rows with missing values/invalid timestamps are filtered out.
7. **Mutually Exclusive Rework Tagging (R10 & R11):**
   * *Repeat (R10):* An immediate consecutive repeat of the same activity (e.g., `X-Ray -> X-Ray`).
   * *Loop-Back (R11):* A return to an activity that occurred earlier in the case, separated by at least one other step (e.g., `Triage -> Doctor Consultation -> X-Ray -> Triage`).

---

## 3. Hospital Bottleneck Identification (`outputs/bottleneck_metrics.csv`)

Across 2,241 transitions, 9 distinct activity handoff pairs were identified and ranked by longest average wait time (`src/analysis/find_bottlenecks.py`):

| Rank | From Activity | To Activity | Count | Avg (min) | Median (min) | Max (min) | Operational Role |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | Doctor Consultation | X-Ray | 275 | **28.15** | 28.0 | 45.0 | **Primary Diagnostic Bottleneck** |
| **2** | Doctor Review | Discharge | 212 | **28.10** | 27.5 | 45.0 | Administrative / Discharge Delay |
| **3** | Triage | Doctor Consultation | 627 | **27.97** | 28.0 | 45.0 | Clinical Consultation Queue |
| **4** | Registration | Triage | 500 | **27.63** | 27.5 | 45.0 | Initial Triage Handoff |
| **5** | X-Ray | Triage | 127 | **27.45** | 26.0 | 45.0 | Clinical Rework Loop-Back |
| **6** | Doctor Consultation | Discharge | 205 | **27.09** | 27.0 | 45.0 | Direct Outpatient Discharge |
| **7** | Doctor Consultation | Doctor Review | 147 | **26.99** | 28.0 | 45.0 | Secondary Internal Review |
| **8** | X-Ray | Discharge | 83 | **26.58** | 25.0 | 45.0 | Post-Radiology Discharge |
| **9** | X-Ray | Doctor Review | 65 | **26.00** | 26.0 | 45.0 | Standard Diagnostic Review |

### Key Bottleneck Findings
* **Diagnostic Delay:** `Doctor Consultation -> X-Ray` is the single longest average handoff at **28.15 minutes** (median 28.0 min, max 45.0 min).
* **Discharge Clearance Delay:** `Doctor Review -> Discharge` ranks second at **28.10 minutes**, reflecting administrative and bed-clearance wait times after clinical sign-off.
* **Consultation Queue Volume:** `Triage -> Doctor Consultation` is the highest-volume transition (`627` occurrences across `500` cases, averaging **27.97 minutes**) due to second-pass consultations from rework loops.

---

## 4. Process Discovery & Directed Process Map (`outputs/process_map_edges.csv`)

Process discovery (`src/analysis/discover_process.py`) mapped the hospital workflow across **9 directed edges**:

| Edge Type | Directed Handoff (`from_activity -> to_activity`) | Transition Count | Cases Affected (%) | Avg Wait (min) |
| :--- | :--- | :---: | :---: | :---: |
| **Ideal** | `Registration -> Triage` | 500 | 500 (100.0%) | 27.63 |
| **Ideal** | `Triage -> Doctor Consultation` | 627 | 500 (100.0%) | 27.97 |
| **Ideal** | `Doctor Consultation -> X-Ray` | 275 | 275 (55.0%) | 28.15 |
| **Ideal** | `Doctor Review -> Discharge` | 212 | 212 (42.4%) | 28.10 |
| **Deviation** | `Doctor Consultation -> Discharge` | 205 | 205 (41.0%) | 27.09 |
| **Deviation** | `Doctor Consultation -> Doctor Review` | 147 | 147 (29.4%) | 26.99 |
| **Loop-Back** | `X-Ray -> Triage` | 127 | 112 (22.4%) | 27.45 |
| **Deviation** | `X-Ray -> Discharge` | 83 | 83 (16.6%) | 26.58 |
| **Ideal** | `X-Ray -> Doctor Review` | 65 | 65 (13.0%) | 26.00 |

---

## 5. Rework Analysis: Repeats vs. Loop-Backs (`outputs/repeat_loop_metrics.csv`)

* **Hospital Rework Rate (R12):** **22.40%** (`112` of `500` cases experienced at least one loop-back).
* **Immediate Repeats (R10):** **0 cases** (`0` back-to-back repeated activities).
* **Loop-Back Transitions (R11):** **127 transitions** on `X-Ray -> Triage` across `112` patients (averaging `27.45` minutes per loop-back), which then forced a second `Triage -> Doctor Consultation` wait (`27.97` minutes avg).

---

## 6. Conformance Checking: Actual vs. Ideal Path (`outputs/conformance_summary.csv`)

Evaluating all 500 cases against the 6-step `IDEAL_PATH` (`src/analysis/check_conformance.py`) partitions the patient population into three operational cohorts:

| Patient Cohort | Case Count | % of Cohort | Mean Duration (min) | Operational Finding |
| :--- | :---: | :---: | :---: | :--- |
| **Conformant (`IDEAL_PATH`)** | 65 | 13.00% | 137.85 | Completed all 6 clinical stages in exact protocol order without rework. |
| **Non-Conformant (Without Rework)** | 323 | 64.60% | 98.88 | Fast-track pathways that skipped optional imaging/review steps (**38.97 min faster** than ideal path). |
| **Non-Conformant (With Rework)** | 112 | 22.40% | 188.03 | Experienced `X-Ray -> Triage` loop-backs (**+50.18 min longer** than ideal path; **+89.15 min longer** than non-rework deviations). |
| **Total / Overall** | **500** | **100.00%** | **123.91** | Overall throughput is heavily pulled upward by the 22.40% rework cohort. |

---

## 7. Actionable Operational Recommendations (Simulated Workflow)

1. **Eliminate Post-X-Ray Triage Re-Entry (`X-Ray -> Triage`):** Route patients completing radiology directly to `Doctor Review` or `Doctor Consultation` instead of sending them back through `Triage`. Removing the extra `X-Ray -> Triage -> Doctor Consultation` loop saves **~55.42 minutes** per affected patient across `22.40%` of hospital volume.
2. **Buffer Radiology Intake (`Doctor Consultation -> X-Ray`):** Target the Rank 1 bottleneck (**28.15 min** average wait) by staggering imaging orders and prioritizing patients waiting >28 minutes.
3. **Streamline Discharge Sign-Off (`Doctor Review -> Discharge`):** Reduce the Rank 2 bottleneck (**28.10 min** average wait) by preparing discharge summaries digitally during `Doctor Review`.

---

## 8. Team Contribution & Task-Per-Member Summary

All development followed strict branch isolation (`member1-data`, `member2-analysis`, `member3-dashboard`) with zero premature merges to `main`, sharing contract files via `git checkout <branch> -- <path>`:

| Team Member & Branch | Role | Owned Files & Key Deliverables |
| :--- | :--- | :--- |
| **Member 1**<br>(`member1-data`) | Data Engineering | • `src/data/generate_events.py` & `src/data/validate_events.py`<br>• `data/sample_event_log.csv`, `data/event_log.csv` (500 cases, 2,741 events), & `data/README.md`<br>• `tests/test_data_validation.py` (10/10 validation checks passed)<br>• `docs/report/01_data_and_quality.md` |
| **Member 2 (Parth)**<br>(`member2-analysis`) | Process Mining & Analysis | • `src/common/schema.py` (Shared Data Contract) & `.gitignore`<br>• `docs/team_charter.md`, `docs/analysis_methodology.md` (Rules R1–R12), & `docs/metrics_explained.md`<br>• `src/analysis/calculate_metrics.py` -> `outputs/event_transitions.csv`<br>• `src/analysis/find_bottlenecks.py` -> `outputs/bottleneck_metrics.csv`<br>• `src/analysis/discover_process.py` -> `outputs/process_paths.csv`, `outputs/repeat_loop_metrics.csv`, `outputs/process_map_edges.csv`<br>• `src/analysis/check_conformance.py` -> `outputs/conformance_summary.csv`<br>• `tests/test_metrics.py` (16/16 unit & integration tests passing)<br>• `docs/report/02_process_mining_and_findings.md` |
| **Member 3**<br>(`member3-dashboard`) | Dashboard & Visualization | • `src/dashboard/app.py` (Interactive Streamlit process mining dashboard)<br>• KPI cards, bottleneck wait-time charts, directed process map graph, rework view, and actual-vs-ideal conformance view<br>• `docs/report/03_dashboard.md` |