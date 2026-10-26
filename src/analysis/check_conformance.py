import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # lets the script run directly

from src.analysis.discover_process import (  # noqa: E402
    flag_repeats_and_loopbacks,
    validate_transitions,
)
from src.common.schema import (  # noqa: E402
    COL_ACTIVITY,
    COL_CASE_ID,
    COL_TRANSITION_MINUTES,
    EVENT_TRANSITIONS_CSV,
    IDEAL_PATH,
    OUTPUTS_DIR,
)

CONFORMANCE_SUMMARY_CSV = OUTPUTS_DIR / "conformance_summary.csv"
IDEAL_PATH_STR = " -> ".join(IDEAL_PATH)
NO_STEPS = "(none)"  # not "None": pandas reads the word None back as an empty value


def classify_case_conformance(
    activities: list[str],
    repeat_count: int,
    loopback_count: int,
) -> tuple[bool, str, str, int]:
    """Compare a single case's ordered activity list against IDEAL_PATH.

    Returns:
        (is_conformant, deviation_type, skipped_steps, skipped_count)
    """
    if activities == IDEAL_PATH:
        return True, "conformant", NO_STEPS, 0

    act_set = set(activities)
    skipped = [act for act in IDEAL_PATH if act not in act_set]
    skipped_str = ", ".join(skipped) if skipped else NO_STEPS
    skipped_count = len(skipped)

    first_seen_ideal = [act for act in dict.fromkeys(activities) if act in IDEAL_PATH]
    expected_ideal_subseq = [act for act in IDEAL_PATH if act in act_set]
    is_out_of_order = first_seen_ideal != expected_ideal_subseq
    extra_acts = [act for act in act_set if act not in IDEAL_PATH]

    reasons = []
    if skipped:
        reasons.append("skipped_steps")
    if is_out_of_order:
        reasons.append("out_of_order")
    if extra_acts:
        reasons.append("extra_steps")
    if repeat_count > 0:
        reasons.append("repeat")
    if loopback_count > 0:
        reasons.append("loop_back")
    if not reasons:
        reasons.append("other_deviation")

    return False, "+".join(reasons), skipped_str, skipped_count


def summarise_conformance(events: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Evaluate conformance per case and aggregate pathway conformance metrics."""
    tagged = flag_repeats_and_loopbacks(events)

    case_rows = []
    for case_id, group in tagged.groupby(COL_CASE_ID, sort=False):
        acts = group[COL_ACTIVITY].tolist()
        rep_cnt = int(group["is_repeat"].sum())
        loop_cnt = int(group["is_loopback"].sum())
        dur = float(group[COL_TRANSITION_MINUTES].sum())
        is_conf, dev_type, skipped_str, skipped_cnt = classify_case_conformance(
            acts, rep_cnt, loop_cnt
        )
        case_rows.append(
            {
                COL_CASE_ID: case_id,
                "path": " -> ".join(acts),
                "is_conformant": is_conf,
                "deviation_type": dev_type,
                "skipped_steps": skipped_str,
                "skipped_count": skipped_cnt,
                "step_count": len(acts),
                "repeat_count": rep_cnt,
                "loopback_count": loop_cnt,
                "duration_minutes": dur,
            }
        )

    cases_df = pd.DataFrame(case_rows)
    total_cases = len(cases_df)
    conformant_cases = int(cases_df["is_conformant"].sum())
    non_conformant_cases = total_cases - conformant_cases

    conf_subset = cases_df[cases_df["is_conformant"]]["duration_minutes"]
    non_conf_subset = cases_df[~cases_df["is_conformant"]]["duration_minutes"]

    has_rework = (cases_df["repeat_count"] > 0) | (cases_df["loopback_count"] > 0)
    plain_subset = cases_df[~cases_df["is_conformant"] & ~has_rework]["duration_minutes"]  # deviate without rework
    rework_subset = cases_df[has_rework]["duration_minutes"]

    stats = {
        "total_cases": total_cases,
        "conformant_cases": conformant_cases,
        "non_conformant_cases": non_conformant_cases,
        "conformance_rate_pct": round(conformant_cases / total_cases * 100.0, 2) if total_cases else 0.0,
        "conformant_avg_minutes": round(float(conf_subset.mean()), 2) if not conf_subset.empty else 0.0,
        "non_conformant_avg_minutes": round(float(non_conf_subset.mean()), 2) if not non_conf_subset.empty else 0.0,
        "no_rework_cases": len(plain_subset),
        "no_rework_avg_minutes": round(float(plain_subset.mean()), 2) if not plain_subset.empty else 0.0,
        "rework_cases": len(rework_subset),
        "rework_avg_minutes": round(float(rework_subset.mean()), 2) if not rework_subset.empty else 0.0,
    }

    summary = (
        cases_df.groupby(
            [
                "path",
                "is_conformant",
                "deviation_type",
                "skipped_steps",
                "skipped_count",
                "step_count",
            ]
        )
        .agg(
            case_count=(COL_CASE_ID, "count"),
            avg_duration_minutes=("duration_minutes", "mean"),
            median_duration_minutes=("duration_minutes", "median"),
            has_repeat=("repeat_count", lambda s: bool((s > 0).any())),
            has_loopback=("loopback_count", lambda s: bool((s > 0).any())),
        )
        .reset_index()
    )

    summary["pct_cases"] = (summary["case_count"] / total_cases * 100.0).round(2) if total_cases else 0.0
    summary[["avg_duration_minutes", "median_duration_minutes"]] = summary[
        ["avg_duration_minutes", "median_duration_minutes"]
    ].round(2)
    summary["rank"] = summary["case_count"].rank(ascending=False, method="min").astype(int)

    cols = [
        "rank",
        "path",
        "is_conformant",
        "deviation_type",
        "skipped_steps",
        "skipped_count",
        "case_count",
        "pct_cases",
        "step_count",
        "avg_duration_minutes",
        "median_duration_minutes",
        "has_repeat",
        "has_loopback",
    ]
    summary = (
        summary[cols]
        .sort_values(
            ["rank", "is_conformant", "avg_duration_minutes", "path"],
            ascending=[True, False, False, True],
        )
        .reset_index(drop=True)
    )
    return summary, stats


def check_conformance(
    transitions_csv_path=EVENT_TRANSITIONS_CSV,
    output_path=CONFORMANCE_SUMMARY_CSV,
    quiet: bool = False,
) -> pd.DataFrame:
    transitions_csv_path = Path(transitions_csv_path)
    if not transitions_csv_path.exists():
        raise FileNotFoundError(f"{transitions_csv_path} not found. Run calculate_metrics.py first.")

    print(f"Loading transitions from {transitions_csv_path}...\n")
    events = pd.read_csv(transitions_csv_path, encoding="utf-8-sig")
    validate_transitions(events)

    summary, stats = summarise_conformance(events)

    if not quiet:
        print(f"Ideal Path: {IDEAL_PATH_STR}\n")
        print("--- Conformance Summary by Pathway ---")
        print(summary.to_string(index=False))

    print(
        f"\nSummary: {stats['conformant_cases']}/{stats['total_cases']} cases conformant "
        f"({stats['conformance_rate_pct']}%) | "
        f"{stats['non_conformant_cases']} non-conformant | "
        f"Conformant Avg: {stats['conformant_avg_minutes']} min vs "
        f"Non-Conformant Avg: {stats['non_conformant_avg_minutes']} min"
    )
    print(
        f"Non-conformant split: {stats['no_rework_cases']} deviate without rework "
        f"(avg {stats['no_rework_avg_minutes']} min) | {stats['rework_cases']} have a repeat or loop-back "
        f"(avg {stats['rework_avg_minutes']} min)"
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    print(f"Success: Saved conformance summary to {output_path}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare actual patient pathways against IDEAL_PATH (Day 11 Conformance Checking)."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=EVENT_TRANSITIONS_CSV,
        help=f"Path to event_transitions.csv (default: {EVENT_TRANSITIONS_CSV})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CONFORMANCE_SUMMARY_CSV,
        help=f"Where to write conformance_summary.csv (default: {CONFORMANCE_SUMMARY_CSV})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the full table printout; still prints the one-line summary.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    check_conformance(args.input, args.output, quiet=args.quiet)