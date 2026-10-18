"""Unit tests and hand-checked verifications for CareFlow analysis metrics (Day 9).

Verifies rules R1-R12 from docs/analysis_methodology.md across:
    - src/analysis/calculate_metrics.py
    - src/analysis/find_bottlenecks.py
    - src/analysis/discover_process.py

Run from anywhere:
    python tests/test_metrics.py
    pytest tests/test_metrics.py -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lets the test file run directly

from src.analysis.calculate_metrics import (  # noqa: E402
    add_transition_times,
    drop_incomplete_cases,
    load_event_log,
    sort_events,
)
from src.analysis.discover_process import (  # noqa: E402
    flag_repeats_and_loopbacks,
    summarise_paths,
    summarise_rework,
)
from src.analysis.find_bottlenecks import (  # noqa: E402
    summarise_transitions,
    validate_transitions as validate_bottleneck_transitions,
)
from src.common.schema import (  # noqa: E402
    ACT_CONSULTATION,
    ACT_DISCHARGE,
    ACT_REGISTRATION,
    ACT_REVIEW,
    ACT_TRIAGE,
    ACT_XRAY,
    COL_ACTIVITY,
    COL_CASE_ID,
    COL_FROM_ACTIVITY,
    COL_PREVIOUS_ACTIVITY,
    COL_TIMESTAMP,
    COL_TO_ACTIVITY,
    COL_TRANSITION_MINUTES,
)


def _make_df(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Helper to build a raw event DataFrame from (case_id, activity, timestamp) tuples."""
    df = pd.DataFrame(rows, columns=[COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP])
    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP], format="%Y-%m-%d %H:%M:%S")
    return df


class TestCalculateMetrics(unittest.TestCase):
    """Verify sorting (R1), transition math (R3), first-event NaN (R4), and filtering (R8, R9)."""

    def test_worked_example_from_methodology(self):
        """Hand-check the 8-event worked example in docs/analysis_methodology.md (R3, R4, R7)."""
        raw = _make_df([
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:10:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:35:00"),
            ("CASE-0001", ACT_XRAY, "2024-01-15 08:50:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 09:20:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 09:40:00"),
            ("CASE-0001", ACT_REVIEW, "2024-01-15 10:10:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 10:25:00"),
        ])
        result = add_transition_times(drop_incomplete_cases(sort_events(raw)))

        # R4: First event must be NaN (empty), never 0
        self.assertTrue(pd.isna(result.loc[0, COL_PREVIOUS_ACTIVITY]))
        self.assertTrue(pd.isna(result.loc[0, COL_TRANSITION_MINUTES]))

        # R3: Consecutive transition times in minutes
        expected_minutes = [10.0, 25.0, 15.0, 30.0, 20.0, 30.0, 15.0]
        self.assertEqual(result[COL_TRANSITION_MINUTES].iloc[1:].tolist(), expected_minutes)

        # R7: Total case duration = 145 minutes
        self.assertEqual(result[COL_TRANSITION_MINUTES].sum(), 145.0)

    def test_sorting_and_midnight_crossing_with_decimals(self):
        """R1 & R3: Out-of-order rows are sorted; midnight crossover and seconds (2.5 min) work."""
        raw = _make_df([
            ("CASE-0001", ACT_DISCHARGE, "2024-01-16 00:15:00"),
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 23:47:30"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 23:50:00"),
        ])
        result = add_transition_times(drop_incomplete_cases(sort_events(raw)))

        self.assertEqual(
            result[COL_ACTIVITY].tolist(),
            [ACT_REGISTRATION, ACT_TRIAGE, ACT_DISCHARGE],
        )
        self.assertEqual(result[COL_TRANSITION_MINUTES].iloc[1:].tolist(), [2.5, 25.0])

    def test_drop_incomplete_cases_r8(self):
        """R8: Exclude any case that does not start with Registration and end with Discharge."""
        raw = _make_df([
            # Valid complete case
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:15:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 08:45:00"),
            # Missing Registration at start
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 09:00:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 09:30:00"),
            # Missing Discharge at end
            ("CASE-0003", ACT_REGISTRATION, "2024-01-15 10:00:00"),
            ("CASE-0003", ACT_TRIAGE, "2024-01-15 10:20:00"),
        ])
        cleaned = drop_incomplete_cases(sort_events(raw))
        self.assertEqual(cleaned[COL_CASE_ID].unique().tolist(), ["CASE-0001"])

    def test_skip_unusable_rows_r9(self):
        """R9: Rows with missing case_id, missing activity, or bad timestamp are skipped."""
        csv_content = (
            "case_id,activity,timestamp\n"
            "CASE-0001,Registration,2024-01-15 08:00:00\n"
            ",Triage,2024-01-15 08:10:00\n"
            "CASE-0001,,2024-01-15 08:20:00\n"
            "CASE-0001,Triage,not-a-timestamp\n"
            "CASE-0001,Discharge,2024-01-15 08:30:00\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "bad_rows.csv"
            csv_path.write_text(csv_content, encoding="utf-8")
            loaded = load_event_log(csv_path)
            self.assertEqual(len(loaded), 2)


class TestBottlenecks(unittest.TestCase):
    """Hand-check pairwise wait-time averages, medians, max, and tie-breaking ranks (R5)."""

    def test_bottleneck_aggregation_and_tie_ranks(self):
        """Verify count, avg, median, max, and shared rank on tied averages."""
        raw = _make_df([
            # Case 1: Reg -> Triage (10m), Triage -> Consult (30m), Consult -> Discharge (20m)
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:10:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:40:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 09:00:00"),
            # Case 2: Reg -> Triage (20m), Triage -> Consult (30m), Consult -> Discharge (40m)
            ("CASE-0002", ACT_REGISTRATION, "2024-01-15 10:00:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 10:20:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 10:50:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 11:30:00"),
        ])
        transitions = add_transition_times(drop_incomplete_cases(sort_events(raw)))
        validate_bottleneck_transitions(transitions)
        summary = summarise_transitions(transitions)

        # Both (Triage -> Doctor Consultation) and (Doctor Consultation -> Discharge) average 30.0 min
        # so both must share rank 1, and (Registration -> Triage) with avg 15.0 min must be rank 3.
        self.assertEqual(len(summary), 3)
        self.assertEqual(summary["rank"].tolist(), [1, 1, 3])

        consult_dis = summary[
            (summary[COL_FROM_ACTIVITY] == ACT_CONSULTATION)
            & (summary[COL_TO_ACTIVITY] == ACT_DISCHARGE)
        ].iloc[0]
        self.assertEqual(consult_dis["count"], 2)
        self.assertEqual(consult_dis["avg_minutes"], 30.0)
        self.assertEqual(consult_dis["median_minutes"], 30.0)
        self.assertEqual(consult_dis["max_minutes"], 40.0)


class TestProcessDiscoveryAndRework(unittest.TestCase):
    """Hand-check repeat (R10), loop-back (R11), rework rate (R12), and pathway summaries."""

    def setUp(self):
        # 3 complete cases:
        # CASE-0001: Worked example with 2 loop-back transitions (X-Ray -> Triage -> Doctor Consultation)
        # CASE-0002: Case with 1 immediate repeat (X-Ray -> X-Ray, 30 min) and no loop-back
        # CASE-0003: Clean ideal path (no repeat, no loop-back)
        raw = _make_df([
            # CASE-0001 (duration = 145m, 2 loop-backs)
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:10:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:35:00"),
            ("CASE-0001", ACT_XRAY, "2024-01-15 08:50:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 09:20:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 09:40:00"),
            ("CASE-0001", ACT_REVIEW, "2024-01-15 10:10:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 10:25:00"),
            # CASE-0002 (duration = 95m, 1 immediate repeat X-Ray -> X-Ray)
            ("CASE-0002", ACT_REGISTRATION, "2024-01-15 09:00:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 09:15:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 09:35:00"),
            ("CASE-0002", ACT_XRAY, "2024-01-15 09:50:00"),
            ("CASE-0002", ACT_XRAY, "2024-01-15 10:20:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 10:35:00"),
            # CASE-0003 (duration = 60m, clean path)
            ("CASE-0003", ACT_REGISTRATION, "2024-01-15 11:00:00"),
            ("CASE-0003", ACT_TRIAGE, "2024-01-15 11:15:00"),
            ("CASE-0003", ACT_CONSULTATION, "2024-01-15 11:35:00"),
            ("CASE-0003", ACT_DISCHARGE, "2024-01-15 12:00:00"),
        ])
        self.events = add_transition_times(drop_incomplete_cases(sort_events(raw)))

    def test_repeat_and_loopback_never_overlap_r10_r11(self):
        """R10 & R11: Immediate repeat and loop-back are mutually exclusive."""
        tagged = flag_repeats_and_loopbacks(self.events)
        overlap = tagged["is_repeat"] & tagged["is_loopback"]
        self.assertFalse(overlap.any())

        # CASE-0001 has 0 repeats and 2 loop-backs
        c1 = tagged[tagged[COL_CASE_ID] == "CASE-0001"]
        self.assertEqual(int(c1["is_repeat"].sum()), 0)
        self.assertEqual(int(c1["is_loopback"].sum()), 2)

        # CASE-0002 has 1 repeat (X-Ray -> X-Ray) and 0 loop-backs
        c2 = tagged[tagged[COL_CASE_ID] == "CASE-0002"]
        self.assertEqual(int(c2["is_repeat"].sum()), 1)
        self.assertEqual(int(c2["is_loopback"].sum()), 0)

    def test_rework_rate_and_summary_r12(self):
        """R12: Rework rate counts only cases with >=1 loop-back (1 of 3 = 33.33%)."""
        rework_df, stats = summarise_rework(self.events)

        self.assertEqual(stats["total_cases"], 3)
        self.assertEqual(stats["loopback_cases"], 1)
        self.assertEqual(stats["repeat_cases"], 1)
        self.assertEqual(stats["rework_rate_pct"], 33.33)
        # Avg throughput (R7) = (145 + 95 + 60) / 3 = 100.0 min
        self.assertEqual(stats["avg_throughput_minutes"], 100.0)

        # 3 distinct rework pairs: (X-Ray -> Triage, loop_back), (Triage -> Consult, loop_back), (X-Ray -> X-Ray, repeat)
        self.assertEqual(len(rework_df), 3)
        self.assertEqual(int(rework_df["transition_count"].sum()), 3)

    def test_summarise_paths_r7(self):
        """Verify pathway frequency, percentage, step count, and duration (R7)."""
        paths_df = summarise_paths(self.events)
        self.assertEqual(len(paths_df), 3)
        self.assertEqual(int(paths_df["case_count"].sum()), 3)
        self.assertAlmostEqual(float(paths_df["pct_cases"].sum()), 99.99, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)