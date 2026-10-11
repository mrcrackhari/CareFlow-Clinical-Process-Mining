# Analysis Methodology & Core Questions

## 1. Core Analysis Questions
Our Python analysis scripts must answer the following business questions using the event log data:
* **Process Discovery:** What is the most frequent clinical pathway patients take from Registration to Discharge?
* **Bottleneck Identification:** Which consecutive activities have the longest average transition times (wait times)?
* **Rework Metrics:** How often do patients experience a "loop-back" (e.g., returning to Triage after an X-Ray)?
* **Throughput:** What is the average total time a patient spends in the hospital system?

## 2. Sorting and Calculation Rules
* **Sorting:** All event logs must be sorted first by `case_id` and then chronologically by `timestamp` before any analysis begins.
* **Transition Time:** Calculated as the difference in minutes between the timestamp of the current activity and the timestamp of the immediately preceding activity for the same `case_id`.
* **Rework Definitions:**
  * **Repeat:** An activity occurs more than once consecutively (e.g., X-Ray -> X-Ray).
  * **Loop-back:** A transition to an activity that already occurred earlier in the case journey (e.g., Triage -> Consultation -> X-Ray -> Triage).

## 3. Conformance Checking
* The actual paths taken by patients will be compared against the `IDEAL_PATH` defined in `src/common/schema.py`.
* Any deviation (skipped steps, extra steps, or loop-backs) will be flagged as non-conformant.