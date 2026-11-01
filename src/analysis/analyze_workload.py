"""Shift and staff resource workload & bottleneck analytics (Day 16).

Analyzes hospital handoff wait times, case volume, and rework loop-backs
broken down by operational shift (Morning, Evening, Night) and staff resource
to pinpoint when and where clinical delays occur in real-world operations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import src.common.schema as schema
except ImportError:
    schema = object()

COL_CASE_ID = getattr(schema, "COL_CASE_ID", "case_id")
COL_ACTIVITY = getattr(schema, "COL_ACTIVITY", "activity")
COL_RESOURCE = getattr(schema, "COL_RESOURCE", "resource")
COL_SHIFT = getattr(schema, "COL_SHIFT", "shift")
COL_PREVIOUS_ACTIVITY = getattr(schema, "COL_PREVIOUS_ACTIVITY", "previous_activity")
COL_TRANSITION_MINUTES = getattr(schema, "COL_TRANSITION_MINUTES", "transition_time_minutes")
OUTPUTS_DIR = Path(getattr(schema, "OUTPUTS_DIR", PROJECT_ROOT / "outputs"))


def compute_shift_resource_metrics(transitions_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transition wait times and loop-back rework rates by shift and resource."""
    trans_col = (
        COL_TRANSITION_MINUTES
        if COL_TRANSITION_MINUTES in transitions_df.columns
        else "transition_time_minutes"
    )
    prev_col = (
        COL_PREVIOUS_ACTIVITY
        if COL_PREVIOUS_ACTIVITY in transitions_df.columns
        else "previous_activity"
    )

    if COL_CASE_ID not in transitions_df.columns or COL_ACTIVITY not in transitions_df.columns:
        raise ValueError("Input DataFrame is missing required case_id or activity columns.")

    df = transitions_df.copy()

    # Tag loop-back transitions (R11): activity seen earlier in the same case, excluding immediate repeats (R10)
    prior_visits = df.groupby([COL_CASE_ID, COL_ACTIVITY]).cumcount() > 0
    is_immediate_repeat = df[prev_col].notna() & (df[COL_ACTIVITY] == df[prev_col])
    df["is_loop_back"] = prior_visits & (~is_immediate_repeat)

    # Filter to valid transitions (exclude first-event NaNs per R4)
    valid = df[df[trans_col].notna()].copy()
    if valid.empty:
        raise ValueError("No valid transitions found to analyze shift and resource workload.")

    records: list[dict[str, object]] = []

    for dimension_label, col_name in [("shift", COL_SHIFT), ("resource", COL_RESOURCE)]:
        if col_name not in valid.columns:
            continue

        for group_val, group_df in valid.groupby(col_name, dropna=False):
            transition_count = int(len(group_df))
            cases_touched = int(group_df[COL_CASE_ID].nunique())
            avg_wait = round(float(group_df[trans_col].mean()), 2)
            median_wait = round(float(group_df[trans_col].median()), 2)
            max_wait = round(float(group_df[trans_col].max()), 2)
            loopback_count = int(group_df["is_loop_back"].sum())
            loopback_rate_pct = (
                round((loopback_count / transition_count) * 100.0, 2) if transition_count else 0.0
            )

            pair_means = (
                group_df.groupby([prev_col, COL_ACTIVITY])[trans_col]
                .mean()
                .reset_index()
                .sort_values(trans_col, ascending=False)
            )
            top_pair_row = pair_means.iloc[0]
            top_bottleneck_pair = f"{top_pair_row[prev_col]} -> {top_pair_row[COL_ACTIVITY]}"
            top_bottleneck_avg = round(float(top_pair_row[trans_col]), 2)

            records.append(
                {
                    "dimension": dimension_label,
                    "group_name": str(group_val),
                    "cases_served": cases_touched,
                    "transition_count": transition_count,
                    "avg_wait_minutes": avg_wait,
                    "median_wait_minutes": median_wait,
                    "max_wait_minutes": max_wait,
                    "loopback_count": loopback_count,
                    "loopback_rate_pct": loopback_rate_pct,
                    "top_bottleneck_pair": top_bottleneck_pair,
                    "top_bottleneck_avg_min": top_bottleneck_avg,
                }
            )

    result_df = pd.DataFrame(records)
    if result_df.empty:
        raise ValueError("Neither 'shift' nor 'resource' columns were found in transitions data.")

    result_df = result_df.sort_values(
        ["dimension", "avg_wait_minutes", "transition_count"],
        ascending=[True, False, False],
        kind="stable",
    ).reset_index(drop=True)

    result_df["rank_in_dimension"] = (
        result_df.groupby("dimension")["avg_wait_minutes"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    return result_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze bottlenecks and rework by shift and staff resource."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=OUTPUTS_DIR / "event_transitions.csv",
        help="Path to event_transitions.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUTS_DIR / "shift_resource_metrics.csv",
        help="Path to write shift_resource_metrics.csv",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress console summary output."
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Transitions file not found: {args.input}. Run calculate_metrics.py first."
        )

    transitions_df = pd.read_csv(args.input)
    metrics_df = compute_shift_resource_metrics(transitions_df)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(args.output, index=False)

    if not args.quiet:
        print(f"Saved {len(metrics_df)} shift/resource workload rows to {args.output}")
        print(metrics_df.to_string(index=False))


if __name__ == "__main__":
    main()