\# CareFlow — Data Generation Guide



\*\*Owner:\*\* Member 1 (Data)  

\*\*File:\*\* `src/data/generate\_events.py`  

\*\*Output:\*\* `data/event\_log.csv` (and `data/event\_log\_dirty.csv`)  

\*\*Contract:\*\* `src/common/schema.py`  



\---



\## 1. Overview



This document explains how the CareFlow synthetic event logs are generated.

The goal is to produce realistic \*\*Emergency Room (ER) patient journeys\*\* that

follow a frozen data contract, so that process-mining algorithms (PM4Py) can

discover a process map, calculate bottlenecks, and check conformance.



The data is \*\*100% synthetic\*\*. No real patients, no PHI, no real hospital

data. All staff names (`Nurse\_Jane`, `Dr\_Smith`, `Tech\_Miller`) are fictional.



\---



\## 2. Configuration (`CONFIG`)



Every magic number lives at the top of `generate\_events.py` in the `CONFIG`

dictionary. To change the simulation, edit these values — do not hardcode

constants inside the generation logic.



| Key | Value | Purpose |

|-----|-------|---------|

| `seed` | `42` | Fixed random seed for deterministic output |

| `num\_patients` | `500` | Cohort size for the full log |

| `start\_date` | `2024-01-15 08:00:00` | Anchor timestamp |

| `output\_file` | `data/event\_log.csv` | Clean output path |

| `output\_dirty` | `data/event\_log\_dirty.csv` | Dirty output path |

| `xray\_inclusion` | `0.55` | 55% of patients get an X-Ray |

| `review\_inclusion` | `0.45` | 45% get a Doctor Review |

| `loopback\_rate` | `0.40` | \*\*40% of X-Ray cases loop back to Triage\*\* |

| `deep\_second\_loop` | `0.15` | 15% of loopers loop a second time |

| `gap\_min` / `gap\_max` | `10` / `45` | Minutes between events for one patient |

| `arrival\_jitter\_min` / `arrival\_jitter\_max` | `2` / `15` | Minutes between patient arrivals |



\---



\## 3. The Journey Builder (`build\_journey()`)



Every patient starts with:

1\. `Registration`

2\. `Triage`

3\. `Doctor Consultation`



From there, the generator rolls dice based on `CONFIG`:



\- \*\*Has X-Ray?\*\* (`55%` chance)

&#x20; - Yes → append `X-Ray`

&#x20;   - \*\*Loop-back?\*\* (`40%` chance) → append `Triage` → `Doctor Consultation`

&#x20;     - \*\*Deep loop?\*\* (`15%` chance) → append `X-Ray` → `Triage` → `Doctor Consultation`

&#x20; - No → skip X-Ray

\- \*\*Has Doctor Review?\*\* (`45%` chance) → append `Doctor Review`

\- Always ends with: `Discharge`



\---



\## 4. Planted Ground Truth (The Hidden Bottleneck)



The CareFlow brief specifies:



> "40% of patients are being sent back to Triage after an X-Ray due to a

> specific missing paperwork form."



This is \*\*deliberately planted\*\* in the code:

\- `loopback\_rate = 0.40`

\- The target rate is verified by `src/data/validate\_events.py` (check

&#x20; `no\_duplicate\_timestamps\_in\_case` indirectly confirms the pattern) and by

&#x20; M2's `calculate\_metrics.py`.



When M2 runs their process-mining analysis, they will discover:

\- \~40% of X-Ray cases contain a `X-Ray → Triage` transition.

\- The dominant edge in the process map is `X-Ray → Triage` (the bottleneck).

\- Removing the bottleneck saves \~20 minutes of average wait time.



\---



\## 5. Modes (`clean` vs `dirty`)



The generator can produce two very different files:



\### `--mode clean` (default)

Produces `data/event\_log.csv`.

\- Every row passes `src/data/validate\_events.py`.

\- Used for analysis, dashboards, and the mid review demo.



\### `--mode dirty`

Produces `data/event\_log\_dirty.csv`.

\- Injects \*\*exactly 7 deliberate defects\*\* into the clean log.

\- Used only for testing the validator.

\- Defects injected:

&#x20; 1. Empty `case\_id`

&#x20; 2. Empty `activity`

&#x20; 3. Short timestamp (missing time component)

&#x20; 4. Unknown activity (`Unknown Activity`)

&#x20; 5. Unknown shift (`Twilight`)

&#x20; 6. Duplicate timestamp within a case

&#x20; 7. Out-of-order timestamps within a case



\---



\## 6. CLI Reference



```bash

\# Clean log (default)

python -m src.data.generate\_events



\# Dirty log (7 defects)

python -m src.data.generate\_events --mode dirty



\# Small test cohort

python -m src.data.generate\_events --patients 20 --out data/small.csv



\# Custom path

python -m src.data.generate\_events --out scratch/my\_log.csv

