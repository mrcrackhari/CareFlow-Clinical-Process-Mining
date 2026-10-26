import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # lets the script run directly

from src.common.schema import (  # noqa: E402
    COL_ACTIVITY,
    COL_CASE_ID,
    COL_PREVIOUS_ACTIVITY,
    COL_TIMESTAMP,
    COL_TRANSITION_MINUTES,
    END_ACTIVITY,
    EVENT_LOG,
    EVENT_TRANSITIONS_CSV,
    REQUIRED_COLUMNS,
    START_ACTIVITY,
    TIMESTAMP_FORMAT,
)

MAX_IDS_SHOWN = 10


def load_event_log(csv_path) -> pd.DataFrame:
    """Read the event log, keeping only rows with a case ID, an activity and a valid timestamp (R9)."""
    if not Path(csv_path).exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Copy Member 1's file with "
            "'git checkout origin/member1-data -- data/event_log.csv', or give another path: "
            "python src/analysis/calculate_metrics.py data/sample_event_log.csv"
        )
    df = pd.read_csv(csv_path, encoding="utf-8-sig")  # also reads files saved with a Windows BOM
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} is missing required columns: {missing}")

    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP], format=TIMESTAMP_FORMAT, errors="coerce")
    unusable = df[REQUIRED_COLUMNS].isna().any(axis=1)
    if unusable.any():
        print(f"WARNING: skipped {unusable.sum()} row(s) with a missing case_id/activity or an invalid timestamp")
        df = df[~unusable]
    if df.empty:
        raise ValueError(f"{csv_path} has no usable rows (timestamps must look like 2023-10-01 08:00:00)")
    return df


def sort_events(df: pd.DataFrame) -> pd.DataFrame:
    """R1: case by case, oldest event first. Equal timestamps keep their recorded order."""
    return df.sort_values([COL_CASE_ID, COL_TIMESTAMP], kind="stable").reset_index(drop=True)


def drop_incomplete_cases(df: pd.DataFrame) -> pd.DataFrame:
    """R8: keep only cases that start with START_ACTIVITY and end with END_ACTIVITY (after sorting).

    A safety net for bad rows, e.g. a Discharge timestamped before the Registration.
    """
    by_case = df.groupby(COL_CASE_ID)[COL_ACTIVITY]
    complete = (by_case.first() == START_ACTIVITY) & (by_case.last() == END_ACTIVITY)
    excluded = list(complete.index[~complete])
    if excluded:
        shown = ", ".join(excluded[:MAX_IDS_SHOWN]) + (" ..." if len(excluded) > MAX_IDS_SHOWN else "")
        print(f"WARNING: excluded {len(excluded)} case(s) that do not run {START_ACTIVITY} -> {END_ACTIVITY}: {shown}")
    return df[~df[COL_CASE_ID].isin(excluded)].reset_index(drop=True)


def add_transition_times(df: pd.DataFrame) -> pd.DataFrame:
    """R3 + R4: previous activity and minutes since it, within each case. First events stay empty."""
    by_case = df.groupby(COL_CASE_ID)
    df[COL_PREVIOUS_ACTIVITY] = by_case[COL_ACTIVITY].shift()
    df[COL_TRANSITION_MINUTES] = by_case[COL_TIMESTAMP].diff().dt.total_seconds() / 60.0
    return df


def calculate_transition_times(csv_path=EVENT_LOG, output_path=EVENT_TRANSITIONS_CSV) -> pd.DataFrame:
    print(f"Loading data from {csv_path}...")
    events = load_event_log(csv_path)
    events = drop_incomplete_cases(sort_events(events))
    if events.empty:  # stop before an existing, good output file is overwritten by an empty one
        raise ValueError(
            f"No complete cases in {csv_path}: every case must start with {START_ACTIVITY} and end with {END_ACTIVITY}."
        )
    events = add_transition_times(events)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_path, index=False, date_format=TIMESTAMP_FORMAT)

    print(f"\nSuccess: {len(events)} events from {events[COL_CASE_ID].nunique()} cases saved to {output_path}")
    print(events[[COL_CASE_ID, COL_ACTIVITY, COL_PREVIOUS_ACTIVITY, COL_TRANSITION_MINUTES]].head(5).to_string(index=False))
    return events


if __name__ == "__main__":
    calculate_transition_times(*sys.argv[1:2])  # optional first argument: path to the event log