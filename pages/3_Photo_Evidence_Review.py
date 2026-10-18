
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Construction Photo Evidence Review",
    page_icon="📷",
    layout="wide",
)

st.title("Construction Photo Evidence Review")
st.write(
    "Upload a construction-site photo and record observations "
    "for human review."
)

st.warning(
    "A photo alone does not verify the project, location, date, "
    "construction quality, or wrongdoing. Reviewer-entered details "
    "are not independently verified."
)

st.subheader("1. Project details")

project_code = st.text_input(
    "Project code",
    placeholder="Example: 618511",
)

project_name = st.text_input(
    "Project name",
    placeholder="Enter the project name",
)

location = st.text_input(
    "Reported site location",
    placeholder="Enter the location",
)

inspection_date = st.date_input(
    "Inspection date recorded by reviewer",
    value=date.today(),
)

st.subheader("2. Upload a photograph")

photo = st.file_uploader(
    "Choose a JPG or PNG image",
    type=["jpg", "jpeg", "png"],
)

photo_bytes = None

if photo is not None:
    photo_bytes = photo.getvalue()
    st.image(
        photo_bytes,
        caption="Uploaded photo: " + Path(photo.name).name,
        width="stretch",
    )

st.subheader("3. Inspection observations")

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

notes = st.text_area(
    "Inspection notes",
    placeholder=(
        "Describe what is visible and what needs further checking."
    ),
    height=120,
)

st.caption(
    "Enter only details you can support. Do not claim that a photo "
    "is from a particular project unless its source is established."
)

if photo_bytes is not None:
    record = {
        "project_code": project_code,
        "project_name": project_name,
        "reported_site_location": location,
        "inspection_date_recorded_by_reviewer": inspection_date.isoformat(),
        "evidence_category": category,
        "reviewer_assessment": assessment,
        "inspection_notes": notes,
        "photo_filename": Path(photo.name).name,
        "photo_size_bytes": len(photo_bytes),
        "verification_status": "Not independently verified",
        "limitations": (
            "Photo authenticity, capture date, GPS location, project "
            "identity and construction completion have not been "
            "independently verified."
        ),
    }

    report_bytes = json.dumps(
        record,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("inspection_record.json", report_bytes)
        archive.writestr(
            "photos/" + Path(photo.name).name,
            photo_bytes,
        )

    st.subheader("4. Inspection record")
    st.json(record)

    st.download_button(
        "Download inspection record and photo (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="project_reality_inspection_record.zip",
        mime="application/zip",
    )
else:
    st.info(
        "Upload an image to preview it and prepare an inspection record."
    )

st.divider()
st.caption(
    "Project Reality · Academic prototype · Human verification required."
)
