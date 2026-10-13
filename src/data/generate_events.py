"""
CareFlow — Synthetic EHR Event Log Generator
=============================================

Member 1 · Day 3–4 deliverable.

Generates `data/event_log.csv` using the frozen data contract from
`src/common/schema.py` (owned by Member 2).

Modes:
  clean  (default) → data/event_log.csv
                     Valid log for analysis + dashboard.

  dirty            → data/event_log_dirty.csv
                     Same generator, but with 7 deliberately-injected
                     defects for src/data/validate_events.py to catch.

Flags:
  --patients N     Number of patients (default 500)
  --mode clean|dirty
  --out PATH       Override output path

Determinism:
  Fixed seed (42). Re-running with the same args produces
  byte-identical output.
"""

import argparse
import csv
import os
import random
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Shared schema — single source of truth (owned by M2)
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
    "seed":                42,
    "num_patients":       500,
    "start_date":         datetime(2024, 1, 15, 8, 0, 0),
    "output_file":        "data/event_log.csv",
    "output_dirty":       "data/event_log_dirty.csv",

    # Planted ground-truth rates
    "xray_inclusion":     0.55,
    "review_inclusion":   0.45,
    "loopback_rate":      0.40,
    "deep_second_loop":   0.15,

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
    h = dt.hour
    if 6 <= h < 14:
        return "Morning"
    if 14 <= h < 22:
        return "Evening"
    return "Night"


def resource_for(activity):
    c = CONFIG
    if activity == ACT_REGISTRATION: return random.choice(c["reg_staff"])
    if activity == ACT_TRIAGE:       return random.choice(c["triage_nurses"])
    if activity == ACT_CONSULTATION: return random.choice(c["doctors"])
    if activity == ACT_XRAY:         return random.choice(c["xray_techs"])
    if activity == ACT_REVIEW:       return random.choice(c["doctors"])
    if activity == ACT_DISCHARGE:    return random.choice(c["doctors"])
    raise ValueError(f"Unknown activity: {activity}")


def build_journey():
    """Return a list of activity names for one patient."""
    c = CONFIG
    has_xray   = random.random() < c["xray_inclusion"]
    has_review = random.random() < c["review_inclusion"]

    journey = [ACT_REGISTRATION, ACT_TRIAGE, ACT_CONSULTATION]

    if has_xray:
        journey.append(ACT_XRAY)
        if random.random() < c["loopback_rate"]:
            journey.append(ACT_TRIAGE)          # ← planted 40% loop-back
            journey.append(ACT_CONSULTATION)
            if random.random() < c["deep_second_loop"]:
                journey.append(ACT_XRAY)
                journey.append(ACT_TRIAGE)
                journey.append(ACT_CONSULTATION)
        if has_review:
            journey.append(ACT_REVIEW)
    else:
        if has_review:
            journey.append(ACT_REVIEW)

    journey.append(ACT_DISCHARGE)
    return journey


# ============================================================
# GENERATION
# ============================================================
def generate(num_patients):
    """Produce the list of row dicts (clean)."""
    c = CONFIG
    random.seed(c["seed"])

    rows = []
    case_counter = 1
    clock = c["start_date"]

    for _ in range(num_patients):
        case_id = f"CASE-{case_counter:04d}"
        case_counter += 1

        t = clock + timedelta(minutes=random.randint(0, c["initial_offset_max"]))

        for activity in build_journey():
            if activity not in VALID_ACTIVITIES:
                raise ValueError(f"Bad activity: {activity}")

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

    return rows


def inject_defects(rows):
    """
    Inject 7 deliberately bad rows into a copy of the log,
    one defect per type, so the Day-5 validator has something to catch.
    """
    rng = random.Random(999)  # separate seed → deterministic defects
    dirty = [dict(r) for r in rows]

    # Pick 6 rows spread through the log
    n = len(dirty)
    idx = [int(n * f) for f in (0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95)]

    # 1) Missing case_id
    dirty[idx[0]]["case_id"] = ""

    # 2) Missing activity
    dirty[idx[1]]["activity"] = ""

    # 3) Invalid timestamp format (missing time component)
    dirty[idx[2]]["timestamp"] = "2024-01-15"

    # 4) Unknown activity name
    dirty[idx[3]]["activity"] = "Unknown Activity"

    # 5) Unknown shift value
    dirty[idx[4]]["shift"] = "Twilight"

    # 6) Duplicate timestamp — clone the timestamp of the row that precedes it
    dirty[idx[5]]["timestamp"] = dirty[idx[5] - 1]["timestamp"]

    # 7) Out-of-order timestamps — swap timestamps of two consecutive rows in same case
    a, b = idx[6], idx[6] + 1
    if a < n and b < n and dirty[a]["case_id"] == dirty[b]["case_id"]:
        dirty[a]["timestamp"], dirty[b]["timestamp"] = (
            dirty[b]["timestamp"], dirty[a]["timestamp"]
        )

    return dirty


# ============================================================
# I/O
# ============================================================
def write_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
        w.writeheader()
        w.writerows(rows)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CareFlow event log generator")
    parser.add_argument("--patients", type=int, default=CONFIG["num_patients"],
                        help="Number of patients (default 500)")
    parser.add_argument("--mode", choices=["clean", "dirty"], default="clean",
                        help="clean → valid log; dirty → log with injected defects")
    parser.add_argument("--out", type=str, default=None,
                        help="Override output path")
    args = parser.parse_args()

    rows = generate(args.patients)

    if args.mode == "dirty":
        rows = inject_defects(rows)
        out = args.out or CONFIG["output_dirty"]
    else:
        out = args.out or CONFIG["output_file"]

    write_csv(rows, out)

    unique_cases = len({r["case_id"] for r in rows if r["case_id"]})
    print(f"[OK] Mode:     {args.mode}")
    print(f"[OK] Wrote:    {len(rows)} events for {unique_cases} patients → {out}")
    print(f"[OK] Seed:     {CONFIG['seed']}  |  Deterministic: yes")
    print(f"[OK] Columns:  {EXPECTED_COLUMNS}")
    print(f"[OK] Activities: {VALID_ACTIVITIES}")


if __name__ == "__main__":
    main()