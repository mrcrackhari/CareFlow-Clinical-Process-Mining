"""
CareFlow Day 20 — Final Review Practice & Live Demonstration Assistant
======================================================================
CLI helper tool for Member 3 (Dashboard Lead) to print exact key metrics 
and presentation talking points during final evaluator viva review.
"""

from pathlib import Path
import pandas as pd
from data_loader import get_dataset_path, prepare, build_cases, calculate_conformance_metrics


def run_viva_demonstration():
    print("=" * 75)
    print("🏥 CAREFLOW CLINICAL PROCESS MINING DASHBOARD — DAY 20 VIVA DEMO")
    print("=" * 75)

    dataset_path = get_dataset_path()
    if not dataset_path.exists():
        print("❌ Dataset not found at expected data path.")
        return

    raw_df = pd.read_csv(dataset_path)
    prepared_df = prepare(raw_df)
    cases_df = build_cases(prepared_df)
    conf_df = calculate_conformance_metrics(cases_df)

    total_patients = len(cases_df)
    conforming_patients = conf_df["is_conforming"].sum()
    conformance_pct = (conforming_patients / total_patients) * 100 if total_patients > 0 else 0.0
    avg_duration = cases_df["duration_hrs"].mean() if not cases_df.empty else 0.0

    print(f"\n📊 KEY DASHBOARD METRICS FOR VIVA DEMONSTRATION:")
    print(f"  • Total Patient Journeys Analyzed : {total_patients:,}")
    print(f"  • Total Clinical Events Logged    : {len(prepared_df):,}")
    print(f"  • Average Pathway Treatment Time  : {avg_duration:.2f} hours")
    print(f"  • Ideal Pathway Conformance Rate  : {conformance_pct:.1f}% ({conforming_patients}/{total_patients} cases)")
    print(f"  • Unique Pathway Variants Count    : {cases_df['pathway'].nunique():,}")

    print("\n🎯 KEY TAB TALKING POINTS FOR EVALUATOR DEMO:")
    print("  1. Sidebar & Controls : Interactive date, department, and SLA target threshold filters.")
    print("  2. Tab 1 (Overview)   : High-level volume trends and department workload distributions.")
    print("  3. Tab 2 (Pathways)   : Ideal vs. actual journey conformance and step-by-step Sankey diagrams.")
    print("  4. Tab 3 (Performance): Bottleneck wait-time detection with red SLA threshold alerts.")
    print("  5. Tab 4 (Loops)       : Re-work detection identifying repeated clinical steps.")
    print("  6. Tab 5 (Cases)       : Outlier patient filtering with CSV data export capability.")

    print("\n" + "=" * 75)
    print("✅ Day 20 dashboard demonstration walkthrough completed successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_viva_demonstration()