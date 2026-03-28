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
if 'inspections' not in st.session_state:
    st.session_state.inspections = []

# ────────────────────────────────────────────────
# Aircraft Database — Helicopters only
# ────────────────────────────────────────────────
AIRCRAFT_DATA = {
    "Robinson R44 Raven II": { ... same as before ... },
    "Enstrom 480": { ... same as before ... }
}

# Truck-specific defaults (each truck now has its own Empty Weight and GVW)
TRUCK_FUEL_MAX_LBS = {
    "Heli2": 480, "Heli3": 420, "Heli4": 420, "Seed1": 420, "C8000": 420
}
HELI_FUEL_MAX_LBS = {
    "Heli2": 3082, "Heli3": 3082, "Heli4": 938, "Seed1": 0, "C8000": 0
}

# NEW: Truck-specific Empty Weight and GVW
DEFAULT_EMPTY_WEIGHT = {
    "Heli2": 31120,
    "Heli3": 31120,
    "Heli4": 31120,
    "Seed1": 31120,   # ← change to your exact value for Seed1
    "C8000": 31120    # ← change to your exact value for C8000
}
DEFAULT_GVW = {
    "Heli2": 54000,
    "Heli3": 54000,
    "Heli4": 54000,
    "Seed1": 54000,   # ← change to your exact value for Seed1
    "C8000": 54000    # ← change to your exact value for C8000
}

# (All your original performance functions remain exactly the same – omitted here for brevity but fully present in the real file)

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
        st.session_state.selected_heli = None
with col3:
    if st.button("🚨 Emergency Checklist", type="primary", use_container_width=True):
        st.session_state.current_mode = "Emergency"

# PILOT MODE – full original helicopter performance (unchanged)
if st.session_state.current_mode == "Pilot":
    # (All the original Pilot code you already had – fleet, selector, inputs, Calculate, chart, risk gauge, etc.)
    # ... [full Pilot code from previous version] ...

# DRIVER MODE – truck-specific Empty Weight & GVW + live Current Weight
if st.session_state.current_mode == "Driver":
    st.subheader("Select Your Truck")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Heli2", type="secondary", use_container_width=True): st.session_state.selected_heli = "Heli2"
        if st.button("Heli4", type="secondary", use_container_width=True): st.session_state.selected_heli = "Heli4"
        if st.button("Seed1", type="secondary", use_container_width=True): st.session_state.selected_heli = "Seed1"
    with col2:
        if st.button("Heli3", type="secondary", use_container_width=True): st.session_state.selected_heli = "Heli3"
        if st.button("C8000", type="secondary", use_container_width=True): st.session_state.selected_heli = "C8000"

    if st.session_state.get("selected_heli"):
        selected = st.session_state.selected_heli
        st.subheader(f"Pre-Trip Inspection for {selected}")

        # === COMPUTE WATER SECTION (BEFORE inspection) ===
        st.markdown("---")
        st.subheader("💧 Compute Water Load")
        st.caption("Enter values – Current Weight updates live")

        empty_weight = st.number_input("Empty Weight (lbs)", 
                                       value=DEFAULT_EMPTY_WEIGHT.get(selected, 31120), step=10)
        gvw = st.number_input("GVW (lbs)", 
                              value=DEFAULT_GVW.get(selected, 54000), step=10)
        product_weight = st.number_input("Product Weight (lbs)", value=0, step=10)
        heli_fuel_pct = st.slider("Heli Fuel Tank % Full", 0, 100, 100)
        truck_fuel_pct = st.slider("Truck Fuel % Full", 0, 100, 100)

        # Live calculations
        truck_fuel_max = TRUCK_FUEL_MAX_LBS.get(selected, 420)
        heli_fuel_max = HELI_FUEL_MAX_LBS.get(selected, 420)
        truck_fuel_weight = (truck_fuel_pct / 100.0) * truck_fuel_max
        heli_fuel_weight = (heli_fuel_pct / 100.0) * heli_fuel_max
        current_weight = empty_weight + truck_fuel_weight + heli_fuel_weight + product_weight

        st.metric("**Current Weight**", f"{current_weight:.0f} lbs")

        if st.button("Compute Water", type="primary", use_container_width=True):
            remaining = gvw - current_weight
            max_water_gal = max(0, remaining / 8.34)
            st.success(f"**Maximum water you can load: {max_water_gal:.0f} gallons**")

        # === Inspection checklist (unchanged) ===
        # ... [full inspection code from previous version] ...

# EMERGENCY CHECKLIST (unchanged)
if st.session_state.current_mode == "Emergency":
    # ... [full emergency checklist from previous version] ...

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
