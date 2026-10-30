"""
tests/test_data_validation.py
Day 11 Deliverable — Pytest suite for the data validator.
"""
import pytest
import csv
import os
import sys

# Ensure the root directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.validate_events import run_checks
from src.common.schema import EXPECTED_COLUMNS

CLEAN_LOG = "data/event_log.csv"
DIRTY_LOG = "data/event_log_dirty.csv"

def load_csv(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = reader.fieldnames or []
    return rows, cols

def test_clean_data_passes_all_checks():
    """The clean event log should pass 100% of the validation checks."""
    assert os.path.exists(CLEAN_LOG), f"Missing {CLEAN_LOG}"
    
    rows, cols = load_csv(CLEAN_LOG)
    results = run_checks(rows, cols)
    
    for check_name, checked, failed in results:
        assert failed == 0, f"Clean data failed check '{check_name}' with {failed} errors."

def test_dirty_data_catches_all_defects():
    """The dirty event log (7 planted defects) should fail exactly 7 times."""
    assert os.path.exists(DIRTY_LOG), f"Missing {DIRTY_LOG}. Run 'python -m src.data.generate_events --mode dirty' first."
    
    rows, cols = load_csv(DIRTY_LOG)
    results = run_checks(rows, cols)
    
    failed_checks = [r[0] for r in results if r[2] > 0]
    
    assert len(failed_checks) == 7, f"Expected 7 failed checks on dirty data, but got {len(failed_checks)}: {failed_checks}"

def test_required_columns():
    """Ensure the schema matches the contract."""
    rows, cols = load_csv(CLEAN_LOG)
    for required in EXPECTED_COLUMNS:
        assert required in cols, f"Missing required column: {required}"