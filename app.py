from PIL import Image
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime, date, time as dt_time, timedelta
import uuid
from zoneinfo import ZoneInfo

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

# CVH Logo and header navigation (logo left, header buttons right)
LOGO_URL = "flaglogo.png"
HEADER_PAGES = ["Monthly Safety Meeting", "Yearly Items", "Equipment", "DOM", "EMPLOYEES"]

# Button Colors and compact wrapping header buttons for phones
st.markdown("""
<style>
    .stButton button[data-baseweb="button"][kind="primary"] { background-color: #007BFF !important; color: white !important; } /* Blue - Pilot / active header */
    .stButton button[data-baseweb="button"][kind="secondary"] { background-color: #FFC107 !important; color: black !important; } /* Yellow - Driver */
    .stButton button[data-baseweb="button"][kind="tertiary"] { background-color: #DC3545 !important; color: white !important; } /* Red - Emergency */
    .stButton button { white-space: normal; line-height: 1.15; height: auto; min-height: 2.75rem; }
    /* Keep the flag logo and the header buttons on one row on phones. */
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img),
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img) [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 0.35rem !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img) div {
        min-width: 0 !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img) [data-testid="stHorizontalBlock"] > div {
        flex: 1 1 0 !important;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img) {
        overflow: hidden;
    }
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has(img) .stButton button {
        font-size: 0.75rem;
        min-height: 2.35rem;
        padding: 0.25rem 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

if "current_mode" not in st.session_state:
    st.session_state.current_mode = "Pilot"

header_left, header_right = st.columns([0.9, 2.1])
with header_left:
    try:
        st.image(LOGO_URL, width=110)
        st.logo(LOGO_URL, size="medium")
    except Exception:
        st.markdown("### CVH Employee Tool ⌯✈︎")
with header_right:
    def _header_btn(label, page, key):
        active = st.session_state.current_mode == page
        # type="primary" (blue) for all header buttons so inactive ones are not Driver-yellow.
        shown = ("● " + label) if active else label
        if st.button(shown, key=key, use_container_width=True, type="primary"):
            st.session_state.current_mode = page
            if page == "EMPLOYEES":
                st.session_state.employees_selected = None
                st.session_state.employees_show_calendar = False
            st.rerun()
    hr1, hr2 = st.columns(2)
    with hr1:
        _header_btn("Monthly Safety Meeting", "Monthly Safety Meeting", "nav_monthly_safety")
    with hr2:
        _header_btn("Yearly Items", "Yearly Items", "nav_yearly_items")
    hr3, hr4, hr5 = st.columns(3)
    with hr3:
        _header_btn("Equipment", "Equipment", "nav_equipment")
    with hr4:
        _header_btn("DOM", "DOM", "nav_dom")
    with hr5:
        _header_btn("EMPLOYEES", "EMPLOYEES", "nav_employees")

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

def frat_sheet_url():
    """Public edit link for the live FRAT log (from secrets or default id)."""
    sid = None
    try:
        sid = st.secrets.get("frat_sheet_id")
    except Exception:
        sid = None
    sid = sid or "1lLDnTMbyZ0JPs8m9I41MX6KsTMCZX8Gl7mVGN92M4E4"
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"

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
    ("pilot_exp", "Daily Pilot Factors", "Recent experience/currency (hours last 30 days – per flight log)", 0),
    ("pilot_fatigue", "Daily Pilot Factors", "Fatigue/sleep last 24 hours", 0),
    ("pilot_health", "Daily Pilot Factors", "Physical/mental health today", 0),
    ("ac_maintenance", "Aircraft Factors", "Maintenance status/known squawks", 0),
    ("ac_fuel", "Aircraft Factors", "Fuel planning/reserves", 0),
    ("ac_weight", "Aircraft Factors", "Weight & balance/CG within limits", 0),
    ("da_performance", "Aircraft Factors", "Density altitude / performance margin (hover OGE/IGE)", 0),
    ("weather_ceiling", "Environment / Weather", "Ceiling/visibility (VFR/IFR conditions)", 0),
    ("weather_turb", "Environment / Weather", "Turbulence/icing/wind forecast", 0),
    ("weather_notams", "Environment / Weather", "NOTAMs/TFRs/airspace restrictions", 0),
    ("terrain", "Environment / Weather", "Terrain / unfamiliar area", 0),
    ("flight_complexity", "Operations / Flight Plan", "Flight complexity (obstructions/towers/wires/slacklines/birds)", 0),
    ("alternate_plan", "Operations / Flight Plan", "Alternate/emergency options planned", 0),
    ("night_ops", "Operations / Flight Plan", "Night or low-light operations", 0),
    ("get_there_itis", "External Pressures", "Get-there-itis/schedule pressure", 0),
    ("customer_pressure", "External Pressures", "Customer/family/operational pressure", 0),
]
PART_FACTORS = {
    "Part 91": [],
    "Part 135": [
        ("landing_zone", "Part 135 Factors", "Landing zone (unimproved / unfamiliar / confined)", 0),
        ("passengers", "Part 135 Factors", "Passengers (number, weights, special needs)", 0),
    ],
    "Part 137": [
        ("ag_wires_field", "Part 137 Factors", "Wires/slacklines/towers in and around the field", 0),
        ("ag_drift_wind", "Part 137 Factors", "Drift / wind / temperature inversion", 0),
        ("ag_chemical", "Part 137 Factors", "Chemical hazard / label restrictions", 0),
        ("ag_sensitive", "Part 137 Factors", "Sensitive areas / buffers (homes, schools, water, organic crops, bees)", 0),
        ("ag_ferry", "Part 137 Factors", "Ferry distance to field", 0),
    ],
    "Part 133": [
        ("ext_load_char", "Part 133 Factors", "Load characteristics (shape / oscillation risk)", 0),
        ("ext_site", "Part 133 Factors", "Pickup/setdown site (confined, rotor-wash debris)", 0),
        ("ext_ground_crew", "Part 133 Factors", "Ground crew experience and communications", 0),
        ("ext_wires_path", "Part 133 Factors", "Wires along load path", 0),
        ("ext_populated", "Part 133 Factors", "Populated area along route", 0),
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

def _gsheets_spreadsheet():
    """Open the production spreadsheet; does not select or modify a worksheet."""
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Google Sheets service account is not configured")
    import gspread
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    sheet_id = st.secrets.get("frat_sheet_id")
    return (gc.open_by_key(sheet_id) if sheet_id else
            gc.open(st.secrets.get("frat_sheet_name") or FRAT_SHEET_NAME))


def _gsheets_worksheet():
    """Open the production FRAT worksheet (sheet1); configuration and network failures propagate."""
    return _gsheets_spreadsheet().sheet1


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
# Equipment squawks (same spreadsheet, separate tabs; never writes the FRAT sheet)
# ────────────────────────────────────────────────
EQUIPMENT_SHEET_TITLE = "Equipment"
SQUAWKS_SHEET_TITLE = "Squawks"
SAFETY_MEETINGS_SHEET_TITLE = "Safety Meetings"
# Add a string here to show another checklist item on the Monthly Safety Meeting form.
SAFETY_MEETING_ITEMS = [
    "Aircraft Fire Extinguishers",
    "Review Equipment",
    "Review Employee Licenses / Certificates",
    "First Aid Kits",
    "PPE",
]
# Add a name here to show another attendee checkbox on the Monthly Safety Meeting form.
SAFETY_MEETING_ATTENDEES = [
    "Ron Cline",
    "Anthony Root",
    "Carl Mulvaney",
    "Barry Markham",
    "Gary Grant",
    "Robert Rackley",
    "Skylar Fingerle",
]
AIRCRAFT_MAINT_SHEET_TITLE = "Aircraft Maint"
AIRCRAFT_MAINT_COLUMNS = [
    "Timestamp", "Aircraft", "Entry Date", "Hobbs",
    "Last 100 Hr", "Next 100 Hr", "Annual Due Date",
    "Last Oil Change", "Next Oil Change", "Entered By",
]
# Add a profile here to enable the Annual/100 Hr form for another aircraft.
# grease_offsets uses a separate N480ML Maint tab so Aircraft Maint headers stay unchanged.
# Ron wrote 25, 50, 25, 100 — the second 25 is treated as 75.
GREASE_CHECKPOINT_OFFSETS = (25, 50, 75, 100)
GREASE_AMBER_HOURS = 2
N480ML_MAINT_SHEET_TITLE = "N480ML Maint"
AIRCRAFT_MAINT_PROFILES = {
    "N893PC": {
        "id": "N893PC",
        "hundred_hr_interval": 100,
        "oil_interval": 50,
        "amber_hours": 10,
        "sheet_title": "Aircraft Maint",
    },
    "N480ML": {
        "id": "N480ML",
        "hundred_hr_interval": 100,
        "amber_hours": 10,
        "grease_amber_hours": GREASE_AMBER_HOURS,
        "grease_offsets": GREASE_CHECKPOINT_OFFSETS,
        "sheet_title": "N480ML Maint",
    },
}
REGISTRATION_EXPIRE_COL = "Registration Expire Date"
ANNUAL_MAINT_COL = "Annual Maint Date"
TONNAGE_APPLIES_COL = "Tonnage Applies"
TONNAGE_EXPIRE_COL = "Tonnage Wt Expire Date"
# Seeded Yes for these six; Ron can change the Tonnage Applies column later.
TONNAGE_DEFAULT_UNITS = ("Heli2", "Heli3", "Heli4", "S1", "C8000", "Boomer")
EQUIPMENT_INFO_COLUMNS = [
    "Year", "Make/Model", "VIN/Serial", "Plate/N-number", "Notes",
    "Registration Expire Date", "Annual Maint Date",
    "Tonnage Applies", "Tonnage Wt Expire Date",
]
EQUIPMENT_COLUMNS = ["Unit ID", "Name", "Type", "Active"] + EQUIPMENT_INFO_COLUMNS
EQUIPMENT_EDIT_COLUMNS = [
    "Type", "Active", "Year", "Make/Model", "VIN/Serial", "Plate/N-number", "Notes",
    "Registration Expire Date", "Annual Maint Date",
    "Tonnage Applies", "Tonnage Wt Expire Date",
]
SQUAWK_COLUMNS = [
    "Timestamp", "Unit ID", "Equipment Name", "Type", "Reported By", "Category",
    "Severity", "Description", "Odometer/Hours", "Status", "Resolved Date",
    "Resolved By", "Notes",
]
EQUIPMENT_TYPES = ["Truck", "Trailer", "Vehicle", "Other"]
SQUAWK_CATEGORIES = ["Mechanical", "Electrical", "Tires", "Body", "Safety", "Other"]
SQUAWK_SEVERITIES = ["Low", "Medium", "Grounded-Do not use"]
SEVERITY_GROUNDED = "Grounded-Do not use"
STATUS_OPEN = "Open"
STATUS_RESOLVED = "Resolved"
REPORTERS = _unique(PILOTS + APPROVERS)
ACTIVE_VALUES = {"", "yes", "y", "true", "1", "active"}


# Ron's equipment list, in this exact order. Type is set only when the name is clearly a trailer.
OFFICIAL_EQUIPMENT_NAMES = [
    "Heli1", "Heli2", "Heli3", "Heli4", "F250", "F350", "PW", "Ram", "FS Truck",
    "C8000", "S1", "Boomer", "Inter Fueler", "Bounder", "Bus", "Equinox", "Tesla", "Mercedes", "Sienna",
    "R44 Trailer", "Enstrom Heli Trailer", "Heli Hauler", "Pod", "Dump Trailer",
    "Fuel Trailer", "Bobcat", "Forklift", "Lift", "JD Tractor", "Grasshopper",
]



# Add a unit ID here to show an IFTA button on the Equipment page, between INFO and Squawk.
IFTA_UNITS = ("Heli2",)
# Drivers for the IFTA Trips form, in Ron's listed order.
# Do not add names here unless Ron authorizes them as drivers.
DRIVERS = [
    "Robert Rackley",
    "Barry Markham",
    "Anthony Root",
    "Carl Mulvaney",
    "Ron Cline",
    "Gary Grant",
]
# Employees page roster, in Ron's listed order. Separate from DRIVERS;
# Skylar Fingerle is not an authorized addition to the driver dropdown.
EMPLOYEES = [
    "Ron Cline",
    "Carl Mulvaney",
    "Anthony Root",
    "Barry Markham",
    "Robert Rackley",
    "Gary Grant",
    "Skylar Fingerle",
]
# Weekly time sheet is only for these employees, in Ron's listed order.
# Official weekly form for these five employees. Ron Cline has no timesheet.
# Anthony Root uses a separate official form (see ANTHONY_TIMESHEET_*) and does
# not get vacation or sick hours on that form.
TIMESHEET_EMPLOYEES = [
    "Carl Mulvaney",
    "Barry Markham",
    "Robert Rackley",
    "Gary Grant",
    "Skylar Fingerle",
]
TIMESHEET_SHEET_TITLE = "Time Sheets"
ANTHONY_TIMESHEET_EMPLOYEE = "Anthony Root"
ANTHONY_TIMESHEET_SHEET_TITLE = "Anthony Time Sheets"
ANTHONY_TIMESHEET_TEMPLATE = "anthony_timesheet_template.xlsx"
ANTHONY_TIMESHEET_DAYS = ("Sun", "Mon", "Tues", "Wed", "Thur", "Fri", "Sat")
# Field keys match the official header labels, including the typo "Survery Hrs".
ANTHONY_TIMESHEET_DAY_FIELDS = (
    ("L&I Ground Hours", "L&I Ground Hours"),
    ("L&I Flight Hours", "L&I Flight Hours"),
    ("Spraying App Acres", "Spraying App Acres"),
    ("Forestry App Acres", "Forestry App Acres"),
    ("BNSF App Acres", "BNSF App Acres"),
    ("Seeding Acres", "Seeding Acres"),
    ("Survery Hrs", "Survery Hrs"),
    ("Standby Hrs", "Standby Hrs"),
    ("Per Diem", "Per Diem"),
    ("Notes", "Notes"),
)
ANTHONY_TIMESHEET_GRID_ROWS = 22  # official template input rows 9-30
ANTHONY_TIMESHEET_WEEK_ROWS = 7
ANTHONY_TIMESHEET_NUMERIC_FIELDS = {
    "L&I Ground Hours", "L&I Flight Hours", "Spraying App Acres",
    "Forestry App Acres", "BNSF App Acres", "Seeding Acres",
    "Survery Hrs", "Standby Hrs",
}
TIMESHEET_DAYS = ("Sun", "Mon", "Tues", "Wed", "Thur", "Fri", "Sat")
# Vacation and Sick sit with the worked-hour rows on the five-person form only.
TIMESHEET_WORKED_HOUR_FIELDS = ("CVH Hours", "Forestry Hours", "BNSF Hours")
TIMESHEET_LEAVE_FIELDS = ("Vacation Hours", "Sick Hours")
TIMESHEET_LEAVE_HOURS_MAX = 24
TIMESHEET_DAY_FIELDS = (
    ("Location", "Location"),
    ("CVH Hours", "CVH # work hours"),
    ("Forestry Hours", "Forestry #  work hours"),
    ("BNSF Hours", "BNSF # work hours"),
    ("Vacation Hours", "Vacation Hours"),
    ("Sick Hours", "Sick Hours"),
    ("Perdiem Rate", "Perdiem Rate"),
    ("Other", "Other"),
)
# Official IRS business standard mileage rates (dollars per mile).
# Source: https://www.irs.gov/tax-professionals/standard-mileage-rates
# Periods and IR notices are copied from that table. Do not invent later rates.
TIMESHEET_IRS_MILEAGE_SOURCE_URL = "https://www.irs.gov/tax-professionals/standard-mileage-rates"
TIMESHEET_IRS_BUSINESS_MILEAGE_RATES = (
    (date(2011, 1, 1), date(2011, 6, 30), 0.51, "IR-2010-119"),
    (date(2011, 7, 1), date(2011, 12, 31), 0.555, "IR-2011-69"),
    (date(2012, 1, 1), date(2012, 12, 31), 0.555, "IRB-2012-02"),
    (date(2013, 1, 1), date(2013, 12, 31), 0.565, "IR-2012-95"),
    (date(2014, 1, 1), date(2014, 12, 31), 0.56, "IR-2013-95"),
    (date(2015, 1, 1), date(2015, 12, 31), 0.575, "IR-2014-114"),
    (date(2016, 1, 1), date(2016, 12, 31), 0.54, "IR-2015-137"),
    (date(2017, 1, 1), date(2017, 12, 31), 0.535, "IR-2016-169"),
    (date(2018, 1, 1), date(2018, 12, 31), 0.545, "IR-2017-204"),
    (date(2019, 1, 1), date(2019, 12, 31), 0.58, "IR-2018-251"),
    (date(2020, 1, 1), date(2020, 12, 31), 0.575, "IR-2019-215"),
    (date(2021, 1, 1), date(2021, 12, 31), 0.56, "IR-2020-279"),
    (date(2022, 1, 1), date(2022, 6, 30), 0.585, "IR-2021-251"),
    (date(2022, 7, 1), date(2022, 12, 31), 0.625, "IR-2022-124"),
    (date(2023, 1, 1), date(2023, 12, 31), 0.655, "IR-2022-234"),
    (date(2024, 1, 1), date(2024, 12, 31), 0.67, "IR-2023-239"),
    (date(2025, 1, 1), date(2025, 12, 31), 0.70, "IR-2024-312"),
    (date(2026, 1, 1), date(2026, 6, 30), 0.725, "IR-2025-128"),
    (date(2026, 7, 1), date(2026, 12, 31), 0.76, "IR-2026-29"),
)
TIMESHEET_IRS_MILEAGE_RATES_START = TIMESHEET_IRS_BUSINESS_MILEAGE_RATES[0][0]
TIMESHEET_IRS_MILEAGE_RATES_END = TIMESHEET_IRS_BUSINESS_MILEAGE_RATES[-1][1]
TIMESHEET_MILEAGE_SHEET_TITLE = "Time Sheet Mileage"
TIMESHEET_MILEAGE_COLUMNS = [
    "Timestamp", "Entry ID", "Action", "Employee", "Week Of",
    "Trip Number", "Travel Date", "Start Location", "End Location",
    "Miles", "Rate", "Amount", "Rate Source", "Status",
]
TIMESHEET_MILEAGE_SOURCE_IRS = "IRS"
TIMESHEET_MILEAGE_SOURCE_COMPANY = "Company override"
TIMESHEET_MILEAGE_SOURCE_SAVED = "Previously saved"
TIMESHEET_EMAIL_TO = "patti@centralvalleyheli.com"
TIME_OFF_SHEET_TITLE = "Time Off"
TIME_OFF_COLUMNS = [
    "Timestamp", "Entry ID", "Action", "Employee", "Type",
    "Start Date", "End Date", "Start Time", "End Time", "Notes", "Status",
    "Project",
]
TIME_OFF_TYPES = ("Full day off", "Partial day", "Vacation", "Project")
TIME_OFF_TYPE_FULL = "Full day off"
TIME_OFF_TYPE_PARTIAL = "Partial day"
TIME_OFF_TYPE_VACATION = "Vacation"
TIME_OFF_TYPE_PROJECT = "Project"
TIME_OFF_PROJECTS = ("BNSF", "Forestry", "WSFW", "West", "Basin", "Other")
TIME_OFF_STATUS_ACTIVE = "Active"
TIME_OFF_STATUS_CANCELLED = "Cancelled"
TIME_OFF_ACTION_CREATE = "Create"
TIME_OFF_ACTION_CANCEL = "Cancel"
TIME_OFF_MAX_PAST_DAYS = 730
TIME_OFF_MAX_FUTURE_DAYS = 730
TIME_OFF_MAX_SPAN_DAYS = 180
IFTA_TRIPS_SHEET_TITLE = "IFTA Trips"
IFTA_FUEL_SHEET_TITLE = "IFTA Fuel"
IFTA_TRIPS_COLUMNS = [
    "Timestamp", "Date", "Unit", "Driver", "Jurisdiction",
    "Start Odometer", "End Odometer", "Miles", "Notes",
]
# Live IFTA Fuel already exists with "Receipt #"; keep that header and store Yes/No in it.
IFTA_RECEIPT_COLUMN = "Receipt #"
IFTA_FUEL_COLUMNS = [
    "Timestamp", "Date", "Unit", "Jurisdiction", "Gallons",
    "Price/Gal", "Total Cost", "Vendor/Location", IFTA_RECEIPT_COLUMN, "Notes",
]
IFTA_DEFAULT_JURISDICTION = "WA"
# IFTA member jurisdictions: 48 contiguous US states and 10 Canadian provinces.
IFTA_JURISDICTIONS = [
    ("AL", "Alabama"), ("AZ", "Arizona"), ("AR", "Arkansas"), ("CA", "California"),
    ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"), ("FL", "Florida"),
    ("GA", "Georgia"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"),
    ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
    ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"),
    ("NE", "Nebraska"), ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"),
    ("NM", "New Mexico"), ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"),
    ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"),
    ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"),
    ("WA", "Washington"), ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
    ("AB", "Alberta"), ("BC", "British Columbia"), ("MB", "Manitoba"),
    ("NB", "New Brunswick"), ("NL", "Newfoundland and Labrador"), ("NS", "Nova Scotia"),
    ("ON", "Ontario"), ("PE", "Prince Edward Island"), ("QC", "Quebec"), ("SK", "Saskatchewan"),
]
IFTA_VIEW_TRIPS = "Trip / Mileage log"
IFTA_VIEW_FUEL = "Fuel purchase log"
IFTA_VIEW_SUMMARY = "Quarterly summary"

def official_equipment_rows():
    """Unit ID and Name are the official names; Type is Trailer only when obvious.

    Info and date columns are left blank — do not invent Year, Make/Model, VIN, plate, notes, or dates.
    Tonnage Applies is Yes only for the six units Ron named; Tonnage Wt Expire Date stays blank.
    """
    rows = []
    for name in OFFICIAL_EQUIPMENT_NAMES:
        record = {col: "" for col in EQUIPMENT_COLUMNS}
        record["Unit ID"] = name
        record["Name"] = name
        record["Type"] = "Trailer" if "Trailer" in name else ""
        record["Active"] = "Yes"
        if name in TONNAGE_DEFAULT_UNITS:
            record[TONNAGE_APPLIES_COL] = "Yes"
        rows.append([record[col] for col in EQUIPMENT_COLUMNS])
    return rows


def is_placeholder_equipment_seed(records):
    """True when the tab still has the temporary placeholder seed, so it can be replaced."""
    if not records:
        return False
    for record in records:
        unit_id = _cell(record.get("Unit ID"))
        name = _cell(record.get("Name"))
        if "(placeholder)" in name or unit_id.startswith(("TRK-", "TRL-", "CAR-", "OTH-")):
            continue
        return False
    return True


def _cell(value):
    return str(value or "").strip()


def parse_equipment_date(value):
    """Parse a date entered on the Equipment tab. Blank stays blank; unparseable is ignored."""
    text_value = _cell(value)
    if not text_value:
        return None
    from datetime import date, datetime, timedelta  # local import safe if already imported
    text_value = text_value.replace(".", "/").replace("-", "/")
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text_value, fmt).date()
        except ValueError:
            continue
    # ISO dates that used hyphen (already swapped to /) are covered; try original hyphen ISO too.
    try:
        return date.fromisoformat(_cell(value)[:10])
    except ValueError:
        return None


def format_equipment_date(value):
    """Store dates as YYYY-MM-DD; blank stays blank."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    parsed = parse_equipment_date(value)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")
    return _cell(value)


def registration_due_date(unit):
    return parse_equipment_date(unit.get(REGISTRATION_EXPIRE_COL))


def tonnage_applies(unit):
    """Sheet flag controls whether Tonnage Wt Expire Date is shown. Default seed is Yes for six units."""
    flag = _cell(unit.get(TONNAGE_APPLIES_COL)).lower()
    return flag in {"yes", "y", "true", "1"}


def tonnage_due_date(unit):
    if not tonnage_applies(unit):
        return None
    return parse_equipment_date(unit.get(TONNAGE_EXPIRE_COL))


def annual_maint_due_date(unit):
    """Due date is one year after the Annual Maint Date."""
    performed = parse_equipment_date(unit.get(ANNUAL_MAINT_COL))
    if performed is None:
        return None
    try:
        return performed.replace(year=performed.year + 1)
    except ValueError:
        # Feb 29 -> Feb 28 the following year
        return performed.replace(year=performed.year + 1, day=28)


DATE_STATUS_COLORS = {
    "expired": "#b91c1c",
    "soon": "#b45309",
    "ok": "#15803d",
    None: "#6b7280",
}


def date_flag(due, today=None):
    """'expired' if past, 'soon' if within 30 days, 'ok' if later; None when the date is blank."""
    if due is None:
        return None
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    if due < today:
        return "expired"
    if (due - today).days <= 30:
        return "soon"
    return "ok"


def date_flag_label(kind, due, label):
    if kind == "expired":
        return label + " expired " + due.strftime("%Y-%m-%d")
    if kind == "soon":
        return label + " due " + due.strftime("%Y-%m-%d")
    if kind == "ok" and due is not None:
        return label + " " + due.strftime("%Y-%m-%d")
    return None


def date_status_markup(label, raw_value, due, today=None, due_note=False):
    """Colored date text: red expired, amber within 30 days, green otherwise, gray 'Not set' if blank."""
    kind = date_flag(due, today)
    if kind is None:
        body = "Not set"
    else:
        shown = due.strftime("%Y-%m-%d")
        raw = _cell(raw_value)
        if due_note:
            body = ((raw + " (due " + shown + ")") if raw else ("due " + shown))
        else:
            body = raw or shown
        if kind == "expired":
            body += " — expired"
        elif kind == "soon":
            body += " — expires within 30 days"
    color = DATE_STATUS_COLORS[kind]
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return kind, "**" + label + ":** <span style='color:" + color + "; font-weight:600'>" + safe + "</span>"


def is_active_equipment(record):
    return _cell(record.get("Active")).lower() in ACTIVE_VALUES


def is_open_squawk(record):
    status = _cell(record.get("Status")) or STATUS_OPEN
    return status.lower() == STATUS_OPEN.lower()


def is_grounded_squawk(record):
    return _cell(record.get("Severity")) == SEVERITY_GROUNDED


def squawks_for(unit_id, squawks):
    """All squawk history for one unit, in sheet order (oldest first)."""
    unit_id = _cell(unit_id)
    return [s for s in squawks if _cell(s.get("Unit ID")) == unit_id]


def open_squawks_for(unit_id, squawks):
    return [s for s in squawks_for(unit_id, squawks) if is_open_squawk(s)]


def equipment_has_grounding(unit_id, squawks):
    return any(is_grounded_squawk(s) for s in open_squawks_for(unit_id, squawks))


def records_from_worksheet(ws, expected_columns):
    """Read rows as dicts keyed by the first-row header; missing columns stay empty."""
    values = ws.get_all_values()
    if not values:
        return []
    header = [_cell(c) for c in values[0]]
    records = []
    for row in values[1:]:
        if not any(_cell(c) for c in row):
            continue
        record = {col: "" for col in expected_columns}
        for idx, col in enumerate(header):
            if col:
                record[col] = _cell(row[idx]) if idx < len(row) else ""
        records.append(record)
    return records


def _worksheet_or_none(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except Exception as exc:
        name = type(exc).__name__
        message = str(exc).lower()
        if name in {"WorksheetNotFound", "NotFound"} or ("worksheet" in message and "not found" in message):
            return None
        raise


def _write_equipment_rows(ws, rows):
    """Replace this tab's values only (never other worksheets)."""
    values = [EQUIPMENT_COLUMNS] + [list(r) for r in rows]
    if hasattr(ws, "clear"):
        ws.clear()
    if hasattr(ws, "update"):
        ws.update("A1", values, value_input_option="RAW")
        return
    # Test doubles that only implement append_row / a rows list.
    if hasattr(ws, "rows"):
        ws.rows = values
        if hasattr(ws, "writes"):
            ws.writes.append(("replace", values))
        return
    for row in values:
        ws.append_row(row, value_input_option="RAW")


def ensure_equipment_worksheet(spreadsheet):
    """Create the Equipment tab, or replace a leftover placeholder seed, with Ron's list."""
    ws = _worksheet_or_none(spreadsheet, EQUIPMENT_SHEET_TITLE)
    created = False
    official = official_equipment_rows()
    if ws is None:
        ws = spreadsheet.add_worksheet(title=EQUIPMENT_SHEET_TITLE, rows=50, cols=len(EQUIPMENT_COLUMNS))
        _write_equipment_rows(ws, official)
        created = True
    else:
        records = records_from_worksheet(ws, EQUIPMENT_COLUMNS)
        header = [_cell(c) for c in ws.row_values(1)]
        if not header or not records or is_placeholder_equipment_seed(records):
            _write_equipment_rows(ws, official)
            created = not records
        else:
            ensure_equipment_info_columns(ws)
    return ws, created


def ensure_equipment_info_columns(ws):
    """Add any missing info-column headers on the right; do not invent or overwrite values."""
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return False
    missing = [col for col in EQUIPMENT_COLUMNS if col not in header]
    if not missing:
        return False
    start = len(header) + 1
    for offset, col in enumerate(missing):
        ws.update_cell(1, start + offset, col)
    return True


def ensure_squawks_worksheet(spreadsheet):
    """Create the Squawks tab with a header only when the tab is missing or has no header."""
    ws = _worksheet_or_none(spreadsheet, SQUAWKS_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=SQUAWKS_SHEET_TITLE, rows=200, cols=len(SQUAWK_COLUMNS))
        ws.append_row(SQUAWK_COLUMNS, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(SQUAWK_COLUMNS, value_input_option="RAW")
            created = True
        elif header != SQUAWK_COLUMNS:
            raise RuntimeError("Squawks worksheet headers do not match this app; check the live sheet")
    return ws, created


def load_equipment_records(spreadsheet=None):
    ws, _created = ensure_equipment_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, EQUIPMENT_COLUMNS)


def load_squawk_records(spreadsheet=None):
    ws, _created = ensure_squawks_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, SQUAWK_COLUMNS)


def build_squawk_record(unit, reported_by, when, category, severity, description, odometer=""):
    description = _cell(description)
    reported_by = _cell(reported_by)
    if not description:
        raise ValueError("A squawk description is required")
    if not reported_by:
        raise ValueError("Reported By is required")
    if category not in SQUAWK_CATEGORIES:
        raise ValueError("Select a squawk category")
    if severity not in SQUAWK_SEVERITIES:
        raise ValueError("Select a squawk severity")
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "Timestamp": stamp,
        "Unit ID": _cell(unit.get("Unit ID")),
        "Equipment Name": _cell(unit.get("Name")),
        "Type": _cell(unit.get("Type")),
        "Reported By": reported_by,
        "Category": category,
        "Severity": severity,
        "Description": description,
        "Odometer/Hours": _cell(odometer),
        "Status": STATUS_OPEN,
        "Resolved Date": "",
        "Resolved By": "",
        "Notes": "",
    }


def save_squawk_record(record, spreadsheet=None):
    """Append one squawk to the Squawks tab only. Never writes the FRAT worksheet."""
    ws, _created = ensure_squawks_worksheet(spreadsheet or _gsheets_spreadsheet())
    ws.append_row([str(record.get(c, "")) for c in SQUAWK_COLUMNS], value_input_option="RAW")
    return "Google Sheets (Squawks)"


def resolve_squawk(timestamp, unit_id, resolved_by, notes="", when=None, spreadsheet=None):
    """Mark a matching open squawk resolved. Updates only the Squawks tab."""
    resolved_by = _cell(resolved_by)
    if not resolved_by:
        raise ValueError("Resolved By is required")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    ws, _created = ensure_squawks_worksheet(spreadsheet or _gsheets_spreadsheet())
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Squawks worksheet has no header")
    header = [_cell(c) for c in values[0]]
    try:
        status_col = header.index("Status") + 1
        resolved_date_col = header.index("Resolved Date") + 1
        resolved_by_col = header.index("Resolved By") + 1
        notes_col = header.index("Notes") + 1
        ts_idx = header.index("Timestamp")
        unit_idx = header.index("Unit ID")
        status_idx = header.index("Status")
    except ValueError as exc:
        raise RuntimeError("Squawks worksheet headers do not match this app; check the live sheet") from exc
    stamp = _cell(timestamp)
    unit_id = _cell(unit_id)
    for row_number, row in enumerate(values[1:], start=2):
        row_status = _cell(row[status_idx]) if status_idx < len(row) else ""
        if ((_cell(row[ts_idx]) if ts_idx < len(row) else "") == stamp
                and (_cell(row[unit_idx]) if unit_idx < len(row) else "") == unit_id
                and (row_status or STATUS_OPEN).lower() == STATUS_OPEN.lower()):
            ws.update_cell(row_number, status_col, STATUS_RESOLVED)
            ws.update_cell(row_number, resolved_date_col, when.strftime("%Y-%m-%d %H:%M:%S"))
            ws.update_cell(row_number, resolved_by_col, resolved_by)
            if _cell(notes):
                existing = _cell(row[notes_col - 1]) if notes_col - 1 < len(row) else ""
                ws.update_cell(row_number, notes_col, (existing + " " + _cell(notes)).strip() if existing else _cell(notes))
            return True
    raise RuntimeError("Could not find that open squawk on the Squawks tab")


def update_equipment_record(unit_id, fields, spreadsheet=None):
    """Update only this unit's data row on the Equipment tab.

    Finds the row by Unit ID and writes values to matching columns by header
    name. Never writes the FRAT (Sheet1) or Squawks tabs, never changes the
    header row, and never changes Unit ID or Name.
    """
    unit_id = _cell(unit_id)
    if not unit_id:
        raise ValueError("Unit ID is required")
    allowed = set(EQUIPMENT_EDIT_COLUMNS)
    incoming = fields or {}
    updates = {}
    for col, value in incoming.items():
        if col in ("Unit ID", "Name"):
            continue
        if col not in allowed:
            continue
        if col in (REGISTRATION_EXPIRE_COL, ANNUAL_MAINT_COL, TONNAGE_EXPIRE_COL):
            updates[col] = format_equipment_date(value)
        else:
            updates[col] = _cell(value)
    if not updates:
        raise ValueError("No editable equipment fields to save")
    spreadsheet = spreadsheet or _gsheets_spreadsheet()
    ws = _worksheet_or_none(spreadsheet, EQUIPMENT_SHEET_TITLE)
    if ws is None:
        raise RuntimeError("Equipment worksheet not found")
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Equipment worksheet has no header")
    header = [_cell(c) for c in values[0]]
    try:
        unit_idx = header.index("Unit ID")
    except ValueError as exc:
        raise RuntimeError("Equipment worksheet is missing the Unit ID column") from exc
    for row_number, row in enumerate(values[1:], start=2):
        row_id = _cell(row[unit_idx]) if unit_idx < len(row) else ""
        if row_id != unit_id:
            continue
        for col_name, value in updates.items():
            if col_name not in header:
                # Do not invent columns or touch the header row.
                continue
            col_number = header.index(col_name) + 1
            ws.update_cell(row_number, col_number, value)
        return True
    raise RuntimeError("Could not find that unit on the Equipment tab")


def safety_meeting_columns():
    """Header for the Safety Meetings tab. New checklist items append as Done/Note pairs."""
    cols = ["Timestamp", "Meeting Date", "Recorded By", "Attendees"]
    for item in SAFETY_MEETING_ITEMS:
        cols.append(item + " Done")
        cols.append(item + " Note")
    cols.append("Discussion Notes")
    return cols


def _safety_item_key(item):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in item).strip("_")


def ensure_safety_meetings_worksheet(spreadsheet):
    """Create the Safety Meetings tab with a header when it is missing.

    Existing headers are left in place; any newly added item columns are
    appended on the right. Never writes FRAT, Squawks, or Equipment.
    """
    cols = safety_meeting_columns()
    ws = _worksheet_or_none(spreadsheet, SAFETY_MEETINGS_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=SAFETY_MEETINGS_SHEET_TITLE, rows=200, cols=max(len(cols), 8))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
        else:
            missing = [col for col in cols if col not in header]
            if missing:
                start = len(header) + 1
                for offset, col in enumerate(missing):
                    ws.update_cell(1, start + offset, col)
    return ws, created


def load_safety_meeting_records(spreadsheet=None):
    ws, _created = ensure_safety_meetings_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, safety_meeting_columns())


def format_safety_meeting_attendees(selected, other=""):
    """Checked names in list order, then any Other attendees, as a comma-separated string."""
    selected_set = {_cell(name) for name in (selected or [])}
    names = [name for name in SAFETY_MEETING_ATTENDEES if name in selected_set]
    other_text = _cell(other)
    if other_text:
        names.append(other_text)
    return ", ".join(names)


def build_safety_meeting_record(meeting_date, recorded_by, attendees, item_states, discussion, when=None):
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    record = {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Meeting Date": format_equipment_date(meeting_date),
        "Recorded By": _cell(recorded_by),
        "Attendees": _cell(attendees),
        "Discussion Notes": _cell(discussion),
    }
    states = item_states or {}
    for item in SAFETY_MEETING_ITEMS:
        state = states.get(item) or {}
        done = state.get("done")
        if done in (True, "Yes", "yes", "Y", "y", "1", "true", "True"):
            record[item + " Done"] = "Yes"
        else:
            record[item + " Done"] = ""
        record[item + " Note"] = _cell(state.get("note"))
    return record


def save_safety_meeting_record(record, spreadsheet=None):
    """Append one meeting to the Safety Meetings tab only."""
    ws, _created = ensure_safety_meetings_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Safety Meetings worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Safety Meetings)"


def update_safety_meeting_discussion(timestamp, notes, spreadsheet=None, meeting_date=None):
    """Replace Discussion Notes on the matching meeting row only. Never other tabs."""
    timestamp = _cell(timestamp)
    meeting_date = _cell(meeting_date)
    if not timestamp:
        raise ValueError("Timestamp is required")
    ws, _created = ensure_safety_meetings_worksheet(spreadsheet or _gsheets_spreadsheet())
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Safety Meetings worksheet has no header")
    header = [_cell(c) for c in values[0]]
    try:
        ts_idx = header.index("Timestamp")
        notes_col = header.index("Discussion Notes") + 1
    except ValueError as exc:
        raise RuntimeError("Safety Meetings worksheet is missing required columns") from exc
    date_idx = header.index("Meeting Date") if "Meeting Date" in header else None
    matches = []
    for row_number, row in enumerate(values[1:], start=2):
        row_ts = _cell(row[ts_idx]) if ts_idx < len(row) else ""
        if row_ts != timestamp:
            continue
        if meeting_date and date_idx is not None:
            row_date = _cell(row[date_idx]) if date_idx < len(row) else ""
            if row_date != meeting_date:
                continue
        matches.append(row_number)
    if not matches:
        raise RuntimeError("Could not find that meeting on the Safety Meetings tab")
    ws.update_cell(matches[-1], notes_col, _cell(notes))
    return True


def safety_meeting_identity(record):
    """Stable widget/id key for one saved meeting row."""
    parts = [
        _cell((record or {}).get("Timestamp")),
        _cell((record or {}).get("Meeting Date")),
        _cell((record or {}).get("Recorded By")),
        _cell((record or {}).get("Attendees")),
    ]
    return _safety_item_key("|".join(parts)) or "meeting"


def _safety_meeting_sort_key(record):
    """Sort by timestamp, then Meeting Date, so two saves in the same second stay ordered."""
    text_value = _cell(record.get("Timestamp"))
    stamp_dt = datetime.min
    if text_value:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                stamp_dt = datetime.strptime(text_value, fmt)
                break
            except ValueError:
                continue
        else:
            stamp = parse_equipment_date(text_value[:10])
            if stamp is not None:
                stamp_dt = datetime(stamp.year, stamp.month, stamp.day)
    meeting = parse_equipment_date(record.get("Meeting Date"))
    if meeting is not None:
        meeting_dt = datetime(meeting.year, meeting.month, meeting.day)
    else:
        meeting_dt = datetime.min
    return (stamp_dt, meeting_dt)



SAFETY_MEETING_VIEW = "View meetings"
SAFETY_MEETING_RECORD = "Record a meeting"


def safety_meeting_entry_date(record):
    """Meeting Date as a date, or None if it is blank or unparseable."""
    return parse_equipment_date((record or {}).get("Meeting Date"))


def load_safety_meeting_records_readonly(spreadsheet=None):
    """Read the Safety Meetings tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), SAFETY_MEETINGS_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    return records_from_worksheet(ws, safety_meeting_columns())


def safety_meeting_months_with_entries(meetings, year):
    months = set()
    for record in meetings or []:
        entry = safety_meeting_entry_date(record)
        if entry is not None and entry.year == int(year):
            months.add(entry.month)
    return months


def safety_meeting_month_status(year, month, meetings, today=None):
    """'ok' if that month has a saved meeting, 'expired' if a past or current month does not, None if future."""
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    year = int(year)
    month = int(month)
    if month in safety_meeting_months_with_entries(meetings, year):
        return "ok"
    if year > today.year or (year == today.year and month > today.month):
        return None
    return "expired"


def current_month_has_safety_meeting(meetings, today=None):
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return safety_meeting_month_status(today.year, today.month, meetings, today=today) == "ok"


def safety_meeting_header_color(meetings, today=None):
    """Green if this Pacific month has a meeting, red if not."""
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    status = safety_meeting_month_status(today.year, today.month, meetings, today=today)
    return DATE_STATUS_COLORS[status]


def safety_meeting_month_strip_markup(year, meetings, today=None):
    """Phone-friendly Jan–Dec status strip: green has a meeting, red missing, gray future."""
    import calendar
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    parts = [
        '<div class="safety-month-strip" style="display:flex;flex-wrap:wrap;gap:0.35rem;'
        'margin:0.4rem 0 0.7rem 0;">'
    ]
    for month in range(1, 13):
        status = safety_meeting_month_status(year, month, meetings, today=today)
        color = DATE_STATUS_COLORS[status]
        label = calendar.month_abbr[month]
        parts.append(
            '<span style="background:' + color + ';color:#fff;padding:0.3rem 0.5rem;'
            'border-radius:6px;font-weight:600;font-size:0.85rem;line-height:1.2;">'
            + label + "</span>"
        )
    parts.append("</div>")
    return "".join(parts)


def apply_monthly_safety_header_style(spreadsheet=None, today=None):
    """Color the Monthly Safety Meeting header button from the current Pacific month."""
    try:
        meetings = load_safety_meeting_records_readonly(spreadsheet)
        color = safety_meeting_header_color(meetings, today=today)
    except Exception:
        return None
    css = (
        "<style>"
        ".st-key-nav_monthly_safety button,"
        ".st-key-nav_monthly_safety button[data-baseweb='button'][kind='primary'],"
        "[data-testid='stMainBlockContainer'] [data-testid='stHorizontalBlock']:has(img) "
        ".st-key-nav_monthly_safety button{"
        "background-color:" + color + " !important;"
        "color:#ffffff !important;"
        "border-color:" + color + " !important;"
        "}"
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)
    return color



def parse_safety_meeting_attendees(attendees):
    """Split the stored Attendees string into checked names and Other attendees."""
    parts = [p.strip() for p in _cell(attendees).split(",") if p.strip()]
    known = set(SAFETY_MEETING_ATTENDEES)
    checked = [name for name in SAFETY_MEETING_ATTENDEES if name in parts]
    other = ", ".join(part for part in parts if part not in known)
    return checked, other


def safety_meeting_item_done(record, item):
    return _cell((record or {}).get(item + " Done")).lower() in {"yes", "y", "true", "1"}


def filter_safety_meetings(meetings, year=None, month=None):
    """Meetings for an optional year and month, newest first."""
    rows = []
    for record in meetings or []:
        entry = safety_meeting_entry_date(record)
        if year is not None and (entry is None or entry.year != int(year)):
            continue
        if month is not None and (entry is None or entry.month != int(month)):
            continue
        rows.append(record)
    return sorted(rows, key=_safety_meeting_sort_key, reverse=True)


def safety_meeting_years(meetings):
    years = {entry.year for entry in (safety_meeting_entry_date(m) for m in meetings or []) if entry}
    return sorted(years, reverse=True)


def safety_meeting_months_for_year(meetings, year):
    months = {
        entry.month
        for entry in (safety_meeting_entry_date(m) for m in meetings or [])
        if entry and year is not None and entry.year == int(year)
    }
    return sorted(months)


def safety_meeting_option_label(record, include_time=False):
    date_text = _cell((record or {}).get("Meeting Date")) or "Meeting"
    recorded = _cell((record or {}).get("Recorded By"))
    label = date_text
    if recorded:
        label += " — " + recorded
    if include_time:
        stamp = _cell((record or {}).get("Timestamp"))
        if stamp:
            label += " (" + stamp + ")"
    return label


def safety_meeting_pdf_filename(record):
    date_text = _cell((record or {}).get("Meeting Date")) or "meeting"
    return "CVH_Monthly_Safety_Meeting_" + date_text + ".pdf"


def safety_meeting_report_logo_path():
    """Prefer Ron's invoice flag logo, then the copy bundled with the app."""
    from pathlib import Path
    here = Path(__file__).resolve().parent if "__file__" in globals() else Path(".")
    candidates = [
        Path("/workspace/invoices/logo/flaglogo.png"),
        here / "flaglogo_report.png",
        Path("flaglogo_report.png"),
        here / "flaglogo.png",
        Path("flaglogo.png"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def build_safety_meeting_pdf(record, logo_path=None):
    """One-page letter PDF of a saved meeting, in the flag-logo report style."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    def _esc(value, newlines=False):
        text = _cell(value)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if newlines:
            text = text.replace('\n', "<br/>")
        return text

    logo_path = logo_path if logo_path is not None else safety_meeting_report_logo_path()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title="Monthly Safety Meeting",
        author="Central Valley Helicopters",
    )
    ss = getSampleStyleSheet()
    company = ParagraphStyle(
        "co", parent=ss["Normal"], fontSize=9, leading=11, alignment=TA_LEFT,
        textColor=colors.HexColor("#222222"),
    )
    company_sm = ParagraphStyle("cosm", parent=company, fontSize=8, leading=10, textColor=colors.HexColor("#333333"))
    title_style = ParagraphStyle(
        "t", parent=ss["Title"], fontSize=15, leading=18, spaceAfter=2, spaceBefore=4, alignment=TA_LEFT,
    )
    heading = ParagraphStyle("h", parent=ss["Heading2"], fontSize=11, leading=14, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("n", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("c", parent=body, fontSize=8.5, leading=11)
    story = []

    logo_flow = None
    if logo_path:
        try:
            logo_flow = Image(logo_path, width=1.25 * inch, height=1.25 * inch * 214 / 320)
        except Exception:
            logo_flow = None
    company_lines = [
        Paragraph("<b>Cline Air Services LLC dba Central Valley Helicopters</b>", company),
        Paragraph("891 Prater Rd, Ellensburg, WA 98926", company_sm),
        Paragraph("Phone: (509) 968-9300", company_sm),
        Paragraph("Email: cvh@centralvalleyheli.com", company_sm),
    ]
    company_block = Table([[line] for line in company_lines], colWidths=[5.8 * inch])
    company_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    if logo_flow is not None:
        head = Table([[logo_flow, company_block]], colWidths=[1.4 * inch, 5.8 * inch])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(head)
    else:
        for line in company_lines:
            story.append(line)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#8B0000"), spaceBefore=2, spaceAfter=8))
    story.append(Paragraph("Monthly Safety Meeting", title_style))

    date_text = _cell(record.get("Meeting Date")) or "—"
    recorded = _cell(record.get("Recorded By")) or "—"
    story.append(Paragraph("<b>Meeting Date:</b> " + _esc(date_text), body))
    story.append(Paragraph("<b>Recorded By:</b> " + _esc(recorded), body))

    story.append(Paragraph("Checklist", heading))
    rows = [[
        Paragraph("<b>Item</b>", small),
        Paragraph("<b>Status</b>", small),
        Paragraph("<b>Note</b>", small),
    ]]
    for item in SAFETY_MEETING_ITEMS:
        done = safety_meeting_item_done(record, item)
        status = "Done / Reviewed" if done else "Not reviewed"
        note = _cell(record.get(item + " Note")) or "—"
        rows.append([
            Paragraph(_esc(item), small),
            Paragraph(_esc(status), small),
            Paragraph(_esc(note, newlines=True), small),
        ])
    table = Table(rows, colWidths=[2.7 * inch, 1.5 * inch, 3.0 * inch])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    story.append(Paragraph("Attendees", heading))
    checked, other = parse_safety_meeting_attendees(record.get("Attendees"))
    if checked:
        story.append(Paragraph(_esc(", ".join(checked)), body))
    else:
        story.append(Paragraph("None of the listed names were checked.", body))
    story.append(Paragraph("<b>Other attendees:</b> " + (_esc(other) if other else "—"), body))

    story.append(Paragraph("Meeting Discussion", heading))
    discussion = _cell(record.get("Discussion Notes"))
    story.append(Paragraph(_esc(discussion, newlines=True) if discussion else "—", body))

    doc.build(story)
    return buf.getvalue()


def show_safety_meetings_page():
    """Monthly Safety Meeting form and a phone-friendly viewer of saved meetings."""
    st.title("Monthly Safety Meeting")
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        spreadsheet = _gsheets_spreadsheet()
        meetings = load_safety_meeting_records(spreadsheet)
    except Exception as exc:
        st.error(f"Could not load safety meetings: {exc}")
        return

    if st.session_state.get("safety_meeting_saved"):
        st.success(st.session_state.pop("safety_meeting_saved"))
    if st.session_state.get("safety_meeting_notes_saved"):
        st.success(st.session_state.pop("safety_meeting_notes_saved"))

    if st.session_state.pop("safety_go_to_view", False):
        st.session_state.safety_mode = SAFETY_MEETING_VIEW
        st.session_state.safety_view_reset_to_newest = True
    if "safety_mode" not in st.session_state:
        st.session_state.safety_mode = SAFETY_MEETING_VIEW if meetings else SAFETY_MEETING_RECORD
    st.radio(
        "Page",
        [SAFETY_MEETING_VIEW, SAFETY_MEETING_RECORD],
        horizontal=True,
        key="safety_mode",
    )

    if st.session_state.safety_mode == SAFETY_MEETING_VIEW:
        _show_safety_meeting_viewer(meetings, spreadsheet)
        return

    gen = int(st.session_state.get("safety_form_gen") or 0)
    st.date_input("Meeting Date", value=today, format="YYYY-MM-DD", key=f"safety_date_{gen}")
    recorded_options = [""] + list(REPORTERS)
    st.selectbox("Recorded By (optional)", recorded_options, key=f"safety_recorded_by_{gen}")
    st.markdown("**Attendees**")
    for name in SAFETY_MEETING_ATTENDEES:
        st.checkbox(name, key=f"safety_attendee_{_safety_item_key(name)}_{gen}")
    st.text_input("Other attendees (optional)", key=f"safety_attendees_other_{gen}")

    st.subheader("Checklist")
    st.caption("Check Done / Reviewed and add a short note if needed.")
    for item in SAFETY_MEETING_ITEMS:
        slug = _safety_item_key(item)
        st.markdown("**" + item + "**")
        st.checkbox("Done / Reviewed", key=f"safety_done_{slug}_{gen}")
        st.text_input("Note (optional)", key=f"safety_note_{slug}_{gen}", label_visibility="visible")

    st.subheader("Meeting Discussion")
    st.text_area("Discussion notes for this meeting", key=f"safety_discussion_{gen}", height=180)

    if st.button("Save meeting", type="primary", key=f"safety_save_{gen}", use_container_width=True):
        item_states = {}
        for item in SAFETY_MEETING_ITEMS:
            slug = _safety_item_key(item)
            item_states[item] = {
                "done": bool(st.session_state.get(f"safety_done_{slug}_{gen}")),
                "note": st.session_state.get(f"safety_note_{slug}_{gen}", ""),
            }
        selected_attendees = [
            name for name in SAFETY_MEETING_ATTENDEES
            if st.session_state.get(f"safety_attendee_{_safety_item_key(name)}_{gen}")
        ]
        attendees = format_safety_meeting_attendees(
            selected_attendees,
            st.session_state.get(f"safety_attendees_other_{gen}", ""),
        )
        record = build_safety_meeting_record(
            st.session_state.get(f"safety_date_{gen}"),
            st.session_state.get(f"safety_recorded_by_{gen}", ""),
            attendees,
            item_states,
            st.session_state.get(f"safety_discussion_{gen}", ""),
        )
        try:
            save_safety_meeting_record(record, spreadsheet=spreadsheet)
        except Exception as exc:
            st.error(f"Could not save the safety meeting: {exc}")
        else:
            st.session_state.safety_meeting_saved = (
                "Saved safety meeting for " + (record.get("Meeting Date") or "today") + "."
            )
            st.session_state.safety_form_gen = gen + 1
            st.session_state.safety_go_to_view = True
            st.rerun()


def _show_safety_meeting_viewer(meetings, spreadsheet):
    """Read-only viewer of saved Safety Meetings rows, with optional discussion edit and PDF."""
    import calendar
    st.subheader("View saved meetings")
    st.caption("Read from the Safety Meetings tab. Newest meetings are listed first.")
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    if not meetings:
        st.info("No meetings recorded yet.")
        st.caption("Green = meeting recorded. Red = no meeting yet. Gray = future month.")
        st.markdown(safety_meeting_month_strip_markup(today.year, meetings, today=today), unsafe_allow_html=True)
        return

    years = safety_meeting_years(meetings)
    newest = filter_safety_meetings(meetings)[0]
    newest_date = safety_meeting_entry_date(newest)
    if not years:
        st.info("No meetings recorded yet.")
        return
    view_gen = int(st.session_state.get("safety_view_gen") or 0)
    if st.session_state.pop("safety_view_reset_to_newest", False) and newest_date:
        view_gen += 1
        st.session_state.safety_view_gen = view_gen
        default_year = newest_date.year
        default_month = newest_date.month
    else:
        default_year = st.session_state.get("safety_view_year_" + str(view_gen), newest_date.year if newest_date else years[0])
        default_month = st.session_state.get("safety_view_month_" + str(view_gen))
    if default_year not in years:
        default_year = years[0]
    year = st.selectbox("Year", years, index=years.index(default_year), key="safety_view_year_" + str(view_gen))
    st.caption("Green = meeting recorded. Red = no meeting yet. Gray = future month.")
    st.markdown(safety_meeting_month_strip_markup(year, meetings, today=today), unsafe_allow_html=True)
    months = safety_meeting_months_for_year(meetings, year)
    if not months:
        st.info("No meetings recorded in " + str(year) + ".")
        return
    if default_month not in months:
        default_month = newest_date.month if newest_date and newest_date.year == year and newest_date.month in months else months[-1]
    month = st.selectbox(
        "Month", months,
        index=months.index(default_month),
        format_func=lambda value: calendar.month_name[value],
        key="safety_view_month_" + str(view_gen),
    )
    filtered = filter_safety_meetings(meetings, year=year, month=month)
    if not filtered:
        st.info("No meetings recorded in " + calendar.month_name[month] + " " + str(year) + ".")
        return
    date_counts = {}
    for record in filtered:
        date_text = _cell(record.get("Meeting Date"))
        date_counts[date_text] = date_counts.get(date_text, 0) + 1
    labels = [
        safety_meeting_option_label(record, include_time=date_counts.get(_cell(record.get("Meeting Date")), 0) > 1)
        for record in filtered
    ]
    pick_key = "safety_view_pick_" + str(view_gen) + "_" + str(year) + "_" + str(month)
    if st.session_state.get(pick_key) not in labels:
        st.session_state.pop(pick_key, None)
    chosen = st.selectbox("Meeting", labels, key=pick_key)
    selected = filtered[labels.index(chosen)]

    meeting_date = _cell(selected.get("Meeting Date")) or "—"
    st.markdown("**Meeting Date:** " + meeting_date)
    recorded = _cell(selected.get("Recorded By"))
    if recorded:
        st.markdown("**Recorded By:** " + recorded)

    st.markdown("**Checklist**")
    for item in SAFETY_MEETING_ITEMS:
        done = safety_meeting_item_done(selected, item)
        note = _cell(selected.get(item + " Note"))
        line = "**" + item + ":** " + ("Done / Reviewed" if done else "Not reviewed")
        if note:
            line = line + " — " + note
        st.markdown(line)

    st.markdown("**Attendees**")
    checked, other = parse_safety_meeting_attendees(selected.get("Attendees"))
    if checked:
        for name in checked:
            st.markdown("✓ " + name)
    else:
        st.caption("None of the listed names were checked.")
    st.markdown("**Other attendees:** " + (other if other else "—"))

    st.markdown("**Meeting Discussion**")
    stamp = _cell(selected.get("Timestamp"))
    identity = safety_meeting_identity(selected)
    disc_key = "safety_past_disc_" + identity
    if disc_key not in st.session_state:
        st.session_state[disc_key] = _cell(selected.get("Discussion Notes"))
    st.text_area("Discussion Notes", key=disc_key, height=140)
    if st.button("Save discussion notes", key="safety_past_save_" + identity, use_container_width=True):
        try:
            update_safety_meeting_discussion(
                stamp, st.session_state.get(disc_key, ""), spreadsheet=spreadsheet, meeting_date=meeting_date,
            )
        except Exception as exc:
            st.error(f"Could not update discussion notes: {exc}")
        else:
            st.session_state.safety_meeting_notes_saved = "Updated discussion notes for " + meeting_date + "."
            st.rerun()

    try:
        pdf_bytes = build_safety_meeting_pdf(selected)
    except Exception as exc:
        st.caption("PDF is unavailable right now.")
        st.warning("Could not build the meeting PDF: " + str(exc))
    else:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=safety_meeting_pdf_filename(selected),
            mime="application/pdf",
            key="safety_view_pdf_" + identity,
            use_container_width=True,
        )



def yearly_item_group_names():
    return [name for name, _items in YEARLY_ITEM_GROUPS]


def yearly_item_sections(group):
    """Return [(heading or None, [item names...])] for display, in listed order."""
    wanted = _cell(group)
    sections = []
    for name, entries in YEARLY_ITEM_GROUPS:
        if name != wanted:
            continue
        current_heading = None
        current_items = []
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[1], (tuple, list)):
                if current_items:
                    sections.append((current_heading, current_items))
                    current_items = []
                sections.append((_cell(entry[0]) or None, [item for item in entry[1]]))
                current_heading = None
            else:
                current_items.append(entry)
        if current_items:
            sections.append((current_heading, current_items))
        return sections
    return []


def yearly_items_for_group(group):
    """Flat list of stored item names for a group, in listed order."""
    items = []
    for _heading, section_items in yearly_item_sections(group):
        items.extend(section_items)
    return items


def yearly_item_display_name(item, heading=None):
    """Under a subheading, show the short name when Item is 'Heading - Name'."""
    text = _cell(item)
    prefix = _cell(heading)
    if prefix and text.startswith(prefix + " - "):
        return text[len(prefix) + 3:]
    return text


def yearly_group_button_key(group):
    """Stable Streamlit/CSS key for a Yearly Items group button."""
    parts = []
    for ch in _cell(group):
        if ch.isalnum():
            parts.append(ch)
        elif not parts or parts[-1] != "_":
            parts.append("_")
    return "yearly_group_" + "".join(parts).strip("_")


def _yearly_item_widget_slug(group, item):
    def _slug(text):
        parts = []
        for ch in _cell(text):
            if ch.isalnum():
                parts.append(ch)
            elif not parts or parts[-1] != "_":
                parts.append("_")
        return "".join(parts).strip("_")
    return _slug(group) + "__" + _slug(item)


def ensure_yearly_items_worksheet(spreadsheet):
    """Create the Yearly Items tab with a header when it is missing.

    Never alters an existing header, and never writes FRAT or other tabs.
    """
    cols = list(YEARLY_ITEMS_COLUMNS)
    ws = _worksheet_or_none(spreadsheet, YEARLY_ITEMS_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=YEARLY_ITEMS_SHEET_TITLE, rows=200, cols=max(len(cols), 8))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
    return ws, created


def load_yearly_item_records(spreadsheet=None):
    ws, _created = ensure_yearly_items_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, YEARLY_ITEMS_COLUMNS)


def load_yearly_item_records_readonly(spreadsheet=None):
    """Read the Yearly Items tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), YEARLY_ITEMS_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    return records_from_worksheet(ws, YEARLY_ITEMS_COLUMNS)


def yearly_item_year_value(record):
    raw = _cell((record or {}).get("Year"))
    try:
        return int(raw)
    except (TypeError, ValueError):
        entry = parse_equipment_date((record or {}).get("Date Done"))
        return entry.year if entry is not None else None


def _yearly_item_sort_key(record):
    stamp = _cell((record or {}).get("Timestamp"))
    stamp_dt = datetime.min
    if stamp:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                stamp_dt = datetime.strptime(stamp, fmt)
                break
            except ValueError:
                continue
    done = parse_equipment_date((record or {}).get("Date Done"))
    done_dt = datetime(done.year, done.month, done.day) if done is not None else datetime.min
    return (stamp_dt, done_dt)


def build_yearly_item_record(year, group, item, date_done, done_by, notes, when=None):
    try:
        year_n = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError("Year is required") from exc
    group = _cell(group)
    item = _cell(item)
    done_by = _cell(done_by)
    if not group or not item:
        raise ValueError("Group and Item are required")
    if not done_by:
        raise ValueError("Done By is required")
    date_text = format_equipment_date(date_done)
    if not date_text:
        raise ValueError("Date Done is required")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Year": str(year_n),
        "Group": group,
        "Item": item,
        "Date Done": date_text,
        "Done By": done_by,
        "Notes": _cell(notes),
    }


def save_yearly_item_record(record, spreadsheet=None):
    ws, _created = ensure_yearly_items_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Yearly Items worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Yearly Items)"


def filter_yearly_items(records, year=None, group=None, item=None):
    rows = list(records or [])
    if year is not None:
        year_n = int(year)
        rows = [r for r in rows if yearly_item_year_value(r) == year_n]
    if group is not None:
        wanted = _cell(group)
        rows = [r for r in rows if _cell(r.get("Group")) == wanted]
    if item is not None:
        wanted = _cell(item)
        rows = [r for r in rows if _cell(r.get("Item")) == wanted]
    return rows


def latest_yearly_item_record(records, year, group, item):
    rows = filter_yearly_items(records, year=year, group=group, item=item)
    if not rows:
        return None
    return max(rows, key=_yearly_item_sort_key)


def yearly_item_is_done(records, year, group, item):
    return latest_yearly_item_record(records, year, group, item) is not None


def yearly_item_status(records, year, group, item):
    """'ok' if the item was recorded for that year, 'expired' if not."""
    return "ok" if yearly_item_is_done(records, year, group, item) else "expired"


def yearly_group_status(records, year, group):
    """'ok' if every item in the group is done for that year, otherwise 'expired'."""
    items = yearly_items_for_group(group)
    if not items:
        return "expired"
    if all(yearly_item_is_done(records, year, group, item) for item in items):
        return "ok"
    return "expired"


def yearly_group_statuses(records, year):
    return {name: yearly_group_status(records, year, name) for name, _items in YEARLY_ITEM_GROUPS}


def yearly_item_years(records, today=None):
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    years = {yearly_item_year_value(r) for r in records or []}
    years.discard(None)
    years.add(today.year)
    return sorted(years, reverse=True)


def yearly_item_status_markup(item, record):
    """Colored item status: green with date and who when done, red if not done yet."""
    if record:
        kind = "ok"
        date_text = _cell(record.get("Date Done"))
        who = _cell(record.get("Done By"))
        bits = ["Done"]
        if date_text:
            bits.append(date_text)
        if who:
            bits.append("— " + who)
        body = " ".join(bits)
    else:
        kind = "expired"
        body = "Not done yet"
    color = DATE_STATUS_COLORS[kind]
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    label = _cell(item).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return kind, "**" + label + ":** <span style='color:" + color + "; font-weight:600'>" + safe + "</span>"


def apply_yearly_group_button_styles(statuses):
    """Color each Yearly Items group button from its status for the selected year."""
    css = ["<style>"]
    for group, status in (statuses or {}).items():
        color = DATE_STATUS_COLORS[status]
        key = yearly_group_button_key(group)
        css.append(
            ".st-key-" + key + " button,"
            ".st-key-" + key + " button[data-baseweb='button'][kind='primary']{"
            "background-color:" + color + " !important;"
            "color:#ffffff !important;"
            "border-color:" + color + " !important;"
            "}"
        )
    css.append("</style>")
    st.markdown("".join(css), unsafe_allow_html=True)
    return statuses


def show_yearly_items_page():
    """Phone-friendly Yearly Items groups, checklists, and a short history."""
    selected = _cell(st.session_state.get("yearly_items_group"))
    if selected:
        show_yearly_group_page(selected)
        return

    st.title("Yearly Items")
    st.caption("Mark each item done for the selected year. Green is done; red is not done yet.")
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        records = load_yearly_item_records_readonly()
        load_ok = True
    except Exception as exc:
        records = []
        load_ok = False
        st.error("Could not load yearly items: " + str(exc))

    years = yearly_item_years(records, today=today)
    if st.session_state.get("yearly_items_year") not in years:
        st.session_state.yearly_items_year = today.year
    year = st.selectbox("Year", years, key="yearly_items_year")

    statuses = yearly_group_statuses(records, year) if load_ok else None
    for name, _items in YEARLY_ITEM_GROUPS:
        if st.button(name, key=yearly_group_button_key(name), use_container_width=True, type="primary"):
            st.session_state.yearly_items_group = name
            st.rerun()
    if statuses is not None:
        apply_yearly_group_button_styles(statuses)

    st.markdown("---")
    st.subheader("History")
    st.caption("What was recorded for the selected year.")
    if not load_ok:
        return
    _show_yearly_items_history(records, year)


def _show_yearly_items_history(records, year):
    any_done = False
    for group_name, _entries in YEARLY_ITEM_GROUPS:
        lines = []
        for heading, section_items in yearly_item_sections(group_name):
            heading_written = False
            for item in section_items:
                record = latest_yearly_item_record(records, year, group_name, item)
                if not record:
                    continue
                if heading and not heading_written:
                    lines.append(("heading", heading))
                    heading_written = True
                line = yearly_item_display_name(item, heading) + " — " + (_cell(record.get("Date Done")) or "—")
                if _cell(record.get("Done By")):
                    line += " — " + _cell(record.get("Done By"))
                if _cell(record.get("Notes")):
                    line += " — " + _cell(record.get("Notes"))
                lines.append(("item", line))
        if lines:
            any_done = True
            st.markdown("**" + group_name + "**")
            for kind, text in lines:
                safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if kind == "heading":
                    st.markdown("*" + safe + "*")
                else:
                    st.markdown(safe)
    if not any_done:
        st.info("No yearly items recorded for " + str(year) + ".")


def show_yearly_group_page(group):
    """Checklist for one Yearly Items group in the selected year."""
    st.title("Yearly Items")
    st.subheader(group)
    if st.button("Back", key="yearly_items_back", use_container_width=True):
        st.session_state.yearly_items_group = None
        st.rerun()

    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        records = load_yearly_item_records_readonly()
    except Exception as exc:
        st.error("Could not load yearly items: " + str(exc))
        return

    years = yearly_item_years(records, today=today)
    if st.session_state.get("yearly_items_year") not in years:
        st.session_state.yearly_items_year = today.year
    year = st.selectbox("Year", years, key="yearly_items_year")

    if st.session_state.get("yearly_item_saved"):
        st.success(st.session_state.pop("yearly_item_saved"))

    items = yearly_items_for_group(group)
    if not items:
        st.info("No items have been listed for this group yet.")
        return

    spreadsheet = _gsheets_spreadsheet()
    for heading, section_items in yearly_item_sections(group):
        if heading:
            st.markdown("**" + heading + "**")
        for item in section_items:
            latest = latest_yearly_item_record(records, year, group, item)
            shown = yearly_item_display_name(item, heading)
            _kind, markup = yearly_item_status_markup(shown, latest)
            st.markdown(markup, unsafe_allow_html=True)
            if latest and _cell(latest.get("Notes")):
                st.caption(_cell(latest.get("Notes")))
            slug = _yearly_item_widget_slug(group, item)
            gen = int(st.session_state.get("yearly_item_gen_" + slug) or 0)
            prefix = "yi_" + slug + "_" + str(year) + "_" + str(gen) + "_"
            with st.expander("Record " + shown, expanded=latest is None):
                st.date_input("Date Done", value=today, format="YYYY-MM-DD", key=prefix + "date")
                st.selectbox("Done By", [""] + list(DRIVERS), key=prefix + "by")
                st.text_input("Notes (optional)", key=prefix + "notes")
                if st.button("Save", type="primary", key=prefix + "save", use_container_width=True):
                    try:
                        record = build_yearly_item_record(
                            year,
                            group,
                            item,
                            st.session_state.get(prefix + "date"),
                            st.session_state.get(prefix + "by", ""),
                            st.session_state.get(prefix + "notes", ""),
                        )
                        save_yearly_item_record(record, spreadsheet=spreadsheet)
                    except Exception as exc:
                        st.error("Could not save " + item + ": " + str(exc))
                    else:
                        st.session_state.yearly_item_saved = (
                            "Saved " + item + " for " + str(year) + "."
                        )
                        st.session_state["yearly_item_gen_" + slug] = gen + 1
                        st.rerun()


def show_placeholder_page(title):
    st.title(title)
    st.info("Coming soon - Ron to define contents")


def employee_button_key(name):
    """Stable Streamlit key for an Employees page person button."""
    parts = []
    for ch in _cell(name):
        if ch.isalnum():
            parts.append(ch)
        elif not parts or parts[-1] != "_":
            parts.append("_")
    return "employee_btn_" + "".join(parts).strip("_")


def new_time_off_entry_id(when=None):
    """Readable unique id for an append-only time-off request."""
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return "TO-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def parse_time_off_time(value):
    """Parse a Pacific clock time. Blank stays blank; unparseable is ignored."""
    if value is None or value == "":
        return None
    if isinstance(value, dt_time):
        return value.replace(second=0, microsecond=0)
    if hasattr(value, "hour") and hasattr(value, "minute") and not hasattr(value, "year"):
        return dt_time(int(value.hour), int(value.minute))
    if hasattr(value, "hour") and hasattr(value, "minute") and hasattr(value, "year"):
        return dt_time(value.hour, value.minute)
    text = _cell(value).strip().upper().replace(".", "")
    text = text.replace("PT", "").strip()
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p"):
        try:
            return datetime.strptime(text, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    return None


def format_time_off_time(value):
    """Store times as HH:MM (24-hour Pacific)."""
    parsed = parse_time_off_time(value)
    if parsed is None:
        return ""
    return parsed.strftime("%H:%M")


def format_time_off_time_display(value):
    """Display a stored time as h:mm AM/PM PT."""
    parsed = parse_time_off_time(value)
    if parsed is None:
        return ""
    hour = parsed.hour % 12 or 12
    suffix = "AM" if parsed.hour < 12 else "PM"
    return str(hour) + ":" + parsed.strftime("%M") + " " + suffix + " PT"


def time_off_date_bounds(today=None):
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return today - timedelta(days=TIME_OFF_MAX_PAST_DAYS), today + timedelta(days=TIME_OFF_MAX_FUTURE_DAYS)


def time_off_shift_month(year, month, delta):
    total = int(year) * 12 + (int(month) - 1) + int(delta)
    return total // 12, total % 12 + 1


def time_off_calendar_weeks(year, month):
    """Sunday-start weeks that cover the given month."""
    first = date(int(year), int(month), 1)
    if int(month) == 12:
        last = date(int(year), 12, 31)
    else:
        last = date(int(year), int(month) + 1, 1) - timedelta(days=1)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = []
    day = start
    while day <= last:
        weeks.append([day + timedelta(days=i) for i in range(7)])
        day += timedelta(days=7)
    return weeks


def time_off_short_name(name):
    parts = _cell(name).split()
    if len(parts) >= 2:
        return parts[0] + " " + parts[-1][0] + "."
    return _cell(name)


def time_off_type_label(value, project=None):
    kind = _cell(value)
    if kind == TIME_OFF_TYPE_PROJECT:
        name = _cell(project)
        if name:
            return "Project \u2013 " + name
        return "Project"
    if kind == TIME_OFF_TYPE_FULL:
        return "Full day"
    if kind == TIME_OFF_TYPE_PARTIAL:
        return "Partial"
    if kind == TIME_OFF_TYPE_VACATION:
        return "Vacation"
    return kind


def time_off_start_date(record):
    return parse_equipment_date((record or {}).get("Start Date"))


def time_off_end_date(record):
    end = parse_equipment_date((record or {}).get("End Date"))
    return end or time_off_start_date(record)


def time_off_span_days(start, end):
    if start is None or end is None:
        return 0
    return (end - start).days + 1


def time_off_covers_date(record, day):
    start = time_off_start_date(record)
    end = time_off_end_date(record)
    if start is None or end is None or day is None:
        return False
    return start <= day <= end


def _time_off_sort_key(record):
    stamp = _cell((record or {}).get("Timestamp"))
    stamp_dt = datetime.min
    if stamp:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                stamp_dt = datetime.strptime(stamp, fmt)
                break
            except ValueError:
                continue
    start = time_off_start_date(record)
    start_dt = datetime(start.year, start.month, start.day) if start is not None else datetime.min
    return (stamp_dt, start_dt, _cell((record or {}).get("Entry ID")))


def time_off_entry_id(record):
    return _cell((record or {}).get("Entry ID"))


def time_off_is_active(record):
    status = _cell((record or {}).get("Status"))
    if status:
        return status == TIME_OFF_STATUS_ACTIVE
    return _cell((record or {}).get("Action")) != TIME_OFF_ACTION_CANCEL


def latest_time_off_record(records, entry_id):
    wanted = _cell(entry_id)
    rows = [r for r in (records or []) if time_off_entry_id(r) == wanted]
    if not rows:
        return None
    return max(rows, key=_time_off_sort_key)


def current_time_off_records(records):
    """Latest row per Entry ID, in start-date order."""
    latest = {}
    for record in records or []:
        entry_id = time_off_entry_id(record)
        if not entry_id:
            continue
        prev = latest.get(entry_id)
        if prev is None or _time_off_sort_key(record) >= _time_off_sort_key(prev):
            latest[entry_id] = record
    rows = list(latest.values())
    rows.sort(key=lambda r: (
        time_off_start_date(r) or date.min,
        time_off_end_date(r) or date.min,
        _cell(r.get("Employee")),
        time_off_entry_id(r),
    ))
    return rows


def active_time_off_records(records):
    return [r for r in current_time_off_records(records) if time_off_is_active(r)]


def time_off_for_date(records, day, employee=None):
    wanted = _cell(employee)
    rows = []
    for record in active_time_off_records(records):
        if wanted and _cell(record.get("Employee")) != wanted:
            continue
        if time_off_covers_date(record, day):
            rows.append(record)
    return rows


def time_off_for_month(records, year, month, employee=None, include_cancelled=False):
    first = date(int(year), int(month), 1)
    if int(month) == 12:
        last = date(int(year), 12, 31)
    else:
        last = date(int(year), int(month) + 1, 1) - timedelta(days=1)
    wanted = _cell(employee)
    source = current_time_off_records(records) if include_cancelled else active_time_off_records(records)
    rows = []
    for record in source:
        if wanted and _cell(record.get("Employee")) != wanted:
            continue
        start = time_off_start_date(record)
        end = time_off_end_date(record)
        if start is None:
            continue
        if end is None:
            end = start
        if end < first or start > last:
            continue
        if not include_cancelled and not time_off_is_active(record):
            continue
        rows.append(record)
    return rows


def time_off_identity(record):
    return (
        _cell((record or {}).get("Employee")),
        _cell((record or {}).get("Type")),
        format_equipment_date((record or {}).get("Start Date")),
        format_equipment_date((record or {}).get("End Date")),
        format_time_off_time((record or {}).get("Start Time")),
        format_time_off_time((record or {}).get("End Time")),
        _cell((record or {}).get("Project")),
    )


def time_off_duplicate_active(records, record, ignore_entry_id=None):
    identity = time_off_identity(record)
    skip = _cell(ignore_entry_id)
    for existing in active_time_off_records(records):
        if skip and time_off_entry_id(existing) == skip:
            continue
        if time_off_identity(existing) == identity:
            return True
    return False


def time_off_summary_text(record, include_employee=True):
    employee = _cell((record or {}).get("Employee"))
    kind = _cell((record or {}).get("Type"))
    start = format_equipment_date((record or {}).get("Start Date"))
    end = format_equipment_date((record or {}).get("End Date"))
    bits = []
    if include_employee and employee:
        bits.append(employee)
    if kind == TIME_OFF_TYPE_PARTIAL:
        start_t = format_time_off_time_display((record or {}).get("Start Time"))
        end_t = format_time_off_time_display((record or {}).get("End Time"))
        when = start or "—"
        if start_t and end_t:
            when += ", " + start_t.replace(" PT", "") + "–" + end_t
        elif start_t or end_t:
            when += ", " + (start_t or end_t)
        bits.append(kind)
        bits.append(when)
    elif kind == TIME_OFF_TYPE_VACATION and start and end and start != end:
        bits.append(kind)
        bits.append(start + " to " + end)
    else:
        shown = kind or "Time off"
        if kind == TIME_OFF_TYPE_PROJECT:
            shown = time_off_type_label(kind, (record or {}).get("Project"))
        bits.append(shown)
        bits.append(start or "—")
    notes = _cell((record or {}).get("Notes"))
    text = " — ".join(bits)
    if notes:
        text += " — " + notes
    return text


def time_off_month_grid_markup(year, month, records, today=None, employee=None):
    """HTML month grid with names and types; multi-day entries appear on each day."""
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    weeks = time_off_calendar_weeks(year, month)
    css = (
        "<style>"
        ".toff-cal{width:100%;border-collapse:collapse;table-layout:fixed;font-size:0.72rem;}"
        ".toff-cal th{text-align:center;padding:0.2rem 0;color:#4b5563;font-weight:600;}"
        ".toff-cal td{border:1px solid #e5e7eb;vertical-align:top;padding:0.2rem;height:4.4rem;}"
        ".toff-cal .muted{color:#9ca3af;background:#f9fafb;}"
        ".toff-cal .today{border:2px solid #007BFF;}"
        ".toff-cal .daynum{font-weight:700;display:block;}"
        ".toff-cal .ev{margin-top:0.12rem;line-height:1.15;}"
        ".toff-full{background:#fef3c7;}"
        ".toff-part{background:#e0f2fe;}"
        ".toff-vac{background:#ede9fe;}"
        ".toff-proj{background:#dcfce7;}"
        "</style>"
    )
    rows = ["<table class='toff-cal'><thead><tr>"]
    for label in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"):
        rows.append("<th>" + label + "</th>")
    rows.append("</tr></thead><tbody>")
    for week in weeks:
        rows.append("<tr>")
        for day in week:
            classes = []
            if day.month != int(month):
                classes.append("muted")
            if day == today:
                classes.append("today")
            attr = " class='" + " ".join(classes) + "'" if classes else ""
            cell = ["<td" + attr + "><span class='daynum'>" + str(day.day) + "</span>"]
            if day.month == int(month):
                for record in time_off_for_date(records, day, employee=employee):
                    kind = _cell(record.get("Type"))
                    ev_class = "ev"
                    if kind == TIME_OFF_TYPE_FULL:
                        ev_class += " toff-full"
                    elif kind == TIME_OFF_TYPE_PARTIAL:
                        ev_class += " toff-part"
                    elif kind == TIME_OFF_TYPE_VACATION:
                        ev_class += " toff-vac"
                    elif kind == TIME_OFF_TYPE_PROJECT:
                        ev_class += " toff-proj"
                    label = time_off_short_name(record.get("Employee")) + " — " + time_off_type_label(
                        kind, record.get("Project")
                    )
                    if kind == TIME_OFF_TYPE_PARTIAL:
                        start_t = format_time_off_time_display(record.get("Start Time"))
                        end_t = format_time_off_time_display(record.get("End Time"))
                        if start_t and end_t:
                            label += " " + start_t.replace(" PT", "") + "–" + end_t.replace(" PT", "")
                    safe = (
                        label.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    cell.append("<div class='" + ev_class + "'>" + safe + "</div>")
            cell.append("</td>")
            rows.append("".join(cell))
        rows.append("</tr>")
    rows.append("</tbody></table>")
    return css + "".join(rows)


def ensure_time_off_project_column(ws):
    """Append a Project column when an older Time Off header does not have one.

    Existing header cells stay in place. Rows saved before the column still
    load with a blank project.
    """
    header = [_cell(c) for c in ws.row_values(1)]
    if not header or "Project" in header:
        return False
    if hasattr(ws, "add_cols"):
        try:
            ws.add_cols(1)
        except Exception:
            pass
    ws.update_cell(1, len(header) + 1, "Project")
    return True


def ensure_time_off_worksheet(spreadsheet):
    """Create the Time Off tab with a header when it is missing.

    An existing header is not reordered or rewritten. A missing Project
    column is appended so a chosen project can be stored. Older rows that
    have no project cell still load with a blank project. Never writes FRAT
    or other tabs.
    """
    cols = list(TIME_OFF_COLUMNS)
    ws = _worksheet_or_none(spreadsheet, TIME_OFF_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=TIME_OFF_SHEET_TITLE, rows=400, cols=max(len(cols), 12))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
        else:
            ensure_time_off_project_column(ws)
    return ws, created


def load_time_off_records(spreadsheet=None):
    ws, _created = ensure_time_off_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, TIME_OFF_COLUMNS)


def load_time_off_records_readonly(spreadsheet=None):
    """Read the Time Off tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), TIME_OFF_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    return records_from_worksheet(ws, TIME_OFF_COLUMNS)


def build_time_off_record(
    employee,
    kind,
    start_date,
    end_date=None,
    start_time=None,
    end_time=None,
    notes="",
    project=None,
    when=None,
    entry_id=None,
    today=None,
    existing=None,
):
    employee = _cell(employee)
    kind = _cell(kind)
    if employee not in list(EMPLOYEES):
        raise ValueError("Employee is required")
    if kind not in TIME_OFF_TYPES:
        raise ValueError("Type is required")
    project_name = ""
    if kind == TIME_OFF_TYPE_PROJECT:
        project_name = _cell(project)
        if project_name not in TIME_OFF_PROJECTS:
            raise ValueError("Project is required")
    start = parse_equipment_date(start_date)
    end = parse_equipment_date(end_date) if end_date not in (None, "") else None
    if start is None:
        raise ValueError("Date is required")
    if kind == TIME_OFF_TYPE_VACATION:
        if end is None:
            raise ValueError("End date is required")
        if end < start:
            raise ValueError("End date must be on or after the start date")
        if time_off_span_days(start, end) > TIME_OFF_MAX_SPAN_DAYS:
            raise ValueError("Vacation can be at most " + str(TIME_OFF_MAX_SPAN_DAYS) + " days")
    else:
        if end is not None and end != start:
            raise ValueError("Full day, partial day, and project entries use a single date")
        end = start
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    low, high = time_off_date_bounds(today=today)
    if start < low or end > high:
        raise ValueError("Dates must be within about two years of today")
    start_t = ""
    end_t = ""
    if kind == TIME_OFF_TYPE_PARTIAL:
        start_parsed = parse_time_off_time(start_time)
        end_parsed = parse_time_off_time(end_time)
        if start_parsed is None or end_parsed is None:
            raise ValueError("Start and end times are required for a partial day")
        if end_parsed <= start_parsed:
            raise ValueError("End time must be after start time")
        start_t = format_time_off_time(start_parsed)
        end_t = format_time_off_time(end_parsed)
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    record = {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Entry ID": _cell(entry_id) or new_time_off_entry_id(when=when),
        "Action": TIME_OFF_ACTION_CREATE,
        "Employee": employee,
        "Type": kind,
        "Start Date": format_equipment_date(start),
        "End Date": format_equipment_date(end),
        "Start Time": start_t,
        "End Time": end_t,
        "Notes": _cell(notes),
        "Status": TIME_OFF_STATUS_ACTIVE,
        "Project": project_name,
    }
    if existing is not None and time_off_duplicate_active(existing, record):
        raise ValueError("This time off is already listed")
    return record


def build_time_off_cancel_record(record, when=None):
    if not record or not time_off_entry_id(record):
        raise ValueError("Nothing to cancel")
    if not time_off_is_active(record):
        raise ValueError("This time off is already cancelled")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    cancelled = dict(record)
    cancelled["Timestamp"] = when.strftime("%Y-%m-%d %H:%M:%S")
    cancelled["Action"] = TIME_OFF_ACTION_CANCEL
    cancelled["Status"] = TIME_OFF_STATUS_CANCELLED
    cancelled["Entry ID"] = time_off_entry_id(record)
    return cancelled


def save_time_off_record(record, spreadsheet=None):
    ws, _created = ensure_time_off_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Time Off worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Time Off)"


def show_time_off_calendar_page():
    """Shared in-app time-off calendar with a month grid, agenda, and list form."""
    st.title("Calendar")
    st.caption(
        "Shared time-off list so everyone can keep track. These are listed time-off "
        "requests, not automatically approved leave. Do not include medical or other "
        "sensitive details in the note."
    )
    if st.button("Back", key="employees_calendar_back", use_container_width=True):
        st.session_state.employees_show_calendar = False
        st.rerun()

    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        records = load_time_off_records_readonly()
        load_ok = True
    except Exception as exc:
        records = []
        load_ok = False
        st.error("Could not load time off: " + str(exc))

    if st.session_state.get("time_off_year") is None or st.session_state.get("time_off_month") is None:
        st.session_state.time_off_year = today.year
        st.session_state.time_off_month = today.month
    year = int(st.session_state.time_off_year)
    month = int(st.session_state.time_off_month)

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("Previous", key="time_off_prev", use_container_width=True):
            y, m = time_off_shift_month(year, month, -1)
            st.session_state.time_off_year = y
            st.session_state.time_off_month = m
            st.rerun()
    with nav2:
        if st.button("Today", key="time_off_today", use_container_width=True):
            st.session_state.time_off_year = today.year
            st.session_state.time_off_month = today.month
            st.rerun()
    with nav3:
        if st.button("Next", key="time_off_next", use_container_width=True):
            y, m = time_off_shift_month(year, month, 1)
            st.session_state.time_off_year = y
            st.session_state.time_off_month = m
            st.rerun()
    st.subheader(date(year, month, 1).strftime("%B %Y"))

    filter_options = ["All employees"] + list(EMPLOYEES)
    if st.session_state.get("time_off_filter") not in filter_options:
        st.session_state.time_off_filter = "All employees"
    filt_col, ref_col = st.columns([3, 1])
    with filt_col:
        shown = st.selectbox("Show", filter_options, key="time_off_filter")
    with ref_col:
        st.markdown("<div style='height:1.55rem'></div>", unsafe_allow_html=True)
        if st.button("Refresh", key="time_off_refresh", use_container_width=True):
            st.session_state.time_off_refreshed = "Refreshed from the shared list."
            st.rerun()
    if st.session_state.get("time_off_refreshed"):
        st.success(st.session_state.pop("time_off_refreshed"))
    if st.session_state.get("time_off_saved"):
        st.success(st.session_state.pop("time_off_saved"))

    employee_filter = None if shown == "All employees" else shown
    if load_ok:
        st.markdown(
            time_off_month_grid_markup(year, month, records, today=today, employee=employee_filter),
            unsafe_allow_html=True,
        )
    else:
        st.info("Calendar grid is unavailable until the list can be loaded.")

    st.markdown("---")
    st.subheader("Agenda")
    st.caption("Time off that falls in this month. Cancel keeps a history row instead of deleting.")
    month_rows = time_off_for_month(records, year, month, employee=employee_filter) if load_ok else []
    if not load_ok:
        pass
    elif not month_rows:
        st.info("No listed time off in " + date(year, month, 1).strftime("%B %Y") + ".")
    else:
        for record in month_rows:
            entry_id = time_off_entry_id(record)
            st.markdown("**" + time_off_summary_text(record) + "**")
            pending = _cell(st.session_state.get("time_off_confirm_cancel"))
            if pending == entry_id:
                st.warning(
                    "Cancel this listed request? It will be marked cancelled and kept in history, not deleted."
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Confirm cancel", key="time_off_confirm_" + entry_id, use_container_width=True):
                        try:
                            save_time_off_record(build_time_off_cancel_record(record))
                        except Exception as exc:
                            st.error("Could not cancel: " + str(exc))
                        else:
                            st.session_state.time_off_confirm_cancel = None
                            st.session_state.time_off_saved = "Cancelled the listed request."
                            st.rerun()
                with c2:
                    if st.button("Never mind", key="time_off_never_" + entry_id, use_container_width=True):
                        st.session_state.time_off_confirm_cancel = None
                        st.rerun()
            else:
                if st.button("Cancel request", key="time_off_cancel_" + entry_id, use_container_width=True):
                    st.session_state.time_off_confirm_cancel = entry_id
                    st.rerun()

    if load_ok:
        cancelled = [
            r for r in time_off_for_month(
                records, year, month, employee=employee_filter, include_cancelled=True
            )
            if not time_off_is_active(r)
        ]
        if cancelled:
            with st.expander("Cancelled requests this month"):
                for record in cancelled:
                    st.markdown(time_off_summary_text(record) + " — Cancelled")

    st.markdown("---")
    gen = int(st.session_state.get("time_off_form_gen") or 0)
    prefix = "to_form_" + str(gen) + "_"
    with st.expander("List time off", expanded=True):
        st.caption("This lists a request on the shared calendar. It is not an approval.")
        st.selectbox("Employee", [""] + list(EMPLOYEES), key=prefix + "employee")
        st.selectbox("Type", list(TIME_OFF_TYPES), key=prefix + "type")
        kind = _cell(st.session_state.get(prefix + "type")) or TIME_OFF_TYPE_FULL
        if kind == TIME_OFF_TYPE_PROJECT:
            st.selectbox("Project", list(TIME_OFF_PROJECTS), key=prefix + "project")
        default_day = today
        if date(year, month, 1) <= today <= (
            date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        ):
            default_day = today
        else:
            default_day = date(year, month, 1)
        if kind == TIME_OFF_TYPE_VACATION:
            st.date_input("Start Date", value=default_day, format="YYYY-MM-DD", key=prefix + "start")
            st.date_input("End Date", value=default_day, format="YYYY-MM-DD", key=prefix + "end")
        else:
            st.date_input("Date", value=default_day, format="YYYY-MM-DD", key=prefix + "start")
        if kind == TIME_OFF_TYPE_PARTIAL:
            st.time_input("Start Time (Pacific)", value=dt_time(8, 0), key=prefix + "start_time")
            st.time_input("End Time (Pacific)", value=dt_time(12, 0), key=prefix + "end_time")
            st.caption("Partial-day times are Pacific Time and must be on the same date, with the end after the start.")
        st.text_input(
            "Note (optional — do not include medical or other sensitive details)",
            key=prefix + "notes",
        )
        if st.button("Save request", type="primary", key=prefix + "save", use_container_width=True):
            try:
                latest = load_time_off_records_readonly()
                record = build_time_off_record(
                    st.session_state.get(prefix + "employee", ""),
                    st.session_state.get(prefix + "type", ""),
                    st.session_state.get(prefix + "start"),
                    end_date=st.session_state.get(prefix + "end") if kind == TIME_OFF_TYPE_VACATION else None,
                    start_time=st.session_state.get(prefix + "start_time") if kind == TIME_OFF_TYPE_PARTIAL else None,
                    end_time=st.session_state.get(prefix + "end_time") if kind == TIME_OFF_TYPE_PARTIAL else None,
                    notes=st.session_state.get(prefix + "notes", ""),
                    project=st.session_state.get(prefix + "project") if kind == TIME_OFF_TYPE_PROJECT else "",
                    existing=latest,
                    today=today,
                )
                save_time_off_record(record)
            except Exception as exc:
                st.error("Could not save time off: " + str(exc))
            else:
                st.session_state.time_off_form_gen = gen + 1
                st.session_state.time_off_saved = "Saved the listed time-off request."
                st.rerun()


def employee_has_timesheet(name):
    """True when this employee gets a time sheet (official weekly form or Anthony's form)."""
    name = _cell(name)
    return name in list(TIMESHEET_EMPLOYEES) or name == ANTHONY_TIMESHEET_EMPLOYEE


def employee_has_official_weekly_timesheet(name):
    """True for the five employees on the official Central Valley Helicopters weekly form."""
    return _cell(name) in list(TIMESHEET_EMPLOYEES)


def employee_has_anthony_timesheet(name):
    """True only for Anthony Root's separate official form."""
    return _cell(name) == ANTHONY_TIMESHEET_EMPLOYEE


def timesheet_week_start(value, today=None):
    """Sunday that starts the week containing value, matching the form's Week of (Sunday's Date)."""
    day = parse_equipment_date(value)
    if day is None:
        today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
        day = today
    return day - timedelta(days=(day.weekday() + 1) % 7)


def timesheet_day_dates(week_of, today=None):
    start = timesheet_week_start(week_of, today=today)
    return [start + timedelta(days=i) for i in range(7)]


def timesheet_day_column(day_label, field):
    return _cell(day_label) + " " + _cell(field)


def timesheet_columns():
    cols = ["Timestamp", "Entry ID", "Action", "Employee", "Week Of"]
    for day in TIMESHEET_DAYS:
        for field, _label in TIMESHEET_DAY_FIELDS:
            cols.append(timesheet_day_column(day, field))
    cols.extend([
        "Mileage Start", "Mileage End", "Mileage Miles", "Mileage Rate", "Mileage Amount",
        "Parts", "Fuel", "Other Reimb", "Reimb Total",
        "Comments", "Signature", "Signature Date", "Initials", "Content Hash", "Status",
    ])
    return cols


def timesheet_leave_columns():
    """Day columns for vacation and sick on the five-person weekly sheet."""
    cols = []
    for day in TIMESHEET_DAYS:
        for field in TIMESHEET_LEAVE_FIELDS:
            cols.append(timesheet_day_column(day, field))
    return cols


def timesheet_leave_hours(value):
    """Paid-leave hours. Blank or missing older cells load as 0."""
    number = timesheet_parse_number(value)
    if number is None:
        return 0.0
    return float(number)


def timesheet_weekly_hour_totals(record):
    """Worked hours stay CVH + Forestry + BNSF. Vacation and sick are separate.

    Total hours including paid leave is worked plus vacation plus sick.
    Reimbursement dollars are not part of these hour totals.
    """
    record = record or {}
    worked = 0.0
    vacation = 0.0
    sick = 0.0
    for day in TIMESHEET_DAYS:
        for field in TIMESHEET_WORKED_HOUR_FIELDS:
            number = timesheet_parse_number(record.get(timesheet_day_column(day, field)))
            if number is not None:
                worked += number
        vacation += timesheet_leave_hours(record.get(timesheet_day_column(day, "Vacation Hours")))
        sick += timesheet_leave_hours(record.get(timesheet_day_column(day, "Sick Hours")))
    worked = round(worked, 2)
    vacation = round(vacation, 2)
    sick = round(sick, 2)
    return {
        "Worked Hours": worked,
        "Vacation Hours": vacation,
        "Sick Hours": sick,
        "Total Hours Including Paid Leave": round(worked + vacation + sick, 2),
    }


def timesheet_hour_total_lines(record):
    """Labeled hour totals. Worked hours do not include paid leave."""
    totals = timesheet_weekly_hour_totals(record)
    return [
        "Worked hours: " + timesheet_format_hours(totals["Worked Hours"]),
        "Vacation: " + timesheet_format_hours(totals["Vacation Hours"]),
        "Sick: " + timesheet_format_hours(totals["Sick Hours"]),
        "Total hours including paid leave: " + timesheet_format_hours(totals["Total Hours Including Paid Leave"]),
    ]


def timesheet_parse_number(value):
    """Parse a timesheet number. Numeric zero stays zero; blank stays missing."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _cell(value).replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def timesheet_format_hours(value):
    number = timesheet_parse_number(value)
    if number is None:
        return ""
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return ("%.2f" % number).rstrip("0").rstrip(".")


def timesheet_format_money(value):
    number = timesheet_parse_number(value)
    if number is None:
        return ""
    return "%.2f" % number


def timesheet_format_rate(value):
    number = timesheet_parse_number(value)
    if number is None:
        return ""
    return ("%.4f" % number).rstrip("0").rstrip(".")


def timesheet_mileage_amount(miles, rate):
    miles_n = timesheet_parse_number(miles)
    rate_n = timesheet_parse_number(rate)
    if miles_n is None or rate_n is None:
        return None
    return round(miles_n * rate_n, 2)


def timesheet_format_mileage_rate(value):
    """Format a per-mile rate, keeping 2 or 3 decimals as published (0.76, 0.725, 0.70)."""
    number = timesheet_parse_number(value)
    if number is None:
        return ""
    text = ("%.3f" % number).rstrip("0")
    if text.endswith("."):
        text += "00"
    elif len(text.split(".")[-1]) == 1:
        text += "0"
    return text


def timesheet_irs_business_mileage_period(value):
    """Return the published IRS business-rate period for a travel date, or None."""
    day = parse_equipment_date(value)
    if day is None:
        return None
    for start, end, rate, notice in TIMESHEET_IRS_BUSINESS_MILEAGE_RATES:
        if start <= day <= end:
            return {
                "start": start,
                "end": end,
                "rate": rate,
                "notice": notice,
                "source": TIMESHEET_IRS_MILEAGE_SOURCE_URL,
            }
    return None


def timesheet_irs_business_mileage_rate(value):
    period = timesheet_irs_business_mileage_period(value)
    if not period:
        return None
    return period["rate"]


def timesheet_irs_mileage_supported_range_text():
    start = format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_START)
    end = format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END)
    return (
        "IRS business standard mileage rates in this app follow the official table "
        "at IRS Standard mileage rates, from " + start + " through " + end + ". "
        "Later rates are not guessed and the last published rate is not carried forward."
    )


def timesheet_irs_mileage_unsupported_reason(value):
    day = parse_equipment_date(value)
    if day is None:
        return (
            "Enter the travel date to apply the IRS business mileage rate for that date, "
            "or enter a company mileage rate override. "
            + timesheet_irs_mileage_supported_range_text()
        )
    if day > TIMESHEET_IRS_MILEAGE_RATES_END:
        return (
            "No published IRS business mileage rate is available in this app for "
            + format_equipment_date(day) + ". Rates are included through "
            + format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END)
            + " and later rates are not invented. Enter a company mileage rate override "
            "if the company has set a rate, or wait until the IRS publishes a new rate."
        )
    if day < TIMESHEET_IRS_MILEAGE_RATES_START:
        return (
            "No published IRS business mileage rate is available in this app for "
            + format_equipment_date(day) + ". Included rates start "
            + format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_START)
            + ". Enter a company mileage rate override if the company has set a rate."
        )
    return (
        "No published IRS business mileage rate is available in this app for "
        + format_equipment_date(day) + ". " + timesheet_irs_mileage_supported_range_text()
    )


def timesheet_mileage_trip_is_blank(trip):
    trip = trip or {}
    keys = ("Travel Date", "Start Location", "End Location", "Miles", "Rate", "Company Override")
    return not any(_cell(trip.get(key)) for key in keys)


def timesheet_structured_mileage_trips(record):
    """Dated or multi-trip mileage rows. Empty for historic single saved entries with no date."""
    raw = (record or {}).get("Mileage Trips")
    if not raw:
        return []
    trips = []
    for item in raw:
        if timesheet_mileage_trip_is_blank(item):
            continue
        trips.append(item)
    if not trips:
        return []
    if (
        len(trips) == 1
        and not _cell(trips[0].get("Travel Date"))
        and _cell(trips[0].get("Rate Source")) in ("", TIMESHEET_MILEAGE_SOURCE_SAVED)
    ):
        # A single undated saved trip is historic mileage; keep the old payload shape.
        return []
    return trips


def timesheet_resolve_mileage_trip(trip, today=None):
    """Validate one mileage trip and apply the IRS rate for its travel date unless overridden."""
    trip = dict(trip or {})
    start = _cell(trip.get("Start Location") or trip.get("start") or "")
    end = _cell(trip.get("End Location") or trip.get("end") or "")
    miles = trip.get("Miles") or trip.get("miles") or ""
    override = trip.get("Company Override")
    if override is None:
        override = trip.get("company_override") or ""
    # An explicit company override is only the Company Override field, never a bare Rate
    # copied from a previously saved IRS/default value.
    travel = parse_equipment_date(trip.get("Travel Date") or trip.get("travel_date"))
    source = _cell(trip.get("Rate Source"))
    if _cell(miles) and timesheet_parse_number(miles) is None:
        raise ValueError("# of miles must be a number")
    miles_n = timesheet_parse_number(miles)
    if miles_n is not None and miles_n < 0:
        raise ValueError("# of miles cannot be negative")
    if _cell(override) and timesheet_parse_number(override) is None:
        raise ValueError("Company mileage rate override must be a number")
    override_n = timesheet_parse_number(override)
    if override_n is not None and override_n < 0:
        raise ValueError("Company mileage rate override cannot be negative")
    rate = None
    rate_source = ""
    amount = None
    if override_n is not None:
        rate = override_n
        rate_source = TIMESHEET_MILEAGE_SOURCE_COMPANY
    elif travel is not None:
        irs_rate = timesheet_irs_business_mileage_rate(travel)
        if irs_rate is None:
            raise ValueError(timesheet_irs_mileage_unsupported_reason(travel))
        rate = irs_rate
        rate_source = TIMESHEET_MILEAGE_SOURCE_IRS
    elif _cell(miles):
        # Miles without a travel date or company override must not silently use
        # Sunday or a stale 2023 rate.
        raise ValueError(timesheet_irs_mileage_unsupported_reason(None))
    if miles_n is not None and rate is not None:
        amount = timesheet_mileage_amount(miles_n, rate)
    return {
        "Travel Date": format_equipment_date(travel),
        "Start Location": start,
        "End Location": end,
        "Miles": timesheet_format_hours(miles),
        "Rate": timesheet_format_mileage_rate(rate),
        "Amount": timesheet_format_money(amount),
        "Rate Source": rate_source,
        "Company Override": timesheet_format_mileage_rate(override) if override_n is not None else "",
    }


def timesheet_summarize_mileage_trips(trips):
    """Fold trips into the existing Time Sheets mileage columns without changing that header."""
    trips = [t for t in (trips or []) if not timesheet_mileage_trip_is_blank(t)]
    if not trips:
        return {
            "Mileage Start": "",
            "Mileage End": "",
            "Mileage Miles": "",
            "Mileage Rate": "",
            "Mileage Amount": "",
        }
    if len(trips) == 1:
        trip = trips[0]
        return {
            "Mileage Start": _cell(trip.get("Start Location")),
            "Mileage End": _cell(trip.get("End Location")),
            "Mileage Miles": _cell(trip.get("Miles")),
            "Mileage Rate": _cell(trip.get("Rate")),
            "Mileage Amount": _cell(trip.get("Amount")),
        }
    total_miles = 0.0
    total_amount = 0.0
    any_miles = False
    any_amount = False
    rates = set()
    for trip in trips:
        miles_n = timesheet_parse_number(trip.get("Miles"))
        if miles_n is not None:
            total_miles += miles_n
            any_miles = True
        amount_n = timesheet_parse_number(trip.get("Amount"))
        if amount_n is not None:
            total_amount += amount_n
            any_amount = True
        if _cell(trip.get("Rate")):
            rates.add(_cell(trip.get("Rate")))
    return {
        "Mileage Start": "",
        "Mileage End": "",
        "Mileage Miles": timesheet_format_hours(total_miles) if any_miles else "",
        "Mileage Rate": rates.pop() if len(rates) == 1 else "",
        "Mileage Amount": timesheet_format_money(total_amount) if any_amount else "",
    }


def timesheet_mileage_help_caption():
    return (
        "Use the date you drove, not automatically the week's Sunday. "
        "A week that crosses a rate change (for example June 30 and July 1, 2026) "
        "needs a separate mileage trip for each travel date. "
        + timesheet_irs_mileage_supported_range_text()
    )



def timesheet_reimb_total(parts, fuel, other):
    total = 0.0
    any_val = False
    for value in (parts, fuel, other):
        number = timesheet_parse_number(value)
        if number is not None:
            total += number
            any_val = True
    if not any_val:
        return None
    return round(total, 2)


def timesheet_content_payload(record):
    """Fields that initials lock; initials/signature metadata are excluded.

    Blank or zero vacation and sick are omitted so they hash the same as older
    rows that had no leave columns. A non-zero leave entry changes the hash.
    """
    days = {}
    for day in TIMESHEET_DAYS:
        fields = {}
        for field, _label in TIMESHEET_DAY_FIELDS:
            raw = (record or {}).get(timesheet_day_column(day, field))
            if field in TIMESHEET_LEAVE_FIELDS:
                number = timesheet_parse_number(raw)
                if number is None or abs(number) < 1e-9:
                    continue
                fields[field] = timesheet_format_hours(number)
            else:
                fields[field] = _cell(raw)
        days[day] = fields
    payload = {
        "Employee": _cell((record or {}).get("Employee")),
        "Week Of": format_equipment_date((record or {}).get("Week Of")),
        "Days": days,
        "Mileage Start": _cell((record or {}).get("Mileage Start")),
        "Mileage End": _cell((record or {}).get("Mileage End")),
        "Mileage Miles": timesheet_format_hours((record or {}).get("Mileage Miles")),
        "Mileage Rate": timesheet_format_rate((record or {}).get("Mileage Rate")),
        "Mileage Amount": timesheet_format_money((record or {}).get("Mileage Amount")),
        "Parts": timesheet_format_money((record or {}).get("Parts")),
        "Fuel": timesheet_format_money((record or {}).get("Fuel")),
        "Other Reimb": timesheet_format_money((record or {}).get("Other Reimb")),
        "Reimb Total": timesheet_format_money((record or {}).get("Reimb Total")),
        "Comments": _cell((record or {}).get("Comments")),
        "Signature": _cell((record or {}).get("Signature")),
        "Signature Date": format_equipment_date((record or {}).get("Signature Date")),
    }
    trips = timesheet_structured_mileage_trips(record)
    if trips:
        payload["Mileage Trips"] = [
            {
                "Travel Date": format_equipment_date(trip.get("Travel Date")),
                "Start Location": _cell(trip.get("Start Location")),
                "End Location": _cell(trip.get("End Location")),
                "Miles": timesheet_format_hours(trip.get("Miles")),
                "Rate": timesheet_format_mileage_rate(trip.get("Rate")) or timesheet_format_rate(trip.get("Rate")),
                "Amount": timesheet_format_money(trip.get("Amount")),
                "Rate Source": _cell(trip.get("Rate Source")),
                "Company Override": timesheet_format_mileage_rate(trip.get("Company Override")),
            }
            for trip in trips
        ]
    return payload


def timesheet_content_hash(record):
    import hashlib
    import json
    if _cell((record or {}).get("Form")) == "Anthony":
        payload = anthony_timesheet_content_payload(record)
    else:
        payload = timesheet_content_payload(record)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def timesheet_initials_valid(record):
    if not _cell((record or {}).get("Initials")):
        return False
    stored = _cell((record or {}).get("Content Hash"))
    if not stored:
        return False
    return stored == timesheet_content_hash(record)


def timesheet_initials_match_current(saved, current):
    """True when saved initials still cover the current time-sheet content."""
    if not saved or not timesheet_initials_valid(saved) or current is None:
        return False
    return timesheet_content_hash(saved) == timesheet_content_hash(current)


def new_timesheet_entry_id(when=None):
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return "TS-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def _timesheet_sort_key(record):
    stamp = _cell((record or {}).get("Timestamp"))
    stamp_dt = datetime.min
    if stamp:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                stamp_dt = datetime.strptime(stamp, fmt)
                break
            except ValueError:
                continue
    return (stamp_dt, _cell((record or {}).get("Entry ID")))


def latest_timesheet_record(records, employee, week_of, today=None):
    employee = _cell(employee)
    week = format_equipment_date(timesheet_week_start(week_of, today=today))
    rows = [
        r for r in (records or [])
        if _cell(r.get("Employee")) == employee and format_equipment_date(r.get("Week Of")) == week
    ]
    if not rows:
        return None
    return max(rows, key=_timesheet_sort_key)


def build_timesheet_record(
    employee,
    week_of,
    day_values=None,
    mileage_start="",
    mileage_end="",
    mileage_miles="",
    mileage_rate="",
    mileage_trips=None,
    parts="",
    fuel="",
    other_reimb="",
    comments="",
    signature="",
    signature_date=None,
    initials="",
    when=None,
    entry_id=None,
    today=None,
):
    employee = _cell(employee)
    if employee not in list(TIMESHEET_EMPLOYEES):
        raise ValueError("This employee does not have a time sheet")
    week = timesheet_week_start(week_of, today=today)
    if parse_equipment_date(week_of) is None:
        raise ValueError("Week of (Sunday's Date) is required")
    day_values = day_values or {}
    cleaned_days = {}
    for day in TIMESHEET_DAYS:
        row = dict(day_values.get(day) or {})
        for field, _label in TIMESHEET_DAY_FIELDS:
            raw = row.get(field, "")
            if field in TIMESHEET_LEAVE_FIELDS:
                # Numeric zero is a real entry. _cell(0) is blank, so don't use it here.
                provided = (
                    isinstance(raw, (int, float)) and not isinstance(raw, bool)
                ) or bool(_cell(raw))
                number = timesheet_parse_number(raw)
                if provided and number is None:
                    raise ValueError(day + " " + field + " must be a number")
                if number is None:
                    number = 0.0
                if number < 0:
                    raise ValueError(day + " " + field + " cannot be negative")
                if number > TIMESHEET_LEAVE_HOURS_MAX:
                    raise ValueError(
                        day + " " + field + " cannot be more than "
                        + str(TIMESHEET_LEAVE_HOURS_MAX) + " hours"
                    )
                row[field] = timesheet_format_hours(number)
            elif field in {"CVH Hours", "Forestry Hours", "BNSF Hours", "Perdiem Rate"}:
                if _cell(raw) and timesheet_parse_number(raw) is None:
                    raise ValueError(day + " " + field + " must be a number")
                number = timesheet_parse_number(raw)
                if number is not None and number < 0:
                    raise ValueError(day + " " + field + " cannot be negative")
                row[field] = timesheet_format_hours(raw) if field != "Perdiem Rate" else timesheet_format_money(raw)
            else:
                row[field] = _cell(raw)
        cleaned_days[day] = row
    for label, value in (
        ("Parts", parts),
        ("Fuel", fuel),
        ("Other reimbursement", other_reimb),
    ):
        if _cell(value) and timesheet_parse_number(value) is None:
            raise ValueError(label + " must be a number")
        number = timesheet_parse_number(value)
        if number is not None and number < 0:
            raise ValueError(label + " cannot be negative")
    cleaned_trips = []
    if mileage_trips is not None:
        for trip in mileage_trips:
            if timesheet_mileage_trip_is_blank(trip):
                continue
            cleaned_trips.append(timesheet_resolve_mileage_trip(trip, today=today))
        summary = timesheet_summarize_mileage_trips(cleaned_trips)
        mileage_start = summary["Mileage Start"]
        mileage_end = summary["Mileage End"]
        mileage_miles = summary["Mileage Miles"]
        rate = summary["Mileage Rate"]
        amount = summary["Mileage Amount"]
    else:
        if _cell(mileage_miles) and timesheet_parse_number(mileage_miles) is None:
            raise ValueError("# of miles must be a number")
        miles_n = timesheet_parse_number(mileage_miles)
        if miles_n is not None and miles_n < 0:
            raise ValueError("# of miles cannot be negative")
        if _cell(mileage_rate) and timesheet_parse_number(mileage_rate) is None:
            raise ValueError("Mileage rate must be a number")
        rate_n = timesheet_parse_number(mileage_rate)
        if rate_n is not None and rate_n < 0:
            raise ValueError("Mileage rate cannot be negative")
        rate = timesheet_format_rate(mileage_rate) if _cell(mileage_rate) else ""
        amount = None
        if _cell(mileage_miles) and _cell(rate):
            amount = timesheet_mileage_amount(mileage_miles, rate)
        elif _cell(mileage_miles) and not _cell(rate):
            raise ValueError(timesheet_irs_mileage_unsupported_reason(None))
    reimb = timesheet_reimb_total(parts, fuel, other_reimb)
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    record = {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Entry ID": _cell(entry_id) or new_timesheet_entry_id(when=when),
        "Action": "Save",
        "Employee": employee,
        "Week Of": format_equipment_date(week),
        "Mileage Start": _cell(mileage_start),
        "Mileage End": _cell(mileage_end),
        "Mileage Miles": timesheet_format_hours(mileage_miles),
        "Mileage Rate": timesheet_format_mileage_rate(rate) or timesheet_format_rate(rate),
        "Mileage Amount": timesheet_format_money(amount),
        "Mileage Trips": cleaned_trips,
        "Parts": timesheet_format_money(parts),
        "Fuel": timesheet_format_money(fuel),
        "Other Reimb": timesheet_format_money(other_reimb),
        "Reimb Total": timesheet_format_money(reimb),
        "Comments": _cell(comments),
        "Signature": _cell(signature),
        "Signature Date": format_equipment_date(signature_date),
        "Initials": _cell(initials),
        "Status": "Saved",
    }
    for day in TIMESHEET_DAYS:
        for field, _label in TIMESHEET_DAY_FIELDS:
            record[timesheet_day_column(day, field)] = cleaned_days[day].get(field, "")
    if record["Initials"]:
        record["Content Hash"] = timesheet_content_hash(record)
        record["Status"] = "Initialed"
    else:
        record["Content Hash"] = ""
    return record


def ensure_timesheet_leave_columns(ws):
    """Append missing Vacation and Sick day columns without reordering the header.

    Older Time Sheets tabs keep every existing header cell. New leave columns
    are added on the right so saves can persist them. Rows that predate those
    columns still load as 0.
    """
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return False
    missing = [col for col in timesheet_leave_columns() if col not in header]
    if not missing:
        return False
    if hasattr(ws, "add_cols"):
        try:
            ws.add_cols(len(missing))
        except Exception:
            pass
    start = len(header) + 1
    for offset, col in enumerate(missing):
        ws.update_cell(1, start + offset, col)
    return True


def ensure_timesheets_worksheet(spreadsheet):
    """Create the Time Sheets tab with a header when it is missing.

    An existing header is not reordered or rewritten. Missing Vacation and
    Sick columns are appended. Never writes FRAT or other tabs.
    """
    cols = list(timesheet_columns())
    ws = _worksheet_or_none(spreadsheet, TIMESHEET_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=TIMESHEET_SHEET_TITLE, rows=400, cols=max(len(cols), 16))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
        else:
            ensure_timesheet_leave_columns(ws)
    return ws, created


def load_timesheet_records(spreadsheet=None):
    ws, _created = ensure_timesheets_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, timesheet_columns())


def load_timesheet_records_readonly(spreadsheet=None):
    """Read the Time Sheets tab without creating or changing it."""
    book = spreadsheet or _gsheets_spreadsheet()
    ws = _worksheet_or_none(book, TIMESHEET_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    records = records_from_worksheet(ws, timesheet_columns())
    return attach_timesheet_mileage_trips(records, book)


def ensure_timesheet_mileage_worksheet(spreadsheet):
    """Create the Time Sheet Mileage tab with a header when it is missing.

    Never alters an existing header, and never writes FRAT or Time Sheets headers.
    """
    cols = list(TIMESHEET_MILEAGE_COLUMNS)
    ws = _worksheet_or_none(spreadsheet, TIMESHEET_MILEAGE_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=TIMESHEET_MILEAGE_SHEET_TITLE, rows=400, cols=max(len(cols), 16))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
    return ws, created


def load_timesheet_mileage_records_readonly(spreadsheet=None):
    """Read dated mileage trips without creating or changing any tab."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), TIMESHEET_MILEAGE_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    return records_from_worksheet(ws, TIMESHEET_MILEAGE_COLUMNS)


def attach_timesheet_mileage_trips(records, spreadsheet=None):
    """Attach dated trips to weekly records. Historic rows stay unchanged when none exist."""
    by_entry = {}
    for row in load_timesheet_mileage_records_readonly(spreadsheet):
        entry = _cell(row.get("Entry ID"))
        if not entry:
            continue
        by_entry.setdefault(entry, []).append({
            "Travel Date": _cell(row.get("Travel Date")),
            "Start Location": _cell(row.get("Start Location")),
            "End Location": _cell(row.get("End Location")),
            "Miles": _cell(row.get("Miles")),
            "Rate": _cell(row.get("Rate")),
            "Amount": _cell(row.get("Amount")),
            "Rate Source": _cell(row.get("Rate Source")),
            "Company Override": _cell(row.get("Company Override")) if "Company Override" in (row or {}) else (
                _cell(row.get("Rate")) if _cell(row.get("Rate Source")) == TIMESHEET_MILEAGE_SOURCE_COMPANY else ""
            ),
        })
    attached = []
    for record in records or []:
        item = dict(record)
        entry = _cell(item.get("Entry ID"))
        if entry in by_entry:
            item["Mileage Trips"] = by_entry[entry]
        attached.append(item)
    return attached


def save_timesheet_mileage_trips(record, spreadsheet=None):
    """Append dated trips to the mileage tab. Does nothing for historic undated records."""
    trips = timesheet_structured_mileage_trips(record)
    if not trips:
        return None
    book = spreadsheet or _gsheets_spreadsheet()
    ws, _created = ensure_timesheet_mileage_worksheet(book)
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Time Sheet Mileage worksheet has no header")
    for index, trip in enumerate(trips, start=1):
        row = {
            "Timestamp": _cell(record.get("Timestamp")),
            "Entry ID": _cell(record.get("Entry ID")),
            "Action": "Save",
            "Employee": _cell(record.get("Employee")),
            "Week Of": _cell(record.get("Week Of")),
            "Trip Number": str(index),
            "Travel Date": _cell(trip.get("Travel Date")),
            "Start Location": _cell(trip.get("Start Location")),
            "End Location": _cell(trip.get("End Location")),
            "Miles": _cell(trip.get("Miles")),
            "Rate": _cell(trip.get("Rate")),
            "Amount": _cell(trip.get("Amount")),
            "Rate Source": _cell(trip.get("Rate Source")),
            "Company Override": _cell(trip.get("Company Override")),
            "Status": _cell(record.get("Status")),
        }
        ws.append_row([str(row.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Time Sheet Mileage)"


def save_timesheet_record(record, spreadsheet=None):
    book = spreadsheet or _gsheets_spreadsheet()
    ws, _created = ensure_timesheets_worksheet(book)
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Time Sheets worksheet has no header")
    values = []
    for col in header:
        value = record.get(col, "")
        if isinstance(value, (list, dict)):
            values.append("")
        else:
            values.append(str(value or ""))
    ws.append_row(values, value_input_option="RAW")
    mileage_dest = save_timesheet_mileage_trips(record, book)
    if mileage_dest:
        return "Google Sheets (Time Sheets, Time Sheet Mileage)"
    return "Google Sheets (Time Sheets)"


def timesheet_gmail_configured(secrets=None):
    """True only when dedicated Gmail send secrets exist. Never reads secret values."""
    source = secrets
    if source is None:
        try:
            source = st.secrets
        except Exception:
            return False
    try:
        if "gmail" in source:
            return True
        if "smtp" in source:
            return True
        if hasattr(source, "get") and (source.get("gmail") is not None or source.get("smtp") is not None):
            return True
    except Exception:
        return False
    return False


def timesheet_email_can_send(record, configured=None):
    """Send stays off until Gmail is configured AND the shared app is not unauthenticated.

    CVHAPP has no user login, so this never returns True in the current app.
    """
    return False


def timesheet_email_block_reason(record=None, configured=None):
    if configured is None:
        configured = timesheet_gmail_configured()
    if not configured:
        return (
            "Email is not enabled. Sending through Ron's Gmail needs server-side Gmail "
            "setup in Streamlit secrets and is not available yet. This button does not send mail."
        )
    return (
        "Email is not enabled. This app has no user login, so send-as-Ron is not turned on."
    )


def timesheet_bundle_path(filename):
    """Find a bundled time-sheet template next to the app or in a parent folder."""
    import pathlib
    roots = []
    file_global = globals().get("__file__")
    if file_global:
        roots.append(pathlib.Path(file_global).resolve().parent)
    here = pathlib.Path.cwd().resolve()
    for _ in range(6):
        roots.append(here)
        if here.parent == here:
            break
        here = here.parent
    seen = set()
    for root in roots:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        path = root / filename
        if path.is_file():
            return path
    return (roots[0] if roots else pathlib.Path(".")) / filename



def timesheet_mileage_trips_for_display(record):
    """Structured trips if present; otherwise one historic saved mileage entry."""
    trips = timesheet_structured_mileage_trips(record)
    if trips:
        return trips
    if not any(_cell((record or {}).get(key)) for key in (
        "Mileage Start", "Mileage End", "Mileage Miles", "Mileage Rate", "Mileage Amount",
    )):
        return []
    return [{
        "Travel Date": "",
        "Start Location": _cell((record or {}).get("Mileage Start")),
        "End Location": _cell((record or {}).get("Mileage End")),
        "Miles": _cell((record or {}).get("Mileage Miles")),
        "Rate": _cell((record or {}).get("Mileage Rate")),
        "Amount": _cell((record or {}).get("Mileage Amount")),
        "Rate Source": TIMESHEET_MILEAGE_SOURCE_SAVED,
        "Company Override": "",
    }]


def timesheet_mileage_rate_line(record):
    trips = timesheet_mileage_trips_for_display(record)
    rates = []
    sources = set()
    dates = []
    for trip in trips:
        if _cell(trip.get("Rate")):
            rates.append(_cell(trip.get("Rate")))
        if _cell(trip.get("Rate Source")):
            sources.add(_cell(trip.get("Rate Source")))
        if _cell(trip.get("Travel Date")):
            dates.append(_cell(trip.get("Travel Date")))
    unique_rates = list(dict.fromkeys(rates))
    if len(unique_rates) == 1 and TIMESHEET_MILEAGE_SOURCE_COMPANY in sources:
        phrase = "the company override rate of $" + unique_rates[0] + " per mile"
    elif len(unique_rates) == 1 and dates:
        phrase = (
            "the IRS business rate of $" + unique_rates[0] + " per mile for "
            + (", ".join(dates) if len(dates) == 1 else "the travel date")
        )
    elif len(unique_rates) == 1 and TIMESHEET_MILEAGE_SOURCE_SAVED in sources:
        phrase = "the previously saved rate of $" + unique_rates[0] + " per mile"
    elif len(unique_rates) == 1:
        phrase = "$" + unique_rates[0] + " per mile"
    elif unique_rates:
        phrase = "the IRS business rate for each travel date"
    else:
        phrase = "the IRS business rate for the travel date"
    return (
        "Personal vechicle usage will be reimbursed at " + phrase
        + " - no company credit card used for gas"
    )


def timesheet_mileage_source_note(record):
    trips = timesheet_mileage_trips_for_display(record)
    if not trips:
        return (
            "IRS business standard mileage rates are published through "
            + format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END) + "."
        )
    notes = []
    for trip in trips:
        travel = _cell(trip.get("Travel Date"))
        rate = _cell(trip.get("Rate"))
        source = _cell(trip.get("Rate Source"))
        if source == TIMESHEET_MILEAGE_SOURCE_COMPANY:
            notes.append(
                "Company mileage rate override"
                + ((" for " + travel) if travel else "")
                + ((" $" + rate + "/mile") if rate else "")
                + " (not the IRS rate)."
            )
        elif source == TIMESHEET_MILEAGE_SOURCE_IRS and travel and rate:
            period = timesheet_irs_business_mileage_period(travel)
            notice = (" " + period["notice"]) if period else ""
            notes.append(
                "IRS business standard mileage rate for " + travel
                + ": $" + rate + "/mile" + (notice + ".")
            )
        elif source == TIMESHEET_MILEAGE_SOURCE_SAVED and rate:
            notes.append("Previously saved mileage rate: $" + rate + "/mile.")
    if not notes:
        notes.append(
            "IRS business standard mileage rates are published through "
            + format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END) + "."
        )
    notes.append(
        "Included IRS rates end " + format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END)
        + "; later rates are not invented."
    )
    return " ".join(notes)


def timesheet_template_labels(record=None):
    labels = [
        "Central Valley Helicopters",
        "Weekly Time Sheet",
        "Name:",
        "Week of :",
        "(Sunday's Date)",
        "Sun", "Mon", "Tues", "Wed", "Thur", "Fri", "Sat",
        "Location",
        "CVH # work hours",
        "Forestry #  work hours",
        "BNSF # work hours",
        "Vacation Hours",
        "Sick Hours",
        "Perdiem Rate",
        "Other",
        "Perdiem Rates -",
        "$60.00 per day with company paid hotel",
        "$100.00 per day without company paid hotel",
        "Mileage Reimbursement  (prior approval required)",
        "Personal vechicle usage will be reimbursed at",
        "Start Location;",
        "End Location:",
        "# of miles",
        "no company credit card used for gas",
        "Other Reimbursements",
        "Receipts must be attached for reimbursement with description on receipt",
        "Parts",
        "Fuel",
        "Total",
        "Comments:",
        "Employee Signature",
        "Date",
    ]
    if record is not None:
        labels.extend(timesheet_hour_total_lines(record))
        labels.append(timesheet_mileage_rate_line(record))
        labels.append(timesheet_mileage_source_note(record))
        for trip in timesheet_mileage_trips_for_display(record):
            if _cell(trip.get("Travel Date")):
                labels.append(_cell(trip.get("Travel Date")))
            if _cell(trip.get("Rate")):
                labels.append(_cell(trip.get("Rate")))
            if _cell(trip.get("Amount")):
                labels.append("$" + _cell(trip.get("Amount")))
            if _cell(trip.get("Miles")):
                labels.append(_cell(trip.get("Miles")))
        end = format_equipment_date(TIMESHEET_IRS_MILEAGE_RATES_END)
        labels.append(end)
        labels.append("later rates are not invented")
    return labels


def build_timesheet_xlsx(record):
    """Fill the official weekly time-sheet template workbook."""
    import io
    from copy import copy
    from openpyxl import load_workbook
    from openpyxl.styles import Font, Alignment, Border, Side

    path = timesheet_bundle_path("timesheet_template.xlsx")
    wb = load_workbook(path)
    ws = wb[wb.sheetnames[0]]
    employee = _cell(record.get("Employee"))
    week = format_equipment_date(record.get("Week Of"))
    ws["B4"] = "Name: " + employee
    ws["F4"] = "Week of : " + week
    days = list(TIMESHEET_DAYS)
    for i, day in enumerate(days):
        col = 3 + i  # C=3
        ws.cell(8, col, _cell(record.get(timesheet_day_column(day, "Location"))))
        ws.cell(9, col, _cell(record.get(timesheet_day_column(day, "CVH Hours"))))
        ws.cell(10, col, _cell(record.get(timesheet_day_column(day, "Forestry Hours"))))
        ws.cell(11, col, _cell(record.get(timesheet_day_column(day, "BNSF Hours"))))
        ws.cell(12, col, _cell(record.get(timesheet_day_column(day, "Perdiem Rate"))))
        ws.cell(13, col, _cell(record.get(timesheet_day_column(day, "Other"))))
    # Rows 14-15 are blank on the official template, between Other and Perdiem Rates.
    ws["B14"] = "Vacation Hours"
    ws["B15"] = "Sick Hours"
    ws.row_dimensions[14].height = 22
    ws.row_dimensions[15].height = 22
    for i, day in enumerate(days):
        col = 3 + i  # C=3
        ws.cell(14, col, _cell(record.get(timesheet_day_column(day, "Vacation Hours"))) or "0")
        ws.cell(15, col, _cell(record.get(timesheet_day_column(day, "Sick Hours"))) or "0")
    ws.row_dimensions[20].height = 18
    ws["B20"] = "    ".join(timesheet_hour_total_lines(record))
    trips = timesheet_mileage_trips_for_display(record)
    ws["B22"] = timesheet_mileage_rate_line(record)
    if len(trips) <= 1:
        trip = trips[0] if trips else {}
        start = _cell(trip.get("Start Location"))
        end = _cell(trip.get("End Location"))
        miles = _cell(trip.get("Miles"))
        rate = _cell(trip.get("Rate"))
        amount = _cell(trip.get("Amount"))
        travel = _cell(trip.get("Travel Date"))
        ws["B23"] = "Start Location; " + (start or "_________________________")
        end_line = "End Location: " + (end or "__________________________")
        if travel:
            end_line += "    Travel date: " + travel
        ws["B24"] = end_line
        if miles:
            ws["C25"] = miles
            ws["D25"] = "X " + (rate or "") + " ="
            ws["E25"] = "$" + amount if amount else "$______________"
        else:
            ws["D25"] = "X " + (rate or "") + " ="
            ws["E25"] = "$" + amount if amount else "$______________"
    else:
        lines = []
        for i, trip in enumerate(trips, start=1):
            lines.append(
                "Trip " + str(i) + " " + _cell(trip.get("Travel Date"))
                + " " + _cell(trip.get("Start Location")) + " to " + _cell(trip.get("End Location"))
                + "  " + _cell(trip.get("Miles")) + " mi X " + _cell(trip.get("Rate"))
                + " = $" + _cell(trip.get("Amount"))
                + ((" (" + _cell(trip.get("Rate Source")) + ")") if _cell(trip.get("Rate Source")) else "")
            )
        ws["B23"] = lines[0]
        ws["B24"] = lines[1] if len(lines) > 1 else ""
        extra = " | ".join(lines[2:]) if len(lines) > 2 else ""
        total = _cell(record.get("Mileage Amount"))
        miles = _cell(record.get("Mileage Miles"))
        ws["C25"] = miles
        ws["D25"] = "Total ="
        ws["E25"] = "$" + total if total else "$______________"
        if extra:
            ws["B25"] = "# of miles  " + extra
    ws["B26"] = timesheet_mileage_source_note(record)
    def _money_cell(coord, value):
        ws[coord] = "$" + value if _cell(value) else "$"
    _money_cell("C31", record.get("Parts"))
    _money_cell("C32", record.get("Fuel"))
    _money_cell("C33", record.get("Other Reimb"))
    _money_cell("C35", record.get("Reimb Total"))
    comments = _cell(record.get("Comments"))
    ws["B37"] = "Comments: " + (comments or "__________________________________________________________________________________")
    sig = _cell(record.get("Signature"))
    initials = _cell(record.get("Initials"))
    sig_line = "Employee Signature"
    if sig:
        sig_line += "  " + sig
    if initials:
        sig_line += "    Initials: " + initials
    ws["B42"] = sig_line
    date_text = format_equipment_date(record.get("Signature Date"))
    ws["F42"] = "Date" + (("  " + date_text) if date_text else "")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def timesheet_pdf_filename(record):
    employee = _cell(record.get("Employee")).replace(" ", "_") or "employee"
    week = format_equipment_date(record.get("Week Of")) or "week"
    return "CVH_Time_Sheet_" + employee + "_" + week + ".pdf"


def timesheet_xlsx_filename(record):
    employee = _cell(record.get("Employee")).replace(" ", "_") or "employee"
    week = format_equipment_date(record.get("Week Of")) or "week"
    return "CVH_Time_Sheet_" + employee + "_" + week + ".xlsx"


def build_timesheet_pdf(record, logo_path=None):
    """One-page letter PDF matching the official weekly time-sheet layout."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, HexColor

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    c.setTitle("Weekly Time Sheet — " + _cell(record.get("Employee")))
    c.setAuthor("Central Valley Helicopters")

    def _s(size, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)

    y = height - 0.55 * inch
    _s(16, True)
    c.drawCentredString(width / 2, y, "Central Valley Helicopters")
    y -= 18
    _s(12, True)
    c.drawCentredString(width / 2, y, "Weekly Time Sheet")
    y -= 28
    _s(10, True)
    c.drawString(0.6 * inch, y, "Name:  " + _cell(record.get("Employee")))
    week = format_equipment_date(record.get("Week Of"))
    c.drawString(4.5 * inch, y, "Week of :  " + week)
    y -= 12
    _s(8, False)
    c.drawString(4.5 * inch, y, "(Sunday's Date)")

    # Grid. Vacation and Sick are extra rows on the same day columns as worked hours.
    y -= 16
    left = 0.55 * inch
    row_labels = [label for _field, label in TIMESHEET_DAY_FIELDS]
    col_labels = [""] + list(TIMESHEET_DAYS)
    col_w = [1.45 * inch] + [0.72 * inch] * 7
    field_rows = len(TIMESHEET_DAY_FIELDS)
    # Header is tall enough for the day name and date. Field rows stay readable
    # with Vacation and Sick added, and the sheet still fits on one page.
    row_h = [0.36 * inch] + [0.40 * inch] * field_rows
    rows = 1 + field_rows
    cols = 8
    grid_top = y
    grid_height = sum(row_h)
    grid_width = sum(col_w)
    c.setStrokeColor(black)
    c.setLineWidth(0.7)
    # horizontal lines
    yy = grid_top
    for r in range(rows + 1):
        c.line(left, yy, left + grid_width, yy)
        if r < rows:
            yy -= row_h[r]
    xx = left
    for col in range(cols + 1):
        c.line(xx, grid_top, xx, grid_top - grid_height)
        if col < cols:
            xx += col_w[col]

    dates = timesheet_day_dates(week)
    _s(8, True)
    xx = left
    # header row
    c.drawCentredString(left + col_w[0] / 2, grid_top - 16, "")
    xx = left + col_w[0]
    for i, day in enumerate(TIMESHEET_DAYS):
        c.drawCentredString(xx + col_w[i + 1] / 2, grid_top - 12, day)
        _s(6, False)
        c.drawCentredString(xx + col_w[i + 1] / 2, grid_top - 22, dates[i].strftime("%m/%d"))
        _s(8, True)
        xx += col_w[i + 1]
    # labels and values
    yy = grid_top - row_h[0]
    for r, (field, label) in enumerate(TIMESHEET_DAY_FIELDS):
        _s(6.5, True)
        # wrap label in first column
        text_y = yy - 12
        for line in _timesheet_wrap_label(label, 24):
            c.drawString(left + 4, text_y, line)
            text_y -= 9
        xx = left + col_w[0]
        _s(7, False)
        for i, day in enumerate(TIMESHEET_DAYS):
            val = _cell(record.get(timesheet_day_column(day, field)))
            if val:
                c.drawCentredString(xx + col_w[i + 1] / 2, yy - 18, val[:14])
            xx += col_w[i + 1]
        yy -= row_h[r + 1]

    y = grid_top - grid_height - 12
    _s(8, True)
    for line in timesheet_hour_total_lines(record):
        c.drawString(left, y, line)
        y -= 11
    y -= 6
    _s(9, True)
    c.drawString(left, y, "Perdiem Rates -")
    _s(8, False)
    c.drawString(left + 1.15 * inch, y, "$60.00 per day with company paid hotel")
    y -= 11
    c.drawString(left + 1.15 * inch, y, "$100.00 per day without company paid hotel")

    y -= 20
    _s(10, True)
    c.drawString(left, y, "Mileage Reimbursement  (prior approval required)")
    y -= 12
    _s(8, False)
    rate_line = timesheet_mileage_rate_line(record)
    # Official typo "vechicle" is preserved; wrap the longer rate sentence.
    for line in _timesheet_wrap_label(rate_line, 110):
        c.drawString(left, y, line)
        y -= 11
    trips = timesheet_mileage_trips_for_display(record)
    if len(trips) <= 1:
        trip = trips[0] if trips else {}
        start = _cell(trip.get("Start Location"))
        c.drawString(left, y, "Start Location; " + (start or "_________________________"))
        y -= 13
        end = _cell(trip.get("End Location"))
        travel = _cell(trip.get("Travel Date"))
        end_line = "End Location: " + (end or "__________________________")
        if travel:
            end_line += "    Travel date: " + travel
        c.drawString(left, y, end_line)
        y -= 14
        miles = _cell(trip.get("Miles")) or "______"
        rate = _cell(trip.get("Rate")) or "______"
        amount = _cell(trip.get("Amount"))
        money = ("$" + amount) if amount else "$______________"
        c.drawString(left, y, "# of miles  " + miles + "     X " + rate + " =     " + money)
        y -= 11
    else:
        for i, trip in enumerate(trips, start=1):
            c.drawString(
                left,
                y,
                "Trip " + str(i) + "  " + _cell(trip.get("Travel Date"))
                + "  " + _cell(trip.get("Start Location")) + " to " + _cell(trip.get("End Location"))
                + "   " + _cell(trip.get("Miles")) + " mi X " + _cell(trip.get("Rate"))
                + " = $" + _cell(trip.get("Amount")),
            )
            y -= 11
        total = _cell(record.get("Mileage Amount"))
        c.drawString(left, y, "Mileage total  $" + (total or "______________"))
        y -= 11
    for line in _timesheet_wrap_label(timesheet_mileage_source_note(record), 110):
        c.drawString(left, y, line)
        y -= 10

    y -= 18
    _s(10, True)
    c.drawString(left, y, "Other Reimbursements")
    y -= 11
    _s(8, False)
    c.drawString(left, y, "Receipts must be attached for reimbursement with description on receipt")
    y -= 16
    for label, key in (("Parts", "Parts"), ("Fuel", "Fuel"), ("Other", "Other Reimb"), ("Total", "Reimb Total")):
        val = _cell(record.get(key))
        shown = ("$" + val) if val else "$"
        _s(9, True if label == "Total" else False)
        c.drawString(left, y, label)
        c.drawString(left + 1.15 * inch, y, shown)
        if label == "Total":
            c.line(left + 1.15 * inch, y - 2, left + 2.3 * inch, y - 2)
        y -= 13

    y -= 8
    _s(9, False)
    comments = _cell(record.get("Comments"))
    c.drawString(left, y, "Comments: " + (comments[:110] if comments else "________________________________________________"))
    y -= 12
    if comments and len(comments) > 110:
        c.drawString(left, y, comments[110:220])
        y -= 14
    else:
        c.line(left, y, left + 7.4 * inch, y)
        y -= 16

    y -= 10
    _s(8, False)
    sig = _cell(record.get("Signature"))
    initials = _cell(record.get("Initials"))
    c.drawString(left, y + 10, sig)
    c.line(left, y + 8, left + 2.6 * inch, y + 8)
    c.drawString(left, y - 4, "Employee Signature")
    if initials:
        c.drawString(left + 2.8 * inch, y + 10, "Initials: " + initials)
    date_text = format_equipment_date(record.get("Signature Date"))
    c.drawString(4.7 * inch, y + 10, date_text)
    c.line(4.7 * inch, y + 8, 6.6 * inch, y + 8)
    c.drawString(4.7 * inch, y - 4, "Date")
    c.showPage()
    c.save()
    return buf.getvalue()


def _timesheet_wrap_label(text, width):
    if len(text) <= width:
        return [text]
    words = text.split(" ")
    lines, cur = [], ""
    for word in words:
        trial = word if cur == "" else cur + " " + word
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def anthony_timesheet_columns():
    cols = ["Timestamp", "Entry ID", "Action", "Form", "Employee", "Week Of"]
    for day in ANTHONY_TIMESHEET_DAYS:
        cols.append(timesheet_day_column(day, "Date"))
        for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
            cols.append(timesheet_day_column(day, field))
    cols.extend(["Initials", "Content Hash", "Status"])
    return cols


def anthony_timesheet_template_labels():
    return [
        "Employee",
        "Week of",
        "Date",
        "L&I Ground Hours",
        "L&I Flight Hours",
        "Spraying App Acres",
        "Forestry App Acres",
        "BNSF App Acres",
        "Seeding Acres",
        "Survery Hrs",
        "Standby Hrs",
        "Per Diem",
        "Notes",
    ]


def anthony_timesheet_content_payload(record):
    """Fields that initials lock on Anthony's form; initials metadata excluded."""
    days = {}
    for day in ANTHONY_TIMESHEET_DAYS:
        days[day] = {
            "Date": format_equipment_date((record or {}).get(timesheet_day_column(day, "Date"))),
        }
        for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
            value = (record or {}).get(timesheet_day_column(day, field))
            if field == "Per Diem":
                days[day][field] = timesheet_format_money(value)
            elif field in ANTHONY_TIMESHEET_NUMERIC_FIELDS:
                days[day][field] = timesheet_format_hours(value)
            else:
                days[day][field] = _cell(value)
    return {
        "Form": "Anthony",
        "Employee": _cell((record or {}).get("Employee")),
        "Week Of": format_equipment_date((record or {}).get("Week Of")),
        "Days": days,
    }


def new_anthony_timesheet_entry_id(when=None):
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return "ANT-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def build_anthony_timesheet_record(
    employee,
    week_of,
    day_values=None,
    initials="",
    when=None,
    entry_id=None,
    today=None,
):
    employee = _cell(employee)
    if not employee_has_anthony_timesheet(employee):
        raise ValueError("This employee does not have Anthony's time sheet")
    week = timesheet_week_start(week_of, today=today)
    if parse_equipment_date(week_of) is None:
        raise ValueError("Week of (Sunday's Date) is required")
    day_values = day_values or {}
    dates = timesheet_day_dates(week, today=today)
    cleaned = {}
    for i, day in enumerate(ANTHONY_TIMESHEET_DAYS):
        row = dict(day_values.get(day) or {})
        row["Date"] = format_equipment_date(dates[i])
        for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
            raw = row.get(field, "")
            if field in ANTHONY_TIMESHEET_NUMERIC_FIELDS or field == "Per Diem":
                if _cell(raw) and timesheet_parse_number(raw) is None:
                    raise ValueError(day + " " + field + " must be a number")
                number = timesheet_parse_number(raw)
                if number is not None and number < 0:
                    raise ValueError(day + " " + field + " cannot be negative")
                row[field] = (
                    timesheet_format_money(raw) if field == "Per Diem" else timesheet_format_hours(raw)
                )
            else:
                row[field] = _cell(raw)
        cleaned[day] = row
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    record = {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Entry ID": _cell(entry_id) or new_anthony_timesheet_entry_id(when=when),
        "Action": "Save",
        "Form": "Anthony",
        "Employee": employee,
        "Week Of": format_equipment_date(week),
        "Initials": _cell(initials),
        "Status": "Saved",
    }
    for day in ANTHONY_TIMESHEET_DAYS:
        record[timesheet_day_column(day, "Date")] = cleaned[day]["Date"]
        for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
            record[timesheet_day_column(day, field)] = cleaned[day].get(field, "")
    if record["Initials"]:
        record["Content Hash"] = timesheet_content_hash(record)
        record["Status"] = "Initialed"
    else:
        record["Content Hash"] = ""
    return record


def ensure_anthony_timesheets_worksheet(spreadsheet):
    """Create the Anthony Time Sheets tab with a header when it is missing.

    Never alters an existing header, and never writes FRAT, Time Sheets, or other tabs.
    """
    cols = list(anthony_timesheet_columns())
    ws = _worksheet_or_none(spreadsheet, ANTHONY_TIMESHEET_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=ANTHONY_TIMESHEET_SHEET_TITLE, rows=400, cols=max(len(cols), 16))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
    return ws, created


def load_anthony_timesheet_records(spreadsheet=None):
    ws, _created = ensure_anthony_timesheets_worksheet(spreadsheet or _gsheets_spreadsheet())
    return records_from_worksheet(ws, anthony_timesheet_columns())


def load_anthony_timesheet_records_readonly(spreadsheet=None):
    """Read the Anthony Time Sheets tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), ANTHONY_TIMESHEET_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    return records_from_worksheet(ws, anthony_timesheet_columns())


def save_anthony_timesheet_record(record, spreadsheet=None):
    ws, _created = ensure_anthony_timesheets_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Anthony Time Sheets worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Anthony Time Sheets)"


def anthony_timesheet_pdf_filename(record):
    employee = _cell(record.get("Employee")).replace(" ", "_") or "Anthony_Root"
    week = format_equipment_date(record.get("Week Of")) or "week"
    return "Anthony_Time_Sheet_" + employee + "_" + week + ".pdf"


def anthony_timesheet_xlsx_filename(record):
    employee = _cell(record.get("Employee")).replace(" ", "_") or "Anthony_Root"
    week = format_equipment_date(record.get("Week Of")) or "week"
    return "Anthony_Time_Sheet_" + employee + "_" + week + ".xlsx"


def build_anthony_timesheet_xlsx(record):
    """Fill Anthony's official template workbook. Extra blank rows stay blank."""
    import io
    from openpyxl import load_workbook

    path = timesheet_bundle_path(ANTHONY_TIMESHEET_TEMPLATE)
    wb = load_workbook(path)
    ws = wb[wb.sheetnames[0]]
    employee = _cell(record.get("Employee")) or ANTHONY_TIMESHEET_EMPLOYEE
    week = format_equipment_date(record.get("Week Of"))
    ws["A1"] = "Employee"
    ws["B1"] = employee
    ws["A4"] = "Week of " + week
    dates = timesheet_day_dates(week)
    for i, day in enumerate(ANTHONY_TIMESHEET_DAYS):
        row = 9 + i
        ws.cell(row, 1, format_equipment_date(dates[i]))
        for col, (field, _label) in enumerate(ANTHONY_TIMESHEET_DAY_FIELDS, start=2):
            ws.cell(row, col, _cell(record.get(timesheet_day_column(day, field))))
    # Official grid continues through row 30; leave those extra rows empty.
    initials = _cell(record.get("Initials"))
    if initials:
        ws["A32"] = "Initials: " + initials
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_anthony_timesheet_pdf(record, logo_path=None):
    """One-page landscape letter PDF matching Anthony's official daily-row form."""
    import io
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black

    buf = io.BytesIO()
    page = landscape(letter)
    c = canvas.Canvas(buf, pagesize=page)
    width, height = page
    employee = _cell(record.get("Employee")) or ANTHONY_TIMESHEET_EMPLOYEE
    week = format_equipment_date(record.get("Week Of"))
    c.setTitle("Time Sheet — " + employee)
    c.setAuthor("Central Valley Helicopters")

    def _s(size, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)

    y = height - 0.45 * inch
    _s(16, True)
    c.drawString(0.4 * inch, y, "Employee  " + employee)
    y -= 22
    _s(14, True)
    c.drawString(0.4 * inch, y, "Week of  " + week)

    headers = ["Date"] + [label for _field, label in ANTHONY_TIMESHEET_DAY_FIELDS]
    left = 0.35 * inch
    col_w = [
        0.85 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch, 0.85 * inch,
        0.8 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.7 * inch, 1.3 * inch,
    ]
    header_h = 0.48 * inch
    row_h = 0.32 * inch
    rows = 1 + ANTHONY_TIMESHEET_WEEK_ROWS
    cols = len(headers)
    grid_top = y - 16
    grid_height = header_h + row_h * ANTHONY_TIMESHEET_WEEK_ROWS
    grid_width = sum(col_w)
    c.setStrokeColor(black)
    c.setLineWidth(0.6)
    yy = grid_top
    for r in range(rows + 1):
        c.line(left, yy, left + grid_width, yy)
        yy -= header_h if r == 0 else row_h
    xx = left
    for col in range(cols + 1):
        c.line(xx, grid_top, xx, grid_top - grid_height)
        if col < cols:
            xx += col_w[col]

    _s(6.5, True)
    xx = left
    for i, label in enumerate(headers):
        text_y = grid_top - 12
        for line in _timesheet_wrap_label(label, 14):
            c.drawCentredString(xx + col_w[i] / 2, text_y, line)
            text_y -= 8
        xx += col_w[i]

    dates = timesheet_day_dates(week)
    yy = grid_top - header_h
    for r, day in enumerate(ANTHONY_TIMESHEET_DAYS):
        values = [format_equipment_date(dates[r])]
        for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
            values.append(_cell(record.get(timesheet_day_column(day, field))))
        xx = left
        for i, val in enumerate(values):
            _s(7, False)
            shown = val
            if shown and i == len(values) - 1:
                shown = shown[:22]
            elif shown:
                shown = shown[:12]
            if shown:
                c.drawCentredString(xx + col_w[i] / 2, yy - 14, shown)
            xx += col_w[i]
        yy -= row_h

    y = grid_top - grid_height - 20
    _s(10, True)
    initials = _cell(record.get("Initials"))
    c.drawString(0.4 * inch, y, "Initials: " + (initials or "________"))
    c.showPage()
    c.save()
    return buf.getvalue()


def show_anthony_timesheet(employee):
    """Anthony Root's official daily-row weekly time sheet."""
    st.subheader("Time Sheet")
    st.caption("Official time sheet for Anthony Root. Name is filled from this employee page.")
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        records = load_anthony_timesheet_records_readonly()
        load_ok = True
    except Exception as exc:
        records = []
        load_ok = False
        st.error("Could not load time sheets: " + str(exc))

    default_week = timesheet_week_start(today, today=today)
    if st.session_state.get("anthony_ts_week_" + employee) is None:
        st.session_state["anthony_ts_week_" + employee] = default_week
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("Previous week", key="ats_prev_" + employee, use_container_width=True):
            current = timesheet_week_start(st.session_state.get("anthony_ts_week_" + employee), today=today)
            st.session_state["anthony_ts_week_" + employee] = current - timedelta(days=7)
            st.session_state["anthony_ts_gen_" + employee] = int(st.session_state.get("anthony_ts_gen_" + employee) or 0) + 1
            st.rerun()
    with nav3:
        if st.button("Next week", key="ats_next_" + employee, use_container_width=True):
            current = timesheet_week_start(st.session_state.get("anthony_ts_week_" + employee), today=today)
            st.session_state["anthony_ts_week_" + employee] = current + timedelta(days=7)
            st.session_state["anthony_ts_gen_" + employee] = int(st.session_state.get("anthony_ts_gen_" + employee) or 0) + 1
            st.rerun()
    week_picked = st.date_input(
        "Week of (Sunday's Date)",
        value=st.session_state.get("anthony_ts_week_" + employee) or default_week,
        format="YYYY-MM-DD",
        key="ats_week_input_" + employee,
    )
    week = timesheet_week_start(week_picked, today=today)
    if week != week_picked:
        st.caption("Week of uses Sunday's date. This week starts " + week.isoformat() + ".")
    if week != st.session_state.get("anthony_ts_week_" + employee):
        st.session_state["anthony_ts_week_" + employee] = week
        st.session_state["anthony_ts_gen_" + employee] = int(st.session_state.get("anthony_ts_gen_" + employee) or 0) + 1
        st.rerun()
    with nav2:
        st.markdown("**Week of " + week.isoformat() + "**")

    saved = latest_timesheet_record(records, employee, week, today=today) if load_ok else None
    gen = int(st.session_state.get("anthony_ts_gen_" + employee) or 0)
    prefix = "ats_" + employee_button_key(employee) + "_" + week.isoformat() + "_" + str(gen) + "_"

    if st.session_state.get("anthony_ts_saved_" + employee):
        st.success(st.session_state.pop("anthony_ts_saved_" + employee))

    def _saved(field, default=""):
        return (saved or {}).get(field, default) if saved else default

    st.markdown("**Employee:** " + ANTHONY_TIMESHEET_EMPLOYEE)
    dates = timesheet_day_dates(week, today=today)
    for i, day in enumerate(ANTHONY_TIMESHEET_DAYS):
        title = day + "  " + dates[i].isoformat()
        with st.expander(title, expanded=(dates[i] == today)):
            st.markdown("**Date:** " + dates[i].isoformat())
            for field, label in ANTHONY_TIMESHEET_DAY_FIELDS:
                key = prefix + day + "_" + field.replace(" ", "_")
                st.text_input(label, value=_saved(timesheet_day_column(day, field)), key=key)

    st.text_input("Initials (required before email)", value=_saved("Initials"), key=prefix + "initials")

    def _form_record(initials=None):
        day_values = {}
        for day in ANTHONY_TIMESHEET_DAYS:
            day_values[day] = {}
            for field, _label in ANTHONY_TIMESHEET_DAY_FIELDS:
                key = prefix + day + "_" + field.replace(" ", "_")
                day_values[day][field] = st.session_state.get(key, "")
        return build_anthony_timesheet_record(
            employee,
            week,
            day_values=day_values,
            initials=initials if initials is not None else st.session_state.get(prefix + "initials", ""),
            today=today,
        )

    try:
        preview = _form_record()
        form_ok = True
        form_error = ""
    except Exception as exc:
        preview = None
        form_ok = False
        form_error = str(exc)

    if form_ok and preview:
        if timesheet_initials_match_current(saved, preview):
            st.success("Initialed for this week's current time-sheet content: " + _cell((saved or preview).get("Initials")))
        elif saved and timesheet_initials_valid(saved):
            st.warning("Time-sheet content changed since the last initials. Save the week again with initials to re-initial.")
        else:
            st.info("Initial this week before email. Initials no longer count if the time sheet changes after you save.")

    if st.button("Save week", type="primary", key=prefix + "save", use_container_width=True):
        try:
            record = _form_record()
            save_anthony_timesheet_record(record)
        except Exception as exc:
            st.error("Could not save time sheet: " + str(exc))
        else:
            st.session_state["anthony_ts_gen_" + employee] = gen + 1
            st.session_state["anthony_ts_saved_" + employee] = "Saved time sheet for week of " + week.isoformat() + "."
            st.rerun()

    if form_ok and preview:
        pdf_bytes = build_anthony_timesheet_pdf(preview)
        xlsx_bytes = build_anthony_timesheet_xlsx(preview)
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=anthony_timesheet_pdf_filename(preview),
                mime="application/pdf",
                use_container_width=True,
                key=prefix + "pdf",
            )
        with d2:
            st.download_button(
                "Download Excel",
                data=xlsx_bytes,
                file_name=anthony_timesheet_xlsx_filename(preview),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=prefix + "xlsx",
            )
    elif form_error:
        st.error(form_error)

    st.button(
        "Email to patti@centralvalleyheli.com",
        disabled=True,
        use_container_width=True,
        key=prefix + "email",
    )
    st.caption(timesheet_email_block_reason(preview if form_ok else None))



def show_employee_timesheet(employee):
    """Weekly time sheet for one eligible employee, matching the official form."""
    st.subheader("Weekly Time Sheet")
    st.caption("Official Central Valley Helicopters weekly time sheet. Name is filled from this employee page.")
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    try:
        records = load_timesheet_records_readonly()
        load_ok = True
    except Exception as exc:
        records = []
        load_ok = False
        st.error("Could not load time sheets: " + str(exc))

    default_week = timesheet_week_start(today, today=today)
    if st.session_state.get("timesheet_week_" + employee) is None:
        st.session_state["timesheet_week_" + employee] = default_week
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("Previous week", key="ts_prev_" + employee, use_container_width=True):
            current = timesheet_week_start(st.session_state.get("timesheet_week_" + employee), today=today)
            st.session_state["timesheet_week_" + employee] = current - timedelta(days=7)
            st.session_state["timesheet_gen_" + employee] = int(st.session_state.get("timesheet_gen_" + employee) or 0) + 1
            st.rerun()
    with nav3:
        if st.button("Next week", key="ts_next_" + employee, use_container_width=True):
            current = timesheet_week_start(st.session_state.get("timesheet_week_" + employee), today=today)
            st.session_state["timesheet_week_" + employee] = current + timedelta(days=7)
            st.session_state["timesheet_gen_" + employee] = int(st.session_state.get("timesheet_gen_" + employee) or 0) + 1
            st.rerun()
    week_picked = st.date_input(
        "Week of (Sunday's Date)",
        value=st.session_state.get("timesheet_week_" + employee) or default_week,
        format="YYYY-MM-DD",
        key="ts_week_input_" + employee,
    )
    week = timesheet_week_start(week_picked, today=today)
    if week != week_picked:
        st.caption("Week of uses Sunday's date. This week starts " + week.isoformat() + ".")
    if week != st.session_state.get("timesheet_week_" + employee):
        st.session_state["timesheet_week_" + employee] = week
        st.session_state["timesheet_gen_" + employee] = int(st.session_state.get("timesheet_gen_" + employee) or 0) + 1
        st.rerun()
    with nav2:
        st.markdown("**Week of " + week.isoformat() + "**")

    saved = latest_timesheet_record(records, employee, week, today=today) if load_ok else None
    gen = int(st.session_state.get("timesheet_gen_" + employee) or 0)
    prefix = "ts_" + employee_button_key(employee) + "_" + week.isoformat() + "_" + str(gen) + "_"

    if st.session_state.get("timesheet_saved_" + employee):
        st.success(st.session_state.pop("timesheet_saved_" + employee))

    def _saved(field, default=""):
        return (saved or {}).get(field, default) if saved else default

    st.markdown("**Name:** " + employee)
    dates = timesheet_day_dates(week, today=today)
    st.caption("Perdiem Rates — $60.00 per day with company paid hotel; $100.00 per day without company paid hotel.")
    for i, day in enumerate(TIMESHEET_DAYS):
        title = day + "  " + dates[i].isoformat()
        with st.expander(title, expanded=(dates[i] == today)):
            st.text_input("Location", value=_saved(timesheet_day_column(day, "Location")), key=prefix + day + "_Location")
            st.text_input("CVH # work hours", value=_saved(timesheet_day_column(day, "CVH Hours")), key=prefix + day + "_CVH")
            st.text_input("Forestry #  work hours", value=_saved(timesheet_day_column(day, "Forestry Hours")), key=prefix + day + "_Forestry")
            st.text_input("BNSF # work hours", value=_saved(timesheet_day_column(day, "BNSF Hours")), key=prefix + day + "_BNSF")
            leave_vacation, leave_sick = st.columns(2)
            with leave_vacation:
                saved_vacation = timesheet_leave_hours(_saved(timesheet_day_column(day, "Vacation Hours")))
                if saved_vacation < 0:
                    saved_vacation = 0.0
                if saved_vacation > TIMESHEET_LEAVE_HOURS_MAX:
                    saved_vacation = float(TIMESHEET_LEAVE_HOURS_MAX)
                st.number_input(
                    "Vacation Hours",
                    min_value=0.0,
                    max_value=float(TIMESHEET_LEAVE_HOURS_MAX),
                    value=float(saved_vacation),
                    step=0.25,
                    format="%.2f",
                    key=prefix + day + "_Vacation",
                    help="Paid vacation hours for this day. 0 to 24.",
                )
            with leave_sick:
                saved_sick = timesheet_leave_hours(_saved(timesheet_day_column(day, "Sick Hours")))
                if saved_sick < 0:
                    saved_sick = 0.0
                if saved_sick > TIMESHEET_LEAVE_HOURS_MAX:
                    saved_sick = float(TIMESHEET_LEAVE_HOURS_MAX)
                st.number_input(
                    "Sick Hours",
                    min_value=0.0,
                    max_value=float(TIMESHEET_LEAVE_HOURS_MAX),
                    value=float(saved_sick),
                    step=0.25,
                    format="%.2f",
                    key=prefix + day + "_Sick",
                    help="Paid sick hours for this day. 0 to 24.",
                )
            st.text_input("Perdiem Rate", value=_saved(timesheet_day_column(day, "Perdiem Rate")), key=prefix + day + "_Perdiem")
            st.text_input("Other", value=_saved(timesheet_day_column(day, "Other")), key=prefix + day + "_Other")

    def _live_hour_record():
        live = {}
        for day_name in TIMESHEET_DAYS:
            live[timesheet_day_column(day_name, "CVH Hours")] = st.session_state.get(
                prefix + day_name + "_CVH", _saved(timesheet_day_column(day_name, "CVH Hours")),
            )
            live[timesheet_day_column(day_name, "Forestry Hours")] = st.session_state.get(
                prefix + day_name + "_Forestry", _saved(timesheet_day_column(day_name, "Forestry Hours")),
            )
            live[timesheet_day_column(day_name, "BNSF Hours")] = st.session_state.get(
                prefix + day_name + "_BNSF", _saved(timesheet_day_column(day_name, "BNSF Hours")),
            )
            live[timesheet_day_column(day_name, "Vacation Hours")] = st.session_state.get(
                prefix + day_name + "_Vacation",
                timesheet_leave_hours(_saved(timesheet_day_column(day_name, "Vacation Hours"))),
            )
            live[timesheet_day_column(day_name, "Sick Hours")] = st.session_state.get(
                prefix + day_name + "_Sick",
                timesheet_leave_hours(_saved(timesheet_day_column(day_name, "Sick Hours"))),
            )
        return live

    for line in timesheet_hour_total_lines(_live_hour_record()):
        st.markdown("**" + line + "**")
    st.caption(
        "Worked hours are CVH, Forestry, and BNSF only. Vacation and sick are paid leave, "
        "0 to 24 hours a day, and are not included in worked hours. "
        "Total hours including paid leave adds them on."
    )

    saved_trips = timesheet_structured_mileage_trips(saved) if saved else []
    if saved and not saved_trips and any(_saved(key) for key in (
        "Mileage Start", "Mileage End", "Mileage Miles", "Mileage Rate", "Mileage Amount",
    )):
        saved_trips = [{
            "Travel Date": "",
            "Start Location": _saved("Mileage Start"),
            "End Location": _saved("Mileage End"),
            "Miles": _saved("Mileage Miles"),
            "Rate": _saved("Mileage Rate"),
            "Amount": _saved("Mileage Amount"),
            "Rate Source": TIMESHEET_MILEAGE_SOURCE_SAVED,
            "Company Override": "",
        }]
    count_key = "ts_mileage_count_" + employee + "_" + week.isoformat()
    if st.session_state.get(count_key) is None:
        st.session_state[count_key] = max(len(saved_trips), 1)

    st.markdown("**Mileage Reimbursement  (prior approval required)**")
    st.caption(timesheet_mileage_help_caption())
    week_date_options = [""] + [day.isoformat() for day in dates] + ["Other date"]
    trip_count = int(st.session_state.get(count_key) or 1)
    for i in range(trip_count):
        trip_saved = saved_trips[i] if i < len(saved_trips) else {}
        with st.expander("Mileage trip " + str(i + 1), expanded=True):
            saved_date = _cell(trip_saved.get("Travel Date"))
            if saved_date and saved_date not in week_date_options:
                default_choice = "Other date"
            elif saved_date in week_date_options:
                default_choice = saved_date
            else:
                default_choice = ""
            choice_key = prefix + "trip" + str(i) + "_date_choice"
            choice = st.selectbox(
                "Travel date",
                week_date_options,
                index=week_date_options.index(default_choice),
                key=choice_key,
            )
            travel = ""
            if choice == "Other date":
                other_default = parse_equipment_date(saved_date) or week
                other = st.date_input(
                    "Other travel date",
                    value=other_default,
                    format="YYYY-MM-DD",
                    key=prefix + "trip" + str(i) + "_other_date",
                )
                travel = format_equipment_date(other)
            elif choice:
                travel = choice
            if travel:
                irs_rate = timesheet_irs_business_mileage_rate(travel)
                if irs_rate is not None:
                    st.caption(
                        "IRS business rate for " + travel + ": $"
                        + timesheet_format_mileage_rate(irs_rate) + " per mile."
                    )
                else:
                    st.warning(timesheet_irs_mileage_unsupported_reason(travel))
            elif _cell(trip_saved.get("Rate Source")) == TIMESHEET_MILEAGE_SOURCE_SAVED and _cell(trip_saved.get("Rate")):
                st.caption(
                    "Previously saved rate: $" + _cell(trip_saved.get("Rate"))
                    + "/mile. Enter a travel date to apply the IRS rate for that date, "
                    "or a company mileage rate override."
                )
            st.text_input(
                "Start Location",
                value=_cell(trip_saved.get("Start Location")),
                key=prefix + "trip" + str(i) + "_start",
            )
            st.text_input(
                "End Location",
                value=_cell(trip_saved.get("End Location")),
                key=prefix + "trip" + str(i) + "_end",
            )
            override_default = ""
            if _cell(trip_saved.get("Rate Source")) == TIMESHEET_MILEAGE_SOURCE_COMPANY:
                override_default = _cell(trip_saved.get("Company Override") or trip_saved.get("Rate"))
            miles_now = st.text_input(
                "# of miles",
                value=_cell(trip_saved.get("Miles")),
                key=prefix + "trip" + str(i) + "_miles",
            )
            override_now = st.text_input(
                "Company mileage rate override (optional, not the IRS rate)",
                value=override_default,
                key=prefix + "trip" + str(i) + "_override",
            )
            live_rate = timesheet_parse_number(override_now)
            live_source = TIMESHEET_MILEAGE_SOURCE_COMPANY if live_rate is not None else ""
            if live_rate is None and travel:
                live_rate = timesheet_irs_business_mileage_rate(travel)
                if live_rate is not None:
                    live_source = TIMESHEET_MILEAGE_SOURCE_IRS
            if live_rate is None and _cell(trip_saved.get("Rate")) and not travel and not _cell(override_now):
                live_rate = timesheet_parse_number(trip_saved.get("Rate"))
                live_source = TIMESHEET_MILEAGE_SOURCE_SAVED
            live_amount = timesheet_mileage_amount(st.session_state.get(prefix + "trip" + str(i) + "_miles"), live_rate)
            st.text_input(
                "Mileage amount $",
                value=timesheet_format_money(live_amount) if live_amount is not None else "",
                disabled=True,
                key=prefix + "trip" + str(i) + "_amount_show",
            )
            if live_source and live_rate is not None:
                st.caption("Using " + live_source + " rate $" + timesheet_format_mileage_rate(live_rate) + "/mile.")
    add1, add2 = st.columns(2)
    with add1:
        if st.button("Add another mileage trip", key=prefix + "add_trip", use_container_width=True):
            st.session_state[count_key] = trip_count + 1
            st.rerun()
    with add2:
        if trip_count > 1 and st.button("Remove last mileage trip", key=prefix + "remove_trip", use_container_width=True):
            st.session_state[count_key] = trip_count - 1
            st.rerun()

    st.markdown("**Other Reimbursements**")
    st.caption("Receipts must be attached for reimbursement with description on receipt")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.text_input("Parts $", value=_saved("Parts"), key=prefix + "parts")
    with r2:
        st.text_input("Fuel $", value=_saved("Fuel"), key=prefix + "fuel")
    with r3:
        st.text_input("Other $", value=_saved("Other Reimb"), key=prefix + "other_reimb")
    live_reimb = timesheet_reimb_total(
        st.session_state.get(prefix + "parts"),
        st.session_state.get(prefix + "fuel"),
        st.session_state.get(prefix + "other_reimb"),
    )
    with r4:
        st.text_input(
            "Total $",
            value=timesheet_format_money(live_reimb) if prefix + "parts" in st.session_state else _saved("Reimb Total"),
            disabled=True,
            key=prefix + "reimb_total_show",
        )

    st.text_area("Comments", value=_saved("Comments"), key=prefix + "comments")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.text_input("Employee Signature", value=_saved("Signature"), key=prefix + "signature")
    with s2:
        sig_date = parse_equipment_date(_saved("Signature Date")) or today
        st.date_input("Date", value=sig_date, format="YYYY-MM-DD", key=prefix + "sig_date")
    with s3:
        st.text_input("Initials (required before email)", value=_saved("Initials"), key=prefix + "initials")

    def _form_record(initials=None):
        day_values = {}
        for day in TIMESHEET_DAYS:
            day_values[day] = {
                "Location": st.session_state.get(prefix + day + "_Location", ""),
                "CVH Hours": st.session_state.get(prefix + day + "_CVH", ""),
                "Forestry Hours": st.session_state.get(prefix + day + "_Forestry", ""),
                "BNSF Hours": st.session_state.get(prefix + day + "_BNSF", ""),
                "Vacation Hours": st.session_state.get(prefix + day + "_Vacation", 0),
                "Sick Hours": st.session_state.get(prefix + day + "_Sick", 0),
                "Perdiem Rate": st.session_state.get(prefix + day + "_Perdiem", ""),
                "Other": st.session_state.get(prefix + day + "_Other", ""),
            }
        trips = []
        for i in range(int(st.session_state.get(count_key) or 1)):
            choice = st.session_state.get(prefix + "trip" + str(i) + "_date_choice", "")
            if choice == "Other date":
                travel = format_equipment_date(st.session_state.get(prefix + "trip" + str(i) + "_other_date"))
            else:
                travel = _cell(choice)
            trips.append({
                "Travel Date": travel,
                "Start Location": st.session_state.get(prefix + "trip" + str(i) + "_start", ""),
                "End Location": st.session_state.get(prefix + "trip" + str(i) + "_end", ""),
                "Miles": st.session_state.get(prefix + "trip" + str(i) + "_miles", ""),
                "Company Override": st.session_state.get(prefix + "trip" + str(i) + "_override", ""),
            })
        filled = [trip for trip in trips if not timesheet_mileage_trip_is_blank(trip)]
        legacy_saved = bool(saved and not timesheet_structured_mileage_trips(saved))
        use_legacy = (
            len(filled) == 1
            and not _cell(filled[0].get("Travel Date"))
            and not _cell(filled[0].get("Company Override"))
            and legacy_saved
        )
        if use_legacy:
            return build_timesheet_record(
                employee,
                week,
                day_values=day_values,
                mileage_start=filled[0].get("Start Location", ""),
                mileage_end=filled[0].get("End Location", ""),
                mileage_miles=filled[0].get("Miles", ""),
                mileage_rate=_saved("Mileage Rate"),
                parts=st.session_state.get(prefix + "parts", ""),
                fuel=st.session_state.get(prefix + "fuel", ""),
                other_reimb=st.session_state.get(prefix + "other_reimb", ""),
                comments=st.session_state.get(prefix + "comments", ""),
                signature=st.session_state.get(prefix + "signature", ""),
                signature_date=st.session_state.get(prefix + "sig_date"),
                initials=initials if initials is not None else st.session_state.get(prefix + "initials", ""),
                today=today,
            )
        return build_timesheet_record(
            employee,
            week,
            day_values=day_values,
            mileage_trips=trips,
            parts=st.session_state.get(prefix + "parts", ""),
            fuel=st.session_state.get(prefix + "fuel", ""),
            other_reimb=st.session_state.get(prefix + "other_reimb", ""),
            comments=st.session_state.get(prefix + "comments", ""),
            signature=st.session_state.get(prefix + "signature", ""),
            signature_date=st.session_state.get(prefix + "sig_date"),
            initials=initials if initials is not None else st.session_state.get(prefix + "initials", ""),
            today=today,
        )

    try:
        preview = _form_record()
        form_ok = True
        form_error = ""
    except Exception as exc:
        preview = None
        form_ok = False
        form_error = str(exc)

    if form_ok and preview:
        if timesheet_initials_match_current(saved, preview):
            st.success("Initialed for this week's current time-sheet content: " + _cell((saved or preview).get("Initials")))
        elif saved and timesheet_initials_valid(saved):
            st.warning("Time-sheet content changed since the last initials. Save the week again with initials to re-initial.")
        else:
            st.info("Initial this week before email. Initials no longer count if the time sheet changes after you save.")

    if st.button("Save week", type="primary", key=prefix + "save", use_container_width=True):
        try:
            record = _form_record()
            save_timesheet_record(record)
        except Exception as exc:
            st.error("Could not save time sheet: " + str(exc))
        else:
            st.session_state["timesheet_gen_" + employee] = gen + 1
            st.session_state["timesheet_saved_" + employee] = "Saved time sheet for week of " + week.isoformat() + "."
            st.rerun()

    if form_ok and preview:
        pdf_bytes = build_timesheet_pdf(preview)
        xlsx_bytes = build_timesheet_xlsx(preview)
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=timesheet_pdf_filename(preview),
                mime="application/pdf",
                use_container_width=True,
                key=prefix + "pdf",
            )
        with d2:
            st.download_button(
                "Download Excel",
                data=xlsx_bytes,
                file_name=timesheet_xlsx_filename(preview),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=prefix + "xlsx",
            )
    elif form_error:
        st.error(form_error)

    st.button(
        "Email to patti@centralvalleyheli.com",
        disabled=True,
        use_container_width=True,
        key=prefix + "email",
    )
    st.caption(timesheet_email_block_reason(preview if form_ok else None))


def show_employees_page():
    """Employee buttons at the top, Calendar below, and per-person pages."""
    selected = _cell(st.session_state.get("employees_selected"))
    show_cal = bool(st.session_state.get("employees_show_calendar"))
    names = list(EMPLOYEES)
    for i in range(0, len(names), 2):
        cols = st.columns(2)
        for col, name in zip(cols, names[i:i + 2]):
            with col:
                shown = ("● " + name) if selected == name else name
                if st.button(shown, key=employee_button_key(name), use_container_width=True, type="primary"):
                    st.session_state.employees_selected = name
                    st.session_state.employees_show_calendar = False
                    st.rerun()

    cal_label = "● Calendar" if show_cal else "Calendar"
    if st.button(cal_label, key="employees_calendar", use_container_width=True, type="primary"):
        st.session_state.employees_show_calendar = True
        st.session_state.employees_selected = None
        st.rerun()

    if show_cal:
        show_time_off_calendar_page()
        return

    if selected:
        st.title(selected)
        if st.button("Back", key="employees_back", use_container_width=True):
            st.session_state.employees_selected = None
            st.rerun()
        if employee_has_anthony_timesheet(selected):
            show_anthony_timesheet(selected)
        elif employee_has_timesheet(selected):
            show_employee_timesheet(selected)
        return

    st.title("Employees")

YEARLY_ITEMS_SHEET_TITLE = "Yearly Items"
YEARLY_ITEMS_COLUMNS = [
    "Timestamp", "Year", "Group", "Item", "Date Done", "Done By", "Notes",
]
# Groups and items in Ron's order. Add items to a group's tuple to extend it.
YEARLY_ITEM_GROUPS = (
    ("Winterizing", (
        "Office irrigation system",
        "Trucks",
        "Rinse Pad",
        "Pod",
        "Heli hauler",
        "Bounder",
    )),
    ("Fuel Systems", (
        "Tanks",
    )),
    # Placeholder item until Ron lists the rest of this group.
    ("Annual Policies & Procedures (SMS)", (
        "Annual SMS policies & procedures review",
    )),
    # A (heading, items) tuple shows a subheading; stored Item names stay as written.
    ("Training", (
        "WPS Mixer/Loader",
        ("Pilot Training", (
            "Pilot Training - N480ML",
            "Pilot Training - N893PC",
        )),
    )),
)


# Add a dict to this list to show another aircraft on the DOM page.
DOM_AIRCRAFT = [
    {"id": "N893PC"},
    {"id": "N480ML"},
]
DOM_ACTION_ANNUAL = "Annual/100 Hr"


def aircraft_maint_profile(aircraft_id):
    """Return the per-aircraft Annual/100 Hr profile, or None for a placeholder."""
    return AIRCRAFT_MAINT_PROFILES.get(_cell(aircraft_id))


def parse_hobbs(value):
    """Parse a Hobbs reading. Blank stays blank; unparseable is ignored."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text_value = _cell(value).replace(",", "")
    if not text_value:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


def format_hobbs(value):
    number = parse_hobbs(value)
    if number is None:
        return ""
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return ("%.4f" % number).rstrip("0").rstrip(".")


def next_hobbs(last, interval):
    last_n = parse_hobbs(last)
    if last_n is None or interval is None:
        return None
    try:
        return last_n + float(interval)
    except (TypeError, ValueError):
        return None


def hobbs_flag(current, next_value, amber_hours=10):
    """'expired' if hobbs >= next, 'soon' if within amber_hours of next, 'ok' if earlier; None if blank."""
    cur = parse_hobbs(current)
    nxt = parse_hobbs(next_value)
    if cur is None or nxt is None:
        return None
    if cur >= nxt:
        return "expired"
    try:
        window = float(amber_hours)
    except (TypeError, ValueError):
        window = 10
    if cur >= nxt - window:
        return "soon"
    return "ok"


def hobbs_status_markup(label, next_value, current, amber_hours=10):
    """Colored next-Hobbs text: red due, amber within the window, green otherwise, gray if blank."""
    nxt = parse_hobbs(next_value)
    kind = hobbs_flag(current, nxt, amber_hours)
    if nxt is None:
        body = "Not set"
        kind = None
    else:
        body = format_hobbs(nxt)
        if kind == "expired":
            body += " — due"
        elif kind == "soon":
            hours = format_hobbs(amber_hours) or "10"
            body += " — within " + hours + " hours"
    color = DATE_STATUS_COLORS[kind]
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return kind, "**" + label + ":** <span style='color:" + color + "; font-weight:600'>" + safe + "</span>"


def ensure_aircraft_maint_worksheet(spreadsheet):
    """Create the Aircraft Maint tab with a header when it is missing.

    Existing headers are left in place; any newly added columns are appended
    on the right. Never writes FRAT, Equipment, Squawks, or Safety Meetings.
    """
    cols = list(AIRCRAFT_MAINT_COLUMNS)
    ws = _worksheet_or_none(spreadsheet, AIRCRAFT_MAINT_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=AIRCRAFT_MAINT_SHEET_TITLE, rows=200, cols=max(len(cols), 8))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
        else:
            missing = [col for col in cols if col not in header]
            if missing:
                start = len(header) + 1
                for offset, col in enumerate(missing):
                    ws.update_cell(1, start + offset, col)
    return ws, created


def load_aircraft_maint_records(spreadsheet=None, aircraft_id=None):
    ws, _created = ensure_aircraft_maint_worksheet(spreadsheet or _gsheets_spreadsheet())
    records = records_from_worksheet(ws, AIRCRAFT_MAINT_COLUMNS)
    if aircraft_id:
        wanted = _cell(aircraft_id)
        records = [r for r in records if _cell(r.get("Aircraft")) == wanted]
    return records


def latest_aircraft_maint_record(records):
    if not records:
        return None
    return max(records, key=_safety_meeting_sort_key)


def build_aircraft_maint_record(
    aircraft_id, entry_date, hobbs, last_100, annual_due, last_oil, entered_by,
    when=None, profile=None,
):
    aircraft_id = _cell(aircraft_id)
    profile = profile or aircraft_maint_profile(aircraft_id)
    if not profile:
        raise ValueError("No maintenance profile for that aircraft")
    next_100 = next_hobbs(last_100, profile.get("hundred_hr_interval"))
    next_oil = next_hobbs(last_oil, profile.get("oil_interval"))
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Aircraft": aircraft_id,
        "Entry Date": format_equipment_date(entry_date),
        "Hobbs": format_hobbs(hobbs),
        "Last 100 Hr": format_hobbs(last_100),
        "Next 100 Hr": format_hobbs(next_100),
        "Annual Due Date": format_equipment_date(annual_due),
        "Last Oil Change": format_hobbs(last_oil),
        "Next Oil Change": format_hobbs(next_oil),
        "Entered By": _cell(entered_by),
    }


def save_aircraft_maint_record(record, spreadsheet=None):
    """Append one maintenance entry to the Aircraft Maint tab only."""
    ws, _created = ensure_aircraft_maint_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Aircraft Maint worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Aircraft Maint)"


def clear_aircraft_maint_widgets(aircraft_id):
    aid = _cell(aircraft_id)
    if not aid:
        return
    for suffix in ("date", "hobbs", "last100", "annual", "lastoil", "entered_by"):
        st.session_state.pop("maint_" + suffix + "_" + aid, None)


def show_aircraft_annual_page(aircraft_id, profile, spreadsheet=None):
    """Phone-friendly Annual/100 Hr form for one aircraft, with latest values and history."""
    aid = _cell(aircraft_id)
    st.title("DOM")
    st.subheader(DOM_ACTION_ANNUAL + " — " + aid)
    if st.button("Back", key="dom_annual_back", use_container_width=True):
        clear_aircraft_maint_widgets(aid)
        st.session_state.dom_annual_aircraft = None
        st.rerun()

    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    amber_hours = profile.get("amber_hours", 10)
    try:
        spreadsheet = spreadsheet or _gsheets_spreadsheet()
        history = load_aircraft_maint_records(spreadsheet, aircraft_id=aid)
    except Exception as exc:
        st.error(f"Could not load aircraft maintenance: {exc}")
        return
    latest = latest_aircraft_maint_record(history)

    if st.session_state.get("aircraft_maint_saved"):
        st.success(st.session_state.pop("aircraft_maint_saved"))

    st.markdown("**Latest values**")
    if not latest:
        st.caption("No entries yet for this aircraft.")
    else:
        current = latest.get("Hobbs")
        _kind, markup = hobbs_status_markup("Next 100 Hr", latest.get("Next 100 Hr"), current, amber_hours)
        st.markdown(markup, unsafe_allow_html=True)
        _kind, markup = hobbs_status_markup("Next Oil Change", latest.get("Next Oil Change"), current, amber_hours)
        st.markdown(markup, unsafe_allow_html=True)
        _kind, markup = date_status_markup(
            "Annual Due Date", latest.get("Annual Due Date"),
            parse_equipment_date(latest.get("Annual Due Date")), today,
        )
        st.markdown(markup, unsafe_allow_html=True)
        bits = []
        if _cell(latest.get("Entry Date")):
            bits.append("Entry Date " + _cell(latest.get("Entry Date")))
        if _cell(latest.get("Hobbs")):
            bits.append("Current Hobbs " + _cell(latest.get("Hobbs")))
        if _cell(latest.get("Last 100 Hr")):
            bits.append("Last 100 Hr " + _cell(latest.get("Last 100 Hr")))
        if _cell(latest.get("Last Oil Change")):
            bits.append("Last Oil Change " + _cell(latest.get("Last Oil Change")))
        if _cell(latest.get("Entered By")):
            bits.append("Entered By " + _cell(latest.get("Entered By")))
        if bits:
            st.caption(" · ".join(bits))

    def _init(key, value):
        if key not in st.session_state:
            st.session_state[key] = value

    _init("maint_date_" + aid, today)
    st.date_input("Date", format="YYYY-MM-DD", key="maint_date_" + aid)
    _init("maint_hobbs_" + aid, _cell(latest.get("Hobbs")) if latest else "")
    st.text_input("Current Hobbs", key="maint_hobbs_" + aid)
    _init("maint_last100_" + aid, _cell(latest.get("Last 100 Hr")) if latest else "")
    st.text_input("Last 100 Hr (Hobbs)", key="maint_last100_" + aid)
    computed_100 = next_hobbs(st.session_state.get("maint_last100_" + aid), profile.get("hundred_hr_interval"))
    _kind, markup = hobbs_status_markup(
        "Next 100 Hr", computed_100, st.session_state.get("maint_hobbs_" + aid), amber_hours,
    )
    st.markdown(markup, unsafe_allow_html=True)
    _init(
        "maint_annual_" + aid,
        parse_equipment_date(latest.get("Annual Due Date")) if latest else None,
    )
    st.date_input("Annual Due Date", format="YYYY-MM-DD", key="maint_annual_" + aid)
    _init("maint_lastoil_" + aid, _cell(latest.get("Last Oil Change")) if latest else "")
    st.text_input("Last Oil Change (Hobbs)", key="maint_lastoil_" + aid)
    computed_oil = next_hobbs(st.session_state.get("maint_lastoil_" + aid), profile.get("oil_interval"))
    _kind, markup = hobbs_status_markup(
        "Next Oil Change", computed_oil, st.session_state.get("maint_hobbs_" + aid), amber_hours,
    )
    st.markdown(markup, unsafe_allow_html=True)
    recorded_options = [""] + list(REPORTERS)
    default_entered = _cell(latest.get("Entered By")) if latest else ""
    if default_entered and default_entered not in recorded_options:
        recorded_options = [default_entered] + recorded_options
    _init("maint_entered_by_" + aid, default_entered if default_entered in recorded_options else "")
    st.selectbox("Entered By", recorded_options, key="maint_entered_by_" + aid)

    if st.button("Save", type="primary", key="maint_save_" + aid, use_container_width=True):
        record = build_aircraft_maint_record(
            aid,
            st.session_state.get("maint_date_" + aid),
            st.session_state.get("maint_hobbs_" + aid),
            st.session_state.get("maint_last100_" + aid),
            st.session_state.get("maint_annual_" + aid),
            st.session_state.get("maint_lastoil_" + aid),
            st.session_state.get("maint_entered_by_" + aid, ""),
            profile=profile,
        )
        try:
            save_aircraft_maint_record(record, spreadsheet=spreadsheet)
        except Exception as exc:
            st.error(f"Could not save aircraft maintenance: {exc}")
        else:
            clear_aircraft_maint_widgets(aid)
            st.session_state.aircraft_maint_saved = "Saved " + DOM_ACTION_ANNUAL + " entry for " + aid + "."
            st.rerun()

    st.markdown("---")
    st.subheader("History")
    if not history:
        st.info("No maintenance entries recorded for this aircraft.")
        return
    for item in sorted(history, key=_safety_meeting_sort_key, reverse=True):
        stamp = _cell(item.get("Timestamp"))
        entry_date = _cell(item.get("Entry Date")) or "Entry"
        title = entry_date
        if _cell(item.get("Hobbs")):
            title = title + " — Hobbs " + _cell(item.get("Hobbs"))
        if stamp:
            title = title + "  (" + stamp + ")"
        with st.expander(title):
            lines = [
                ("Entry Date", item.get("Entry Date")),
                ("Current Hobbs", item.get("Hobbs")),
                ("Last 100 Hr", item.get("Last 100 Hr")),
                ("Next 100 Hr", item.get("Next 100 Hr")),
                ("Annual Due Date", item.get("Annual Due Date")),
                ("Last Oil Change", item.get("Last Oil Change")),
                ("Next Oil Change", item.get("Next Oil Change")),
                ("Entered By", item.get("Entered By")),
            ]
            for label, raw in lines:
                st.markdown("**" + label + ":** " + (_cell(raw) if _cell(raw) else "—"))


def grease_offsets_for(profile):
    offsets = (profile or {}).get("grease_offsets") or ()
    return tuple(int(offset) for offset in offsets)


def grease_checkpoint_label(offset):
    return str(int(offset)) + " Hr"


def grease_checkpoint_columns(offset):
    label = str(int(offset))
    return (
        "Grease " + label + " Done",
        "Grease " + label + " Initials",
        "Grease " + label + " Hobbs/Date",
    )


def n480ml_maint_columns(offsets=None):
    cols = [
        "Timestamp", "Aircraft", "Entry Date", "Hobbs",
        "Last 100 Hr", "Next 100 Hr", "Grease Hobbs",
    ]
    for offset in (offsets or GREASE_CHECKPOINT_OFFSETS):
        cols.extend(grease_checkpoint_columns(offset))
    cols.append("Entered By")
    return cols


def grease_due_hobbs(grease_hobbs, offset):
    return next_hobbs(grease_hobbs, offset)


def grease_amber_hours(profile=None):
    """Grease checkpoints turn amber within 2 hours, not the 10-hour 100 Hr window."""
    raw = (profile or {}).get("grease_amber_hours", GREASE_AMBER_HOURS)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(GREASE_AMBER_HOURS)


def format_grease_hobbs_date(hobbs, when):
    """Store 'Hobbs / YYYY-MM-DD' in the checkpoint Hobbs/Date column."""
    if hasattr(when, "strftime"):
        if hasattr(when, "date"):
            try:
                date_text = format_equipment_date(when.date())
            except Exception:
                date_text = format_equipment_date(when)
        else:
            date_text = format_equipment_date(when)
    else:
        date_text = format_equipment_date(when)
    hobbs_text = format_hobbs(hobbs)
    if hobbs_text and date_text:
        return hobbs_text + " / " + date_text
    return hobbs_text or date_text or ""


def is_grease_checkpoint_done(record, offset):
    done_col, _initials_col, _when_col = grease_checkpoint_columns(offset)
    return _cell((record or {}).get(done_col)).lower() in {"yes", "y", "true", "1"}


def grease_done_markup(label, record, offset):
    """Gray completed checkpoint: check mark, initials, and Hobbs/date when greased."""
    _done_col, initials_col, when_col = grease_checkpoint_columns(offset)
    initials = _cell((record or {}).get(initials_col))
    when_text = _cell((record or {}).get(when_col))
    body = "✓ Done"
    if initials:
        body += " — " + initials
    if when_text:
        body += " (" + when_text + ")"
    color = DATE_STATUS_COLORS[None]
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "**" + label + ":** <span style='color:" + color + "; font-weight:600'>" + safe + "</span>"


def ensure_n480ml_maint_worksheet(spreadsheet):
    """Create the N480ML Maint tab with a header when it is missing.

    Never alters an existing header, and never writes Aircraft Maint, FRAT,
    Equipment, Squawks, or Safety Meetings.
    """
    cols = n480ml_maint_columns()
    ws = _worksheet_or_none(spreadsheet, N480ML_MAINT_SHEET_TITLE)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=N480ML_MAINT_SHEET_TITLE, rows=200, cols=max(len(cols), 8))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
    return ws, created


def load_n480ml_maint_records(spreadsheet=None):
    ws, _created = ensure_n480ml_maint_worksheet(spreadsheet or _gsheets_spreadsheet())
    records = records_from_worksheet(ws, n480ml_maint_columns())
    return [r for r in records if _cell(r.get("Aircraft")) in {"", "N480ML"}]


def build_n480ml_maint_record(
    entry_date, hobbs, last_100, grease_hobbs, entered_by,
    checkpoints=None, when=None, profile=None,
):
    profile = profile or aircraft_maint_profile("N480ML")
    if not profile or not grease_offsets_for(profile):
        raise ValueError("No N480ML grease maintenance profile")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    record = {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Aircraft": "N480ML",
        "Entry Date": format_equipment_date(entry_date),
        "Hobbs": format_hobbs(hobbs),
        "Last 100 Hr": format_hobbs(last_100),
        "Next 100 Hr": format_hobbs(next_hobbs(last_100, profile.get("hundred_hr_interval"))),
        "Grease Hobbs": format_hobbs(grease_hobbs),
        "Entered By": _cell(entered_by),
    }
    states = checkpoints or {}
    for offset in grease_offsets_for(profile):
        done_col, initials_col, when_col = grease_checkpoint_columns(offset)
        state = states.get(offset) or states.get(str(offset)) or {}
        initials = _cell(state.get("initials"))
        done = state.get("done") in (True, "Yes", "yes", "Y", "y", "1", "true", "True")
        record[done_col] = ""
        record[initials_col] = ""
        record[when_col] = ""
        if done:
            record[done_col] = "Yes"
            record[initials_col] = initials
            record[when_col] = format_grease_hobbs_date(
                state.get("hobbs", hobbs), state.get("when", when),
            )
    return record


def save_n480ml_maint_record(record, spreadsheet=None):
    """Append one N480ML maintenance entry to the N480ML Maint tab only."""
    ws, _created = ensure_n480ml_maint_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("N480ML Maint worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (N480ML Maint)"


def update_n480ml_grease_checkpoint(timestamp, offset, initials, hobbs, when=None, spreadsheet=None):
    """Mark one grease checkpoint on the matching row only. Never other tabs or the header."""
    timestamp = _cell(timestamp)
    initials = _cell(initials)
    if not timestamp:
        raise ValueError("Timestamp is required")
    if not initials:
        raise ValueError("Initials are required to mark a grease checkpoint")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    done_col, initials_col, when_col = grease_checkpoint_columns(offset)
    ws, _created = ensure_n480ml_maint_worksheet(spreadsheet or _gsheets_spreadsheet())
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("N480ML Maint worksheet has no header")
    header = [_cell(c) for c in values[0]]
    try:
        ts_idx = header.index("Timestamp")
        done_number = header.index(done_col) + 1
        initials_number = header.index(initials_col) + 1
        when_number = header.index(when_col) + 1
    except ValueError as exc:
        raise RuntimeError("N480ML Maint worksheet is missing required columns") from exc
    for row_number, row in enumerate(values[1:], start=2):
        row_ts = _cell(row[ts_idx]) if ts_idx < len(row) else ""
        if row_ts != timestamp:
            continue
        ws.update_cell(row_number, done_number, "Yes")
        ws.update_cell(row_number, initials_number, initials)
        ws.update_cell(row_number, when_number, format_grease_hobbs_date(hobbs, when))
        return True
    raise RuntimeError("Could not find that N480ML maintenance entry")


def clear_n480ml_maint_widgets():
    aid = "N480ML"
    for suffix in ("date", "hobbs", "last100", "grease", "entered_by"):
        st.session_state.pop("n480_" + suffix + "_" + aid, None)
    profile = aircraft_maint_profile(aid) or {}
    for offset in grease_offsets_for(profile) or GREASE_CHECKPOINT_OFFSETS:
        for prefix in ("n480_greased_", "n480_initials_", "n480_latest_greased_", "n480_latest_initials_"):
            st.session_state.pop(prefix + str(int(offset)) + "_" + aid, None)


def show_n480ml_annual_page(profile, spreadsheet=None):
    """Phone-friendly N480ML Annual/100 Hr + grease cycle form."""
    aid = "N480ML"
    amber_hours = profile.get("amber_hours", 10)
    offsets = grease_offsets_for(profile)
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    st.title("DOM")
    st.subheader(DOM_ACTION_ANNUAL + " — " + aid)
    if st.button("Back", key="dom_annual_back", use_container_width=True):
        clear_n480ml_maint_widgets()
        st.session_state.dom_annual_aircraft = None
        st.rerun()

    try:
        spreadsheet = spreadsheet or _gsheets_spreadsheet()
        history = load_n480ml_maint_records(spreadsheet)
    except Exception as exc:
        st.error(f"Could not load N480ML maintenance: {exc}")
        return
    latest = latest_aircraft_maint_record(history)

    if st.session_state.get("n480ml_maint_saved"):
        st.success(st.session_state.pop("n480ml_maint_saved"))
    if st.session_state.get("n480ml_grease_saved"):
        st.success(st.session_state.pop("n480ml_grease_saved"))

    def _init(key, value):
        if key not in st.session_state:
            st.session_state[key] = value

    st.markdown("**Latest values**")
    if not latest:
        st.caption("No entries yet for this aircraft.")
    else:
        current = latest.get("Hobbs")
        _kind, markup = hobbs_status_markup("Next 100 Hr", latest.get("Next 100 Hr"), current, amber_hours)
        st.markdown(markup, unsafe_allow_html=True)
        grease_hobbs = latest.get("Grease Hobbs")
        st.markdown("**Grease Hobbs:** " + (format_hobbs(grease_hobbs) or "—"))
        bits = []
        if _cell(latest.get("Entry Date")):
            bits.append("Entry Date " + _cell(latest.get("Entry Date")))
        if _cell(latest.get("Hobbs")):
            bits.append("Current Hobbs " + _cell(latest.get("Hobbs")))
        if _cell(latest.get("Last 100 Hr")):
            bits.append("Last 100 Hr " + _cell(latest.get("Last 100 Hr")))
        if _cell(latest.get("Entered By")):
            bits.append("Entered By " + _cell(latest.get("Entered By")))
        if bits:
            st.caption(" · ".join(bits))
        pending = False
        for offset in offsets:
            label = grease_checkpoint_label(offset)
            if is_grease_checkpoint_done(latest, offset):
                st.markdown(grease_done_markup(label, latest, offset), unsafe_allow_html=True)
                continue
            due = grease_due_hobbs(grease_hobbs, offset)
            _kind, markup = hobbs_status_markup(label, due, current, grease_amber_hours(profile))
            st.markdown(markup, unsafe_allow_html=True)
            st.checkbox("Greased", key="n480_latest_greased_" + str(int(offset)) + "_" + aid)
            st.text_input("Initials", key="n480_latest_initials_" + str(int(offset)) + "_" + aid)
            pending = True
        if pending and st.button("Save grease checks", key="n480_latest_grease_save", use_container_width=True):
            when = datetime.now(ZoneInfo("America/Los_Angeles"))
            current_hobbs = st.session_state.get("n480_hobbs_" + aid) or latest.get("Hobbs")
            errors = []
            saved_any = False
            for offset in offsets:
                if is_grease_checkpoint_done(latest, offset):
                    continue
                checked = bool(st.session_state.get("n480_latest_greased_" + str(int(offset)) + "_" + aid))
                initials = _cell(st.session_state.get("n480_latest_initials_" + str(int(offset)) + "_" + aid))
                if checked and not initials:
                    errors.append("Initials are required for " + grease_checkpoint_label(offset))
                    continue
                if not checked:
                    continue
                try:
                    update_n480ml_grease_checkpoint(
                        latest.get("Timestamp"), offset, initials, current_hobbs,
                        when=when, spreadsheet=spreadsheet,
                    )
                    saved_any = True
                except Exception as exc:
                    errors.append(str(exc))
            for msg in errors:
                st.error(msg)
            if saved_any and not errors:
                st.session_state.n480ml_grease_saved = "Saved grease checks for N480ML."
                for offset in offsets:
                    st.session_state.pop("n480_latest_greased_" + str(int(offset)) + "_" + aid, None)
                    st.session_state.pop("n480_latest_initials_" + str(int(offset)) + "_" + aid, None)
                st.rerun()

    st.markdown("---")
    st.subheader("New entry")
    st.caption("Enter a new Grease Hobbs to start a new 25 / 50 / 75 / 100 hour cycle.")
    _init("n480_date_" + aid, today)
    st.date_input("Date", format="YYYY-MM-DD", key="n480_date_" + aid)
    _init("n480_hobbs_" + aid, _cell(latest.get("Hobbs")) if latest else "")
    st.text_input("Current Hobbs", key="n480_hobbs_" + aid)
    _init("n480_last100_" + aid, _cell(latest.get("Last 100 Hr")) if latest else "")
    st.text_input("Last 100 Hr Hobbs", key="n480_last100_" + aid)
    computed_100 = next_hobbs(st.session_state.get("n480_last100_" + aid), profile.get("hundred_hr_interval"))
    _kind, markup = hobbs_status_markup(
        "Next 100 Hr", computed_100, st.session_state.get("n480_hobbs_" + aid), amber_hours,
    )
    st.markdown(markup, unsafe_allow_html=True)
    _init("n480_grease_" + aid, "")
    st.text_input("Grease Hobbs", key="n480_grease_" + aid)
    current_grease = st.session_state.get("n480_grease_" + aid)
    current_hobbs_val = st.session_state.get("n480_hobbs_" + aid)
    for offset in offsets:
        label = grease_checkpoint_label(offset)
        due = grease_due_hobbs(current_grease, offset)
        _kind, markup = hobbs_status_markup(label, due, current_hobbs_val, grease_amber_hours(profile))
        st.markdown(markup, unsafe_allow_html=True)
        st.checkbox("Greased", key="n480_greased_" + str(int(offset)) + "_" + aid)
        st.text_input("Initials", key="n480_initials_" + str(int(offset)) + "_" + aid)

    recorded_options = [""] + list(REPORTERS)
    _init("n480_entered_by_" + aid, "")
    st.selectbox("Entered By", recorded_options, key="n480_entered_by_" + aid)

    if st.button("Save", type="primary", key="n480_save_" + aid, use_container_width=True):
        when = datetime.now(ZoneInfo("America/Los_Angeles"))
        hobbs_val = st.session_state.get("n480_hobbs_" + aid)
        checkpoints = {}
        errors = []
        for offset in offsets:
            checked = bool(st.session_state.get("n480_greased_" + str(int(offset)) + "_" + aid))
            initials = _cell(st.session_state.get("n480_initials_" + str(int(offset)) + "_" + aid))
            if checked and not initials:
                errors.append("Initials are required for " + grease_checkpoint_label(offset))
                continue
            if checked:
                checkpoints[offset] = {
                    "done": True,
                    "initials": initials,
                    "hobbs": hobbs_val,
                    "when": when,
                }
        if errors:
            for msg in errors:
                st.error(msg)
        else:
            record = build_n480ml_maint_record(
                st.session_state.get("n480_date_" + aid),
                hobbs_val,
                st.session_state.get("n480_last100_" + aid),
                st.session_state.get("n480_grease_" + aid),
                st.session_state.get("n480_entered_by_" + aid, ""),
                checkpoints=checkpoints,
                when=when,
                profile=profile,
            )
            try:
                save_n480ml_maint_record(record, spreadsheet=spreadsheet)
            except Exception as exc:
                st.error(f"Could not save N480ML maintenance: {exc}")
            else:
                clear_n480ml_maint_widgets()
                st.session_state.n480ml_maint_saved = "Saved " + DOM_ACTION_ANNUAL + " entry for N480ML."
                st.rerun()

    st.markdown("---")
    st.subheader("History")
    if not history:
        st.info("No maintenance entries recorded for this aircraft.")
        return
    for item in sorted(history, key=_safety_meeting_sort_key, reverse=True):
        stamp = _cell(item.get("Timestamp"))
        entry_date = _cell(item.get("Entry Date")) or "Entry"
        title = entry_date
        if _cell(item.get("Hobbs")):
            title = title + " — Hobbs " + _cell(item.get("Hobbs"))
        if stamp:
            title = title + "  (" + stamp + ")"
        with st.expander(title):
            lines = [
                ("Entry Date", item.get("Entry Date")),
                ("Current Hobbs", item.get("Hobbs")),
                ("Last 100 Hr", item.get("Last 100 Hr")),
                ("Next 100 Hr", item.get("Next 100 Hr")),
                ("Grease Hobbs", item.get("Grease Hobbs")),
            ]
            for label, raw in lines:
                st.markdown("**" + label + ":** " + (_cell(raw) if _cell(raw) else "—"))
            for offset in offsets:
                label = grease_checkpoint_label(offset)
                if is_grease_checkpoint_done(item, offset):
                    st.markdown(grease_done_markup(label, item, offset), unsafe_allow_html=True)
                else:
                    due = grease_due_hobbs(item.get("Grease Hobbs"), offset)
                    _kind, markup = hobbs_status_markup(label, due, item.get("Hobbs"), grease_amber_hours(profile))
                    st.markdown(markup, unsafe_allow_html=True)
            if _cell(item.get("Entered By")):
                st.markdown("**Entered By:** " + _cell(item.get("Entered By")))



def load_aircraft_maint_records_readonly(spreadsheet=None, aircraft_id=None):
    """Read the Aircraft Maint tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), AIRCRAFT_MAINT_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    records = records_from_worksheet(ws, AIRCRAFT_MAINT_COLUMNS)
    if aircraft_id:
        wanted = _cell(aircraft_id)
        records = [r for r in records if _cell(r.get("Aircraft")) == wanted]
    return records


def load_n480ml_maint_records_readonly(spreadsheet=None):
    """Read the N480ML Maint tab without creating or changing it."""
    ws = _worksheet_or_none(spreadsheet or _gsheets_spreadsheet(), N480ML_MAINT_SHEET_TITLE)
    if ws is None:
        return []
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return []
    records = records_from_worksheet(ws, n480ml_maint_columns())
    return [r for r in records if _cell(r.get("Aircraft")) in {"", "N480ML"}]


def combine_maint_status(*kinds):
    """Worst of expired, soon, and ok. None if nothing can be scored."""
    rank = {"expired": 3, "soon": 2, "ok": 1}
    worst = None
    worst_rank = 0
    for kind in kinds:
        value = rank.get(kind, 0)
        if value > worst_rank:
            worst_rank = value
            worst = kind
    return worst


def n893pc_annual_status(record, today=None, profile=None):
    """Roll up N893PC 100 Hr, oil, and annual-date flags."""
    if not record:
        return None
    profile = profile or aircraft_maint_profile("N893PC") or {}
    amber = profile.get("amber_hours", 10)
    current = record.get("Hobbs")
    return combine_maint_status(
        hobbs_flag(current, record.get("Next 100 Hr"), amber),
        hobbs_flag(current, record.get("Next Oil Change"), amber),
        date_flag(parse_equipment_date(record.get("Annual Due Date")), today),
    )


def n480ml_annual_status(record, today=None, profile=None):
    """Roll up N480ML 100 Hr and undone grease checkpoints (2-hour grease window)."""
    if not record:
        return None
    profile = profile or aircraft_maint_profile("N480ML") or {}
    amber = profile.get("amber_hours", 10)
    current = record.get("Hobbs")
    kinds = [hobbs_flag(current, record.get("Next 100 Hr"), amber)]
    grease_hobbs = record.get("Grease Hobbs")
    grease_window = grease_amber_hours(profile)
    for offset in grease_offsets_for(profile):
        if is_grease_checkpoint_done(record, offset):
            continue
        kinds.append(hobbs_flag(current, grease_due_hobbs(grease_hobbs, offset), grease_window))
    return combine_maint_status(*kinds)


def aircraft_annual_status(aircraft_id, record, today=None, profile=None):
    """Overall Annual/100 Hr status for one aircraft, or None when nothing is saved."""
    profile = profile or aircraft_maint_profile(aircraft_id)
    if profile and grease_offsets_for(profile):
        return n480ml_annual_status(record, today=today, profile=profile)
    if profile:
        return n893pc_annual_status(record, today=today, profile=profile)
    return None


def aircraft_annual_button_label(status):
    if status is None:
        return DOM_ACTION_ANNUAL + " — No data"
    return DOM_ACTION_ANNUAL


def aircraft_annual_button_color(status):
    return DATE_STATUS_COLORS[status]


def load_latest_annual_record_readonly(aircraft_id, spreadsheet=None):
    profile = aircraft_maint_profile(aircraft_id)
    if profile and grease_offsets_for(profile):
        records = load_n480ml_maint_records_readonly(spreadsheet)
    elif profile:
        records = load_aircraft_maint_records_readonly(spreadsheet, aircraft_id=aircraft_id)
    else:
        return None
    return latest_aircraft_maint_record(records)


def dom_annual_statuses(spreadsheet=None, today=None):
    """Read-only Annual/100 Hr status for each DOM aircraft. Missing tabs count as no data."""
    spreadsheet = spreadsheet or _gsheets_spreadsheet()
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date()
    statuses = {}
    for aircraft in DOM_AIRCRAFT:
        aid = _cell(aircraft.get("id") or aircraft.get("name"))
        if not aid:
            continue
        latest = load_latest_annual_record_readonly(aid, spreadsheet)
        statuses[aid] = aircraft_annual_status(aid, latest, today=today)
    return statuses


def apply_dom_annual_button_styles(statuses):
    """Color each DOM Annual/100 Hr button from its status."""
    css = ["<style>"]
    for aid, status in (statuses or {}).items():
        color = aircraft_annual_button_color(status)
        key = "dom_annual_" + _cell(aid)
        css.append(
            ".st-key-" + key + " button,"
            ".st-key-" + key + " button[data-baseweb='button'][kind='primary']{"
            "background-color:" + color + " !important;"
            "color:#ffffff !important;"
            "border-color:" + color + " !important;"
            "}"
        )
    css.append("</style>")
    st.markdown("".join(css), unsafe_allow_html=True)
    return statuses


def show_dom_annual_panel(aircraft_id):
    """Open the Annual/100 Hr form when a profile exists; otherwise a placeholder."""
    profile = aircraft_maint_profile(aircraft_id)
    if profile and grease_offsets_for(profile):
        show_n480ml_annual_page(profile)
        return
    if profile:
        show_aircraft_annual_page(aircraft_id, profile)
        return
    st.title("DOM")
    st.subheader(DOM_ACTION_ANNUAL + " — " + _cell(aircraft_id))
    st.info("Coming soon - Ron to define contents")
    if st.button("Back", key="dom_annual_back", use_container_width=True):
        st.session_state.dom_annual_aircraft = None
        st.rerun()


def show_dom_page():
    """Phone-friendly DOM list: one section per aircraft, actions stacked underneath."""
    selected = _cell(st.session_state.get("dom_annual_aircraft"))
    if selected:
        show_dom_annual_panel(selected)
        return
    st.title("DOM")
    try:
        statuses = dom_annual_statuses()
    except Exception:
        statuses = None
    for aircraft in DOM_AIRCRAFT:
        aid = _cell(aircraft.get("id") or aircraft.get("name"))
        if not aid:
            continue
        name = _cell(aircraft.get("name")) or aid
        st.markdown("**" + name + "**")
        if statuses is None:
            button_label = DOM_ACTION_ANNUAL
        else:
            button_label = aircraft_annual_button_label(statuses.get(aid))
        if st.button(button_label, key="dom_annual_" + aid, use_container_width=True, type="primary"):
            st.session_state.dom_annual_aircraft = aid
            st.rerun()
    if statuses is not None:
        apply_dom_annual_button_styles(statuses)


def clear_equipment_edit_widgets(unit_id):
    """Drop edit-form widget state so the next open starts from the sheet row."""
    unit_id = _cell(unit_id)
    if not unit_id:
        return
    for suffix in (
        "type", "active", "year", "make", "vin", "plate", "notes",
        "reg", "annual", "tonnage_applies", "tonnage_expire",
    ):
        st.session_state.pop(f"edit_{suffix}_{unit_id}", None)


def show_equipment_edit_form(unit, spreadsheet):
    """Phone-friendly editor for one unit. Unit ID and Name stay read-only."""
    unit_id = _cell(unit.get("Unit ID"))
    name = _cell(unit.get("Name")) or unit_id
    st.markdown("**Unit ID:** " + (unit_id if unit_id else "—"))
    st.markdown("**Name:** " + (name if name else "—"))

    def _init(key, value):
        if key not in st.session_state:
            st.session_state[key] = value

    blank_type = "—"
    type_options = [blank_type] + [t for t in EQUIPMENT_TYPES]
    current_type = _cell(unit.get("Type"))
    if current_type and current_type not in type_options:
        type_options = [current_type] + type_options
    _init(f"edit_type_{unit_id}", current_type if current_type else blank_type)
    st.selectbox("Type", type_options, key=f"edit_type_{unit_id}")

    _init(f"edit_active_{unit_id}", "Yes" if is_active_equipment(unit) else "No")
    st.selectbox("Active", ["Yes", "No"], key=f"edit_active_{unit_id}")

    _init(f"edit_year_{unit_id}", _cell(unit.get("Year")))
    st.text_input("Year", key=f"edit_year_{unit_id}")
    _init(f"edit_make_{unit_id}", _cell(unit.get("Make/Model")))
    st.text_input("Make/Model", key=f"edit_make_{unit_id}")
    _init(f"edit_vin_{unit_id}", _cell(unit.get("VIN/Serial")))
    st.text_input("VIN/Serial", key=f"edit_vin_{unit_id}")
    _init(f"edit_plate_{unit_id}", _cell(unit.get("Plate/N-number")))
    st.text_input("Plate/N-number", key=f"edit_plate_{unit_id}")
    _init(f"edit_notes_{unit_id}", _cell(unit.get("Notes")))
    st.text_area("Notes", key=f"edit_notes_{unit_id}")

    _init(f"edit_reg_{unit_id}", parse_equipment_date(unit.get(REGISTRATION_EXPIRE_COL)))
    st.date_input("Registration Expire Date", format="YYYY-MM-DD", key=f"edit_reg_{unit_id}")
    _init(f"edit_annual_{unit_id}", parse_equipment_date(unit.get(ANNUAL_MAINT_COL)))
    st.date_input("Annual Maint Date", format="YYYY-MM-DD", key=f"edit_annual_{unit_id}")

    # Read the widget first so a toggle immediately shows or hides the expire date.
    _init(f"edit_tonnage_applies_{unit_id}", "Yes" if tonnage_applies(unit) else "No")
    applies_choice = st.selectbox(
        "Tonnage Applies",
        ["Yes", "No"],
        key=f"edit_tonnage_applies_{unit_id}",
    )
    if applies_choice == "Yes":
        _init(f"edit_tonnage_expire_{unit_id}", parse_equipment_date(unit.get(TONNAGE_EXPIRE_COL)))
        st.date_input("Tonnage Wt Expire Date", format="YYYY-MM-DD", key=f"edit_tonnage_expire_{unit_id}")

    cancel_col, save_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", key=f"equip_edit_cancel_{unit_id}", use_container_width=True):
            clear_equipment_edit_widgets(unit_id)
            st.session_state.edit_unit_id = None
            st.rerun()
    with save_col:
        if st.button("Save", type="primary", key=f"equip_edit_save_{unit_id}", use_container_width=True):
            fields = {
                "Type": ("" if st.session_state.get(f"edit_type_{unit_id}", "") == "—" else st.session_state.get(f"edit_type_{unit_id}", "")),
                "Active": st.session_state.get(f"edit_active_{unit_id}", ""),
                "Year": st.session_state.get(f"edit_year_{unit_id}", ""),
                "Make/Model": st.session_state.get(f"edit_make_{unit_id}", ""),
                "VIN/Serial": st.session_state.get(f"edit_vin_{unit_id}", ""),
                "Plate/N-number": st.session_state.get(f"edit_plate_{unit_id}", ""),
                "Notes": st.session_state.get(f"edit_notes_{unit_id}", ""),
                REGISTRATION_EXPIRE_COL: st.session_state.get(f"edit_reg_{unit_id}"),
                ANNUAL_MAINT_COL: st.session_state.get(f"edit_annual_{unit_id}"),
                TONNAGE_APPLIES_COL: st.session_state.get(f"edit_tonnage_applies_{unit_id}", ""),
            }
            if _cell(fields[TONNAGE_APPLIES_COL]).lower() in {"yes", "y", "true", "1"}:
                fields[TONNAGE_EXPIRE_COL] = st.session_state.get(f"edit_tonnage_expire_{unit_id}")
            try:
                update_equipment_record(unit_id, fields, spreadsheet=spreadsheet)
            except Exception as exc:
                st.error(f"Could not save equipment updates: {exc}")
                return
            clear_equipment_edit_widgets(unit_id)
            st.session_state.edit_unit_id = None
            if _cell(fields.get("Active")).lower() in {"no", "n", "false", "0", "inactive"}:
                st.session_state.info_unit_id = None
                st.session_state.equipment_saved = (
                    "Saved updates for " + name + ". It is now inactive and hidden from this list."
                )
            else:
                st.session_state.equipment_saved = "Saved updates for " + name + "."
            st.rerun()


def show_equipment_info(unit, squawks, spreadsheet=None):
    """Details from the Equipment tab plus this unit's squawk history. Blank fields stay blank."""
    name = _cell(unit.get("Name")) or _cell(unit.get("Unit ID"))
    unit_id = _cell(unit.get("Unit ID"))
    st.markdown("---")
    st.subheader("Info — " + name)
    editing = st.session_state.get("edit_unit_id") == unit_id
    if not editing:
        if st.button("Edit", key=f"equip_edit_btn_{unit_id}", use_container_width=True):
            st.session_state.edit_unit_id = unit_id
            st.rerun()
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        for col in EQUIPMENT_COLUMNS:
            if col == TONNAGE_APPLIES_COL:
                continue
            if col == TONNAGE_EXPIRE_COL and not tonnage_applies(unit):
                continue
            if col == REGISTRATION_EXPIRE_COL:
                _kind, markup = date_status_markup(col, unit.get(col), registration_due_date(unit), today)
                st.markdown(markup, unsafe_allow_html=True)
                continue
            if col == ANNUAL_MAINT_COL:
                _kind, markup = date_status_markup(
                    col, unit.get(col), annual_maint_due_date(unit), today, due_note=True
                )
                st.markdown(markup, unsafe_allow_html=True)
                continue
            if col == TONNAGE_EXPIRE_COL:
                _kind, markup = date_status_markup(col, unit.get(col), tonnage_due_date(unit), today)
                st.markdown(markup, unsafe_allow_html=True)
                continue
            value = _cell(unit.get(col))
            st.markdown("**" + col + ":** " + (value if value else "—"))
    else:
        show_equipment_edit_form(unit, spreadsheet)
    history = list(reversed(squawks_for(unit.get("Unit ID"), squawks)))
    st.markdown("**Squawk history**")
    if not history:
        st.info("No squawks recorded for this unit.")
    else:
        for item in history:
            status = _cell(item.get("Status")) or STATUS_OPEN
            line = (
                "**" + _cell(item.get("Timestamp")) + "** — " + status
                + " — " + _cell(item.get("Severity"))
                + " — " + _cell(item.get("Category"))
            )
            st.markdown(line)
            if _cell(item.get("Description")):
                st.markdown(_cell(item.get("Description")))
            extras = []
            if _cell(item.get("Reported By")):
                extras.append("Reported by " + _cell(item.get("Reported By")))
            if _cell(item.get("Odometer/Hours")):
                extras.append("Odometer/Hours " + _cell(item.get("Odometer/Hours")))
            if _cell(item.get("Resolved Date")) or _cell(item.get("Resolved By")):
                extras.append(
                    "Resolved " + " ".join(
                        part for part in [_cell(item.get("Resolved Date")), _cell(item.get("Resolved By"))] if part
                    )
                )
            if _cell(item.get("Notes")):
                extras.append("Notes: " + _cell(item.get("Notes")))
            if extras:
                st.caption(" · ".join(extras))
    st.markdown("---")



def unit_has_ifta(unit):
    """True when this equipment unit should show an IFTA button."""
    wanted = {_cell(item) for item in IFTA_UNITS}
    if isinstance(unit, dict):
        return _cell(unit.get("Unit ID")) in wanted or _cell(unit.get("Name")) in wanted
    return _cell(unit) in wanted


def ifta_jurisdiction_label(code):
    code = _cell(code).upper()
    for item_code, name in IFTA_JURISDICTIONS:
        if item_code == code:
            return item_code + " — " + name
    return _cell(code)


def ifta_jurisdiction_options():
    return [ifta_jurisdiction_label(code) for code, _name in IFTA_JURISDICTIONS]


def parse_ifta_jurisdiction(value):
    """Accept a code, 'WA — Washington', or a full name; store the two-letter code."""
    text_value = _cell(value)
    if not text_value:
        return ""
    if "—" in text_value:
        text_value = text_value.split("—", 1)[0].strip()
    elif "-" in text_value and len(text_value.split("-", 1)[0].strip()) <= 3:
        maybe = text_value.split("-", 1)[0].strip()
        if maybe.isalpha() and len(maybe) <= 3:
            text_value = maybe
    upper = text_value.upper()
    for code, name in IFTA_JURISDICTIONS:
        if upper == code or text_value.lower() == name.lower():
            return code
    if len(upper) <= 3 and upper.isalpha():
        return upper
    return _cell(value)


def parse_ifta_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text_value = _cell(value).replace(",", "").replace("$", "")
    if not text_value:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


def format_ifta_number(value, places=None):
    number = parse_ifta_number(value)
    if number is None:
        return ""
    if places is not None:
        return ("%." + str(int(places)) + "f") % number
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return ("%.4f" % number).rstrip("0").rstrip(".")


def ifta_trip_miles(start_odometer, end_odometer):
    start = parse_ifta_number(start_odometer)
    end = parse_ifta_number(end_odometer)
    if start is None or end is None:
        return None
    return end - start


def ifta_fuel_amounts(gallons, price_per_gal, total_cost):
    """Fill a blank Price/Gal or Total Cost when the other amount and gallons are known."""
    gallons_n = parse_ifta_number(gallons)
    price_n = parse_ifta_number(price_per_gal)
    total_n = parse_ifta_number(total_cost)
    if gallons_n is not None and price_n is not None and total_n is None:
        total_n = gallons_n * price_n
    elif gallons_n is not None and total_n is not None and price_n is None and gallons_n != 0:
        price_n = total_n / gallons_n
    return gallons_n, price_n, total_n


def ifta_quarter_range(year, quarter):
    from datetime import date, timedelta
    year = int(year)
    quarter = int(quarter)
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    if quarter == 4:
        end = date(year, 12, 31)
    else:
        end = date(year, start_month + 3, 1) - timedelta(days=1)
    return start, end


def ifta_in_quarter(record, year, quarter):
    entry = parse_equipment_date((record or {}).get("Date"))
    if entry is None:
        return False
    start, end = ifta_quarter_range(year, quarter)
    return start <= entry <= end


def _ensure_ifta_worksheet(spreadsheet, title, columns):
    """Create an IFTA tab with a header when it is missing. Never alter an existing header."""
    cols = list(columns)
    ws = _worksheet_or_none(spreadsheet, title)
    created = False
    if ws is None:
        ws = spreadsheet.add_worksheet(title=title, rows=400, cols=max(len(cols), 8))
        ws.append_row(cols, value_input_option="RAW")
        created = True
    else:
        header = [_cell(c) for c in ws.row_values(1)]
        if not header:
            ws.append_row(cols, value_input_option="RAW")
            created = True
    return ws, created


def ensure_ifta_trips_worksheet(spreadsheet):
    return _ensure_ifta_worksheet(spreadsheet, IFTA_TRIPS_SHEET_TITLE, IFTA_TRIPS_COLUMNS)


def ensure_ifta_fuel_worksheet(spreadsheet):
    return _ensure_ifta_worksheet(spreadsheet, IFTA_FUEL_SHEET_TITLE, IFTA_FUEL_COLUMNS)


def format_ifta_have_receipt(value):
    """Store Yes if they have a receipt, otherwise No."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = _cell(value).strip()
    if not text:
        return "No"
    if text.lower() in {"no", "n", "false", "0", "✗", "x"}:
        return "No"
    # "Yes", "✓", or a leftover receipt number from before the checkbox.
    return "Yes"


def ifta_have_receipt_checked(value):
    return format_ifta_have_receipt(value) == "Yes"


def ifta_have_receipt_display(value):
    """Show a saved receipt flag as a check or cross."""
    return "✓" if ifta_have_receipt_checked(value) else "✗"


def ifta_receipt_from_record(record):
    if not record:
        return ""
    if IFTA_RECEIPT_COLUMN in record:
        return record.get(IFTA_RECEIPT_COLUMN)
    for key in ("Have Receipt", "Receipt", "Receipt #"):
        if key in record:
            return record.get(key)
    return ""



def load_ifta_trip_records(spreadsheet=None, unit_id=None):
    ws, _created = ensure_ifta_trips_worksheet(spreadsheet or _gsheets_spreadsheet())
    records = records_from_worksheet(ws, IFTA_TRIPS_COLUMNS)
    if unit_id:
        wanted = _cell(unit_id)
        records = [r for r in records if _cell(r.get("Unit")) == wanted]
    return records


def load_ifta_fuel_records(spreadsheet=None, unit_id=None):
    ws, _created = ensure_ifta_fuel_worksheet(spreadsheet or _gsheets_spreadsheet())
    records = records_from_worksheet(ws, IFTA_FUEL_COLUMNS)
    if unit_id:
        wanted = _cell(unit_id)
        records = [r for r in records if _cell(r.get("Unit")) == wanted]
    return records


def _ifta_row_sort_key(record):
    entry = parse_equipment_date((record or {}).get("Date"))
    stamp = _cell((record or {}).get("Timestamp"))
    stamp_dt = datetime.min
    if stamp:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                stamp_dt = datetime.strptime(stamp, fmt)
                break
            except ValueError:
                continue
    entry_dt = datetime(entry.year, entry.month, entry.day) if entry is not None else datetime.min
    return (entry_dt, stamp_dt)


def build_ifta_trip_record(entry_date, unit_id, driver, jurisdiction, start_odometer, end_odometer, notes, when=None):
    miles = ifta_trip_miles(start_odometer, end_odometer)
    if miles is None:
        raise ValueError("Start and End Odometer are required")
    if miles < 0:
        raise ValueError("Miles must be 0 or greater (End Odometer cannot be less than Start Odometer)")
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Date": format_equipment_date(entry_date),
        "Unit": _cell(unit_id),
        "Driver": _cell(driver),
        "Jurisdiction": parse_ifta_jurisdiction(jurisdiction) or IFTA_DEFAULT_JURISDICTION,
        "Start Odometer": format_ifta_number(start_odometer),
        "End Odometer": format_ifta_number(end_odometer),
        "Miles": format_ifta_number(miles),
        "Notes": _cell(notes),
    }


def build_ifta_fuel_record(entry_date, unit_id, jurisdiction, gallons, price_per_gal, total_cost, vendor, receipt, notes, when=None):
    gallons_n = parse_ifta_number(gallons)
    if gallons_n is None or gallons_n < 0:
        raise ValueError("Gallons is required and must be 0 or greater")
    gallons_n, price_n, total_n = ifta_fuel_amounts(gallons, price_per_gal, total_cost)
    when = when or datetime.now(ZoneInfo("America/Los_Angeles"))
    return {
        "Timestamp": when.strftime("%Y-%m-%d %H:%M:%S"),
        "Date": format_equipment_date(entry_date),
        "Unit": _cell(unit_id),
        "Jurisdiction": parse_ifta_jurisdiction(jurisdiction) or IFTA_DEFAULT_JURISDICTION,
        "Gallons": format_ifta_number(gallons_n, 3),
        "Price/Gal": format_ifta_number(price_n, 3) if price_n is not None else "",
        "Total Cost": format_ifta_number(total_n, 2) if total_n is not None else "",
        "Vendor/Location": _cell(vendor),
        IFTA_RECEIPT_COLUMN: format_ifta_have_receipt(receipt),
        "Notes": _cell(notes),
    }


def save_ifta_trip_record(record, spreadsheet=None):
    ws, _created = ensure_ifta_trips_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("IFTA Trips worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (IFTA Trips)"


def save_ifta_fuel_record(record, spreadsheet=None):
    ws, _created = ensure_ifta_fuel_worksheet(spreadsheet or _gsheets_spreadsheet())
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("IFTA Fuel worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (IFTA Fuel)"


def ifta_mpg(miles, gallons):
    miles_n = parse_ifta_number(miles) or 0
    gallons_n = parse_ifta_number(gallons) or 0
    if gallons_n <= 0:
        return None
    return miles_n / gallons_n


def build_ifta_quarterly_summary(trips, fuel, year, quarter, unit_id=None):
    """Miles and gallons by jurisdiction, unit totals, fleet totals, and overall MPG."""
    year = int(year)
    quarter = int(quarter)
    start, end = ifta_quarter_range(year, quarter)
    trip_rows = [r for r in (trips or []) if ifta_in_quarter(r, year, quarter)]
    fuel_rows = [r for r in (fuel or []) if ifta_in_quarter(r, year, quarter)]
    wanted = _cell(unit_id)

    def _accumulate(rows, field, unit_filter=None):
        totals = {}
        for record in rows:
            if unit_filter and _cell(record.get("Unit")) != unit_filter:
                continue
            code = parse_ifta_jurisdiction(record.get("Jurisdiction")) or "—"
            totals[code] = totals.get(code, 0) + (parse_ifta_number(record.get(field)) or 0)
        return totals

    fleet_miles = _accumulate(trip_rows, "Miles")
    fleet_gallons = _accumulate(fuel_rows, "Gallons")
    unit_miles = _accumulate(trip_rows, "Miles", wanted) if wanted else dict(fleet_miles)
    unit_gallons = _accumulate(fuel_rows, "Gallons", wanted) if wanted else dict(fleet_gallons)

    def _rows(miles_map, gallons_map):
        codes = sorted(set(miles_map) | set(gallons_map), key=lambda code: (code == "—", code))
        rows = []
        total_miles = 0
        total_gallons = 0
        for code in codes:
            miles_n = miles_map.get(code, 0)
            gallons_n = gallons_map.get(code, 0)
            total_miles += miles_n
            total_gallons += gallons_n
            rows.append({
                "Jurisdiction": code,
                "Jurisdiction Label": ifta_jurisdiction_label(code) if code != "—" else "—",
                "Miles": miles_n,
                "Gallons": gallons_n,
                "MPG": ifta_mpg(miles_n, gallons_n),
            })
        return rows, total_miles, total_gallons, ifta_mpg(total_miles, total_gallons)

    unit_rows, unit_total_miles, unit_total_gallons, unit_mpg = _rows(unit_miles, unit_gallons)
    fleet_rows, fleet_total_miles, fleet_total_gallons, fleet_mpg = _rows(fleet_miles, fleet_gallons)
    units = sorted({_cell(r.get("Unit")) for r in trip_rows + fuel_rows if _cell(r.get("Unit"))})
    return {
        "year": year,
        "quarter": quarter,
        "start": start,
        "end": end,
        "unit_id": wanted,
        "units": units,
        "unit_rows": unit_rows,
        "unit_total_miles": unit_total_miles,
        "unit_total_gallons": unit_total_gallons,
        "unit_mpg": unit_mpg,
        "fleet_rows": fleet_rows,
        "fleet_total_miles": fleet_total_miles,
        "fleet_total_gallons": fleet_total_gallons,
        "fleet_mpg": fleet_mpg,
    }


def build_ifta_summary_csv(summary):
    import csv
    from io import StringIO
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Year", "Quarter", "Scope", "Unit", "Jurisdiction", "Miles", "Gallons", "MPG"])
    year = summary.get("year")
    quarter = "Q" + str(summary.get("quarter"))
    unit_id = _cell(summary.get("unit_id")) or "—"

    def _emit(scope, unit_name, rows, total_miles, total_gallons, mpg):
        for row in rows:
            writer.writerow([
                year, quarter, scope, unit_name, row["Jurisdiction"],
                format_ifta_number(row["Miles"], 1),
                format_ifta_number(row["Gallons"], 3),
                format_ifta_number(row["MPG"], 2) if row["MPG"] is not None else "",
            ])
        writer.writerow([
            year, quarter, scope, unit_name, "TOTAL",
            format_ifta_number(total_miles, 1),
            format_ifta_number(total_gallons, 3),
            format_ifta_number(mpg, 2) if mpg is not None else "",
        ])

    _emit("Unit", unit_id, summary.get("unit_rows") or [], summary.get("unit_total_miles"), summary.get("unit_total_gallons"), summary.get("unit_mpg"))
    _emit("Fleet", "Fleet", summary.get("fleet_rows") or [], summary.get("fleet_total_miles"), summary.get("fleet_total_gallons"), summary.get("fleet_mpg"))
    return buf.getvalue()


def ifta_summary_pdf_filename(summary):
    year = str(summary.get("year") or "")
    quarter = "Q" + str(summary.get("quarter") or "")
    unit_id = _cell(summary.get("unit_id"))
    bits = ["CVH_IFTA"]
    if unit_id:
        bits.append(unit_id)
    bits.append(quarter)
    bits.append(year)
    return "_".join(bits) + ".pdf"


def build_ifta_summary_pdf(summary, logo_path=None):
    """One-page letter PDF of an IFTA quarterly summary, in the flag-logo report style."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    def _esc(value):
        text = _cell(value)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    logo_path = logo_path if logo_path is not None else safety_meeting_report_logo_path()
    buf = BytesIO()
    title = "IFTA Quarterly Summary"
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title=title, author="Central Valley Helicopters",
    )
    ss = getSampleStyleSheet()
    company = ParagraphStyle("co", parent=ss["Normal"], fontSize=9, leading=11, alignment=TA_LEFT, textColor=colors.HexColor("#222222"))
    company_sm = ParagraphStyle("cosm", parent=company, fontSize=8, leading=10, textColor=colors.HexColor("#333333"))
    title_style = ParagraphStyle("t", parent=ss["Title"], fontSize=15, leading=18, spaceAfter=2, spaceBefore=4, alignment=TA_LEFT)
    heading = ParagraphStyle("h", parent=ss["Heading2"], fontSize=11, leading=14, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("n", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("c", parent=body, fontSize=8.5, leading=11)
    story = []
    logo_flow = None
    if logo_path:
        try:
            logo_flow = Image(logo_path, width=1.25 * inch, height=1.25 * inch * 214 / 320)
        except Exception:
            logo_flow = None
    company_lines = [
        Paragraph("<b>Cline Air Services LLC dba Central Valley Helicopters</b>", company),
        Paragraph("891 Prater Rd, Ellensburg, WA 98926", company_sm),
        Paragraph("Phone: (509) 968-9300", company_sm),
        Paragraph("Email: cvh@centralvalleyheli.com", company_sm),
    ]
    company_block = Table([[line] for line in company_lines], colWidths=[5.8 * inch])
    company_block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    if logo_flow is not None:
        head = Table([[logo_flow, company_block]], colWidths=[1.4 * inch, 5.8 * inch])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(head)
    else:
        for line in company_lines:
            story.append(line)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#8B0000"), spaceBefore=2, spaceAfter=8))
    story.append(Paragraph(title, title_style))
    quarter = "Q" + str(summary.get("quarter"))
    start = format_equipment_date(summary.get("start"))
    end = format_equipment_date(summary.get("end"))
    unit_id = _cell(summary.get("unit_id")) or "—"
    story.append(Paragraph("<b>Period:</b> " + _esc(quarter + " " + str(summary.get("year")) + "  (" + start + " to " + end + ")"), body))
    story.append(Paragraph("<b>Unit:</b> " + _esc(unit_id), body))
    if summary.get("units"):
        story.append(Paragraph("<b>Fleet units in this quarter:</b> " + _esc(", ".join(summary.get("units"))), body))

    def _mpg(value):
        return format_ifta_number(value, 2) if value is not None else "—"

    def _table(title_text, rows, total_miles, total_gallons, mpg):
        story.append(Paragraph(title_text, heading))
        data = [[
            Paragraph("<b>Jurisdiction</b>", small),
            Paragraph("<b>Miles</b>", small),
            Paragraph("<b>Gallons</b>", small),
            Paragraph("<b>MPG</b>", small),
        ]]
        for row in rows:
            data.append([
                Paragraph(_esc(row.get("Jurisdiction Label") or row.get("Jurisdiction")), small),
                Paragraph(_esc(format_ifta_number(row.get("Miles"), 1)), small),
                Paragraph(_esc(format_ifta_number(row.get("Gallons"), 3)), small),
                Paragraph(_esc(_mpg(row.get("MPG"))), small),
            ])
        data.append([
            Paragraph("<b>Total</b>", small),
            Paragraph("<b>" + _esc(format_ifta_number(total_miles, 1)) + "</b>", small),
            Paragraph("<b>" + _esc(format_ifta_number(total_gallons, 3)) + "</b>", small),
            Paragraph("<b>" + _esc(_mpg(mpg)) + "</b>", small),
        ])
        table = Table(data, colWidths=[2.8 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F3F4F6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ]))
        story.append(table)

    _table("Unit miles and fuel", summary.get("unit_rows") or [], summary.get("unit_total_miles"), summary.get("unit_total_gallons"), summary.get("unit_mpg"))
    _table("Fleet totals", summary.get("fleet_rows") or [], summary.get("fleet_total_miles"), summary.get("fleet_total_gallons"), summary.get("fleet_mpg"))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Overall fleet MPG:</b> " + _esc(_mpg(summary.get("fleet_mpg"))), body))
    doc.build(story)
    return buf.getvalue()


def show_ifta_page(unit, spreadsheet):
    """Phone-friendly IFTA trip, fuel, and quarterly summary page for one unit."""
    unit_id = _cell(unit.get("Unit ID")) or _cell(unit.get("Name"))
    name = _cell(unit.get("Name")) or unit_id
    st.title("IFTA")
    st.subheader(name)
    st.caption("Trip miles and fuel purchases are saved to the IFTA Trips and IFTA Fuel tabs.")
    if st.button("Back", key="ifta_back", use_container_width=True):
        st.session_state.ifta_unit_id = None
        st.rerun()

    if st.session_state.get("ifta_trip_saved"):
        st.success(st.session_state.pop("ifta_trip_saved"))
    if st.session_state.get("ifta_fuel_saved"):
        st.success(st.session_state.pop("ifta_fuel_saved"))

    try:
        trips = load_ifta_trip_records(spreadsheet)
        fuel = load_ifta_fuel_records(spreadsheet)
    except Exception as exc:
        st.error(f"Could not load IFTA records: {exc}")
        return

    if "ifta_view" not in st.session_state:
        st.session_state.ifta_view = IFTA_VIEW_TRIPS
    st.radio("IFTA section", [IFTA_VIEW_TRIPS, IFTA_VIEW_FUEL, IFTA_VIEW_SUMMARY], horizontal=False, key="ifta_view")
    view = st.session_state.ifta_view
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    jurisdiction_options = ifta_jurisdiction_options()
    default_label = ifta_jurisdiction_label(IFTA_DEFAULT_JURISDICTION)

    if view == IFTA_VIEW_TRIPS:
        _show_ifta_trips_form(unit_id, trips, spreadsheet, today, jurisdiction_options, default_label)
    elif view == IFTA_VIEW_FUEL:
        _show_ifta_fuel_form(unit_id, fuel, spreadsheet, today, jurisdiction_options, default_label)
    else:
        _show_ifta_summary(unit_id, trips, fuel, today)


def _show_ifta_trips_form(unit_id, trips, spreadsheet, today, jurisdiction_options, default_label):
    unit_trips = [r for r in trips if _cell(r.get("Unit")) == unit_id]
    latest = sorted(unit_trips, key=_ifta_row_sort_key, reverse=True)
    last_end = _cell(latest[0].get("End Odometer")) if latest else ""
    gen = int(st.session_state.get("ifta_trip_gen_" + unit_id) or 0)
    prefix = "ifta_trip_" + unit_id + "_" + str(gen) + "_"
    st.markdown("**New trip**")
    st.date_input("Date", value=today, format="YYYY-MM-DD", key=prefix + "date")
    st.markdown("**Unit:** " + unit_id)
    st.selectbox("Driver", list(DRIVERS), key=prefix + "driver")
    default_index = jurisdiction_options.index(default_label) if default_label in jurisdiction_options else 0
    st.selectbox("Jurisdiction", jurisdiction_options, index=default_index, key=prefix + "jurisdiction")
    st.text_input("Start Odometer", value=last_end, key=prefix + "start")
    st.text_input("End Odometer", key=prefix + "end")
    miles = ifta_trip_miles(st.session_state.get(prefix + "start"), st.session_state.get(prefix + "end"))
    if miles is None:
        st.markdown("**Miles:** —")
    elif miles < 0:
        st.markdown("**Miles:** " + format_ifta_number(miles) + "  (must be 0 or greater)")
    else:
        st.markdown("**Miles:** " + format_ifta_number(miles))
    st.text_input("Notes", key=prefix + "notes")
    if st.button("Save trip", type="primary", key=prefix + "save", use_container_width=True):
        try:
            record = build_ifta_trip_record(
                st.session_state.get(prefix + "date"),
                unit_id,
                st.session_state.get(prefix + "driver", ""),
                st.session_state.get(prefix + "jurisdiction"),
                st.session_state.get(prefix + "start"),
                st.session_state.get(prefix + "end"),
                st.session_state.get(prefix + "notes", ""),
            )
            save_ifta_trip_record(record, spreadsheet=spreadsheet)
        except Exception as exc:
            st.error(f"Could not save the IFTA trip: {exc}")
        else:
            st.session_state.ifta_trip_saved = "Saved IFTA trip for " + unit_id + " on " + (record.get("Date") or "today") + "."
            st.session_state["ifta_trip_gen_" + unit_id] = gen + 1
            st.rerun()

    st.markdown("---")
    st.subheader("Trip history")
    if not latest:
        st.info("No trips recorded yet for this unit.")
        return
    for item in latest:
        title = (_cell(item.get("Date")) or "Trip") + " — " + (ifta_jurisdiction_label(item.get("Jurisdiction")) or "—")
        if _cell(item.get("Miles")):
            title = title + "  (" + _cell(item.get("Miles")) + " mi)"
        with st.expander(title):
            st.markdown("**Date:** " + (_cell(item.get("Date")) or "—"))
            st.markdown("**Driver:** " + (_cell(item.get("Driver")) or "—"))
            st.markdown("**Jurisdiction:** " + (ifta_jurisdiction_label(item.get("Jurisdiction")) or "—"))
            st.markdown("**Start Odometer:** " + (_cell(item.get("Start Odometer")) or "—"))
            st.markdown("**End Odometer:** " + (_cell(item.get("End Odometer")) or "—"))
            st.markdown("**Miles:** " + (_cell(item.get("Miles")) or "—"))
            st.markdown("**Notes:** " + (_cell(item.get("Notes")) or "—"))


def _show_ifta_fuel_form(unit_id, fuel, spreadsheet, today, jurisdiction_options, default_label):
    unit_fuel = [r for r in fuel if _cell(r.get("Unit")) == unit_id]
    latest = sorted(unit_fuel, key=_ifta_row_sort_key, reverse=True)
    gen = int(st.session_state.get("ifta_fuel_gen_" + unit_id) or 0)
    prefix = "ifta_fuel_" + unit_id + "_" + str(gen) + "_"
    st.markdown("**New fuel purchase**")
    st.date_input("Date", value=today, format="YYYY-MM-DD", key=prefix + "date")
    st.markdown("**Unit:** " + unit_id)
    default_index = jurisdiction_options.index(default_label) if default_label in jurisdiction_options else 0
    st.selectbox("Jurisdiction", jurisdiction_options, index=default_index, key=prefix + "jurisdiction")
    st.text_input("Gallons", key=prefix + "gallons")
    st.text_input("Price/Gal", key=prefix + "price")
    st.text_input("Total Cost", key=prefix + "total")
    gallons_n, price_n, total_n = ifta_fuel_amounts(
        st.session_state.get(prefix + "gallons"),
        st.session_state.get(prefix + "price"),
        st.session_state.get(prefix + "total"),
    )
    if gallons_n is not None and (price_n is not None or total_n is not None):
        bits = []
        if price_n is not None and not _cell(st.session_state.get(prefix + "price")):
            bits.append("Price/Gal " + format_ifta_number(price_n, 3))
        if total_n is not None and not _cell(st.session_state.get(prefix + "total")):
            bits.append("Total Cost " + format_ifta_number(total_n, 2))
        if bits:
            st.caption("Computed: " + " · ".join(bits))
    st.text_input("Vendor/Location", key=prefix + "vendor")
    st.checkbox("Have receipt", key=prefix + "receipt")
    st.text_input("Notes", key=prefix + "notes")
    if st.button("Save fuel purchase", type="primary", key=prefix + "save", use_container_width=True):
        try:
            record = build_ifta_fuel_record(
                st.session_state.get(prefix + "date"),
                unit_id,
                st.session_state.get(prefix + "jurisdiction"),
                st.session_state.get(prefix + "gallons"),
                st.session_state.get(prefix + "price"),
                st.session_state.get(prefix + "total"),
                st.session_state.get(prefix + "vendor", ""),
                st.session_state.get(prefix + "receipt", ""),
                st.session_state.get(prefix + "notes", ""),
            )
            save_ifta_fuel_record(record, spreadsheet=spreadsheet)
        except Exception as exc:
            st.error(f"Could not save the IFTA fuel purchase: {exc}")
        else:
            st.session_state.ifta_fuel_saved = "Saved IFTA fuel purchase for " + unit_id + " on " + (record.get("Date") or "today") + "."
            st.session_state["ifta_fuel_gen_" + unit_id] = gen + 1
            st.rerun()

    st.markdown("---")
    st.subheader("Fuel history")
    if not latest:
        st.info("No fuel purchases recorded yet for this unit.")
        return
    for item in latest:
        title = (_cell(item.get("Date")) or "Fuel") + " — " + (ifta_jurisdiction_label(item.get("Jurisdiction")) or "—")
        if _cell(item.get("Gallons")):
            title = title + "  (" + _cell(item.get("Gallons")) + " gal)"
        with st.expander(title):
            st.markdown("**Date:** " + (_cell(item.get("Date")) or "—"))
            st.markdown("**Jurisdiction:** " + (ifta_jurisdiction_label(item.get("Jurisdiction")) or "—"))
            st.markdown("**Gallons:** " + (_cell(item.get("Gallons")) or "—"))
            st.markdown("**Price/Gal:** " + (_cell(item.get("Price/Gal")) or "—"))
            st.markdown("**Total Cost:** " + (_cell(item.get("Total Cost")) or "—"))
            st.markdown("**Vendor/Location:** " + (_cell(item.get("Vendor/Location")) or "—"))
            st.markdown("**Have receipt:** " + ifta_have_receipt_display(ifta_receipt_from_record(item)))
            st.markdown("**Notes:** " + (_cell(item.get("Notes")) or "—"))


def _show_ifta_summary(unit_id, trips, fuel, today):
    trip_years = {parse_equipment_date(r.get("Date")).year for r in trips if parse_equipment_date(r.get("Date"))}
    fuel_years = {parse_equipment_date(r.get("Date")).year for r in fuel if parse_equipment_date(r.get("Date"))}
    years = sorted(trip_years | fuel_years | {today.year}, reverse=True)
    default_year = today.year
    default_quarter = ((today.month - 1) // 3) + 1
    if "ifta_sum_year" not in st.session_state or st.session_state.get("ifta_sum_year") not in years:
        st.session_state.ifta_sum_year = default_year
    year = st.selectbox("Year", years, key="ifta_sum_year")
    quarters = [1, 2, 3, 4]
    if st.session_state.get("ifta_sum_quarter") not in quarters:
        st.session_state.ifta_sum_quarter = default_quarter
    quarter = st.selectbox("Quarter", quarters, format_func=lambda value: "Q" + str(value), key="ifta_sum_quarter")
    summary = build_ifta_quarterly_summary(trips, fuel, year, quarter, unit_id=unit_id)
    start = format_equipment_date(summary["start"])
    end = format_equipment_date(summary["end"])
    st.caption(start + " to " + end)

    def _mpg(value):
        return format_ifta_number(value, 2) if value is not None else "—"

    st.markdown("**" + unit_id + "**")
    if not summary["unit_rows"]:
        st.info("No IFTA trips or fuel purchases for this unit in " + "Q" + str(quarter) + " " + str(year) + ".")
    else:
        for row in summary["unit_rows"]:
            st.markdown(
                "**" + row["Jurisdiction Label"] + ":** "
                + format_ifta_number(row["Miles"], 1) + " mi · "
                + format_ifta_number(row["Gallons"], 3) + " gal · "
                + "MPG " + _mpg(row["MPG"])
            )
        st.markdown(
            "**Unit total:** "
            + format_ifta_number(summary["unit_total_miles"], 1) + " mi · "
            + format_ifta_number(summary["unit_total_gallons"], 3) + " gal · "
            + "MPG " + _mpg(summary["unit_mpg"])
        )

    st.markdown("**Fleet totals**")
    if summary["units"]:
        st.caption("Units in this quarter: " + ", ".join(summary["units"]))
    st.markdown(
        "**Fleet total:** "
        + format_ifta_number(summary["fleet_total_miles"], 1) + " mi · "
        + format_ifta_number(summary["fleet_total_gallons"], 3) + " gal · "
        + "MPG " + _mpg(summary["fleet_mpg"])
    )
    csv_text = build_ifta_summary_csv(summary)
    st.download_button(
        "Download CSV",
        data=csv_text,
        file_name="CVH_IFTA_" + unit_id + "_Q" + str(quarter) + "_" + str(year) + ".csv",
        mime="text/csv",
        key="ifta_csv_" + unit_id + "_" + str(year) + "_" + str(quarter),
        use_container_width=True,
    )
    try:
        pdf_bytes = build_ifta_summary_pdf(summary)
    except Exception as exc:
        st.warning("Could not build the IFTA PDF: " + str(exc))
    else:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=ifta_summary_pdf_filename(summary),
            mime="application/pdf",
            key="ifta_pdf_" + unit_id + "_" + str(year) + "_" + str(quarter),
            use_container_width=True,
        )


def show_equipment_page():
    try:
        spreadsheet = _gsheets_spreadsheet()
        units = [u for u in load_equipment_records(spreadsheet) if is_active_equipment(u) and _cell(u.get("Unit ID"))]
        squawks = load_squawk_records(spreadsheet)
    except Exception as e:
        st.title("Equipment Squawks")
        st.error(f"Could not load equipment or squawks: {e}")
        return

    ifta_id = _cell(st.session_state.get("ifta_unit_id"))
    if ifta_id:
        ifta_unit = next((u for u in units if _cell(u.get("Unit ID")) == ifta_id), None)
        if ifta_unit is not None:
            show_ifta_page(ifta_unit, spreadsheet)
            return
        st.session_state.ifta_unit_id = None

    st.title("Equipment Squawks")
    st.caption(
        "Tap a unit and save a squawk to the Google Sheet. "
        "Edit names on the Equipment tab of the CVH FRAT Log if the list changes."
    )
    st.link_button("Open CVH FRAT Log (Equipment and Squawks tabs)", frat_sheet_url(), use_container_width=True)

    if not units:
        st.warning("No active equipment found. Add units on the Equipment tab (Unit ID, Name, Type, Active).")
        return

    if st.session_state.get("squawk_saved"):
        st.success(st.session_state.pop("squawk_saved"))
    if st.session_state.get("squawk_resolved"):
        st.success(st.session_state.pop("squawk_resolved"))
    if st.session_state.get("equipment_saved"):
        st.success(st.session_state.pop("equipment_saved"))

    selected_id = st.session_state.get("squawk_unit_id")
    info_id = st.session_state.get("info_unit_id")
    for unit in units:
        unit_id = _cell(unit.get("Unit ID"))
        open_items = open_squawks_for(unit_id, squawks)
        grounded = equipment_has_grounding(unit_id, squawks)
        name = _cell(unit.get("Name")) or unit_id
        if unit_has_ifta(unit):
            name_col, info_col, ifta_col, squawk_col = st.columns([2.4, 1, 1, 1])
        else:
            name_col, info_col, squawk_col = st.columns([3.2, 1, 1])
            ifta_col = None
        with name_col:
            st.markdown("**" + name + "**")
            if unit_id and unit_id != name:
                st.caption(unit_id)
            if grounded:
                st.error("GROUNDED — Do not use")
            today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
            # Set dates are colored on the row; blank dates stay off the list (INFO shows gray 'Not set').
            for label, raw, due, due_note in (
                ("Registration Expire Date", unit.get(REGISTRATION_EXPIRE_COL), registration_due_date(unit), False),
                ("Annual Maint Date", unit.get(ANNUAL_MAINT_COL), annual_maint_due_date(unit), True),
                ("Tonnage Wt Expire Date", unit.get(TONNAGE_EXPIRE_COL), tonnage_due_date(unit), False),
            ):
                if due is None:
                    continue
                _kind, markup = date_status_markup(label, raw, due, today, due_note=due_note)
                st.markdown(markup, unsafe_allow_html=True)
            if open_items and not grounded:
                count = len(open_items)
                st.warning(f"{count} open squawk{'s' if count != 1 else ''}")
        with info_col:
            if st.button("INFO", key=f"info_btn_{unit_id}", use_container_width=True):
                clear_equipment_edit_widgets(st.session_state.get("edit_unit_id"))
                st.session_state.info_unit_id = None if info_id == unit_id else unit_id
                st.session_state.squawk_unit_id = None
                st.session_state.edit_unit_id = None
                st.session_state.ifta_unit_id = None
                st.rerun()
        if ifta_col is not None:
            with ifta_col:
                if st.button("IFTA", key=f"ifta_btn_{unit_id}", use_container_width=True):
                    clear_equipment_edit_widgets(st.session_state.get("edit_unit_id"))
                    st.session_state.ifta_unit_id = unit_id
                    st.session_state.info_unit_id = None
                    st.session_state.squawk_unit_id = None
                    st.session_state.edit_unit_id = None
                    st.rerun()
        with squawk_col:
            if st.button("Squawk", key=f"squawk_btn_{unit_id}", use_container_width=True):
                clear_equipment_edit_widgets(st.session_state.get("edit_unit_id"))
                st.session_state.squawk_unit_id = unit_id
                st.session_state.info_unit_id = None
                st.session_state.edit_unit_id = None
                st.session_state.ifta_unit_id = None
                st.rerun()
        if info_id == unit_id:
            show_equipment_info(unit, squawks, spreadsheet=spreadsheet)
        if _cell(selected_id) == unit_id:
            typ = _cell(unit.get("Type"))
            form_bits = [unit_id] + ([typ] if typ else []) + ["times are Pacific (America/Los_Angeles)"]
            st.markdown("---")
            st.subheader("New squawk — " + name)
            st.caption(" · ".join(form_bits))
            now = datetime.now(ZoneInfo("America/Los_Angeles"))
            with st.form("equipment_squawk_form"):
                reporter = st.selectbox("Reported by", REPORTERS + ["Other"], index=None, placeholder="Select name")
                other_name = st.text_input("Name if Other")
                c1, c2 = st.columns(2)
                with c1:
                    squawk_date = st.date_input("Date", value=now.date())
                with c2:
                    squawk_time = st.time_input("Time (Pacific)", value=now.time().replace(microsecond=0))
                category = st.selectbox("Category", SQUAWK_CATEGORIES, index=None, placeholder="Select category")
                severity = st.selectbox("Severity", SQUAWK_SEVERITIES, index=None, placeholder="Select severity")
                description = st.text_area("Description", placeholder="What is wrong, and where?")
                odometer = st.text_input("Odometer / Hours (optional)")
                submitted = st.form_submit_button("Save squawk", type="primary", use_container_width=True)
            if st.button("Cancel", key="squawk_form_cancel"):
                st.session_state.squawk_unit_id = None
                st.rerun()
            if submitted:
                reported_by = other_name.strip() if reporter == "Other" else (reporter or "")
                when = datetime.combine(squawk_date, squawk_time).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
                try:
                    record = build_squawk_record(
                        unit, reported_by, when, category, severity, description, odometer
                    )
                    save_squawk_record(record, spreadsheet)
                except Exception as e:
                    st.error("Could not save squawk: " + str(e))
                else:
                    st.session_state.squawk_saved = (
                        "Saved squawk for " + record["Equipment Name"] + " (" + record["Unit ID"] + ")."
                    )
                    st.session_state.squawk_unit_id = None
                    st.rerun()
            st.markdown("---")

    open_all = [s for s in squawks if is_open_squawk(s)]
    st.markdown("---")
    st.subheader("Open squawks")
    if not open_all:
        st.info("No open squawks.")
        return
    for idx, item in enumerate(open_all):
        title = f"{item.get('Equipment Name') or item.get('Unit ID')} — {item.get('Severity')} — {item.get('Category')}"
        if is_grounded_squawk(item):
            title = "GROUNDED · " + title
        with st.expander(title):
            st.markdown(
                f"**Unit:** {item.get('Unit ID')}  \n"
                f"**Reported:** {item.get('Timestamp')} by {item.get('Reported By')}  \n"
                f"**Odometer/Hours:** {item.get('Odometer/Hours') or '—'}  \n"
                f"**Description:** {item.get('Description')}"
            )
            if item.get("Notes"):
                st.markdown(f"**Notes:** {item.get('Notes')}")
            resolved_by = st.selectbox(
                "Resolved by",
                REPORTERS + ["Other"],
                index=None,
                placeholder="Select name",
                key=f"resolve_by_{idx}_{item.get('Timestamp')}_{item.get('Unit ID')}",
            )
            resolve_other = st.text_input(
                "Name if Other",
                key=f"resolve_other_{idx}_{item.get('Timestamp')}_{item.get('Unit ID')}",
            )
            resolve_notes = st.text_input(
                "Resolution notes (optional)",
                key=f"resolve_notes_{idx}_{item.get('Timestamp')}_{item.get('Unit ID')}",
            )
            if st.button("Mark resolved", key=f"resolve_btn_{idx}_{item.get('Timestamp')}_{item.get('Unit ID')}"):
                who = resolve_other.strip() if resolved_by == "Other" else (resolved_by or "")
                try:
                    resolve_squawk(
                        item.get("Timestamp"),
                        item.get("Unit ID"),
                        who,
                        resolve_notes,
                        datetime.now(ZoneInfo("America/Los_Angeles")),
                        spreadsheet,
                    )
                except Exception as e:
                    st.error(f"Could not mark resolved: {e}")
                else:
                    st.session_state.squawk_resolved = (
                        f"Marked resolved: {item.get('Equipment Name') or item.get('Unit ID')}."
                    )
                    st.rerun()

# ────────────────────────────────────────────────
# Risk Assessment – FRAT function (per FAR part; Part 5 §5.51–5.55, records §5.97)
# ────────────────────────────────────────────────
def assessment_key(name):
    """Give each confirmed new assessment fresh frontend widget identities."""
    generation = st.session_state.get("assessment_generation", 0)
    return f"{name}__assessment_{generation}" if generation else name


def request_assessment_reset():
    st.session_state.pilot_reset_pending = True


def cancel_assessment_reset():
    st.session_state.pilot_reset_pending = False


def reset_pilot_assessment():
    """Clear only unsaved Pilot assessment state, never history/configuration."""
    for key in list(st.session_state):
        if (key.startswith(("frat_", "pilot_config_", "pax_w_", "far_part_ctrl__assessment_"))
                or key in ("far_part", "far_part_ctrl")):
            del st.session_state[key]
    # Deleting server values alone can leave browser widgets showing old values.
    # New keys force frontend remounting on the callback-triggered rerun.
    st.session_state.assessment_generation = st.session_state.get("assessment_generation", 0) + 1
    st.session_state.pilot_reset_pending = False


def show_risk_assessment(part, config, da_hint=None, default_aircraft_idx=0):
    st.subheader(f"FRAT – {part}")
    st.caption("Complete before every flight. Score each factor 0–10 (higher = more risk). Records kept 5 years.")
    pax = int(config.get("pax_count") or 0)

    st.markdown("**Flight Information**")
    h1, h2, h3 = st.columns(3)
    with h1:
        frat_date = st.date_input("Date", value=datetime.now(ZoneInfo("America/Los_Angeles")).date(), key=assessment_key("frat_date"))
    with h2:
        pilot = st.selectbox("Pilot", PILOTS, index=None, placeholder="Select pilot", key=assessment_key("frat_pilot"))
    with h3:
        aircraft = FRAT_AIRCRAFT[default_aircraft_idx]
        st.text_input("Aircraft (from configuration)", value=aircraft, disabled=True,
                      key=assessment_key(f"frat_aircraft_display_{default_aircraft_idx}"))
    route_job = st.text_input("Route or job", key=assessment_key("frat_route"))
    st.caption(f"Operation: **{part}**" + (f" · Passengers: **{pax}** (from configuration)" if part == "Part 135" else ""))

    st.caption("0 = not assessed. Review every factor and select 1–10 for this flight. "
               "Every factor must be greater than 0 before completing or saving the assessment.")
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
            st.caption("No passengers entered. Review this factor before selecting a score.")
        scores[key] = st.slider(label, min_value=0, max_value=10, value=default, step=1, key=assessment_key(f"frat_{part}_{key}"))
    unassessed = [label for key, _, label, _ in factors if scores[key] == 0]
    if unassessed:
        st.warning("NOT RELEASED — risk review incomplete. 0 = not assessed. "
                   "Review these factors and select 1–10:\n\n"
                   + "\n".join(f"- {label}" for label in unassessed))
    total_risk = sum(scores.values())
    frat_max = 10 * len(factors)

    st.markdown("**Stop Items** – any *No* is a NO-GO regardless of score")
    stops = {}
    for key, label in PART_STOPS[part]:
        if key == "stop_pax_brief" and pax == 0:
            stops[key] = "N/A"
            continue
        ans = st.radio(label, ["Yes", "No"], index=None, horizontal=True, key=assessment_key(f"frat_{part}_{key}"))
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
    if unassessed:
        st.markdown(f"### ⚠️ {total_risk} — Risk review incomplete")
    else:
        st.markdown(f"### {emoji} {total_risk} — {level}")
    st.caption(f"Low 0–{cut['low_max']} · Medium {cut['low_max'] + 1}–{cut['med_max']} "
               f"· High {cut['med_max'] + 1}+")

    st.markdown("**Decision & Sign-off**")
    mitigations, approver, approved = "", "", False
    ron_unreachable = False
    if level == "Medium Risk" and not stop_failed:
        mitigations = st.text_area("Mitigations (required for Medium risk)", key=assessment_key(f"frat_{part}_mitigations"))
        approver = st.selectbox("Medium-risk approver", APPROVERS, index=None, placeholder="Select approver", key=assessment_key(f"frat_{part}_approver"))
        if approver == DIRECTOR_MAINTENANCE:
            ron_unreachable = st.checkbox("Ron could not be reached (required for Carl to approve)", key=assessment_key(f"frat_{part}_ron_unreachable"))
        approved = st.checkbox(f"{approver or 'Selected approver'} approves this flight with the mitigations above", key=assessment_key(f"frat_{part}_approved"))
    elif level == "Low Risk" and not stop_failed:
        mitigations = st.text_area("Mitigations (optional)", key=assessment_key(f"frat_{part}_mitigations"))
    sig_name = st.selectbox("Pilot signature", PILOTS, index=None, placeholder="Select name", key=assessment_key("frat_sig"))
    pilot_accepts = st.checkbox("I have completed this assessment accurately and accept the risk for this flight", key=assessment_key(f"frat_{part}_accept"))

    reasons = []
    if stop_failed:
        decision, reasons = "NO-GO", ["Stop item answered No"]
    elif level == "High Risk":
        decision, reasons = "NO-GO", ["High risk cannot be accepted – re-plan or cancel"]
    else:
        if not pilot:
            reasons.append("Select pilot")
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
        if (sig_name or "").strip() and (sig_name or "").strip().lower() != (pilot or "").lower():
            reasons.append("Signature must match selected pilot")
        decision = "INCOMPLETE" if reasons else "GO"

    if unassessed:
        reasons.append("Review every zero risk factor and select 1–10 before completing or saving")
        if decision != "NO-GO":
            decision = "INCOMPLETE"

    if decision == "GO":
        st.markdown(f"""<div style="background:#4CAF50; color:white; padding:18px; text-align:center; font-size:26px; font-weight:bold; border-radius:8px;">✅ GO – {part} – {level} accepted</div>""", unsafe_allow_html=True)
    elif decision == "NO-GO":
        st.markdown(f"""<div style="background:#F44336; color:white; padding:18px; text-align:center; font-size:26px; font-weight:bold; border-radius:8px;">⛔ NO-GO – {'; '.join(reasons)}</div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style="background:#FFC107; color:black; padding:18px; text-align:center; font-size:20px; font-weight:bold; border-radius:8px;">⚠️ NOT RELEASED – {'; '.join(reasons)}</div>""", unsafe_allow_html=True)

    st.caption("Fully reviewed NO-GO assessments should also be saved – they are part of the safety record.")
    signoff_complete = bool(pilot and pilot_accepts and sig_name == pilot)
    if not signoff_complete:
        st.caption("Select the matching pilot signature and check the attestation before saving, including NO-GO records.")
    if st.button("💾 Save Assessment", type="primary", use_container_width=True, disabled=(bool(unassessed) or decision == "INCOMPLETE" or not signoff_complete), key=assessment_key(f"frat_{part}_save")):
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
            st.caption(f"Save error: {type(e).__name__}: {e}")
            st.caption("Check Streamlit Secrets (CVHAPP app, not the test app), live Sheet sharing, connectivity and worksheet headers. Verify the last row before retrying to avoid duplicates.")

    st.link_button("📄 Open FRAT Google Sheet", frat_sheet_url(), use_container_width=True)

def show_frat_history():
    st.subheader("FRAT History")
    st.link_button("📄 Open FRAT Google Sheet", frat_sheet_url(), use_container_width=True)
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
# Mode Buttons (Pilot / Driver / Emergency remain so FRAT and existing tools stay reachable)
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
        "registration": "N893PC",
        # User-supplied aircraft-specific weights (lb); spray weight includes dry gear.
        "base_empty_weight_lbs": 1596,
        "spray_empty_weight_lbs": 1772,
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
        "registration": "N480ML",
        # User-supplied aircraft-specific weights (lb); spray weight includes dry gear.
        "base_empty_weight_lbs": 1822,
        "spray_empty_weight_lbs": 2013,
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

def aircraft_empty_weight(aircraft_data, part):
    """Part 137 includes dry spray equipment once; liquid is a separate payload."""
    field = "spray_empty_weight_lbs" if part == "Part 137" else "base_empty_weight_lbs"
    return aircraft_data[field]


def aircraft_total_weight(aircraft_data, part, pilot_weight, fuel_gal, payload_weight):
    return (aircraft_empty_weight(aircraft_data, part) + pilot_weight
            + fuel_gal * aircraft_data["fuel_weight_per_gal"] + payload_weight)


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

# Color the Monthly Safety Meeting header button from the current Pacific month.
apply_monthly_safety_header_style()

# ────────────────────────────────────────────────
# Pilot Mode
# ────────────────────────────────────────────────
if st.session_state.current_mode == "Pilot":
    st.title("🛩️ Pilot Performance Calculator")
    st.button("Reset / New Assessment", key="pilot_reset_request", on_click=request_assessment_reset)
    st.caption("Clears unsaved assessment only; saved records are kept.")
    if st.session_state.get("pilot_reset_pending", False):
        st.warning("Discard the current unsaved Pilot assessment and start a new one?")
        st.caption("Resets to N893PC / Part 135 with no pilot selected; flight inputs return to "
                   "their defaults (pilot weight 200 lb, fuel 30 gal, altitude 0 ft, OAT 15°C, "
                   "zero passengers/load). Review all defaults for the new flight.")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            st.button("Confirm reset", key="pilot_reset_confirm", on_click=reset_pilot_assessment)
        with cancel_col:
            st.button("Cancel", key="pilot_reset_cancel", on_click=cancel_assessment_reset)
    if "far_part" not in st.session_state:
        st.session_state.far_part = "Part 135"
    sel = st.segmented_control("Operation (FAR Part)", PARTS, default=st.session_state.far_part, key=assessment_key("far_part_ctrl"))
    if sel:
        st.session_state.far_part = sel
    part = st.session_state.far_part
    selected_aircraft = st.selectbox("Select Aircraft", list(AIRCRAFT_DATA.keys()),
        key=assessment_key("pilot_config_aircraft"), format_func=lambda name: f"{AIRCRAFT_DATA[name]['registration']} – {name}")
    aircraft_data = AIRCRAFT_DATA[selected_aircraft]
    st.subheader(f"Aircraft Configuration – {part}")
    empty_weight = aircraft_empty_weight(aircraft_data, part)
    empty_label = "Aircraft empty weight with spray gear" if part == "Part 137" else "Aircraft empty weight"
    st.metric(f"{aircraft_data['registration']} — {empty_label}", f"{empty_weight:,} lbs")
    st.caption("Empty weight used below excludes pilot, usable fuel and liquid spray load. "
               "Part 137 includes dry spray gear; it is not added again. "
               "This weight calculation does not establish CG compliance or operating authorization; "
               "use current aircraft W&B and approved manuals.")
    if part == "Part 135" and aircraft_data["registration"] == "N480ML":
        st.warning("N480ML is not approved for CVH Part 135 operations. "
                   "Displaying a weight calculation does not authorize this operation.")
    pressure_alt = st.number_input("Pressure Altitude (ft)", key=assessment_key("pilot_config_pressure_alt"), value=0, step=100)
    oat_c = st.number_input("Outside Air Temperature (°C)", key=assessment_key("pilot_config_oat_c"), value=15, step=1)
    pilot_weight = st.number_input("Pilot Weight (lbs)", key=assessment_key("pilot_config_pilot_weight"), value=200, step=10)
    fuel_gal = st.number_input("Fuel (gal)", key=assessment_key("pilot_config_fuel_gal"), value=30, step=5)
    config = {"pilot_weight": pilot_weight, "fuel_gal": fuel_gal}
    payload_weight = 0
    hook_limit = None
    ext_total = 0
    if part == "Part 91":
        pax_bag = st.number_input("Passenger/baggage weight (optional, lbs)", key=assessment_key("pilot_config_pax_bag"), value=0, step=10, min_value=0)
        payload_weight = pax_bag
        config["pax_weight"] = pax_bag
    elif part == "Part 135":
        max_pax = MAX_PAX[selected_aircraft]
        st.caption(f"Max passengers for {selected_aircraft}: {max_pax} (confirm with Ron)")
        pax_count = st.number_input("Number of passengers", key=assessment_key("pilot_config_pax_count"), min_value=0, max_value=max_pax, value=0, step=1)
        pax_mode = st.radio("Passenger weights", key=assessment_key("pilot_config_pax_mode"), options=["Total", "Individual"], horizontal=True)
        if pax_mode == "Individual" and pax_count > 0:
            pcols = st.columns(int(pax_count))
            pax_weight = sum(pcols[i].number_input(f"Pax {i+1} (lbs)", value=170, step=5, min_value=0, key=assessment_key(f"pax_w_{i}")) for i in range(int(pax_count)))
        else:
            pax_weight = st.number_input("Total passenger weight (lbs)", key=assessment_key("pilot_config_pax_weight"), value=0, step=10, min_value=0)
        baggage = st.number_input("Baggage weight (lbs)", key=assessment_key("pilot_config_baggage"), value=0, step=5, min_value=0)
        payload_weight = pax_weight + baggage
        config.update({"pax_count": pax_count, "pax_weight": pax_weight, "baggage_weight": baggage})
    elif part == "Part 137":
        st.info("Part 137: no non-crew passengers may be carried (§137.35/§137.41 – crew members essential to the operation only).")
        hopper_gal = st.number_input("Hopper / Spray load (gal)", key=assessment_key("pilot_config_hopper_gal"), value=0, step=5, min_value=0)
        density = st.number_input("Product density (lb/gal)", key=assessment_key("pilot_config_density"), value=8.34, step=0.01, format="%.2f")
        payload_weight = hopper_gal * density
        st.caption(f"Hopper load weight: {payload_weight:.0f} lbs (hopper capacity {aircraft_data['hopper_capacity_gal']} gal)")
        if hopper_gal > aircraft_data["hopper_capacity_gal"]:
            st.warning("Hopper load exceeds listed hopper capacity.")
        config.update({"hopper_gal": hopper_gal, "product_density": density})
    elif part == "Part 133":
        st.info("Part 133: no passengers. External load weight is limited by the RFM cargo hook limit – enter it from the RFM/supplement.")
        hook_equip = st.number_input("Hook/equipment weight carried internally (lbs)", key=assessment_key("pilot_config_hook_equip"), value=0, step=5, min_value=0)
        ext_load = st.number_input("External load weight (lbs)", key=assessment_key("pilot_config_ext_load"), value=0, step=10, min_value=0)
        longline = st.number_input("Longline length (ft)", key=assessment_key("pilot_config_longline"), value=0, step=10, min_value=0)
        hook_limit = st.number_input("Hook limit (lbs) [confirm hook limit from RFM]", key=assessment_key("pilot_config_hook_limit"), value=0, step=10, min_value=0)
        payload_weight = hook_equip
        ext_total = ext_load
        config.update({"hook_equip_weight": hook_equip, "ext_load_weight": ext_load, "longline_ft": longline, "hook_limit": hook_limit})
    da_ft = calculate_density_altitude(pressure_alt, oat_c)
    st.metric("Density Altitude", f"{da_ft:.0f} ft")
    total_weight = aircraft_total_weight(aircraft_data, part, pilot_weight, fuel_gal, payload_weight)
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
# HEADER PAGES (Equipment, Monthly Safety Meeting, Yearly Items, DOM, EMPLOYEES)
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Equipment":
    show_equipment_page()

elif st.session_state.current_mode == "Monthly Safety Meeting":
    show_safety_meetings_page()

elif st.session_state.current_mode == "Yearly Items":
    show_yearly_items_page()

elif st.session_state.current_mode == "DOM":
    show_dom_page()

elif st.session_state.current_mode == "EMPLOYEES":
    show_employees_page()

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
