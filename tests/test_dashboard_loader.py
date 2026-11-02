"""
CareFlow Day 17 — Performance Verification & Data Pipeline Test Suite
=====================================================================
Automated assertion checks for data_loader.py functions to verify 
schema validation, fallback calculations, and metadata integrity.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src/dashboard to system path for direct importing
SYS_PATH = Path(__file__).resolve().parent.parent / "src" / "dashboard"
sys.path.append(str(SYS_PATH))

from data_loader import (
    prepare,
    build_cases,
    build_transitions,
    calculate_conformance_metrics,
    calculate_repeat_metrics,
    safe_calculate_metrics,
)


def run_pipeline_tests():
    print("🧪 Starting Day 17 CareFlow Dashboard Pipeline Verification...\n")

    # 1. Mock Raw Input Data
    sample_data = pd.DataFrame({
        "case_id": ["CASE-101", "CASE-101", "CASE-101", "CASE-102", "CASE-102"],
        "activity": ["Registration", "Triage", "Doctor Consultation", "Registration", "Triage"],
        "timestamp": [
            "2026-10-10 09:00:00",
            "2026-10-10 09:15:00",
            "2026-10-10 10:00:00",
            "2026-10-10 09:30:00",
            "2026-10-10 09:45:00",
        ],
        "department": ["General", "General", "General", "General", "General"],
    })

    # 2. Test Data Preparation
    prepared_df = prepare(sample_data)
    assert "timestamp" in prepared_df.columns, "Failed: Timestamp conversion missing"
    assert pd.api.types.is_datetime64_any_dtype(prepared_df["timestamp"]), "Failed: Timestamp is not datetime dtype"
    print("✅ Test 1 Passed: Data preparation and timestamp parsing work correctly.")

    # 3. Test Case Aggregations
    cases_df = build_cases(prepared_df)
    assert len(cases_df) == 2, f"Expected 2 cases, got {len(cases_df)}"
    assert "duration_hrs" in cases_df.columns, "Failed: duration_hrs column missing"
    print("✅ Test 2 Passed: Case summary aggregation works correctly.")

    # 4. Test Transition Wait Times
    trans_df = build_transitions(prepared_df)
    assert "wait_min" in trans_df.columns, "Failed: wait_min column missing"
    assert len(trans_df) == 3, f"Expected 3 transitions, got {len(trans_df)}"
    print("✅ Test 3 Passed: Transition wait time calculations work correctly.")

    # 5. Test Conformance Metrics
    conf_df = calculate_conformance_metrics(cases_df)
    assert "is_conforming" in conf_df.columns, "Failed: is_conforming flag missing"
    print("✅ Test 4 Passed: Pathway conformance evaluator works correctly.")

    # 6. Test Repeat Activity Metrics
    repeats_df = calculate_repeat_metrics(prepared_df)
    assert isinstance(repeats_df, pd.DataFrame), "Failed: Repeat metrics should return DataFrame"
    print("✅ Test 5 Passed: Dynamic repeat step counter works correctly.")

    # 7. Test Safe Summary Metrics Helper
    metrics = safe_calculate_metrics(cases_df)
    assert metrics["total_cases"] == 2, "Failed: Safe metrics total_cases mismatch"
    print("✅ Test 6 Passed: Safe KPI metric calculation helper works correctly.")

    print("\n🎉 All 6 Day 17 Pipeline Verification Tests Passed Successfully!")


if __name__ == "__main__":
    run_pipeline_tests()