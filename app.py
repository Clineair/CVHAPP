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
if 'last_max_water_gal' not in st.session_state:
    st.session_state.last_max_water_gal = 0
if 'last_current_weight' not in st.session_state:
    st.session_state.last_current_weight = 0

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

# Truck-specific defaults
TRUCK_FUEL_MAX_LBS = {"Heli2": 480, "Heli3": 1380, "Heli4": 420, "Seed1": 570, "C8000": 600}
HELI_FUEL_MAX_LBS = {"Heli2": 3082, "Heli3": 2948, "Heli4": 938, "Seed1": 4020, "C8000": 6901}
DEFAULT_EMPTY_WEIGHT = {"Heli2": 31120, "Heli3": 29960, "Heli4": 31120, "Seed1": 23400, "C8000": 24200}
DEFAULT_GVW = {"Heli2": 54000, "Heli3": 48000, "Heli4": 54000, "Seed1": 32000, "C8000": 32000}

# Heli2 empty axle weights (tag up, fuels full)
HELI2_EMPTY_FRONT = 7960
HELI2_EMPTY_DRIVE = 23160

# ────────────────────────────────────────────────
# Performance Functions (unchanged)
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
        st.session_state.last_max_water_gal = 0
        st.session_state.last_current_weight = 0
with col3:
    if st.button("🚨 Emergency Checklist", type="primary", use_container_width=True):
        st.session_state.current_mode = "Emergency"

# ────────────────────────────────────────────────
# PILOT MODE (unchanged)
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.subheader("Pilot Mode – Helicopter Performance & Risk Assessment")

    st.subheader("My Fleet")
    if st.session_state.fleet:
        fleet_nicknames = ["— Select a saved aircraft —"] + [e["nickname"] for e in st.session_state.fleet]
        selected_nickname = st.selectbox("Load from Fleet", fleet_nicknames)
        if selected_nickname != "— Select a saved aircraft —":
            entry = next(e for e in st.session_state.fleet if e["nickname"] == selected_nickname)
            st.session_state.selected_option = entry["aircraft"]
            st.success(f"Loaded **{selected_nickname}**")
    else:
        st.info("No aircraft saved to fleet yet.")

    selected_aircraft = st.selectbox("Select Helicopter", list(AIRCRAFT_DATA.keys()))

    st.subheader("Custom Empty Weight (optional)")
    current_empty = st.session_state.get('custom_empty_weight') or AIRCRAFT_DATA[selected_aircraft]["base_empty_weight_lbs"]
    custom_empty = st.number_input(
        f"Custom Empty Weight for {selected_aircraft} (lb)",
        min_value=500,
        max_value=int(AIRCRAFT_DATA[selected_aircraft]["max_takeoff_weight_lbs"] * 0.9),
        value=int(current_empty),
        step=10
    )
    if st.button("Save to Fleet"):
        nickname = st.text_input("Nickname (e.g. N893PC-R44)", key="fleet_nickname")
        if nickname.strip():
            st.session_state.fleet.append({"nickname": nickname.strip(), "aircraft": selected_aircraft, "custom_empty": custom_empty})
            st.success(f"Saved **{nickname}** to fleet!")

    st.subheader("Performance Inputs")
    col_a, col_b = st.columns(2)
    with col_a:
        pressure_alt_ft = st.number_input("Pressure Altitude (ft)", value=1600, step=100)
        oat_c = st.number_input("OAT (°C)", value=15, step=1)
        wind_kts = st.number_input("Wind (kts, headwind positive)", value=0, step=1)
    with col_b:
        fuel_gal = st.number_input("Fuel (gal)", value=30, step=5)
        hopper_gal = st.number_input("Hopper / Spray (gal)", value=83 if "R44" in selected_aircraft else 100, step=5)
        pilot_weight_lbs = st.number_input("Pilot Weight (lbs)", value=200, step=10)

    if st.button("Calculate Performance", type="primary"):
        da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
        weight_lbs = custom_empty + fuel_gal * AIRCRAFT_DATA[selected_aircraft]["fuel_weight_per_gal"] + hopper_gal * AIRCRAFT_DATA[selected_aircraft]["hopper_weight_per_gal"] + pilot_weight_lbs

        ground_roll_to, to_50ft = compute_takeoff(pressure_alt_ft, oat_c, weight_lbs, wind_kts, selected_aircraft)
        ground_roll_land, from_50ft = compute_landing(pressure_alt_ft, oat_c, weight_lbs, wind_kts, selected_aircraft)
        climb_rate = compute_climb_rate(pressure_alt_ft, oat_c, weight_lbs, selected_aircraft)
        stall_speed = compute_stall_speed(weight_lbs, selected_aircraft)
        glide_dist = compute_glide_distance(5000, wind_kts, selected_aircraft)
        total_weight, cg_status = compute_weight_balance(fuel_gal, hopper_gal, pilot_weight_lbs, selected_aircraft)
        ige_ceiling, oge_ceiling = compute_hover_ceiling(da_ft, weight_lbs, selected_aircraft)

        st.subheader("Results")
        st.metric("Takeoff Ground Roll", f"{ground_roll_to:.0f} ft")
        st.metric("Takeoff to 50 ft", f"{to_50ft:.0f} ft")
        st.metric("Landing Ground Roll", f"{ground_roll_land:.0f} ft")
        st.metric("Landing from 50 ft", f"{from_50ft:.0f} ft")
        st.metric("Climb Rate", f"{climb_rate:.0f} fpm")
        st.metric("Stall Speed (flaps down)", f"{stall_speed:.1f} mph")
        st.metric("Glide Distance (from 5000 ft)", f"{glide_dist:.1f} nm")
        st.metric("Total Weight", f"{total_weight:.0f} lbs – {cg_status}")
        st.metric("IGE Hover Ceiling", f"{ige_ceiling:.0f} ft")
        st.metric("OGE Hover Ceiling", f"{oge_ceiling:.0f} ft")

        st.subheader("Rate of Climb vs Pressure Altitude")
        altitudes = np.linspace(0, 12000, 60)
        climb_rates = [compute_climb_rate(alt, oat_c, weight_lbs, selected_aircraft) for alt in altitudes]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(altitudes, climb_rates, color='darkgreen', linewidth=2)
        ax.set_xlabel("Pressure Altitude (ft)")
        ax.set_ylabel("Rate of Climb (fpm)")
        ax.set_title(f"Climb Performance – {selected_aircraft}")
        ax.grid(True)
        st.pyplot(fig)

    if st.button("Risk Assessment", type="secondary"):
        st.session_state.show_risk = not st.session_state.show_risk
    if st.session_state.show_risk:
        show_risk_assessment()

# ────────────────────────────────────────────────
# DRIVER MODE – Rear Weight for Heli2 + updated Axle Load Status
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Driver":
    st.subheader("Select Your Truck")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Heli2", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli2"
            st.session_state.last_max_water_gal = 0
            st.session_state.last_current_weight = 0
        if st.button("Heli4", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli4"
            st.session_state.last_max_water_gal = 0
            st.session_state.last_current_weight = 0
        if st.button("Seed1", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Seed1"
            st.session_state.last_max_water_gal = 0
            st.session_state.last_current_weight = 0
    with col2:
        if st.button("Heli3", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "Heli3"
            st.session_state.last_max_water_gal = 0
            st.session_state.last_current_weight = 0
        if st.button("C8000", type="secondary", use_container_width=True):
            st.session_state.selected_heli = "C8000"
            st.session_state.last_max_water_gal = 0
            st.session_state.last_current_weight = 0

    if st.session_state.get("selected_heli"):
        selected = st.session_state.selected_heli
        st.subheader(f"Pre-Trip Inspection for {selected}")

        st.markdown("---")
        st.subheader("💧 Compute Water Load")
        st.caption("Enter values – Current Weight updates live")

        empty_weight = st.number_input("Empty Weight (lbs)", value=DEFAULT_EMPTY_WEIGHT.get(selected, 31120), step=10)
        gvw = st.number_input("GVW (lbs)", value=DEFAULT_GVW.get(selected, 54000), step=10)
        product_weight = st.number_input("Product Weight (lbs)", value=0, step=10)

        # Rear Weight slider – only for Heli2
        if selected == "Heli2":
            rear_weight = st.number_input("Rear Weight (lbs)", value=0, step=10)
        else:
            rear_weight = 0

        heli_fuel_pct = st.slider("Heli Fuel Tank % Full", 0, 100, 100)
        truck_fuel_pct = st.slider("Truck Fuel % Full", 0, 100, 100)

        truck_fuel_max = TRUCK_FUEL_MAX_LBS.get(selected, 420)
        heli_fuel_max = HELI_FUEL_MAX_LBS.get(selected, 420)
        truck_fuel_weight = (truck_fuel_pct / 100.0) * truck_fuel_max
        heli_fuel_weight = (heli_fuel_pct / 100.0) * heli_fuel_max
        current_weight = empty_weight + truck_fuel_weight + heli_fuel_weight + product_weight + rear_weight

        st.metric("**Current Weight**", f"{current_weight:.0f} lbs")

        if st.button("Compute Water", type="primary", use_container_width=True):
            remaining = gvw - current_weight
            max_water_gal = max(0, remaining / 8.34)
            total_with_water = current_weight + (max_water_gal * 8.34)
            st.session_state.last_max_water_gal = max_water_gal
            st.session_state.last_current_weight = current_weight
            st.success(f"**Maximum water you can load: {max_water_gal:.0f} gallons**")
            st.markdown(f"**New Weight with Water = {total_with_water:.0f} lbs.**")

        # Flashing label for Heli2 only (after Compute Water)
        if selected == "Heli2" and st.session_state.get("last_max_water_gal", 0) > 0:
            total_with_water = st.session_state.last_current_weight + (st.session_state.last_max_water_gal * 8.34)
            if product_weight > 0 and total_with_water > 48000:
                st.markdown("""
                <div style="animation: flash 1s infinite; background:#ff4444; color:white; padding:15px; 
                            text-align:center; font-size:18px; font-weight:bold; border-radius:8px;">
                    ⚠️ Put Drop Axle Down for weight exceeding 48,000 lbs.
                </div>
                <style>
                @keyframes flash {
                    0% { opacity: 1; }
                    50% { opacity: 0.3; }
                    100% { opacity: 1; }
                }
                </style>
                """, unsafe_allow_html=True)

        # Axle Load Status for Heli2 – using your exact empty weights and new positions
        if selected == "Heli2":
            st.subheader("Axle Load Status (Heli2)")
            st.metric("Front Axle (empty)", f"{HELI2_EMPTY_FRONT} lbs")
            st.metric("Drive Axle 1 (empty)", f"{HELI2_EMPTY_DRIVE // 2} lbs (approx)")
            st.metric("Drive Axle 2 (empty)", f"{HELI2_EMPTY_DRIVE // 2} lbs (approx)")
            st.metric("Tag Axle (empty)", "0 lbs")
            st.caption("Positions: Front = 0\", Drive1 = 232\", Drive2 = 283\", Tag = 334\"")
            st.caption("**Note:** Full live axle load calculation (with product, water, rear, fuels) requires exact load distribution and tag-up/down logic. Reply with any additional data and I’ll add the complete live calculator.")

        # Pre-Trip Inspection Checklist
        st.markdown("---")
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
                "heli": selected,
                "results": results,
                "notes": notes,
                "photo": photo
            })
            st.success("Inspection submitted!")

        if st.session_state.inspections:
            st.subheader("Recent Inspections")
            for insp in reversed(st.session_state.inspections[-5:]):
                with st.expander(f"{insp['timestamp']} – {insp.get('heli','Unknown')}"):
                    for k, v in insp["results"].items():
                        st.write(f"{k}: {v}")
                    if insp["notes"]:
                        st.caption(f"Notes: {insp['notes']}")
                    if insp.get("photo"):
                        st.image(insp["photo"])

# ────────────────────────────────────────────────
# EMERGENCY CHECKLIST
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Emergency":
    st.subheader("🚨 Emergency Response Checklist")
    st.markdown("### Priority (PILOT): Aviate → Navigate → Communicate")
    st.markdown("""
    1. **Declare emergency / Call 911 / First aid**
       - Turn fuel shut-off off, battery switch off.
       - Evacuate upwind if fire or chemical risk.
       - Check for spray/fuel contamination; give SDS to responders.
       - Follow Spill Response Procedure.
       - Preserve wreckage and documents.

    2. **Witnesses & Scene Control**
       - Secure scene with spill response team.
       - Do NOT speak to media or officials.
       - Say only: "Company has contacted appropriate authorities for full investigation to determine root cause and prevent recurrence."
       - Do NOT speculate on cause.

    3. **Media & Press Inquiries**
       - Refer all calls to informed management.
       - Management will notify FAA and NTSB.
       - Direct inquiries to informed managers.
       - Contact local law enforcement.
       - Arrange wreckage preservation.

    4. **Additional Immediate Steps**
       - Is ELT activated?
       - Treat injuries (first aid kit); assure area is protected.
       - Call 911 or local: Kittitas County Sheriff 509-962-1234
    """)
    st.markdown("**Local Emergency Contacts**")
    st.markdown("- **Emergency**: **911**")
    st.markdown("- **Poison Control**: **1-800-222-1222**")
    st.markdown("[Call 911 (Emergency)](tel:911)", unsafe_allow_html=True)
    st.info("Quick-reference only. Follow your company Emergency Response Plan.")

st.caption("**Safe flying & have a Blessed day** ⌯✈︎")
