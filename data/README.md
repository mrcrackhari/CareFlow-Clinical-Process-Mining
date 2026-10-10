\# CareFlow — Clinical Pathway Process Mining: Data Module



\## Purpose

Synthetic EHR event log for hospital ER process mining.



\## Columns

case\_id, patient\_id, activity, timestamp, resource,

department, age, gender, insurance\_type, loop\_back\_flag



\## Synthetic Only

No real patient data. All names and IDs are fictional.



\## Planted Ground Truth (The Hidden Bottleneck)

\- 40% of patients are sent back to Triage after an X-Ray

\- Marks a missing paperwork form

\- loop\_back\_flag = Y indicates a return to a prior activity



\## Files

\- sample\_event\_log.csv  — 10 hand-made journeys (Day 2)

\- event\_log.csv         — 500 patients, seed=42 (Day 10)

\- quality\_report.csv    — validation checks (Day 9)

