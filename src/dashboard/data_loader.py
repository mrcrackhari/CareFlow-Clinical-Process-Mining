from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "event_log.csv"
REQUIRED = {"case_id", "activity", "timestamp"}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(sorted(missing))}")
    if "department" not in df.columns:
        df["department"] = "All"
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["case_id", "activity", "timestamp"]).drop_duplicates()
    return df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)


def build_cases(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("case_id")
    cases = g.agg(
        start=("timestamp", "min"),
        end=("timestamp", "max"),
        steps=("activity", "count"),
        department=("department", "first"),
    )
    cases["duration_hrs"] = (cases["end"] - cases["start"]).dt.total_seconds() / 3600
    cases["pathway"] = g["activity"].apply(lambda s: " → ".join(s))
    return cases.reset_index()


def build_transitions(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["next_activity"] = d.groupby("case_id")["activity"].shift(-1)
    d["next_time"] = d.groupby("case_id")["timestamp"].shift(-1)
    d = d.dropna(subset=["next_activity"])
    d["wait_min"] = (d["next_time"] - d["timestamp"]).dt.total_seconds() / 60
    return d