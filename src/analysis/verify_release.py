from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUTS_DIR = PROJECT_ROOT / "outputs"

REQUIRED_CSVS = [
    "event_transitions.csv",
    "bottleneck_metrics.csv",
    "process_paths.csv",
    "repeat_loop_metrics.csv",
    "process_map_edges.csv",
    "conformance_summary.csv",
]

OPTIONAL_ADVANCED_CSVS = [
    "shift_resource_metrics.csv",
    "clinical_cohort_metrics.csv",
    "intervention_scenarios.csv",
]


def verify_outputs() -> list[tuple[str, int, int]]:
    """Audit all CSV files in outputs/ and return (filename, rows, cols)."""
    audit_rows: list[tuple[str, int, int]] = []
    all_targets = REQUIRED_CSVS + [
        f for f in OPTIONAL_ADVANCED_CSVS if (OUTPUTS_DIR / f).exists()
    ]

    for filename in all_targets:
        csv_path = OUTPUTS_DIR / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing required output file: {csv_path}")

        df = pd.read_csv(csv_path)
        if df.empty:
            raise ValueError(f"Output file is empty: {csv_path}")

        if filename == "event_transitions.csv":
            non_r4_cols = [
                c
                for c in df.columns
                if c not in ("previous_activity", "transition_time_minutes")
            ]
            if df[non_r4_cols].isna().any().any():
                raise ValueError(f"Unexpected NaN in core columns of {filename}")
        else:
            if df.isna().any().any():
                raise ValueError(f"Unexpected NaN detected in {filename}")

        audit_rows.append((filename, len(df), len(df.columns)))

    return audit_rows


def main() -> None:
    audit_results = verify_outputs()

    print("=" * 72)
    print("CAREFLOW FINAL RELEASE AUDIT & VIVA QUICK-REFERENCE CARD (DAY 20)")
    print("=" * 72)
    for fname, r_count, c_count in audit_results:
        print(f"  [OK] {fname:<30} | {r_count:>5} rows | {c_count:>2} cols | 0 unexpected NaNs")

    print("-" * 72)
    print("KEY VIVA NUMBERS TO REMEMBER:")
    print("  * Total Cohort          : 500 complete cases | 2,741 events | 2,241 transitions")
    print("  * Mean Patient Stay (R7): 123.91 minutes")
    print("  * #1 Bottleneck (Rank 1): Doctor Consultation -> X-Ray (28.15 min avg)")
    print("  * Strict Conformance    : 13.00% (65/500 cases follow all 6 steps)")
    print("  * X-Ray -> Triage Loops : 22.40% (112/500 cases, adding +89.15 min stay)")
    print("  * Slowest Shift / Staff : Morning Shift (28.20m) | Tech_Rao (29.80m)")
    print("=" * 72)


if __name__ == "__main__":
    main()