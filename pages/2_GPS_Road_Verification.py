
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="GPS Road Verification",
    page_icon="🛣️",
    layout="wide"
)

st.title("GPS Road Verification")
st.write(
    "Compare an approved road length with a distance calculated "
    "from an uploaded GPS track."
)

st.warning(
    "Demonstration feature: the supplied sample GPS track is artificial. "
    "Results are preliminary checks, not proof of misconduct or "
    "independently verified measurements."
)


def distance_km(point1, point2):
    lat1, lon1 = point1
    lat2, lon2 = point2

    earth_radius = 6371.0088

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    difference_lat = math.radians(lat2 - lat1)
    difference_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(difference_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(difference_lon / 2) ** 2
    )

    a = max(0.0, min(1.0, a))
    return 2 * earth_radius * math.asin(math.sqrt(a))


def line_distance(points):
    return sum(
        distance_km(points[i], points[i + 1])
        for i in range(len(points) - 1)
    )


def parse_geojson(data):
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
            coordinates = item.get("coordinates", [])
            points = [
                (float(point[1]), float(point[0]))
                for point in coordinates
                if len(point) >= 2
            ]
            if len(points) >= 2:
                lines.append(points)

        elif geometry_type == "MultiLineString":
            for coordinates in item.get("coordinates", []):
                points = [
                    (float(point[1]), float(point[0]))
                    for point in coordinates
                    if len(point) >= 2
                ]
                if len(points) >= 2:
                    lines.append(points)

    visit(obj)

    if not lines:
        raise ValueError(
            "No usable LineString or MultiLineString was found."
        )

    return lines


def parse_gpx(data):
    root = ET.fromstring(data)
    lines = []

    def tag_name(element):
        return element.tag.rsplit("}", 1)[-1]

    for segment in root.iter():
        if tag_name(segment) == "trkseg":
            points = []
            for point in segment.iter():
                if tag_name(point) == "trkpt":
                    points.append(
                        (float(point.attrib["lat"]),
                         float(point.attrib["lon"]))
                    )
            if len(points) >= 2:
                lines.append(points)

    if not lines:
        for route in root.iter():
            if tag_name(route) == "rte":
                points = []
                for point in route.iter():
                    if tag_name(point) == "rtept":
                        points.append(
                            (float(point.attrib["lat"]),
                             float(point.attrib["lon"]))
                        )
                if len(points) >= 2:
                    lines.append(points)

    if not lines:
        points = [
            (float(point.attrib["lat"]), float(point.attrib["lon"]))
            for point in root.iter()
            if tag_name(point) == "trkpt"
        ]
        if len(points) >= 2:
            lines.append(points)

    if not lines:
        raise ValueError("No usable GPS track points were found.")

    return lines


project_root = Path(__file__).resolve().parents[1]
demo_path = project_root / "data" / "sample_road_track.geojson"

uploaded_file = st.file_uploader(
    "Upload one GPS track (.geojson, .json or .gpx)",
    type=["geojson", "json", "gpx"]
)

file_bytes = None
file_name = None
is_demo = False

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
elif demo_path.exists():
    file_bytes = demo_path.read_bytes()
    file_name = demo_path.name
    is_demo = True

if file_bytes is None:
    st.info(
        "Upload a GPS track to begin. Your sample file was not found "
        "in the project's data folder."
    )
    st.stop()

st.write(f"**Track loaded:** {file_name}")

if is_demo:
    st.caption(
        "The displayed track is synthetic sample data from your data folder."
    )

try:
    if file_name.lower().endswith(".gpx"):
        lines = parse_gpx(file_bytes)
    else:
        lines = parse_geojson(file_bytes)

    measured_km = sum(line_distance(line) for line in lines)

    if measured_km <= 0:
        raise ValueError("The measured track distance is zero.")

except Exception as error:
    st.error(f"Could not read this GPS file: {error}")
    st.stop()

st.subheader("Road Length Comparison")

approved_km = st.number_input(
    "Approved road length (km)",
    min_value=0.001,
    value=0.5,
    step=0.1,
    format="%.3f"
)

tolerance = st.number_input(
    "Difference allowed before review (%)",
    min_value=0.0,
    max_value=100.0,
    value=10.0,
    step=1.0
)

difference_km = measured_km - approved_km
difference_percent = difference_km / approved_km * 100

col1, col2, col3 = st.columns(3)

col1.metric("Approved Length", f"{approved_km:.3f} km")
col2.metric("GPS Track Length", f"{measured_km:.3f} km")
col3.metric("Absolute Difference", f"{abs(difference_km):.3f} km")

st.write(f"**Difference from approved length:** {difference_percent:+.2f}%")

if abs(difference_percent) > tolerance:
    st.error(
        "REVIEW FLAG: The difference exceeds the selected tolerance. "
        "Verify the route, approved measurement and supporting records."
    )
else:
    st.success(
        "No review flag under the selected tolerance. "
        "This does not prove that the road work is complete or correct."
    )

st.caption(
    "Distance is calculated from the straight-line distance between "
    "consecutive GPS coordinates. Accuracy depends on track quality, "
    "sampling and route coverage. This tool does not independently verify "
    "the approved length or the identity of the road."
)
