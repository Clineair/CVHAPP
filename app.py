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

# [All your original functions are here exactly as before: calculate_density_altitude, compute_takeoff, etc., show_risk_assessment()]

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
with col3:
    if st.button("🚨 Emergency Checklist", type="primary", use_container_width=True):
        st.session_state.current_mode = "Emergency"

# ────────────────────────────────────────────────
# PILOT MODE
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
                status = st.radio("Status", ["OK ✅", "DEFECT ❌"], key=f"{st.session_state.selected_heli}_{item}", horizontal=True, index=0)
                results[item] = status

        notes = st.text_area("Notes / Defects found")
        photo = st.camera_input("Take photo of defect (optional)") or st.file_uploader("Upload photo", type=["jpg","png"])

        if st.button("✅ Submit Pre-Trip Inspection", type="primary", use_container_width=True):
            st.session_state.inspections.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "heli": st.session_state.selected_heli,
                "results": results,
                "notes": notes,
                "photo": photo
            })

            # Email to you
            try:
                msg = MIMEMultipart()
                msg['From'] = st.secrets["email"]["address"]
                msg['To'] = "cvh@centralvalleyheli.com"
                msg['Subject'] = f"CVH Driver Pre-Trip – {st.session_state.selected_heli} – {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                body = f"Heli: {st.session_state.selected_heli}\n\n"
                for item, status in results.items():
                    body += f"{item}: {status}\n"
                body += f"\nNotes: {notes or 'None'}\n"
                msg.attach(MIMEText(body, 'plain'))

                if photo:
                    img = MIMEImage(photo.getvalue())
                    img.add_header('Content-Disposition', 'attachment', filename="defect_photo.jpg")
                    msg.attach(img)

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(st.secrets["email"]["address"], st.secrets["email"]["password"])
                server.send_message(msg)
                server.quit()

                st.success("✅ Inspection submitted and emailed to cvh@centralvalleyheli.com!")
                st.balloons()
            except Exception as e:
                st.error(f"Email failed: {e} (check Secrets)")

        # Recent inspections
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
