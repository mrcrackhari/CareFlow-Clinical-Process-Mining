\# tests/fixtures — Hand-Checked Journeys



\## Purpose



`hand\_checked\_journeys.csv` is a small, hand-pickable subset of

`data/event\_log.csv` — 5 cases that together cover \*\*every process shape\*\*

our generator can produce. Member 2 uses these cases on Day 9 to compute

metrics by hand, then compares against the output of

`src/analysis/calculate\_metrics.py` (recorded in `expected\_metrics.csv`).



If the analysis pipeline is correct, the hand-computed values will match

the script-generated values for these 5 cases exactly.



\## Fixture Cases



| Case | Shape | Tests |

|------|-------|-------|

| `CASE-0003` | `Registration → Triage → Doctor Consultation → Discharge` | Baseline — no imaging, no review |

| `CASE-0006` | `Registration → Triage → Doctor Consultation → Doctor Review → Discharge` | Review without X-Ray |

| `CASE-0002` | `Registration → Triage → Doctor Consultation → X-Ray → Doctor Review → Discharge` | Matches `IDEAL\_PATH` (conformant case) |

| `CASE-0007` | `Registration → Triage → Doctor Consultation → X-Ray → Triage → Doctor Consultation → Discharge` | Single loop-back (planted bottleneck) |

| `CASE-0001` | `Registration → Triage → Doctor Consultation → X-Ray → Triage → Doctor Consultation → X-Ray → Triage → Doctor Consultation → Discharge` | Double loop-back (edge case) |



\## Regeneration



To rebuild this fixture from the current `data/event\_log.csv`:



```python

import csv

WANTED = \["CASE-0001", "CASE-0002", "CASE-0003", "CASE-0006", "CASE-0007"]

with open("data/event\_log.csv", newline="") as f:

&#x20;   reader = csv.DictReader(f)

&#x20;   fields = reader.fieldnames

&#x20;   rows = \[r for r in reader if r\["case\_id"] in WANTED]

with open("tests/fixtures/hand\_checked\_journeys.csv", "w", newline="") as f:

&#x20;   w = csv.DictWriter(f, fieldnames=fields)

&#x20;   w.writeheader()

&#x20;   w.writerows(rows)

