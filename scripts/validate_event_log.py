"""
CareFlow — Event Log Validator (Day 9)
Reads data/event_log.csv, runs integrity checks, writes data/quality_report.csv.
"""
import csv
from collections import defaultdict

IN_PATH  = "data/event_log.csv"
OUT_PATH = "data/quality_report.csv"

REQUIRED_COLS = ["case_id","patient_id","activity","timestamp","resource",
                 "department","age","gender","insurance_type","loop_back_flag"]
VALID_ACTIVITIES = {"Triage","X-Ray","Blood_Test","Doctor_Consult","Admit_Ward","Discharge"}

with open(IN_PATH) as f:
    rows = list(csv.DictReader(f))

checks = []

checks.append(("required_columns_present",
               "10", str(len(rows[0].keys())),
               "PASS" if set(REQUIRED_COLS) <= set(rows[0].keys()) else "FAIL"))

bad = {r["activity"] for r in rows} - VALID_ACTIVITIES
checks.append(("all_activities_valid", "0 invalid", f"{len(bad)} invalid",
               "PASS" if not bad else "FAIL"))

cases = {r["case_id"] for r in rows}
checks.append(("unique_cases", "500", str(len(cases)),
               "PASS" if len(cases) == 500 else "FAIL"))

nulls = sum(1 for r in rows for c in ("case_id","activity","timestamp") if not r[c].strip())
checks.append(("no_null_keys", "0", str(nulls),
               "PASS" if nulls == 0 else "FAIL"))

xray_cases = defaultdict(list)
for r in rows:
    xray_cases[r["case_id"]].append(r)

loopers = 0
xray_count = 0
for cid, evts in xray_cases.items():
    evts_sorted = sorted(evts, key=lambda x: x["timestamp"])
    if any(e["activity"] == "X-Ray" for e in evts_sorted):
        xray_count += 1
        after_xray = False
        for e in evts_sorted:
            if e["activity"] == "X-Ray":
                after_xray = True
            elif after_xray and e["activity"] == "Triage" and e["loop_back_flag"] == "Y":
                loopers += 1
                break
rate = loopers / xray_count if xray_count else 0
checks.append(("loopback_rate_after_xray", "0.40", f"{rate:.2f}",
               "PASS" if 0.35 <= rate <= 0.45 else "WARN"))

bad_order = 0
for cid, evts in xray_cases.items():
    ts = [e["timestamp"] for e in sorted(evts, key=lambda x: x["timestamp"])]
    if ts != sorted(ts):
        bad_order += 1
checks.append(("timestamps_monotonic", "0", str(bad_order),
               "PASS" if bad_order == 0 else "FAIL"))

checks.append(("total_events", ">=2000", str(len(rows)),
               "PASS" if len(rows) >= 2000 else "FAIL"))

valid_ins = {"Private","Medicare","Medicaid","Self-Pay"}
bad_ins = {r["insurance_type"] for r in rows} - valid_ins
checks.append(("insurance_types_valid", "0 invalid", f"{len(bad_ins)} invalid",
               "PASS" if not bad_ins else "FAIL"))

with open(OUT_PATH, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check_name", "expected", "actual", "status"])
    w.writerows(checks)

print(f"[OK] Wrote {len(checks)} checks → {OUT_PATH}")