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
    page_title="AgPilotApp – Aerial Application Performance Tool",
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
# Custom Logo (your provided logo – using raw GitHub URL)
# ────────────────────────────────────────────────
LOGO_URL = "https://raw.githubusercontent.com/Clineair/AgPilot-app/main/AgPilotApp.png"

try:
    st.image(LOGO_URL, use_column_width=True)  # Displays as full-width header logo
    st.logo(LOGO_URL, size="medium")  # Sidebar logo
except Exception:
    try:
        st.image("AgPilotApp.png", use_column_width=True)  # Fallback to local file if URL fails
        st.logo("AgPilotApp.png", size="medium")
    except Exception:
        st.markdown("### AgPilotApp ⌯✈︎ (logo not loaded – check file/URL)")

# ────────────────────────────────────────────────
# Session State Initialization
# ────────────────────────────────────────────────
if 'fleet' not in st.session_state:
    st.session_state.fleet = []
if 'custom_empty_weight' not in st.session_state:
    st.session_state.custom_empty_weight = None
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False

# ────────────────────────────────────────────────
# Default performance values (PREVENTS NameError before first calculation)
# ────────────────────────────────────────────────
ground_roll_to = to_50ft = ground_roll_land = from_50ft = 0
climb_rate = stall_speed = glide_dist = total_weight = 0
ige_ceiling = oge_ceiling = 0
cg_status = "Not calculated yet"

# ────────────────────────────────────────────────
# Aircraft Database
# ────────────────────────────────────────────────
AIRCRAFT_DATA = {
    "Air Tractor AT-502B": {
        "name": "Air Tractor AT-502B",
        "base_takeoff_ground_roll_ft": 1140,
        "base_takeoff_to_50ft_ft": 2600,
        "base_landing_ground_roll_ft": 600,
        "base_landing_to_50ft_ft": 1350,
        "base_climb_rate_fpm": 870,
        "base_stall_flaps_down_mph": 68,
        "best_climb_speed_mph": 111,
        "base_empty_weight_lbs": 4546,
        "base_fuel_capacity_gal": 170,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 500,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 9400,
        "max_landing_weight_lbs": 8000,
        "glide_ratio": 8.0,
        "description": "Single-engine piston ag aircraft"
    },
    "Air Tractor AT-602": {
        "name": "Air Tractor AT-602",
        "base_takeoff_ground_roll_ft": 1400,
        "base_takeoff_to_50ft_ft": 2800,
        "base_landing_ground_roll_ft": 850,
        "base_landing_to_50ft_ft": 1850,
        "base_climb_rate_fpm": 1050,
        "base_stall_flaps_down_mph": 74,
        "best_climb_speed_mph": 118,
        "base_empty_weight_lbs": 6200,
        "base_fuel_capacity_gal": 380,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 600,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 12500,
        "max_landing_weight_lbs": 11000,
        "glide_ratio": 7.2,
        "description": "Turbine ag aircraft – balanced payload & performance",
        "hover_ceiling_ige_max_gw": 0,
        "hover_ceiling_oge_max_gw": 0
    },
    "Air Tractor AT-802": {
        "name": "Air Tractor AT-802",
        "base_takeoff_ground_roll_ft": 1800,
        "base_takeoff_to_50ft_ft": 3400,
        "base_landing_ground_roll_ft": 1100,
        "base_landing_to_50ft_ft": 2200,
        "base_climb_rate_fpm": 1050,
        "base_stall_flaps_down_mph": 78,
        "best_climb_speed_mph": 120,
        "base_empty_weight_lbs": 6750,
        "base_fuel_capacity_gal": 380,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 800,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 16000,
        "max_landing_weight_lbs": 14000,
        "glide_ratio": 7.0,
        "description": "Large turbine ag aircraft – high payload & range"
    },
    "Thrush 510P": {
        "name": "Thrush 510P",
        "base_takeoff_ground_roll_ft": 1300,
        "base_takeoff_to_50ft_ft": 2800,
        "base_landing_ground_roll_ft": 750,
        "base_landing_to_50ft_ft": 1600,
        "base_climb_rate_fpm": 950,
        "base_stall_flaps_down_mph": 72,
        "best_climb_speed_mph": 115,
        "base_empty_weight_lbs": 6800,
        "base_fuel_capacity_gal": 380,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 510,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 12000,
        "max_landing_weight_lbs": 10500,
        "glide_ratio": 7.5,
        "description": "Turbine-powered high-capacity ag aircraft"
    },
    "Ayres Thrush S2R-T34 Eagle": {
        "name": "Ayres Thrush S2R-T34 Eagle",
        "base_takeoff_ground_roll_ft": 1650,
        "base_takeoff_to_50ft_ft": 2500,
        "base_landing_ground_roll_ft": 600,
        "base_landing_to_50ft_ft": 1500,
        "base_climb_rate_fpm": 666,
        "base_stall_flaps_down_mph": 50,
        "best_climb_speed_mph": 110,
        "base_empty_weight_lbs": 4900,
        "base_fuel_capacity_gal": 228,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 510,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 10500,
        "max_landing_weight_lbs": 10500,
        "glide_ratio": 7.0,
        "description": "Turbine-powered high-capacity ag sprayer – excellent short-field & payload",
        "hover_ceiling_ige_max_gw": 0,
        "hover_ceiling_oge_max_gw": 0
    },
    "Grumman G-164B Ag-Cat": {
        "name": "Grumman G-164B Ag-Cat",
        "base_takeoff_ground_roll_ft": 1200,
        "base_takeoff_to_50ft_ft": 2200,
        "base_landing_ground_roll_ft": 800,
        "base_landing_to_50ft_ft": 1800,
        "base_climb_rate_fpm": 1080,
        "base_stall_flaps_down_mph": 64,
        "best_climb_speed_mph": 90,
        "base_empty_weight_lbs": 3150,
        "base_fuel_capacity_gal": 190,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 400,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 4500,
        "max_landing_weight_lbs": 4500,
        "glide_ratio": 7.5,
        "description": "Classic radial-engine biplane ag sprayer – rugged & low stall speed"
    },
    "Cessna 188 Ag Truck": {
        "name": "Cessna 188 Ag Truck",
        "base_takeoff_ground_roll_ft": 680,
        "base_takeoff_to_50ft_ft": 1090,
        "base_landing_ground_roll_ft": 420,
        "base_landing_to_50ft_ft": 1265,
        "base_climb_rate_fpm": 690,
        "base_stall_flaps_down_mph": 50,
        "best_climb_speed_mph": 80,
        "base_empty_weight_lbs": 2220,
        "base_fuel_capacity_gal": 54,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 280,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 4200,
        "max_landing_weight_lbs": 4200,
        "glide_ratio": 8.0,
        "description": "Classic single-engine piston ag sprayer"
    },
    "Cessna AgHusky": {
        "name": "Cessna AgHusky",
        "base_takeoff_ground_roll_ft": 750,
        "base_takeoff_to_50ft_ft": 1350,
        "base_landing_ground_roll_ft": 450,
        "base_landing_to_50ft_ft": 1200,
        "base_climb_rate_fpm": 750,
        "base_stall_flaps_down_mph": 52,
        "best_climb_speed_mph": 85,
        "base_empty_weight_lbs": 2400,
        "base_fuel_capacity_gal": 60,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 280,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 4200,
        "max_landing_weight_lbs": 4200,
        "glide_ratio": 8.0,
        "description": "Cessna 188 AgHusky variant – rugged piston ag sprayer with good short-field performance"
    },
    "Piper PA-36 Pawnee Brave": {
        "name": "Piper PA-36 Pawnee Brave",
        "base_takeoff_ground_roll_ft": 1200,
        "base_takeoff_to_50ft_ft": 1500,
        "base_landing_ground_roll_ft": 850,
        "base_landing_to_50ft_ft": 1800,
        "base_climb_rate_fpm": 920,
        "base_stall_flaps_down_mph": 65,
        "best_climb_speed_mph": 100,
        "base_empty_weight_lbs": 2560,
        "base_fuel_capacity_gal": 86,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 275,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 4800,
        "max_landing_weight_lbs": 4800,
        "glide_ratio": 7.5,
        "description": "Single-engine piston ag sprayer – large hopper & good swath width"
    },
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
    "Bell 206 JetRanger III": {
        "name": "Bell 206 JetRanger III",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1280,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1635,
        "base_fuel_capacity_gal": 91,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 100,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 3200,
        "max_landing_weight_lbs": 3200,
        "glide_ratio": 4.0,
        "description": "Light utility helicopter (spray capable)",
        "hover_ceiling_ige_max_gw": 12800,
        "hover_ceiling_oge_max_gw": 8800
    },
    "Airbus AS350 B2": {
        "name": "Airbus AS350 B2",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1675,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 2800,
        "base_fuel_capacity_gal": 143,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 150,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 4960,
        "max_landing_weight_lbs": 4960,
        "glide_ratio": 4.0,
        "description": "Turbine ag spray helicopter – high performance utility",
        "hover_ceiling_ige_max_gw": 9850,
        "hover_ceiling_oge_max_gw": 7550
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
    },
    "Enstrom 480B": {
        "name": "Enstrom 480B",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1200,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1800,
        "base_fuel_capacity_gal": 95,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 100,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2850,
        "max_landing_weight_lbs": 2850,
        "glide_ratio": 4.0,
        "description": "Improved turbine light utility helicopter (spray capable)",
        "hover_ceiling_ige_max_gw": 12000,
        "hover_ceiling_oge_max_gw": 9000
    },
    "Robinson R66": {
        "name": "Robinson R66",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1100,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1290,
        "base_fuel_capacity_gal": 73.6,
        "fuel_weight_per_gal": 6.7,
        "hopper_capacity_gal": 130,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2700,
        "max_landing_weight_lbs": 2700,
        "glide_ratio": 4.0,
        "description": "Turbine light utility helicopter (spray capable)",
        "hover_ceiling_ige_max_gw": 11000,
        "hover_ceiling_oge_max_gw": 10000
    },
    "Enstrom F28F": {
        "name": "Enstrom F28F",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 1450,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 57,
        "base_empty_weight_lbs": 1640,
        "base_fuel_capacity_gal": 40,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 100,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2600,
        "max_landing_weight_lbs": 2600,
        "glide_ratio": 4.0,
        "description": "Piston helicopter (Falcon) – utility/ag capable",
        "hover_ceiling_ige_max_gw": 13200,
        "hover_ceiling_oge_max_gw": 8700
    },
    "Scott's Bell 47": {
        "name": "Scott's Bell 47",
        "base_takeoff_ground_roll_ft": 0,
        "base_takeoff_to_50ft_ft": 0,
        "base_landing_ground_roll_ft": 0,
        "base_landing_to_50ft_ft": 0,
        "base_climb_rate_fpm": 900,
        "base_stall_flaps_down_mph": 0,
        "best_climb_speed_mph": 60,
        "base_empty_weight_lbs": 1900,
        "base_fuel_capacity_gal": 43,
        "fuel_weight_per_gal": 6.0,
        "hopper_capacity_gal": 100,
        "hopper_weight_per_gal": 8.3,
        "max_takeoff_weight_lbs": 2950,
        "max_landing_weight_lbs": 2950,
        "glide_ratio": 4.0,
        "description": "Light piston utility/ag helicopter – classic bubble canopy, spray capable",
        "hover_ceiling_ige_max_gw": 10000,
        "hover_ceiling_oge_max_gw": 8000
    },
}

# ────────────────────────────────────────────────
# Density Altitude Calculation
# ────────────────────────────────────────────────
def calculate_density_altitude(pressure_alt_ft, oat_c):
    isa_temp_c = 15 - (2 * (pressure_alt_ft / 1000))
    deviation = oat_c - isa_temp_c
    da_ft = pressure_alt_ft + (120 * deviation)
    return round(da_ft)

# ────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────
def adjust_for_weight(value, current_weight, base_weight, exponent=1.5):
    return value * (current_weight / base_weight) ** exponent

def adjust_for_runway_condition(value, condition):
    multipliers = {
        "Paved / Dry Hard Surface": 1.00,
        "Dry Grass / Firm Turf": 1.15,
        "Wet Grass / Damp Turf": 1.45,
        "Soft / Muddy / Rough": 1.80
    }
    factor = multipliers.get(condition, 1.00)
    return value * factor

def adjust_for_wind(value, wind_kts):
    factor = 1 - (0.1 * wind_kts / 9)
    return value * max(factor, 0.5)

def adjust_for_da(value, da_ft):
    factor = 1 + (0.07 * da_ft / 1000)
    return value * factor

@st.cache_data
def compute_takeoff(pressure_alt_ft, oat_c, weight_lbs, wind_kts, runway_condition, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
    ground_roll = adjust_for_weight(data["base_takeoff_ground_roll_ft"], weight_lbs, data["max_takeoff_weight_lbs"])
    ground_roll = adjust_for_da(ground_roll, da_ft)
    ground_roll = adjust_for_wind(ground_roll, wind_kts)
    ground_roll = adjust_for_runway_condition(ground_roll, runway_condition)
    to_50ft = adjust_for_weight(data["base_takeoff_to_50ft_ft"], weight_lbs, data["max_takeoff_weight_lbs"])
    to_50ft = adjust_for_da(to_50ft, da_ft)
    to_50ft = adjust_for_wind(to_50ft, wind_kts)
    to_50ft = adjust_for_runway_condition(to_50ft, runway_condition) * 1.10
    return ground_roll, to_50ft

@st.cache_data
def compute_landing(pressure_alt_ft, oat_c, weight_lbs, wind_kts, runway_condition, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    weight_lbs = min(weight_lbs, data["max_landing_weight_lbs"])
    da_ft = calculate_density_altitude(pressure_alt_ft, oat_c)
    ground_roll = adjust_for_weight(data["base_landing_ground_roll_ft"], weight_lbs, data["max_landing_weight_lbs"], exponent=1.0)
    ground_roll = adjust_for_da(ground_roll, da_ft)
    ground_roll = adjust_for_wind(ground_roll, wind_kts)
    ground_roll = adjust_for_runway_condition(ground_roll, runway_condition)
    from_50ft = adjust_for_weight(data["base_landing_to_50ft_ft"], weight_lbs, data["max_landing_weight_lbs"], exponent=1.0)
    from_50ft = adjust_for_da(from_50ft, da_ft)
    from_50ft = adjust_for_wind(from_50ft, wind_kts)
    from_50ft = adjust_for_runway_condition(from_50ft, runway_condition) * 1.15
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
    data = AIRCRAFT_DATA[aircraft]
    is_helicopter = any(heli in aircraft for heli in ["R44", "Bell 206", "Enstrom 480", "Enstrom 480B", "Robinson R66", "Airbus AS350", "Enstrom F28F", "Bell 47"])
    if is_helicopter:
        base_distance_nm = height_ft / 1300
        wind_factor = 1 + (wind_kts / 20)
        return base_distance_nm * wind_factor
    else:
        ground_speed_mph = 100 + wind_kts
        return (height_ft / 6076) * data["glide_ratio"] * (ground_speed_mph / 60)

@st.cache_data
def compute_weight_balance(fuel_gal, hopper_gal, pilot_weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    empty_weight = st.session_state.get('custom_empty_weight')
    if empty_weight is None:
        empty_weight = data["base_empty_weight_lbs"]
    else:
        empty_weight = int(empty_weight)
    fuel_weight = fuel_gal * data["fuel_weight_per_gal"]
    hopper_weight = hopper_gal * data["hopper_weight_per_gal"]
    total_weight = empty_weight + fuel_weight + hopper_weight + pilot_weight_lbs
    status = "Within limits" if total_weight <= data["max_takeoff_weight_lbs"] else "Overweight!"
    if total_weight > data["max_landing_weight_lbs"]:
        status += " (Exceeds max landing weight)"
    return total_weight, status

def compute_hover_ceiling(da_ft, weight_lbs, aircraft):
    data = AIRCRAFT_DATA[aircraft]
    base_ceiling_ige = data.get("hover_ceiling_ige_max_gw", 0)
    base_ceiling_oge = data.get("hover_ceiling_oge_max_gw", 0)
    weight_factor = (data["max_takeoff_weight_lbs"] - weight_lbs) / 500.0
    ige_ceiling = base_ceiling_ige + (weight_factor * 1000)
    oge_ceiling = base_ceiling_oge + (weight_factor * 800)
    da_loss = da_ft / 1000 * 1000
    ige_ceiling -= da_loss
    oge_ceiling -= da_loss
    ige_ceiling = max(0, ige_ceiling)
    oge_ceiling = max(0, oge_ceiling)
    return ige_ceiling, oge_ceiling

# ────────────────────────────────────────────────
# Risk Assessment
# ────────────────────────────────────────────────
def show_risk_assessment():
    st.subheader("Risk Assessment")
    st.caption("Score each factor 0–10 (higher = more risk).")
    total_risk = 0
    st.markdown("**Pilot Factors**")
    pilot_exp = st.slider("Recent experience/currency (hours last 30 days)", min_value=0, max_value=10, value=5, step=1)
    total_risk += pilot_exp
    pilot_fatigue = st.slider("Fatigue/sleep last 24 hours", min_value=0, max_value=10, value=5, step=1)
    total_risk += pilot_fatigue
    pilot_health = st.slider("Physical/mental health today", min_value=0, max_value=10, value=2, step=1)
    total_risk += pilot_health
    st.markdown("**Aircraft Factors**")
    ac_maintenance = st.slider("Maintenance status/known squawks", min_value=0, max_value=10, value=3, step=1)
    total_risk += ac_maintenance
    ac_fuel = st.slider("Fuel planning/reserves", min_value=0, max_value=10, value=2, step=1)
    total_risk += ac_fuel
    ac_weight = st.slider("Weight & balance/CG within limits", min_value=0, max_value=10, value=2, step=1)
    total_risk += ac_weight
    st.markdown("**Environment / Weather**")
    weather_ceiling = st.slider("Ceiling/visibility (VFR/IFR conditions)", min_value=0, max_value=10, value=4, step=1)
    total_risk += weather_ceiling
    weather_turb = st.slider("Turbulence/icing/wind forecast", min_value=0, max_value=10, value=3, step=1)
    total_risk += weather_turb
    weather_notams = st.slider("NOTAMs/TFRs/airspace restrictions", min_value=0, max_value=10, value=3, step=1)
    total_risk += weather_notams
    st.markdown("**Operations / Flight Plan**")
    flight_complexity = st.slider("Flight complexity (obstructions/towers/wires/tracklines/birds)", min_value=0, max_value=10, value=4, step=1)
    total_risk += flight_complexity
    alternate_plan = st.slider("Alternate/emergency options planned", min_value=0, max_value=10, value=2, step=1)
    total_risk += alternate_plan
    night_ops = st.slider("Night or low-light operations", min_value=0, max_value=10, value=0, step=1)
    total_risk += night_ops
    st.markdown("**External Pressures**")
    get_there_itis = st.slider("Get-there-itis/schedule pressure", min_value=0, max_value=10, value=2, step=1)
    total_risk += get_there_itis
    customer_pressure = st.slider("Customer/family/operational pressure", min_value=0, max_value=10, value=2, step=1)
    total_risk += customer_pressure
    st.markdown("---")
    risk_percent = (total_risk / 100) * 100
    if total_risk <= 30:
        level = "Low Risk"
        color = "#4CAF50"
        emoji = "🟢"
    elif total_risk <= 60:
        level = "Medium Risk"
        color = "#FF9800"
        emoji = "🟡"
    else:
        level = "High Risk"
        color = "#F44336"
        emoji = "🔴"
    gauge_html = f"""
    <div style="text-align:center; margin: 30px 0;">
        <div style="
            width: 220px;
            height: 220px;
            border-radius: 50%;
            background: conic-gradient(
                {color} {risk_percent}%,
                #e0e0e0 {risk_percent}% 100%
            );
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
            position: relative;
            box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        ">
            <div style="
                width: 170px;
                height: 170px;
                background: white;
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                box-shadow: inset 0 4px 10px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 48px; font-weight: bold; color: {color};">{risk_percent:.0f}%</div>
                <div style="font-size: 18px; color: #555;">{level}</div>
            </div>
        </div>
        <div style="margin-top: 15px; font-size: 22px; font-weight: bold; color: {color};">
            {emoji} {level}
        </div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)
    if total_risk > 30:
        st.info("**Mitigation Recommendations**")
        st.markdown("- Delay departure or mitigate")
        st.markdown("- Increase fuel or choose closer field")
        st.markdown("- Consult for second opinion")
        st.markdown("- Screenshot and re-assess high risk")
    st.caption("Not a substitute for official preflight briefing or company policy.")

# ────────────────────────────────────────────────
# Main App
# ────────────────────────────────────────────────
st.title("AgPilot")
st.markdown("Performance calculator for agricultural aircraft & helicopters")
st.caption("Prototype – educational use only. Always refer to the official Pilot Operating Handbook (POH) for actual operations.")

# Fleet Management
st.subheader("My Fleet")
if st.session_state.fleet:
    fleet_nicknames = ["— Select a saved aircraft —"] + [entry["nickname"] for entry in st.session_state.fleet]
    selected_nickname = st.selectbox("Load from Fleet", fleet_nicknames)
    if selected_nickname != "— Select a saved aircraft —":
        entry = next(e for e in st.session_state.fleet if e["nickname"] == selected_nickname)
        st.session_state.selected_aircraft = entry["aircraft"]
        custom = entry.get("custom_empty")
        st.session_state.custom_empty_weight = int(custom) if custom is not None else None
        st.success(f"Loaded **{selected_nickname}** ({entry['aircraft']}) – Empty: {custom or 'base'} lb")
else:
    st.info("No aircraft saved to fleet yet.")

# Aircraft selection
selected_aircraft = st.selectbox(
    "Select Aircraft",
    options=list(AIRCRAFT_DATA.keys()),
    index=0 if 'selected_aircraft' not in st.session_state else list(AIRCRAFT_DATA.keys()).index(st.session_state.get("selected_aircraft", list(AIRCRAFT_DATA.keys())[0])),
    format_func=lambda x: f"{AIRCRAFT_DATA[x]['name']} – {AIRCRAFT_DATA[x]['description']}"
)
aircraft_data = AIRCRAFT_DATA[selected_aircraft]

# Helicopter detection
is_helicopter = any(heli in selected_aircraft for heli in [
    "R44", "Bell 206", "Enstrom 480", "Enstrom 480B", "Robinson R66",
    "Airbus AS350", "Enstrom F28F", "Bell 47"
])

# Custom Empty Weight Input
st.subheader("Custom Empty Weight (optional)")
col_empty1, col_empty2 = st.columns([3, 1])
with col_empty1:
    current_empty = st.session_state.get('custom_empty_weight')
    if current_empty is None:
        current_empty = aircraft_data["base_empty_weight_lbs"]
    else:
        current_empty = int(current_empty)
    custom_empty = st.number_input(
        f"Custom Empty Weight for {aircraft_data['name']} (lb)",
        min_value=500,
        max_value=int(aircraft_data["max_takeoff_weight_lbs"] * 0.9),
        value=current_empty,
        step=10,
        help="Override base empty weight if your aircraft has modifications, avionics, etc."
    )
with col_empty2:
    st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
    if st.button("Save to Fleet"):
        nickname = st.text_input("Give this configuration a nickname (e.g. 'N123AB R66')", key="fleet_nickname")
        if nickname.strip():
            st.session_state.fleet = [e for e in st.session_state.fleet if e["nickname"] != nickname.strip()]
            st.session_state.fleet.append({
                "nickname": nickname.strip(),
                "aircraft": selected_aircraft,
                "custom_empty": custom_empty
            })
            st.success(f"Saved **{nickname}** to fleet!")
        else:
            st.warning("Please enter a nickname to save.")

effective_empty = custom_empty if custom_empty != aircraft_data["base_empty_weight_lbs"] else aircraft_data["base_empty_weight_lbs"]
st.caption(f"**Effective Empty Weight:** {effective_empty} lb {'(custom)' if custom_empty != aircraft_data['base_empty_weight_lbs'] else '(base)'}")

# Risk Assessment button
if st.button("Risk Assessment", type="secondary"):
    st.session_state.show_risk = not st.session_state.get("show_risk", False)

st.info(f"Performance data loaded for **{aircraft_data['name']}**")

if st.session_state.get("show_risk", False):
    show_risk_assessment()

# Airport Weather & Notices
st.subheader("Airport Weather & Notices (METAR + TAF + NOTAMs)")
common_airports = {
    "KELN": "Ellensburg Bowers Field (KELN) – Home base",
    "KYKM": "Yakima Air Terminal (KYKM)",
    "KEAT": "Pangborn Memorial (KEAT) – Wenatchee",
    "KPUW": "Pullman/Moscow Regional (KPUW)",
    "KSEA": "Seattle-Tacoma Intl (KSEA)",
    "None": "—— No airport selected ——"
}
selected_icao = st.selectbox(
    "Select Nearby Airport",
    options=list(common_airports.keys()),
    format_func=lambda x: common_airports.get(x, x),
    index=0
)
custom_icao = st.text_input(
    "Or enter any ICAO code (4 letters)",
    value="",
    max_chars=4,
    help="For any airport worldwide (e.g. KLAX for Los Angeles, KMIA for Miami)"
).strip().upper()
icao_upper = custom_icao if custom_icao and len(custom_icao) == 4 and custom_icao.isalnum() else selected_icao
metar_text = None
metar_timestamp = None
taf_text = None
taf_issued = None
if icao_upper and icao_upper != "None":
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao_upper}.TXT"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            lines = response.text.strip().splitlines()
            if len(lines) >= 2:
                metar_timestamp = lines[0].strip()
                metar_text = lines[1].strip()
            elif lines:
                metar_text = lines[0].strip()
    except Exception as e:
        st.warning(f"METAR fetch error for {icao_upper}: {e}")
    try:
        url = f"https://aviationweather.gov/api/data/taf?ids={icao_upper}&format=raw"
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and response.text.strip():
            taf_text = response.text.strip()
            lines = taf_text.splitlines()
            if lines and "Z" in lines[0]:
                taf_issued = lines[0].split()[1] if len(lines[0].split()) > 1 else None
    except Exception as e:
        st.warning(f"TAF fetch error for {icao_upper}: {e}")
if icao_upper and icao_upper != "None":
    st.markdown(f"**Latest Weather for {icao_upper}**")
    st.markdown("**METAR (Current)**")
    if metar_text:
        st.markdown(f"({metar_timestamp or 'fetched ' + datetime.now().strftime('%Y-%m-%d %H:%M UTC')})")
        st.code(metar_text, language="text")
        parts = metar_text.split()
        wind_part = next((p for p in parts if "KT" in p and len(p) >= 6), "—")
        temp_dew_part = next((p for p in parts if "/" in p and len(p.split("/")) == 2), "—")
        altimeter_part = next((p for p in parts if (p.startswith("A") and len(p) == 5) or p.startswith("Q")), "—")
        cols = st.columns(3)
        cols[0].metric("Wind", wind_part)
        cols[1].metric("Temp / Dew", temp_dew_part)
        cols[2].metric("Altimeter", altimeter_part)
    else:
        st.info("No METAR available – check ICAO code or try later.")
    st.markdown("**TAF (Forecast)**")
    if taf_text:
        issued_str = f"Issued ~ {taf_issued}" if taf_issued else f"Fetched {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        st.markdown(f"({issued_str})")
        st.code(taf_text, language="text")
    else:
        st.info("No TAF available (common for small fields).")
    st.markdown("**NOTAMs (Notices to Airmen)**")
    st.caption("**Always check current NOTAMs via official FAA sources before flight.**")
