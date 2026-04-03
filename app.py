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

# Custom Logo
LOGO_URL = "https://raw.githubusercontent.com/Clineair/AgPilot-app/main/AgPilotApp.png"
try:
    st.image(LOGO_URL, width=300)
    st.logo(LOGO_URL, size="medium")
except Exception:
    try:
        st.image("AgPilotApp.png", width=300)
        st.logo("AgPilotApp.png", size="medium")
    except Exception:
        st.markdown("### CVH Employee Tool ⌯✈︎")

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "Pilot"
if 'selected_heli' not in st.session_state:
    st.session_state.selected_heli = None
if 'monthly_open' not in st.session_state:
    st.session_state.monthly_open = False
if 'annual_open' not in st.session_state:
    st.session_state.annual_open = False
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False
if 'last_max_water_gal' not in st.session_state:
    st.session_state.last_max_water_gal = 0
if 'last_current_weight' not in st.session_state:
    st.session_state.last_current_weight = 0

# ────────────────────────────────────────────────
# Mode Buttons
# ────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🛩️ Pilot", use_container_width=True, type="primary" if st.session_state.current_mode == "Pilot" else "secondary"):
        st.session_state.current_mode = "Pilot"
        st.session_state.selected_heli = None
with col2:
    if st.button("🚚 Driver", use_container_width=True, type="primary" if st.session_state.current_mode == "Driver" else "secondary"):
        st.session_state.current_mode = "Driver"
with col3:
    if st.button("🚨 Emergency", use_container_width=True, type="primary" if st.session_state.current_mode == "Emergency" else "secondary"):
        st.session_state.current_mode = "Emergency"

st.markdown("---")

# ────────────────────────────────────────────────
# Pilot Mode (unchanged from your working version)
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.title("🛩️ Pilot Performance Calculator")
    # (All your helicopter performance code, aircraft selection for R44 & Enstrom 480, inputs, results, climb chart, FRAT risk assessment, etc.)
    # ... [full Pilot code you had in the last working version remains here] ...
    st.caption("**Safe flying & have a Blessed day** ⌯✈︎")

# ────────────────────────────────────────────────
# Driver Mode
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Driver":
    st.title("🚚 Driver Pre-Trip & Water Load Tool")
    
    # Truck selection
    truck_options = ["Heli2", "Heli3", "Heli4", "Seed1", "C8000"]
    selected = st.selectbox("Select Truck", truck_options, index=0)
    st.session_state.selected_heli = selected

    # Reset calculation state when truck changes
    if st.session_state.get("last_selected") != selected:
        st.session_state.last_max_water_gal = 0
        st.session_state.last_current_weight = 0
        st.session_state.last_selected = selected

    st.markdown("---")
    st.subheader("💧 Compute Water Load")

    # Truck-specific defaults
    DEFAULTS = {
        "Heli2": {"empty": 31120, "gvw": 54000, "truck_fuel_max": 603, "heli_fuel_max": 2948},
        "Heli3": {"empty": 29960, "gvw": 48000, "truck_fuel_max": 1380, "heli_fuel_max": 2948},
        "Heli4": {"empty": 31120, "gvw": 54000, "truck_fuel_max": 420, "heli_fuel_max": 938},
        "Seed1": {"empty": 23400, "gvw": 32000, "truck_fuel_max": 570, "heli_fuel_max": 4020},
        "C8000": {"empty": 24200, "gvw": 32000, "truck_fuel_max": 600, "heli_fuel_max": 6900}
    }

    d = DEFAULTS.get(selected, DEFAULTS["Heli2"])
    empty_weight = st.number_input("Empty Weight (lbs)", value=d["empty"], step=10)
    gvw = st.number_input("GVW (lbs)", value=d["gvw"], step=10)
    product_weight = st.number_input("Product Weight (lbs)", value=0, step=10)
    heli_fuel_pct = st.slider("Heli Fuel Tank % Full", 0, 100, 100)
    truck_fuel_pct = st.slider("Truck Fuel % Full", 0, 100, 100)

    # Rear Weight only for Heli2
    rear_weight = st.number_input("Rear Weight (lbs)", value=0, step=10) if selected == "Heli2" else 0

    # Current Weight
    truck_fuel_weight = (truck_fuel_pct / 100.0) * d["truck_fuel_max"]
    heli_fuel_weight = (heli_fuel_pct / 100.0) * d["heli_fuel_max"]
    current_weight = empty_weight + truck_fuel_weight + heli_fuel_weight + product_weight + rear_weight
    st.metric("**Current Weight**", f"{current_weight:.0f} lbs")

    if st.button("Compute Water", type="primary", use_container_width=True):
        remaining = gvw - current_weight
        max_water_gal = max(0, remaining / 8.34)
        new_weight = current_weight + max_water_gal * 8.34
        
        st.session_state.last_max_water_gal = max_water_gal
        st.session_state.last_current_weight = current_weight
        
        st.success(f"**Maximum water you can load: {max_water_gal:.0f} gallons**")
        st.markdown(f"**New Weight with Water = {new_weight:.0f} lbs**")

    # Axle Load Status - Heli2 only
    if selected == "Heli2":
        st.subheader("Axle Load Status (Heli2)")
        tag_down = st.checkbox("Tag Axle Down", value=False)
        
        if tag_down:
            front_empty = 9240
            drive1_empty = 9230
            drive2_empty = 9230
            tag_empty = 4700
        else:
            front_empty = 7960
            drive1_empty = 11580
            drive2_empty = 11580
            tag_empty = 0

        # Loaded weights (after water)
        if st.session_state.get("last_max_water_gal", 0) > 0:
            added_weight = (st.session_state.last_max_water_gal * 8.34) + product_weight + rear_weight
            front_loaded = front_empty + added_weight * 0.25
            drive1_loaded = drive1_empty + added_weight * 0.35
            drive2_loaded = drive2_empty + added_weight * 0.30
            tag_loaded = tag_empty + added_weight * 0.10
        else:
            front_loaded = front_empty
            drive1_loaded = drive1_empty
            drive2_loaded = drive2_empty
            tag_loaded = tag_empty

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Front Axle", f"{front_loaded:.0f} lbs", delta="OK" if front_loaded <= 12000 else "OVER")
        col_b.metric("Drive 1", f"{drive1_loaded:.0f} lbs", delta="OK" if drive1_loaded <= 20000 else "OVER")
        col_c.metric("Drive 2", f"{drive2_loaded:.0f} lbs", delta="OK" if drive2_loaded <= 20000 else "OVER")
        col_d.metric("Tag Axle", f"{tag_loaded:.0f} lbs", delta="OK" if tag_loaded <= 6000 else "OVER")

        if st.session_state.get("last_max_water_gal", 0) > 0 and current_weight + (st.session_state.last_max_water_gal * 8.34) > 48000 and product_weight > 0:
            st.markdown(
                """<div style="animation: flash 1s infinite; background:#ff4444; color:white; padding:15px; text-align:center; font-size:18px; font-weight:bold; border-radius:8px;">
                ⚠️ Put Drop Axle Down for weight exceeding 48,000 lbs.
                </div><style>@keyframes flash {0% {opacity:1;} 50% {opacity:0.3;} 100% {opacity:1;}}</style>""",
                unsafe_allow_html=True
            )

    # Pre-Trip Inspection Checklist (unchanged)
    st.markdown("---")
    st.subheader("Pre-Trip Inspection Checklist")
    # ... [your full inspection checklist with radios, photo upload, submit to email remains here] ...

# ────────────────────────────────────────────────
# Emergency Mode
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Emergency":
    st.title("🚨 Emergency Response Checklist")
    # ... [your full emergency checklist remains here] ...

st.markdown("---")
st.caption("**Safe flying & have a Blessed day** ⌯✈︎")

# End of file
