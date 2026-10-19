from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import hashlib
import io
import zipfile
from datetime import date, datetime

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
    /* Keep text-entry controls readable against the light page background. */
    div[data-baseweb="textarea"] textarea,
    div[data-baseweb="input"] input,
    textarea,
    input[type="text"],
    input[type="date"] {{
        background-color: #FFFFFF !important;
        color: #1A2C3B !important;
        -webkit-text-fill-color: #1A2C3B !important;
        caret-color: #1A2C3B !important;
        border-color: #CBD5E1 !important;
    }}
    div[data-baseweb="textarea"] textarea::placeholder,
    div[data-baseweb="input"] input::placeholder,
    textarea::placeholder,
    input::placeholder {{
        color: #7A8795 !important;
        -webkit-text-fill-color: #7A8795 !important;
        opacity: 1 !important;
    }}
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



def gps_distance_km(point1, point2):
    """Calculate the great-circle distance between (latitude, longitude) points."""
    lat1, lon1 = point1
    lat2, lon2 = point2
    earth_radius_km = 6371.0088
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    a = max(0.0, min(1.0, a))
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def gps_line_distance_km(points):
    return sum(
        gps_distance_km(points[index], points[index + 1])
        for index in range(len(points) - 1)
    )


def parse_gps_geojson(data):
    obj = json.loads(data.decode("utf-8-sig"))
    lines = []

    def visit(item):
        if not isinstance(item, dict):
            return
        geometry_type = item.get("type")
        if geometry_type == "FeatureCollection":
            for feature in item.get("features", []):
                visit(feature)
        elif geometry_type == "Feature":
            visit(item.get("geometry"))
        elif geometry_type == "GeometryCollection":
            for geometry in item.get("geometries", []):
                visit(geometry)
        elif geometry_type == "LineString":
            points = [
                (float(coord[1]), float(coord[0]))
                for coord in item.get("coordinates", [])
                if isinstance(coord, (list, tuple)) and len(coord) >= 2
            ]
            if len(points) >= 2:
                lines.append(points)
        elif geometry_type == "MultiLineString":
            for coordinates in item.get("coordinates", []):
                points = [
                    (float(coord[1]), float(coord[0]))
                    for coord in coordinates
                    if isinstance(coord, (list, tuple)) and len(coord) >= 2
                ]
                if len(points) >= 2:
                    lines.append(points)

    visit(obj)
    if not lines:
        raise ValueError("No usable LineString or MultiLineString was found in the file.")
    return lines


def parse_gps_gpx(data):
    root = ET.fromstring(data)
    lines = []

    def local_name(element):
        return element.tag.rsplit("}", 1)[-1]

    for segment in root.iter():
        if local_name(segment) == "trkseg":
            points = [
                (float(point.attrib["lat"]), float(point.attrib["lon"]))
                for point in segment.iter()
                if local_name(point) == "trkpt"
            ]
            if len(points) >= 2:
                lines.append(points)

    if not lines:
        for route in root.iter():
            if local_name(route) == "rte":
                points = [
                    (float(point.attrib["lat"]), float(point.attrib["lon"]))
                    for point in route.iter()
                    if local_name(point) == "rtept"
                ]
                if len(points) >= 2:
                    lines.append(points)

    if not lines:
        points = [
            (float(point.attrib["lat"]), float(point.attrib["lon"]))
            for point in root.iter()
            if local_name(point) == "trkpt"
        ]
        if len(points) >= 2:
            lines.append(points)

    if not lines:
        raise ValueError("No usable GPS track points were found in the GPX file.")
    return lines


def parse_gps_track(filename, data):
    """Return track lines and point count for a GPX, GeoJSON, or JSON upload."""
    if filename.lower().endswith(".gpx"):
        lines = parse_gps_gpx(data)
    elif filename.lower().endswith((".geojson", ".json")):
        lines = parse_gps_geojson(data)
    else:
        raise ValueError("Use a .gpx, .geojson, or .json track file.")

    point_count = sum(len(line) for line in lines)
    total_km = sum(gps_line_distance_km(line) for line in lines)
    if not math.isfinite(total_km) or total_km <= 0:
        raise ValueError("The uploaded track has no positive, usable distance.")
    return lines, total_km, point_count


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

# Photo evidence records are session-only until the user downloads the evidence bundle.
st.session_state.setdefault("project_photo_evidence", [])

st.caption("Data source: PAIMANA March 2026 Flash Report, Table 6: All Ongoing Projects. Project-level data extracted from the report.")
st.warning(
    "Review flags are simple rules for prioritising human review, not AI findings or proof of wrongdoing. "
    "This report gives project cost, cumulative expenditure, dates and reported physical progress; it does not provide invoice-level payment trails or independent site-photo evidence."
)


st.markdown("### Navigate Project Reality")
page = st.radio(
    "Choose a section",
    ["Overview", "Project explorer", "Risk review queue", "Money Trail & Fund Reconciliation", "Road Length Reality Check", "GPS Road Verification", "Construction Photo Evidence Review", "Data notes"],
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

    k2.metric(
        "Original cost",
        f"₹{filtered_original:,.2f} crore"
        if filtered_original < 100000
        else crore_to_lakh_crore(filtered_original)
    )

    k3.metric(
        "Revised cost",
        f"₹{filtered_revised:,.2f} crore"
        if filtered_revised < 100000
        else crore_to_lakh_crore(filtered_revised)
    )

    k4.metric(
        "Cumulative expenditure",
        f"₹{filtered_spend:,.2f} crore"
        if filtered_spend < 100000
        else crore_to_lakh_crore(filtered_spend)
       )
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

        if str(item["project_code"]) == "618511":
            st.markdown("### Desk-Based Source Verification")
            st.success(
                "SOURCE AVAILABLE: Government project and tender references."
            )

            st.info(
                "PROVISIONAL: Road chainages and design lengths "
                "need confirmation from an authoritative document."
            )

            st.warning(
                "EVIDENCE STILL NEEDED: A verified road alignment "
                "and genuine GPS track matching this project section."
            )

            st.markdown(
                "[Open official PAIMANA dashboard]"
                "(https://ipm.mospi.gov.in/Home/PublicDashboard)"
            )

            st.markdown(
                "[Open official NHAI government tender record]"
                "(https://etenders.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=SuUDWhfsOKvKqIFmbU29B6A%3D%3D)"
            )

            st.write(
                "**Tender reference:** "
                "Proj-27015 (21)/1/2025-PIU Pune"
            )
            st.write("**Tender ID:** 2025_NHAI_225109_1")
            st.write("**Tender value:** ₹604.59 crore")
            st.markdown(
                "**Official MoRTH/PIB reference:** "
                "[Traffic congestion and road infrastructure in Pune]"
                "(https://www.pib.gov.in/PressReleasePage.aspx?PRID=2198344&lang=1&reg=1)"
            )
            st.write(
                "**Government-reported service/slip road length:** 41 km"
            )
            st.write(
                "**Target completion reported by PIB:** June 2027"
            )
            st.info(
                "The 32.350 km design sections cited from a secondary "
                "report have not yet been reconciled with the official "
                "project scope. Treat them as provisional."
            )

            st.write(
                "**March 2026 dataset snapshot:** "
                "Expenditure ₹43.71 crore; reported progress 13.9%."
            )

            st.write(
                "**PAIMANA public dashboard:** "
                "The displayed cumulative expenditure was reported "
                "as ₹54.16 crore in our earlier check. Verify the "
                "current figure and access date before relying on it."
            )

            st.markdown(
                "**Technical design reference:** "
                "[Pune-Satara NH-48 Pavement Design Report]"
                "(https://www.scribd.com/document/923560767/136-Pavement-Design-Report-Pune-Satara-2)"
            )

            st.write(
                "**Provisionally reported design alignment:** 32.350 km"
            )

            st.markdown(
                "**Reported design sections:**\n"
                "- 819+500 to 825+150 — 5.650 km\n"
                "- 837+400 to 853+550 — 16.150 km\n"
                "- 853+550 to 864+100 — 10.550 km"
            )

            st.warning(
                "The technical report copy is hosted on Scribd, not "
                "an official NHAI website. Verify these chainages and "
                "lengths against an authoritative project document. "
                "The sample GPS track is artificial and is not evidence "
                "for this project."
            )

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


elif page == "Money Trail & Fund Reconciliation":
    st.subheader("Money Trail & Fund Reconciliation")
    st.write(
        "Follow project financial records from the reported project cost to fund releases, "
        "contractor payments, invoices, and supporting documents."
    )
    st.info(
        "The PAIMANA March 2026 dataset contains aggregate cost and cumulative-expenditure fields. "
        "It does not contain transaction-level releases, contractor payments, or invoices. "
        "Upload a genuine transaction ledger below to perform reference-based checks. "
        "No missing-money conclusion is generated from the project budget alone."
    )

    choices = filtered[["project_code", "project_name"]].astype(str).drop_duplicates()
    choices["label"] = choices["project_code"] + " — " + choices["project_name"].str.slice(0, 115)
    if choices.empty:
        st.warning("No projects match the current search and filters. Clear or adjust the filters above.")
    else:
        preferred = choices.index[choices["project_code"].astype(str).str.strip() == "618511"].tolist()
        default_idx = choices.index.get_loc(preferred[0]) if preferred else 0
        selection = st.selectbox(
            "Select the project to investigate",
            choices["label"].tolist(),
            index=min(default_idx, len(choices) - 1),
            key="money_trail_project",
        )
        selected_code = choices.loc[choices["label"] == selection, "project_code"].iloc[0].strip()
        item = filtered[filtered["project_code"].astype(str).str.strip() == selected_code].iloc[0]

        st.markdown(f"### {item['project_name']}")
        st.caption(
            f"Project code: {selected_code} · {item['implementing_agency']} · "
            f"Source snapshot: {item.get('report_month', 'March 2026')}"
        )

        original_cost = float(item["original_cost_crore"]) if pd.notna(item["original_cost_crore"]) else 0.0
        revised_cost = float(item["revised_cost_crore"]) if pd.notna(item["revised_cost_crore"]) else 0.0
        expenditure = float(item["cumulative_expenditure_crore"]) if pd.notna(item["cumulative_expenditure_crore"]) else 0.0
        progress = float(item["physical_progress_pct"]) if pd.notna(item["physical_progress_pct"]) else None
        expenditure_pct = (expenditure / revised_cost * 100) if revised_cost > 0 else None
        cost_less_spend = revised_cost - expenditure

        a, b, c, d = st.columns(4)
        a.metric("Original cost", f"₹{original_cost:,.2f} Cr")
        b.metric("Revised cost", f"₹{revised_cost:,.2f} Cr")
        c.metric("Cumulative expenditure", f"₹{expenditure:,.2f} Cr")
        d.metric("Reported physical progress", f"{progress:.1f}%" if progress is not None else "Not provided")

        st.markdown("#### What the existing project dataset tells us")
        e, f, g = st.columns(3)
        e.metric("Expenditure / revised cost", f"{expenditure_pct:.2f}%" if expenditure_pct is not None else "Not calculable")
        f.metric("Revised cost less expenditure", f"₹{cost_less_spend:,.2f} Cr")
        g.metric("Funds released", "Not in dataset")
        st.caption(
            "‘Revised cost less expenditure’ is an arithmetic comparison, not a cash balance or missing-money estimate. "
            "Project cost, fund release, expenditure and contractor payments are different accounting concepts."
        )

        st.markdown("#### Add the transaction-level records")
        st.write(
            "Upload a CSV containing records from an official fund-release report, payment ledger, invoice register, "
            "or other traceable source. The app processes the upload for this session; it does not permanently store "
            "the file in a database."
        )
        expected_cols = [
            "project_code", "record_type", "record_id", "date", "counterparty",
            "amount_crore", "linked_record_id", "description", "source_url", "verification_status"
        ]
        template_df = pd.DataFrame(columns=expected_cols)
        st.download_button(
            "Download transaction CSV template",
            data=template_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="project_reality_transaction_template.csv",
            mime="text/csv",
            key="download_money_trail_template",
        )
        st.caption(
            "Required columns: project_code, record_type, record_id, date, counterparty, amount_crore, "
            "linked_record_id, description, source_url, verification_status. "
            "Use record_type values: fund_release, payment, invoice, or work_certificate. "
            "For a payment-to-invoice check, put the invoice's record_id in the payment row's linked_record_id. "
            "Amounts must be in ₹ crore. Include only records you can source."
        )
        uploaded_ledger = st.file_uploader(
            "Upload the transaction ledger (CSV)",
            type=["csv"],
            key="money_trail_ledger_upload",
        )

        if uploaded_ledger is not None:
            try:
                ledger = pd.read_csv(uploaded_ledger, encoding="utf-8-sig", dtype={"project_code": str})
            except Exception as exc:
                st.error(f"Could not read the uploaded CSV: {exc}")
                ledger = None

            if ledger is not None:
                missing_cols = [col for col in expected_cols if col not in ledger.columns]
                if missing_cols:
                    st.error("The uploaded CSV is missing these required columns: " + ", ".join(missing_cols))
                else:
                    ledger = ledger[expected_cols].copy()
                    for col in ["project_code", "record_type", "record_id", "date", "counterparty", "linked_record_id", "description", "source_url", "verification_status"]:
                        ledger[col] = ledger[col].fillna("").astype(str).str.strip()
                    ledger["record_type"] = ledger["record_type"].str.casefold()
                    ledger["amount_crore"] = pd.to_numeric(ledger["amount_crore"], errors="coerce")
                    ledger["project_code_normalized"] = ledger["project_code"].str.replace(r"\.0$", "", regex=True).str.strip()
                    ledger["record_id_normalized"] = ledger["record_id"].str.strip()
                    ledger["linked_record_id_normalized"] = ledger["linked_record_id"].str.strip()
                    allowed_types = {"fund_release", "payment", "invoice", "work_certificate"}
                    invalid_types = sorted(set(ledger["record_type"]) - allowed_types - {""})
                    bad_amounts = ledger["amount_crore"].isna() | (ledger["amount_crore"] < 0)
                    if invalid_types:
                        st.warning("Unrecognized record_type value(s): " + ", ".join(invalid_types) + ". Use the values listed above.")
                    if bad_amounts.any():
                        st.warning(f"{int(bad_amounts.sum())} row(s) have a missing, non-numeric, or negative amount and will be excluded from monetary totals.")

                    project_ledger = ledger[ledger["project_code_normalized"] == selected_code].copy()
                    if project_ledger.empty:
                        st.warning(f"No uploaded records match project code {selected_code}. Check the project_code values in your CSV.")
                    else:
                        valid_amount = project_ledger["amount_crore"].notna() & (project_ledger["amount_crore"] >= 0)
                        records = project_ledger[valid_amount].copy()
                        releases = records.loc[records["record_type"] == "fund_release", "amount_crore"].sum()
                        payments = records.loc[records["record_type"] == "payment", "amount_crore"].sum()
                        invoices = records.loc[records["record_type"] == "invoice", "amount_crore"].sum()
                        certs = records.loc[records["record_type"] == "work_certificate", "amount_crore"].sum()

                        st.markdown(f"#### Uploaded records for project {selected_code}")
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Recorded fund releases", f"₹{releases:,.2f} Cr")
                        r2.metric("Recorded payments", f"₹{payments:,.2f} Cr")
                        r3.metric("Recorded invoice amounts", f"₹{invoices:,.2f} Cr")
                        r4.metric("Work certificate amounts", f"₹{certs:,.2f} Cr")

                        invoice_rows = records[records["record_type"] == "invoice"].copy()
                        payment_rows = records[records["record_type"] == "payment"].copy()
                        invoice_ids = set(invoice_rows.loc[invoice_rows["record_id_normalized"] != "", "record_id_normalized"])
                        payment_rows["invoice_reference_found"] = payment_rows["linked_record_id_normalized"].isin(invoice_ids) & (payment_rows["linked_record_id_normalized"] != "")
                        linked_payment_amount = payment_rows.loc[payment_rows["invoice_reference_found"], "amount_crore"].sum()
                        unlinked_payment_rows = payment_rows[~payment_rows["invoice_reference_found"]]
                        unlinked_payment_amount = unlinked_payment_rows["amount_crore"].sum()

                        p1, p2, p3 = st.columns(3)
                        p1.metric("Payments linked to an uploaded invoice ID", f"₹{linked_payment_amount:,.2f} Cr")
                        p2.metric("Payments without a matching invoice ID", f"₹{unlinked_payment_amount:,.2f} Cr")
                        p3.metric("Payment rows needing reference review", f"{len(unlinked_payment_rows):,}")
                        st.caption(
                            "A reference match only means the entered invoice ID exists in this uploaded file. "
                            "It does not prove that the payment was proper, that the invoice is genuine, or that the work was completed."
                        )

                        if not invoice_rows.empty:
                            inv_totals = invoice_rows.groupby("record_id_normalized", dropna=False)["amount_crore"].sum().rename("Invoice amount (₹ crore)")
                            pay_totals = payment_rows[payment_rows["invoice_reference_found"]].groupby("linked_record_id_normalized")["amount_crore"].sum().rename("Payments linked (₹ crore)")
                            reconciliation = pd.concat([inv_totals, pay_totals], axis=1).fillna(0).reset_index().rename(columns={"record_id_normalized": "Invoice record ID"})
                            reconciliation["Invoice amount less linked payments (₹ crore)"] = reconciliation["Invoice amount (₹ crore)"] - reconciliation["Payments linked (₹ crore)"]
                            reconciliation["Review note"] = reconciliation["Invoice amount less linked payments (₹ crore)"].apply(
                                lambda value: "Amounts match within ₹0.01 Cr tolerance" if abs(value) <= 0.01 else ("Invoice amount exceeds linked payments; check payment timing/retention" if value > 0 else "Linked payments exceed invoice amount; check links/duplicates/adjustments")
                            )
                            st.markdown("#### Invoice-to-payment reference check")
                            st.dataframe(reconciliation, width="stretch", hide_index=True)
                            st.caption(
                                "Differences are review prompts, not proof of missing money. Partial payments, advances, retention, taxes, "
                                "multiple invoices, amendments or different accounting periods can explain differences. Verify the contract and ledger before interpreting them."
                            )

                        source_missing = (records["source_url"].str.strip() == "")
                        not_marked_verified = ~records["verification_status"].str.casefold().eq("verified")
                        s1, s2 = st.columns(2)
                        s1.metric("Records without a source URL", f"{int(source_missing.sum()):,}")
                        s2.metric("Records not marked 'verified'", f"{int(not_marked_verified.sum()):,}")
                        st.markdown("#### Uploaded ledger records")
                        show_cols = ["project_code", "record_type", "record_id", "date", "counterparty", "amount_crore", "linked_record_id", "description", "source_url", "verification_status"]
                        st.dataframe(project_ledger[show_cols], width="stretch", hide_index=True)
                        st.download_button(
                            "Download filtered ledger records (CSV)",
                            data=project_ledger[show_cols].to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"project_reality_ledger_{selected_code}.csv",
                            mime="text/csv",
                            key="download_filtered_money_trail",
                        )
                        st.warning(
                            "Do not subtract invoice totals, recorded payments, and PAIMANA cumulative expenditure as if they were separate pots of money. "
                            "They may describe overlapping stages of the same expenditure and may cover different dates or accounting scopes. "
                            "A defensible unexplained amount requires reconciled source records and a defined accounting period."
                        )

elif page == "Road Length Reality Check":
    st.subheader("Road Length Reality Check")
    st.write(
        "Compare the approved road length with the length reported as completed "
        "and, where genuine matching GPS evidence exists, the measured track length."
    )
    st.warning(
        "This tool calculates differences from values entered by the reviewer. "
        "It does not independently authenticate documents, prove the entire road was built, "
        "or establish missing money. Compare the same road sections and chainages."
    )

    choices = filtered[["project_code", "project_name"]].astype(str).drop_duplicates()
    choices["label"] = choices["project_code"] + " — " + choices["project_name"].str.slice(0, 115)
    if choices.empty:
        st.warning("No projects match the current search and filters. Clear or adjust the filters above.")
    else:
        preferred = choices.index[choices["project_code"].astype(str).str.strip() == "618511"].tolist()
        default_idx = choices.index.get_loc(preferred[0]) if preferred else 0
        selection = st.selectbox(
            "Select the project to investigate",
            choices["label"].tolist(),
            index=min(default_idx, len(choices) - 1),
            key="road_length_project",
        )
        selected_code = choices.loc[choices["label"] == selection, "project_code"].iloc[0].strip()
        item = filtered[filtered["project_code"].astype(str).str.strip() == selected_code].iloc[0]
        st.markdown(f"### {item['project_name']}")
        st.caption(f"Project code: {selected_code} · {item['implementing_agency']} · Source snapshot: March 2026")

        linked_photos = [
            entry for entry in st.session_state.get("project_photo_evidence", [])
            if str(entry.get("record", {}).get("project_code", "")).strip() == selected_code
        ]
        if linked_photos:
            st.info(
                f"Construction photo evidence recorded in this browser session for this project: "
                f"{len(linked_photos)} item(s). These records are user-entered and not independently authenticated."
            )
            photo_summary = pd.DataFrame([
                {
                    "Evidence ID": entry["record"].get("evidence_id", ""),
                    "Photo": entry.get("filename", ""),
                    "Inspection date": entry["record"].get("inspection_date_recorded_by_reviewer", ""),
                    "Category": entry["record"].get("evidence_category", ""),
                    "Assessment": entry["record"].get("reviewer_assessment", ""),
                    "Verification status": entry["record"].get("verification_status", ""),
                }
                for entry in linked_photos
            ])
            st.dataframe(photo_summary, width="stretch", hide_index=True)
        else:
            st.caption("No construction photo records are linked to this project in the current browser session.")

        if selected_code == "618511":
            st.info(
                "A Ministry/PIB release has described 41 km of Pune–Satara NH-48 service/slip roads. "
                "Treat this as a reported scope figure until it is matched to the approved contract/BOQ "
                "and exact chainages. It is not a measurement of the road already built."
            )
            st.markdown(
                "Source reference: [Ministry of Road Transport and Highways / PIB release]"
                "(https://www.pib.gov.in/PressReleasePage.aspx?PRID=2198344&lang=1&reg=1)"
            )

        st.markdown("#### 1. Enter comparable length records")
        st.caption(
            "Only enter lengths supported by records. If one measurement covers a different road section, "
            "direction, service road, or chainage range, do not compare it directly with another."
        )

        approved_available = st.checkbox(
            "I have an approved/tendered length for this exact scope",
            value=False,
            key="road_approved_available",
        )
        approved_length = None
        approved_source = ""
        approved_scope = ""
        if approved_available:
            approved_length = st.number_input(
                "Approved/tendered length (km)", min_value=0.0, max_value=5000.0,
                value=0.0, step=0.1, format="%.3f",
                key="road_approved_length",
            )
            approved_scope = st.text_input(
                "Approved chainages / section covered", key="road_approved_scope",
                placeholder="e.g. start chainage to end chainage; both sides if applicable",
            )
            approved_source = st.text_input(
                "Approved length source URL or document reference", key="road_approved_source",
                value="",
            )

        reported_available = st.checkbox(
            "I have an official reported-completed length",
            value=False,
            key="road_reported_available",
        )
        reported_length = None
        reported_source = ""
        reported_date = ""
        if reported_available:
            reported_length = st.number_input(
                "Reported completed length (km)", min_value=0.0, max_value=5000.0,
                value=0.0, step=0.1, format="%.3f", key="road_reported_length",
            )
            reported_date = st.text_input(
                "Report date / reporting period", key="road_reported_date", placeholder="e.g. March 2026"
            )
            reported_source = st.text_input(
                "Reported completion source URL or document reference", key="road_reported_source"
            )

        st.markdown("#### Upload a GPS track to calculate its length")
        st.caption(
            "Upload a genuine track covering the same road sections and chainages as the approved length. "
            "The bundled sample track used by the separate GPS demo is synthetic and must not be used as project evidence."
        )
        uploaded_gps = st.file_uploader(
            "Upload genuine GPS evidence (.gpx, .geojson or .json)",
            type=["gpx", "geojson", "json"],
            key=f"road_gps_upload_{selected_code}",
        )
        gps_length = None
        gps_source = ""
        gps_scope = ""
        gps_method = "Not provided"
        gps_point_count = 0
        gps_segment_count = 0
        gps_confirmation_status = "Not provided"

        if uploaded_gps is not None:
            gps_source = uploaded_gps.name
            try:
                gps_lines, calculated_gps_km, gps_point_count = parse_gps_track(
                    uploaded_gps.name, uploaded_gps.getvalue()
                )
                gps_segment_count = len(gps_lines)
                st.metric("Calculated length from uploaded track", f"{calculated_gps_km:,.3f} km")
                st.caption(
                    f"File: {uploaded_gps.name} · {gps_point_count:,} points · "
                    f"{gps_segment_count:,} track segment(s). This is a coordinate-based calculation, not independent proof of road completion."
                )
                gps_scope = st.text_input(
                    "GPS track coverage / chainages",
                    key=f"road_gps_scope_{selected_code}",
                    placeholder="Describe the road section, direction, and start/end chainages covered",
                )
                gps_confirmed = st.checkbox(
                    "I confirm this is genuine GPS evidence and matches the same approved road scope",
                    value=False,
                    key=f"road_gps_confirm_{selected_code}",
                )
                if gps_confirmed:
                    gps_length = calculated_gps_km
                    gps_method = "Uploaded GPS track; length calculated by this app"
                    gps_confirmation_status = "User confirmed scope and authenticity; not independently authenticated by the app"
                    st.success("GPS track length will be included in the road-length comparison.")
                else:
                    st.warning(
                        "The calculated length is shown for inspection only. Confirm the track's source and matching scope "
                        "before the app uses it in comparison results."
                    )
            except Exception as exc:
                st.error(f"Could not calculate length from this GPS file: {exc}")
                st.caption("Check that the file is valid and contains a line track with at least two coordinates.")
        else:
            with st.expander("Already have a GPS length from a separate survey record? Enter it instead"):
                manual_gps_available = st.checkbox(
                    "I have a documented GPS measurement for this same road scope",
                    value=False,
                    key=f"road_manual_gps_available_{selected_code}",
                )
                if manual_gps_available:
                    manual_gps_length = st.number_input(
                        "GPS-measured length from the report (km)", min_value=0.0, max_value=5000.0,
                        value=0.0, step=0.001, format="%.3f", key=f"road_manual_gps_length_{selected_code}",
                    )
                    gps_scope = st.text_input(
                        "GPS report coverage / chainages", key=f"road_manual_gps_scope_{selected_code}",
                        placeholder="Confirm this covers the same approved section",
                    )
                    gps_source = st.text_input(
                        "GPS report reference or source URL", key=f"road_manual_gps_source_{selected_code}"
                    )
                    manual_confirmed = st.checkbox(
                        "I confirm this length is copied from a genuine, traceable GPS survey record",
                        value=False,
                        key=f"road_manual_gps_confirm_{selected_code}",
                    )
                    if manual_gps_length > 0 and manual_confirmed:
                        gps_length = float(manual_gps_length)
                        gps_method = "Manually transcribed from separate GPS survey record"
                        gps_confirmation_status = "User confirmed; source not independently authenticated by the app"
                    elif manual_gps_length > 0:
                        st.warning("Confirm that the source is genuine before including this value in comparison results.")

        st.markdown("#### 2. Comparison results")
        available_lengths = []
        if approved_length is not None:
            available_lengths.append(("Approved/tendered", approved_length))
        if reported_length is not None:
            available_lengths.append(("Reported completed", reported_length))
        if gps_length is not None:
            available_lengths.append(("GPS-measured", gps_length))

        if approved_length is None or approved_length <= 0:
            st.info("Enter a positive approved/tendered length for the exact scope first. Without it, a length shortfall cannot be calculated.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Approved/tendered length", f"{approved_length:,.3f} km")
            m2.metric("Reported completed length", f"{reported_length:,.3f} km" if reported_length is not None else "Not provided")
            m3.metric("GPS-measured length", f"{gps_length:,.3f} km" if gps_length is not None else "Not provided")

            result_rows = []
            if reported_length is not None:
                diff = reported_length - approved_length
                pct = (diff / approved_length * 100) if approved_length > 0 else None
                result_rows.append({
                    "Comparison": "Reported completed vs approved",
                    "Reference length (km)": approved_length,
                    "Compared length (km)": reported_length,
                    "Difference (km)": round(diff, 3),
                    "Difference (%)": round(pct, 2) if pct is not None else None,
                    "Interpretation": "Reported length is below reference; investigate scope and records" if diff < 0 else ("Reported length exceeds reference; confirm scope/measurement" if diff > 0 else "Lengths match numerically"),
                })
            if gps_length is not None:
                diff = gps_length - approved_length
                pct = (diff / approved_length * 100) if approved_length > 0 else None
                result_rows.append({
                    "Comparison": "GPS-measured vs approved",
                    "Reference length (km)": approved_length,
                    "Compared length (km)": gps_length,
                    "Difference (km)": round(diff, 3),
                    "Difference (%)": round(pct, 2) if pct is not None else None,
                    "Interpretation": "GPS length is below reference; confirm track coverage and site work" if diff < 0 else ("GPS length exceeds reference; confirm scope/measurement" if diff > 0 else "Lengths match numerically"),
                })
            if reported_length is not None and gps_length is not None:
                diff = gps_length - reported_length
                pct = (diff / reported_length * 100) if reported_length > 0 else None
                result_rows.append({
                    "Comparison": "GPS-measured vs reported completed",
                    "Reference length (km)": reported_length,
                    "Compared length (km)": gps_length,
                    "Difference (km)": round(diff, 3),
                    "Difference (%)": round(pct, 2) if pct is not None else None,
                    "Interpretation": "GPS length is lower; inspect track coverage and reported measurement" if diff < 0 else ("GPS length is higher; confirm scope and avoid double-counting" if diff > 0 else "Lengths match numerically"),
                })
            if result_rows:
                result_df = pd.DataFrame(result_rows)
                st.dataframe(result_df, width="stretch", hide_index=True)
                st.warning(
                    "A calculated length difference is a review lead, not proof of missing construction or misused money. "
                    "Check road section, carriageway/service-road scope, chainages, measurement date, and supporting certificates."
                )
                evidence_status = "User-entered evidence references; not independently authenticated by this app."
                snapshot = pd.DataFrame([{
                    "project_code": selected_code,
                    "project_name": item["project_name"],
                    "approved_length_km": approved_length,
                    "approved_scope": approved_scope,
                    "approved_source": approved_source,
                    "reported_completed_length_km": reported_length,
                    "reported_completion_date": reported_date,
                    "reported_completion_source": reported_source,
                    "gps_measured_length_km": gps_length,
                    "gps_measurement_method": gps_method,
                    "gps_uploaded_point_count": gps_point_count,
                    "gps_uploaded_segment_count": gps_segment_count,
                    "gps_scope": gps_scope,
                    "gps_source": gps_source,
                    "gps_confirmation_status": gps_confirmation_status,
                    "evidence_status": evidence_status,
                }])
                st.download_button(
                    "Download road-length review record (CSV)",
                    data=snapshot.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"road_length_review_{selected_code}.csv",
                    mime="text/csv",
                )
            else:
                st.info("Add an official reported length or a genuine GPS measurement to calculate a comparison.")

        with st.expander("What this feature can and cannot conclude"):
            st.markdown(
                "- It can calculate differences between lengths entered for comparable scopes.\n"
                "- It cannot authenticate a source URL or prove a GPS track is complete.\n"
                "- A reported scope length is not the same as completed length.\n"
                "- A shortfall does not by itself show where money went. Link any finding to bills, payments, "
                "work certificates and an approved BOQ before drawing a financial conclusion."
            )

elif page == "GPS Road Verification":
    st.subheader("GPS Road Verification")
    st.write(
        "Compare approved road length with a distance calculated "
        "from an uploaded GPS track."
    )
    st.info(
        "The bundled sample GPS track is synthetic and is not "
        "real project evidence."
    )
    st.page_link(
        "pages/2_GPS_Road_Verification.py",
        label="Open GPS Road Verification calculator",
        icon="🛣️",
    )

elif page == "Construction Photo Evidence Review":
    st.subheader("Construction Photo Evidence Review")
    st.write(
        "Attach a photograph and reviewer observations to a selected project so the evidence can appear "
        "in that project's Road Length Reality Check during this browser session."
    )
    st.warning(
        "A photo alone does not verify project identity, capture location/date, construction quality, "
        "completion, or wrongdoing. Uploaded images and reviewer-entered details are not independently verified. "
        "Records are kept only in this active Streamlit session until you download the evidence bundle."
    )

    photo_project_choices = df[["project_code", "project_name", "state", "implementing_agency"]].astype(str).drop_duplicates()
    photo_project_choices["label"] = (
        photo_project_choices["project_code"] + " — " + photo_project_choices["project_name"].str.slice(0, 115)
    )
    preferred_photo = photo_project_choices.index[
        photo_project_choices["project_code"].str.strip() == "618511"
    ].tolist()
    default_photo_index = photo_project_choices.index.get_loc(preferred_photo[0]) if preferred_photo else 0

    if photo_project_choices.empty:
        st.warning("No project records are available to attach evidence.")
    else:
        photo_project_label = st.selectbox(
            "Select the project this photo relates to",
            photo_project_choices["label"].tolist(),
            index=min(default_photo_index, len(photo_project_choices) - 1),
            key="photo_evidence_project",
        )
        photo_project = photo_project_choices.loc[
            photo_project_choices["label"] == photo_project_label
        ].iloc[0]
        selected_photo_project_code = str(photo_project["project_code"]).strip()
        st.caption(
            f"Project code: {selected_photo_project_code} · {photo_project['implementing_agency']} · "
            f"{photo_project['state']}"
        )

        with st.form("project_photo_evidence_form", clear_on_submit=True):
            st.markdown("#### 1. Inspection details")
            reported_location = st.text_input(
                "Reported site location",
                placeholder="Enter road section / location; do not guess coordinates",
            )
            inspection_date = st.date_input(
                "Inspection date recorded by reviewer",
                value=date.today(),
            )
            category = st.selectbox(
                "Evidence category",
                [
                    "Construction progress",
                    "Road surface or pavement",
                    "Building or structure",
                    "Construction materials",
                    "Site safety",
                    "Other",
                ],
            )
            assessment = st.selectbox(
                "Reviewer assessment",
                [
                    "Pending human review",
                    "Potential discrepancy to verify",
                    "Photo unclear or insufficient",
                    "No obvious discrepancy visible in this photo",
                ],
            )
            source_reference = st.text_input(
                "Photo source / reference (optional)",
                placeholder="e.g. inspection report ID, official URL, or who supplied the photo",
            )
            st.markdown("#### 2. Upload a photo and record observations")
            photo = st.file_uploader(
                "Choose a JPG or PNG image",
                type=["jpg", "jpeg", "png"],
            )
            notes = st.text_area(
                "Inspection notes",
                placeholder="Describe only what is visible and what should be checked next.",
                height=110,
            )
            submitted_photo = st.form_submit_button("Save evidence record for this session")

        if submitted_photo:
            if photo is None:
                st.error("Upload a JPG or PNG photograph before saving the evidence record.")
            else:
                photo_bytes = photo.getvalue()
                photo_hash = hashlib.sha256(photo_bytes).hexdigest()
                duplicate = any(
                    entry.get("photo_sha256") == photo_hash
                    and str(entry.get("record", {}).get("project_code", "")).strip() == selected_photo_project_code
                    for entry in st.session_state["project_photo_evidence"]
                )
                if duplicate:
                    st.warning("This same photo file is already recorded for this project in the current session.")
                else:
                    evidence_id = datetime.now().strftime("PHOTO-%Y%m%d-%H%M%S-%f")
                    record = {
                        "evidence_id": evidence_id,
                        "project_code": selected_photo_project_code,
                        "project_name": str(photo_project["project_name"]),
                        "implementing_agency": str(photo_project["implementing_agency"]),
                        "project_state": str(photo_project["state"]),
                        "reported_site_location": reported_location.strip(),
                        "inspection_date_recorded_by_reviewer": inspection_date.isoformat(),
                        "evidence_category": category,
                        "reviewer_assessment": assessment,
                        "photo_source_reference": source_reference.strip(),
                        "inspection_notes": notes.strip(),
                        "photo_filename": Path(photo.name).name,
                        "photo_size_bytes": len(photo_bytes),
                        "photo_sha256": photo_hash,
                        "record_created_at_local": datetime.now().isoformat(timespec="seconds"),
                        "verification_status": "Not independently verified",
                        "limitations": (
                            "Photo authenticity, capture date, GPS location, project identity, and construction completion "
                            "have not been independently verified by this application."
                        ),
                    }
                    st.session_state["project_photo_evidence"].append({
                        "record": record,
                        "filename": Path(photo.name).name,
                        "photo_bytes": photo_bytes,
                        "photo_sha256": photo_hash,
                    })
                    st.success(
                        f"Saved {evidence_id} to this active session and linked it to project {selected_photo_project_code}. "
                        "Download the evidence bundle before closing or restarting the app."
                    )

    all_photo_entries = st.session_state.get("project_photo_evidence", [])
    if all_photo_entries:
        st.markdown("#### Evidence records saved in this session")
        all_photo_rows = [
            {
                "Evidence ID": entry["record"].get("evidence_id", ""),
                "Project code": entry["record"].get("project_code", ""),
                "Project": entry["record"].get("project_name", ""),
                "Photo": entry.get("filename", ""),
                "Inspection date": entry["record"].get("inspection_date_recorded_by_reviewer", ""),
                "Category": entry["record"].get("evidence_category", ""),
                "Assessment": entry["record"].get("reviewer_assessment", ""),
                "Verification": entry["record"].get("verification_status", ""),
            }
            for entry in all_photo_entries
        ]
        st.dataframe(pd.DataFrame(all_photo_rows), width="stretch", hide_index=True)

        export_project_codes = sorted({
            str(entry["record"].get("project_code", "")).strip() for entry in all_photo_entries
        })
        export_scope = st.selectbox(
            "Evidence bundle to download",
            ["All projects"] + export_project_codes,
            key="photo_evidence_export_scope",
        )
        if export_scope == "All projects":
            export_entries = all_photo_entries
        else:
            export_entries = [
                entry for entry in all_photo_entries
                if str(entry["record"].get("project_code", "")).strip() == export_scope
            ]

        if export_entries:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                records_manifest = []
                for index, entry in enumerate(export_entries, start=1):
                    record = entry["record"]
                    records_manifest.append(record)
                    safe_filename = Path(entry["filename"]).name
                    archive.writestr(
                        f"photos/{record.get('project_code', 'unknown')}/{index}_{safe_filename}",
                        entry["photo_bytes"],
                    )
                archive.writestr(
                    "inspection_records.json",
                    json.dumps(records_manifest, indent=2, ensure_ascii=False).encode("utf-8"),
                )
            st.download_button(
                "Download selected photo evidence bundle (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=(
                    "project_reality_photo_evidence_all_projects.zip"
                    if export_scope == "All projects"
                    else f"project_reality_photo_evidence_{export_scope}.zip"
                ),
                mime="application/zip",
            )
        st.caption(
            "The evidence bundle preserves the uploaded images and JSON records for download. "
            "It is not a permanent database or independent verification."
        )
    else:
        st.info(
            "No evidence has been saved in this session yet. Upload a photo, choose its project, "
            "and save the record. It will then appear in this list and in that project's Road Length Reality Check."
        )

elif page == "Data notes":
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
