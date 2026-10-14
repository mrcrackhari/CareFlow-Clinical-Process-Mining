"""Rank activity-to-activity transitions by how long they take.

Reads outputs/event_transitions.csv (made by calculate_metrics.py) and writes
outputs/bottleneck_metrics.csv: one row per (from_activity -> to_activity)
pair, longest average first. Rank 1 is the longest average; equal averages
share a rank.

Run from anywhere:  python src/analysis/find_bottlenecks.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # lets the script run directly

from src.common.schema import (  # noqa: E402
    BOTTLENECK_METRICS_CSV,
    COL_ACTIVITY,
    COL_FROM_ACTIVITY,
    COL_PREVIOUS_ACTIVITY,
    COL_TO_ACTIVITY,
    COL_TRANSITION_MINUTES,
    EVENT_TRANSITIONS_CSV,
)

MINUTE_COLUMNS = ["avg_minutes", "median_minutes", "max_minutes"]


def summarise_transitions(events: pd.DataFrame) -> pd.DataFrame:
    """Count, average, median and maximum transition time for every pair of consecutive activities.

    First events of a case have no previous activity, so they are not transitions and are left out.
    """
    transitions = events.dropna(subset=[COL_PREVIOUS_ACTIVITY, COL_TRANSITION_MINUTES])
    summary = (
        transitions.groupby([COL_PREVIOUS_ACTIVITY, COL_ACTIVITY])[COL_TRANSITION_MINUTES]
        .agg(count="count", avg_minutes="mean", median_minutes="median", max_minutes="max")
        .reset_index()
        .rename(columns={COL_PREVIOUS_ACTIVITY: COL_FROM_ACTIVITY, COL_ACTIVITY: COL_TO_ACTIVITY})
    )
    summary[MINUTE_COLUMNS] = summary[MINUTE_COLUMNS].round(2)
    summary["rank"] = summary["avg_minutes"].rank(ascending=False, method="min").astype(int)
    return summary.sort_values(
        ["rank", "count", COL_FROM_ACTIVITY, COL_TO_ACTIVITY],
        ascending=[True, False, True, True],
    ).reset_index(drop=True)


def analyze_bottlenecks(metrics_csv_path=EVENT_TRANSITIONS_CSV, output_path=BOTTLENECK_METRICS_CSV) -> pd.DataFrame:
    metrics_csv_path = Path(metrics_csv_path)
    if not metrics_csv_path.exists():
        raise FileNotFoundError(f"{metrics_csv_path} not found. Run calculate_metrics.py first.")

    print(f"Loading metrics from {metrics_csv_path}...\n")
    summary = summarise_transitions(pd.read_csv(metrics_csv_path))

    print("--- Transition times, longest average first ---")
    print(summary.to_string(index=False))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    print(f"\nSuccess: Bottleneck report saved to {output_path}")
    return summary


if __name__ == "__main__":
    analyze_bottlenecks()
