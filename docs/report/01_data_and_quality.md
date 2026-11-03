
## 6. Data Findings (Day 14)

Based on the final stable 500-case dataset (`data/event_log.csv`), here are the key data findings that drive the process mining analysis:

### A. The Hidden Bottleneck
The most significant finding is the deliberately planted operational bottleneck. 
- **40% of X-Ray cases** loop back to `Triage` due to a simulated missing paperwork delay. 
- This creates a massive non-conformant edge in the process map (`X-Ray → Triage`), which Member 2's PM4Py analysis correctly identifies as the primary source of extended wait times.
- **ROI Impact:** Eliminating this loop-back reduces the average patient journey time by approximately 20 minutes.

### B. Shift Distribution
The data accurately reflects a 24-hour emergency room cycle. The event distribution across shifts provides sufficient volume for Member 3's dashboard filters:
- **Morning (06:00 - 13:59):** 31% of events
- **Evening (14:00 - 21:59):** 33% of events
- **Night (22:00 - 05:59):** 36% of events

### C. Resource Workload
The generator assigns 12 fictional staff members (5 Doctors, 4 Nurses, 3 Techs) across the activities. This allows the analysis to pinpoint which specific staff roles are bearing the brunt of the bottleneck during loop-backs.

---

## 7. Integration Status (Day 14)

As of Day 14, the Data Module is fully integrated with the team's analysis and dashboard branches.

- **Schema Alignment:** Both `member1-data` and `member2-analysis` share the exact same contract file (`src/common/schema.py`), preventing any column-mismatch crashes.
- **Automated Testing:** The `tests/test_data_validation.py` pytest suite guarantees that the clean data passes 10/10 checks before M2's analysis or M3's dashboard ever reads it. 
- **Error Handling:** We verified that the validation suite successfully catches 7 distinct defect types if bad data is introduced.

The data foundation is stable, documented, and ready for the final presentation.