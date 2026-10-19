import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # lets the script run directly

from src.common.schema import (  # noqa: E402
    COL_ACTIVITY,
    COL_CASE_ID,
    COL_FROM_ACTIVITY,
    COL_PREVIOUS_ACTIVITY,
    COL_TIMESTAMP,
    COL_TO_ACTIVITY,
    COL_TRANSITION_MINUTES,
    EVENT_TRANSITIONS_CSV,
    IDEAL_PATH,
    OUTPUTS_DIR,
    TIMESTAMP_FORMAT,
)

PROCESS_PATHS_CSV = OUTPUTS_DIR / "process_paths.csv"
REPEAT_LOOP_METRICS_CSV = OUTPUTS_DIR / "repeat_loop_metrics.csv"
PROCESS_MAP_EDGES_CSV = OUTPUTS_DIR / "process_map_edges.csv"

IDEAL_EDGES = set(zip(IDEAL_PATH[:-1], IDEAL_PATH[1:]))

REQUIRED_TRANSITION_COLUMNS = {
    COL_CASE_ID,
    COL_ACTIVITY,
    COL_TIMESTAMP,
    COL_PREVIOUS_ACTIVITY,
    COL_TRANSITION_MINUTES,
}


def validate_transitions(events: pd.DataFrame) -> None:
    """Fail fast with a clear message instead of silently mis-tagging bad input."""
    missing = REQUIRED_TRANSITION_COLUMNS - set(events.columns)
    if missing:
        raise ValueError(
            f"{EVENT_TRANSITIONS_CSV.name} is missing required column(s): {sorted(missing)}. "
            "Re-run calculate_metrics.py to regenerate it."
        )

    if events.empty:
        raise ValueError(f"{EVENT_TRANSITIONS_CSV.name} has no rows -- nothing to analyse.")

    case_col = events[COL_CASE_ID]
    block_count = (case_col != case_col.shift()).sum()
    if block_count != case_col.nunique():
        raise ValueError(
            f"{EVENT_TRANSITIONS_CSV.name} is not grouped by case: at least one "
            f"{COL_CASE_ID} value appears in more than one contiguous block."
        )

    timestamps = pd.to_datetime(events[COL_TIMESTAMP], format=TIMESTAMP_FORMAT, errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"{EVENT_TRANSITIONS_CSV.name} contains invalid timestamps.")
    if (timestamps.groupby(case_col, sort=False).diff().dt.total_seconds() < 0).any():
        raise ValueError(
            f"{EVENT_TRANSITIONS_CSV.name} has out-of-order timestamps within a case (violates R1)."
        )


def flag_repeats_and_loopbacks(events: pd.DataFrame) -> pd.DataFrame:
    """Tag each event with is_repeat (R10) and is_loopback (R11) within its case."""
    df = events.copy()
    is_repeat = []
    is_loopback = []

    for _, group in df.groupby(COL_CASE_ID, sort=False):
        seen = set()
        prev_act = None
        for act in group[COL_ACTIVITY]:
            if prev_act is not None and act == prev_act:
                is_repeat.append(True)
                is_loopback.append(False)
            elif act in seen:
                is_repeat.append(False)
                is_loopback.append(True)
            else:
                is_repeat.append(False)
                is_loopback.append(False)
            seen.add(act)
            prev_act = act

    df["is_repeat"] = is_repeat
    df["is_loopback"] = is_loopback
    return df


def summarise_paths(events: pd.DataFrame) -> pd.DataFrame:
    """Group complete cases by their full activity sequence and compute frequency and throughput (R7)."""
    tagged = flag_repeats_and_loopbacks(events)

    cases = (
        tagged.groupby(COL_CASE_ID, sort=False)
        .agg(
            path=(COL_ACTIVITY, lambda s: " -> ".join(s)),
            step_count=(COL_ACTIVITY, "count"),
            duration_minutes=(COL_TRANSITION_MINUTES, "sum"),
            repeat_count=("is_repeat", "sum"),
            loopback_count=("is_loopback", "sum"),
        )
        .reset_index()
    )

    total_cases = len(cases)
    paths = (
        cases.groupby("path")
        .agg(
            case_count=(COL_CASE_ID, "count"),
            step_count=("step_count", "first"),
            avg_duration_minutes=("duration_minutes", "mean"),
            median_duration_minutes=("duration_minutes", "median"),
            has_repeat=("repeat_count", lambda s: bool((s > 0).any())),
            has_loopback=("loopback_count", lambda s: bool((s > 0).any())),
        )
        .reset_index()
    )

    paths["pct_cases"] = (paths["case_count"] / total_cases * 100.0).round(2)
    paths[["avg_duration_minutes", "median_duration_minutes"]] = paths[
        ["avg_duration_minutes", "median_duration_minutes"]
    ].round(2)
    paths["rank"] = paths["case_count"].rank(ascending=False, method="min").astype(int)

    cols = [
        "rank",
        "path",
        "case_count",
        "pct_cases",
        "step_count",
        "avg_duration_minutes",
        "median_duration_minutes",
        "has_repeat",
        "has_loopback",
    ]
    return paths[cols].sort_values(
        ["rank", "avg_duration_minutes", "path"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def summarise_rework(events: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Summarise repeat (R10) and loop-back (R11) transitions and overall rework rate (R12)."""
    tagged = flag_repeats_and_loopbacks(events)
    total_cases = tagged[COL_CASE_ID].nunique()

    case_rework = tagged.groupby(COL_CASE_ID, sort=False).agg(
        has_repeat=("is_repeat", "any"),
        has_loopback=("is_loopback", "any"),
        duration_minutes=(COL_TRANSITION_MINUTES, "sum"),
    )
    loopback_cases = int(case_rework["has_loopback"].sum())
    repeat_cases = int(case_rework["has_repeat"].sum())
    stats = {
        "total_cases": total_cases,
        "loopback_cases": loopback_cases,
        "repeat_cases": repeat_cases,
        "rework_rate_pct": round(loopback_cases / total_cases * 100.0, 2) if total_cases else 0.0,
        "avg_throughput_minutes": round(float(case_rework["duration_minutes"].mean()), 2) if total_cases else 0.0,
    }

    rework_rows = tagged[tagged["is_repeat"] | tagged["is_loopback"]].copy()
    if rework_rows.empty:
        empty_df = pd.DataFrame(
            columns=[
                COL_FROM_ACTIVITY,
                COL_TO_ACTIVITY,
                "rework_type",
                "transition_count",
                "cases_affected",
                "pct_cases_affected",
                "avg_minutes",
                "median_minutes",
                "max_minutes",
            ]
        )
        return empty_df, stats

    rework_rows["rework_type"] = rework_rows["is_repeat"].map({True: "repeat", False: "loop_back"})
    summary = (
        rework_rows.groupby([COL_PREVIOUS_ACTIVITY, COL_ACTIVITY, "rework_type"])
        .agg(
            transition_count=(COL_CASE_ID, "count"),
            cases_affected=(COL_CASE_ID, "nunique"),
            avg_minutes=(COL_TRANSITION_MINUTES, "mean"),
            median_minutes=(COL_TRANSITION_MINUTES, "median"),
            max_minutes=(COL_TRANSITION_MINUTES, "max"),
        )
        .reset_index()
        .rename(columns={COL_PREVIOUS_ACTIVITY: COL_FROM_ACTIVITY, COL_ACTIVITY: COL_TO_ACTIVITY})
    )
    summary["pct_cases_affected"] = (summary["cases_affected"] / total_cases * 100.0).round(2)
    summary[["avg_minutes", "median_minutes", "max_minutes"]] = summary[
        ["avg_minutes", "median_minutes", "max_minutes"]
    ].round(2)

    cols = [
        COL_FROM_ACTIVITY,
        COL_TO_ACTIVITY,
        "rework_type",
        "transition_count",
        "cases_affected",
        "pct_cases_affected",
        "avg_minutes",
        "median_minutes",
        "max_minutes",
    ]
    summary = summary[cols].sort_values(
        ["transition_count", "avg_minutes", COL_FROM_ACTIVITY, COL_TO_ACTIVITY],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    return summary, stats


def summarise_process_map_edges(events: pd.DataFrame) -> pd.DataFrame:
    """Build directed edge table (from_activity -> to_activity) for the Day 10 process map."""
    tagged = flag_repeats_and_loopbacks(events)
    total_cases = tagged[COL_CASE_ID].nunique()
    transitions = tagged.dropna(subset=[COL_PREVIOUS_ACTIVITY, COL_TRANSITION_MINUTES]).copy()

    edges = (
        transitions.groupby([COL_PREVIOUS_ACTIVITY, COL_ACTIVITY])
        .agg(
            count=(COL_CASE_ID, "count"),
            case_count=(COL_CASE_ID, "nunique"),
            avg_minutes=(COL_TRANSITION_MINUTES, "mean"),
            median_minutes=(COL_TRANSITION_MINUTES, "median"),
            max_minutes=(COL_TRANSITION_MINUTES, "max"),
            loopback_count=("is_loopback", "sum"),
        )
        .reset_index()
        .rename(columns={COL_PREVIOUS_ACTIVITY: COL_FROM_ACTIVITY, COL_ACTIVITY: COL_TO_ACTIVITY})
    )

    edges["pct_cases"] = (edges["case_count"] / total_cases * 100.0).round(2) if total_cases else 0.0
    edges[["avg_minutes", "median_minutes", "max_minutes"]] = edges[
        ["avg_minutes", "median_minutes", "max_minutes"]
    ].round(2)
    edges["is_ideal_edge"] = edges.apply(
        lambda r: (r[COL_FROM_ACTIVITY], r[COL_TO_ACTIVITY]) in IDEAL_EDGES, axis=1
    )

    def _classify_edge(row) -> str:
        if row["is_ideal_edge"]:
            return "ideal"
        if row[COL_FROM_ACTIVITY] == row[COL_TO_ACTIVITY]:
            return "repeat"
        if row["loopback_count"] > 0:
            return "loop_back"
        return "deviation"

    edges["edge_type"] = edges.apply(_classify_edge, axis=1)

    cols = [
        COL_FROM_ACTIVITY,
        COL_TO_ACTIVITY,
        "count",
        "case_count",
        "pct_cases",
        "avg_minutes",
        "median_minutes",
        "max_minutes",
        "is_ideal_edge",
        "edge_type",
    ]
    return edges[cols].sort_values(
        ["count", "avg_minutes", COL_FROM_ACTIVITY, COL_TO_ACTIVITY],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)


def discover_process(
    transitions_csv_path=EVENT_TRANSITIONS_CSV,
    paths_output_path=PROCESS_PATHS_CSV,
    rework_output_path=REPEAT_LOOP_METRICS_CSV,
    edges_output_path=PROCESS_MAP_EDGES_CSV,
    quiet: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    transitions_csv_path = Path(transitions_csv_path)
    if not transitions_csv_path.exists():
        raise FileNotFoundError(f"{transitions_csv_path} not found. Run calculate_metrics.py first.")

    print(f"Loading transitions from {transitions_csv_path}...\n")
    events = pd.read_csv(transitions_csv_path, encoding="utf-8-sig")
    validate_transitions(events)

    paths_df = summarise_paths(events)
    rework_df, stats = summarise_rework(events)
    edges_df = summarise_process_map_edges(events)

    if not quiet:
        print("--- Patient Pathways (Most Frequent First) ---")
        print(paths_df.to_string(index=False))

        print("\n--- Repeat (R10) & Loop-Back (R11) Transitions ---")
        print(rework_df.to_string(index=False))

        print("\n--- Process Map Directed Edges ---")
        print(edges_df.to_string(index=False))

    print(
        f"\nSummary: {stats['total_cases']} cases | "
        f"{len(edges_df)} directed edges | "
        f"Avg Throughput (R7): {stats['avg_throughput_minutes']} min | "
        f"Rework Rate (R12): {stats['rework_rate_pct']}% ({stats['loopback_cases']}/{stats['total_cases']} cases)"
    )

    for out_path, df in [
        (Path(paths_output_path), paths_df),
        (Path(rework_output_path), rework_df),
        (Path(edges_output_path), edges_df),
    ]:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Success: Saved {out_path}")

    return paths_df, rework_df, edges_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover frequent patient pathways, rework metrics, and process map edges (R7, R10-R12)."
    )
    parser.add_argument(
        "--input", type=Path, default=EVENT_TRANSITIONS_CSV,
        help=f"Path to event_transitions.csv (default: {EVENT_TRANSITIONS_CSV})",
    )
    parser.add_argument(
        "--paths-output", type=Path, default=PROCESS_PATHS_CSV,
        help=f"Where to write process_paths.csv (default: {PROCESS_PATHS_CSV})",
    )
    parser.add_argument(
        "--rework-output", type=Path, default=REPEAT_LOOP_METRICS_CSV,
        help=f"Where to write repeat_loop_metrics.csv (default: {REPEAT_LOOP_METRICS_CSV})",
    )
    parser.add_argument(
        "--edges-output", type=Path, default=PROCESS_MAP_EDGES_CSV,
        help=f"Where to write process_map_edges.csv (default: {PROCESS_MAP_EDGES_CSV})",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress the full table printouts; still prints the one-line summary.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    discover_process(
        args.input,
        args.paths_output,
        args.rework_output,
        args.edges_output,
        quiet=args.quiet,
    )