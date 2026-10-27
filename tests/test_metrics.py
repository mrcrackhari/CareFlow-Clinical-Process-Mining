
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lets the test file run directly

from src.analysis.calculate_metrics import (  # noqa: E402
    add_transition_times,
    calculate_transition_times,
    drop_incomplete_cases,
    load_event_log,
    sort_events,
)
from src.analysis.check_conformance import (  # noqa: E402
    NO_STEPS,
    check_conformance,
    classify_case_conformance,
    summarise_conformance,
)
from src.analysis.discover_process import (  # noqa: E402
    discover_process,
    flag_repeats_and_loopbacks,
    summarise_paths,
    summarise_process_map_edges,
    summarise_rework,
    validate_transitions as validate_discovery_transitions,
)
from src.analysis.find_bottlenecks import (  # noqa: E402
    analyze_bottlenecks,
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
    IDEAL_PATH,
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
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:15:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 08:45:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 09:00:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 09:30:00"),
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

    def test_empty_complete_cases_guard_prevents_overwriting_output(self):
        """If no complete cases remain after R8, raise ValueError before overwriting output."""
        csv_content = (
            "case_id,activity,timestamp\n"
            "CASE-0001,Triage,2024-01-15 08:10:00\n"
            "CASE-0001,Discharge,2024-01-15 08:30:00\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bad_input = tmp / "incomplete_only.csv"
            bad_input.write_text(csv_content, encoding="utf-8")
            existing_output = tmp / "event_transitions.csv"
            existing_output.write_text("KEEP_EXISTING_CONTENT", encoding="utf-8")

            with self.assertRaises(ValueError):
                calculate_transition_times(bad_input, existing_output)

            self.assertEqual(existing_output.read_text(encoding="utf-8"), "KEEP_EXISTING_CONTENT")


class TestBottlenecks(unittest.TestCase):
    """Hand-check pairwise wait-time averages, medians, max, tie ranks (R5), and validation."""

    def test_bottleneck_aggregation_and_tie_ranks(self):
        """Verify count, avg, median, max, and shared rank on tied averages."""
        raw = _make_df([
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:10:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:40:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 09:00:00"),
            ("CASE-0002", ACT_REGISTRATION, "2024-01-15 10:00:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 10:20:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 10:50:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 11:30:00"),
        ])
        transitions = add_transition_times(drop_incomplete_cases(sort_events(raw)))
        validate_bottleneck_transitions(transitions)
        summary = summarise_transitions(transitions)

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

    def test_validate_bottleneck_transitions_rejects_bad_activities_or_negative_waits(self):
        """Fail fast if an unrecognised activity name or negative transition time appears."""
        bad_act_df = pd.DataFrame({
            COL_CASE_ID: ["CASE-0001", "CASE-0001"],
            COL_ACTIVITY: [ACT_REGISTRATION, "Unknown_Step"],
            COL_PREVIOUS_ACTIVITY: [None, ACT_REGISTRATION],
            COL_TRANSITION_MINUTES: [None, 15.0],
        })
        with self.assertRaises(ValueError):
            validate_bottleneck_transitions(bad_act_df)

        neg_wait_df = pd.DataFrame({
            COL_CASE_ID: ["CASE-0001", "CASE-0001"],
            COL_ACTIVITY: [ACT_REGISTRATION, ACT_DISCHARGE],
            COL_PREVIOUS_ACTIVITY: [None, ACT_REGISTRATION],
            COL_TRANSITION_MINUTES: [None, -5.0],
        })
        with self.assertRaises(ValueError):
            validate_bottleneck_transitions(neg_wait_df)


class TestProcessDiscoveryAndRework(unittest.TestCase):
    """Hand-check repeat (R10), loop-back (R11), rework rate (R12), and process map edges."""

    def setUp(self):
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
            # CASE-0003 (duration = 60m, clean shortcut path)
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

        c1 = tagged[tagged[COL_CASE_ID] == "CASE-0001"]
        self.assertEqual(int(c1["is_repeat"].sum()), 0)
        self.assertEqual(int(c1["is_loopback"].sum()), 2)

        c2 = tagged[tagged[COL_CASE_ID] == "CASE-0002"]
        self.assertEqual(int(c2["is_repeat"].sum()), 1)
        self.assertEqual(int(c2["is_loopback"].sum()), 0)

    def test_vectorized_flagging_handles_interleaved_cases(self):
        """Vectorized flag_repeats_and_loopbacks tags each row accurately even if cases interleave."""
        interleaved = pd.DataFrame({
            COL_CASE_ID: ["C1", "C2", "C1", "C2", "C1", "C2"],
            COL_ACTIVITY: [
                ACT_REGISTRATION,
                ACT_REGISTRATION,
                ACT_TRIAGE,
                ACT_TRIAGE,
                ACT_TRIAGE,        # C1 immediate repeat (R10)
                ACT_REGISTRATION,  # C2 loop-back (R11)
            ],
        })
        tagged = flag_repeats_and_loopbacks(interleaved)
        self.assertEqual(tagged["is_repeat"].tolist(), [False, False, False, False, True, False])
        self.assertEqual(tagged["is_loopback"].tolist(), [False, False, False, False, False, True])

    def test_validate_discovery_transitions_rejects_split_cases(self):
        """validate_transitions raises ValueError if a case's rows are split into multiple blocks."""
        split_df = pd.DataFrame({
            COL_CASE_ID: ["CASE-0001", "CASE-0002", "CASE-0001"],
            COL_ACTIVITY: [ACT_REGISTRATION, ACT_REGISTRATION, ACT_DISCHARGE],
            COL_TIMESTAMP: ["2024-01-15 08:00:00", "2024-01-15 08:05:00", "2024-01-15 08:30:00"],
            COL_PREVIOUS_ACTIVITY: [None, None, ACT_REGISTRATION],
            COL_TRANSITION_MINUTES: [None, None, 30.0],
        })
        with self.assertRaises(ValueError):
            validate_discovery_transitions(split_df)

    def test_rework_rate_and_summary_r12(self):
        """R12: Rework rate counts only cases with >=1 loop-back (1 of 3 = 33.33%)."""
        rework_df, stats = summarise_rework(self.events)

        self.assertEqual(stats["total_cases"], 3)
        self.assertEqual(stats["loopback_cases"], 1)
        self.assertEqual(stats["repeat_cases"], 1)
        self.assertEqual(stats["rework_rate_pct"], 33.33)
        self.assertEqual(stats["avg_throughput_minutes"], 100.0)
        self.assertEqual(len(rework_df), 3)
        self.assertEqual(int(rework_df["transition_count"].sum()), 3)

    def test_summarise_paths_r7(self):
        """Verify pathway frequency, percentage, step count, and duration (R7)."""
        paths_df = summarise_paths(self.events)
        self.assertEqual(len(paths_df), 3)
        self.assertEqual(int(paths_df["case_count"].sum()), 3)
        self.assertAlmostEqual(float(paths_df["pct_cases"].sum()), 99.99, places=1)

    def test_process_map_edges_classification_and_loopback_count(self):
        """Day 10: Verify directed edge table classifies ideal, repeat, loop_back, and deviation edges."""
        edges_df = summarise_process_map_edges(self.events)
        edge_lookup = edges_df.set_index([COL_FROM_ACTIVITY, COL_TO_ACTIVITY])

        triage_consult = edge_lookup.loc[(ACT_TRIAGE, ACT_CONSULTATION)]
        self.assertEqual(int(triage_consult["count"]), 4)
        self.assertEqual(int(triage_consult["case_count"]), 3)
        self.assertTrue(bool(triage_consult["is_ideal_edge"]))
        self.assertEqual(triage_consult["edge_type"], "ideal")
        self.assertEqual(int(triage_consult["loopback_count"]), 1)

        xray_repeat = edge_lookup.loc[(ACT_XRAY, ACT_XRAY)]
        self.assertEqual(xray_repeat["edge_type"], "repeat")

        xray_triage = edge_lookup.loc[(ACT_XRAY, ACT_TRIAGE)]
        self.assertEqual(xray_triage["edge_type"], "loop_back")
        self.assertEqual(int(xray_triage["loopback_count"]), 1)


class TestConformanceChecking(unittest.TestCase):
    """Day 11: Verify conformance classification, NO_STEPS sentinel, and rework vs non-rework split."""

    def test_classify_case_conformance_all_deviation_types(self):
        """Directly verify classify_case_conformance across ideal, skipped, out_of_order, repeat, loop_back."""
        # 1. Exact ideal path
        self.assertEqual(
            classify_case_conformance(IDEAL_PATH, repeat_count=0, loopback_count=0),
            (True, "conformant", NO_STEPS, 0),
        )
        # 2. Skipped X-Ray and Doctor Review
        self.assertEqual(
            classify_case_conformance(
                [ACT_REGISTRATION, ACT_TRIAGE, ACT_CONSULTATION, ACT_DISCHARGE],
                repeat_count=0,
                loopback_count=0,
            ),
            (False, "skipped_steps", "X-Ray, Doctor Review", 2),
        )
        # 3. Out of order + skipped Doctor Review (X-Ray before Doctor Consultation)
        self.assertEqual(
            classify_case_conformance(
                [ACT_REGISTRATION, ACT_TRIAGE, ACT_XRAY, ACT_CONSULTATION, ACT_DISCHARGE],
                repeat_count=0,
                loopback_count=0,
            ),
            (False, "skipped_steps+out_of_order", "Doctor Review", 1),
        )

    def test_conformance_classification_and_rework_split(self):
        raw = _make_df([
            # CASE-0001: Exact 6-step IDEAL_PATH (duration = 100m, conformant)
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:15:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:35:00"),
            ("CASE-0001", ACT_XRAY, "2024-01-15 08:55:00"),
            ("CASE-0001", ACT_REVIEW, "2024-01-15 09:20:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 09:40:00"),
            # CASE-0002: Skipped X-Ray & Doctor Review without rework (duration = 60m)
            ("CASE-0002", ACT_REGISTRATION, "2024-01-15 10:00:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 10:15:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 10:35:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 11:00:00"),
            # CASE-0003: Loop-back rework case (duration = 140m)
            ("CASE-0003", ACT_REGISTRATION, "2024-01-15 12:00:00"),
            ("CASE-0003", ACT_TRIAGE, "2024-01-15 12:15:00"),
            ("CASE-0003", ACT_CONSULTATION, "2024-01-15 12:40:00"),
            ("CASE-0003", ACT_XRAY, "2024-01-15 13:05:00"),
            ("CASE-0003", ACT_TRIAGE, "2024-01-15 13:30:00"),
            ("CASE-0003", ACT_CONSULTATION, "2024-01-15 13:55:00"),
            ("CASE-0003", ACT_REVIEW, "2024-01-15 14:10:00"),
            ("CASE-0003", ACT_DISCHARGE, "2024-01-15 14:20:00"),
        ])
        events = add_transition_times(drop_incomplete_cases(sort_events(raw)))
        summary, stats = summarise_conformance(events)

        self.assertEqual(stats["total_cases"], 3)
        self.assertEqual(stats["conformant_cases"], 1)
        self.assertEqual(stats["non_conformant_cases"], 2)
        self.assertEqual(stats["conformance_rate_pct"], 33.33)
        self.assertEqual(stats["conformant_avg_minutes"], 100.0)
        self.assertEqual(stats["non_conformant_avg_minutes"], 100.0)
        self.assertEqual(stats["no_rework_cases"], 1)
        self.assertEqual(stats["no_rework_avg_minutes"], 60.0)
        self.assertEqual(stats["rework_cases"], 1)
        self.assertEqual(stats["rework_avg_minutes"], 140.0)

        conf_row = summary[summary["is_conformant"]].iloc[0]
        self.assertEqual(conf_row["skipped_steps"], NO_STEPS)


class TestEndToEndPipelineIntegration(unittest.TestCase):
    """Day 13: Full-run integration check across all 4 scripts and 6 output CSV files."""

    def test_full_pipeline_generates_all_six_outputs_and_cross_file_totals_match(self):
        raw_rows = [
            ("CASE-0001", ACT_REGISTRATION, "2024-01-15 08:00:00"),
            ("CASE-0001", ACT_TRIAGE, "2024-01-15 08:15:00"),
            ("CASE-0001", ACT_CONSULTATION, "2024-01-15 08:40:00"),
            ("CASE-0001", ACT_XRAY, "2024-01-15 09:05:00"),
            ("CASE-0001", ACT_REVIEW, "2024-01-15 09:30:00"),
            ("CASE-0001", ACT_DISCHARGE, "2024-01-15 09:55:00"),
            ("CASE-0002", ACT_REGISTRATION, "2024-01-15 10:00:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 10:20:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 10:45:00"),
            ("CASE-0002", ACT_XRAY, "2024-01-15 11:10:00"),
            ("CASE-0002", ACT_TRIAGE, "2024-01-15 11:35:00"),
            ("CASE-0002", ACT_CONSULTATION, "2024-01-15 12:00:00"),
            ("CASE-0002", ACT_DISCHARGE, "2024-01-15 12:30:00"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            event_log_csv = tmp / "event_log.csv"
            pd.DataFrame(
                raw_rows, columns=[COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP]
            ).to_csv(event_log_csv, index=False)

            transitions_csv = tmp / "event_transitions.csv"
            bottlenecks_csv = tmp / "bottleneck_metrics.csv"
            paths_csv = tmp / "process_paths.csv"
            rework_csv = tmp / "repeat_loop_metrics.csv"
            edges_csv = tmp / "process_map_edges.csv"
            conformance_csv = tmp / "conformance_summary.csv"

            calculate_transition_times(event_log_csv, transitions_csv)
            analyze_bottlenecks(transitions_csv, bottlenecks_csv, quiet=True)
            discover_process(transitions_csv, paths_csv, rework_csv, edges_csv, quiet=True)
            check_conformance(transitions_csv, conformance_csv, quiet=True)

            # 1. Verify all 5 summary CSVs exist, are non-empty, and have 0 NaN values when reloaded
            for summary_file in [bottlenecks_csv, paths_csv, rework_csv, edges_csv, conformance_csv]:
                self.assertTrue(summary_file.exists(), f"Missing {summary_file.name}")
                reloaded = pd.read_csv(summary_file)
                self.assertFalse(reloaded.empty, f"{summary_file.name} is empty")
                self.assertEqual(
                    int(reloaded.isna().sum().sum()),
                    0,
                    f"Unexpected NaN found when reloading {summary_file.name}",
                )

            # 2. Verify cross-file mathematical consistency across all 6 outputs
            et_df = pd.read_csv(transitions_csv)
            bn_df = pd.read_csv(bottlenecks_csv)
            pp_df = pd.read_csv(paths_csv)
            ed_df = pd.read_csv(edges_csv)
            cf_df = pd.read_csv(conformance_csv)

            expected_cases = et_df[COL_CASE_ID].nunique()
            self.assertEqual(int(pp_df["case_count"].sum()), expected_cases)
            self.assertEqual(int(cf_df["case_count"].sum()), expected_cases)

            expected_transitions = int(et_df[COL_TRANSITION_MINUTES].notna().sum())
            self.assertEqual(int(bn_df["count"].sum()), expected_transitions)
            self.assertEqual(int(ed_df["count"].sum()), expected_transitions)


if __name__ == "__main__":
    unittest.main(verbosity=2)