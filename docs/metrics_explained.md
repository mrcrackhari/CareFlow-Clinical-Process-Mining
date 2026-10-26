# Clinical Process Mining Metrics Explained

> **Synthetic Data Disclaimer:** All patient records, timestamps, staff resources, shifts, and analytical findings in the CareFlow Clinical Process Mining project are **100% computer-generated (synthetic/simulated)**. No real patient data or Protected Health Information (PHI) is used anywhere in this repository. All metrics and bottleneck rankings reflect simulated hospital workflows designed for process-mining demonstration and evaluation.

---

## 1. Overview for Non-Technical Readers

CareFlow tracks each simulated patient journey from **Registration** to **Discharge** as a sequence of time-stamped clinical events (`data/event_log.csv`). Our analysis pipeline turns those raw timestamps into six structured tables in `outputs/` that answer four core hospital operations questions:

1. **Where do patients wait the longest?** (*Bottleneck Identification* — `outputs/bottleneck_metrics.csv`)
2. **Which clinical routes do patients actually take?** (*Process Discovery* — `outputs/process_paths.csv` and `outputs/process_map_edges.csv`)
3. **How often do patients repeat a step or loop back to an earlier stage?** (*Rework Analysis* — `outputs/repeat_loop_metrics.csv`)
4. **How closely do actual journeys match the hospital's ideal 6-step protocol?** (*Conformance Checking* — `outputs/conformance_summary.csv`)

---

## 2. Core Metric Definitions & Formulas

Every calculation follows the team's agreed methodology rules (`R1`–`R12` in `docs/analysis_methodology.md`).

### 2.1 Transition Time ("Wait Time") — Rules R3, R4, R5, R6
* **What it measures:** The elapsed time in minutes between two consecutive activities within the same patient case:
  $$\text{Transition Time (min)} = \frac{t_{\text{current}} - t_{\text{previous}}}{60}$$
* **Why we call it Transition Time (R6):** Because the event log records a single timestamp per activity, the time gap between two consecutive events includes both **queue/waiting time** and **the service time of the activity itself**.
* **First Event Handling (R4):** A patient's first event (`Registration`) has no preceding step. Its transition time is left **empty (`NaN`), never `0`**, so it never artificially lowers any wait-time average.
* **Pairwise Attribution (R5):** Transition times are always grouped by the directed pair $(\text{from\_activity} \rightarrow \text{to\_activity})$, never by a single destination activity alone, because arriving at `Doctor Consultation` after `Triage` represents a different clinical handoff than arriving from another stage.

### 2.2 Bottleneck Ranking Metrics — Rule R5
For every $(\text{from\_activity} \rightarrow \text{to\_activity})$ transition pair in `outputs/bottleneck_metrics.csv`:
* **`count`:** Total number of times this handoff occurred across all included cases.
* **`avg_minutes`:** Arithmetic mean of transition times for the pair (rounded to 2 decimal places).
* **`median_minutes`:** Middle value (50th percentile) of transition times—useful for checking whether extreme outliers skew the average.
* **`max_minutes`:** Longest single wait recorded for that transition pair.
* **`rank`:** Competition rank (`1` = longest `avg_minutes`, i.e., the primary bottleneck). Equal averages share the same rank.

### 2.3 Case Duration (Throughput Time) — Rule R7
* **What it measures:** The total end-to-end time a patient spends in the hospital from initial `Registration` to final `Discharge`:
  $$\text{Case Duration (min)} = t_{\text{Discharge}} - t_{\text{Registration}} = \sum_{i=2}^{n} \text{Transition Time}_i$$
* **Included Cases Only (R8):** Only complete cases that start with `Registration` and end with `Discharge` (after chronological sorting by `R1`) are included in throughput and bottleneck metrics.

### 2.4 Rework Metrics: Repeats vs. Loop-Backs — Rules R10, R11, R12
Repeat and loop-back definitions are mutually exclusive (an event is never counted as both):
* **Immediate Repeat (`R10`):** An activity is followed immediately by the **exact same activity** within the same case (e.g., `X-Ray -> X-Ray`).
* **Loop-Back (`R11`):** A patient returns to an activity that already occurred **earlier** in their visit, separated by at least one different step (e.g., `Triage -> Doctor Consultation -> X-Ray -> Triage`).
* **Hospital Rework Rate (`R12`):** The percentage of complete patient cases that experience **at least one loop-back**:
  $$\text{Rework Rate (\%)} = \left( \frac{\text{Cases with } \ge 1 \text{ Loop-Back}}{\text{Total Complete Cases}} \right) \times 100$$

### 2.5 Conformance Checking Metrics — Section 4 of Methodology
Actual patient trajectories are compared against the 6-step reference pathway (`IDEAL_PATH` in `src/common/schema.py`):
$$\text{Registration} \rightarrow \text{Triage} \rightarrow \text{Doctor Consultation} \rightarrow \text{X-Ray} \rightarrow \text{Doctor Review} \rightarrow \text{Discharge}$$
* **`is_conformant`:** `True` only if the patient's chronological sequence matches `IDEAL_PATH` step-for-step with no skipped activities, out-of-order steps, repeats, or loop-backs.
* **`deviation_type`:** Explains why a non-conformant pathway deviated (`skipped_steps`, `out_of_order`, `extra_steps`, `repeat`, `loop_back`, or combinations joined with `+`).
* **`skipped_steps` & `skipped_count`:** Lists any activities from `IDEAL_PATH` absent from the case (writes `(none)` when no steps were skipped so spreadsheet/dashboard readers do not misread the text as a missing null value).

---

## 3. Guide to Generated Output Files (`outputs/`)

All files in `outputs/` are automatically generated by running the scripts in `src/analysis/` and are read directly by the dashboard (`src/dashboard/app.py`).

| Output File | Generated By | Granularity | Key Columns & Purpose |
| :--- | :--- | :--- | :--- |
| `outputs/event_transitions.csv` | `src/analysis/calculate_metrics.py` | 1 row per event (`2,741` rows across `500` cases) | `case_id`, `activity`, `timestamp`, `resource`, `shift`, `previous_activity`, `transition_time_minutes`. Base enriched log used by all downstream scripts. |
| `outputs/bottleneck_metrics.csv` | `src/analysis/find_bottlenecks.py` | 1 row per activity pair (`9` pairs, `2,241` transitions) | `from_activity`, `to_activity`, `count`, `avg_minutes`, `median_minutes`, `max_minutes`, `rank`. Powers the dashboard wait-time & bottleneck view. |
| `outputs/process_paths.csv` | `src/analysis/discover_process.py` | 1 row per unique pathway | `rank`, `path`, `case_count`, `pct_cases`, `step_count`, `avg_duration_minutes`, `median_duration_minutes`, `has_repeat`, `has_loopback`. Shows most common patient journeys. |
| `outputs/repeat_loop_metrics.csv` | `src/analysis/discover_process.py` | 1 row per rework transition pair | `from_activity`, `to_activity`, `rework_type`, `transition_count`, `cases_affected`, `pct_cases_affected`, `avg_minutes`, `median_minutes`, `max_minutes`. Quantifies clinical rework bottlenecks. |
| `outputs/process_map_edges.csv` | `src/analysis/discover_process.py` | 1 row per directed graph edge (`9` edges) | Adds `case_count`, `pct_cases`, `is_ideal_edge`, `edge_type` (`ideal`, `repeat`, `loop_back`, `deviation`), and `loopback_count` for drawing the process map. |
| `outputs/conformance_summary.csv` | `src/analysis/check_conformance.py` | 1 row per unique pathway | Compares actual pathways against `IDEAL_PATH` with `is_conformant`, `deviation_type`, `skipped_steps`, `skipped_count`, and throughput durations. |

---

## 4. Key Simulated Findings (500-Case Synthetic Dataset)

Across the **500 synthetic patient cases (`2,741` events, `2,241` transitions)**:
* **Data Completeness:** `100%` of cases (`500/500`) start with `Registration` and end with `Discharge` with zero missing values or invalid timestamps.
* **Primary Bottlenecks (`outputs/bottleneck_metrics.csv`):**
  1. **Rank 1 (`Doctor Consultation -> X-Ray`):** `28.15 min` average (`28.0 min` median, `45.0 min` max across `275` transitions).
  2. **Rank 2 (`Doctor Review -> Discharge`):** `28.10 min` average (`27.5 min` median, `45.0 min` max across `212` transitions).
  3. **Rank 3 (`Triage -> Doctor Consultation`):** `27.97 min` average (`28.0 min` median, `45.0 min` max across `627` transitions).
* **Loop-Back & Rework Impact:** `X-Ray -> Triage` occurs `127` times (averaging `27.45 min`), triggering a second `Triage -> Doctor Consultation` pass (`627` total consultations for `500` patients) and adding substantial extra wait time compared to non-rework journeys.
* **Synthetic Interpretation Note:** Because transition durations in the baseline generator are drawn from bounded synthetic distributions (up to `45.0` minutes per step), average transition times cluster tightly between `26.00` and `28.15` minutes. Total case duration differences are therefore driven primarily by **step count and rework loops** rather than single-step outliers.