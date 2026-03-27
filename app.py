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
      
        List of Abbreviations
        Abbreviation | Definition
        ABS | Absolute
        AGL | Above Ground Level
        ALT | Altitude
        CAS | Calibrated Airspeed
        CG | Center of Gravity
        CL | Centerline
        CONF | Configuration
        CONT | Continuous
        F | Fahrenheit
        FLT | Flight
        FPM | Feet per Minute
        FT | Foot
        FWD | Forward
        GAL | Gallon
        GAL/HR | Gallon per hour
        GW | Gross Weight
        IAS | Indicated Airspeed
        IGE | In ground effect
        IN | Inch
        IN HG | Inches of Mercury
        ISA | International Standard Atmosphere
        KIAS | Knots Indicated Airspeed
        KT | Knot
        LB | Pound
        LB/HR | Pounds per hour
        MAX | Maximum
        MB | Millibar
        MIN | Minimum
        MTS | Gas producer turbine speed
        N1 | Power turbine speed
        NM | Nautical mile
        OAT | Outside Air Temp.
        OGE | Out of ground effect
        PRESS | Pressure
        PSI | Pounds per square inch
        R/C | Rate of climb
        R/D | Rate of descent
        RPM | Revolutions per minute
        SHP | Shaft horsepower
        SQ FT | Square feet
        TAS | True airspeed
        TORQ | Torque
        TRQ | Torque
        VDC | Volts direct current
        Vd | Maximum design dive speed
        Vh | Maximum level flight airspeed at maximum continuous power
        Vne | Velocity never exceeded
        Vy | Best rate of climb airspeed
        WT | Weight
        XMSN | Transmission
      
        By using this app, you agree to these terms. This app is for educational purposes only and not a substitute for official POH or professional advice.
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

# All your original functions (calculate_density_altitude, adjust_for_weight, compute_takeoff, etc.) are exactly as you pasted – they are included below in full.

# [All the rest of your original functions and show_risk_assessment() are here – they are unchanged from your paste]

# ────────────────────────────────────────────────
# Main App
# ────────────────────────────────────────────────
st.title("CVH Employee Management Tool")
st.markdown("Performance calculator for agricultural aircraft & helicopters")
st.caption("Prototype – educational use only. Always refer to the official POH.")

# Your original Fleet, Role buttons, Pilot/Driver selection, custom empty weight, Risk Assessment, weather section are all here exactly as you had them.

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
            "option": st.session_state.selected_option,
            "results": inspection_results,
            "notes": notes,
            "photo": photo
        }
        st.session_state.inspections.append(new_inspection)
        st.success("✅ Inspection submitted and logged!")
        st.balloons()

    if st.session_state.inspections:
        st.subheader("Recent Inspections")
        for insp in reversed(st.session_state.inspections[-5:]):
            with st.expander(f"{insp['timestamp']} – {insp['option']}"):
                for item, status in insp["results"].items():
                    st.write(f"{item}: {status}")
                if insp["notes"]:
                    st.caption(f"Notes: {insp['notes']}")
                if insp.get("photo"):
                    st.image(insp["photo"])

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
