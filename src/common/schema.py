"""Shared names used by the whole CareFlow pipeline.

Single source of truth: the data generator, the analysis scripts and the
dashboard all import from here, so column names, activity names and file
locations cannot drift apart.

The activity names below must match data/sample_event_log.csv exactly.
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
EXPECTED_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS  # all five, as before

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # 24-hour clock, no timezone

# ---- Columns added by the analysis ----
COL_PREVIOUS_ACTIVITY = "previous_activity"
COL_TRANSITION_MINUTES = "transition_time_minutes"
COL_FROM_ACTIVITY = "from_activity"
COL_TO_ACTIVITY = "to_activity"

# ---- Activities ----
ACT_ADMISSION = "Admission"
ACT_TRIAGE = "Triage"
ACT_CONSULTATION = "Doctor_Consult"
ACT_XRAY = "X-Ray"
ACT_BLOOD_TEST = "Blood_Test"
ACT_DISCHARGE = "Discharge"

VALID_ACTIVITIES = [
    ACT_ADMISSION,
    ACT_TRIAGE,
    ACT_CONSULTATION,
    ACT_XRAY,
    ACT_BLOOD_TEST,
    ACT_DISCHARGE,
]

# A complete journey starts and ends with these two activities.
START_ACTIVITY = ACT_ADMISSION
END_ACTIVITY = ACT_DISCHARGE

# Reference journey for conformance checking. X-Ray and Blood_Test are the
# optional diagnostic steps, so a case that uses them deviates from this path.
IDEAL_PATH = [
    ACT_ADMISSION,
    ACT_TRIAGE,
    ACT_CONSULTATION,
    ACT_DISCHARGE,
]

VALID_SHIFTS = ["Morning", "Evening", "Night"]

# ---- File locations (independent of where a script is run from) ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_EVENT_LOG = PROJECT_ROOT / "data" / "sample_event_log.csv"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EVENT_TRANSITIONS_CSV = OUTPUTS_DIR / "event_transitions.csv"
BOTTLENECK_METRICS_CSV = OUTPUTS_DIR / "bottleneck_metrics.csv"
