"""
CareFlow — Synthetic EHR Event Log Generator
=============================================

Member 1 · Day 3–4 deliverable.

Generates `data/event_log.csv` using the frozen data contract from
`src/common/schema.py` (owned by Member 2).

- 500 synthetic patient ER visits
- Deterministic: fixed seed (42) → byte-identical output every run
- Planted ground truth: ~40% of X-Ray cases deviate from IDEAL_PATH
  via an X-Ray → Triage loop-back (the hidden paperwork bottleneck)

Schema is imported from src/common/schema.py — single source of truth.
"""

import csv
import os
import random
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Import the shared schema (M2's file — single source of truth)
# ------------------------------------------------------------------
from src.common.schema import (
    EXPECTED_COLUMNS,
    ACT_REGISTRATION, ACT_TRIAGE, ACT_CONSULTATION,
    ACT_XRAY, ACT_REVIEW, ACT_DISCHARGE,
    VALID_ACTIVITIES, VALID_SHIFTS, IDEAL_PATH,
)


# ============================================================
# CONFIG — tunable knobs
# ============================================================
CONFIG = {
    # Reproducibility
    "seed":                42,
    "num_patients":       500,
    "start_date":         datetime(2024, 1, 15, 8, 0, 0),
    "output_file":        "data/event_log.csv",

    # Planted ground-truth rates (recorded in data/README.md §6)
    "xray_inclusion":     0.55,   # ~55% of patients get an X-Ray
    "review_inclusion":   0.45,   # ~45% get a Doctor Review
    "loopback_rate":      0.40,   # 40% of X-Ray cases loop back to Triage
    "deep_second_loop":   0.15,   # of loopers, ~15% loop again
    "admit_rate":         0.40,   # 40% admitted (get Review before Discharge)

    # Timing (minutes between consecutive events)
    "gap_min":            10,
    "gap_max":            45,
    "arrival_jitter_min":  2,
    "arrival_jitter_max": 15,
    "initial_offset_max": 480,

    # Fictional staff pools
    "reg_staff":     ["Reg_Clerk_A", "Reg_Clerk_B"],
    "triage_nurses": ["Nurse_Jane", "Nurse_Tom", "Nurse_Sara", "Nurse_Mike"],
    "doctors":       ["Dr_Smith", "Dr_Lee", "Dr_Patel", "Dr_Adams", "Dr_Kim"],
    "xray_techs":    ["Tech_Miller", "Tech_Rao", "Tech_Kim"],
}


# ============================================================
# HELPERS
# ============================================================
def shift_for(dt):
    """Return Morning / Evening / Night for a datetime."""
    h = dt.hour
    if 6 <= h < 14:
        return "Morning"
    if 14 <= h < 22:
        return "Evening"
    return "Night"


def resource_for(activity):
    """Return a fictional staff member for the given activity."""
    c = CONFIG
    if activity == ACT_REGISTRATION:
        return random.choice(c["reg_staff"])
    if activity == ACT_TRIAGE:
        return random.choice(c["triage_nurses"])
    if activity == ACT_CONSULTATION:
        return random.choice(c["doctors"])
    if activity == ACT_XRAY:
        return random.choice(c["xray_techs"])
    if activity == ACT_REVIEW:
        return random.choice(c["doctors"])
    if activity == ACT_DISCHARGE:
        return random.choice(c["doctors"])
    raise ValueError(f"Unknown activity: {activity}")


def build_journey():
    """
    Return a list of activity names for one patient.

    The 'default' path when a patient has both X-Ray and Review follows
    the IDEAL_PATH from schema.py exactly:

        Registration → Triage → Doctor Consultation
                     → X-Ray → Doctor Review → Discharge

    Deviations:
      - No X-Ray, no Review  : Registration → Triage → Consultation → Discharge
      - Review, no X-Ray     : Registration → Triage → Consultation → Review → Discharge
      - X-Ray + loop-back    : Registration → Triage → Consultation → X-Ray
                               → Triage (LOOP) → Consultation → ... → Discharge
      - Deep second loop     : a second X-Ray + Triage loop before Discharge
    """
    c = CONFIG
    has_xray   = random.random() < c["xray_inclusion"]
    has_review = random.random() < c["review_inclusion"]

    journey = [ACT_REGISTRATION, ACT_TRIAGE, ACT_CONSULTATION]

    if has_xray:
        journey.append(ACT_XRAY)

        # ── Planted 40% bottleneck: X-Ray → Triage loop-back ──
        if random.random() < c["loopback_rate"]:
            journey.append(ACT_TRIAGE)              # ← loop-back
            journey.append(ACT_CONSULTATION)        # re-consult after loop

            # Deep second loop (a second X-Ray + Triage)
            if random.random() < c["deep_second_loop"]:
                journey.append(ACT_XRAY)
                journey.append(ACT_TRIAGE)          # ← second loop-back
                journey.append(ACT_CONSULTATION)

        if has_review:
            journey.append(ACT_REVIEW)

    else:
        # No X-Ray. Review is still possible.
        if has_review:
            journey.append(ACT_REVIEW)

    journey.append(ACT_DISCHARGE)
    return journey


# ============================================================
# MAIN
# ============================================================
def main():
    c = CONFIG
    random.seed(c["seed"])

    rows = []
    case_counter = 1
    clock = c["start_date"]

    for _ in range(c["num_patients"]):
        case_id = f"CASE-{case_counter:04d}"
        case_counter += 1

        t = clock + timedelta(minutes=random.randint(0, c["initial_offset_max"]))

        for activity in build_journey():
            if activity not in VALID_ACTIVITIES:
                raise ValueError(
                    f"Generated activity '{activity}' not in VALID_ACTIVITIES "
                    f"from src/common/schema.py"
                )

            rows.append({
                "case_id":   case_id,
                "activity":  activity,
                "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                "resource":  resource_for(activity),
                "shift":     shift_for(t),
            })
            t += timedelta(minutes=random.randint(c["gap_min"], c["gap_max"]))

        clock += timedelta(
            minutes=random.randint(c["arrival_jitter_min"], c["arrival_jitter_max"])
        )

    os.makedirs(os.path.dirname(c["output_file"]), exist_ok=True)

    with open(c["output_file"], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    unique_cases = len({r["case_id"] for r in rows})
    print(f"[OK] Wrote {len(rows)} events for {unique_cases} patients → {c['output_file']}")
    print(f"[OK] Seed: {c['seed']}  |  Deterministic: yes")
    print(f"[OK] Schema imported from src/common/schema.py")
    print(f"[OK] Columns: {EXPECTED_COLUMNS}")
    print(f"[OK] Activities: {VALID_ACTIVITIES}")


if __name__ == "__main__":
    main()