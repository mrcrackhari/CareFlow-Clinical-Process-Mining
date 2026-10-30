
"""
CareFlow — Synthetic EHR Event Log Generator
=============================================

Member 1 — Day 3–4 deliverable.

Generates data/event_log.csv using the shared schema.

Modes:
  clean  -> data/event_log.csv
  dirty  -> data/event_log_dirty.csv

Dirty mode injects 7 deliberate defects for validation testing.
"""

import argparse
import csv
import os
import random
from datetime import datetime, timedelta

from src.common.schema import (
    EXPECTED_COLUMNS,
    ACT_REGISTRATION,
    ACT_TRIAGE,
    ACT_CONSULTATION,
    ACT_XRAY,
    ACT_REVIEW,
    ACT_DISCHARGE,
    VALID_ACTIVITIES,
    VALID_SHIFTS,
    IDEAL_PATH,
)


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    "seed": 42,
    "num_patients": 500,
    "start_date": datetime(2024, 1, 15, 8, 0, 0),
    "output_file": "data/event_log.csv",
    "output_dirty": "data/event_log_dirty.csv",

    "xray_inclusion": 0.55,
    "review_inclusion": 0.45,
    "loopback_rate": 0.40,
    "deep_second_loop": 0.15,

    "gap_min": 10,
    "gap_max": 45,
    "arrival_jitter_min": 2,
    "arrival_jitter_max": 15,
    "initial_offset_max": 480,

    "reg_staff": ["Reg_Clerk_A", "Reg_Clerk_B"],
    "triage_nurses": [
        "Nurse_Jane", "Nurse_Tom",
        "Nurse_Sara", "Nurse_Mike"
    ],
    "doctors": [
        "Dr_Smith", "Dr_Lee",
        "Dr_Patel", "Dr_Adams", "Dr_Kim"
    ],
    "xray_techs": [
        "Tech_Miller", "Tech_Rao", "Tech_Kim"
    ],
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
    """Return a list of activities for one patient."""

    c = CONFIG

    has_xray = random.random() < c["xray_inclusion"]
    has_review = random.random() < c["review_inclusion"]

    journey = [
        ACT_REGISTRATION,
        ACT_TRIAGE,
        ACT_CONSULTATION
    ]

    if has_xray:
        journey.append(ACT_XRAY)

        if random.random() < c["loopback_rate"]:

            journey.append(ACT_TRIAGE)
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
    """Generate clean patient event log."""

    c = CONFIG

    random.seed(c["seed"])

    rows = []
    case_counter = 1
    clock = c["start_date"]

    for _ in range(num_patients):

        case_id = f"CASE-{case_counter:04d}"
        case_counter += 1

        t = clock + timedelta(
            minutes=random.randint(
                0, c["initial_offset_max"]
            )
        )

        for activity in build_journey():

            if activity not in VALID_ACTIVITIES:
                raise ValueError(f"Bad activity: {activity}")

            rows.append({
                "case_id": case_id,
                "activity": activity,
                "timestamp": t.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "resource": resource_for(activity),
                "shift": shift_for(t),
            })

            t += timedelta(
                minutes=random.randint(
                    c["gap_min"], c["gap_max"]
                )
            )

        clock += timedelta(
            minutes=random.randint(
                c["arrival_jitter_min"],
                c["arrival_jitter_max"]
            )
        )

    return rows


# ============================================================
# DEFECT INJECTION
# ============================================================

def inject_defects(rows):
    """
    Inject 7 deliberately bad conditions into a copy
    of the clean event log.
    """

    dirty = [dict(r) for r in rows]

    n = len(dirty)

    idx = [
        int(n * f)
        for f in (0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95)
    ]

    # 1. Missing case_id
    dirty[idx[0]]["case_id"] = ""

    # 2. Missing activity
    dirty[idx[1]]["activity"] = ""

    # 3. Invalid timestamp format
    dirty[idx[2]]["timestamp"] = "2024-01-15"

    # 4. Unknown activity
    dirty[idx[3]]["activity"] = "Unknown Activity"

    # 5. Invalid shift
    dirty[idx[4]]["shift"] = "Twilight"

    # 6. Duplicate timestamp within the same case
    duplicate_index = idx[5]

    dirty[duplicate_index]["timestamp"] = (
        dirty[duplicate_index - 1]["timestamp"]
    )

    # 7. Out-of-order timestamps within the same case
    # Find two consecutive events belonging to the same case.
    # Skip rows already modified by other timestamp defects.

    blocked_indices = {
        idx[0],
        idx[2],
        idx[5],
        idx[5] - 1
    }

    candidate_indices = (
        list(range(idx[6], n - 1))
        + list(range(0, idx[6]))
    )

    swapped = False

    for a in candidate_indices:

        b = a + 1

        if a in blocked_indices or b in blocked_indices:
            continue

        case_a = dirty[a]["case_id"]
        case_b = dirty[b]["case_id"]

        timestamp_a = dirty[a]["timestamp"]
        timestamp_b = dirty[b]["timestamp"]

        if (
            case_a
            and case_a == case_b
            and timestamp_a != timestamp_b
        ):

            try:
                datetime.strptime(
                    timestamp_a, "%Y-%m-%d %H:%M:%S"
                )

                datetime.strptime(
                    timestamp_b, "%Y-%m-%d %H:%M:%S"
                )

            except ValueError:
                continue

            dirty[a]["timestamp"], dirty[b]["timestamp"] = (
                timestamp_b,
                timestamp_a
            )

            swapped = True
            break

    if not swapped:
        raise ValueError(
            "Could not inject out-of-order timestamp defect."
        )

    return dirty


# ============================================================
# CSV OUTPUT
# ============================================================

def write_csv(rows, path):

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=EXPECTED_COLUMNS
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# MAIN FUNCTION
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="CareFlow event log generator"
    )

    parser.add_argument(
        "--patients",
        type=int,
        default=CONFIG["num_patients"],
        help="Number of patients (default 500)"
    )

    parser.add_argument(
        "--mode",
        choices=["clean", "dirty"],
        default="clean",
        help="Generate clean or dirty event log"
    )

    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Override output path"
    )

    args = parser.parse_args()

    if args.patients <= 0:
        parser.error("--patients must be greater than zero")

    rows = generate(args.patients)

    if args.mode == "dirty":

        rows = inject_defects(rows)

        output_path = (
            args.out or CONFIG["output_dirty"]
        )

    else:

        output_path = (
            args.out or CONFIG["output_file"]
        )

    write_csv(rows, output_path)

    unique_cases = len({
        r["case_id"]
        for r in rows
        if r["case_id"]
    })

    print(f"[OK] Mode: {args.mode}")
    print(
        f"[OK] Wrote: {len(rows)} events "
        f"for {unique_cases} patients -> {output_path}"
    )

    print(f"[OK] Seed: {CONFIG['seed']}")
    print(f"[OK] Columns: {EXPECTED_COLUMNS}")
    print(f"[OK] Activities: {VALID_ACTIVITIES}")


if __name__ == "__main__":
    main()
