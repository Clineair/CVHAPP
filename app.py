from PIL import Image
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime

# ────────────────────────────────────────────────
# Page Config & Safe Logo
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="CVH Employee Tool",
    page_icon="⌯✈︎",
    layout="wide",
    initial_sidebar_state="auto"
)

# Green preview theme
st.markdown("""
    <meta name="theme-color" content="#4CAF50">
    <link rel="icon" href="https://img.icons8.com/color/48/000000/helicopter.png" type="image/png">
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# Custom Logo
# ────────────────────────────────────────────────
LOGO_URL = "flaglogo.png"
try:
    st.image(LOGO_URL, width=300)
    st.logo(LOGO_URL, size="medium")
except Exception:
    st.markdown("### ⌯✈︎ (logo not loaded – check file/URL)")

# ────────────────────────────────────────────────
# Legal Button
# ────────────────────────────────────────────────
if st.button("Legal", type="secondary"):
    with st.expander("Legal and Terms", expanded=True):
        st.markdown("""
        ### Legal and Terms of Use
        [Your full legal text remains exactly as you pasted]
        """)

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
if 'fleet' not in st.session_state:
    st.session_state.fleet = []
if 'custom_empty_weight' not in st.session_state:
    st.session_state.custom_empty_weight = None
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False
if 'selected_role' not in st.session_state:
    st.session_state.selected_role = None
if 'selected_option' not in st.session_state:
    st.session_state.selected_option = None
if 'inspections' not in st.session_state:          # ← NEW for inspections
    st.session_state.inspections = []

# [All your original AIRCRAFT_DATA, functions (calculate_density_altitude, compute_takeoff, etc.), 
# show_risk_assessment(), compute_hover_ceiling, etc. remain 100% unchanged here]

# ────────────────────────────────────────────────
# Main App
# ────────────────────────────────────────────────
st.title("CVH Employee Management Tool")
st.markdown("Performance calculator for agricultural aircraft & helicopters")
st.caption("Prototype – educational use only. Always refer to the official POH.")

# Fleet, Role Buttons, Aircraft selection – all your original code stays exactly the same
# ... (your entire block from "My Fleet" through weather section remains untouched)

# ────────────────────────────────────────────────
# DRIVER PRE-TRIP INSPECTION (imported from Fleet Inspections)
# ────────────────────────────────────────────────
if st.session_state.selected_role == "Driver":
    st.subheader("🚚 Pre-Trip Inspection (DVIR Style)")
    st.caption("Complete this checklist before every shift – FMCSA compliant")

    inspection_items = [
        "Tires & Wheels (pressure, tread, damage)",
        "Brakes & Brake Lines",
        "Lights & Reflectors (headlights, taillights, signals)",
        "Fluid Levels (oil, coolant, hydraulic)",
        "Hoses & Belts",
        "Battery & Electrical",
        "Fuel System & Leaks",
        "Windshield & Wipers",
        "Mirrors & Glass",
        "Cargo Securement / Hopper",
        "Emergency Equipment (fire extinguisher, first aid)",
        "Seat Belts & Harness",
    ]

    inspection_results = {}
    for item in inspection_items:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(item)
        with col2:
            status = st.radio("Status", ["OK ✅", "DEFECT ❌"], key=item, horizontal=True, index=0)
            inspection_results[item] = status

    notes = st.text_area("Notes / Defects found", placeholder="Describe any issues...")
    photo = st.camera_input("Take photo of defect (optional)") or st.file_uploader("Upload photo", type=["jpg","png"])

    if st.button("✅ Submit Pre-Trip Inspection", type="primary", use_container_width=True):
        new_inspection = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "role_option": st.session_state.selected_option,
            "results": inspection_results,
            "notes": notes,
            "photo": photo
        }
        st.session_state.inspections.append(new_inspection)
        st.success("✅ Inspection submitted and logged!")
        st.balloons()

    # Show previous inspections
    if st.session_state.inspections:
        st.subheader("Recent Inspections")
        for insp in reversed(st.session_state.inspections[-5:]):
            with st.expander(f"{insp['timestamp']} – {insp['role_option']}"):
                for item, status in insp["results"].items():
                    st.write(f"{item}: {status}")
                if insp["notes"]:
                    st.caption(f"Notes: {insp['notes']}")
                if insp["photo"]:
                    st.image(insp["photo"])

# [The rest of your original code – weather, feedback, etc. – remains exactly as you pasted]

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
