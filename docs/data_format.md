# CareFlow — Data Format Contract

Frozen contract. Any code that reads or writes event logs must match this.

## Event log schema

Columns (in order):

1. `case_id` — e.g. `CASE-0001` (hyphens, 4-digit zero-padded)
2. `activity` — one of the 6 below
3. `timestamp` — `YYYY-MM-DD HH:MM:SS`, no timezone
4. `resource` — fictional staff member
5. `shift` — `Morning` / `Evening` / `Night`

Defined in `src/common/schema.py` as `EXPECTED_COLUMNS`.

## Activities (VALID_ACTIVITIES)

- Registration
- Triage
- Doctor Consultation
- X-Ray
- Doctor Review
- Discharge

## Ideal path (IDEAL_PATH)

`Registration → Triage → Doctor Consultation → X-Ray → Doctor Review → Discharge`

## Planted bottleneck

40% of X-Ray cases loop back to Triage (see `data/README.md` section 6).

## Generation

```bash
python -m src.data.generate_events               # clean, 500 patients
python -m src.data.generate_events --mode dirty  # + 7 defect types