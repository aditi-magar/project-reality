from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "PAIMANA_March_2026_All_Ongoing_Projects.csv"

st.set_page_config(
    page_title="Project Reality | Where Did the Money Go?",
    page_icon="🏗️",
    layout="wide",
)

NAVY = "#10243A"
TEAL = "#1F9D91"
ORANGE = "#F4A340"
RED = "#D9534F"
PALE = "#F5F7FA"

st.markdown(
    f"""
    <style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {{
        background: {PALE} !important; color: #1A2C3B !important;
    }}
    [data-testid="stHeader"] {{ background: rgba(245,247,250,0.95); }}
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3,
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
    [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
    label, h1, h2, h3, h4, h5, h6 {{ color: #1A2C3B !important; }}
    .hero {{ background: {NAVY}; padding: 1.6rem 1.8rem; border-radius: 14px;
             color: #FFFFFF !important; margin-bottom: 1rem; }}
    .hero h1, .hero h1 * {{ color: #FFFFFF !important; margin: 0; font-size: 2rem; }}
    .hero p, .hero p * {{ color: #D8E2EE !important; margin: 0.5rem 0 0 0; }}
    .small-note {{ color: #526171 !important; font-size: 0.9rem; }}
    div[data-testid="stMetric"] {{ background: #FFFFFF !important; padding: 1rem;
       border: 1px solid #DCE4ED; border-radius: 12px; color: #1A2C3B !important; }}
    div[data-testid="stMetric"] label, [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] p {{ color: #536273 !important; }}
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{ color: {NAVY} !important; }}
    [data-testid="stAlert"] {{ background-color: #FFF7D6 !important; border: 1px solid #F0D36B !important; }}
    [data-testid="stAlert"] * {{ color: #624B00 !important; }}
    [data-baseweb="select"] *, [data-baseweb="tag"] {{ color: #1A2C3B !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style_chart(fig, height=420):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=13, color=NAVY),
        title=dict(font=dict(size=16, color=NAVY), x=0.02, xanchor="left"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        height=height,
        margin=dict(l=45, r=25, t=75, b=80),
        legend=dict(font=dict(size=12, color=NAVY), title=dict(font=dict(size=12, color=NAVY))),
    )
    fig.update_xaxes(tickfont=dict(size=11, color="#536273"), title_font=dict(size=12, color=NAVY),
                     gridcolor="#EEF2F6", linecolor="#CBD5E1", zerolinecolor="#CBD5E1")
    fig.update_yaxes(tickfont=dict(size=11, color="#536273"), title_font=dict(size=12, color=NAVY),
                     gridcolor="#E2E8F0", linecolor="#CBD5E1", zerolinecolor="#CBD5E1")
    return fig


def crore_to_lakh_crore(value):
    return f"₹{value / 100000:,.2f} lakh crore"


def add_review_flags(frame):
    frame = frame.copy()
    frame["expenditure_pct_revised_cost"] = (
        frame["cumulative_expenditure_crore"] / frame["revised_cost_crore"].replace(0, pd.NA) * 100
    )
    frame["cost_revision_pct"] = (
        (frame["revised_cost_crore"] - frame["original_cost_crore"])
        / frame["original_cost_crore"].replace(0, pd.NA) * 100
    )
    reasons = []
    scores = []
    for row in frame.itertuples(index=False):
        row_reasons = []
        spend_pct = getattr(row, "expenditure_pct_revised_cost")
        progress = getattr(row, "physical_progress_pct")
        cost_change = getattr(row, "cost_revision_pct")
        revised_cost = getattr(row, "revised_cost_crore")
        expenditure = getattr(row, "cumulative_expenditure_crore")
        if pd.notna(cost_change) and cost_change >= 20:
            row_reasons.append("Revised cost increased by 20% or more")
        if pd.notna(spend_pct) and pd.notna(progress) and spend_pct - progress >= 20:
            row_reasons.append("Spending percentage is at least 20 points above physical progress")
        if pd.notna(progress) and pd.notna(spend_pct) and progress < 25 and spend_pct >= 50:
            row_reasons.append("Low physical progress with at least 50% of revised cost spent")
        if pd.notna(revised_cost) and revised_cost > 0 and pd.notna(expenditure) and expenditure > revised_cost:
            row_reasons.append("Cumulative expenditure exceeds revised cost")
        reasons.append("; ".join(row_reasons) if row_reasons else "No rule-based flag from these fields")
        scores.append(len(row_reasons))
    frame["review_flag_count"] = scores
    frame["review_reasons"] = reasons
    frame["review_priority"] = frame["review_flag_count"].map(lambda x: "High" if x >= 2 else ("Review" if x == 1 else "No flag"))
    return frame


st.markdown(
    """
    <div class="hero">
      <h1>🏗️ Project Reality</h1>
      <p>Where Did the Money Go? · Government infrastructure spending and progress monitor</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not DATA_PATH.exists():
    st.error(f"Project dataset not found: {DATA_PATH}. Keep the CSV inside the project's data folder.")
    st.stop()

try:
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
except Exception as exc:
    st.error(f"Could not read the project CSV: {exc}")
    st.stop()

numeric_cols = [
    "serial_no", "original_cost_crore", "revised_cost_crore",
    "cumulative_expenditure_crore", "physical_progress_pct",
]
for column in numeric_cols:
    df[column] = pd.to_numeric(df[column], errors="coerce")

text_cols = ["ministry_department", "sector_category", "project_name", "implementing_agency", "project_code", "legacy_ocms_code", "state"]
for column in text_cols:
    df[column] = df[column].fillna("Not specified").astype(str).str.strip()

df = add_review_flags(df)

st.caption("Data source: PAIMANA March 2026 Flash Report, Table 6: All Ongoing Projects. Project-level data extracted from the report.")
st.warning(
    "Review flags are simple rules for prioritising human review, not AI findings or proof of wrongdoing. "
    "This report gives project cost, cumulative expenditure, dates and reported physical progress; it does not provide invoice-level payment trails or independent site-photo evidence."
)

st.markdown("### Navigate Project Reality")
page = st.radio(
    "Choose a section",
    ["Overview", "Project explorer", "Risk review queue", "Data notes"],
    horizontal=True,
    label_visibility="collapsed",
    key="main_page_navigation",
)

with st.expander("Search and filter projects", expanded=False):
    st.caption("These filters apply to the charts, project list, and review queue.")
    search = st.text_input("Search project, code or agency", placeholder="e.g. high speed rail")
    ministry_options = sorted(x for x in df["ministry_department"].unique() if x and x != "Not specified")
    sector_options = sorted(x for x in df["sector_category"].unique() if x and x != "Not specified")
    state_options = sorted(x for x in df["state"].unique() if x and x != "Not specified")
    f1, f2, f3 = st.columns(3)
    with f1:
        selected_ministries = st.multiselect("Ministry / department", ministry_options, default=[])
    with f2:
        selected_sectors = st.multiselect("Sector", sector_options, default=[])
    with f3:
        selected_states = st.multiselect("State / location", state_options, default=[])
    progress_range = st.slider("Physical progress (%)", 0, 100, (0, 100), step=5)

filtered = df.copy()
if search.strip():
    query = search.strip().casefold()
    mask = (
        filtered["project_name"].str.casefold().str.contains(query, na=False)
        | filtered["project_code"].str.casefold().str.contains(query, na=False)
        | filtered["implementing_agency"].str.casefold().str.contains(query, na=False)
    )
    filtered = filtered[mask]
if selected_ministries:
    filtered = filtered[filtered["ministry_department"].isin(selected_ministries)]
if selected_sectors:
    filtered = filtered[filtered["sector_category"].isin(selected_sectors)]
if selected_states:
    filtered = filtered[filtered["state"].isin(selected_states)]
filtered = filtered[filtered["physical_progress_pct"].between(progress_range[0], progress_range[1], inclusive="both")]

all_count = len(df)
filtered_original = filtered["original_cost_crore"].sum()
filtered_revised = filtered["revised_cost_crore"].sum()
filtered_spend = filtered["cumulative_expenditure_crore"].sum()

if page == "Overview":
    st.subheader("Overview")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Projects listed", f"{len(filtered):,}")
    k2.metric("Original cost", crore_to_lakh_crore(filtered_original))
    k3.metric("Revised cost", crore_to_lakh_crore(filtered_revised))
    k4.metric("Cumulative expenditure", crore_to_lakh_crore(filtered_spend))
    ratio = (filtered_spend / filtered_revised * 100) if filtered_revised else 0
    st.caption(f"For current filters: cumulative expenditure is {ratio:.1f}% of the combined revised cost. Overall source list contains {all_count:,} numbered project records.")

    left, right = st.columns(2)
    with left:
        progress_bins = pd.cut(
            filtered["physical_progress_pct"],
            bins=[-0.01, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            labels=["0-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-100"],
            include_lowest=True,
        )
        progress_counts = progress_bins.value_counts(sort=False).rename_axis("Progress band (%)").reset_index(name="Project count")
        fig = px.bar(progress_counts, x="Progress band (%)", y="Project count", title="Projects by reported physical progress", color_discrete_sequence=[TEAL], text_auto=True)
        st.plotly_chart(style_chart(fig, 390), width="stretch")
    with right:
        sector = filtered.groupby("sector_category", dropna=False)["cumulative_expenditure_crore"].sum().sort_values(ascending=False).head(10).reset_index()
        fig = px.bar(sector.sort_values("cumulative_expenditure_crore"), x="cumulative_expenditure_crore", y="sector_category", orientation="h", title="Top sectors by cumulative expenditure", labels={"cumulative_expenditure_crore": "Expenditure (₹ crore)", "sector_category": "Sector"}, color_discrete_sequence=[ORANGE])
        st.plotly_chart(style_chart(fig, 390), width="stretch")

    top_spend = filtered.nlargest(10, "cumulative_expenditure_crore")[["project_name", "state", "cumulative_expenditure_crore", "physical_progress_pct", "project_code"]]
    fig = px.bar(top_spend.sort_values("cumulative_expenditure_crore"), x="cumulative_expenditure_crore", y="project_name", orientation="h", title="Top 10 projects by cumulative expenditure", labels={"cumulative_expenditure_crore": "Expenditure (₹ crore)", "project_name": "Project"}, hover_data=["state", "physical_progress_pct", "project_code"], color_discrete_sequence=[NAVY])
    st.plotly_chart(style_chart(fig, 540), width="stretch")

elif page == "Project explorer":
    st.subheader("Project explorer")
    st.write(f"Showing **{len(filtered):,}** project records after filters.")
    shown_cols = [
        "project_code", "project_name", "ministry_department", "sector_category", "state",
        "original_cost_crore", "revised_cost_crore", "cumulative_expenditure_crore",
        "physical_progress_pct", "original_target_completion_mm_yyyy", "revised_completion_mm_yyyy",
    ]
    table = filtered[shown_cols].rename(columns={
        "project_code": "Project code", "project_name": "Project name", "ministry_department": "Ministry / department",
        "sector_category": "Sector", "state": "State / location", "original_cost_crore": "Original cost (₹ crore)",
        "revised_cost_crore": "Revised cost (₹ crore)", "cumulative_expenditure_crore": "Cumulative expenditure (₹ crore)",
        "physical_progress_pct": "Physical progress (%)", "original_target_completion_mm_yyyy": "Original target completion",
        "revised_completion_mm_yyyy": "Revised completion",
    })
    st.dataframe(table, width="stretch", hide_index=True, height=540)
    st.download_button("Download filtered project records (CSV)", data=filtered.to_csv(index=False).encode("utf-8-sig"), file_name="project_reality_filtered_projects.csv", mime="text/csv")

    choices = filtered[["project_code", "project_name"]].astype(str)
    choices["label"] = choices["project_code"] + " — " + choices["project_name"].str.slice(0, 115)
    if not choices.empty:
        selection = st.selectbox("View one project", choices["label"].tolist())
        selected_code = choices.loc[choices["label"] == selection, "project_code"].iloc[0]
        item = filtered[filtered["project_code"] == selected_code].iloc[0]
        st.markdown(f"### {item['project_name']}")
        a, b, c, d = st.columns(4)
        a.metric("Physical progress", f"{item['physical_progress_pct']:.2f}%")
        b.metric("Cumulative expenditure", f"₹{item['cumulative_expenditure_crore']:,.2f} crore")
        c.metric("Revised cost", f"₹{item['revised_cost_crore']:,.2f} crore")
        d.metric("Review priority", item["review_priority"])
        st.write(f"**Project code:** {item['project_code']}  ·  **State/location:** {item['state']}")
        st.write(f"**Ministry:** {item['ministry_department']}  ·  **Sector:** {item['sector_category']}")
        st.write(f"**Implementing agency:** {item['implementing_agency']}")
        st.write(f"**Original / revised completion:** {item['original_target_completion_mm_yyyy']} / {item['revised_completion_mm_yyyy']}")
        st.write(f"**Rule-based review note:** {item['review_reasons']}")

elif page == "Risk review queue":
    st.subheader("Risk review queue")
    st.caption("This is a transparent rule-based screening queue. It prioritises records for human verification; it does not accuse a project or contractor of wrongdoing.")
    flagged = filtered[filtered["review_flag_count"] > 0].copy()
    priority = st.multiselect("Priority", ["High", "Review"], default=["High", "Review"])
    flagged = flagged[flagged["review_priority"].isin(priority)]
    a, b, c = st.columns(3)
    a.metric("Records in queue", f"{len(flagged):,}")
    b.metric("High priority", f"{(flagged['review_priority'] == 'High').sum():,}")
    c.metric("Average physical progress", f"{flagged['physical_progress_pct'].mean():.1f}%" if not flagged.empty else "—")
    if flagged.empty:
        st.info("No records meet the selected screening rules under the current filters.")
    else:
        display = flagged[["project_code", "project_name", "state", "revised_cost_crore", "cumulative_expenditure_crore", "physical_progress_pct", "expenditure_pct_revised_cost", "cost_revision_pct", "review_flag_count", "review_priority", "review_reasons"]].sort_values(["review_flag_count", "expenditure_pct_revised_cost"], ascending=False)
        display = display.rename(columns={
            "project_code": "Project code", "project_name": "Project name", "state": "State / location",
            "revised_cost_crore": "Revised cost (₹ crore)", "cumulative_expenditure_crore": "Expenditure (₹ crore)",
            "physical_progress_pct": "Physical progress (%)", "expenditure_pct_revised_cost": "Expenditure / revised cost (%)",
            "cost_revision_pct": "Cost revision (%)", "review_priority": "Priority", "review_reasons": "Why flagged",
        })
        st.dataframe(display, width="stretch", hide_index=True, height=540)
        st.download_button("Download review queue (CSV)", data=flagged.to_csv(index=False).encode("utf-8-sig"), file_name="project_reality_review_queue.csv", mime="text/csv")

else:
    st.subheader("Data notes and methodology")
    st.markdown(
        """
        **Source:** PAIMANA, *Flash Report — March 2026*, Table 6: *All Ongoing Projects*.

        **Fields in this data:** project name, implementing agency, project codes, state/location, ministry/department, sector, approval and start dates, original and revised completion dates, original and revised cost, cumulative expenditure, and reported physical progress.

        **Rule-based review flags:**
        - Revised cost is at least 20% above original cost.
        - Expenditure as a percentage of revised cost is at least 20 percentage points above reported physical progress.
        - Reported physical progress is below 25% while expenditure is at least 50% of revised cost.
        - Cumulative expenditure exceeds revised cost.

        These thresholds are illustrative project-screening rules for this academic prototype, not official PAIMANA risk ratings. A flag should prompt a human to examine source records; it is not proof of fraud, corruption, or poor quality.

        The report does not include invoice-level payment transfers or independent photo/GPS site evidence in this dataset. Those would require additional sources or a later prototype phase.
        """
    )
    st.write("**Source report portal:** https://ipm.mospi.gov.in/")
    st.write("**Report month:** March 2026")
    st.write(f"**Numbered project records extracted:** {all_count:,}")
    st.write("**Extraction note:** The sum of extracted project-level expenditure values differs by ₹1.39 crore from the report overview total. Values were retained as transcribed and have not been silently adjusted. Verify precise totals against the official report before formal use.")
    st.download_button("Download full project dataset (CSV)", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="PAIMANA_March_2026_All_Ongoing_Projects.csv", mime="text/csv")

st.divider()
st.caption("Project Reality · Academic prototype · Report data snapshot: March 2026 · AI does not make the final verification decision.")
