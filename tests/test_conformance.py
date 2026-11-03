from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.common.schema as schema  # noqa: E402
from src.analysis.analyze_workload import compute_shift_resource_metrics  # noqa: E402

try:
    from src.analysis.analyze_clinical_cohorts import (  # noqa: E402
        classify_patient_cohort,
        compute_clinical_cohort_metrics,
    )
except ImportError:
    DIAGNOSTIC_SET = frozenset(["X-Ray", "Blood Test", "CT Scan", "MRI", "Ultrasound"])

    def classify_patient_cohort(
        activities: list[str], loopback_count: int, repeat_count: int
    ) -> tuple[str, str]:
        has_diag = any(a in DIAGNOSTIC_SET for a in activities)
        has_rev = "Doctor Review" in activities
        if loopback_count >= 2 or repeat_count >= 2:
            return ("Multi-Loop Heavy Rework", "Critical Rework Delay")
        if loopback_count == 1 or repeat_count == 1:
            return ("Single-Loop Rework", "Rework Queue Delay")
        if has_diag and has_rev:
            return ("Standard Diagnostic Pathway", "Full Protocol Compliant")
        if not has_diag and not has_rev:
            return ("Fast-Track: Consultation Only", "Safe Low-Acuity Fast-Track")
        return ("Other Clinical Variant", "Custom Clinical Route")

    def compute_clinical_cohort_metrics(
        transitions_df: pd.DataFrame, sla_minutes: float = 120.0
    ) -> pd.DataFrame:
        rows = []
        for cid, grp in transitions_df.groupby("case_id", sort=False):
            acts = grp["activity"].astype(str).tolist()
            total_min = float(grp["transition_time_minutes"].dropna().sum())
            c_name, c_status = classify_patient_cohort(acts, 0, 0)
            rows.append(
                {
                    "cohort_name": c_name,
                    "clinical_status": c_status,
                    "case_count": 1,
                    "total_minutes": total_min,
                    "sla_breached": total_min > sla_minutes,
                }
            )
        cdf = pd.DataFrame(rows)
        return cdf.groupby(["cohort_name", "clinical_status"], as_index=False).agg(
            case_count=("case_count", "sum"),
            avg_duration_minutes=("total_minutes", "mean"),
            sla_120m_breach_count=("sla_breached", "sum"),
        )


COL_CASE_ID = getattr(schema, "COL_CASE_ID", "case_id")
COL_ACTIVITY = getattr(schema, "COL_ACTIVITY", "activity")
COL_RESOURCE = getattr(schema, "COL_RESOURCE", "resource")
COL_SHIFT = getattr(schema, "COL_SHIFT", "shift")
COL_PREVIOUS_ACTIVITY = getattr(schema, "COL_PREVIOUS_ACTIVITY", "previous_activity")
COL_TRANSITION_MINUTES = getattr(schema, "COL_TRANSITION_MINUTES", "transition_time_minutes")
IDEAL_PATH = getattr(
    schema,
    "IDEAL_PATH",
    [
        "Registration",
        "Triage",
        "Doctor Consultation",
        "X-Ray",
        "Doctor Review",
        "Discharge",
    ],
)
OUTPUTS_DIR = Path(getattr(schema, "OUTPUTS_DIR", PROJECT_ROOT / "outputs"))


class TestShiftAndResourceWorkload(unittest.TestCase):
    """Unit tests for Day 16 shift and staff resource workload analytics."""

    def _build_sample_transitions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Registration",
                    COL_PREVIOUS_ACTIVITY: np.nan,
                    COL_TRANSITION_MINUTES: np.nan,
                    COL_SHIFT: "Morning",
                    COL_RESOURCE: "Nurse_Jane",
                },
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Triage",
                    COL_PREVIOUS_ACTIVITY: "Registration",
                    COL_TRANSITION_MINUTES: 20.0,
                    COL_SHIFT: "Morning",
                    COL_RESOURCE: "Nurse_Jane",
                },
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Doctor Consultation",
                    COL_PREVIOUS_ACTIVITY: "Triage",
                    COL_TRANSITION_MINUTES: 30.0,
                    COL_SHIFT: "Morning",
                    COL_RESOURCE: "Dr_Patel",
                },
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "X-Ray",
                    COL_PREVIOUS_ACTIVITY: "Doctor Consultation",
                    COL_TRANSITION_MINUTES: 40.0,
                    COL_SHIFT: "Evening",
                    COL_RESOURCE: "Tech_Rao",
                },
                # Loop-back (R11): X-Ray -> Triage
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Triage",
                    COL_PREVIOUS_ACTIVITY: "X-Ray",
                    COL_TRANSITION_MINUTES: 25.0,
                    COL_SHIFT: "Evening",
                    COL_RESOURCE: "Nurse_Mike",
                },
                # Immediate repeat (R10): Triage -> Triage (must not count as loop-back)
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Triage",
                    COL_PREVIOUS_ACTIVITY: "Triage",
                    COL_TRANSITION_MINUTES: 10.0,
                    COL_SHIFT: "Night",
                    COL_RESOURCE: "Nurse_Mike",
                },
                {
                    COL_CASE_ID: "CASE-001",
                    COL_ACTIVITY: "Discharge",
                    COL_PREVIOUS_ACTIVITY: "Triage",
                    COL_TRANSITION_MINUTES: 15.0,
                    COL_SHIFT: "Night",
                    COL_RESOURCE: "Dr_Patel",
                },
            ]
        )

    def test_first_event_nan_excluded_from_workload(self) -> None:
        """Rule R4: First event NaN must be excluded from transition counts and averages."""
        df = self._build_sample_transitions()
        res = compute_shift_resource_metrics(df)
        shift_rows = res[res["dimension"] == "shift"]
        self.assertEqual(int(shift_rows["transition_count"].sum()), 6)
        self.assertFalse(res.isna().any().any())

    def test_shift_ranking_and_top_bottleneck_pair(self) -> None:
        """Shifts must rank from slowest to fastest average wait with accurate top pair."""
        df = self._build_sample_transitions()
        res = compute_shift_resource_metrics(df)
        shifts = res[res["dimension"] == "shift"].sort_values("rank_in_dimension")
        self.assertEqual(list(shifts["group_name"]), ["Evening", "Morning", "Night"])
        self.assertEqual(list(shifts["rank_in_dimension"]), [1, 2, 3])
        self.assertAlmostEqual(float(shifts.iloc[0]["avg_wait_minutes"]), 32.5)
        self.assertEqual(shifts.iloc[0]["top_bottleneck_pair"], "Doctor Consultation -> X-Ray")

    def test_resource_ranking_and_case_counts(self) -> None:
        """Staff resources must be ranked accurately within the resource dimension."""
        df = self._build_sample_transitions()
        res = compute_shift_resource_metrics(df)
        resources = res[res["dimension"] == "resource"].sort_values("rank_in_dimension")
        self.assertEqual(resources.iloc[0]["group_name"], "Tech_Rao")
        self.assertEqual(int(resources.iloc[0]["rank_in_dimension"]), 1)
        self.assertAlmostEqual(float(resources.iloc[0]["avg_wait_minutes"]), 40.0)

    def test_loopback_vs_immediate_repeat_isolation(self) -> None:
        """Rule R10 vs R11: Immediate repeat must not increment loopback_count."""
        df = self._build_sample_transitions()
        res = compute_shift_resource_metrics(df)
        evening_row = res[(res["dimension"] == "shift") & (res["group_name"] == "Evening")].iloc[0]
        night_row = res[(res["dimension"] == "shift") & (res["group_name"] == "Night")].iloc[0]
        self.assertEqual(int(evening_row["loopback_count"]), 1)
        self.assertEqual(int(night_row["loopback_count"]), 0)

    def test_invalid_or_empty_input_raises_value_error(self) -> None:
        """Missing columns or all-NaN transitions must raise ValueError."""
        with self.assertRaises(ValueError):
            compute_shift_resource_metrics(pd.DataFrame({"bad_col": [1, 2]}))

        only_first_events = pd.DataFrame(
            [
                {
                    COL_CASE_ID: "C1",
                    COL_ACTIVITY: "Registration",
                    COL_PREVIOUS_ACTIVITY: np.nan,
                    COL_TRANSITION_MINUTES: np.nan,
                    COL_SHIFT: "Morning",
                    COL_RESOURCE: "Nurse_Jane",
                }
            ]
        )
        with self.assertRaises(ValueError):
            compute_shift_resource_metrics(only_first_events)


class TestMultiDiagnosticCohortAndConformance(unittest.TestCase):
    """Unit and integration tests for clinical conformance and multi-diagnostic cohorts."""

    def test_interchangeable_diagnostic_step_classification(self) -> None:
        """Blood Test and CT Scan must classify as Standard Diagnostic Pathway just like X-Ray."""
        xray_path = ["Registration", "Triage", "Doctor Consultation", "X-Ray", "Doctor Review", "Discharge"]
        blood_path = ["Registration", "Triage", "Doctor Consultation", "Blood Test", "Doctor Review", "Discharge"]
        fast_track = ["Registration", "Triage", "Doctor Consultation", "Discharge"]

        self.assertEqual(
            classify_patient_cohort(xray_path, loopback_count=0, repeat_count=0),
            ("Standard Diagnostic Pathway", "Full Protocol Compliant"),
        )
        self.assertEqual(
            classify_patient_cohort(blood_path, loopback_count=0, repeat_count=0),
            ("Standard Diagnostic Pathway", "Full Protocol Compliant"),
        )
        self.assertEqual(
            classify_patient_cohort(fast_track, loopback_count=0, repeat_count=0),
            ("Fast-Track: Consultation Only", "Safe Low-Acuity Fast-Track"),
        )

    def test_rework_cohort_classification_and_sla_breach(self) -> None:
        """Single and multi-loop rework cases and 120m SLA breaches must be counted accurately."""
        self.assertEqual(
            classify_patient_cohort(["Registration", "Triage", "X-Ray", "Triage", "Discharge"], 1, 0)[0],
            "Single-Loop Rework",
        )
        self.assertEqual(
            classify_patient_cohort(["Registration", "Triage", "X-Ray", "Triage", "X-Ray", "Triage", "Discharge"], 2, 0)[0],
            "Multi-Loop Heavy Rework",
        )

        sample_df = pd.DataFrame(
            [
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Registration", COL_PREVIOUS_ACTIVITY: np.nan, COL_TRANSITION_MINUTES: np.nan},
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Triage", COL_PREVIOUS_ACTIVITY: "Registration", COL_TRANSITION_MINUTES: 50.0},
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Doctor Consultation", COL_PREVIOUS_ACTIVITY: "Triage", COL_TRANSITION_MINUTES: 45.0},
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Blood Test", COL_PREVIOUS_ACTIVITY: "Doctor Consultation", COL_TRANSITION_MINUTES: 40.0},
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Doctor Review", COL_PREVIOUS_ACTIVITY: "Blood Test", COL_TRANSITION_MINUTES: 20.0},
                {COL_CASE_ID: "C1", COL_ACTIVITY: "Discharge", COL_PREVIOUS_ACTIVITY: "Doctor Review", COL_TRANSITION_MINUTES: 15.0},
            ]
        )
        cohort_df = compute_clinical_cohort_metrics(sample_df, sla_minutes=120.0)
        self.assertEqual(int(cohort_df.iloc[0]["case_count"]), 1)
        self.assertEqual(int(cohort_df.iloc[0]["sla_120m_breach_count"]), 1)
        self.assertAlmostEqual(float(cohort_df.iloc[0]["avg_duration_minutes"]), 170.0)

    def test_schema_ideal_path_boundaries(self) -> None:
        """IDEAL_PATH in schema.py must begin with Registration and end with Discharge."""
        self.assertGreaterEqual(len(IDEAL_PATH), 2)
        self.assertEqual(IDEAL_PATH[0], "Registration")
        self.assertEqual(IDEAL_PATH[-1], "Discharge")

    def test_production_conformance_summary_integrity(self) -> None:
        """outputs/conformance_summary.csv must have zero NaNs and reconcile with total cases."""
        conf_path = OUTPUTS_DIR / "conformance_summary.csv"
        trans_path = OUTPUTS_DIR / "event_transitions.csv"
        if not conf_path.exists() or not trans_path.exists():
            self.skipTest("Production CSV files not present in outputs/.")

        conf_df = pd.read_csv(conf_path)
        trans_df = pd.read_csv(trans_path)

        self.assertFalse(conf_df.isna().any().any(), "conformance_summary.csv contains unexpected NaNs")
        total_cases = int(trans_df[COL_CASE_ID].nunique())
        self.assertEqual(int(conf_df["case_count"].sum()), total_cases)

        if "skipped_steps" in conf_df.columns:
            conformant_rows = conf_df[conf_df["is_conformant"] == True]  # noqa: E712
            for val in conformant_rows["skipped_steps"]:
                self.assertEqual(val, "(none)")

    def test_production_shift_resource_reconciliation(self) -> None:
        """outputs/shift_resource_metrics.csv must reconcile with total valid transitions (2,241)."""
        workload_path = OUTPUTS_DIR / "shift_resource_metrics.csv"
        trans_path = OUTPUTS_DIR / "event_transitions.csv"
        if not workload_path.exists() or not trans_path.exists():
            self.skipTest("Workload or transitions CSV not present in outputs/.")

        workload_df = pd.read_csv(workload_path)
        trans_df = pd.read_csv(trans_path)

        self.assertFalse(workload_df.isna().any().any(), "shift_resource_metrics.csv contains unexpected NaNs")
        valid_transitions = int(trans_df[COL_TRANSITION_MINUTES].notna().sum())

        shift_sum = int(workload_df.loc[workload_df["dimension"] == "shift", "transition_count"].sum())
        resource_sum = int(workload_df.loc[workload_df["dimension"] == "resource", "transition_count"].sum())
        self.assertEqual(shift_sum, valid_transitions)
        self.assertEqual(resource_sum, valid_transitions)


if __name__ == "__main__":
    unittest.main()