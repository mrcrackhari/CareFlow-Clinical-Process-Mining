import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # lets the script run directly

from src.common.schema import (  # noqa: E402
    BOTTLENECK_METRICS_CSV,
    COL_ACTIVITY,
    COL_CASE_ID,
    COL_FROM_ACTIVITY,
    COL_PREVIOUS_ACTIVITY,
    COL_TO_ACTIVITY,
    COL_TRANSITION_MINUTES,
    EVENT_TRANSITIONS_CSV,
    VALID_ACTIVITIES,
)

MINUTE_COLUMNS = ["avg_minutes", "median_minutes", "max_minutes"]
REQUIRED_TRANSITION_COLUMNS = {
    COL_CASE_ID,
    COL_ACTIVITY,
    COL_PREVIOUS_ACTIVITY,
    COL_TRANSITION_MINUTES,
}


def validate_transitions(events: pd.DataFrame) -> None:
    """Verify required columns, non-empty transitions, valid activities, and non-negative waits."""
    missing = REQUIRED_TRANSITION_COLUMNS - set(events.columns)
    if missing:
        raise ValueError(
            f"{EVENT_TRANSITIONS_CSV.name} is missing required column(s): {sorted(missing)}. "
            "Re-run calculate_metrics.py to regenerate it."
        )

    if events.empty:
        raise ValueError(f"{EVENT_TRANSITIONS_CSV.name} has no rows -- nothing to analyse.")

    transitions = events.dropna(subset=[COL_PREVIOUS_ACTIVITY, COL_TRANSITION_MINUTES])
    if transitions.empty:
        raise ValueError(f"{EVENT_TRANSITIONS_CSV.name} has no valid activity-to-activity transitions.")

    invalid_from = set(transitions[COL_PREVIOUS_ACTIVITY]) - set(VALID_ACTIVITIES)
    invalid_to = set(transitions[COL_ACTIVITY]) - set(VALID_ACTIVITIES)
    invalid_acts = sorted(invalid_from | invalid_to)
    if invalid_acts:
        raise ValueError(f"Unrecognised activity name(s) outside schema contract: {invalid_acts}")

    if (transitions[COL_TRANSITION_MINUTES] < 0).any():
        raise ValueError("Negative transition_time_minutes detected; ensure events are sorted (R1).")


def summarise_transitions(events: pd.DataFrame) -> pd.DataFrame:
    """Count, average, median and maximum transition time for every pair of consecutive activities (R5).

    First events of a case have no previous activity (R4), so they are not transitions and are left out.
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


def analyze_bottlenecks(
    metrics_csv_path=EVENT_TRANSITIONS_CSV,
    output_path=BOTTLENECK_METRICS_CSV,
    quiet: bool = False,
) -> pd.DataFrame:
    metrics_csv_path = Path(metrics_csv_path)
    if not metrics_csv_path.exists():
        raise FileNotFoundError(f"{metrics_csv_path} not found. Run calculate_metrics.py first.")

    print(f"Loading metrics from {metrics_csv_path}...\n")
    events = pd.read_csv(metrics_csv_path, encoding="utf-8-sig")
    validate_transitions(events)
    summary = summarise_transitions(events)

    if not quiet:
        print("--- Transition times, longest average first ---")
        print(summary.to_string(index=False))

    top_row = summary.iloc[0]
    total_transitions = int(summary["count"].sum())
    print(
        f"\nSummary: {total_transitions} transitions across {len(summary)} pairs | "
        f"Rank 1 Bottleneck: {top_row[COL_FROM_ACTIVITY]} -> {top_row[COL_TO_ACTIVITY]} "
        f"(avg {top_row['avg_minutes']} min, max {top_row['max_minutes']} min)"
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    print(f"Success: Bottleneck report saved to {output_path}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank activity-to-activity transitions by average and maximum wait times (R5)."
    )
    parser.add_argument(
        "--input", type=Path, default=EVENT_TRANSITIONS_CSV,
        help=f"Path to event_transitions.csv (default: {EVENT_TRANSITIONS_CSV})",
    )
    parser.add_argument(
        "--output", type=Path, default=BOTTLENECK_METRICS_CSV,
        help=f"Where to write bottleneck_metrics.csv (default: {BOTTLENECK_METRICS_CSV})",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress the full table printout; still prints the one-line summary.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    analyze_bottlenecks(args.input, args.output, quiet=args.quiet)