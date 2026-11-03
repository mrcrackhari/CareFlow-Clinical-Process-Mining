"""
CareFlow Clinical Pathway Dashboard — Interactive Process Mining Platform
========================================================================
Architecture: Dual-read pipeline (Primary: precomputed outputs from Member 2,
              Fallback: dynamic pandas calculations from event log).
Features: Executive KPIs, Conformance, Bottleneck SLA Alerts, Re-work Loops.
Version: v1.9 (Fully Corrected Release — Defensive CSV & Schema Protection)
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Import data loader helpers
from data_loader import (
    get_dataset_path,
    build_cases,
    build_transitions,
    prepare,
    load_precomputed_bottlenecks,
    load_precomputed_repeat_loops,
    load_precomputed_process_map,
    calculate_repeat_metrics,
    calculate_conformance_metrics,
    get_dataset_metadata,
    safe_calculate_metrics,
    get_user_guide_content,
    STANDARD_PATHWAY,
)

st.set_page_config(page_title="CareFlow Dashboard", page_icon="🏥", layout="wide")


# ---------------------------------------------------------------- Streamlit Cached Wrappers
@st.cache_data
def load_prepared_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    return prepare(raw_df)


@st.cache_data
def get_cases(df: pd.DataFrame) -> pd.DataFrame:
    return build_cases(df)


@st.cache_data
def get_transitions(df: pd.DataFrame) -> pd.DataFrame:
    return build_transitions(df)


# ---------------------------------------------------------------- Sidebar & Data Loading
st.sidebar.title("🏥 CareFlow Analytics Console")
st.sidebar.caption("⚡ Clinical Process Mining & Pathway Optimization Platform")

uploaded = st.sidebar.file_uploader(
    "📂 Upload Event Log (CSV)", 
    type="csv", 
    help="Select a custom clinical event log CSV dataset to analyze patient flows."
)
dataset_path = get_dataset_path()

try:
    if uploaded is not None:
        raw = pd.read_csv(uploaded)
    elif dataset_path.exists():
        raw = pd.read_csv(dataset_path)
    else:
        st.title("CareFlow: Clinical Pathway Dashboard")
        st.caption("Process mining view of patient journeys: volumes, pathways, delays and bottlenecks.")

        st.info("👋 Welcome to CareFlow! No default `event_log.csv` dataset was detected in `data/`.")

        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📋 Expected Dataset Schema")
            st.markdown("""
            Please upload a CSV file from the sidebar to begin process mining analysis. 
            Your file should include the standard contract columns:
            - **`case_id`**: Unique identifier (e.g., `CASE-0001`)
            - **`activity`**: Clinical step (`Registration`, `Triage`, `Doctor Consultation`, `X-Ray`, `Doctor Review`, `Discharge`)
            - **`timestamp`**: Event time (`YYYY-MM-DD HH:MM:SS`)
            - **`department`**: *(Optional)* Hospital unit
            """)

        with c2:
            st.subheader("💡 Example Layout")
            sample_table = pd.DataFrame({
                "case_id": ["CASE-0001", "CASE-0001", "CASE-0002"],
                "activity": ["Registration", "Triage", "Registration"],
                "timestamp": ["2026-10-10 09:00:00", "2026-10-10 09:15:00", "2026-10-10 09:30:00"],
                "department": ["General", "General", "General"]
            })
            st.dataframe(sample_table, hide_index=True, width="stretch")

        st.stop()

    data = load_prepared_data(raw)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not load data: {e}")
    st.stop()

cases_all = get_cases(data)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Dynamic Interactive Filters")

metadata = get_dataset_metadata(data)
st.sidebar.info(
    f"📊 **Active Log Summary**\n"
    f"- Total Events: `{metadata['total_records']:,}`\n"
    f"- Total Patient Cases: `{metadata['total_cases']:,}`\n"
    f"- Date Span: `{metadata['min_date']}` to `{metadata['max_date']}`"
)

min_d, max_d = cases_all["start"].min().date(), cases_all["start"].max().date()
date_range = st.sidebar.date_input(
    "🗓️ Select Case Start Date Range", 
    (min_d, max_d), 
    min_value=min_d, 
    max_value=max_d,
    help="Filter data to analyze specific patient arrival windows."
)

depts = sorted(cases_all["department"].unique())
sel_depts = st.sidebar.multiselect(
    "🏢 Hospital Department Filter", 
    depts, 
    default=depts,
    help="Select hospital departments to include in performance analysis."
)

all_pathways = sorted(cases_all["pathway"].unique())
sel_pathways = st.sidebar.multiselect(
    "🔀 Specific Pathway Variant Filter", 
    all_pathways, 
    default=[],
    help="Filter view by explicit step-by-step treatment pathways."
)

# Target Threshold Controls
st.sidebar.markdown("---")
st.sidebar.header("⚠️ Target Thresholds & SLA Controls")
target_duration = st.sidebar.number_input(
    "⏱️ Max Target Pathway Time (Hours)", 
    value=2.0, 
    step=0.5,
    help="Target SLA limit for complete patient treatment pathway duration."
)
target_wait = st.sidebar.number_input(
    "⏳ Max Wait Alert Threshold (Minutes)", 
    value=25.0, 
    step=5.0,
    help="SLA threshold for transition delay wait times between clinical steps."
)

st.sidebar.markdown("---")
st.sidebar.caption("ℹ️ *CareFlow v1.9 — Fully Corrected Release*")

if len(date_range) != 2:
    st.warning("Pick both a start and an end date.")
    st.stop()

mask = (
    (cases_all["start"].dt.date >= date_range[0])
    & (cases_all["start"].dt.date <= date_range[1])
    & (cases_all["department"].isin(sel_depts))
)

if sel_pathways:
    mask = mask & (cases_all["pathway"].isin(sel_pathways))

cases = cases_all[mask]
df = data[data["case_id"].isin(cases["case_id"])]

if cases.empty:
    st.warning("⚠️ No cases match the selected filters. Adjust your sidebar settings.")
    st.stop()

trans = get_transitions(df)

# ---------------------------------------------------------------- Header + KPIs
st.title("CareFlow: Clinical Pathway Dashboard")
st.caption("Process mining view of patient journeys: volumes, pathways, delays and bottlenecks.")

# Evaluator Walkthrough Guide
with st.expander("📖 Evaluator Walkthrough & User Guide (Click to expand)"):
    guide = get_user_guide_content()
    st.markdown(f"**Overview:** {guide['overview']}")
    for t in guide['tabs']:
        st.markdown(f"- {t}")

metrics = safe_calculate_metrics(cases)
avg_duration = metrics["avg_duration"]
delayed_count = (cases['duration_hrs'] > target_duration).sum() if not cases.empty else 0

if avg_duration > target_duration:
    st.warning(f"⚠️ **Target SLA Alert:** Average pathway time ({avg_duration:.1f} h) exceeds target limit of {target_duration:.1f} h! ({delayed_count} delayed cases)")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Patients (cases)", f"{len(cases):,}")
k2.metric("Events", f"{len(df):,}")
k3.metric("Avg pathway time", f"{avg_duration:.1f} h", delta=f"{avg_duration - target_duration:+.1f} h vs target", delta_color="inverse")
k4.metric("Median pathway time", f"{cases['duration_hrs'].median():.1f} h" if not cases.empty else "0.0 h")
k5.metric("Unique pathways", f"{cases['pathway'].nunique():,}" if not cases.empty else "0")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "🔀 Pathways & Conformance", "⏱️ Bottleneck Performance", "🔁 Re-Work & Loops", "📋 Patient Cases"])

# ---------------------------------------------------------------- Tab 1: Overview
with tab1:
    c1, c2 = st.columns(2)
    freq = df["activity"].value_counts().reset_index()
    freq.columns = ["activity", "count"]
    c1.plotly_chart(
        px.bar(freq, x="count", y="activity", orientation="h", title="Activity Frequency Distribution")
        .update_yaxes(categoryorder="total ascending"),
        width="stretch",
    )
    vol = cases.set_index("start").resample("W").size().reset_index(name="patients")
    c2.plotly_chart(
        px.line(vol, x="start", y="patients", markers=True, title="Weekly Patient Volume Trend"),
        width="stretch",
    )
    c3, c4 = st.columns(2)
    dept = cases.groupby("department").agg(patients=("case_id", "count"), avg_hrs=("duration_hrs", "mean")).reset_index()
    c3.plotly_chart(px.bar(dept, x="department", y="patients", title="Patient Distribution by Department"), width="stretch")
    c4.plotly_chart(
        px.bar(dept, x="department", y="avg_hrs", title="Average Pathway Time by Department (Hours)"),
        width="stretch",
    )

# ---------------------------------------------------------------- Tab 2: Pathways & Conformance
with tab2:
    st.subheader("🎯 Actual vs. Ideal Standard Care Conformance Analysis")
    
    target_path = st.text_input("Ideal Standard Pathway Target Specification", value=STANDARD_PATHWAY)
    
    conf_cases = calculate_conformance_metrics(cases, standard_path=target_path)
    total_cases = len(conf_cases)
    conforming_count = conf_cases["is_conforming"].sum()
    non_conforming_count = total_cases - conforming_count
    conformance_rate = (conforming_count / total_cases * 100) if total_cases > 0 else 0.0

    m1, m2, m3 = st.columns(3)
    m1.metric("Overall Conformance Score", f"{conformance_rate:.1f}%")
    m2.metric("Standard Target Journeys", f"{conforming_count:,}")
    m3.metric("Deviated Patient Journeys", f"{non_conforming_count:,}")

    if conformance_rate < 70.0:
        st.warning(f"⚠️ **Pathway Conformance Alert:** Only {conformance_rate:.1f}% of patients strictly followed the ideal standard pathway!")
    else:
        st.success(f"✅ **High Conformance Achieved:** {conformance_rate:.1f}% of patients followed the ideal target care path.")

    st.subheader("Most Frequent Clinical Pathway Variants")
    top_n = st.slider("Select number of variants to display", 5, 20, 10)
    variants = cases.groupby("pathway").agg(
        patients=("case_id", "count"), avg_hours=("duration_hrs", "mean")
    ).reset_index().sort_values("patients", ascending=False)
    variants["share_%"] = (variants["patients"] / variants["patients"].sum() * 100).round(1)
    variants["avg_hours"] = variants["avg_hours"].round(1)
    variants["is_standard"] = variants["pathway"] == target_path
    
    st.dataframe(variants.head(top_n), width="stretch", hide_index=True)

    st.subheader("Process Map Edge Network Statistics")
    proc_map = load_precomputed_process_map()
    if proc_map is not None and not proc_map.empty:
        st.success("✅ Loaded precalculated process map edges from `outputs/process_map_edges.csv`")
        st.dataframe(proc_map, width="stretch", hide_index=True)
    else:
        st.info("No precalculated process map edge file found in `outputs/`. Showing dynamic transition flow diagram below.")

    st.subheader("Multi-Step Patient Journey Flow (Sankey Diagram)")
    s = df.copy()
    s["step"] = s.groupby("case_id").cumcount() + 1
    s = s[s["step"] <= 10]
    s["node"] = s["step"].astype(str) + ". " + s["activity"]
    s["next_node"] = s.groupby("case_id")["node"].shift(-1)
    links = s.dropna(subset=["next_node"]).groupby(["node", "next_node"]).size().reset_index(name="value")
    nodes = sorted(set(links["node"]) | set(links["next_node"]), key=lambda x: (int(x.split(".")[0]), x))
    idx = {n: i for i, n in enumerate(nodes)}
    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, pad=15, thickness=15),
        link=dict(
            source=links["node"].map(idx), target=links["next_node"].map(idx), value=links["value"]
        ),
    ))
    fig.update_layout(height=550, margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- Tab 3: Bottleneck Performance
with tab3:
    st.header("⏱️ Clinical Performance & Bottleneck Wait-Time Analysis")
    
    c1, c2 = st.columns(2)
    c1.plotly_chart(
        px.histogram(cases, x="duration_hrs", nbins=40, title="Pathway Time Distribution (Hours)"),
        width="stretch",
    )
    c2.plotly_chart(
        px.box(cases, x="department", y="duration_hrs", title="Pathway Time Variance by Department (Hours)"),
        width="stretch",
    )

    st.subheader("Step-by-Step Transition Wait Times & SLA Violations")

    precomputed_bt = load_precomputed_bottlenecks()

    # Robust validation: check if precomputed data exists AND contains 'avg_wait_min'
    if precomputed_bt is not None and not precomputed_bt.empty and "avg_wait_min" in precomputed_bt.columns:
        st.success("✅ Loaded precalculated bottleneck metrics from `outputs/bottleneck_metrics.csv`")
        bt_data = precomputed_bt.copy()
        
        act_col = "activity" if "activity" in bt_data.columns else bt_data.columns[0]
        top_step = bt_data.sort_values("avg_wait_min", ascending=False).iloc[0]
        st.error(f"🚨 **Primary Bottleneck Highlight:** `{top_step[act_col]}` step experiences an average delay of **{top_step['avg_wait_min']:.1f} minutes**!")
        
        st.dataframe(bt_data, width="stretch", hide_index=True)
        
        top_bt = bt_data.sort_values("avg_wait_min", ascending=False).head(10)
        top_bt["is_alert"] = top_bt["avg_wait_min"] > target_wait
        
        st.plotly_chart(
            px.bar(
                top_bt,
                x="avg_wait_min",
                y=act_col,
                orientation="h",
                color="is_alert",
                color_discrete_map={True: "#d9534f", False: "#0275d8"},
                title=f"Top Slowest Clinical Steps (Red indicates wait > {target_wait} min threshold)"
            ).update_yaxes(categoryorder="total ascending"),
            width="stretch",
        )
    else:
        # Dynamic fallback calculation from event log transitions
        bt_summary = trans.groupby(["activity", "next_activity"]).agg(
            avg_wait_min=("wait_min", "mean"),
            transitions=("wait_min", "count")
        ).reset_index()
        bt_summary["step"] = bt_summary["activity"] + " → " + bt_summary["next_activity"]
        bt_summary = bt_summary.sort_values("avg_wait_min", ascending=False)
        top_bt = bt_summary.head(10)

        if not top_bt.empty:
            top_bt["is_alert"] = top_bt["avg_wait_min"] > target_wait
            slowest = top_bt.iloc[0]
            st.error(f"🚨 **Primary Transition Bottleneck:** `{slowest['step']}` (Avg Wait: **{slowest['avg_wait_min']:.1f} min**)")

            st.plotly_chart(
                px.bar(
                    top_bt,
                    x="avg_wait_min",
                    y="step",
                    orientation="h",
                    color="is_alert",
                    color_discrete_map={True: "#d9534f", False: "#0275d8"},
                    title=f"Top Slowest Clinical Transitions (Red indicates wait > {target_wait} min threshold)"
                ).update_yaxes(categoryorder="total ascending"),
                width="stretch",
            )
        else:
            st.info("No transition wait-time data available for the current filter selection.")

    st.subheader("Transition Matrix Heatmap (Patient Density)")
    pivot = trans.pivot_table(index="activity", columns="next_activity", values="case_id", aggfunc="count", fill_value=0)
    st.plotly_chart(
        px.imshow(pivot, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                  labels=dict(x="Next Clinical Step", y="Current Clinical Step", color="Patient Volume")),
        width="stretch",
    )

# ---------------------------------------------------------------- Tab 4: Re-Work & Loops
with tab4:
    st.header("🔁 Repeated Step Detection & Clinical Re-Work Analysis")
    
    precomputed_loops = load_precomputed_repeat_loops()
    
    # Robust validation for repeat loops CSV schema
    if precomputed_loops is not None and not precomputed_loops.empty and len(precomputed_loops.columns) >= 2:
        st.success("✅ Loaded precalculated repeat loop metrics from `outputs/repeat_loop_metrics.csv`")
        st.dataframe(precomputed_loops, width="stretch", hide_index=True)
        
        act_col = "activity" if "activity" in precomputed_loops.columns else precomputed_loops.columns[0]
        val_col = "repeat_count" if "repeat_count" in precomputed_loops.columns else precomputed_loops.columns[1]
        
        st.plotly_chart(
            px.bar(precomputed_loops, x=act_col, y=val_col, title="Repeat Activity Frequency Count"),
            width="stretch",
        )
    else:
        st.info("Calculating repeat activities dynamically from raw event log...")
        repeat_df = calculate_repeat_metrics(df)
        if not repeat_df.empty:
            summary_repeats = repeat_df.groupby("activity").agg(
                affected_cases=("case_id", "nunique"),
                total_repeats=("occurrence_count", "sum")
            ).reset_index().sort_values("total_repeats", ascending=False)
            
            top_rework = summary_repeats.iloc[0]
            st.warning(f"🔁 **Highest Re-Work Activity:** `{top_rework['activity']}` step was repeated **{top_rework['total_repeats']} times** across {top_rework['affected_cases']} patient cases.")

            st.dataframe(summary_repeats, width="stretch", hide_index=True)
            st.plotly_chart(
                px.bar(summary_repeats, x="activity", y="total_repeats", title="Repeated Activity Step Frequencies"),
                width="stretch",
            )
        else:
            st.success("🎉 No repeated activities or clinical re-work loops detected in the filtered dataset!")

# ---------------------------------------------------------------- Tab 5: Patient Cases
with tab5:
    st.header("📋 Patient Case Audit & Outlier Export")
    pct = st.slider("Select delay percentile threshold filter", 50, 99, 90)
    threshold = cases["duration_hrs"].quantile(pct / 100)
    st.caption(f"Calculated Duration Threshold ({pct}th Percentile): {threshold:.1f} hours")
    
    slow = cases[cases["duration_hrs"] >= threshold].sort_values("duration_hrs", ascending=False)
    search = st.text_input("🔍 Search cases by Case ID or Pathway text", help="Enter a Case ID like 'CASE-0001' or a step name like 'X-Ray'")
    
    if search:
        slow = slow[slow["case_id"].str.contains(search, case=False) | slow["pathway"].str.contains(search, case=False)]
        
    show = slow[["case_id", "department", "start", "duration_hrs", "steps", "pathway"]].round({"duration_hrs": 1})
    st.dataframe(show, width="stretch", hide_index=True)
    
    col_dl1, col_dl2 = st.columns(2)
    col_dl1.download_button("⬇️ Export Outlier Cases (CSV)", show.to_csv(index=False), "delayed_outlier_cases.csv", "text/csv")
    col_dl2.download_button("⬇️ Export All Filtered Cases (CSV)", cases.to_csv(index=False), "all_filtered_patient_cases.csv", "text/csv")