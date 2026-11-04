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
COL_PREVIOUS_ACTIVITY = getattr(schema, "COL_PREVIOUS_ACTIVITY", "previous_activity")
COL_TRANSITION_MINUTES = getattr(schema, "COL_TRANSITION_MINUTES", "transition_time_minutes")
OUTPUTS_DIR = Path(getattr(schema, "OUTPUTS_DIR", PROJECT_ROOT / "outputs"))

SLA_TARGET_MINUTES = 120.0


def simulate_interventions(
    transitions_df: pd.DataFrame,
    sla_minutes: float = SLA_TARGET_MINUTES,
) -> pd.DataFrame:
    """Evaluate baseline vs. operational intervention scenarios across all cases."""
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
    valid = df[df[trans_col].notna()].copy()
    if valid.empty:
        raise ValueError("No valid transitions found to run intervention simulation.")

    # Identify Rank 1 bottleneck transitions (Doctor Consultation -> X-Ray)
    is_xray_handoff = (valid[prev_col] == "Doctor Consultation") & (valid[COL_ACTIVITY] == "X-Ray")

    # Identify loop-back transitions (R11) and repeated rework steps (excluding final Discharge)
    is_repeat = df[prev_col].notna() & (df[COL_ACTIVITY] == df[prev_col])
    prior_visits = df.groupby([COL_CASE_ID, COL_ACTIVITY]).cumcount() > 0
    df["_is_loopback"] = prior_visits & (~is_repeat)
    df["_cum_loopbacks"] = df.groupby(COL_CASE_ID)["_is_loopback"].cumsum()

    case_totals = valid.groupby(COL_CASE_ID)[trans_col].sum()
    xray_minutes = (
        valid[is_xray_handoff]
        .groupby(COL_CASE_ID)[trans_col]
        .sum()
        .reindex(case_totals.index, fill_value=0.0)
    )

    rework_events = df[
        (df["_cum_loopbacks"] > 0)
        & (df[COL_ACTIVITY] != "Discharge")
        & (df[trans_col].notna())
    ]
    rework_minutes = (
        rework_events.groupby(COL_CASE_ID)[trans_col]
        .sum()
        .reindex(case_totals.index, fill_value=0.0)
    )

    scenarios = [
        ("1. Baseline (Current Operations)", 0.0, 0.0),
        ("2. Fast-Track Radiology (-30% Consultation -> X-Ray Wait)", 0.30, 0.0),
        ("3. Rework Prevention (-50% X-Ray -> Triage Loop-Back Delay)", 0.0, 0.50),
        ("4. Combined Intervention (-30% X-Ray Wait & -50% Rework)", 0.30, 0.50),
        ("5. Zero-Rework Target (-30% X-Ray Wait & 100% Loop Elimination)", 0.30, 1.00),
    ]

    baseline_avg = float(case_totals.mean())
    baseline_breaches = int((case_totals > sla_minutes).sum())
    total_cases = len(case_totals)

    rows: list[dict[str, object]] = []
    for name, xray_reduction, rework_reduction in scenarios:
        sim_durations = (
            case_totals
            - (xray_minutes * xray_reduction)
            - (rework_minutes * rework_reduction)
        )
        avg_min = round(float(sim_durations.mean()), 2)
        median_min = round(float(sim_durations.median()), 2)
        p90_min = round(float(sim_durations.quantile(0.90)), 2)
        saved_per_case = round(baseline_avg - float(sim_durations.mean()), 2)
        total_hours_saved = round(float((case_totals - sim_durations).sum()) / 60.0, 2)
        breaches = int((sim_durations > sla_minutes).sum())
        breach_pct = round((breaches / total_cases) * 100.0, 2)
        breaches_prevented = baseline_breaches - breaches

        rows.append(
            {
                "scenario_name": name,
                "xray_wait_reduction_pct": round(xray_reduction * 100.0, 1),
                "rework_reduction_pct": round(rework_reduction * 100.0, 1),
                "avg_los_minutes": avg_min,
                "median_los_minutes": median_min,
                "p90_los_minutes": p90_min,
                "avg_minutes_saved_per_case": saved_per_case,
                "total_patient_hours_saved": total_hours_saved,
                "sla_120m_breach_count": breaches,
                "sla_120m_breach_pct": breach_pct,
                "sla_breaches_prevented": breaches_prevented,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate hospital capacity and rework interventions on patient throughput."
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
        default=OUTPUTS_DIR / "intervention_scenarios.csv",
        help="Path to write intervention_scenarios.csv",
    )
    parser.add_argument(
        "--sla-minutes",
        type=float,
        default=SLA_TARGET_MINUTES,
        help="Target maximum length of stay in minutes (default: 120.0).",
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
    scenarios_df = simulate_interventions(transitions_df, sla_minutes=args.sla_minutes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scenarios_df.to_csv(args.output, index=False)

    if not args.quiet:
        print(f"Saved {len(scenarios_df)} intervention scenarios to {args.output}")
        print(scenarios_df.to_string(index=False))


if __name__ == "__main__":
    main()