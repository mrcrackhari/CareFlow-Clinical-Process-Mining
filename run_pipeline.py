"""One-command end-to-end clinical process mining pipeline runner (Day 15).

Executes all four CareFlow analysis stages in sequence, verifies cross-file
data integrity across all 6 output CSVs, runs the automated test suite,
and prints a concise operational summary table in the terminal.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.common.schema as schema  # noqa: E402

COL_CASE_ID = getattr(schema, "COL_CASE_ID", "case_id")
COL_TRANSITION_MINUTES = getattr(schema, "COL_TRANSITION_MINUTES", "transition_time_minutes")
EVENT_LOG_PATH = Path(getattr(schema, "EVENT_LOG_PATH", PROJECT_ROOT / "data" / "event_log.csv"))
OUTPUTS_DIR = Path(getattr(schema, "OUTPUTS_DIR", PROJECT_ROOT / "outputs"))

PIPELINE_STAGES = [
    ("1/4 Calculate Transition Metrics", PROJECT_ROOT / "src" / "analysis" / "calculate_metrics.py", []),
    ("2/4 Identify Bottlenecks", PROJECT_ROOT / "src" / "analysis" / "find_bottlenecks.py", ["--quiet"]),
    ("3/4 Discover Process & Rework", PROJECT_ROOT / "src" / "analysis" / "discover_process.py", ["--quiet"]),
    ("4/4 Check Protocol Conformance", PROJECT_ROOT / "src" / "analysis" / "check_conformance.py", ["--quiet"]),
]

EXPECTED_OUTPUT_FILES = [
    "event_transitions.csv",
    "bottleneck_metrics.csv",
    "process_paths.csv",
    "repeat_loop_metrics.csv",
    "process_map_edges.csv",
    "conformance_summary.csv",
]


def run_stage(label: str, script_path: Path, extra_args: list[str], quiet: bool = False) -> float:
    """Run a single analysis script and return its execution time in seconds."""
    if not script_path.exists():
        raise FileNotFoundError(f"Missing pipeline script: {script_path}")

    start = time.perf_counter()
    cmd = [sys.executable, str(script_path), *extra_args]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)

    # Fallback if a script does not accept --quiet
    if result.returncode != 0 and "--quiet" in extra_args:
        cmd = [sys.executable, str(script_path)]
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)

    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"Stage '{label}' failed with exit code {result.returncode}")

    if not quiet:
        print(f"[PASS] {label} ({elapsed:.2f}s)")
    return elapsed


def verify_outputs(outputs_dir: Path = OUTPUTS_DIR) -> dict[str, object]:
    """Verify all 6 output CSVs exist, contain no unexpected NaNs, and reconcile totals."""
    for filename in EXPECTED_OUTPUT_FILES:
        file_path = outputs_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Expected output file missing: {file_path}")

    transitions_df = pd.read_csv(outputs_dir / "event_transitions.csv")
    bottlenecks_df = pd.read_csv(outputs_dir / "bottleneck_metrics.csv")
    paths_df = pd.read_csv(outputs_dir / "process_paths.csv")
    rework_df = pd.read_csv(outputs_dir / "repeat_loop_metrics.csv")
    edges_df = pd.read_csv(outputs_dir / "process_map_edges.csv")
    conformance_df = pd.read_csv(outputs_dir / "conformance_summary.csv")

    for name, df in [
        ("bottleneck_metrics.csv", bottlenecks_df),
        ("process_paths.csv", paths_df),
        ("repeat_loop_metrics.csv", rework_df),
        ("process_map_edges.csv", edges_df),
        ("conformance_summary.csv", conformance_df),
    ]:
        if df.isna().any().any():
            raise ValueError(f"Unexpected NaN detected in summary output: {name}")

    trans_col = COL_TRANSITION_MINUTES if COL_TRANSITION_MINUTES in transitions_df.columns else "transition_time_minutes"
    total_cases = int(transitions_df[COL_CASE_ID].nunique())
    total_events = int(len(transitions_df))
    total_transitions = int(transitions_df[trans_col].notna().sum())

    if "case_count" in paths_df.columns and int(paths_df["case_count"].sum()) != total_cases:
        raise ValueError("Case count mismatch between event_transitions.csv and process_paths.csv")
    if "case_count" in conformance_df.columns and int(conformance_df["case_count"].sum()) != total_cases:
        raise ValueError("Case count mismatch between event_transitions.csv and conformance_summary.csv")
    if "count" in bottlenecks_df.columns and int(bottlenecks_df["count"].sum()) != total_transitions:
        raise ValueError("Transition count mismatch between event_transitions.csv and bottleneck_metrics.csv")

    case_durations = transitions_df.groupby(COL_CASE_ID)[trans_col].sum()
    avg_throughput = round(float(case_durations.mean()), 2)

    top_row = bottlenecks_df.sort_values("rank").iloc[0] if "rank" in bottlenecks_df.columns else bottlenecks_df.iloc[0]
    avg_col = "avg_minutes" if "avg_minutes" in bottlenecks_df.columns else "avg_wait_minutes"
    top_bottleneck = f"{top_row['from_activity']} -> {top_row['to_activity']} ({top_row[avg_col]} min avg)"

    if "is_conformant" in conformance_df.columns:
        conf_cases = int(conformance_df.loc[conformance_df["is_conformant"] == True, "case_count"].sum())  # noqa: E712
    else:
        conf_cases = int(conformance_df.iloc[0]["case_count"])
    conf_pct = round((conf_cases / total_cases) * 100.0, 2) if total_cases else 0.0

    type_col = "rework_type" if "rework_type" in rework_df.columns else ("kind" if "kind" in rework_df.columns else None)
    cases_col = "cases_affected" if "cases_affected" in rework_df.columns else "case_count"
    if type_col:
        loop_rows = rework_df[rework_df[type_col] == "loop_back"]
        rework_cases = int(loop_rows[cases_col].sum()) if not loop_rows.empty else 0
    else:
        rework_cases = int(rework_df[cases_col].sum()) if not rework_df.empty else 0
    rework_pct = round((rework_cases / total_cases) * 100.0, 2) if total_cases else 0.0

    return {
        "total_cases": total_cases,
        "total_events": total_events,
        "total_transitions": total_transitions,
        "avg_throughput_min": avg_throughput,
        "top_bottleneck": top_bottleneck,
        "conformance_str": f"{conf_pct}% ({conf_cases}/{total_cases} cases)",
        "rework_str": f"{rework_pct}% ({rework_cases}/{total_cases} cases)",
    }


def run_unit_tests(quiet: bool = False) -> int:
    """Discover and run all unit tests under tests/."""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(PROJECT_ROOT / "tests"), pattern="test_*.py")
    stream = io.StringIO() if quiet else sys.stdout
    runner = unittest.TextTestRunner(stream=stream, verbosity=1 if not quiet else 0)
    result = runner.run(suite)
    if not result.wasSuccessful():
        if quiet:
            sys.stderr.write(stream.getvalue())
        raise RuntimeError("Automated unit tests failed.")
    return result.testsRun


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete CareFlow analysis pipeline.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running the unit test suite.")
    parser.add_argument("--quiet", action="store_true", help="Print only the final summary.")
    args = parser.parse_args()

    if not EVENT_LOG_PATH.exists():
        raise FileNotFoundError(f"Input event log not found at {EVENT_LOG_PATH}")

    if not args.quiet:
        print("=" * 72)
        print("CAREFLOW CLINICAL PROCESS MINING — PIPELINE ORCHESTRATOR")
        print("=" * 72)

    total_time = 0.0
    for label, script_path, extra_args in PIPELINE_STAGES:
        total_time += run_stage(label, script_path, extra_args, quiet=args.quiet)

    summary = verify_outputs(OUTPUTS_DIR)
    if not args.quiet:
        print("[PASS] Cross-file reconciliation & zero-NaN audit verified")

    if not args.skip_tests:
        tests_run = run_unit_tests(quiet=True)
        if not args.quiet:
            print(f"[PASS] Automated test suite ({tests_run}/{tests_run} tests passing)")

    print("-" * 72)
    print(f"Dataset Cohort      : {summary['total_cases']} cases | {summary['total_events']} events | {summary['total_transitions']} transitions")
    print(f"Mean Throughput (R7): {summary['avg_throughput_min']} minutes")
    print(f"Rank 1 Bottleneck   : {summary['top_bottleneck']}")
    print(f"Protocol Conformance: {summary['conformance_str']}")
    print(f"Hospital Rework Rate: {summary['rework_str']}")
    print(f"Pipeline Runtime    : {total_time:.2f}s (6 CSVs written to {OUTPUTS_DIR.name}/)")
    print("-" * 72)


if __name__ == "__main__":
    main()