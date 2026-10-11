from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Import processing logic from data_loader
from data_loader import DATA_PATH, build_cases, build_transitions, prepare

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


# ---------------------------------------------------------------- Sidebar
st.sidebar.title("🏥 CareFlow")
uploaded = st.sidebar.file_uploader("Upload event log (CSV)", type="csv")

try:
    if uploaded is not None:
        raw = pd.read_csv(uploaded)
    elif DATA_PATH.exists():
        raw = pd.read_csv(DATA_PATH)
    else:
        st.info("No data found. Run `python generate_data.py` or upload a CSV from the sidebar.")
        st.stop()
    data = load_prepared_data(raw)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not load data: {e}")
    st.stop()

cases_all = get_cases(data)

st.sidebar.header("Filters")
min_d, max_d = cases_all["start"].min().date(), cases_all["start"].max().date()
date_range = st.sidebar.date_input("Case start date", (min_d, max_d), min_value=min_d, max_value=max_d)
depts = sorted(cases_all["department"].unique())
sel_depts = st.sidebar.multiselect("Department", depts, default=depts)

if len(date_range) != 2:
    st.warning("Pick both a start and an end date.")
    st.stop()

mask = (
    (cases_all["start"].dt.date >= date_range[0])
    & (cases_all["start"].dt.date <= date_range[1])
    & (cases_all["department"].isin(sel_depts))
)
cases = cases_all[mask]
df = data[data["case_id"].isin(cases["case_id"])]

if cases.empty:
    st.warning("No cases match the selected filters.")
    st.stop()

trans = get_transitions(df)

# ---------------------------------------------------------------- Header + KPIs
st.title("CareFlow: Clinical Pathway Dashboard")
st.caption("Process mining view of patient journeys: volumes, pathways, delays and bottlenecks.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Patients (cases)", f"{len(cases):,}")
k2.metric("Events", f"{len(df):,}")
k3.metric("Avg pathway time", f"{cases['duration_hrs'].mean():.1f} h")
k4.metric("Median pathway time", f"{cases['duration_hrs'].median():.1f} h")
k5.metric("Unique pathways", f"{cases['pathway'].nunique():,}")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🔀 Pathways", "⏱️ Performance", "📋 Cases"])

# ---------------------------------------------------------------- Overview
with tab1:
    c1, c2 = st.columns(2)
    freq = df["activity"].value_counts().reset_index()
    freq.columns = ["activity", "count"]
    c1.plotly_chart(
        px.bar(freq, x="count", y="activity", orientation="h", title="Activity frequency")
        .update_yaxes(categoryorder="total ascending"),
        width="stretch",
    )
    vol = cases.set_index("start").resample("W").size().reset_index(name="patients")
    c2.plotly_chart(
        px.line(vol, x="start", y="patients", markers=True, title="Weekly patient volume"),
        width="stretch",
    )
    c3, c4 = st.columns(2)
    dept = cases.groupby("department").agg(patients=("case_id", "count"), avg_hrs=("duration_hrs", "mean")).reset_index()
    c3.plotly_chart(px.bar(dept, x="department", y="patients", title="Patients by department"), width="stretch")
    c4.plotly_chart(
        px.bar(dept, x="department", y="avg_hrs", title="Average pathway time by department (hours)"),
        width="stretch",
    )

# ---------------------------------------------------------------- Pathways
with tab2:
    st.subheader("Most common clinical pathways")
    top_n = st.slider("Number of pathways", 5, 20, 10)
    variants = cases.groupby("pathway").agg(
        patients=("case_id", "count"), avg_hours=("duration_hrs", "mean")
    ).reset_index().sort_values("patients", ascending=False)
    variants["share_%"] = (variants["patients"] / variants["patients"].sum() * 100).round(1)
    variants["avg_hours"] = variants["avg_hours"].round(1)
    st.dataframe(variants.head(top_n), width="stretch", hide_index=True)

    st.subheader("Patient flow (Sankey)")
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

# ---------------------------------------------------------------- Performance
with tab3:
    c1, c2 = st.columns(2)
    c1.plotly_chart(
        px.histogram(cases, x="duration_hrs", nbins=40, title="Pathway time distribution (hours)"),
        width="stretch",
    )
    c2.plotly_chart(
        px.box(cases, x="department", y="duration_hrs", title="Pathway time by department (hours)"),
        width="stretch",
    )

    st.subheader("Bottlenecks: average wait between steps")
    bt = trans.groupby(["activity", "next_activity"]).agg(
        avg_wait_min=("wait_min", "mean"), transitions=("wait_min", "count")
    ).reset_index()
    bt["step"] = bt["activity"] + " → " + bt["next_activity"]
    bt = bt.sort_values("avg_wait_min", ascending=False)
    top_bt = bt.head(10)
    st.plotly_chart(
        px.bar(top_bt, x="avg_wait_min", y="step", orientation="h", color="avg_wait_min",
               color_continuous_scale="Reds", title="Top 10 slowest transitions (minutes)")
        .update_yaxes(categoryorder="total ascending"),
        width="stretch",
    )

    st.subheader("Transition heatmap (patient counts)")
    pivot = trans.pivot_table(index="activity", columns="next_activity", values="case_id", aggfunc="count", fill_value=0)
    st.plotly_chart(
        px.imshow(pivot, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                  labels=dict(x="Next activity", y="Activity", color="Patients")),
        width="stretch",
    )

# ---------------------------------------------------------------- Cases
with tab4:
    st.subheader("Delayed / outlier cases")
    pct = st.slider("Show cases slower than this percentile", 50, 99, 90)
    threshold = cases["duration_hrs"].quantile(pct / 100)
    st.caption(f"Threshold: {threshold:.1f} hours")
    slow = cases[cases["duration_hrs"] >= threshold].sort_values("duration_hrs", ascending=False)
    search = st.text_input("Search by case ID or pathway text")
    if search:
        slow = slow[slow["case_id"].str.contains(search, case=False) | slow["pathway"].str.contains(search, case=False)]
    show = slow[["case_id", "department", "start", "duration_hrs", "steps", "pathway"]].round({"duration_hrs": 1})
    st.dataframe(show, width="stretch", hide_index=True)
    st.download_button("⬇️ Download these cases (CSV)", show.to_csv(index=False), "delayed_cases.csv", "text/csv")