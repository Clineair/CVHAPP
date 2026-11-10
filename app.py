from PIL import Image
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime
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

# CVH Logo and header navigation (logo left, four buttons right)
LOGO_URL = "flaglogo.png"
HEADER_PAGES = ["Monthly Safety Meeting", "Yearly Items", "Equipment", "DOM"]

# Button Colors and compact wrapping header buttons for phones
st.markdown("""
<style>
    .stButton button[data-baseweb="button"][kind="primary"] { background-color: #007BFF !important; color: white !important; } /* Blue - Pilot / active header */
    .stButton button[data-baseweb="button"][kind="secondary"] { background-color: #FFC107 !important; color: black !important; } /* Yellow - Driver */
    .stButton button[data-baseweb="button"][kind="tertiary"] { background-color: #DC3545 !important; color: white !important; } /* Red - Emergency */
    .stButton button { white-space: normal; line-height: 1.15; height: auto; min-height: 2.75rem; }
    /* Keep the flag logo and the four header buttons on one row on phones. */
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
            st.rerun()
    hr1, hr2 = st.columns(2)
    with hr1:
        _header_btn("Monthly Safety Meeting", "Monthly Safety Meeting", "nav_monthly_safety")
    with hr2:
        _header_btn("Yearly Items", "Yearly Items", "nav_yearly_items")
    hr3, hr4 = st.columns(2)
    with hr3:
        _header_btn("Equipment", "Equipment", "nav_equipment")
    with hr4:
        _header_btn("DOM", "DOM", "nav_dom")

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


def update_safety_meeting_discussion(timestamp, notes, spreadsheet=None):
    """Replace Discussion Notes on the matching meeting row only. Never other tabs."""
    timestamp = _cell(timestamp)
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
    for row_number, row in enumerate(values[1:], start=2):
        row_ts = _cell(row[ts_idx]) if ts_idx < len(row) else ""
        if row_ts != timestamp:
            continue
        ws.update_cell(row_number, notes_col, _cell(notes))
        return True
    raise RuntimeError("Could not find that meeting on the Safety Meetings tab")


def _safety_meeting_sort_key(record):
    stamp = parse_equipment_date(_cell(record.get("Timestamp"))[:10]) if _cell(record.get("Timestamp")) else None
    # Prefer the full timestamp when present so same-day meetings sort correctly.
    text_value = _cell(record.get("Timestamp"))
    if text_value:
        from datetime import datetime as _dt
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                return _dt.strptime(text_value, fmt)
            except ValueError:
                continue
    meeting = parse_equipment_date(record.get("Meeting Date"))
    if meeting is not None:
        return datetime(meeting.year, meeting.month, meeting.day)
    if stamp is not None:
        return datetime(stamp.year, stamp.month, stamp.day)
    return datetime.min


def show_safety_meetings_page():
    """Monthly Safety Meeting form and past-meeting list. Phone-friendly, stacked fields."""
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
            st.rerun()

    st.markdown("---")
    st.subheader("Past meetings")
    if not meetings:
        st.info("No meetings recorded yet.")
        return
    for meeting in sorted(meetings, key=_safety_meeting_sort_key, reverse=True):
        stamp = _cell(meeting.get("Timestamp"))
        meeting_date = _cell(meeting.get("Meeting Date")) or "Meeting"
        recorded = _cell(meeting.get("Recorded By"))
        title = meeting_date + ((" — " + recorded) if recorded else "")
        if stamp:
            title = title + "  (" + stamp + ")"
        with st.expander(title):
            attendees = _cell(meeting.get("Attendees"))
            st.markdown("**Attendees:** " + (attendees if attendees else "—"))
            for item in SAFETY_MEETING_ITEMS:
                done = _cell(meeting.get(item + " Done"))
                note = _cell(meeting.get(item + " Note"))
                mark = "Yes" if done.lower() in {"yes", "y", "true", "1"} else "No"
                line = "**" + item + ":** " + ("Done / Reviewed" if mark == "Yes" else "Not reviewed")
                if note:
                    line = line + " — " + note
                st.markdown(line)
            disc_key = "safety_past_disc_" + _safety_item_key(stamp or meeting_date)
            if disc_key not in st.session_state:
                st.session_state[disc_key] = _cell(meeting.get("Discussion Notes"))
            st.text_area("Discussion Notes", key=disc_key, height=140)
            if st.button("Save discussion notes", key="safety_past_save_" + _safety_item_key(stamp or meeting_date), use_container_width=True):
                try:
                    update_safety_meeting_discussion(stamp, st.session_state.get(disc_key, ""), spreadsheet=spreadsheet)
                except Exception as exc:
                    st.error(f"Could not update discussion notes: {exc}")
                else:
                    st.session_state.safety_meeting_notes_saved = "Updated discussion notes for " + meeting_date + "."
                    st.rerun()


def show_placeholder_page(title):
    st.title(title)
    st.info("Coming soon - Ron to define contents")


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
            _kind, markup = hobbs_status_markup(label, due, current, amber_hours)
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
        _kind, markup = hobbs_status_markup(label, due, current_hobbs_val, amber_hours)
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
                    st.markdown("**" + label + " due:** " + (format_hobbs(due) or "—"))
            if _cell(item.get("Entered By")):
                st.markdown("**Entered By:** " + _cell(item.get("Entered By")))


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
    for aircraft in DOM_AIRCRAFT:
        aid = _cell(aircraft.get("id") or aircraft.get("name"))
        if not aid:
            continue
        label = _cell(aircraft.get("name")) or aid
        st.markdown("**" + label + "**")
        if st.button(DOM_ACTION_ANNUAL, key="dom_annual_" + aid, use_container_width=True):
            st.session_state.dom_annual_aircraft = aid
            st.rerun()


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


def show_equipment_page():
    st.title("Equipment Squawks")
    st.caption(
        "Tap a unit and save a squawk to the Google Sheet. "
        "Edit names on the Equipment tab of the CVH FRAT Log if the list changes."
    )
    st.link_button("Open CVH FRAT Log (Equipment and Squawks tabs)", frat_sheet_url(), use_container_width=True)
    try:
        spreadsheet = _gsheets_spreadsheet()
        units = [u for u in load_equipment_records(spreadsheet) if is_active_equipment(u) and _cell(u.get("Unit ID"))]
        squawks = load_squawk_records(spreadsheet)
    except Exception as e:
        st.error(f"Could not load equipment or squawks: {e}")
        return

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
        name_col, info_col, squawk_col = st.columns([3.2, 1, 1])
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
                st.rerun()
        with squawk_col:
            if st.button("Squawk", key=f"squawk_btn_{unit_id}", use_container_width=True):
                clear_equipment_edit_widgets(st.session_state.get("edit_unit_id"))
                st.session_state.squawk_unit_id = unit_id
                st.session_state.info_unit_id = None
                st.session_state.edit_unit_id = None
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
# HEADER PAGES (Equipment, Monthly Safety Meeting, DOM aircraft list; Yearly Items is a placeholder)
# ────────────────────────────────────────────────
elif st.session_state.current_mode == "Equipment":
    show_equipment_page()

elif st.session_state.current_mode == "Monthly Safety Meeting":
    show_safety_meetings_page()

elif st.session_state.current_mode == "Yearly Items":
    show_placeholder_page("Yearly Items")

elif st.session_state.current_mode == "DOM":
    show_dom_page()

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
