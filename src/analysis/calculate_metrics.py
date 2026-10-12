import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.common.schema import COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP
def calculate_transition_times(csv_path):
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    df[COL_TIMESTAMP] = pd.to_datetime(df[COL_TIMESTAMP])
    df = df.sort_values(by=[COL_CASE_ID, COL_TIMESTAMP])
    df['transition_time_minutes'] = df.groupby(COL_CASE_ID)[COL_TIMESTAMP].diff().dt.total_seconds() / 60.0
    df['transition_time_minutes'] = df['transition_time_minutes'].fillna(0)
    os.makedirs('outputs', exist_ok=True)
    output_path = 'outputs/bottleneck_metrics.csv'
    df.to_csv(output_path, index=False)
    print(f"\nSuccess: Metrics calculated and saved to {output_path}")
    print(df[[COL_CASE_ID, COL_ACTIVITY, 'transition_time_minutes']].head(5))
    return df
if __name__ == "__main__":
    calculate_transition_times('data/sample_event_log.csv')