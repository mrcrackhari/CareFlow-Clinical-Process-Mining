\# Data Realism \& Privacy Audit (Day 12)



\*\*Author:\*\* Member 1 (Data)

\*\*Module:\*\* CareFlow Data Pipeline



\## 1. Privacy Guarantee (No Real Data)

The CareFlow project strictly adheres to data privacy guidelines. \*\*No real patient data (PHI) or real hospital data is present in this repository.\*\*



To ensure this, the data generation relies on a synthetic Python script (`src/data/generate\_events.py`). The following safeguards are in place:

\- \*\*Fictional Identifiers:\*\* Patient IDs are sequential (`CASE-0001`), and Staff IDs are fictional (`Nurse\_Jane`, `Dr\_Smith`).

\- \*\*No PII:\*\* Names, addresses, dates of birth, and real medical record numbers are entirely absent.

\- \*\*Simulated Timestamps:\*\* All timestamps are generated relative to a fixed start date (`2024-01-15`), not real-world dates.



\## 2. Realism \& Process Mining Validity

While the data is synthetic, it is structurally realistic enough to support PM4Py process mining. 



The generator simulates a standard Emergency Room workflow:

`Registration → Triage → Doctor Consultation → (X-Ray / Review) → Discharge`



\### Why is it realistic?

\- \*\*Stochastic Variance:\*\* The generator uses real-world probability rates (e.g., 55% chance of an X-Ray, 45% chance of a Doctor Review).

\- \*\*The Hidden Bottleneck:\*\* The project brief requires a bottleneck. We planted a \*\*40% loop-back rate\*\* where patients are sent back to Triage after an X-Ray (simulating a missing paperwork delay). 

\- \*\*Time Deltas:\*\* Transition times between events are randomized (10–45 minutes), mimicking realistic hospital waiting times.

\- \*\*Concurrency \& Shifts:\*\* Staff assignments rotate based on the time of day (Morning/Evening/Night), allowing for realistic dashboard filtering by shift.



\## 3. Validating the Data

To ensure the realism doesn't compromise structural integrity, the dataset passes all 10 checks in our `validate\_events.py` script (0 missing IDs, 0 invalid timestamps, 0 malformed activities).



\## 4. Conclusion

The dataset is 100% safe for public repository hosting and meets all criteria for the process-mining analysis.

