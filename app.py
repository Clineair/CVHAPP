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
# Custom Logo
# ────────────────────────────────────────────────
LOGO_URL = "https://raw.githubusercontent.com/Clineair/AgPilot-app/main/AgPilotApp.png"
try:
    st.image(LOGO_URL, use_column_width=True)
    st.logo(LOGO_URL, size="medium")
except Exception:
    try:
        st.image("AgPilotApp.png", use_column_width=True)
        st.logo("AgPilotApp.png", size="medium")
    except Exception:
        st.markdown("### AgPilotApp ⌯✈︎ (logo not loaded – check file/URL)")

# ────────────────────────────────────────────────
# Legal Button (under logo)
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
# Session State & Defaults
# ────────────────────────────────────────────────
if 'fleet' not in st.session_state:
    st.session_state.fleet = []
if 'custom_empty_weight' not in st.session_state:
    st.session_state.custom_empty_weight = None
if 'show_risk' not in st.session_state:
    st.session_state.show_risk = False

ground_roll_to = to_50ft = ground_roll_land = from_50ft = 0
climb_rate = stall_speed = glide_dist = total_weight = 0
ige_ceiling = oge_ceiling = 0
cg_status = "Not calculated yet"

# ────────────────────────────────────────────────
# Aircraft Database (CORRECT 4-SPACE INDENTATION)
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
    }
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
# Helper Functions (rest of your code continues exactly as before)
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

# ... (continue pasting the rest of your original helper functions, risk assessment, main app, weather section, etc. exactly as they were before the dictionary)

# (The rest of your code from compute_landing onward stays identical — just make sure the dictionary above is replaced with this fixed version.)
