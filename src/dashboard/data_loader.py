"""
CareFlow Data Loader & Fallback Pipeline Engine
============================================================
Handles data preparation, dataset discovery, dual-read loading from 
precomputed backend CSV files (`outputs/`), dynamic calculations fallback,
and metadata helper functions for UI rendering.
"""

import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "event_log.csv"
FALLBACK_DATA_PATH = Path(__file__).resolve().parent / "data" / "event_log.csv"
BOTTLENECK_OUTPUT_PATH = BASE_DIR / "outputs" / "bottleneck_metrics.csv"
REPEAT_LOOP_OUTPUT_PATH = BASE_DIR / "outputs" / "repeat_loop_metrics.csv"
PROCESS_MAP_OUTPUT_PATH = BASE_DIR / "outputs" / "process_map_edges.csv"

STANDARD_PATHWAY = "Registration → Triage → Doctor Consultation → X-Ray → Doctor Review → Discharge"


def get_dataset_path() -> Path:
    if DATA_PATH.exists():
        logging.info(f"Primary event log detected at: {DATA_PATH}")
        return DATA_PATH
    if FALLBACK_DATA_PATH.exists():
        logging.info(f"Fallback event log detected at: {FALLBACK_DATA_PATH}")
        return FALLBACK_DATA_PATH
    logging.warning("No default event log file found in data/ directories.")
    return DATA_PATH


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()

    required_cols = {"case_id", "activity", "timestamp"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Missing required columns in dataset schema: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    if "department" not in df.columns:
        df["department"] = "General"
    else:
        df["department"] = df["department"].fillna("General")

    return df.sort_values(["case_id", "timestamp"])


def build_cases(df: pd.DataFrame) -> pd.DataFrame:
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
    df_sorted = df.sort_values(["case_id", "timestamp"]).copy()
    df_sorted["next_activity"] = df_sorted.groupby("case_id")["activity"].shift(-1)
    df_sorted["next_timestamp"] = df_sorted.groupby("case_id")["timestamp"].shift(-1)

    transitions = df_sorted.dropna(subset=["next_activity"]).copy()
    transitions["wait_min"] = (
        transitions["next_timestamp"] - transitions["timestamp"]
    ).dt.total_seconds() / 60.0

    return transitions


def load_precomputed_bottlenecks() -> pd.DataFrame | None:
    if BOTTLENECK_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(BOTTLENECK_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception as err:
            logging.error(f"Error reading precomputed bottlenecks: {err}")
            return None
    return None


def load_precomputed_repeat_loops() -> pd.DataFrame | None:
    if REPEAT_LOOP_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(REPEAT_LOOP_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception as err:
            logging.error(f"Error reading precomputed repeat loops: {err}")
            return None
    return None


def load_precomputed_process_map() -> pd.DataFrame | None:
    if PROCESS_MAP_OUTPUT_PATH.exists():
        try:
            df = pd.read_csv(PROCESS_MAP_OUTPUT_PATH)
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception as err:
            logging.error(f"Error reading precomputed process map: {err}")
            return None
    return None


def calculate_repeat_metrics(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby(["case_id", "activity"]).size().reset_index(name="occurrence_count")
    repeats = counts[counts["occurrence_count"] > 1].copy()
    return repeats


def calculate_conformance_metrics(cases_df: pd.DataFrame, standard_path: str = STANDARD_PATHWAY) -> pd.DataFrame:
    cases = cases_df.copy()
    cases["is_conforming"] = cases["pathway"] == standard_path
    return cases


def get_dataset_metadata(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total_records": 0, "total_cases": 0, "min_date": "N/A", "max_date": "N/A"}
    return {
        "total_records": len(df),
        "total_cases": df["case_id"].nunique(),
        "min_date": df["timestamp"].min().strftime("%Y-%m-%d"),
        "max_date": df["timestamp"].max().strftime("%Y-%m-%d"),
    }


def safe_calculate_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"avg_duration": 0.0, "total_cases": 0, "total_events": 0}
    return {
        "avg_duration": df["duration_hrs"].mean() if "duration_hrs" in df.columns else 0.0,
        "total_cases": df["case_id"].nunique() if "case_id" in df.columns else 0,
        "total_events": len(df),
    }


def get_user_guide_content() -> dict:
    return {
        "overview": "CareFlow Clinical Pathway Dashboard process mining platform built using Streamlit and Plotly.",
        "tabs": [
            "📊 Overview: High-level volume and frequency metrics.",
            "🔀 Pathways: Conformance analysis, Sankey flow diagrams, and edge networks.",
            "⏱️ Performance: Bottleneck wait-time detection with alert thresholds.",
            "🔁 Repeat & Loops: Re-work detection and activity re-visit counts.",
            "📋 Cases: Outlier detection with export functionality."
        ]
    }