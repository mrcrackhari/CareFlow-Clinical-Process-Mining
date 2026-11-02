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

# Interchangeable diagnostic activities supported in real clinical workflows
DIAGNOSTIC_ACTIVITIES = frozenset(
    getattr(
        schema,
        "DIAGNOSTIC_ACTIVITIES",
        ["X-Ray", "Blood Test", "CT Scan", "MRI", "Ultrasound"],
    )
)
SLA_TARGET_MINUTES = 120.0


def classify_patient_cohort(
    activities: list[str], loopback_count: int, repeat_count: int
) -> tuple[str, str]:
    """Classify a single patient's activity sequence into a real-world clinical cohort."""
    has_diagnostic = any(act in DIAGNOSTIC_ACTIVITIES for act in activities)
    has_review = "Doctor Review" in activities

    if loopback_count >= 2 or repeat_count >= 2:
        return ("Multi-Loop Heavy Rework", "Critical Rework Delay")
    if loopback_count == 1 or repeat_count == 1:
        return ("Single-Loop Rework", "Rework Queue Delay")
    if has_diagnostic and has_review:
        return ("Standard Diagnostic Pathway", "Full Protocol Compliant")
    if not has_diagnostic and not has_review:
        return ("Fast-Track: Consultation Only", "Safe Low-Acuity Fast-Track")
    if not has_diagnostic and has_review:
        return ("Fast-Track: Direct Review (No Imaging)", "Safe Non-Imaging Fast-Track")
    if has_diagnostic and not has_review:
        return ("Fast-Track: Direct Diagnostic Discharge", "Accelerated Diagnostic Track")
    return ("Other Clinical Variant", "Custom Clinical Route")


def compute_clinical_cohort_metrics(
    transitions_df: pd.DataFrame,
    sla_minutes: float = SLA_TARGET_MINUTES,
) -> pd.DataFrame:
    """Compute throughput, P90 duration, and SLA breach rates across clinical cohorts."""
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

    # Vectorized R10 (immediate repeat) and R11 (loop-back) tagging
    is_repeat = df[prev_col].notna() & (df[COL_ACTIVITY] == df[prev_col])
    prior_visits = df.groupby([COL_CASE_ID, COL_ACTIVITY]).cumcount() > 0
    is_loopback = prior_visits & (~is_repeat)

    df["_is_repeat"] = is_repeat
    df["_is_loopback"] = is_loopback

    case_records: list[dict[str, object]] = []
    for case_id, group in df.groupby(COL_CASE_ID, sort=False):
        activities = group[COL_ACTIVITY].astype(str).tolist()
        total_minutes = float(group[trans_col].dropna().sum())
        loops = int(group["_is_loopback"].sum())
        repeats = int(group["_is_repeat"].sum())
        diagnostics_used = sorted({act for act in activities if act in DIAGNOSTIC_ACTIVITIES})

        cohort_name, clinical_status = classify_patient_cohort(activities, loops, repeats)
        case_records.append(
            {
                "case_id": case_id,
                "cohort_name": cohort_name,
                "clinical_status": clinical_status,
                "diagnostic_type": ", ".join(diagnostics_used) if diagnostics_used else "(none)",
                "step_count": len(activities),
                "total_minutes": total_minutes,
                "sla_breached": total_minutes > sla_minutes,
            }
        )

    cases_df = pd.DataFrame(case_records)
    total_cases = len(cases_df)
    if total_cases == 0:
        raise ValueError("No complete cases found to compute clinical cohort metrics.")

    summary_rows: list[dict[str, object]] = []
    for (cohort_name, clinical_status), grp in cases_df.groupby(
        ["cohort_name", "clinical_status"], sort=False
    ):
        count = int(len(grp))
        share_pct = round((count / total_cases) * 100.0, 2)
        avg_min = round(float(grp["total_minutes"].mean()), 2)
        median_min = round(float(grp["total_minutes"].median()), 2)
        p90_min = round(float(grp["total_minutes"].quantile(0.90)), 2)
        max_min = round(float(grp["total_minutes"].max()), 2)
        avg_steps = round(float(grp["step_count"].mean()), 2)
        breach_count = int(grp["sla_breached"].sum())
        breach_pct = round((breach_count / count) * 100.0, 2)
        diag_mode = str(grp["diagnostic_type"].mode().iloc[0])

        summary_rows.append(
            {
                "cohort_name": cohort_name,
                "clinical_status": clinical_status,
                "primary_diagnostic": diag_mode,
                "case_count": count,
                "percentage": share_pct,
                "avg_steps": avg_steps,
                "avg_duration_minutes": avg_min,
                "median_duration_minutes": median_min,
                "p90_duration_minutes": p90_min,
                "max_duration_minutes": max_min,
                "sla_120m_breach_count": breach_count,
                "sla_120m_breach_pct": breach_pct,
            }
        )

    result_df = (
        pd.DataFrame(summary_rows)
        .sort_values(["avg_duration_minutes", "case_count"], ascending=[False, False], kind="stable")
        .reset_index(drop=True)
    )
    return result_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze multi-diagnostic clinical cohorts and ED SLA breaches."
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
        default=OUTPUTS_DIR / "clinical_cohort_metrics.csv",
        help="Path to write clinical_cohort_metrics.csv",
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
    cohort_df = compute_clinical_cohort_metrics(transitions_df, sla_minutes=args.sla_minutes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cohort_df.to_csv(args.output, index=False)

    if not args.quiet:
        print(f"Saved {len(cohort_df)} clinical cohorts to {args.output}")
        print(cohort_df.to_string(index=False))


if __name__ == "__main__":
    main()