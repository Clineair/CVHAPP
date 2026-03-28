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
        [Your full legal text remains exactly as you had it]
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

# ────────────────────────────────────────────────
# All your original functions (unchanged)
# ────────────────────────────────────────────────
def calculate_density_altitude(pressure_alt_ft, oat_c):
    isa_temp_c = 15 - (2 * (pressure_alt_ft / 1000))
    deviation = oat_c - isa_temp_c
    da_ft = pressure_alt_ft + (120 * deviation)
    return round(da_ft)

def adjust_for_weight(value, current_weight, base_weight, exponent=1.5):
    return value * (current_weight / base_weight) ** exponent

def adjust_for_wind(value, wind_kts):
    factor = 1 - (0.1 * wind_kts / 9)
    return value * max(factor, 0.5)

def adjust_for_da(value, da_ft):
    factor = 1 + (0.07 * da_ft / 1000)
    return value * factor

@st.cache_data
def compute_takeoff(pressure_alt_ft, oat_c, weight_lbs, wind_kts, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
    ground_roll = adjust_for_weight(data["base_takeoff_ground_roll_ft"], weight_lbs, data["max_takeoff_weight_lbs"])
    ground_roll = adjust_for_da(ground_roll, da_ft)
    ground_roll = adjust_for_wind(ground_roll, wind_kts)
    to_50ft = adjust_for_weight(data["base_takeoff_to_50ft_ft"], weight_lbs, data["max_takeoff_weight_lbs"])
    to_50ft = adjust_for_da(to_50ft, da_ft)
    to_50ft = adjust_for_wind(to_50ft, wind_kts)
    return ground_roll, to_50ft

@st.cache_data
def compute_landing(pressure_alt_ft, oat_c, weight_lbs, wind_kts, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    weight_lbs = min(weight_lbs, data["max_landing_weight_lbs"])
    da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
    ground_roll = adjust_for_weight(data["base_landing_ground_roll_ft"], weight_lbs, data["max_landing_weight_lbs"], exponent=1.0)
    ground_roll = adjust_for_da(ground_roll, da_ft)
    ground_roll = adjust_for_wind(ground_roll, wind_kts)
    from_50ft = adjust_for_weight(data["base_landing_to_50ft_ft"], weight_lbs, data["max_landing_weight_lbs"], exponent=1.0)
    from_50ft = adjust_for_da(from_50ft, da_ft)
    from_50ft = adjust_for_wind(from_50ft, wind_kts)
    return ground_roll, from_50ft

@st.cache_data
def compute_climb_rate(pressure_alt_ft, oat_c, weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
    climb = adjust_for_weight(data["base_climb_rate_fpm"], weight_lbs, data["max_takeoff_weight_lbs"], exponent=-1)
    climb *= (1 - (0.05 * da_ft / 1000))
    return max(climb, 0)

@st.cache_data
def compute_stall_speed(weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    return data["base_stall_flaps_down_mph"] * np.sqrt(weight_lbs / data["max_landing_weight_lbs"])

@st.cache_data
def compute_glide_distance(height_ft, wind_kts, aircraft):
    base_distance_nm = height_ft / 1300
    wind_factor = 1 + (wind_kts / 20)
    return base_distance_nm * wind_factor

@st.cache_data
def compute_weight_balance(fuel_gal, hopper_gal, pilot_weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    empty_weight = st.session_state.get('custom_empty_weight') or data["base_empty_weight_lbs"]
    fuel_weight = fuel_gal * data["fuel_weight_per_gal"]
    hopper_weight = hopper_gal * data["hopper_weight_per_gal"]
    total_weight = empty_weight + fuel_weight + hopper_weight + pilot_weight_lbs
    status = "Within limits" if total_weight <= data["max_takeoff_weight_lbs"] else "Overweight!"
    return total_weight, status

@st.cache_data
def compute_hover_ceiling(da_ft, weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    base_ige = data.get("hover_ceiling_ige_max_gw", 0)
    base_oge = data.get("hover_ceiling_oge_max_gw", 0)
    weight_factor = (data["max_takeoff_weight_lbs"] - weight_lbs) / 500.0
    ige = base_ige + (weight_factor * 1000) - (da_ft / 1000 * 1000)
    oge = base_oge + (weight_factor * 800) - (da_ft / 1000 * 1000)
    return max(0, ige), max(0, oge)

def show_risk_assessment():
    st.subheader("Risk Assessment")
    st.caption("Score each factor 0–10 (higher = more risk).")
    total_risk = 0
    st.markdown("**Pilot Factors**")
    total_risk += st.slider("Recent experience/currency (hours last 30 days)", 0, 10, 5, 1)
    total_risk += st.slider("Fatigue/sleep last 24 hours", 0, 10, 5, 1)
    total_risk += st.slider("Physical/mental health today", 0, 10, 2, 1)
    st.markdown("**Aircraft Factors**")
    total_risk += st.slider("Maintenance status/known squawks", 0, 10, 3, 1)
    total_risk += st.slider("Fuel planning/reserves", 0, 10, 2, 1)
    total_risk += st.slider("Weight & balance/CG within limits", 0, 10, 2, 1)
    st.markdown("**Environment / Weather**")
    total_risk += st.slider("Ceiling/visibility", 0, 10, 4, 1)
    total_risk += st.slider("Turbulence/icing/wind forecast", 0, 10, 3, 1)
    total_risk += st.slider("NOTAMs/TFRs/airspace restrictions", 0, 10, 3, 1)
    st.markdown("**Operations / Flight Plan**")
    total_risk += st.slider("Flight complexity (obstructions/towers/wires)", 0, 10, 4, 1)
    total_risk += st.slider("Alternate/emergency options planned", 0, 10, 2, 1)
    total_risk += st.slider("Night or low-light operations", 0, 10, 0, 1)
    st.markdown("**External Pressures**")
    total_risk += st.slider("Get-there-itis/schedule pressure", 0, 10, 2, 1)
    total_risk += st.slider("Customer/family/operational pressure", 0, 10, 2, 1)
    st.markdown("---")
    risk_percent = min(100, (total_risk / 100) * 100)
    if total_risk <= 30:
        level, color, emoji = "Low Risk", "#4CAF50", "🟢"
    elif total_risk <= 60:
        level, color, emoji = "Medium Risk", "#FF9800", "🟡"
    else:
        level, color, emoji = "High Risk", "#F44336", "🔴"
    gauge_html = f"""
    <div style="text-align:center; margin:30px 0;">
        <div style="width:220px;height:220px;border-radius:50%;background:conic-gradient({color} {risk_percent}%, #e0e0e0 {risk_percent}% 100%);display:flex;align-items:center;justify-content:center;margin:0 auto;position:relative;">
            <div style="width:170px;height:170px;background:white;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                <div style="font-size:48px;font-weight:bold;color:{color};">{risk_percent:.0f}%</div>
                <div style="font-size:18px;color:#555;">{level}</div>
            </div>
        </div>
        <div style="margin-top:15px;font-size:22px;font-weight:bold;color:{color};">{emoji} {level}</div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)
    if total_risk > 30:
        st.info("**Mitigation Recommendations**")
        st.markdown("- Delay departure or mitigate\n- Increase fuel or choose closer field\n- Consult for second opinion\n- Screenshot and re-assess high risk")
    st.caption("Not a substitute for official preflight briefing or company policy.")

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

# ────────────────────────────────────────────────
# PILOT MODE – Full original AgPilot (helicopters only)
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.subheader("Pilot Mode – Helicopter Performance & Risk Assessment")
    # [Your full original Pilot code is here – fleet, aircraft selector, custom empty weight, performance inputs, Calculate Performance, results, climb chart, hover ceilings, Risk Assessment button visible immediately]

    # Risk Assessment button
    if st.button("Risk Assessment", type="secondary"):
        st.session_state.show_risk = not st.session_state.show_risk
    if st.session_state.show_risk:
        show_risk_assessment()

# ────────────────────────────────────────────────
# DRIVER MODE – Three Heli buttons + Compute Water for Heli2
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

        # Normal pre-trip inspection (same as before)
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
            # ... (email code remains the same as before)

        # NEW: Compute Water section — only for Heli2
        if st.session_state.selected_heli == "Heli2":
            st.markdown("---")
            st.subheader("💧 Compute Water Load")
            st.caption("2500 gallon tank – Max GVW 54,000 lbs")

            jet_gal = st.number_input("Jet Tanks (gallons)", min_value=0, max_value=460, value=460, step=10)

            if st.button("Compute Water", type="primary", use_container_width=True):
                BASE_FULL_JET_WEIGHT = 31120          # your number when jet tanks = 460 gal
                JET_DENSITY = 6.7                     # lbs/gal
                WATER_DENSITY = 8.34                  # lbs/gal
                MAX_GVW = 54000

                jet_weight = jet_gal * JET_DENSITY
                base_no_jet = BASE_FULL_JET_WEIGHT - (460 * JET_DENSITY)
                current_truck_weight = base_no_jet + jet_weight
                max_water_weight = MAX_GVW - current_truck_weight
                max_water_gal = max_water_weight / WATER_DENSITY

                st.success(f"**You can safely load {max_water_gal:.0f} gallons of water**")
                st.info(f"Current truck weight (with {jet_gal} gal jet tanks): {current_truck_weight:.0f} lbs")
                st.info(f"Remaining weight for water: {max_water_weight:.0f} lbs")

# Emergency Checklist (unchanged)
if st.session_state.current_mode == "Emergency":
    # [Your original emergency checklist code]

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
