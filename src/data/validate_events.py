"""
CareFlow — Event Log Validator
===============================

Member 1 · Day 5 deliverable.

Reads a CareFlow event log CSV, runs validation checks, writes a
quality report CSV matching TEAM_STRUCTURE §5:
    check, rows_checked, rows_failed

Usage:
    python -m src.data.validate_events
    python -m src.data.validate_events --in data/event_log_dirty.csv --out data/quality_report_dirty.csv

Exits with code 1 if any check reports failures (CI-friendly).
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

from src.common.schema import (
    EXPECTED_COLUMNS,
    VALID_ACTIVITIES,
    VALID_SHIFTS,
)


TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _s(row, key):
    return (row.get(key) or "").strip()


def run_checks(rows, columns):
    results = []
    n = len(rows)

    # 1. Required columns present
    missing = [c for c in EXPECTED_COLUMNS if c not in columns]
    results.append(("required_columns_present", n, len(missing)))

    # 2. Non-empty case_id
    results.append(("non_empty_case_id", n,
                    sum(1 for r in rows if not _s(r, "case_id"))))

    # 3. Non-empty activity
    results.append(("non_empty_activity", n,
                    sum(1 for r in rows if not _s(r, "activity"))))

    # 4. Activity in VALID_ACTIVITIES
    results.append(("activity_in_valid_activities", n,
                    sum(1 for r in rows if _s(r, "activity")
                        and _s(r, "activity") not in VALID_ACTIVITIES)))

    # 5. Shift in VALID_SHIFTS
    results.append(("shift_in_valid_shifts", n,
                    sum(1 for r in rows if _s(r, "shift")
                        and _s(r, "shift") not in VALID_SHIFTS)))

    # 6. Timestamp format valid
    results.append(("timestamp_format_valid", n,
                    sum(1 for r in rows if not TIMESTAMP_RE.match(_s(r, "timestamp")))))

    # Group by case for temporal checks
    by_case = defaultdict(list)
    for i, r in enumerate(rows):
        by_case[_s(r, "case_id")].append((i, _s(r, "timestamp")))

    # 7. Monotonic timestamps within case
    failed_cases = 0
    for cid, entries in by_case.items():
        if not cid:
            continue
        ordered = [ts for _, ts in sorted(entries, key=lambda x: x[0])]
        valid = [ts for ts in ordered if TIMESTAMP_RE.match(ts)]
        if valid != sorted(valid):
            failed_cases += 1
    results.append(("timestamp_monotonic_within_case", len(by_case), failed_cases))

    # 8. No duplicate timestamps within case
    failed_cases = 0
    for cid, entries in by_case.items():
        if not cid:
            continue
        seen = defaultdict(int)
        for _, ts in entries:
            if TIMESTAMP_RE.match(ts):
                seen[ts] += 1
        if any(v > 1 for v in seen.values()):
            failed_cases += 1
    results.append(("no_duplicate_timestamps_in_case", len(by_case), failed_cases))

    # 9. Non-empty resource
    results.append(("non_empty_resource", n,
                    sum(1 for r in rows if not _s(r, "resource"))))

    # 10. Non-empty timestamp
    results.append(("non_empty_timestamp", n,
                    sum(1 for r in rows if not _s(r, "timestamp"))))

    return results


def main():
    p = argparse.ArgumentParser(description="CareFlow event log validator")
    p.add_argument("--in",  dest="in_path",  default="data/event_log.csv")
    p.add_argument("--out", dest="out_path", default="data/quality_report.csv")
    args = p.parse_args()

    if not os.path.exists(args.in_path):
        print(f"[FATAL] Input not found: {args.in_path}")
        sys.exit(2)

    with open(args.in_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames or []

    results = run_checks(rows, columns)

    os.makedirs(os.path.dirname(args.out_path) or ".", exist_ok=True)
    with open(args.out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "rows_checked", "rows_failed"])
        w.writerows(results)

    print(f"[OK] Validated: {args.in_path}  ({len(rows)} rows)")
    print(f"[OK] Report:    {args.out_path}")
    print()
    print(f"{'check':<40}{'checked':>10}{'failed':>10}")
    print("-" * 62)
    for check, checked, failed in results:
        flag = "PASS" if failed == 0 else "FAIL"
        print(f"{check:<40}{checked:>10}{failed:>10}  {flag}")

    total = sum(f for _, _, f in results)
    if total > 0:
        print(f"\n[FAIL] {total} total failure(s) across all checks.")
        sys.exit(1)
    print("\nAll checks passed")


if __name__ == "__main__":
    main()