from pathlib import Path
import pandas as pd

# Define path helpers for dataset and output discovery
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "event_log.csv"
FALLBACK_DATA_PATH = Path(__file__).resolve().parent / "data" / "event_log.csv"
BOTTLENECK_OUTPUT_PATH = BASE_DIR / "outputs" / "bottleneck_metrics.csv"
REPEAT_LOOP_OUTPUT_PATH = BASE_DIR / "outputs" / "repeat_loop_metrics.csv"
PROCESS_MAP_OUTPUT_PATH = BASE_DIR / "outputs" / "process_map_edges.csv"


def get_dataset_path() -> Path:
    """Finds available event log path in root data/ or dashboard data/."""
    if DATA_PATH.exists():
        return DATA_PATH
    if FALLBACK_DATA_PATH.exists():
        return FALLBACK_DATA_PATH
    return DATA_PATH


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans raw event log dataframe and casts timestamp columns."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()

    required_cols = {"case_id", "activity", "timestamp"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Missing required columns in dataset: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if "department" not in df.columns:
        df["department"] = "General"
    else:
        df["department"] = df["department"].fillna("General")

    return df.sort_values(["case_id", "timestamp"])


def build_cases(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates case-level summary metrics (duration, pathway variants)."""
    grouped = df.groupby("case_id")

    cases = grouped.agg(
        start=("timestamp", "min"),
        end=("timestamp", "max"),
        steps=("activity", "count"),
        department=("department", "first"),
        pathway=("activity", lambda x: " → ".join(x)),
    ).reset_index()

    cases["duration_hrs"] = (cases["end"] - cases["start"]).dt.total_seconds() / 3600.0
    return cases


def build_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Computes transition step-to-step wait times in minutes."""
    df_sorted = df.sort_values(["case_id", "timestamp"]).copy()
    df_sorted["next_activity"] = df_sorted.groupby("case_id")["activity"].shift(-1)
    df_sorted["next_timestamp"] = df_sorted.groupby("case_id")["timestamp"].shift(-1)

    transitions = df_sorted.dropna(subset=["next_activity"]).copy()
    transitions["wait_min"] = (
        transitions["next_timestamp"] - transitions["timestamp"]
    ).dt.total_seconds() / 60.0

    return transitions


def load_precomputed_bottlenecks() -> pd.DataFrame | None:
    """Loads pre-calculated bottleneck metrics from outputs/ sitting in workspace root."""
    if BOTTLENECK_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(BOTTLENECK_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception:
            return None
    return None


def load_precomputed_repeat_loops() -> pd.DataFrame | None:
    """Loads pre-calculated repeat loop metrics from outputs/ sitting in workspace root."""
    if REPEAT_LOOP_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(REPEAT_LOOP_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception:
            return None
    return None


def load_precomputed_process_map() -> pd.DataFrame | None:
    """Loads pre-calculated process map edge counts from outputs/ sitting in workspace root."""
    if PROCESS_MAP_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(PROCESS_MAP_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception:
            return None
    return None


def calculate_repeat_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates on-the-fly repeat activity counts per case if precomputed metrics are absent."""
    counts = df.groupby(["case_id", "activity"]).size().reset_index(name="occurrence_count")
    repeats = counts[counts["occurrence_count"] > 1].copy()
    return repeats