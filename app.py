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
        ... (full table as before)
        
        By using this app, you agree to these terms. This app is for educational purposes only.
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

# ────────────────────────────────────────────────
# Aircraft Database – PERFECTLY INDENTED (this was the error line 63)
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
    }
}

# (All the rest of the functions and main app code are exactly the same as my previous message – 
# density altitude, helpers, compute_takeoff, compute_landing, risk gauge, fleet, weather, etc.)

# ────────────────────────────────────────────────
# [Full rest of the code from my previous response continues here – 
# I kept it identical except the dictionary is now perfectly indented]
# ────────────────────────────────────────────────
# ... (density altitude function, all @st.cache_data functions, show_risk_assessment, main UI, weather section) ...

# END OF FILE
