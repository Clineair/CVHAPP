from PIL import Image
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime

# ────────────────────────────────────────────────
# Page Config & CVH Logo
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

# CVH Logo
LOGO_URL = "flaglogo.png"
try:
    st.image(LOGO_URL, width=300)
    st.logo(LOGO_URL, size="medium")
except Exception:
    st.markdown("### CVH Employee Tool ⌯✈︎")

# Button Colors
st.markdown("""
<style>
    .stButton button[data-baseweb="button"][kind="primary"] { background-color: #007BFF !important; color: white !important; } /* Blue - Pilot */
    .stButton button[data-baseweb="button"][kind="secondary"] { background-color: #FFC107 !important; color: black !important; } /* Yellow - Driver */
    .stButton button[data-baseweb="button"][kind="tertiary"] { background-color: #DC3545 !important; color: white !important; } /* Red - Emergency */
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "Pilot"
if 'selected_heli' not in st.session_state:
    st.session_state.selected_heli = None
if 'last_selected' not in st.session_state:
    st.session_state.last_selected = None
if 'last_max_water_gal' not in st.session_state:
    st.session_state.last_max_water_gal = 0
if 'last_current_weight' not in st.session_state:
    st.session_state.last_current_weight = 0
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False

# ────────────────────────────────────────────────
# Mode Buttons
# ────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🛩️ Pilot", use_container_width=True, type="primary"):
        st.session_state.current_mode = "Pilot"
        st.session_state.selected_heli = None
with col2:
    if st.button("🚚 Driver", use_container_width=True, type="secondary"):
        st.session_state.current_mode = "Driver"
with col3:
    if st.button("🚨 Emergency", use_container_width=True, type="tertiary"):
        st.session_state.current_mode = "Emergency"

st.markdown("---")

# ────────────────────────────────────────────────
# Aircraft Database (Helicopters only)
# ────────────────────────────────────────────────
AIRCRAFT_DATA = {
    "Robinson R44 Raven II": {
        "name": "Robinson R44 Raven II",
        "base_climb_rate_fpm": 1200,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1500,
        "base_fuel_capacity_gal": 30,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 83,
        "hopper_weight_per_gal": 8.34,
        "max_takeoff_weight_lbs": 2500,
        "max_landing_weight_lbs": 2500,
        "glide_ratio": 4.0,
        "hover_ceiling_ige_max_gw": 11000,
        "hover_ceiling_oge_max_gw": 8500
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

# ────────────────────────────────────────────────
# Performance Helpers
# ────────────────────────────────────────────────
def calculate_density_altitude(pressure_alt_ft, oat_c):
    isa_temp_c = 15 - (2 * pressure_alt_ft / 1000)
    return pressure_alt_ft + (120 * (oat_c - isa_temp_c))

def compute_climb_rate(alt, oat_c, weight_lbs, aircraft):
    base = AIRCRAFT_DATA[aircraft]["base_climb_rate_fpm"]
    return base * (1 - alt / 10000) * (1 - (weight_lbs - 2000) / 1000)

def compute_hover_ceiling(da_ft, weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    ige = data["hover_ceiling_ige_max_gw"] - (da_ft / 1000 * 500) - ((weight_lbs - 2000) / 100 * 100)
    oge = data["hover_ceiling_oge_max_gw"] - (da_ft / 1000 * 800) - ((weight_lbs - 2000) / 100 * 150)
    return max(0, ige), max(0, oge)

# ────────────────────────────────────────────────
# Pilot Mode
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.title("🛩️ Pilot Performance Calculator")
    selected_aircraft = st.selectbox("Select Aircraft", list(AIRCRAFT_DATA.keys()))
    aircraft_data = AIRCRAFT_DATA[selected_aircraft]

    pressure_alt = st.number_input("Pressure Altitude (ft)", value=0, step=100)
    oat_c = st.number_input("Outside Air Temperature (°C)", value=15, step=1)
    pilot_weight = st.number_input("Pilot Weight (lbs)", value=200, step=10)
    fuel_gal = st.number_input("Fuel (gal)", value=30, step=5)
    hopper_gal = st.number_input("Hopper / Spray (gal)", value=83, step=5)

    da_ft = calculate_density_altitude(pressure_alt, oat_c)
    st.metric("Density Altitude", f"{da_ft:.0f} ft")

    fuel_weight = fuel_gal * aircraft_data["fuel_weight_per_gal"]
    hopper_weight = hopper_gal * aircraft_data["hopper_weight_per_gal"]
    total_weight = aircraft_data["base_empty_weight_lbs"] + pilot_weight + fuel_weight + hopper_weight
    st.metric("Total Weight", f"{total_weight:.0f} lbs")

    st.subheader("Performance Results")
    climb_rate = compute_climb_rate(pressure_alt, oat_c, total_weight, selected_aircraft)
    ige, oge = compute_hover_ceiling(da_ft, total_weight, selected_aircraft)
    st.metric("Climb Rate", f"{climb_rate:.0f} fpm")
    st.metric("IGE Hover Ceiling", f"{ige:.0f} ft")
    st.metric("OGE Hover Ceiling", f"{oge:.0f} ft")

    if st.button("Flight Risk Assessment Tool (FRAT)", type="secondary"):
        st.session_state.show_risk = not st.session_state.get("show_risk", False)
    if st.session_state.get("show_risk", False):
        st.subheader("Flight Risk Assessment Tool (FRAT)")
        risk_score = 0
        risk_score += 10 - st.slider("Mission Pressure", 0, 10, 5)
        risk_score += 10 - st.slider("Fatigue Level", 0, 10, 5)
        risk_score += 10 - st.slider("Weather Conditions", 0, 10, 5)
        risk_score += 10 - st.slider("Aircraft Status", 0, 10, 5)
        risk_score += 10 - st.slider("Personal Factors", 0, 10, 5)
        st.metric("Total Risk Score", f"{risk_score}/50")
        if risk_score > 30:
            st.error("HIGH RISK — Consider mitigation or cancel flight")
        else:
            st.success("Risk Acceptable")

# ────────────────────────────────────────────────
# Driver Mode (All 5 trucks + Heli2 axle loads that ALWAYS sum exactly to total weight)
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Driver":
    st.title("🚚 Driver Pre-Trip & Water Load Tool")
    
    truck_options = ["Heli2", "Heli3", "Heli4", "Seed1", "C8000"]
    selected = st.selectbox("Select Truck", truck_options, index=0)
    st.session_state.selected_heli = selected

    if st.session_state.get("last_selected") != selected:
        st.session_state.last_max_water_gal = 0
        st.session_state.last_current_weight = 0
        st.session_state.last_selected = selected

    st.markdown("---")
    st.subheader("💧 Compute Water Load")

    DEFAULTS = {
        "Heli2": {"empty": 31120, "gvw": 54000, "truck_fuel_max": 603, "heli_fuel_max": 2948},
        "Heli3": {"empty": 25335, "gvw": 48000, "truck_fuel_max": 1380, "heli_fuel_max": 2948},
        "Heli4": {"empty": 31120, "gvw": 54000, "truck_fuel_max": 420, "heli_fuel_max": 938},
        "Seed1": {"empty": 23400, "gvw": 32000, "truck_fuel_max": 570, "heli_fuel_max": 4020},
        "C8000": {"empty": 24200, "gvw": 32000, "truck_fuel_max": 600, "heli_fuel_max": 6900}
    }

    d = DEFAULTS.get(selected, DEFAULTS["Heli2"])

    empty_weight = st.number_input("Empty Weight (lbs)", value=d["empty"], step=10)
    gvw = st.number_input("GVW (lbs)", value=d["gvw"], step=10)
    product_weight = st.number_input("Product Weight (lbs)", value=0, step=10)
    heli_fuel_pct = st.slider("Heli Fuel Tank % Full", 0, 100, 0)
    truck_fuel_pct = st.slider("Truck Fuel % Full", 0, 100, 0)
    rear_weight = st.number_input("Rear Weight (lbs)", value=0, step=10) if selected == "Heli2" else 0

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

    # ── HELI2 ONLY: Axle loads that ALWAYS sum exactly to total weight ──
    if selected == "Heli2":
        st.subheader("Axle Load Status (Heli2)")
        tag_down = st.checkbox("Tag Axle Down", value=False)
        
        if tag_down:
            base_front = 9240
            base_drive1 = 9230
            base_drive2 = 9230
            base_tag = 4700
        else:
            base_front = 7960
            base_drive1 = 11580
            base_drive2 = 11580
            base_tag = 0

        # Fuel deltas (Heli fuel at 334" unloads front, loads drives)
        truck_front_delta = truck_fuel_weight * 0.65
        truck_drive_delta = truck_fuel_weight * 0.35
        heli_front_delta = heli_fuel_weight * (-0.20)
        heli_drive_delta = heli_fuel_weight * 0.80

        # Added weight from water/product/rear
        added_water = st.session_state.get("last_max_water_gal", 0) * 8.34 if st.session_state.get("last_max_water_gal", 0) > 0 else 0
        extra_weight = added_water + product_weight + rear_weight
        extra_front_delta = extra_weight * 0.22
        extra_drive_delta = extra_weight * 0.78

        # Raw loaded axles
        front_loaded = base_front + truck_front_delta + heli_front_delta + extra_front_delta
        drive1_loaded = base_drive1 + (truck_drive_delta * 0.5) + (heli_drive_delta * 0.5) + (extra_drive_delta * 0.5)
        drive2_loaded = base_drive2 + (truck_drive_delta * 0.5) + (heli_drive_delta * 0.5) + (extra_drive_delta * 0.5)
        tag_loaded = base_tag + (extra_weight * 0.2 if tag_down else 0)

        # NORMALIZE so they always sum exactly to total weight
        total_axle_sum = front_loaded + drive1_loaded + drive2_loaded + tag_loaded
        total_weight = current_weight + added_water
        if total_axle_sum > 0:
            scale = total_weight / total_axle_sum
            front_loaded *= scale
            drive1_loaded *= scale
            drive2_loaded *= scale
            tag_loaded *= scale

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Front Axle", f"{front_loaded:.0f} lbs", delta="OK" if front_loaded <= 12000 else "OVER")
        col_b.metric("Drive 1", f"{drive1_loaded:.0f} lbs", delta="OK" if drive1_loaded <= 20000 else "OVER")
        col_c.metric("Drive 2", f"{drive2_loaded:.0f} lbs", delta="OK" if drive2_loaded <= 20000 else "OVER")
        col_d.metric("Tag Axle", f"{tag_loaded:.0f} lbs", delta="OK" if tag_loaded <= 6000 else "OVER")

        if st.session_state.get("last_max_water_gal", 0) > 0 and current_weight + (st.session_state.last_max_water_gal * 8.34) > 48000 and product_weight > 0:
            st.markdown("""<div style="animation: flash 1s infinite; background:#ff4444; color:white; padding:15px; text-align:center; font-size:18px; font-weight:bold; border-radius:8px;">⚠️ Put Drop Axle Down for weight exceeding 48,000 lbs.</div><style>@keyframes flash {0% {opacity:1;} 50% {opacity:0.3;} 100% {opacity:1;}}</style>""", unsafe_allow_html=True)

    # Pre-Trip Inspection Checklist
    st.markdown("---")
    st.subheader("Pre-Trip Inspection Checklist")
    # ← Paste your full inspection checklist here

# ────────────────────────────────────────────────
# Emergency Mode
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Emergency":
    st.title("🚨 Emergency Response Checklist")
    # ← Paste your full emergency checklist here


st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
