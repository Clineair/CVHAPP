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
if 'completed_checklists' not in st.session_state:
    st.session_state.completed_checklists = []

# ────────────────────────────────────────────────
# FRAT Record Storage (Google Sheets via service account; Appendix C paper backup on outage)
# ────────────────────────────────────────────────
import pandas as pd

FRAT_SHEET_NAME = "CVH FRAT Log"
PILOTS = ["Ronald A Cline", "Anthony Root"]
ACCOUNTABLE_EXEC = "Ronald A Cline"
DIRECTOR_MAINTENANCE = "Carl Mulvaney"
APPROVERS = [ACCOUNTABLE_EXEC, DIRECTOR_MAINTENANCE]
PAPER_BACKUP = (
    "Google Sheets save could not be confirmed. Use the Appendix C paper Hazard Log "
    "backup (Manual Sec 3.8): complete the paper assessment, mitigations, pilot sign-off "
    "and any required Medium-risk acceptance BEFORE departure. The Safety Manager "
    "transfers the paper record to Sheets later, checking for duplicates. "
    "No local CSV backup was saved. A NO-GO remains NO-GO."
)
FRAT_AIRCRAFT = ["N893PC – Robinson R44 Raven II (SN 14940)", "N480ML – Enstrom 480 Turbine (SN 5032)"]
PARTS = ["Part 91", "Part 135", "Part 137", "Part 133"]
# Max passengers by aircraft for Part 135 – CONFIRM WITH RON
MAX_PAX = {"Robinson R44 Raven II": 3, "Enstrom 480": 4}

# (key, section, label, default)
CORE_FACTORS = [
    ("pilot_exp", "Daily Pilot Factors", "Recent experience/currency (hours last 30 days – per flight log)", 5),
    ("pilot_fatigue", "Daily Pilot Factors", "Fatigue/sleep last 24 hours", 5),
    ("pilot_health", "Daily Pilot Factors", "Physical/mental health today", 2),
    ("ac_maintenance", "Aircraft Factors", "Maintenance status/known squawks", 3),
    ("ac_fuel", "Aircraft Factors", "Fuel planning/reserves", 2),
    ("ac_weight", "Aircraft Factors", "Weight & balance/CG within limits", 2),
    ("da_performance", "Aircraft Factors", "Density altitude / performance margin (hover OGE/IGE)", 2),
    ("weather_ceiling", "Environment / Weather", "Ceiling/visibility (VFR/IFR conditions)", 4),
    ("weather_turb", "Environment / Weather", "Turbulence/icing/wind forecast", 3),
    ("weather_notams", "Environment / Weather", "NOTAMs/TFRs/airspace restrictions", 3),
    ("terrain", "Environment / Weather", "Terrain / unfamiliar area", 2),
    ("flight_complexity", "Operations / Flight Plan", "Flight complexity (obstructions/towers/wires/slacklines/birds)", 4),
    ("alternate_plan", "Operations / Flight Plan", "Alternate/emergency options planned", 2),
    ("night_ops", "Operations / Flight Plan", "Night or low-light operations", 0),
    ("get_there_itis", "External Pressures", "Get-there-itis/schedule pressure", 2),
    ("customer_pressure", "External Pressures", "Customer/family/operational pressure", 2),
]
PART_FACTORS = {
    "Part 91": [],
    "Part 135": [
        ("landing_zone", "Part 135 Factors", "Landing zone (unimproved / unfamiliar / confined)", 2),
        ("passengers", "Part 135 Factors", "Passengers (number, weights, special needs)", 0),
    ],
    "Part 137": [
        ("ag_wires_field", "Part 137 Factors", "Wires/slacklines/towers in and around the field", 3),
        ("ag_drift_wind", "Part 137 Factors", "Drift / wind / temperature inversion", 2),
        ("ag_chemical", "Part 137 Factors", "Chemical hazard / label restrictions", 2),
        ("ag_sensitive", "Part 137 Factors", "Sensitive areas / buffers (homes, schools, water, organic crops, bees)", 2),
        ("ag_ferry", "Part 137 Factors", "Ferry distance to field", 1),
    ],
    "Part 133": [
        ("ext_load_char", "Part 133 Factors", "Load characteristics (shape / oscillation risk)", 3),
        ("ext_site", "Part 133 Factors", "Pickup/setdown site (confined, rotor-wash debris)", 2),
        ("ext_ground_crew", "Part 133 Factors", "Ground crew experience and communications", 2),
        ("ext_wires_path", "Part 133 Factors", "Wires along load path", 2),
        ("ext_populated", "Part 133 Factors", "Populated area along route", 1),
    ],
}
PART_STOPS = {
    "Part 91": [
        ("stop_airworthy", "Aircraft airworthy with no open grounding squawks"),
        ("stop_vfr_wx", "Weather within VFR minimums (§91.155) for the route"),
        ("stop_wb", "Weight & balance within limits"),
        ("stop_pilot_fit", "Pilot fit to fly (IMSAFE)"),
    ],
    "Part 135": [
        ("stop_duty", "Within duty and rest limits per today's duty log (§135.267)"),
        ("stop_wx", "Weather at or above company minimums for the route (§135.203/§135.205)"),
        ("stop_airworthy", "Aircraft airworthy with no open grounding squawks"),
        ("stop_wb_perf", "Weight & balance and performance within limits for the landing zones"),
        ("stop_pax_brief", "Passengers will receive the required briefing (§135.117)"),
    ],
    "Part 137": [
        ("stop_label", "Product label and application rates verified"),
        ("stop_mix_ppe", "Mixing/loading procedures and PPE in place"),
        ("stop_area_clear", "No unauthorized persons in treatment area; required notifications done"),
        ("stop_ag_wx", "Weather/wind within label and company limits"),
        ("stop_airworthy", "Aircraft airworthy with no open grounding squawks"),
    ],
    "Part 133": [
        ("stop_hook_limit", "Load within hook / RFM limits"),
        ("stop_hook_test", "Cargo hook and release (electrical and manual) tested"),
        ("stop_crew_brief", "Ground crew briefed – hand signals / radio"),
        ("stop_route", "Route avoids congested areas or is approved"),
        ("stop_airworthy", "Aircraft airworthy with no open grounding squawks"),
    ],
}
# Raw-total cutoffs per part (Ron to decide rescaling): Low <= low_max, Medium <= med_max, else High
RISK_CUTOFFS = {p: {"low_max": 30, "med_max": 60} for p in PARTS}

CONFIG_FIELDS = ["pilot_weight", "fuel_gal", "pax_count", "pax_weight", "baggage_weight",
                 "hopper_gal", "product_density", "ext_load_weight", "longline_ft", "hook_equip_weight",
                 "hook_limit", "density_altitude", "internal_weight", "max_gross"]

def _unique(seq):
    out = []
    for s in seq:
        if s not in out:
            out.append(s)
    return out

ALL_FACTOR_KEYS = _unique([f[0] for f in CORE_FACTORS] + [f[0] for p in PARTS for f in PART_FACTORS[p]])
ALL_STOP_KEYS = _unique([s[0] for p in PARTS for s in PART_STOPS[p]])
FRAT_COLUMNS = (["timestamp", "date", "part", "pilot", "aircraft", "route_job"] + CONFIG_FIELDS
                + ALL_FACTOR_KEYS + ALL_STOP_KEYS
                + ["total", "max_total", "percent", "risk_level", "mitigations", "approver",
                   "approved", "pilot_signature", "decision", "ron_unreachable", "pilot_attests"])

def _gsheets_worksheet():
    """Open the production worksheet; configuration and network failures propagate."""
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Google Sheets service account is not configured")
    import gspread
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    sheet_id = st.secrets.get("frat_sheet_id")
    sheet = (gc.open_by_key(sheet_id) if sheet_id else
             gc.open(st.secrets.get("frat_sheet_name") or FRAT_SHEET_NAME))
    return sheet.sheet1


def save_frat_record(record):
    """Append only to Google Sheets. Never silently fall back to a local file."""
    ws = _gsheets_worksheet()
    header = ws.row_values(1)
    if not header:
        ws.append_row(FRAT_COLUMNS, value_input_option="RAW")
    elif header != FRAT_COLUMNS:
        raise RuntimeError("FRAT worksheet headers do not match this app; check the live sheet")
    ws.append_row([str(record.get(c, "")) for c in FRAT_COLUMNS], value_input_option="RAW")
    return "Google Sheets (live FRAT log)"


def load_frat_records():
    """Read Sheets only; the history UI reports unavailable configuration or service."""
    ws = _gsheets_worksheet()
    return pd.DataFrame(ws.get_all_records())

# ────────────────────────────────────────────────
# Risk Assessment – FRAT function (per FAR part; Part 5 §5.51–5.55, records §5.97)
# ────────────────────────────────────────────────
def show_risk_assessment(part, config, da_hint=None, default_aircraft_idx=0):
    st.subheader(f"FRAT – {part}")
    st.caption("Complete before every flight. Score each factor 0–10 (higher = more risk). Records kept 5 years.")
    pax = int(config.get("pax_count") or 0)

    st.markdown("**Flight Information**")
    h1, h2, h3 = st.columns(3)
    with h1:
        frat_date = st.date_input("Date", value=datetime.now().date(), key="frat_date")
    with h2:
        pilot = st.selectbox("Pilot", PILOTS, key="frat_pilot")
    with h3:
        aircraft = st.selectbox("Aircraft", FRAT_AIRCRAFT, index=default_aircraft_idx, key=f"frat_aircraft_{default_aircraft_idx}")
    route_job = st.text_input("Route or job", key="frat_route")
    st.caption(f"Operation: **{part}**" + (f" · Passengers: **{pax}** (from configuration)" if part == "Part 135" else ""))

    factors = CORE_FACTORS + PART_FACTORS[part]
    scores = {}
    section = None
    for key, sec, label, default in factors:
        if sec != section:
            st.markdown(f"**{sec}**")
            section = sec
        if key == "da_performance" and da_hint is not None:
            st.caption(f"ℹ️ Density altitude from calculator: {da_hint:.0f} ft")
        if key == "passengers" and pax == 0:
            st.caption("No passengers entered – score 0 unless special considerations apply.")
        scores[key] = st.slider(label, min_value=0, max_value=10, value=default, step=1, key=f"frat_{part}_{key}")
    total_risk = sum(scores.values())
    frat_max = 10 * len(factors)

    st.markdown("**Stop Items** – any *No* is a NO-GO regardless of score")
    stops = {}
    for key, label in PART_STOPS[part]:
        if key == "stop_pax_brief" and pax == 0:
            stops[key] = "N/A"
            continue
        ans = st.radio(label, ["Yes", "No"], index=None, horizontal=True, key=f"frat_{part}_{key}")
        stops[key] = ans if ans else ""
    stop_failed = any(v == "No" for v in stops.values())
    stops_incomplete = any(v == "" for v in stops.values())

    st.markdown("---")
    risk_percent = total_risk / frat_max * 100
    cut = RISK_CUTOFFS[part]
    if total_risk <= cut["low_max"]:
        level, color, emoji = "Low Risk", "#4CAF50", "🟢"
    elif total_risk <= cut["med_max"]:
        level, color, emoji = "Medium Risk", "#FF9800", "🟡"
    else:
        level, color, emoji = "High Risk", "#F44336", "🔴"
    gauge_html = f"""
    <div style="text-align:center; margin: 30px 0;">
        <div style="width: 220px; height: 220px; border-radius: 50%; background: conic-gradient({color} {risk_percent}%, #e0e0e0 {risk_percent}% 100%); display: flex; align-items: center; justify-content: center; margin: 0 auto; position: relative; box-shadow: 0 6px 20px rgba(0,0,0,0.2);">
            <div style="width: 170px; height: 170px; background: white; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: inset 0 4px 10px rgba(0,0,0,0.1);">
                <div style="font-size: 48px; font-weight: bold; color: {color};">{risk_percent:.0f}%</div>
                <div style="font-size: 18px; color: #555;">{level}</div>
            </div>
        </div>
        <div style="margin-top: 15px; font-size: 22px; font-weight: bold; color: {color};">{emoji} {level} – {total_risk} / {frat_max}</div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)

    st.markdown("**Decision & Sign-off**")
    mitigations, approver, approved = "", "", False
    ron_unreachable = False
    if level == "Medium Risk" and not stop_failed:
        mitigations = st.text_area("Mitigations (required for Medium risk)", key=f"frat_{part}_mitigations")
        approver = st.selectbox("Medium-risk approver", APPROVERS, key=f"frat_{part}_approver")
        if approver == DIRECTOR_MAINTENANCE:
            ron_unreachable = st.checkbox("Ron could not be reached (required for Carl to approve)", key=f"frat_{part}_ron_unreachable")
        approved = st.checkbox(f"{approver} approves this flight with the mitigations above", key=f"frat_{part}_approved")
    elif level == "Low Risk" and not stop_failed:
        mitigations = st.text_area("Mitigations (optional)", key=f"frat_{part}_mitigations")
    sig_name = st.selectbox("Pilot signature", PILOTS, index=None, placeholder="Select name", key="frat_sig")
    pilot_accepts = st.checkbox("I have completed this assessment accurately and accept the risk for this flight", key=f"frat_{part}_accept")

    reasons = []
    if stop_failed:
        decision, reasons = "NO-GO", ["Stop item answered No"]
    elif level == "High Risk":
        decision, reasons = "NO-GO", ["High risk cannot be accepted – re-plan or cancel"]
    else:
        if stops_incomplete:
            reasons.append("Answer all stop items")
        if level == "Medium Risk":
            if not mitigations.strip():
                reasons.append("Enter mitigations")
            if not (approved and approver in APPROVERS):
                reasons.append("Medium-risk approval required")
            if approver == DIRECTOR_MAINTENANCE and not ron_unreachable:
                reasons.append("Confirm Ron could not be reached before Carl approves")
        if not (pilot_accepts and (sig_name or "").strip()):
            reasons.append("Pilot signature and acceptance required")
        if (sig_name or "").strip() and (sig_name or "").strip().lower() != pilot.lower():
            reasons.append("Signature must match selected pilot")
        decision = "INCOMPLETE" if reasons else "GO"

    if decision == "GO":
        st.markdown(f"""<div style="background:#4CAF50; color:white; padding:18px; text-align:center; font-size:26px; font-weight:bold; border-radius:8px;">✅ GO – {part} – {level} accepted</div>""", unsafe_allow_html=True)
    elif decision == "NO-GO":
        st.markdown(f"""<div style="background:#F44336; color:white; padding:18px; text-align:center; font-size:26px; font-weight:bold; border-radius:8px;">⛔ NO-GO – {'; '.join(reasons)}</div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style="background:#FFC107; color:black; padding:18px; text-align:center; font-size:20px; font-weight:bold; border-radius:8px;">⚠️ NOT RELEASED – {'; '.join(reasons)}</div>""", unsafe_allow_html=True)

    st.caption("NO-GO assessments should also be saved – they are part of the safety record.")
    signoff_complete = pilot_accepts and sig_name == pilot
    if not signoff_complete:
        st.caption("Select the matching pilot signature and check the attestation before saving, including NO-GO records.")
    if st.button("💾 Save Assessment", type="primary", use_container_width=True, disabled=(decision == "INCOMPLETE" or not signoff_complete), key=f"frat_{part}_save"):
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date": frat_date.isoformat(), "part": part, "pilot": pilot,
            "aircraft": aircraft.split(" – ")[0], "route_job": route_job,
            **{k: v for k, v in config.items() if k in CONFIG_FIELDS},
            **scores, **stops,
            "total": total_risk, "max_total": frat_max, "percent": f"{risk_percent:.0f}",
            "risk_level": level, "mitigations": mitigations, "approver": approver if approved else "",
            "approved": "Yes" if approved else "No", "pilot_signature": sig_name, "decision": decision,
            "ron_unreachable": "Yes" if ron_unreachable else "No",
            "pilot_attests": "Yes" if pilot_accepts else "No",
        }
        try:
            where = save_frat_record(record)
            st.success(f"Assessment saved to {where}.")
        except Exception as e:
            st.error(PAPER_BACKUP)
            st.caption("Check Streamlit Secrets, live Sheet sharing, connectivity and worksheet headers. Verify the last row before retrying to avoid duplicates.")

def show_frat_history():
    st.subheader("FRAT History")
    try:
        df = load_frat_records()
    except Exception as e:
        st.error(f"Could not load records: {e}")
        return
    if df.empty:
        st.info("No assessments saved yet.")
        return
    part_filter = st.multiselect("Filter by part", PARTS, default=PARTS, key="hist_part_filter")
    if "part" in df.columns:
        df = df[df["part"].isin(part_filter)]
    st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode(), file_name=f"cvh_frat_log_{datetime.now():%Y%m%d}.csv", mime="text/csv")
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
    if "far_part" not in st.session_state:
        st.session_state.far_part = "Part 135"
    sel = st.segmented_control("Operation (FAR Part)", PARTS, default=st.session_state.far_part, key="far_part_ctrl")
    if sel:
        st.session_state.far_part = sel
    part = st.session_state.far_part
    selected_aircraft = st.selectbox("Select Aircraft", list(AIRCRAFT_DATA.keys()))
    aircraft_data = AIRCRAFT_DATA[selected_aircraft]
    st.subheader(f"Aircraft Configuration – {part}")
    pressure_alt = st.number_input("Pressure Altitude (ft)", value=0, step=100)
    oat_c = st.number_input("Outside Air Temperature (°C)", value=15, step=1)
    pilot_weight = st.number_input("Pilot Weight (lbs)", value=200, step=10)
    fuel_gal = st.number_input("Fuel (gal)", value=30, step=5)
    config = {"pilot_weight": pilot_weight, "fuel_gal": fuel_gal}
    payload_weight = 0
    hook_limit = None
    ext_total = 0
    if part == "Part 91":
        pax_bag = st.number_input("Passenger/baggage weight (optional, lbs)", value=0, step=10, min_value=0)
        payload_weight = pax_bag
        config["pax_weight"] = pax_bag
    elif part == "Part 135":
        max_pax = MAX_PAX[selected_aircraft]
        st.caption(f"Max passengers for {selected_aircraft}: {max_pax} (confirm with Ron)")
        pax_count = st.number_input("Number of passengers", min_value=0, max_value=max_pax, value=0, step=1)
        pax_mode = st.radio("Passenger weights", ["Total", "Individual"], horizontal=True)
        if pax_mode == "Individual" and pax_count > 0:
            pcols = st.columns(int(pax_count))
            pax_weight = sum(pcols[i].number_input(f"Pax {i+1} (lbs)", value=170, step=5, min_value=0, key=f"pax_w_{i}") for i in range(int(pax_count)))
        else:
            pax_weight = st.number_input("Total passenger weight (lbs)", value=0, step=10, min_value=0)
        baggage = st.number_input("Baggage weight (lbs)", value=0, step=5, min_value=0)
        payload_weight = pax_weight + baggage
        config.update({"pax_count": pax_count, "pax_weight": pax_weight, "baggage_weight": baggage})
    elif part == "Part 137":
        st.info("Part 137: no non-crew passengers may be carried (§137.35/§137.41 – crew members essential to the operation only).")
        hopper_gal = st.number_input("Hopper / Spray load (gal)", value=0, step=5, min_value=0)
        density = st.number_input("Product density (lb/gal)", value=8.34, step=0.01, format="%.2f")
        payload_weight = hopper_gal * density
        st.caption(f"Hopper load weight: {payload_weight:.0f} lbs (hopper capacity {aircraft_data['hopper_capacity_gal']} gal)")
        if hopper_gal > aircraft_data["hopper_capacity_gal"]:
            st.warning("Hopper load exceeds listed hopper capacity.")
        config.update({"hopper_gal": hopper_gal, "product_density": density})
    elif part == "Part 133":
        st.info("Part 133: no passengers. External load weight is limited by the RFM cargo hook limit – enter it from the RFM/supplement.")
        hook_equip = st.number_input("Hook/equipment weight carried internally (lbs)", value=0, step=5, min_value=0)
        ext_load = st.number_input("External load weight (lbs)", value=0, step=10, min_value=0)
        longline = st.number_input("Longline length (ft)", value=0, step=10, min_value=0)
        hook_limit = st.number_input("Hook limit (lbs) [confirm hook limit from RFM]", value=0, step=10, min_value=0)
        payload_weight = hook_equip
        ext_total = ext_load
        config.update({"hook_equip_weight": hook_equip, "ext_load_weight": ext_load, "longline_ft": longline, "hook_limit": hook_limit})
    da_ft = calculate_density_altitude(pressure_alt, oat_c)
    st.metric("Density Altitude", f"{da_ft:.0f} ft")
    fuel_weight = fuel_gal * aircraft_data["fuel_weight_per_gal"]
    total_weight = aircraft_data["base_empty_weight_lbs"] + pilot_weight + fuel_weight + payload_weight
    st.metric("Total Internal Weight" if part == "Part 133" else "Total Weight", f"{total_weight:.0f} lbs")
    max_gw = aircraft_data["max_takeoff_weight_lbs"]
    if total_weight > max_gw:
        st.error(f"⚠️ OVER MAX GROSS WEIGHT: {total_weight:.0f} lbs exceeds {max_gw} lbs by {total_weight - max_gw:.0f} lbs. Reduce fuel or load.")
    else:
        st.caption(f"Max gross weight {max_gw} lbs – margin {max_gw - total_weight:.0f} lbs")
    if part == "Part 133":
        if not hook_limit:
            st.warning("Enter the hook limit from the RFM [confirm hook limit] to check the external load.")
        elif ext_total > hook_limit:
            st.error(f"⚠️ EXTERNAL LOAD {ext_total:.0f} lbs EXCEEDS HOOK LIMIT {hook_limit:.0f} lbs.")
        else:
            st.caption(f"External load {ext_total:.0f} lbs within hook limit {hook_limit:.0f} lbs")
    config.update({"density_altitude": round(da_ft), "internal_weight": round(total_weight), "max_gross": max_gw})
    st.subheader("Performance Results")
    perf_weight = total_weight + ext_total
    if part == "Part 133":
        st.caption("Performance below includes the external load.")
    climb_rate = compute_climb_rate(pressure_alt, oat_c, perf_weight, selected_aircraft)
    ige, oge = compute_hover_ceiling(da_ft, perf_weight, selected_aircraft)
    st.metric("Climb Rate", f"{climb_rate:.0f} fpm")
    st.metric("IGE Hover Ceiling", f"{ige:.0f} ft")
    st.metric("OGE Hover Ceiling", f"{oge:.0f} ft")
    frat_tab, hist_tab = st.tabs(["📋 FRAT", "🗂️ FRAT History"])
    with frat_tab:
        show_risk_assessment(part, config, da_hint=da_ft, default_aircraft_idx=0 if selected_aircraft.startswith("Robinson") else 1)
    with hist_tab:
        show_frat_history()


# ────────────────────────────────────────────────
# Driver Mode
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
        "Heli4": {"empty": 17290, "gvw": 32000, "truck_fuel_max": 670, "heli_fuel_max": 780},
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
        truck_front_delta = truck_fuel_weight * 0.65
        truck_drive_delta = truck_fuel_weight * 0.35
        heli_front_delta = heli_fuel_weight * (-0.20)
        heli_drive_delta = heli_fuel_weight * 0.80
        added_water = st.session_state.get("last_max_water_gal", 0) * 8.34 if st.session_state.get("last_max_water_gal", 0) > 0 else 0
        extra_weight = added_water + product_weight + rear_weight
        extra_front_delta = extra_weight * 0.22
        extra_drive_delta = extra_weight * 0.78
        front_loaded = base_front + truck_front_delta + heli_front_delta + extra_front_delta
        drive1_loaded = base_drive1 + (truck_drive_delta * 0.5) + (heli_drive_delta * 0.5) + (extra_drive_delta * 0.5)
        drive2_loaded = base_drive2 + (truck_drive_delta * 0.5) + (heli_drive_delta * 0.5) + (extra_drive_delta * 0.5)
        tag_loaded = base_tag + (extra_weight * 0.2 if tag_down else 0)
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

    # ────────────────────────────────────────────────
    # CHECKLISTS – ALL WORKING (including Survey)
    # ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Saved Job Type Checklists")
    checklist_type = st.selectbox(
        "Select Job Type Checklist",
        ["Forestry", "Mt. Vernon", "Seeding", "Local Spraying", "BNSF", "Survey"],
        help="Load your pre-defined checklist for this job"
    )

    with st.expander(f"✅ {checklist_type} Checklist", expanded=True):
        
        if checklist_type == "Survey":
            st.checkbox("Fuel for Aircraft/Vehicle – Full")
            st.checkbox("Fuel Filter / Aircraft tanks & Vehicle – 1 each")
            st.checkbox("Covers for Aircraft, Wheels, Blade Tie Downs")
            st.checkbox("Oil: Aircraft/Vehicle – 4 each")
            st.checkbox("Radios & Chargers – 2 each")
            st.checkbox("Plexus & White Cloth Rags – 1 & 6")
            st.checkbox("Portable Tool Box – Full")
            st.checkbox("Hearing Protection – 1")
            st.checkbox("Gloves (Fuel & Work) – 1 each")
            st.checkbox("Battery Start Pack (24 volt) – 1")
            st.checkbox("Jumper Cables – 1")
            st.checkbox("Jump Box (12 volt) – 1")
            st.checkbox("Drinking Water – 6")
            st.checkbox("Grease Gun & Grease (480 t/r AeroShell) – 1 each")
            st.checkbox("Cell Phones & Chargers – 1 each")
            st.checkbox("Six-Outlet Surge Protector – 1")
            st.checkbox("Paper Towels – 1 Roll")
            st.checkbox("Red Devil Heater / Propane Bottle Half to Full / Heating Hose – 1 each")
            st.checkbox("Ladder – 1")
            st.checkbox("50' Extension Cord – 1")

        elif checklist_type == "Forestry":
            st.checkbox("Fuel: Aircraft / Vehicle / 2-Gal Fuel Can for Pump (1 per truck) – Full")
            st.checkbox("Oil: Aircraft & Vehicle – 4 qt. ea.")
            st.checkbox("Fuel Filters: Aircraft & Vehicle – 1 each")
            st.checkbox("Portable Tool Box – Full")
            st.checkbox("Torque Wrenches – 2")
            st.checkbox("Radios w headsets & Chargers – 3")
            st.checkbox("Six-Outlet Surge Protector – 1")
            st.checkbox("Covers for Aircraft: Bubble / Head / Tail Rotor – 3")
            st.checkbox("Wheels for Aircraft – 2")
            st.checkbox("Hearing Protection – 2")
            st.checkbox("Gloves: Chemical & Work / Mix Coats – 4 each")
            st.checkbox("Tire chains / per Helitruck – 1 set")
            st.checkbox("Battery Start Pack (24 volt) – 1")
            st.checkbox("Jumper Cables – 1")
            st.checkbox("Jump Box (12 volt) – 1")
            st.checkbox("Battery Charger (12 volt) – 1")
            st.checkbox("Grease Gun & Grease (480 t/r Aeroshell) – 1 each")
            st.checkbox("Plexus & White Cloth Rags – 1 & 1 pack")
            st.checkbox("Paper Towels – 1 Roll")
            st.checkbox("Drinking Water – 12")
            st.checkbox("Dry Brake & Load Hoses & suction screen / per truck – 1 each")
            st.checkbox("Cell Phones & Chargers – 1 each")
            st.checkbox("Pilot Gel Cushions – 2")
            st.checkbox("ELD, iPad – 1 each")
            st.checkbox("Spill Kit per truck – Full")
            st.checkbox("Extra Spray Nozzle Parts – All")
            st.checkbox("Extra Pull Rope & Spark Plug for Pumps – 1 each")
            st.checkbox("Load Secured Properly – All")
            st.checkbox("Pre-Check Vehicles: Lights/Wipers/Heat/Horn/Tires-Air Pressure – All")
            st.checkbox("Fire Extinguisher: HeliTruck & Aircraft – 2 each & 1")
            st.checkbox("Triangles / per truck – 1 set")
            st.checkbox("Ice Scraper – 1")
            st.checkbox("Drill – 1")
            st.checkbox("Di-electrical grease (Check Jet Fuel electrical connections) – 1")

        elif checklist_type == "Mt. Vernon":
            st.checkbox("Fuel: Aircraft / Vehicle / 2-Gal Fuel Can for Pump – Full")
            st.checkbox("Oil: Aircraft & Vehicle – 4 qt. ea.")
            st.checkbox("Fuel Filters: Aircraft & Vehicle – 1 each")
            st.checkbox("Portable Tool Box – Full")
            st.checkbox("Torque Wrenches – 2")
            st.checkbox("Radios & Chargers – 2")
            st.checkbox("Six-Outlet Surge Protector – 1")
            st.checkbox("Covers for Aircraft: Bubble / Head / Tail Rotor – 3")
            st.checkbox("Wheels for Aircraft – 2")
            st.checkbox("Hearing Protection – 2")
            st.checkbox("Gloves: Chemical & Work – 1 each")
            st.checkbox("Battery Start Pack (24 volt) – 1")
            st.checkbox("Jumper Cables – 1")
            st.checkbox("Jump Box (12 volt) – 1")
            st.checkbox("Battery Charger (12 volt) – 1")
            st.checkbox("Grease Gun & Grease (480 t/r Aeroshell) – 1 each")
            st.checkbox("Plexus & White Cloth Rags – 1 & 6")
            st.checkbox("Paper Towels – 1 Roll")
            st.checkbox("Extra Fuel Tank & Filter (As Needed) – 1 each")
            st.checkbox("Drinking Water – 12")
            st.checkbox("Fill Tanker with Water & Chemical as Required – Full")
            st.checkbox("Dry Brake / Load Hoses – 1 & 2")
            st.checkbox("Cell Phones & Chargers – 1 each")
            st.checkbox("Pilot Gel Cushions – 2")
            st.checkbox("Red Devil Heater / Propane Bottle Half to Full – 1 each")
            st.checkbox("ELD, iPad – 1")
            st.checkbox("Spill Kit – Full")
            st.checkbox("Extra Spray Nozzle Parts – All")
            st.checkbox("Extra Pull Rope & Spark Plug for Pumps – 1 each")
            st.checkbox("Load Secured Properly – All")
            st.checkbox("Pre-Check Vehicles: Lights/Wipers/Heat/Horn/Tires-Air Pressure – All")
            st.checkbox("Winter Chains – 2")
            st.checkbox("Fire Extinguisher: HeliTruck & Aircraft – 2 & 1")
            st.checkbox("Triangles – 1 set")
            st.checkbox("Ice Scraper – 1")
            st.checkbox("Drill – 1")
            st.checkbox("Di-electrical grease (Check Jet Fuel electrical connections) – 1")
            st.checkbox("Temp Gun – 1")
            st.checkbox("Wind Meter – 1")

        elif checklist_type == "BNSF":
            st.checkbox("Confirm proximity to BNSF rail line")
            st.checkbox("Verify no spraying over or near railroad tracks")
            st.checkbox("Check BNSF specific safety protocols")
            st.checkbox("Confirm altitude and swath width for BNSF area")
            st.checkbox("Verify no drift risk to rail corridor")
            st.checkbox("Load Secured Properly – All")
            st.checkbox("Pre-Check Vehicles – All")
            st.checkbox("Fire Extinguisher – Checked")
            st.checkbox("Spill Kit – Full")

        elif checklist_type in ["Seeding", "Local Spraying"]:
            st.checkbox("Load Secured Properly – All")
            st.checkbox("Pre-Check Vehicles – All")
            st.checkbox("Fire Extinguisher – Checked")
            st.checkbox("Spill Kit – Full")
            if checklist_type == "Seeding":
                st.checkbox("Check seed hopper calibration and rate")
                st.checkbox("Verify seed type and quantity")
            else:
                st.checkbox("Verify local spraying permits")
                st.checkbox("Confirm spray mixture and rate for local job")
                st.checkbox("Check for buffer zones and no-drift requirements")

        # Mark as completed button (works for all checklists)
        if st.button(f"✅ Mark {checklist_type} Checklist as Completed"):
            st.success(f"✅ {checklist_type} Checklist completed and logged!")
            if 'completed_checklists' not in st.session_state:
                st.session_state.completed_checklists = []
            st.session_state.completed_checklists.append(f"{checklist_type} – {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Show completed checklists
    if st.session_state.get('completed_checklists'):
        st.subheader("Completed Checklists")
        for item in st.session_state.completed_checklists:
            st.success(item) 

# ────────────────────────────────────────────────
# EMERGENCY CHECKLIST
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Emergency":
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

