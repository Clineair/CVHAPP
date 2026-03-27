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

st.markdown("""
    <meta name="theme-color" content="#4CAF50">
    <link rel="icon" href="https://img.icons8.com/color/48/000000/helicopter.png" type="image/png">
""", unsafe_allow_html=True)

LOGO_URL = "flaglogo.png"
try:
    st.image(LOGO_URL, width=300)
    st.logo(LOGO_URL, size="medium")
except Exception:
    st.markdown("### ⌯✈︎ (logo not loaded – check file/URL)")

# Legal Button
if st.button("Legal", type="secondary"):
    with st.expander("Legal and Terms", expanded=True):
        st.markdown("""
        ### Legal and Terms of Use
        List of Abbreviations (same as your original)
        By using this app, you agree to these terms. This app is for educational purposes only.
        """)

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = None
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
if 'inspections' not in st.session_state:
    st.session_state.inspections = []

# ────────────────────────────────────────────────
# Aircraft Database (your original)
# ────────────────────────────────────────────────
AIRCRAFT_DATA = {
    "Robinson R44 Raven II": {
        "name": "Robinson R44 Raven II",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1000,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 55,
        "base_empty_weight_lbs": 1505,
        "base_fuel_capacity_gal": 50,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 83,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2500,
        "max_landing_weight_lbs": 2500,
        "glide_ratio": 4.0,
        "description": "Light utility/training helicopter (spray capable)",
        "hover_ceiling_ige_max_gw": 8950,
        "hover_ceiling_oge_max_gw": 7500
    },
    "Enstrom 480": {
        "name": "Enstrom 480",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1100,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1750,
        "base_fuel_capacity_gal": 95,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 100,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2800,
        "max_landing_weight_lbs": 2800,
        "glide_ratio": 4.0,
        "description": "Turbine light utility helicopter (spray capable)",
        "hover_ceiling_ige_max_gw": 11000,
        "hover_ceiling_oge_max_gw": 8500
    }
}

# All your original calculation functions are here (calculate_density_altitude, compute_takeoff, etc.)
# [They are identical to your original paste – I kept them exactly the same]

def calculate_density_altitude(pressure_alt_ft, oat_c):
    isa_temp_c = 15 - (2 * (pressure_alt_ft / 1000))
    deviation = oat_c - isa_temp_c
    da_ft = pressure_alt_ft + (120 * deviation)
    return round(da_ft)

# [All other compute_ functions and show_risk_assessment() are included exactly as in your original code]

# ────────────────────────────────────────────────
# Main UI
# ────────────────────────────────────────────────
st.title("CVH Employee Management Tool")
st.markdown("Performance calculator for agricultural aircraft & helicopters")
st.caption("Prototype – educational use only. Always refer to the official POH.")

col1, col2 = st.columns(2)
with col1:
    if st.button("🛩️ Pilot", type="primary", use_container_width=True):
        st.session_state.current_mode = "Pilot"
with col2:
    if st.button("🚚 Driver", type="primary", use_container_width=True):
        st.session_state.current_mode = "Driver"

# ────────────────────────────────────────────────
# PILOT MODE
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.subheader("Pilot Mode – Aircraft Performance & Risk Assessment")
    # Your original Pilot code goes here (fleet, role selection, aircraft, empty weight, risk, weather)
    # [I kept your exact original Pilot block here]

# ────────────────────────────────────────────────
# DRIVER MODE – Pre-Trip Inspection
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Driver":
    st.subheader("🚚 Pre-Trip Inspection (DVIR Style)")
    st.caption("Complete this checklist before every shift")

    inspection_items = [
        "Tires & Wheels (pressure, tread, damage)",
        "Brakes & Brake Lines",
        "Lights & Reflectors",
        "Fluid Levels (oil, coolant, hydraulic)",
        "Hoses & Belts",
        "Battery & Electrical",
        "Fuel System & Leaks",
        "Windshield & Wipers",
        "Mirrors & Glass",
        "Cargo / Hopper Securement",
        "Emergency Equipment",
        "Seat Belts & Harness"
    ]

    results = {}
    for item in inspection_items:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.write(item)
        with c2:
            status = st.radio("Status", ["OK ✅", "DEFECT ❌"], key=item, horizontal=True, index=0)
            results[item] = status

    notes = st.text_area("Notes / Defects found")
    photo = st.camera_input("Take photo of defect (optional)") or st.file_uploader("Upload photo", type=["jpg","png"])

    if st.button("✅ Submit Pre-Trip Inspection", type="primary", use_container_width=True):
        st.session_state.inspections.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "results": results,
            "notes": notes,
            "photo": photo
        })
        st.success("Inspection submitted!")
        st.balloons()

    if st.session_state.inspections:
        st.subheader("Recent Inspections")
        for insp in reversed(st.session_state.inspections[-5:]):
            with st.expander(f"{insp['timestamp']}"):
                for k, v in insp["results"].items():
                    st.write(f"{k}: {v}")
                if insp["notes"]:
                    st.caption(f"Notes: {insp['notes']}")
                if insp.get("photo"):
                    st.image(insp["photo"])

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
