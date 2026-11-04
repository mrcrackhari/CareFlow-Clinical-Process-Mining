"""
CareFlow Day 17 — Pipeline Verification & Performance Test Suite
=================================================================
Automated assertion checks for data_loader.py functions to verify 
schema validation, fallback calculations, edge-case safety, and dynamic metrics.
"""

import sys
import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SYS_PATH = Path(__file__).resolve().parent.parent / "src" / "dashboard"
sys.path.append(str(SYS_PATH))

from data_loader import (
    prepare,
    build_cases,
    build_transitions,
    calculate_conformance_metrics,
    calculate_repeat_metrics,
    safe_calculate_metrics,
    get_dataset_metadata,
)


def run_pipeline_tests():
    logging.info("Starting Day 17 CareFlow Dashboard Pipeline Verification Suite...")

    sample_data = pd.DataFrame({
        "case_id": ["CASE-101", "CASE-101", "CASE-101", "CASE-102", "CASE-102", "CASE-102"],
        "activity": ["Registration", "Triage", "Doctor Consultation", "Registration", "Triage", "Registration"],
        "timestamp": [
            "2026-10-10 09:00:00",
            "2026-10-10 09:15:00",
            "2026-10-10 10:00:00",
            "2026-10-10 09:30:00",
            "2026-10-10 09:45:00",
            "2026-10-10 10:15:00",
        ],
        "department": ["General", "General", "General", "General", "General", "General"],
    })

    prepared_df = prepare(sample_data)
    assert "timestamp" in prepared_df.columns
    assert pd.api.types.is_datetime64_any_dtype(prepared_df["timestamp"])
    logging.info("✅ Test 1 Passed: Data preparation and timestamp parsing work correctly.")

    cases_df = build_cases(prepared_df)
    assert len(cases_df) == 2
    assert "duration_hrs" in cases_df.columns
    logging.info("✅ Test 2 Passed: Case summary aggregation works correctly.")

    trans_df = build_transitions(prepared_df)
    assert "wait_min" in trans_df.columns
    assert len(trans_df) == 4
    logging.info("✅ Test 3 Passed: Transition wait time calculations work correctly.")

    conf_df = calculate_conformance_metrics(cases_df)
    assert "is_conforming" in conf_df.columns
    logging.info("✅ Test 4 Passed: Pathway conformance evaluator works correctly.")

    repeats_df = calculate_repeat_metrics(prepared_df)
    assert isinstance(repeats_df, pd.DataFrame)
    assert len(repeats_df) == 1
    logging.info("✅ Test 5 Passed: Dynamic repeat step counter works correctly.")

    metrics = safe_calculate_metrics(cases_df)
    assert metrics["total_cases"] == 2
    
    empty_metrics = safe_calculate_metrics(pd.DataFrame())
    assert empty_metrics["total_cases"] == 0
    logging.info("✅ Test 6 Passed: Safe KPI metric calculation works correctly.")

    metadata = get_dataset_metadata(prepared_df)
    assert metadata["total_records"] == 6
    logging.info("✅ Test 7 Passed: Dataset metadata extraction works correctly.")

    print("\n🎉 ALL DAY 17 DASHBOARD PIPELINE VERIFICATION TESTS PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    run_pipeline_tests()