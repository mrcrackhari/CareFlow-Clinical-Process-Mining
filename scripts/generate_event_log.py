"""
CareFlow — Event Log Generator (Day 10)
Generates data/event_log.csv — 500 synthetic patients, fixed seed for reproducibility.
"""
import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)  # Fixed seed → stable demo file

NUM_PATIENTS = 500
START_DATE = datetime(2024, 1, 15, 8, 0, 0)
OUTPUT_FILE = "data/event_log.csv"

TRIAGE_NURSES = ["Nurse_Jane", "Nurse_Tom", "Nurse_Sara", "Nurse_Mike"]
DOCTORS       = ["Dr_Smith", "Dr_Lee", "Dr_Patel", "Dr_Adams", "Dr_Kim"]
LAB_TECHS     = ["Lab_Tech_A", "Lab_Tech_B", "Lab_Tech_C"]
WARD_NURSES   = ["Nurse_Mary", "Nurse_John", "Nurse_Lisa"]

DEPARTMENTS = {
    "Triage": "Emergency", "X-Ray": "Radiology", "Blood_Test": "Pathology",
    "Doctor_Consult": "Emergency", "Admit_Ward": "Ward_3", "Discharge": "Emergency",
}
INSURANCE = ["Private", "Medicare", "Medicaid", "Self-Pay"]

LOOPBACK_AFTER_XRAY = 0.40
DEEP_SECOND_LOOP    = 0.15
XRAY_INCLUSION      = 0.55
BLOOD_INCLUSION     = 0.45
ADMIT_RATE          = 0.40


def build_journey():
    journey = [("Triage", "N")]
    has_xray  = random.random() < XRAY_INCLUSION
    has_blood = random.random() < BLOOD_INCLUSION
    is_admit  = random.random() < ADMIT_RATE

    if has_blood:
        journey.append(("Blood_Test", "N"))
    if has_xray:
        journey.append(("X-Ray", "N"))
        if random.random() < LOOPBACK_AFTER_XRAY:
            journey.append(("Triage", "Y"))
            journey.append(("Doctor_Consult", "N"))
            if random.random() < DEEP_SECOND_LOOP:
                journey.append(("X-Ray", "Y"))
                journey.append(("Triage", "Y"))
                journey.append(("Doctor_Consult", "N"))
        else:
            journey.append(("Doctor_Consult", "N"))
    else:
        journey.append(("Doctor_Consult", "N"))

    if has_blood and not has_xray:
        journey.append(("Doctor_Consult", "N"))

    journey.append(("Admit_Ward", "N") if is_admit else ("Discharge", "N"))
    return journey


def pick_resource(activity):
    if activity == "Triage":         return random.choice(TRIAGE_NURSES)
    if activity == "X-Ray":          return random.choice(DOCTORS)
    if activity == "Blood_Test":     return random.choice(LAB_TECHS)
    if activity == "Doctor_Consult": return random.choice(DOCTORS)
    if activity == "Admit_Ward":     return random.choice(WARD_NURSES)
    return random.choice(DOCTORS)


rows = []
patient_counter = 10234
clock = START_DATE

for i in range(1, NUM_PATIENTS + 1):
    case_id    = f"C{i:04d}"
    patient_id = f"P{patient_counter}"
    patient_counter += 1
    age        = random.randint(18, 85)
    gender     = random.choice(["M", "F"])
    insurance  = random.choice(INSURANCE)

    t = clock + timedelta(minutes=random.randint(0, 480))
    for activity, loop_flag in build_journey():
        rows.append({
            "case_id":        case_id,
            "patient_id":     patient_id,
            "activity":       activity,
            "timestamp":      t.strftime("%Y-%m-%d %H:%M:%S"),
            "resource":       pick_resource(activity),
            "department":     DEPARTMENTS[activity],
            "age":            age,
            "gender":         gender,
            "insurance_type": insurance,
            "loop_back_flag": loop_flag,
        })
        t += timedelta(minutes=random.randint(10, 45))

    clock += timedelta(minutes=random.randint(2, 15))

FIELDS = ["case_id", "patient_id", "activity", "timestamp", "resource",
          "department", "age", "gender", "insurance_type", "loop_back_flag"]

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

print(f"[OK] Wrote {len(rows)} events for {NUM_PATIENTS} patients → {OUTPUT_FILE}")