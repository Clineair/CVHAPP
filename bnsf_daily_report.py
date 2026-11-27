"""BNSF Daily Field Report: gather, review, save, and print the CVH form."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import bnsf_notice
import bnsf_weather as bw

PACIFIC = ZoneInfo("America/Los_Angeles")
ACRES_PER_LOAD = 15.0
DEFAULT_AIRCRAFT_ID = "N480ML"
WEATHER_SLOTS = 6
SPRAY_ROWS = 30
FORM_TEMPLATE = Path(__file__).resolve().parent / "data" / "CVH_DAILY_FIELD_REPORT.docx"
FORM_LOGO = Path(__file__).resolve().parent / "data" / "cvh_eagle_logo.jpeg"
NPDES_LINE = "Met NPDES Requirements.  Buffered Water Crossings 50’ on Each Side."
FORM_PRODUCT_MIX_FALLBACK = (
    "Triumph 22k: 24 oz/@, Edict RTU: 8 oz/@, MSM 60 DF: 1oz/@, "
    "Novita DF: 4oz/@, Novita Foamnomore: 1oz/100 (as needed)."
)

BNSF_DAILY_REPORT_SHEET_TITLE = "BNSF Daily Reports"
BNSF_NOTICE_SHEET_TITLE = "BNSF 10-Day Notices"

SPRAY_FIELDS = ("Time", "MP ST", "MP END", "MP ST 2", "MP END 2", "Notes")


def _weather_slot_columns():
    names = ("Time", "Sky", "Wind Speed", "Wind Direction", "Temperature", "Precipitation", "MP Location")
    columns = []
    for index in range(1, WEATHER_SLOTS + 1):
        for name in names:
            columns.append("Weather %s %s" % (index, name))
    return columns


BNSF_DAILY_REPORT_COLUMNS = [
    "Entry ID",
    "Timestamp",
    "Date",
    "Pilot",
    "Aircraft",
    "Hobbs Start",
    "Hobbs End",
    "Flight Time",
    "BNSF Subdivision",
    "Division",
    "Line Segment",
    "MP Start",
    "MP End",
    "County",
    "BNSF Time Start",
    "BNSF Time End",
    "CVH Time Start",
    "CVH Time End",
    "Loads",
    "Acres Sprayed",
    "Video ON",
    "Product mix",
    "Notice ID",
    "Notice title",
    "Roadmaster",
] + _weather_slot_columns() + [
    "Spray log",
    "Not sprayed",
    "Notes",
    "Edited fields",
]

BNSF_NOTICE_COLUMNS = [
    "Entry ID",
    "Timestamp",
    "Title",
    "Notice ID",
    "Roadmaster",
    "Roadmaster ID",
    "Division",
    "Program Name",
    "Product mix",
    "Segments JSON",
    "Source",
]


def _cell(value):
    return str(value or "").strip()


def _as_pacific(when=None):
    when = when or datetime.now(PACIFIC)
    if when.tzinfo is None:
        return when.replace(tzinfo=PACIFIC)
    return when.astimezone(PACIFIC)


def format_timestamp(when=None):
    return _as_pacific(when).strftime("%Y-%m-%d %H:%M:%S")


def format_date(when=None):
    return _as_pacific(when).strftime("%Y-%m-%d")


def format_date_mdy(when=None):
    return _as_pacific(when).strftime("%m/%d/%Y")


def format_clock(when=None):
    when = _as_pacific(when)
    hour = when.strftime("%I").lstrip("0") or "12"
    return hour + when.strftime(":%M %p")


def new_entry_id(prefix="DR", when=None):
    import uuid
    when = _as_pacific(when)
    return prefix + "-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def aircraft_id(value, default=DEFAULT_AIRCRAFT_ID):
    match = re.search(r"\bN[0-9A-Z]{2,6}\b", _cell(value), re.I)
    if match:
        return match.group(0).upper()
    return default


def parse_hobbs(value):
    text = _cell(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group())


def format_hobbs(value):
    if value is None or value == "":
        return ""
    try:
        return ("%.1f" % float(value)).rstrip("0").rstrip(".") + ("0" if False else "")
    except (TypeError, ValueError):
        return _cell(value)


def flight_time_hours(hobbs_start, hobbs_end):
    start = parse_hobbs(hobbs_start)
    end = parse_hobbs(hobbs_end)
    if start is None or end is None:
        return ""
    if end < start:
        return ""
    return "%.1f" % (end - start)


def acres_from_loads(loads):
    try:
        count = float(loads)
    except (TypeError, ValueError):
        return ""
    if count < 0:
        return ""
    acres = count * ACRES_PER_LOAD
    text = ("%.1f" % acres).rstrip("0").rstrip(".")
    return text


def parse_clock(text, day=None):
    """Parse a time like '7:12 AM' or '07:12' onto the given Pacific date."""
    raw = _cell(text).upper().replace(".", "")
    if not raw:
        return None
    day = _as_pacific(day).date() if day is not None else _as_pacific().date()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H%M", "%I %p"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return datetime.combine(day, parsed.time(), tzinfo=PACIFIC)
        except ValueError:
            continue
    return None


def parse_mp(value):
    text = _cell(value)
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group())


def empty_spray_rows(count=SPRAY_ROWS):
    return [{field: "" for field in SPRAY_FIELDS} for _ in range(count)]


def normalize_spray_rows(rows):
    out = empty_spray_rows()
    for index, row in enumerate(rows or []):
        if index >= SPRAY_ROWS:
            break
        for field in SPRAY_FIELDS:
            out[index][field] = _cell((row or {}).get(field))
    return out


def clocks_key(pilot, now=None):
    return "bnsf_ops_clocks|" + (_cell(pilot) or "none") + "|" + format_date(now)


def default_clocks():
    return {
        "bnsf_start": "",
        "bnsf_end": "",
        "cvh_start": "",
        "cvh_end": "",
    }


def get_ops_clocks(store, pilot, now=None):
    store = store if store is not None else {}
    data = store.get(clocks_key(pilot, now)) or {}
    clocks = default_clocks()
    clocks.update({k: _cell(data.get(k)) for k in clocks})
    return clocks


def set_ops_clocks(store, pilot, fields, now=None):
    key = clocks_key(pilot, now)
    clocks = get_ops_clocks(store, pilot, now=now)
    clocks.update({k: _cell(v) for k, v in (fields or {}).items() if k in clocks})
    store[key] = clocks
    return clocks


def start_bnsf_spray(store, pilot, now=None):
    """BNSF Start: spraying is underway, and a previous Stop no longer applies."""
    return set_ops_clocks(store, pilot, {"bnsf_start": format_clock(now), "bnsf_end": ""}, now=now)


def stop_bnsf_spray(store, pilot, now=None):
    """BNSF Stop: the spray session is over."""
    return set_ops_clocks(store, pilot, {"bnsf_end": format_clock(now)}, now=now)


def spraying_in_progress(clocks):
    """True from BNSF Start until BNSF Stop. A blank end time means still spraying."""
    clocks = clocks or {}
    return bool(_cell(clocks.get("bnsf_start"))) and not _cell(clocks.get("bnsf_end"))


def bnsf_nav_visible(aircraft, far_part):
    """BNSF is offered only after an aircraft is chosen and the operation is FAR 137."""
    return bool(_cell(aircraft)) and _cell(far_part) == "Part 137"


def pilot_menu_bnsf(aircraft, far_part, opened=False):
    """What the Pilot menu shows for BNSF. Pages stay behind the button."""
    button = bnsf_nav_visible(aircraft, far_part)
    return {"button": button, "pages": button and bool(opened)}


def bnsf_aircraft_label(registration, labels):
    """Match the Pilot-menu aircraft to a BNSF aircraft label. Blank if none match."""
    wanted = _cell(registration).upper()
    if not wanted:
        return ""
    for label in labels or []:
        if wanted in _cell(label).upper():
            return label
    return wanted


def not_sprayed_actions(spraying):
    """Voice and Mark MP are in-flight only. Review stays available after landing."""
    active = bool(spraying)
    return {
        "capture": active,
        "review": True,
        "note": "" if active else "Available while spraying.",
    }


def weather_logs_for_pilot_date(records, pilot, now=None):
    now = _as_pacific(now)
    name = _cell(pilot)
    rows = []
    for record in records or []:
        if name and _cell(record.get("Pilot")) != name:
            continue
        if bw.record_date(record, tz=PACIFIC) != now.date():
            continue
        stamp = bw.parse_sheet_timestamp(record.get("Timestamp"), tz=PACIFIC)
        rows.append((stamp or datetime.min.replace(tzinfo=PACIFIC), record))
    rows.sort(key=lambda item: item[0])
    return [record for _stamp, record in rows]


def weather_slots_from_logs(records, limit=WEATHER_SLOTS):
    slots = []
    for record in (records or [])[:limit]:
        stamp = bw.parse_sheet_timestamp(record.get("Timestamp"), tz=PACIFIC)
        time_text = format_clock(stamp) if stamp else _cell(record.get("Timestamp"))
        slots.append({
            "Time": time_text,
            "Sky": _cell(record.get("Sky condition")),
            "Wind Speed": _cell(record.get("Wind (mph)")),
            "Wind Direction": _cell(record.get("Wind direction")),
            "Temperature": _cell(record.get("Temperature (F)")),
            "Precipitation": _cell(record.get("Precipitation")),
            "MP Location": _cell(record.get("Location")),
            "Division": _cell(record.get("Division")),
            "Subdivision": _cell(record.get("Subdivision")),
            "Mile marker": _cell(record.get("Mile marker")),
            "Latitude": _cell(record.get("Latitude")),
            "Longitude": _cell(record.get("Longitude")),
        })
    while len(slots) < limit:
        slots.append({key: "" for key in ("Time", "Sky", "Wind Speed", "Wind Direction", "Temperature", "Precipitation", "MP Location", "Division", "Subdivision", "Mile marker", "Latitude", "Longitude")})
    return slots


def most_common(values):
    counts = {}
    for value in values:
        text = _cell(value)
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def mp_range_from_values(*groups):
    numbers = []
    for group in groups:
        for value in group or []:
            parsed = parse_mp(value)
            if parsed is not None:
                numbers.append(parsed)
    if not numbers:
        return "", ""
    return bw.format_milepost(min(numbers)), bw.format_milepost(max(numbers))


def lookup_county(lat, lon, session=None):
    """County name from the NWS points API, or empty if it cannot be found."""
    if lat is None or lon is None or lat == "" or lon == "":
        return ""
    try:
        session = session or __import__("requests")
        points = bw._session_get(session, "https://api.weather.gov/points/%.4f,%.4f" % (float(lat), float(lon)))
        points.raise_for_status()
        county_url = ((points.json() or {}).get("properties") or {}).get("county")
        if not county_url:
            return ""
        county = bw._session_get(session, county_url)
        county.raise_for_status()
        name = ((county.json() or {}).get("properties") or {}).get("name") or ""
        return _cell(name)
    except Exception:
        return ""


def county_from_slots(slots, lookup=lookup_county):
    for slot in slots or []:
        if slot.get("Latitude") and slot.get("Longitude"):
            name = lookup(slot.get("Latitude"), slot.get("Longitude"))
            if name:
                return name
    return ""


def gather_daily_report(pilot, aircraft="", weather_records=None, clocks=None, notice=None, spray_rows=None, loads="", hobbs_start="", hobbs_end="", video_on="Yes", county="", now=None, county_lookup=lookup_county, not_sprayed=None):
    """Build a prefilled Daily Field Report from the day's logs and a 10-day notice."""
    now = _as_pacific(now)
    clocks = clocks or default_clocks()
    logs = weather_logs_for_pilot_date(weather_records, pilot, now=now)
    slots = weather_slots_from_logs(logs)
    spray_rows = normalize_spray_rows(spray_rows)
    division = most_common([s.get("Division") for s in slots] + [((notice or {}).get("division") or "")])
    subdivision = most_common([s.get("Subdivision") for s in slots])
    spray_mps = []
    for row in spray_rows:
        spray_mps.extend([row.get("MP ST"), row.get("MP END"), row.get("MP ST 2"), row.get("MP END 2")])
    mp_start, mp_end = mp_range_from_values([s.get("Mile marker") for s in slots], spray_mps)
    if not county:
        county = county_from_slots(slots, lookup=county_lookup)
    line_segment = ""
    product_mix = FORM_PRODUCT_MIX_FALLBACK
    notice_id = ""
    notice_title = ""
    roadmaster = ""
    if notice:
        product_mix = _cell(notice.get("product_mix")) or product_mix
        notice_id = _cell(notice.get("id"))
        notice_title = _cell(notice.get("title") or notice.get("program_name"))
        roadmaster = _cell(notice.get("roadmaster"))
        if not division and notice.get("division"):
            division = _cell(notice.get("division"))
        mid = parse_mp(mp_start) if mp_start else None
        if mid is None:
            mid = parse_mp(mp_end)
        matched = bnsf_notice.match_segment(notice, subdivision, mid)
        if matched:
            line_segment = bnsf_notice.segment_label(matched)
            if not subdivision:
                subdivision = _cell(matched.get("subdivision"))
    acres = acres_from_loads(loads)
    report = {
        "Pilot": _cell(pilot),
        "Aircraft": aircraft_id(aircraft),
        "Date": format_date(now),
        "Date display": format_date_mdy(now),
        "Hobbs Start": _cell(hobbs_start),
        "Hobbs End": _cell(hobbs_end),
        "Flight Time": flight_time_hours(hobbs_start, hobbs_end),
        "BNSF Subdivision": subdivision,
        "Division": division,
        "Line Segment": line_segment,
        "MP Start": mp_start,
        "MP End": mp_end,
        "County": county,
        "BNSF Time Start": _cell(clocks.get("bnsf_start")),
        "BNSF Time End": _cell(clocks.get("bnsf_end")),
        "CVH Time Start": _cell(clocks.get("cvh_start")),
        "CVH Time End": _cell(clocks.get("cvh_end")),
        "Loads": _cell(loads),
        "Acres Sprayed": acres,
        "Video ON": _cell(video_on) or "Yes",
        "Product mix": product_mix,
        "Notice ID": notice_id,
        "Notice title": notice_title,
        "Roadmaster": roadmaster,
        "weather_slots": slots,
        "spray_rows": spray_rows,
        "not_sprayed": list(not_sprayed or []),
        "Notes": "",
    }
    return report


def report_to_record(report, original=None, when=None, entry_id=None):
    when = _as_pacific(when)
    record = {column: "" for column in BNSF_DAILY_REPORT_COLUMNS}
    for column in BNSF_DAILY_REPORT_COLUMNS:
        if column in report and column not in {"weather_slots", "spray_rows", "Spray log", "not_sprayed", "Not sprayed"}:
            record[column] = _cell(report.get(column))
    slots = report.get("weather_slots") or weather_slots_from_logs([])
    names = ("Time", "Sky", "Wind Speed", "Wind Direction", "Temperature", "Precipitation", "MP Location")
    for index, slot in enumerate(slots, start=1):
        for name in names:
            record["Weather %s %s" % (index, name)] = _cell(slot.get(name))
    rows = normalize_spray_rows(report.get("spray_rows"))
    record["Spray log"] = json.dumps(rows, separators=(",", ":"))
    record["Not sprayed"] = json.dumps(normalize_not_sprayed(report.get("not_sprayed")), separators=(",", ":"))
    record["Entry ID"] = entry_id or new_entry_id("DR", when)
    record["Timestamp"] = format_timestamp(when)
    record["Date"] = format_date(when)
    changed = []
    if original:
        changed = bw.edited_fields(original, {**record, **{k: report.get(k, "") for k in report}}, fields=[
            "Pilot", "Aircraft", "Hobbs Start", "Hobbs End", "Flight Time",
            "BNSF Subdivision", "Division", "Line Segment", "MP Start", "MP End",
            "County", "BNSF Time Start", "BNSF Time End", "CVH Time Start", "CVH Time End",
            "Loads", "Acres Sprayed", "Video ON", "Product mix",
        ])
    record["Edited fields"] = ", ".join(changed)
    return record


def record_to_report(record):
    report = {column: _cell(record.get(column)) for column in BNSF_DAILY_REPORT_COLUMNS}
    report["Date display"] = ""
    if report.get("Date"):
        try:
            report["Date display"] = datetime.strptime(report["Date"][:10], "%Y-%m-%d").strftime("%m/%d/%Y")
        except ValueError:
            report["Date display"] = report["Date"]
    slots = []
    names = ("Time", "Sky", "Wind Speed", "Wind Direction", "Temperature", "Precipitation", "MP Location")
    for index in range(1, WEATHER_SLOTS + 1):
        slot = {name: _cell(record.get("Weather %s %s" % (index, name))) for name in names}
        slots.append(slot)
    report["weather_slots"] = slots
    raw = _cell(record.get("Spray log"))
    rows = empty_spray_rows()
    if raw:
        try:
            parsed = json.loads(raw)
            rows = normalize_spray_rows(parsed)
        except json.JSONDecodeError:
            pass
    report["spray_rows"] = rows
    raw_ns = _cell(record.get("Not sprayed"))
    report["not_sprayed"] = []
    if raw_ns:
        try:
            report["not_sprayed"] = normalize_not_sprayed(json.loads(raw_ns))
        except json.JSONDecodeError:
            report["not_sprayed"] = []
    return report


def _set_paragraph_text(paragraph, text):
    runs = paragraph.runs
    if runs:
        runs[0].text = text
        for run in runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def _fill_labeled_cell(cell, label_prefixes, value):
    text = cell.text or ""
    if not any(text.strip().startswith(prefix) or prefix in text for prefix in label_prefixes):
        return False
    # Keep the original label (everything through the last colon) and put the value after it.
    if ":" in text:
        label = text.split(":", 1)[0] + ":"
        new_text = label + (("  " + _cell(value)) if _cell(value) else "")
    else:
        new_text = text.rstrip() + (("  " + _cell(value)) if _cell(value) else "")
    if cell.paragraphs:
        _set_paragraph_text(cell.paragraphs[0], new_text)
        for extra in cell.paragraphs[1:]:
            _set_paragraph_text(extra, "")
    return True


def fill_daily_report_docx(report, template_path=None):
    """Fill the official CVH Daily Field Report Word form. Returns .docx bytes."""
    from docx import Document

    path = Path(template_path or FORM_TEMPLATE)
    document = Document(str(path))
    date_text = report.get("Date display") or format_date_mdy()
    for paragraph in document.paragraphs:
        text = paragraph.text or ""
        if "DATE:" in text or "DAILY FIELD REPORT" in text:
            updated = re.sub(r"DATE:\s*\d{0,2}\s*/\s*\d{0,2}\s*/\s*\d{2,4}", "DATE:  " + date_text, text)
            updated = re.sub(r"DATE:\s*/\s*/\s*\d{2,4}", "DATE:  " + date_text, updated)
            updated = re.sub(r"/2025", "/" + date_text[-4:], updated) if "DATE:" not in updated else updated
            if "DATE:" in text and date_text not in updated:
                updated = re.sub(r"DATE:.*", "DATE:  " + date_text, text)
            _set_paragraph_text(paragraph, updated)
        if text.strip().startswith("PRODUCTS:"):
            mix = _cell(report.get("Product mix"))
            if mix:
                _set_paragraph_text(paragraph, "PRODUCTS: " + mix)

    header_map = [
        (("Hobbs   End", "Hobbs End"), report.get("Hobbs End")),
        (("Hobbs Start",), report.get("Hobbs Start")),
        (("Flight  Time", "Flight Time"), report.get("Flight Time")),
        (("Pilot:", "Pilot"), report.get("Pilot")),
        (("Acres Sprayed",), report.get("Acres Sprayed")),
        (("BNSF Subdivision",), report.get("BNSF Subdivision")),
        (("Division:", "Division"), report.get("Division")),
        (("Line Segment",), report.get("Line Segment")),
        (("Aircraft ID", "Aircraft"), report.get("Aircraft")),
        (("MP Start",), report.get("MP Start")),
        (("MP  End", "MP End"), report.get("MP End")),
        (("County:", "County"), report.get("County")),
        (("BNSF Time Start",), report.get("BNSF Time Start")),
        (("BNSF Time  End", "BNSF Time End"), report.get("BNSF Time End")),
        (("CVH Time  Start", "CVH Time Start"), report.get("CVH Time Start")),
        (("CVH Time    End", "CVH Time End"), report.get("CVH Time End")),
        (("Video ON",), report.get("Video ON")),
    ]
    if document.tables:
        header = document.tables[0]
        used = set()
        for row in header.rows:
            for cell in row.cells:
                for prefixes, value in header_map:
                    key = prefixes[0]
                    if key in used:
                        continue
                    if _fill_labeled_cell(cell, prefixes, value):
                        used.add(key)
                        break

    if len(document.tables) >= 2:
        weather = document.tables[1]
        slots = report.get("weather_slots") or weather_slots_from_logs([])
        row_keys = [
            ("Time", "Time"),
            ("Sky Condition", "Sky"),
            ("Wind Speed", "Wind Speed"),
            ("Wind Direction", "Wind Direction"),
            ("Temperature", "Temperature"),
            ("Precipitation", "Precipitation"),
            ("MP Location", "MP Location"),
        ]
        for r_index, (_label, key) in enumerate(row_keys):
            if r_index >= len(weather.rows):
                break
            row = weather.rows[r_index]
            for c_index in range(1, min(len(row.cells), WEATHER_SLOTS + 1)):
                value = _cell(slots[c_index - 1].get(key))
                if row.cells[c_index].paragraphs:
                    _set_paragraph_text(row.cells[c_index].paragraphs[0], value)

    if len(document.tables) >= 3:
        spray = document.tables[2]
        rows = spray_rows_with_not_sprayed(report.get("spray_rows"), report.get("not_sprayed"))
        for r_index in range(1, min(len(spray.rows), SPRAY_ROWS + 1)):
            row = rows[r_index - 1]
            cells = spray.rows[r_index].cells
            values = [
                "",
                row["Time"],
                row["MP ST"],
                row["MP END"],
                "",
                row["MP ST 2"],
                row["MP END 2"],
                row["Notes"],
            ]
            for c_index, value in enumerate(values):
                if c_index == 0 or c_index >= len(cells):
                    continue
                if cells[c_index].paragraphs:
                    _set_paragraph_text(cells[c_index].paragraphs[0], value)

    for item in normalize_not_sprayed(report.get("not_sprayed")):
        source = item["MP source"] or "GPS"
        document.add_paragraph(
            "Not sprayed %s %s MP %s (%s) %s — %s [%s]"
            % (
                item["Date display"] or item["Date"],
                item["Time"],
                item["MP"] or "—",
                source,
                item["Aircraft"] or DEFAULT_AIRCRAFT_ID,
                item["Reason"] or "(no reason yet)",
                item["Status"] or NOT_SPRAYED_STATUS,
            )
        )
        if item["Transcript"]:
            document.add_paragraph("Transcript: " + item["Transcript"])

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_logo():
    path = FORM_LOGO
    if path.is_file():
        return str(path)
    return None


def build_daily_report_pdf(report):
    """Look-alike PDF of the CVH Daily Field Report (used on Streamlit Cloud)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether, PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title="CVH Daily Field Report",
        author="Central Valley Helicopters",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Normal"], fontName="Times-Bold", fontSize=13, alignment=TA_CENTER, leading=16)
    date_style = ParagraphStyle("ReportDate", parent=styles["Normal"], fontName="Times-Bold", fontSize=11, alignment=TA_RIGHT, leading=14)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontName="Times-Roman", fontSize=8, leading=10)
    small_bold = ParagraphStyle("SmallBold", parent=styles["Normal"], fontName="Times-Bold", fontSize=9, leading=11, textColor=colors.HexColor("#222222"))
    warning = ParagraphStyle("WeatherWarn", parent=styles["Normal"], fontName="Times-Bold", fontSize=10, textColor=colors.HexColor("#b00000"), leading=12)
    cell = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Times-Roman", fontSize=7, leading=9)
    label = ParagraphStyle("Label", parent=styles["Normal"], fontName="Times-Bold", fontSize=7, leading=9)
    footer = ParagraphStyle("Footer", parent=styles["Normal"], fontName="Times-Roman", fontSize=8, leading=10)

    def P(text, style=cell):
        return Paragraph((_cell(text) or "&nbsp;").replace(" ", "&nbsp;") if False else (_cell(text).replace("&", "&amp;") or " "), style)

    flow = []
    logo_path = _pdf_logo()
    date_text = "DATE:  " + (report.get("Date display") or format_date_mdy())
    if logo_path:
        logo = Image(logo_path, width=0.95 * inch, height=0.64 * inch)
    else:
        logo = Paragraph("CENTRAL VALLEY<br/>HELICOPTERS", small_bold)
    header = Table(
        [[logo, Paragraph("DAILY FIELD REPORT", title_style), Paragraph(date_text, date_style)]],
        colWidths=[1.15 * inch, 4.5 * inch, 2.0 * inch],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    flow.append(header)
    flow.append(Spacer(1, 4))

    def labeled(name, value):
        return Paragraph("<b>%s</b>  %s" % (name, _cell(value)), label)

    r = report
    header_data = [
        [labeled("Hobbs End:", r.get("Hobbs End")), labeled("BNSF Subdivision:", r.get("BNSF Subdivision")),
         labeled("MP Start:", r.get("MP Start")), labeled("BNSF Time Start:", r.get("BNSF Time Start"))],
        [labeled("Hobbs Start:", r.get("Hobbs Start")), labeled("Division:", r.get("Division")),
         labeled("MP End:", r.get("MP End")), labeled("BNSF Time End:", r.get("BNSF Time End"))],
        [labeled("Flight Time:", r.get("Flight Time")), labeled("Line Segment:", r.get("Line Segment")),
         labeled("County:", r.get("County")), labeled("CVH Time Start:", r.get("CVH Time Start"))],
        [labeled("Pilot:", r.get("Pilot")), labeled("Aircraft ID:", r.get("Aircraft")),
         Paragraph("", cell), labeled("CVH Time End:", r.get("CVH Time End"))],
        [labeled("Acres Sprayed:", r.get("Acres Sprayed")), Paragraph("", cell),
         Paragraph("", cell), labeled("Video ON?", r.get("Video ON"))],
    ]
    header_table = Table(header_data, colWidths=[1.85 * inch, 2.15 * inch, 1.5 * inch, 2.15 * inch])
    header_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(header_table)
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("WEATHER EVERY 2 HOURS!", warning))

    slots = r.get("weather_slots") or weather_slots_from_logs([])
    weather_rows = [
        ["Time"] + [P(s.get("Time")) for s in slots],
        ["Sky Condition"] + [P(s.get("Sky")) for s in slots],
        ["Wind Speed"] + [P(s.get("Wind Speed")) for s in slots],
        ["Wind Direction"] + [P(s.get("Wind Direction")) for s in slots],
        ["Temperature"] + [P(s.get("Temperature")) for s in slots],
        ["Precipitation"] + [P(s.get("Precipitation")) for s in slots],
        ["MP Location"] + [P(s.get("MP Location")) for s in slots],
    ]
    label_w = 1.2 * inch
    slot_w = (7.65 * inch - label_w) / WEATHER_SLOTS
    weather_table = Table(weather_rows, colWidths=[label_w] + [slot_w] * WEATHER_SLOTS)
    weather_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (0, -1), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    flow.append(weather_table)
    flow.append(Spacer(1, 6))
    mix = _cell(r.get("Product mix")) or FORM_PRODUCT_MIX_FALLBACK
    flow.append(Paragraph("<b>PRODUCTS:</b> " + mix.replace("&", "&amp;"), small))
    flow.append(Spacer(1, 6))

    spray = spray_rows_with_not_sprayed(r.get("spray_rows"), r.get("not_sprayed"))
    spray_header = ["#", "Time", "MP ST", "MP END", "", "MP ST", "MP END", "NOTES / REASON FOR NO SPRAY"]
    spray_data = [spray_header]
    for index, row in enumerate(spray, start=1):
        spray_data.append([
            str(index),
            P(row["Time"]),
            P(row["MP ST"]),
            P(row["MP END"]),
            "",
            P(row["MP ST 2"]),
            P(row["MP END 2"]),
            P(row["Notes"]),
        ])
    widths = [0.28 * inch, 0.95 * inch, 0.7 * inch, 0.75 * inch, 0.15 * inch, 0.7 * inch, 0.75 * inch, 3.37 * inch]
    # Page 1: header + first 21 rows; page 2: remaining + NPDES
    first, rest = spray_data[:22], spray_data[22:]  # header + 21 rows

    def spray_table(data, header=True):
        table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold") if header else ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("BACKGROUND", (4, 0), (4, -1), colors.white),
        ]))
        return table

    flow.append(spray_table(first, header=True))
    if rest:
        flow.append(PageBreak())
        flow.append(spray_table([spray_header] + rest, header=True))
    not_sprayed = normalize_not_sprayed(r.get("not_sprayed"))
    if not_sprayed:
        flow.append(Spacer(1, 8))
        flow.append(Paragraph("NOT SPRAYED", warning))
        for item in not_sprayed:
            source = item["MP source"] or "GPS"
            line = "%s %s  MP %s (%s)  %s  %s  [%s]" % (
                item["Date display"] or item["Date"],
                item["Time"],
                item["MP"] or "—",
                source,
                item["Aircraft"] or DEFAULT_AIRCRAFT_ID,
                item["Reason"] or "(no reason yet)",
                item["Status"] or NOT_SPRAYED_STATUS,
            )
            flow.append(Paragraph(line, small))
            if item["Transcript"]:
                flow.append(Paragraph("Transcript: " + item["Transcript"], small))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(NPDES_LINE, footer))
    doc.build(flow)
    return buffer.getvalue()


def _worksheet_or_none(spreadsheet, title):
    return bw._worksheet_or_none(spreadsheet, title)


def ensure_worksheet(spreadsheet, title, columns, rows=400):
    worksheet = _worksheet_or_none(spreadsheet, title)
    created = False
    if worksheet is None:
        worksheet = spreadsheet.add_worksheet(title=title, rows=rows, cols=max(len(columns), 12))
        worksheet.append_row(list(columns), value_input_option="RAW")
        created = True
    else:
        header = [_cell(col) for col in worksheet.row_values(1)]
        if not header:
            worksheet.append_row(list(columns), value_input_option="RAW")
            created = True
        else:
            missing = [col for col in columns if col not in header]
            if missing:
                bw._write_header_row(worksheet, header + missing)
    return worksheet, created


def ensure_bnsf_daily_report_worksheet(spreadsheet):
    """Create the BNSF Daily Reports tab when missing. Never writes other tabs."""
    return ensure_worksheet(spreadsheet, BNSF_DAILY_REPORT_SHEET_TITLE, BNSF_DAILY_REPORT_COLUMNS)


def ensure_bnsf_notice_worksheet(spreadsheet):
    return ensure_worksheet(spreadsheet, BNSF_NOTICE_SHEET_TITLE, BNSF_NOTICE_COLUMNS, rows=100)


def save_daily_report_record(record, spreadsheet):
    worksheet, _created = ensure_bnsf_daily_report_worksheet(spreadsheet)
    header = [_cell(col) for col in worksheet.row_values(1)]
    if not header:
        raise RuntimeError("BNSF Daily Reports worksheet has no header")
    worksheet.append_row([str(record.get(col, "")) for col in header], value_input_option="RAW")
    return "Google Sheets (BNSF Daily Reports)"


def save_notice_record(notice, spreadsheet, source="", when=None):
    worksheet, _created = ensure_bnsf_notice_worksheet(spreadsheet)
    header = [_cell(col) for col in worksheet.row_values(1)]
    if not header:
        raise RuntimeError("BNSF 10-Day Notices worksheet has no header")
    when = _as_pacific(when)
    record = {
        "Entry ID": new_entry_id("TN", when),
        "Timestamp": format_timestamp(when),
        "Title": _cell(notice.get("title") or notice.get("program_name")),
        "Notice ID": _cell(notice.get("id")),
        "Roadmaster": _cell(notice.get("roadmaster")),
        "Roadmaster ID": _cell(notice.get("roadmaster_id")),
        "Division": _cell(notice.get("division")),
        "Program Name": _cell(notice.get("program_name")),
        "Product mix": _cell(notice.get("product_mix")),
        "Segments JSON": json.dumps(notice.get("segments") or [], separators=(",", ":")),
        "Source": _cell(source),
    }
    worksheet.append_row([str(record.get(col, "")) for col in header], value_input_option="RAW")
    return record


def load_saved_notices(spreadsheet):
    if spreadsheet is None:
        return []
    worksheet = _worksheet_or_none(spreadsheet, BNSF_NOTICE_SHEET_TITLE)
    if worksheet is None:
        return []
    values = worksheet.get_all_values() if hasattr(worksheet, "get_all_values") else []
    if not values:
        return []
    header = [_cell(col) for col in values[0]]
    notices = []
    for row in values[1:]:
        record = {header[i]: _cell(row[i]) if i < len(row) else "" for i in range(len(header))}
        if not any(record.values()):
            continue
        segments = []
        raw = record.get("Segments JSON") or ""
        if raw:
            try:
                segments = json.loads(raw)
            except json.JSONDecodeError:
                segments = []
        notices.append({
            "id": record.get("Notice ID") or record.get("Entry ID"),
            "title": record.get("Title") or record.get("Program Name"),
            "roadmaster": record.get("Roadmaster"),
            "roadmaster_id": record.get("Roadmaster ID"),
            "division": record.get("Division"),
            "program_name": record.get("Program Name"),
            "product_mix": record.get("Product mix"),
            "segments": segments,
        })
    return notices


def all_notices(spreadsheet=None, extra=None):
    notices = list(bnsf_notice.load_bundled_notices())
    seen = { _cell(n.get("id")) for n in notices }
    for notice in load_saved_notices(spreadsheet):
        ident = _cell(notice.get("id"))
        if ident and ident in seen:
            continue
        notices.append(notice)
        seen.add(ident)
    for notice in extra or []:
        ident = _cell(notice.get("id"))
        if ident and ident in seen:
            continue
        notices.append(notice)
        seen.add(ident)
    return notices


def notice_option_label(notice):
    title = _cell(notice.get("title") or notice.get("program_name") or notice.get("id") or "Notice")
    rdm = _cell(notice.get("roadmaster"))
    if rdm and rdm.lower() not in title.lower():
        return "%s (%s)" % (title, rdm)
    return title


NOT_SPRAYED_STATUS = "Pending review"
SPEECH_SECRET_SECTION = "bnsf_speech"
_SPOKEN_ONES = {
    "zero": 0, "oh": 0, "o": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_SPOKEN_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_WORDS = set(_SPOKEN_ONES) | set(_SPOKEN_TENS) | {"hundred", "point", "dot", "and"}


def _speech_words(text):
    cleaned = re.sub(r"[^A-Za-z0-9.\s]", " ", _cell(text).lower().replace("-", " "))
    return [word for word in cleaned.split() if word]


def _is_number_token(token):
    if token in _NUMBER_WORDS:
        return True
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", token))


def _parse_small_number(tokens):
    if not tokens:
        return None
    if len(tokens) == 1:
        token = tokens[0]
        if re.fullmatch(r"\d+", token):
            return int(token)
        if token in _SPOKEN_TENS:
            return _SPOKEN_TENS[token]
        if token in _SPOKEN_ONES:
            return _SPOKEN_ONES[token]
        return None
    if len(tokens) == 2 and tokens[0] in _SPOKEN_TENS and tokens[1] in _SPOKEN_ONES and _SPOKEN_ONES[tokens[1]] < 10:
        return _SPOKEN_TENS[tokens[0]] + _SPOKEN_ONES[tokens[1]]
    return None


def _parse_whole_number(tokens):
    tokens = [token for token in tokens if token != "and"]
    if not tokens:
        return None
    if any(re.fullmatch(r"\d+\.\d+", token) for token in tokens):
        return None
    if "hundred" in tokens:
        index = tokens.index("hundred")
        left = _parse_small_number(tokens[:index]) if tokens[:index] else 1
        right = _parse_small_number(tokens[index + 1:]) if tokens[index + 1:] else 0
        if left is None or right is None:
            return None
        return left * 100 + right
    parts = []
    index = 0
    while index < len(tokens):
        pair = tokens[index:index + 2]
        combined = _parse_small_number(pair) if len(pair) == 2 and pair[0] in _SPOKEN_TENS else None
        if combined is not None and pair[1] in _SPOKEN_ONES and _SPOKEN_ONES[pair[1]] < 10:
            parts.append(str(combined))
            index += 2
            continue
        token = tokens[index]
        if re.fullmatch(r"\d+", token):
            parts.append(token)
        elif token in _SPOKEN_TENS:
            parts.append(str(_SPOKEN_TENS[token]))
        elif token in _SPOKEN_ONES:
            parts.append(str(_SPOKEN_ONES[token]))
        else:
            return None
        index += 1
    if not parts:
        return None
    return int("".join(parts))


def _parse_fraction(tokens):
    digits = []
    for token in tokens:
        if token in {"point", "dot", "and"}:
            continue
        if re.fullmatch(r"\d+", token):
            digits.append(token)
        elif token in _SPOKEN_ONES and _SPOKEN_ONES[token] < 10:
            digits.append(str(_SPOKEN_ONES[token]))
        else:
            return None
    return "".join(digits)


def _milepost_from_tokens(tokens):
    if len(tokens) == 1 and re.fullmatch(r"\d+\.\d+", tokens[0]):
        return float(tokens[0])
    if "point" in tokens or "dot" in tokens:
        splitter = "point" if "point" in tokens else "dot"
        index = tokens.index(splitter)
        whole = _parse_whole_number(tokens[:index])
        fraction = _parse_fraction(tokens[index + 1:])
        if whole is None or not fraction:
            return None
        return float("%s.%s" % (whole, fraction))
    whole = _parse_whole_number(tokens)
    if whole is None:
        return None
    return float(whole)


def _consume_number_tokens(words, start):
    index = start
    while index < len(words) and _is_number_token(words[index]):
        index += 1
    return words[start:index], index


def parse_not_sprayed_speech(text):
    """Pull a spoken or typed milepost out of a not-sprayed note.

    Returns mp (float or None) and the remaining words as the reason.
    The raw transcript is not changed here.
    """
    words = _speech_words(text)
    span = None
    for index, word in enumerate(words):
        start = None
        if word in {"mp", "milepost"}:
            start = index + 1
        elif word == "mile" and index + 1 < len(words) and words[index + 1] == "post":
            start = index + 2
        if start is None:
            continue
        phrase, end = _consume_number_tokens(words, start)
        if phrase and _milepost_from_tokens(phrase) is not None:
            span = (index, end)
            break
    if span is None:
        for index, word in enumerate(words):
            if not (_is_number_token(word) and (re.match(r"\d", word) or word in _SPOKEN_ONES or word in _SPOKEN_TENS)):
                continue
            phrase, end = _consume_number_tokens(words, index)
            if "point" not in phrase and "dot" not in phrase and not any(re.fullmatch(r"\d+\.\d+", token) for token in phrase):
                continue
            if _milepost_from_tokens(phrase) is not None:
                span = (index, end)
                break
    if span is None:
        return {"mp": None, "reason": _cell(text)}
    phrase = words[span[0]:span[1]]
    while phrase and phrase[0] in {"mp", "milepost", "mile", "post"}:
        phrase = phrase[1:]
    value = _milepost_from_tokens(phrase)
    reason_words = words[:span[0]] + words[span[1]:]
    reason = " ".join(reason_words).strip(" .")
    if value is None:
        return {"mp": None, "reason": _cell(text)}
    return {"mp": round(float(value), 1), "reason": reason}


def speech_settings(secrets=None):
    """Optional Whisper settings. A missing key means keyboard dictation.

    The returned dict includes whether transcription is turned on. The API key
    stays only for the request helper and is not meant to be shown.
    """
    section = {}
    if secrets is not None:
        try:
            raw = secrets.get(SPEECH_SECRET_SECTION) if hasattr(secrets, "get") else None
        except Exception:
            raw = None
        if raw is None:
            try:
                raw = secrets[SPEECH_SECRET_SECTION]
            except Exception:
                raw = None
        if isinstance(raw, dict):
            section = raw
    enabled_flag = str(section.get("enabled", "")).strip().lower() in {"1", "true", "yes", "on"}
    api_key = _cell(section.get("api_key"))
    return {
        "enabled": bool(enabled_flag and api_key),
        "api_key": api_key,
        "url": _cell(section.get("url")) or "https://api.openai.com/v1/audio/transcriptions",
        "model": _cell(section.get("model")) or "whisper-1",
    }


def transcribe_not_sprayed_clip(audio_bytes, secrets=None, http_post=None):
    """Transcribe a clip when [bnsf_speech] is enabled. Otherwise return None.

    http_post(audio_bytes, settings) is injectable for tests. Errors do not
    include the API key.
    """
    settings = speech_settings(secrets)
    if not settings["enabled"]:
        return None
    if not audio_bytes:
        return None
    poster = http_post
    if poster is None:
        poster = _post_whisper_clip
    try:
        text = poster(audio_bytes, settings)
    except Exception:
        raise ValueError("Speech service could not transcribe the clip.")
    return _cell(text)


def _post_whisper_clip(audio_bytes, settings):
    import uuid
    from urllib.request import Request, urlopen

    boundary = "----cvh" + uuid.uuid4().hex
    model = settings["model"]
    body = b"".join([
        ("--" + boundary + "\r\n").encode(),
        b'Content-Disposition: form-data; name="model"\r\n\r\n',
        model.encode(),
        b"\r\n",
        ("--" + boundary + "\r\n").encode(),
        b'Content-Disposition: form-data; name="file"; filename="not-sprayed.wav"\r\n',
        b"Content-Type: audio/wav\r\n\r\n",
        audio_bytes,
        b"\r\n",
        ("--" + boundary + "--\r\n").encode(),
    ])
    request = Request(
        settings["url"],
        data=body,
        headers={
            "Authorization": "Bearer " + settings["api_key"],
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _cell(payload.get("text"))


NOT_SPRAYED_FIELDS = (
    "id", "Date", "Date display", "Time", "Timestamp", "MP", "MP source",
    "GPS MP", "Subdivision", "Division", "Reason", "Aircraft", "Transcript", "Status",
)


def normalize_not_sprayed(rows):
    cleaned = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {field: _cell(row.get(field)) for field in NOT_SPRAYED_FIELDS}
        if not item["Status"]:
            item["Status"] = NOT_SPRAYED_STATUS
        if not item["Aircraft"]:
            item["Aircraft"] = DEFAULT_AIRCRAFT_ID
        if any(item[field] for field in ("Time", "MP", "Reason", "Transcript")):
            cleaned.append(item)
    return cleaned


def capture_not_sprayed_fix(lat=None, lon=None, now=None, aircraft="", points=None):
    """Time plus the nearest tenth-mile BNSF post. Speech can replace the MP later."""
    now = _as_pacific(now)
    mp = ""
    subdivision = ""
    division = ""
    if lat is not None and lon is not None:
        fix = bw.locate_milepost(float(lat), float(lon), points=points)
        mp = bw.format_milepost(fix.milepost)
        subdivision = fix.subdivision
        division = fix.division
    return {
        "id": new_entry_id("NS", now),
        "Date": format_date(now),
        "Date display": format_date_mdy(now),
        "Time": format_clock(now),
        "Timestamp": format_timestamp(now),
        "MP": mp,
        "MP source": "GPS" if mp else "",
        "GPS MP": mp,
        "Subdivision": subdivision,
        "Division": division,
        "Reason": "",
        "Aircraft": aircraft_id(aircraft),
        "Transcript": "",
        "Status": NOT_SPRAYED_STATUS,
    }


def apply_spoken_milepost(row, transcript):
    """Use a spoken milepost when the pilot says one. Keep the GPS post."""
    parsed = parse_not_sprayed_speech(transcript)
    updated = dict(row or {})
    updated["Transcript"] = _cell(transcript)
    if parsed["mp"] is not None:
        updated["MP"] = bw.format_milepost(parsed["mp"])
        updated["MP source"] = "Spoken"
        updated["Reason"] = parsed["reason"]
    else:
        updated["Reason"] = parsed["reason"]
    if not updated.get("Status"):
        updated["Status"] = NOT_SPRAYED_STATUS
    if not updated.get("Aircraft"):
        updated["Aircraft"] = DEFAULT_AIRCRAFT_ID
    return normalize_not_sprayed([updated])[0]


def spray_rows_with_not_sprayed(spray_rows, not_sprayed):
    """Copy the spray grid and put not-sprayed notes in the first empty rows."""
    rows = [dict(row) for row in normalize_spray_rows(spray_rows)]
    cursor = 0
    for item in normalize_not_sprayed(not_sprayed):
        while cursor < len(rows) and any(_cell(rows[cursor].get(field)) for field in SPRAY_FIELDS):
            cursor += 1
        if cursor >= len(rows):
            break
        source = item["MP source"] or "GPS"
        rows[cursor]["Time"] = item["Time"]
        rows[cursor]["MP ST"] = item["MP"]
        rows[cursor]["Notes"] = "Not sprayed (%s): %s" % (source, item["Reason"])
        cursor += 1
    return rows


def render_ops_clocks(pilot, now=None):
    """BNSF Start/Stop buttons and editable CVH times, shown on the BNSF Ops page."""
    import streamlit as st

    now = _as_pacific(now)
    clocks = get_ops_clocks(st.session_state, pilot, now=now)
    st.markdown("**BNSF time**")
    st.caption("Start and Stop are when you tap the buttons (you can still edit the times). CVH time is longer — it includes pre- and post-flight inspections.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("BNSF Start", key="bnsf_clock_start", use_container_width=True):
            started = start_bnsf_spray(st.session_state, pilot, now=now)
            st.session_state.bnsf_clock_start_text = started["bnsf_start"]
            st.session_state.bnsf_clock_end_text = ""
            st.rerun()
    with c2:
        if st.button("BNSF Stop", key="bnsf_clock_stop", use_container_width=True):
            stopped = stop_bnsf_spray(st.session_state, pilot, now=now)
            st.session_state.bnsf_clock_end_text = stopped["bnsf_end"]
            st.rerun()
    clocks = get_ops_clocks(st.session_state, pilot, now=now)
    with c3:
        if "bnsf_clock_start_text" not in st.session_state:
            st.session_state.bnsf_clock_start_text = clocks["bnsf_start"]
        start_val = st.text_input("BNSF Time Start", key="bnsf_clock_start_text")
    with c4:
        if "bnsf_clock_end_text" not in st.session_state:
            st.session_state.bnsf_clock_end_text = clocks["bnsf_end"]
        end_val = st.text_input("BNSF Time End", key="bnsf_clock_end_text")
    d1, d2 = st.columns(2)
    with d1:
        if "bnsf_clock_cvh_start" not in st.session_state:
            st.session_state.bnsf_clock_cvh_start = clocks["cvh_start"]
        cvh_start = st.text_input("CVH Time Start", key="bnsf_clock_cvh_start")
    with d2:
        if "bnsf_clock_cvh_end" not in st.session_state:
            st.session_state.bnsf_clock_cvh_end = clocks["cvh_end"]
        cvh_end = st.text_input("CVH Time End", key="bnsf_clock_cvh_end")
    set_ops_clocks(st.session_state, pilot, {
        "bnsf_start": start_val,
        "bnsf_end": end_val,
        "cvh_start": cvh_start,
        "cvh_end": cvh_end,
    }, now=now)


def _not_sprayed_rows():
    import streamlit as st

    return normalize_not_sprayed(st.session_state.get("bnsf_not_sprayed_rows"))


def _store_not_sprayed_rows(rows):
    import streamlit as st

    cleaned = normalize_not_sprayed(rows)
    st.session_state.bnsf_not_sprayed_rows = cleaned
    report = st.session_state.get("bnsf_report_data")
    if isinstance(report, dict):
        report["not_sprayed"] = cleaned
        st.session_state.bnsf_report_data = report
    return cleaned


def _speech_secrets():
    try:
        import streamlit as st
        return st.secrets
    except Exception:
        return None


def _render_not_sprayed_capture(pilot, aircraft, now, location_getter=None):
    """In-flight Not sprayed and Mark MP controls. Capture happens on the tap."""
    import streamlit as st

    st.markdown(
        """
        <style>
        div[class*="st-key-bnsf_not_sprayed_voice"] button {
            min-height: 4.6rem;
            font-size: 1.45rem;
            font-weight: 700;
        }
        div[class*="st-key-bnsf_not_sprayed_mark"] button {
            min-height: 3.4rem;
            font-size: 1.2rem;
            font-weight: 650;
        }
        div[class*="st-key-bnsf_not_sprayed_voice"] button:disabled,
        div[class*="st-key-bnsf_not_sprayed_mark"] button:disabled {
            background-color: #d5d8de !important;
            color: #5c6570 !important;
            border-color: #c5cad3 !important;
            opacity: 1 !important;
            cursor: not-allowed !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    clocks = get_ops_clocks(st.session_state, pilot, now=now)
    actions = not_sprayed_actions(spraying_in_progress(clocks))
    st.markdown("**Not sprayed**")
    if actions["capture"]:
        st.caption(
            "Tap once in flight. The phone records the time and the nearest BNSF milepost. "
            "With the audio panel in TEL, speak the reason. If you say a milepost, that replaces the GPS post."
        )
    else:
        st.caption(actions["note"])
    if st.button(
        "Not sprayed (voice)",
        key="bnsf_not_sprayed_voice",
        type="primary",
        use_container_width=True,
        disabled=not actions["capture"],
    ):
        st.session_state.bnsf_ns_mode = "voice"
        st.session_state.bnsf_ns_gps_waited = False
        st.session_state.pop("bnsf_ns_draft", None)
        st.session_state.pop("bnsf_ns_text", None)
        st.session_state.pop("bnsf_ns_audio_id", None)
        st.session_state.pop("bnsf_ns_audio", None)
        st.rerun()
    if st.button("Mark MP", key="bnsf_not_sprayed_mark", use_container_width=True, disabled=not actions["capture"]):
        st.session_state.bnsf_ns_mode = "mark"
        st.session_state.bnsf_ns_gps_waited = False
        st.session_state.pop("bnsf_ns_draft", None)
        st.rerun()

    mode = st.session_state.get("bnsf_ns_mode")
    if not actions["capture"] and not st.session_state.get("bnsf_ns_draft"):
        st.session_state.pop("bnsf_ns_mode", None)
        mode = None
    elif not actions["capture"]:
        mode = None
    if mode in {"voice", "mark"} and not st.session_state.get("bnsf_ns_draft"):
        coords = None
        st.caption("Getting your location… Allow location access if the phone asks.")
        try:
            coords = bw.request_browser_location(getter=location_getter)
        except Exception as exc:
            st.warning("Could not read GPS (%s). Say the milepost, or edit it after landing." % exc)
            coords = None
        if coords is None and location_getter is None and not st.session_state.get("bnsf_ns_gps_waited"):
            st.session_state.bnsf_ns_gps_waited = True
            st.stop()
        lat, lon = (coords or (None, None))
        draft = capture_not_sprayed_fix(lat, lon, now=now, aircraft=aircraft or DEFAULT_AIRCRAFT_ID)
        st.session_state.bnsf_ns_draft = draft
        if mode == "mark":
            _store_not_sprayed_rows(_not_sprayed_rows() + [draft])
            st.session_state.pop("bnsf_ns_mode", None)
            st.session_state.pop("bnsf_ns_draft", None)
            where = ("MP " + draft["MP"]) if draft["MP"] else "no GPS milepost"
            st.session_state.bnsf_ns_flash = "Marked %s at %s. Add the reason after landing." % (where, draft["Time"])
            st.rerun()

    if st.session_state.get("bnsf_ns_flash"):
        st.success(st.session_state.bnsf_ns_flash)
        st.session_state.pop("bnsf_ns_flash", None)

    draft = st.session_state.get("bnsf_ns_draft")
    if st.session_state.get("bnsf_ns_mode") == "voice" and isinstance(draft, dict):
        where = ("MP " + draft["MP"] + " (GPS)") if draft.get("MP") else "GPS milepost not available"
        st.info("Captured %s, %s, %s. %s." % (draft.get("Date display") or draft.get("Date"), draft.get("Time"), draft.get("Aircraft") or DEFAULT_AIRCRAFT_ID, where))
        settings = speech_settings(_speech_secrets())
        audio = None
        if hasattr(st, "audio_input"):
            audio = st.audio_input("Hold to record the reason", key="bnsf_ns_audio")
        if settings["enabled"]:
            st.caption("A clip is transcribed on this phone. The API key stays in secrets and is not shown.")
        else:
            st.caption(
                "Automatic transcription is off. Time and milepost are already captured. "
                "Tap the microphone on the iPhone keyboard in the box below, or type the reason after landing."
            )
        if audio is not None and settings["enabled"]:
            raw = audio.getvalue() if hasattr(audio, "getvalue") else bytes(audio)
            clip_id = "%s:%s" % (len(raw), raw[:24].hex() if raw else "")
            if raw and clip_id != st.session_state.get("bnsf_ns_audio_id"):
                try:
                    heard = transcribe_not_sprayed_clip(raw, secrets=_speech_secrets())
                except ValueError as exc:
                    st.warning(str(exc))
                    heard = ""
                st.session_state.bnsf_ns_audio_id = clip_id
                if heard:
                    st.session_state.bnsf_ns_text = heard
                    st.rerun()
        if "bnsf_ns_text" not in st.session_state:
            st.session_state.bnsf_ns_text = ""
        transcript = st.text_area(
            "Reason (dictate or type)",
            key="bnsf_ns_text",
            height=120,
            placeholder="Example: milepost one twelve point four, trees over the track",
        )
        if st.button("Save voice note", key="bnsf_ns_save", type="primary", use_container_width=True):
            row = apply_spoken_milepost(draft, transcript)
            _store_not_sprayed_rows(_not_sprayed_rows() + [row])
            st.session_state.pop("bnsf_ns_mode", None)
            st.session_state.pop("bnsf_ns_draft", None)
            st.session_state.pop("bnsf_ns_text", None)
            st.session_state.pop("bnsf_ns_audio_id", None)
            label = ("MP " + row["MP"] + " (" + row["MP source"] + ")") if row["MP"] else "no milepost"
            st.session_state.bnsf_ns_flash = "Saved not-sprayed note at %s, %s. Pending review." % (row["Time"], label)
            st.rerun()
        if st.button("Cancel voice note", key="bnsf_ns_cancel"):
            st.session_state.pop("bnsf_ns_mode", None)
            st.session_state.pop("bnsf_ns_draft", None)
            st.session_state.pop("bnsf_ns_text", None)
            st.rerun()

    rows = _not_sprayed_rows()
    if rows:
        st.markdown("**Not sprayed — pending review**")
        kept = []
        for index, row in enumerate(rows):
            source = row["MP source"] or "GPS"
            title = "%s %s · MP %s (%s) · %s · %s" % (
                row["Date display"] or row["Date"],
                row["Time"],
                row["MP"] or "—",
                source,
                row["Aircraft"] or DEFAULT_AIRCRAFT_ID,
                row["Status"] or NOT_SPRAYED_STATUS,
            )
            with st.expander(title, expanded=False):
                row_key = row["id"] or str(index)
                mp_value = st.text_input("Milepost", value=row["MP"], key="bnsf_ns_edit_mp_%s" % row_key)
                reason_value = st.text_area("Reason", value=row["Reason"], key="bnsf_ns_edit_reason_%s" % row_key)
                if row["Transcript"]:
                    st.caption("Transcript: " + row["Transcript"])
                c1, c2, c3 = st.columns(3)
                updated = dict(row)
                updated["MP"] = _cell(mp_value)
                updated["Reason"] = _cell(reason_value)
                with c1:
                    if st.button("Save edit", key="bnsf_ns_edit_save_%s" % row_key):
                        updated["Status"] = NOT_SPRAYED_STATUS
                        kept.append(updated)
                        _store_not_sprayed_rows(kept + rows[index + 1:])
                        st.rerun()
                with c2:
                    if st.button("Mark reviewed", key="bnsf_ns_reviewed_%s" % row_key):
                        updated["Status"] = "Reviewed"
                        kept.append(updated)
                        _store_not_sprayed_rows(kept + rows[index + 1:])
                        st.rerun()
                with c3:
                    if st.button("Delete", key="bnsf_ns_delete_%s" % row_key):
                        _store_not_sprayed_rows(kept + rows[index + 1:])
                        st.rerun()
                kept.append(updated)


def render_daily_field_report(pilot="", aircraft="", weather_records=None, spreadsheet_fn=None, now=None, location_getter=None):
    """Daily Field Report section under BNSF Ops."""
    import streamlit as st

    now = _as_pacific(now)
    st.markdown("---")
    st.subheader("Daily Field Report")
    st.caption(
        "Builds today's report from weather logs, BNSF Start/Stop, and a 10-day notice "
        "(line segment and product mix). Check every field before you save or download."
    )
    _render_not_sprayed_capture(pilot, aircraft, now, location_getter=location_getter)

    spreadsheet = None
    if spreadsheet_fn is not None:
        try:
            spreadsheet = spreadsheet_fn()
        except Exception as exc:
            st.warning("Could not open the spreadsheet: %s" % exc)

    uploaded_notices = list(st.session_state.get("bnsf_uploaded_notices") or [])
    notices = all_notices(spreadsheet, extra=uploaded_notices)
    notice_labels = ["(none — type line segment and mix by hand)"] + [notice_option_label(n) for n in notices]
    selected = st.selectbox("10-day notice", notice_labels, key="bnsf_report_notice_choice")
    notice = None
    if selected and not selected.startswith("(none"):
        notice = notices[notice_labels.index(selected) - 1]

    uploaded = st.file_uploader(
        "Or upload a 10-day notice (email text, PDF, Word, or JSON)",
        type=["txt", "pdf", "docx", "json"],
        key="bnsf_report_notice_upload",
    )
    if uploaded is not None and st.session_state.get("bnsf_report_notice_upload_name") != uploaded.name:
        data = uploaded.getvalue()
        parsed = bnsf_notice.notice_from_upload(uploaded.name, data)
        if parsed and (parsed.get("segments") or parsed.get("product_mix") or parsed.get("roadmaster")):
            uploaded_notices = [n for n in uploaded_notices if n.get("id") != parsed.get("id")] + [parsed]
            st.session_state.bnsf_uploaded_notices = uploaded_notices
            st.session_state.bnsf_report_notice_upload_name = uploaded.name
            st.session_state.bnsf_report_notice_choice = notice_option_label(parsed)
            if spreadsheet is not None:
                try:
                    save_notice_record(parsed, spreadsheet, source=uploaded.name, when=now)
                except Exception as exc:
                    st.warning("The notice was parsed but could not be saved to the sheet: %s" % exc)
            st.success("Loaded notice: " + notice_option_label(parsed))
            st.rerun()
        else:
            st.warning("Could not find line segments or a product mix in that file. You can still type them by hand.")

    if notice:
        st.caption(
            "Roadmaster %s. Product mix and line segments come from this notice. "
            "You can still edit them on the report."
            % (_cell(notice.get("roadmaster")) or "on file")
        )

    if st.button("Open today's Daily Field Report", key="bnsf_report_open", type="primary", use_container_width=True):
        if not _cell(pilot):
            st.error("Select a pilot first.")
        else:
            clocks = get_ops_clocks(st.session_state, pilot, now=now)
            gathered = gather_daily_report(
                pilot,
                aircraft=aircraft or DEFAULT_AIRCRAFT_ID,
                weather_records=weather_records,
                clocks=clocks,
                notice=notice,
                now=now,
                not_sprayed=_not_sprayed_rows(),
            )
            st.session_state.bnsf_report_data = gathered
            st.session_state.bnsf_report_original = json.loads(json.dumps(gathered, default=str))
            st.session_state.pop("bnsf_report_saved", None)
            st.session_state.pop("bnsf_report_pdf", None)
            st.session_state.pop("bnsf_report_docx", None)
            st.rerun()

    if st.session_state.get("bnsf_report_saved"):
        st.success(st.session_state.bnsf_report_saved)

    report = st.session_state.get("bnsf_report_data")
    if not report:
        return
    report["not_sprayed"] = _not_sprayed_rows()

    st.markdown("**Check or edit this report**")
    c1, c2, c3 = st.columns(3)
    with c1:
        report["Pilot"] = st.text_input("Pilot", value=report.get("Pilot", ""), key="bnsf_rep_pilot")
        report["Aircraft"] = st.text_input("Aircraft ID", value=report.get("Aircraft") or DEFAULT_AIRCRAFT_ID, key="bnsf_rep_ac")
        report["County"] = st.text_input("County", value=report.get("County", ""), key="bnsf_rep_county")
    with c2:
        report["Hobbs Start"] = st.text_input("Hobbs Start", value=report.get("Hobbs Start", ""), key="bnsf_rep_hobbs_s")
        report["Hobbs End"] = st.text_input("Hobbs End", value=report.get("Hobbs End", ""), key="bnsf_rep_hobbs_e")
        report["Flight Time"] = st.text_input(
            "Flight Time (auto from Hobbs)",
            value=flight_time_hours(report["Hobbs Start"], report["Hobbs End"]) or report.get("Flight Time", ""),
            key="bnsf_rep_flight",
        )
    with c3:
        loads_default = report.get("Loads") or ""
        loads = st.text_input("Loads (15 acres each)", value=loads_default, key="bnsf_rep_loads")
        report["Loads"] = loads
        auto_acres = acres_from_loads(loads)
        if _cell(loads) != _cell(st.session_state.get("bnsf_rep_loads_prev", loads_default)):
            acres_value = auto_acres
        else:
            acres_value = report.get("Acres Sprayed") or auto_acres
        st.session_state.bnsf_rep_loads_prev = loads
        report["Acres Sprayed"] = st.text_input("Acres Sprayed", value=acres_value, key="bnsf_rep_acres")
        video_options = ["Yes", "No"]
        video = report.get("Video ON") or "Yes"
        report["Video ON"] = st.selectbox("Video ON?", video_options, index=0 if video.lower() != "no" else 1, key="bnsf_rep_video")

    d1, d2 = st.columns(2)
    with d1:
        report["Division"] = st.text_input("Division", value=report.get("Division", ""), key="bnsf_rep_div")
        report["BNSF Subdivision"] = st.text_input("BNSF Subdivision", value=report.get("BNSF Subdivision", ""), key="bnsf_rep_sub")
        if notice and notice.get("segments"):
            labels = [bnsf_notice.segment_label(s) for s in notice["segments"]]
            current = report.get("Line Segment") or ""
            if current and current not in labels:
                labels = [current] + labels
            choice = st.selectbox("Line Segment", [""] + labels, index=([""] + labels).index(current) if current in labels else 0, key="bnsf_rep_seg_pick")
            custom = st.text_input("Line Segment (edit)", value=choice or current, key="bnsf_rep_seg")
            report["Line Segment"] = custom or choice
        else:
            report["Line Segment"] = st.text_input("Line Segment", value=report.get("Line Segment", ""), key="bnsf_rep_seg")
            st.caption("Upload or pick a 10-day notice to choose from that roadmaster's line segments.")
    with d2:
        report["MP Start"] = st.text_input("MP Start", value=report.get("MP Start", ""), key="bnsf_rep_mp_s")
        report["MP End"] = st.text_input("MP End", value=report.get("MP End", ""), key="bnsf_rep_mp_e")
        report["BNSF Time Start"] = st.text_input("BNSF Time Start", value=report.get("BNSF Time Start", ""), key="bnsf_rep_bnsf_s")
        report["BNSF Time End"] = st.text_input("BNSF Time End", value=report.get("BNSF Time End", ""), key="bnsf_rep_bnsf_e")
        report["CVH Time Start"] = st.text_input("CVH Time Start", value=report.get("CVH Time Start", ""), key="bnsf_rep_cvh_s")
        report["CVH Time End"] = st.text_input("CVH Time End", value=report.get("CVH Time End", ""), key="bnsf_rep_cvh_e")

    report["Product mix"] = st.text_area("Product mix", value=report.get("Product mix", ""), key="bnsf_rep_mix")
    if not notice:
        st.caption("Default mix is from the form until a 10-day notice is loaded. Mix is the same per roadmaster.")

    st.markdown("**Weather every 2 hours**")
    slots = report.get("weather_slots") or weather_slots_from_logs([])
    slot_records = []
    for index in range(WEATHER_SLOTS):
        slot = slots[index] if index < len(slots) else {k: "" for k in ("Time", "Sky", "Wind Speed", "Wind Direction", "Temperature", "Precipitation", "MP Location")}
        slot_records.append({
            "Slot": str(index + 1),
            "Time": slot.get("Time", ""),
            "Sky Condition": slot.get("Sky", ""),
            "Wind Speed": slot.get("Wind Speed", ""),
            "Wind Direction": slot.get("Wind Direction", ""),
            "Temperature": slot.get("Temperature", ""),
            "Precipitation": slot.get("Precipitation", ""),
            "MP Location": slot.get("MP Location", ""),
        })
    edited_weather = st.data_editor(
        slot_records,
        num_rows="fixed",
        use_container_width=True,
        key="bnsf_rep_weather_editor",
        hide_index=True,
    )
    new_slots = []
    for index, row in enumerate(edited_weather):
        base = slots[index] if index < len(slots) else {}
        new_slots.append({
            **base,
            "Time": _cell(row.get("Time")),
            "Sky": _cell(row.get("Sky Condition")),
            "Wind Speed": _cell(row.get("Wind Speed")),
            "Wind Direction": _cell(row.get("Wind Direction")),
            "Temperature": _cell(row.get("Temperature")),
            "Precipitation": _cell(row.get("Precipitation")),
            "MP Location": _cell(row.get("MP Location")),
        })
    report["weather_slots"] = new_slots

    st.markdown("**Spray log** (typed — time, two milepost ranges, and notes)")
    spray_rows = normalize_spray_rows(report.get("spray_rows"))
    spray_view = [{"#": i + 1, **row} for i, row in enumerate(spray_rows)]
    edited_spray = st.data_editor(
        spray_view,
        num_rows="fixed",
        use_container_width=True,
        key="bnsf_rep_spray_editor",
        hide_index=True,
        column_config={"#": st.column_config.NumberColumn(disabled=True)},
    )
    report["spray_rows"] = normalize_spray_rows([{k: r.get(k, "") for k in SPRAY_FIELDS} for r in edited_spray])
    report["Date display"] = report.get("Date display") or format_date_mdy(now)
    st.session_state.bnsf_report_data = report

    def _generate():
        docx_bytes = fill_daily_report_docx(report)
        pdf_bytes = build_daily_report_pdf(report)
        st.session_state.bnsf_report_docx = docx_bytes
        st.session_state.bnsf_report_pdf = pdf_bytes
        return docx_bytes, pdf_bytes

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Save report", key="bnsf_rep_save", type="primary", use_container_width=True):
            if not _cell(report.get("Pilot")):
                st.error("A pilot name is required to save.")
            elif spreadsheet_fn is None:
                st.error("Google Sheets is not configured, so the report was not saved.")
            else:
                try:
                    record = report_to_record(report, original=st.session_state.get("bnsf_report_original"), when=now)
                    save_daily_report_record(record, spreadsheet_fn())
                    _generate()
                    st.session_state.bnsf_report_saved = "Saved Daily Field Report %s for %s." % (
                        record["Entry ID"], report.get("Date display") or record["Date"]
                    )
                    st.rerun()
                except Exception as exc:
                    st.error("Could not save the report: %s" % exc)
    with b2:
        if st.button("Build PDF and Word files", key="bnsf_rep_build", use_container_width=True):
            try:
                _generate()
                st.rerun()
            except Exception as exc:
                st.error("Could not build the files: %s" % exc)
    with b3:
        if st.button("Close report", key="bnsf_rep_close", use_container_width=True):
            for key in ("bnsf_report_data", "bnsf_report_original", "bnsf_report_pdf", "bnsf_report_docx"):
                st.session_state.pop(key, None)
            st.rerun()

    day = (report.get("Date") or format_date(now)).replace("-", "")
    ac = aircraft_id(report.get("Aircraft"))
    base = "CVH_Daily_Field_Report_%s_%s" % (day, ac)
    if st.session_state.get("bnsf_report_pdf"):
        st.download_button(
            "Download PDF",
            data=st.session_state.bnsf_report_pdf,
            file_name=base + ".pdf",
            mime="application/pdf",
            key="bnsf_rep_dl_pdf",
            use_container_width=True,
        )
    if st.session_state.get("bnsf_report_docx"):
        st.download_button(
            "Download Word form",
            data=st.session_state.bnsf_report_docx,
            file_name=base + ".docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="bnsf_rep_dl_docx",
            use_container_width=True,
        )
        st.caption(
            "The PDF is built in the app so it works on Streamlit Cloud (LibreOffice is not available there). "
            "The Word download is the official form with the eagle logo, filled in with this report."
        )
