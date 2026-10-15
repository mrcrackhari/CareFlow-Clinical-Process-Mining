"""Shared names used by the whole CareFlow pipeline.

Single source of truth: the data generator, the analysis scripts and the
dashboard all import from here, so column names, activity names and file
locations cannot drift apart.

THE TEAM CONTRACT: the six activity names and five columns below are the
ones Member 1's generator writes into data/event_log.csv. Only Member 2
edits this file; everyone else asks in the team channel.
"""
from pathlib import Path

# ---- Event-log columns (the file Member 1 produces) ----
COL_CASE_ID = "case_id"
COL_ACTIVITY = "activity"
COL_TIMESTAMP = "timestamp"
COL_RESOURCE = "resource"  # optional: staff role or synthetic doctor ID
COL_SHIFT = "shift"        # optional: Morning / Evening / Night

REQUIRED_COLUMNS = [COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP]
OPTIONAL_COLUMNS = [COL_RESOURCE, COL_SHIFT]
EXPECTED_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS  # all five

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # 24-hour clock, no timezone

# ---- Columns added by the analysis ----
COL_PREVIOUS_ACTIVITY = "previous_activity"
COL_TRANSITION_MINUTES = "transition_time_minutes"
COL_FROM_ACTIVITY = "from_activity"
COL_TO_ACTIVITY = "to_activity"

# ---- Activities (the contract) ----
ACT_REGISTRATION = "Registration"
ACT_TRIAGE = "Triage"
ACT_CONSULTATION = "Doctor Consultation"
ACT_XRAY = "X-Ray"
ACT_REVIEW = "Doctor Review"
ACT_DISCHARGE = "Discharge"

VALID_ACTIVITIES = [
    ACT_REGISTRATION,
    ACT_TRIAGE,
    ACT_CONSULTATION,
    ACT_XRAY,
    ACT_REVIEW,
    ACT_DISCHARGE,
]

# A complete journey starts and ends with these two activities.
START_ACTIVITY = ACT_REGISTRATION
END_ACTIVITY = ACT_DISCHARGE

# Reference journey for conformance checking.
IDEAL_PATH = [
    ACT_REGISTRATION,
    ACT_TRIAGE,
    ACT_CONSULTATION,
    ACT_XRAY,
    ACT_REVIEW,
    ACT_DISCHARGE,
]

VALID_SHIFTS = ["Morning", "Evening", "Night"]

# ---- File locations (independent of where a script is run from) ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVENT_LOG = PROJECT_ROOT / "data" / "event_log.csv"                # Member 1's generated file
SAMPLE_EVENT_LOG = PROJECT_ROOT / "data" / "sample_event_log.csv"  # Member 1's hand-made journeys
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EVENT_TRANSITIONS_CSV = OUTPUTS_DIR / "event_transitions.csv"
BOTTLENECK_METRICS_CSV = OUTPUTS_DIR / "bottleneck_metrics.csv"
