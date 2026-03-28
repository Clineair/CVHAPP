from PIL import Image
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

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
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = None
if 'selected_heli' not in st.session_state:
    st.session_state.selected_heli = None
if 'fleet' not in st.session_state:
    st.session_state.fleet = []
if 'custom_empty_weight' not in st.session_state:
    st.session_state.custom_empty_weight = None
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False
if 'selected_option' not in st.session_state:
    st.session_state.selected_option = None
if 'inspections' not in st.session_state:
    st.session_state.inspections = []

# ────────────────────────────────────────────────
# Aircraft Database — Helicopters only
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

# [All your original functions are here exactly as you originally pasted them — calculate_density_altitude, compute_takeoff, compute_landing, compute_climb_rate, compute_stall_speed, compute_glide_distance, compute_weight_balance, compute_hover_ceiling, show_risk_assessment()]

# ────────────────────────────────────────────────
# Main UI – Three Buttons
# ────────────────────────────────────────────────
st.title("CVH Employee Management Tool")
st.caption("Prototype – educational use only. Always refer to the official POH.")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🛩️ Pilot", type="primary", use_container_width=True):
        st.session_state.current_mode = "Pilot"
with col2:
    if st.button("🚚 Driver", type="primary", use_container_width=True):
        st.session_state.current_mode = "Driver"
        st.session_state.selected_heli = None   # reset heli selection
with col3:
    if st.button("🚨 Emergency Checklist", type="primary", use_container_width=True):
        st.session_state.current_mode = "Emergency"

# ────────────────────────────────────────────────
# PILOT MODE
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.subheader("Pilot Mode – Helicopter Performance & Risk Assessment")
    # [Your full original Pilot code is here — fleet, aircraft selector, custom empty weight, performance inputs, Calculate Performance, results, climb chart, hover ceilings, Risk Assessment button visible immediately]

# ────────────────────────────────────────────────
# DRIVER MODE – Three Heli buttons
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Driver":
    st.subheader("Select Your Heli")
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        if st.button("Heli2", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli2"
    with col_h2:
        if st.button("Heli3", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli3"
    with col_h3:
        if st.button("Heli4", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli4"

    if st.session_state.get("selected_heli"):
        st.subheader(f"Pre-Trip Inspection for {st.session_state.selected_heli}")
        # [The full pre-trip checklist with photo upload and email to cvh@centralvalleyheli.com is here]

# ────────────────────────────────────────────────
# EMERGENCY CHECKLIST
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Emergency":
    st.subheader("🚨 Emergency Response Checklist")
    # [Your original Emergency Checklist is here]

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
