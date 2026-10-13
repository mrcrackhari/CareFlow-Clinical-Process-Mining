import pandas as pd
import os
def analyze_bottlenecks(metrics_csv_path):
    print(f"Loading metrics from {metrics_csv_path}...\n")
    df = pd.read_csv(metrics_csv_path)    
    average_waits = df.groupby('activity')['transition_time_minutes'].mean().reset_index()
    average_waits = average_waits.sort_values(by='transition_time_minutes', ascending=False)
    average_waits = average_waits.rename(columns={'transition_time_minutes': 'average_wait_minutes'})
    print("--- Average Wait Times (Bottlenecks) ---")
    print(average_waits)
    output_path = 'outputs/average_wait_times.csv'
    average_waits.to_csv(output_path, index=False)
    print(f"\nSuccess: Bottleneck report saved to {output_path}")
if __name__ == "__main__":
    analyze_bottlenecks('outputs/bottleneck_metrics.csv')