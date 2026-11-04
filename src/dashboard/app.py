"""
CareFlow Clinical Pathway Dashboard — Enterprise Process Mining Platform
========================================================================
Architecture: Dual-read pipeline (Primary: precomputed outputs from Member 2,
              Fallback: dynamic pandas calculations from event log).
Features: Executive KPIs, Conformance Analysis, Bottleneck SLA Alerts, Re-Work Loops,
          Financial Cost Engine, Patient Journey Gantt Timelines, Automated Insights,
          and Interactive Color-Coded Case Auditing.
Styling: React-Inspired Glassmorphism UI (Dark Slate Aesthetic).
Version: v2.3 (Final Enterprise Release)
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

# ---------------------------------------------------------------- Streamlit Page Configuration
st.set_page_config(
    page_title="CareFlow Enterprise Dashboard", 
    page_icon="🏥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------- React-Inspired Glassmorphism CSS
st.markdown("""
<style>
    /* Main App Dark Background */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Sidebar Dark Glass Styling */
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155;
    }
    
    /* React-Style Modern Metric Cards */
    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.75);
        border: 1px solid #334155;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -1px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(8px);
    }
    
    div[data-testid="stMetricLabel"] p {
        color: #94a3b8 !important;
        font-weight: 600;
        font-size: 0.9rem;
    }

    div[data-testid="stMetricValue"] div {
        color: #38bdf8 !important;
        font-weight: 700;
    }

    /* Tab Header Navigation Styling */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        color: #94a3b8 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #0284c7 !important;
        color: #ffffff !important;
    }

    /* Headings Accent Glow */
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }

    /* Expander Box Customization */
    .stExpander {
        background-color: #1e293b;
        border: 1px solid #334155 !important;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- Streamlit Cached Data Functions
@st.cache_data
def load_prepared_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    return prepare(raw_df)


@st.cache_data
def get_cases(df: pd.DataFrame) -> pd.DataFrame:
    return build_cases(df)


@st.cache_data
def get_transitions(df: pd.DataFrame) -> pd.DataFrame:
    return build_transitions(df)


# ---------------------------------------------------------------- Sidebar Setup & Data Ingestion
st.sidebar.title("🏥 CareFlow Console")
st.sidebar.caption("⚡ Enterprise Process Mining & Cost Engine")

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
            Please upload a CSV file from the sidebar to begin process mining analysis:
            - **`case_id`**: Unique identifier (e.g., `CASE-0001`)
            - **`activity`**: Clinical step name
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
except Exception as e:
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

# Operational SLA Threshold Controls
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

# Enterprise Financial Parameters
st.sidebar.markdown("---")
st.sidebar.header("💰 Financial Cost Engine")
cost_per_delay_hour = st.sidebar.number_input("Cost per Delay Hour (₹)", value=500, step=50)
cost_per_rework_step = st.sidebar.number_input("Cost per Re-Work Activity (₹)", value=1200, step=100)

st.sidebar.markdown("---")
st.sidebar.caption("ℹ️ *CareFlow v2.3 — Interactive Audit Edition*")

if len(date_range) != 2:
    st.warning("Pick both a start and an end date.")
    st.stop()

# Filtering Mask
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

# ---------------------------------------------------------------- Header & Metric Cards
st.title("CareFlow: Clinical Pathway Dashboard")
st.caption("Process mining view of patient journeys: volumes, pathways, delays, bottlenecks, and financial impact.")

# Walkthrough Guide
with st.expander("📖 Evaluator Walkthrough & User Guide (Click to expand)"):
    guide = get_user_guide_content()
    st.markdown(f"**Overview:** {guide['overview']}")
    for t in guide['tabs']:
        st.markdown(f"- {t}")

# Calculate Operations & Financial Metrics
metrics = safe_calculate_metrics(cases)
avg_duration = metrics["avg_duration"]

cases["excess_hours"] = (cases["duration_hrs"] - target_duration).clip(lower=0)
total_delay_cost = cases["excess_hours"].sum() * cost_per_delay_hour

repeat_df = calculate_repeat_metrics(df)
total_reworks = (repeat_df["occurrence_count"].sum() - len(repeat_df)) if not repeat_df.empty else 0
total_rework_cost = total_reworks * cost_per_rework_step
total_financial_impact = total_delay_cost + total_rework_cost
delayed_count = (cases['duration_hrs'] > target_duration).sum() if not cases.empty else 0

# Executive SLA Warning Banner
if avg_duration > target_duration:
    st.warning(
        f"⚠️ **Target SLA Alert:** Average pathway time ({avg_duration:.1f} h) exceeds target limit of {target_duration:.1f} h! "
        f"({delayed_count} delayed cases). Estimated Total Financial Loss: **₹{total_financial_impact:,.0f}**."
    )

# Styled Metric Cards
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Patients (cases)", f"{len(cases):,}")
k2.metric("Events Logged", f"{len(df):,}")
k3.metric("Avg Pathway Time", f"{avg_duration:.1f} h", delta=f"{avg_duration - target_duration:+.1f} h vs target", delta_color="inverse")
k4.metric("Est. Delay Cost", f"₹{total_delay_cost:,.0f}")
k5.metric("Total Financial Loss", f"₹{total_financial_impact:,.0f}", delta=f"Includes ₹{total_rework_cost:,.0f} Re-Work", delta_color="inverse")

# 5 Main Dashboard Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview & Insights", 
    "🔀 Pathways & Conformance", 
    "⏱️ Bottleneck Performance", 
    "🔁 Re-Work & Loops", 
    "📋 Patient Cases & Timeline"
])

# ================================================================ Tab 1: Overview & Insights
with tab1:
    st.subheader("🤖 Automated Operational Insights & Root Cause Analysis")
    
    highest_dept = cases.groupby("department")["duration_hrs"].mean().idxmax()
    highest_dept_val = cases.groupby("department")["duration_hrs"].mean().max()
    peak_arrival_hour = df["timestamp"].dt.hour.mode()[0]
    
    c_ins1, c_ins2 = st.columns(2)
    c_ins1.info(f"💡 **Departmental Bottleneck:** `{highest_dept}` department exhibits the longest average treatment time at **{highest_dept_val:.1f} hours** per patient case.")
    c_ins2.info(f"💡 **Peak Arrival Window:** Patient registrations spike around **{peak_arrival_hour}:00 hrs**, causing temporary downstream throughput bottlenecks.")

    st.markdown("---")
    c1, c2 = st.columns(2)
    freq = df["activity"].value_counts().reset_index()
    freq.columns = ["activity", "count"]
    c1.plotly_chart(
        px.bar(freq, x="count", y="activity", orientation="h", title="Activity Frequency Distribution", template="plotly_dark")
        .update_yaxes(categoryorder="total ascending"),
        width="stretch",
    )
    vol = cases.set_index("start").resample("W").size().reset_index(name="patients")
    c2.plotly_chart(
        px.line(vol, x="start", y="patients", markers=True, title="Weekly Patient Volume Trend", template="plotly_dark"),
        width="stretch",
    )
    
    c3, c4 = st.columns(2)
    dept = cases.groupby("department").agg(patients=("case_id", "count"), avg_hrs=("duration_hrs", "mean")).reset_index()
    c3.plotly_chart(px.bar(dept, x="department", y="patients", title="Patient Distribution by Department", template="plotly_dark"), width="stretch")
    c4.plotly_chart(
        px.bar(dept, x="department", y="avg_hrs", title="Average Pathway Time by Department (Hours)", template="plotly_dark"),
        width="stretch",
    )

# ================================================================ Tab 2: Pathways & Conformance
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
    fig.update_layout(height=550, margin=dict(t=10, b=10), template="plotly_dark")
    st.plotly_chart(fig, width="stretch")

# ================================================================ Tab 3: Bottleneck Performance
with tab3:
    st.header("⏱️ Clinical Performance & Bottleneck Wait-Time Analysis")
    
    c1, c2 = st.columns(2)
    c1.plotly_chart(
        px.histogram(cases, x="duration_hrs", nbins=40, title="Pathway Time Distribution (Hours)", template="plotly_dark"),
        width="stretch",
    )
    c2.plotly_chart(
        px.box(cases, x="department", y="duration_hrs", title="Pathway Time Variance by Department (Hours)", template="plotly_dark"),
        width="stretch",
    )

    st.subheader("Step-by-Step Transition Wait Times & SLA Violations")
    precomputed_bt = load_precomputed_bottlenecks()

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
                title=f"Top Slowest Clinical Steps (Red indicates wait > {target_wait} min threshold)",
                template="plotly_dark"
            ).update_yaxes(categoryorder="total ascending"),
            width="stretch",
        )
    else:
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
                    title=f"Top Slowest Clinical Transitions (Red indicates wait > {target_wait} min threshold)",
                    template="plotly_dark"
                ).update_yaxes(categoryorder="total ascending"),
                width="stretch",
            )
        else:
            st.info("No transition wait-time data available for the current filter selection.")

    st.subheader("Transition Matrix Heatmap (Patient Density)")
    pivot = trans.pivot_table(index="activity", columns="next_activity", values="case_id", aggfunc="count", fill_value=0)
    st.plotly_chart(
        px.imshow(pivot, text_auto=True, aspect="auto", color_continuous_scale="Blues", template="plotly_dark",
                  labels=dict(x="Next Clinical Step", y="Current Clinical Step", color="Patient Volume")),
        width="stretch",
    )

# ================================================================ Tab 4: Re-Work & Loops
with tab4:
    st.header("🔁 Repeated Step Detection & Clinical Re-Work Analysis")
    
    precomputed_loops = load_precomputed_repeat_loops()
    
    if precomputed_loops is not None and not precomputed_loops.empty and len(precomputed_loops.columns) >= 2:
        st.success("✅ Loaded precalculated repeat loop metrics from `outputs/repeat_loop_metrics.csv`")
        st.dataframe(precomputed_loops, width="stretch", hide_index=True)
        
        act_col = "activity" if "activity" in precomputed_loops.columns else precomputed_loops.columns[0]
        val_col = "repeat_count" if "repeat_count" in precomputed_loops.columns else precomputed_loops.columns[1]
        
        st.plotly_chart(
            px.bar(precomputed_loops, x=act_col, y=val_col, title="Repeat Activity Frequency Count", template="plotly_dark"),
            width="stretch",
        )
    else:
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
                px.bar(summary_repeats, x="activity", y="total_repeats", title="Repeated Activity Step Frequencies", template="plotly_dark"),
                width="stretch",
            )
        else:
            st.success("🎉 No repeated activities or clinical re-work loops detected in the filtered dataset!")

# ================================================================ Tab 5: Patient Cases & Timeline
with tab5:
    st.header("📋 Patient Case Audit & Individual Journey Timeline")
    
    st.subheader("🔍 Individual Patient Journey Timeline Trace (Gantt Chart)")
    selected_case = st.selectbox("Select Patient Case ID to Inspect Timeline", options=sorted(cases["case_id"].unique()))
    
    case_timeline = df[df["case_id"] == selected_case].sort_values("timestamp").copy()
    case_timeline["next_timestamp"] = case_timeline["timestamp"].shift(-1)
    case_timeline["next_timestamp"] = case_timeline["next_timestamp"].fillna(case_timeline["timestamp"] + pd.Timedelta(minutes=15))
    
    fig_timeline = px.timeline(
        case_timeline,
        x_start="timestamp",
        x_end="next_timestamp",
        y="activity",
        color="activity",
        title=f"Chronological Step Timeline for Patient {selected_case}",
        labels={"timestamp": "Step Start", "next_timestamp": "Step End", "activity": "Clinical Activity"},
        template="plotly_dark"
    )
    fig_timeline.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig_timeline, width="stretch")
    
    st.markdown("---")
    st.subheader("Outlier Patient Case Audit Table")
    pct = st.slider("Select delay percentile threshold filter", 50, 99, 90)
    threshold = cases["duration_hrs"].quantile(pct / 100)
    st.caption(f"Calculated Duration Threshold ({pct}th Percentile): {threshold:.1f} hours")
    
    slow = cases[cases["duration_hrs"] >= threshold].sort_values("duration_hrs", ascending=False)
    search = st.text_input("🔍 Search cases by Case ID or Pathway text", help="Enter a Case ID like 'CASE-0001'")
    
    if search:
        slow = slow[slow["case_id"].str.contains(search, case=False) | slow["pathway"].str.contains(search, case=False)]
        
    show = slow[["case_id", "department", "start", "duration_hrs", "steps", "pathway"]].copy()
    show["duration_hrs"] = show["duration_hrs"].round(1)
    
    # 1. Custom Status Badges
    show["Status"] = show["duration_hrs"].apply(
        lambda x: "🚨 SLA Breached" if x > target_duration else "✅ Optimal"
    )
    
    # 2. Color-Coded Heatmap Styling
    def highlight_sla(row):
        color = 'background-color: rgba(217, 83, 79, 0.3)' if row['duration_hrs'] > target_duration else ''
        return [color] * len(row)
    
    styled_show = show.style.apply(highlight_sla, axis=1)
    
    # 3. Interactive Data Editor
    st.data_editor(
        styled_show, 
        use_container_width=True, 
        hide_index=True,
        disabled=["case_id", "start", "pathway", "Status"], # Protects core data from accidental edits
        help="You can interactively click and edit 'department' or 'duration_hrs' cells for live scenario testing."
    )
    
    col_dl1, col_dl2 = st.columns(2)
    col_dl1.download_button("⬇️ Export Outlier Cases (CSV)", show.to_csv(index=False), "delayed_outlier_cases.csv", "text/csv")
    col_dl2.download_button("⬇️ Export All Filtered Cases (CSV)", cases.to_csv(index=False), "all_filtered_patient_cases.csv", "text/csv")