"""Equipment list, squawk save/resolve, and header navigation. No live Sheets writes."""
import ast
import hashlib
import json
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from test_aircraft_weights import SOURCE, TREE, offline_app

APP = Path(__file__).resolve().parents[1] / "app.py"


def _exec_equipment_helpers():
    names = {
        "PILOTS", "ACCOUNTABLE_EXEC", "DIRECTOR_MAINTENANCE", "APPROVERS",
        "EQUIPMENT_SHEET_TITLE", "SQUAWKS_SHEET_TITLE", "SAFETY_MEETINGS_SHEET_TITLE", "SAFETY_MEETING_ITEMS", "SAFETY_MEETING_ATTENDEES", "SAFETY_MEETING_VIEW", "SAFETY_MEETING_RECORD", "AIRCRAFT_MAINT_SHEET_TITLE", "AIRCRAFT_MAINT_COLUMNS", "AIRCRAFT_MAINT_PROFILES",
        "GREASE_CHECKPOINT_OFFSETS", "GREASE_AMBER_HOURS", "N480ML_MAINT_SHEET_TITLE",
        "EQUIPMENT_INFO_COLUMNS", "EQUIPMENT_COLUMNS", "EQUIPMENT_EDIT_COLUMNS", "SQUAWK_COLUMNS", "EQUIPMENT_TYPES",
        "SQUAWK_CATEGORIES", "SQUAWK_SEVERITIES", "SEVERITY_GROUNDED", "STATUS_OPEN",
        "STATUS_RESOLVED", "REPORTERS", "ACTIVE_VALUES", "HEADER_PAGES",
        "OFFICIAL_EQUIPMENT_NAMES", "REGISTRATION_EXPIRE_COL", "ANNUAL_MAINT_COL",
        "TONNAGE_APPLIES_COL", "TONNAGE_EXPIRE_COL", "TONNAGE_DEFAULT_UNITS", "DATE_STATUS_COLORS",
        "IFTA_UNITS", "DRIVERS", "IFTA_TRIPS_SHEET_TITLE", "IFTA_FUEL_SHEET_TITLE", "IFTA_TRIPS_COLUMNS", "IFTA_FUEL_COLUMNS", "IFTA_RECEIPT_COLUMN", "IFTA_DEFAULT_JURISDICTION", "IFTA_JURISDICTIONS",
        "DOM_AIRCRAFT", "DOM_ACTION_ANNUAL", "YEARLY_ITEMS_SHEET_TITLE", "YEARLY_ITEMS_COLUMNS", "YEARLY_ITEM_GROUPS",
        "PARTS", "CORE_FACTORS", "PART_FACTORS", "PART_STOPS", "CONFIG_FIELDS",
        "ALL_FACTOR_KEYS", "ALL_STOP_KEYS", "FRAT_COLUMNS",
    }
    functions = {
        "_unique", "official_equipment_rows", "is_placeholder_equipment_seed",
        "_cell", "parse_equipment_date", "format_equipment_date", "registration_due_date", "annual_maint_due_date",
        "date_flag", "date_flag_label", "date_status_markup", "tonnage_applies", "tonnage_due_date", "is_active_equipment",
        "is_open_squawk", "is_grounded_squawk", "squawks_for", "open_squawks_for",
        "equipment_has_grounding", "records_from_worksheet", "_worksheet_or_none",
        "_write_equipment_rows", "ensure_equipment_worksheet", "ensure_equipment_info_columns",
        "ensure_squawks_worksheet", "load_equipment_records",
        "load_squawk_records", "build_squawk_record", "save_squawk_record", "resolve_squawk",
        "update_equipment_record",
        "safety_meeting_columns", "format_safety_meeting_attendees", "_safety_item_key", "ensure_safety_meetings_worksheet",
        "load_safety_meeting_records", "build_safety_meeting_record", "save_safety_meeting_record",
        "update_safety_meeting_discussion", "_safety_meeting_sort_key",
        "safety_meeting_entry_date", "parse_safety_meeting_attendees", "safety_meeting_item_done",
        "filter_safety_meetings", "safety_meeting_years", "safety_meeting_months_for_year",
        "safety_meeting_option_label", "safety_meeting_pdf_filename",
        "safety_meeting_report_logo_path", "build_safety_meeting_pdf", "safety_meeting_identity",
        "load_safety_meeting_records_readonly", "safety_meeting_months_with_entries",
        "safety_meeting_month_status", "current_month_has_safety_meeting",
        "safety_meeting_header_color", "safety_meeting_month_strip_markup",
        "apply_monthly_safety_header_style",
        "aircraft_maint_profile", "parse_hobbs", "format_hobbs", "next_hobbs",
        "hobbs_flag", "hobbs_status_markup", "ensure_aircraft_maint_worksheet",
        "load_aircraft_maint_records", "latest_aircraft_maint_record",
        "build_aircraft_maint_record", "save_aircraft_maint_record",
        "grease_offsets_for", "grease_checkpoint_label", "grease_checkpoint_columns",
        "n480ml_maint_columns", "grease_due_hobbs", "format_grease_hobbs_date",
        "is_grease_checkpoint_done", "grease_done_markup", "grease_amber_hours",
        "ensure_n480ml_maint_worksheet", "load_n480ml_maint_records",
        "load_aircraft_maint_records_readonly", "load_n480ml_maint_records_readonly",
        "combine_maint_status", "n893pc_annual_status", "n480ml_annual_status",
        "aircraft_annual_status", "aircraft_annual_button_label", "aircraft_annual_button_color",
        "load_latest_annual_record_readonly", "dom_annual_statuses",
        "apply_dom_annual_button_styles",
        "build_n480ml_maint_record", "save_n480ml_maint_record",
        "update_n480ml_grease_checkpoint",
        "unit_has_ifta", "ifta_jurisdiction_label", "ifta_jurisdiction_options", "parse_ifta_jurisdiction",
        "parse_ifta_number", "format_ifta_number", "ifta_trip_miles", "ifta_fuel_amounts",
        "format_ifta_have_receipt", "ifta_have_receipt_checked", "ifta_have_receipt_display", "ifta_receipt_from_record",
        "ifta_quarter_range", "ifta_in_quarter", "_ensure_ifta_worksheet", "ensure_ifta_trips_worksheet", "ensure_ifta_fuel_worksheet",
        "load_ifta_trip_records", "load_ifta_fuel_records", "build_ifta_trip_record", "build_ifta_fuel_record",
        "save_ifta_trip_record", "save_ifta_fuel_record", "ifta_mpg", "build_ifta_quarterly_summary",
        "build_ifta_summary_csv", "ifta_summary_pdf_filename", "build_ifta_summary_pdf",
        "yearly_item_group_names", "yearly_item_sections", "yearly_items_for_group",
        "yearly_item_display_name", "yearly_group_button_key",
        "ensure_yearly_items_worksheet", "load_yearly_item_records",
        "load_yearly_item_records_readonly", "yearly_item_year_value",
        "build_yearly_item_record", "save_yearly_item_record", "filter_yearly_items",
        "_yearly_item_sort_key", "latest_yearly_item_record", "yearly_item_is_done", "yearly_item_status",
        "yearly_group_status", "yearly_group_statuses", "yearly_item_years",
        "yearly_item_status_markup", "apply_yearly_group_button_styles",
    }
    nodes = [n for n in TREE.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name in functions)]
    from datetime import date, timedelta
    scope = {"datetime": datetime, "date": date, "timedelta": timedelta, "ZoneInfo": ZoneInfo}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), "exec"), scope)
    return scope


class WorksheetNotFound(Exception):
    pass


class FakeWorksheet:
    def __init__(self, title, rows=None):
        self.title = title
        self.rows = [list(r) for r in (rows or [])]
        self.writes = []

    def row_values(self, row):
        return list(self.rows[row - 1]) if 0 < row <= len(self.rows) else []

    def append_row(self, row, **kwargs):
        self.writes.append(("append_row", list(row)))
        self.rows.append(list(row))

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def get_all_records(self):
        if not self.rows:
            return []
        header = self.rows[0]
        records = []
        for row in self.rows[1:]:
            padded = list(row) + [""] * (len(header) - len(row))
            records.append(dict(zip(header, padded[:len(header)])))
        return records

    def update_cell(self, row, col, value):
        self.writes.append(("update_cell", row, col, value))
        while len(self.rows) < row:
            self.rows.append([])
        current = self.rows[row - 1]
        while len(current) < col:
            current.append("")
        current[col - 1] = value


class FakeSpreadsheet:
    def __init__(self, sheet1_header=None):
        self.sheets = {"Sheet1": FakeWorksheet("Sheet1", [list(sheet1_header or ["timestamp"])])}
        self.added = []

    @property
    def sheet1(self):
        return self.sheets["Sheet1"]

    def worksheet(self, title):
        if title not in self.sheets:
            raise WorksheetNotFound(f"Worksheet not found: {title}")
        return self.sheets[title]

    def add_worksheet(self, title, rows=0, cols=0):
        self.added.append(title)
        ws = FakeWorksheet(title)
        self.sheets[title] = ws
        return ws


def _pacific(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("America/Los_Angeles"))


class PlaceholderAndLogicTests(unittest.TestCase):
    def setUp(self):
        self.s = _exec_equipment_helpers()

    def test_official_list_order_and_blank_info_columns(self):
        expected = [
            "Heli1", "Heli2", "Heli3", "Heli4", "F250", "F350", "PW", "Ram", "FS Truck",
            "C8000", "S1", "Boomer", "Inter Fueler", "Bounder", "Bus", "Equinox", "Tesla", "Mercedes", "Sienna",
            "R44 Trailer", "Enstrom Heli Trailer", "Heli Hauler", "Pod", "Dump Trailer",
            "Fuel Trailer", "Bobcat", "Forklift", "Lift", "JD Tractor", "Grasshopper",
        ]
        self.assertEqual(self.s["OFFICIAL_EQUIPMENT_NAMES"], expected)
        rows = self.s["official_equipment_rows"]()
        self.assertEqual(len(rows), 30)
        self.assertEqual([r[0] for r in rows], expected)
        self.assertEqual([r[1] for r in rows], expected)
        trailer_names = {"R44 Trailer", "Enstrom Heli Trailer", "Dump Trailer", "Fuel Trailer"}
        for row in rows:
            self.assertEqual(len(row), len(self.s["EQUIPMENT_COLUMNS"]))
            self.assertEqual(row[3], "Yes")
            self.assertEqual(row[2], "Trailer" if row[0] in trailer_names else "")
            self.assertEqual(row[0], row[1])
            # Info and date columns stay blank — no invented values.
            # Tonnage Applies is Yes only for the six units Ron named.
            applies = "Yes" if row[0] in self.s["TONNAGE_DEFAULT_UNITS"] else ""
            self.assertEqual(self.s["tonnage_applies"](dict(zip(self.s["EQUIPMENT_COLUMNS"], row))), bool(applies))
            for col, val in zip(self.s["EQUIPMENT_COLUMNS"][4:], row[4:]):
                if col == "Tonnage Applies":
                    self.assertEqual(val, applies)
                else:
                    self.assertEqual(val, "")
        self.assertEqual(set(self.s["TONNAGE_DEFAULT_UNITS"]), {"Heli2", "Heli3", "Heli4", "S1", "C8000", "Boomer"})
        self.assertIn("Registration Expire Date", self.s["EQUIPMENT_COLUMNS"])
        self.assertIn("Annual Maint Date", self.s["EQUIPMENT_COLUMNS"])
        self.assertIn("Tonnage Wt Expire Date", self.s["EQUIPMENT_COLUMNS"])
        self.assertIn("Tonnage Applies", self.s["EQUIPMENT_COLUMNS"])
        self.assertEqual(self.s["official_equipment_rows"]()[21][0], "Heli Hauler")
        self.assertEqual(self.s["official_equipment_rows"]()[21][2], "")

    def test_registration_and_annual_maint_flags(self):
        from datetime import date
        today = date(2026, 11, 10)
        parse = self.s["parse_equipment_date"]
        self.assertEqual(parse(""), None)
        self.assertEqual(parse("2026-12-01"), date(2026, 12, 1))
        self.assertEqual(parse("11/15/2026"), date(2026, 11, 15))
        self.assertIsNone(parse("not a date"))
        expire = self.s["registration_due_date"]
        maint_due = self.s["annual_maint_due_date"]
        flag = self.s["date_flag"]
        self.assertEqual(expire({"Registration Expire Date": "2026-10-01"}), date(2026, 10, 1))
        self.assertEqual(flag(date(2026, 10, 1), today), "expired")
        self.assertEqual(flag(date(2026, 12, 1), today), "soon")
        self.assertEqual(flag(date(2027, 2, 1), today), "ok")
        self.assertIsNone(flag(None, today))
        self.assertEqual(maint_due({"Annual Maint Date": "2025-11-01"}), date(2026, 11, 1))
        self.assertEqual(flag(maint_due({"Annual Maint Date": "2025-11-01"}), today), "expired")
        self.assertEqual(flag(maint_due({"Annual Maint Date": "2025-12-01"}), today), "soon")
        self.assertEqual(flag(maint_due({"Annual Maint Date": "2026-01-15"}), today), "ok")
        self.assertEqual(maint_due({"Annual Maint Date": "2024-02-29"}), date(2025, 2, 28))
        self.assertIsNone(maint_due({"Annual Maint Date": ""}))
        markup = self.s["date_status_markup"]
        colors = self.s["DATE_STATUS_COLORS"]
        kind, html = markup("Registration Expire Date", "", None, today)
        self.assertIsNone(kind)
        self.assertIn("Not set", html)
        self.assertIn(colors[None], html)
        kind, html = markup("Registration Expire Date", "2026-10-01", date(2026, 10, 1), today)
        self.assertEqual(kind, "expired")
        self.assertIn(colors["expired"], html)
        kind, html = markup("Registration Expire Date", "2026-12-01", date(2026, 12, 1), today)
        self.assertEqual(kind, "soon")
        self.assertIn(colors["soon"], html)
        kind, html = markup("Registration Expire Date", "2027-02-01", date(2027, 2, 1), today)
        self.assertEqual(kind, "ok")
        self.assertIn(colors["ok"], html)
        applies = self.s["tonnage_applies"]
        self.assertTrue(applies({"Tonnage Applies": "Yes"}))
        self.assertFalse(applies({"Tonnage Applies": ""}))
        self.assertFalse(applies({"Tonnage Applies": "No"}))
        self.assertIsNone(self.s["tonnage_due_date"]({"Tonnage Applies": "", "Tonnage Wt Expire Date": "2026-10-01"}))
        self.assertEqual(
            self.s["tonnage_due_date"]({"Tonnage Applies": "Yes", "Tonnage Wt Expire Date": "2026-10-01"}),
            date(2026, 10, 1),
        )

    def test_frat_columns_unchanged(self):
        self.assertEqual(
            hashlib.sha256(json.dumps(self.s["FRAT_COLUMNS"]).encode()).hexdigest(),
            "f4b28b40aa9f60bf256574455cdab0d0ba642420cc368e1dca2490a7ec400eb0",
        )

    def test_reporters_reuse_existing_names(self):
        for name in self.s["PILOTS"] + self.s["APPROVERS"]:
            self.assertIn(name, self.s["REPORTERS"])

    def test_open_count_and_grounded_badge(self):
        squawks = [
            {"Unit ID": "TRK-01", "Status": "Open", "Severity": "Low"},
            {"Unit ID": "TRK-01", "Status": "Open", "Severity": "Medium"},
            {"Unit ID": "TRK-01", "Status": "Resolved", "Severity": "Grounded-Do not use"},
            {"Unit ID": "TRK-02", "Status": "Open", "Severity": "Grounded-Do not use"},
            {"Unit ID": "TRK-03", "Status": "Resolved", "Severity": "Low"},
        ]
        open_1 = self.s["open_squawks_for"]("TRK-01", squawks)
        self.assertEqual(len(open_1), 2)
        self.assertFalse(self.s["equipment_has_grounding"]("TRK-01", squawks))
        self.assertEqual(len(self.s["open_squawks_for"]("TRK-02", squawks)), 1)
        self.assertTrue(self.s["equipment_has_grounding"]("TRK-02", squawks))
        self.assertEqual(self.s["open_squawks_for"]("TRK-03", squawks), [])
        self.assertFalse(self.s["equipment_has_grounding"]("TRK-03", squawks))

    def test_inactive_equipment_hidden_by_flag(self):
        self.assertTrue(self.s["is_active_equipment"]({"Active": "Yes"}))
        self.assertTrue(self.s["is_active_equipment"]({"Active": ""}))
        self.assertFalse(self.s["is_active_equipment"]({"Active": "No"}))

    def test_build_squawk_requires_description_and_reporter(self):
        unit = {"Unit ID": "Heli4", "Name": "Heli4", "Type": ""}
        when = _pacific("2026-11-10 08:15:00")
        with self.assertRaisesRegex(ValueError, "description"):
            self.s["build_squawk_record"](unit, "Ronald A Cline", when, "Mechanical", "Low", "  ")
        with self.assertRaisesRegex(ValueError, "Reported By"):
            self.s["build_squawk_record"](unit, "", when, "Mechanical", "Low", "Brake light out")
        record = self.s["build_squawk_record"](
            unit, "Anthony Root", when, "Tires", "Medium", "Left rear tire low", "124500"
        )
        self.assertEqual(record["Timestamp"], "2026-11-10 08:15:00")
        self.assertEqual(record["Unit ID"], "Heli4")
        self.assertEqual(record["Equipment Name"], "Heli4")
        self.assertEqual(record["Type"], "")
        self.assertEqual(record["Reported By"], "Anthony Root")
        self.assertEqual(record["Category"], "Tires")
        self.assertEqual(record["Severity"], "Medium")
        self.assertEqual(record["Description"], "Left rear tire low")
        self.assertEqual(record["Odometer/Hours"], "124500")
        self.assertEqual(record["Status"], "Open")
        self.assertEqual(record["Resolved Date"], "")
        self.assertEqual(list(record), self.s["SQUAWK_COLUMNS"])

    def test_dom_aircraft_list_is_easy_to_extend(self):
        ids = [a["id"] for a in self.s["DOM_AIRCRAFT"]]
        self.assertEqual(ids, ["N893PC", "N480ML"])
        self.assertEqual(self.s["DOM_ACTION_ANNUAL"], "Annual/100 Hr")
        self.assertTrue(all("id" in aircraft for aircraft in self.s["DOM_AIRCRAFT"]))

    def test_format_equipment_date(self):
        from datetime import date
        fmt = self.s["format_equipment_date"]
        self.assertEqual(fmt(None), "")
        self.assertEqual(fmt(date(2027, 3, 1)), "2027-03-01")
        self.assertEqual(fmt("03/01/2027"), "2027-03-01")
        self.assertEqual(fmt(""), "")

    def test_safety_meeting_columns_are_extensible(self):
        items = self.s["SAFETY_MEETING_ITEMS"]
        self.assertEqual(items, [
            "Aircraft Fire Extinguishers",
            "Review Equipment",
            "Review Employee Licenses / Certificates",
            "First Aid Kits",
            "PPE",
        ])
        cols = self.s["safety_meeting_columns"]()
        self.assertEqual(cols[:4], ["Timestamp", "Meeting Date", "Recorded By", "Attendees"])
        self.assertEqual(cols[-1], "Discussion Notes")
        for item in items:
            self.assertIn(item + " Done", cols)
            self.assertIn(item + " Note", cols)
            self.assertLess(cols.index(item + " Done"), cols.index(item + " Note"))
        # Adding an item later should only append new Done/Note pairs before Discussion Notes.
        original = list(items)
        try:
            items.append("New Item")
            extended = self.s["safety_meeting_columns"]()
            self.assertEqual(extended[-3:], ["New Item Done", "New Item Note", "Discussion Notes"])
            self.assertEqual(extended[:-3], cols[:-1])
        finally:
            items[:] = original

    def test_safety_meeting_attendee_list_order_and_format(self):
        names = self.s["SAFETY_MEETING_ATTENDEES"]
        self.assertEqual(names, [
            "Ron Cline",
            "Anthony Root",
            "Carl Mulvaney",
            "Barry Markham",
            "Gary Grant",
            "Robert Rackley",
            "Skylar Fingerle",
        ])
        fmt = self.s["format_safety_meeting_attendees"]
        # Checked names are saved in list order, not click order; Other is appended.
        self.assertEqual(
            fmt(["Carl Mulvaney", "Ron Cline", "Unknown"], "Guest Pilot"),
            "Ron Cline, Carl Mulvaney, Guest Pilot",
        )
        self.assertEqual(fmt(["Skylar Fingerle"], ""), "Skylar Fingerle")
        self.assertEqual(fmt([], "Visitor"), "Visitor")
        self.assertEqual(fmt([], "  "), "")
        # Existing Attendees column name is unchanged.
        self.assertEqual(self.s["safety_meeting_columns"]()[3], "Attendees")

    def test_hobbs_next_values_and_color_flags(self):
        from datetime import date
        parse = self.s["parse_hobbs"]
        fmt = self.s["format_hobbs"]
        nxt = self.s["next_hobbs"]
        flag = self.s["hobbs_flag"]
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("not a number"))
        self.assertEqual(parse("1,205.5"), 1205.5)
        self.assertEqual(fmt(1200), "1200")
        self.assertEqual(fmt(1200.5), "1200.5")
        self.assertEqual(nxt(1105, 100), 1205)
        self.assertEqual(nxt(1160, 50), 1210)
        self.assertIsNone(nxt("", 100))
        # GREEN when current < next - 10; AMBER in [next-10, next); RED when >= next.
        self.assertEqual(flag(1194, 1205, 10), "ok")
        self.assertEqual(flag(1195, 1205, 10), "soon")
        self.assertEqual(flag(1204.9, 1205, 10), "soon")
        self.assertEqual(flag(1205, 1205, 10), "expired")
        self.assertEqual(flag(1206, 1205, 10), "expired")
        self.assertIsNone(flag("", 1205, 10))
        self.assertIsNone(flag(1200, "", 10))
        colors = self.s["DATE_STATUS_COLORS"]
        kind, html = self.s["hobbs_status_markup"]("Next 100 Hr", "", 1200, 10)
        self.assertIsNone(kind)
        self.assertIn("Not set", html)
        self.assertIn(colors[None], html)
        kind, html = self.s["hobbs_status_markup"]("Next 100 Hr", 1205, 1190, 10)
        self.assertEqual(kind, "ok")
        self.assertIn(colors["ok"], html)
        kind, html = self.s["hobbs_status_markup"]("Next Oil Change", 1210, 1200, 10)
        self.assertEqual(kind, "soon")
        self.assertIn(colors["soon"], html)
        kind, html = self.s["hobbs_status_markup"]("Next 100 Hr", 1205, 1205, 10)
        self.assertEqual(kind, "expired")
        self.assertIn(colors["expired"], html)
        today = date(2026, 11, 10)
        kind, html = self.s["date_status_markup"]("Annual Due Date", "2026-10-01", date(2026, 10, 1), today)
        self.assertEqual(kind, "expired")
        kind, html = self.s["date_status_markup"]("Annual Due Date", "2026-12-01", date(2026, 12, 1), today)
        self.assertEqual(kind, "soon")
        kind, html = self.s["date_status_markup"]("Annual Due Date", "2027-02-01", date(2027, 2, 1), today)
        self.assertEqual(kind, "ok")
        kind, html = self.s["date_status_markup"]("Annual Due Date", "", None, today)
        self.assertIsNone(kind)
        self.assertIn("Not set", html)
        self.assertEqual(self.s["aircraft_maint_profile"]("N893PC")["oil_interval"], 50)
        self.assertEqual(self.s["aircraft_maint_profile"]("N893PC")["hundred_hr_interval"], 100)
        self.assertNotIn("grease_offsets", self.s["aircraft_maint_profile"]("N893PC"))
        n480 = self.s["aircraft_maint_profile"]("N480ML")
        self.assertEqual(tuple(n480["grease_offsets"]), (25, 50, 75, 100))
        self.assertEqual(n480["hundred_hr_interval"], 100)
        self.assertEqual(n480["amber_hours"], 10)
        self.assertEqual(n480["grease_amber_hours"], 2)
        self.assertEqual(self.s["GREASE_AMBER_HOURS"], 2)
        self.assertEqual(self.s["grease_amber_hours"](n480), 2)
        self.assertNotIn("oil_interval", n480)

    def test_safety_meeting_month_status_and_header_color(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        today = date(2026, 11, 10)
        when_march = datetime(2026, 3, 12, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        when_nov = datetime(2026, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        march = self.s["build_safety_meeting_record"](
            date(2026, 3, 12), "Ronald A Cline", "Ron Cline", {}, "March notes.",
            when=when_march,
        )
        november = self.s["build_safety_meeting_record"](
            date(2026, 11, 10), "Ronald A Cline", "Ron Cline", {}, "November notes.",
            when=when_nov,
        )
        meetings = [march, november]
        status = self.s["safety_meeting_month_status"]
        self.assertEqual(status(2026, 3, meetings, today=today), "ok")
        self.assertEqual(status(2026, 11, meetings, today=today), "ok")
        self.assertEqual(status(2026, 1, meetings, today=today), "expired")
        self.assertEqual(status(2026, 10, meetings, today=today), "expired")
        self.assertIsNone(status(2026, 12, meetings, today=today))
        self.assertEqual(status(2025, 6, meetings, today=today), "expired")
        self.assertIsNone(status(2027, 1, meetings, today=today))
        self.assertTrue(self.s["current_month_has_safety_meeting"](meetings, today=today))
        self.assertFalse(self.s["current_month_has_safety_meeting"]([march], today=today))
        self.assertFalse(self.s["current_month_has_safety_meeting"]([], today=today))
        self.assertEqual(self.s["safety_meeting_header_color"](meetings, today=today), "#15803d")
        self.assertEqual(self.s["safety_meeting_header_color"]([march], today=today), "#b91c1c")
        self.assertEqual(self.s["safety_meeting_header_color"]([], today=today), "#b91c1c")
        self.assertEqual(self.s["DATE_STATUS_COLORS"]["ok"], "#15803d")
        self.assertEqual(self.s["DATE_STATUS_COLORS"]["expired"], "#b91c1c")
        self.assertEqual(self.s["DATE_STATUS_COLORS"][None], "#6b7280")
        html = self.s["safety_meeting_month_strip_markup"](2026, meetings, today=today)
        self.assertIn("safety-month-strip", html)
        for label in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"):
            self.assertIn(">" + label + "</span>", html)
        self.assertEqual(html.count("#15803d"), 2)
        self.assertEqual(html.count("#b91c1c"), 9)
        self.assertEqual(html.count("#6b7280"), 1)
        self.assertEqual(self.s["safety_meeting_months_with_entries"](meetings, 2026), {3, 11})
        self.assertEqual(self.s["safety_meeting_months_with_entries"](meetings, 2025), set())



    def test_annual_button_status_rollup_and_grease_two_hour_window(self):
        from datetime import date
        today = date(2026, 11, 10)
        colors = self.s["DATE_STATUS_COLORS"]
        good_n893 = {
            "Hobbs": "1190",
            "Next 100 Hr": "1205",
            "Next Oil Change": "1210",
            "Annual Due Date": "2027-03-01",
        }
        self.assertIsNone(self.s["n893pc_annual_status"](None, today=today))
        self.assertIsNone(self.s["aircraft_annual_status"]("N893PC", None, today=today))
        self.assertEqual(self.s["n893pc_annual_status"](good_n893, today=today), "ok")
        soon_100 = dict(good_n893, Hobbs="1196")
        self.assertEqual(self.s["n893pc_annual_status"](soon_100, today=today), "soon")
        soon_annual = dict(good_n893, **{"Annual Due Date": "2026-12-01"})
        self.assertEqual(self.s["n893pc_annual_status"](soon_annual, today=today), "soon")
        overdue_100 = dict(good_n893, Hobbs="1205")
        self.assertEqual(self.s["n893pc_annual_status"](overdue_100, today=today), "expired")
        overdue_annual = dict(good_n893, **{"Annual Due Date": "2026-10-01"})
        self.assertEqual(self.s["n893pc_annual_status"](overdue_annual, today=today), "expired")
        expired_wins = dict(good_n893, Hobbs="1205", **{"Annual Due Date": "2026-12-01"})
        self.assertEqual(self.s["n893pc_annual_status"](expired_wins, today=today), "expired")

        good_n480 = {
            "Hobbs": "1020",
            "Next 100 Hr": "1100",
            "Grease Hobbs": "1000",
            "Grease 25 Done": "Yes",
            "Grease 50 Done": "",
            "Grease 75 Done": "",
            "Grease 100 Done": "",
        }
        self.assertIsNone(self.s["n480ml_annual_status"](None, today=today))
        # 25 is done; 50 is due at 1050 (30 hours out) so overall good.
        self.assertEqual(self.s["n480ml_annual_status"](good_n480, today=today), "ok")
        # 5 hours before the 25 Hr grease due is still green; 2 hours is amber.
        open_25 = dict(good_n480, **{"Grease 25 Done": ""})
        self.assertEqual(self.s["n480ml_annual_status"](open_25, today=today), "ok")
        grease_soon = dict(open_25, Hobbs="1024")
        self.assertEqual(self.s["n480ml_annual_status"](grease_soon, today=today), "soon")
        grease_due = dict(open_25, Hobbs="1025")
        self.assertEqual(self.s["n480ml_annual_status"](grease_due, today=today), "expired")
        # 25/50/75 already done; grease 100 is due at 1100 (8 hours out, still green).
        hundred_soon = dict(
            good_n480, Hobbs="1092", **{
                "Next 100 Hr": "1100",
                "Grease 50 Done": "Yes",
                "Grease 75 Done": "Yes",
            },
        )
        self.assertEqual(self.s["n480ml_annual_status"](hundred_soon, today=today), "soon")
        self.assertEqual(self.s["aircraft_annual_button_label"](None), "Annual/100 Hr — No data")
        self.assertEqual(self.s["aircraft_annual_button_label"]("ok"), "Annual/100 Hr")
        self.assertEqual(self.s["aircraft_annual_button_label"]("soon"), "Annual/100 Hr")
        self.assertEqual(self.s["aircraft_annual_button_label"]("expired"), "Annual/100 Hr")
        self.assertEqual(self.s["aircraft_annual_button_color"](None), colors[None])
        self.assertEqual(self.s["aircraft_annual_button_color"]("ok"), colors["ok"])
        self.assertEqual(self.s["aircraft_annual_button_color"]("soon"), colors["soon"])
        self.assertEqual(self.s["aircraft_annual_button_color"]("expired"), colors["expired"])
        self.assertEqual(colors["soon"], "#b45309")
        self.assertEqual(self.s["combine_maint_status"]("ok", "soon", "expired"), "expired")
        self.assertEqual(self.s["combine_maint_status"]("ok", "soon"), "soon")
        self.assertEqual(self.s["combine_maint_status"]("ok", None), "ok")
        self.assertIsNone(self.s["combine_maint_status"](None, None))



    def test_yearly_items_groups_status_and_training_subheading(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        today = date(2026, 11, 10)
        self.assertEqual(self.s["YEARLY_ITEMS_SHEET_TITLE"], "Yearly Items")
        self.assertEqual(self.s["YEARLY_ITEMS_COLUMNS"], [
            "Timestamp", "Year", "Group", "Item", "Date Done", "Done By", "Notes",
        ])
        self.assertEqual(self.s["yearly_item_group_names"](), [
            "Winterizing",
            "Fuel Systems",
            "Annual Policies & Procedures (SMS)",
            "Training",
        ])
        self.assertEqual(self.s["yearly_items_for_group"]("Winterizing"), [
            "Office irrigation system",
            "Trucks",
            "Rinse Pad",
            "Pod",
            "Heli hauler",
            "Bounder",
        ])
        self.assertEqual(self.s["yearly_items_for_group"]("Fuel Systems"), ["Tanks"])
        self.assertEqual(
            self.s["yearly_items_for_group"]("Annual Policies & Procedures (SMS)"),
            ["Annual SMS policies & procedures review"],
        )
        self.assertEqual(self.s["yearly_items_for_group"]("Training"), [
            "WPS Mixer/Loader",
            "Pilot Training - N480ML",
            "Pilot Training - N893PC",
        ])
        sections = self.s["yearly_item_sections"]("Training")
        self.assertEqual(sections[0], (None, ["WPS Mixer/Loader"]))
        self.assertEqual(sections[1], ("Pilot Training", [
            "Pilot Training - N480ML",
            "Pilot Training - N893PC",
        ]))
        self.assertEqual(self.s["yearly_item_display_name"]("Pilot Training - N480ML", "Pilot Training"), "N480ML")
        self.assertEqual(self.s["yearly_item_display_name"]("WPS Mixer/Loader", None), "WPS Mixer/Loader")
        self.assertEqual(self.s["yearly_group_button_key"]("Fuel Systems"), "yearly_group_Fuel_Systems")
        self.assertEqual(
            self.s["yearly_group_button_key"]("Annual Policies & Procedures (SMS)"),
            "yearly_group_Annual_Policies_Procedures_SMS",
        )

        when = datetime(2026, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        trucks = self.s["build_yearly_item_record"](
            2026, "Winterizing", "Trucks", date(2026, 10, 15), "Ron Cline", "Winterized", when=when,
        )
        self.assertEqual(trucks["Year"], "2026")
        self.assertEqual(trucks["Group"], "Winterizing")
        self.assertEqual(trucks["Item"], "Trucks")
        self.assertEqual(trucks["Date Done"], "2026-10-15")
        self.assertEqual(trucks["Done By"], "Ron Cline")
        tanks = self.s["build_yearly_item_record"](
            2026, "Fuel Systems", "Tanks", date(2026, 11, 1), "Gary Grant", "", when=when,
        )
        n480 = self.s["build_yearly_item_record"](
            2026, "Training", "Pilot Training - N480ML", date(2026, 9, 1), "Anthony Root", "", when=when,
        )
        records = [trucks, tanks, n480]
        self.assertEqual(self.s["yearly_item_status"](records, 2026, "Winterizing", "Trucks"), "ok")
        self.assertEqual(self.s["yearly_item_status"](records, 2026, "Winterizing", "Pod"), "expired")
        self.assertEqual(self.s["yearly_group_status"](records, 2026, "Winterizing"), "expired")
        self.assertEqual(self.s["yearly_group_status"](records, 2026, "Fuel Systems"), "ok")
        self.assertEqual(self.s["yearly_group_status"](records, 2026, "Annual Policies & Procedures (SMS)"), "expired")
        self.assertEqual(self.s["yearly_group_status"](records, 2026, "Training"), "expired")
        self.assertEqual(self.s["yearly_item_status"](records, 2026, "Training", "Pilot Training - N480ML"), "ok")
        self.assertEqual(self.s["yearly_item_status"](records, 2026, "Training", "WPS Mixer/Loader"), "expired")
        all_winter = records + [
            self.s["build_yearly_item_record"](2026, "Winterizing", item, date(2026, 10, 15), "Ron Cline", "", when=when)
            for item in self.s["yearly_items_for_group"]("Winterizing")
            if item != "Trucks"
        ]
        self.assertEqual(self.s["yearly_group_status"](all_winter, 2026, "Winterizing"), "ok")
        self.assertEqual(self.s["yearly_group_status"](records, 2025, "Fuel Systems"), "expired")
        self.assertEqual(self.s["yearly_item_years"](records, today=today), [2026])
        kind, html = self.s["yearly_item_status_markup"]("Trucks", trucks)
        self.assertEqual(kind, "ok")
        self.assertIn("#15803d", html)
        self.assertIn("2026-10-15", html)
        self.assertIn("Ron Cline", html)
        kind, html = self.s["yearly_item_status_markup"]("Pod", None)
        self.assertEqual(kind, "expired")
        self.assertIn("#b91c1c", html)
        self.assertIn("Not done yet", html)
        with self.assertRaisesRegex(ValueError, "Done By"):
            self.s["build_yearly_item_record"](2026, "Fuel Systems", "Tanks", date(2026, 11, 1), "", "")

    def test_ifta_have_receipt_yes_no_and_keeps_receipt_hash_header(self):
        from datetime import date
        self.assertEqual(self.s["IFTA_RECEIPT_COLUMN"], "Receipt #")
        self.assertEqual(self.s["IFTA_FUEL_COLUMNS"][8], "Receipt #")
        fmt = self.s["format_ifta_have_receipt"]
        self.assertEqual(fmt(True), "Yes")
        self.assertEqual(fmt(False), "No")
        self.assertEqual(fmt("Yes"), "Yes")
        self.assertEqual(fmt("No"), "No")
        self.assertEqual(fmt(""), "No")
        self.assertEqual(fmt(None), "No")
        self.assertEqual(fmt("R-100"), "Yes")  # leftover receipt number still means they had one
        self.assertTrue(self.s["ifta_have_receipt_checked"]("Yes"))
        self.assertFalse(self.s["ifta_have_receipt_checked"]("No"))
        self.assertEqual(self.s["ifta_have_receipt_display"]("Yes"), "✓")
        self.assertEqual(self.s["ifta_have_receipt_display"]("No"), "✗")
        self.assertEqual(self.s["ifta_have_receipt_display"](""), "✗")
        rec = self.s["build_ifta_fuel_record"](
            date(2026, 11, 10), "Heli2", "WA", "10", "4", "",
            "Shell", True, "",
        )
        self.assertEqual(rec["Receipt #"], "Yes")
        self.assertEqual(self.s["ifta_receipt_from_record"](rec), "Yes")
        rec_no = self.s["build_ifta_fuel_record"](
            date(2026, 11, 10), "Heli2", "WA", "10", "4", "",
            "Shell", False, "",
        )
        self.assertEqual(rec_no["Receipt #"], "No")

    def test_ifta_drivers_dropdown_order_and_trips_header_unchanged(self):
        self.assertEqual(self.s["DRIVERS"], [
            "Robert Rackley",
            "Barry Markham",
            "Anthony Root",
            "Carl Mulvaney",
            "Ron Cline",
            "Gary Grant",
        ])
        self.assertEqual(self.s["IFTA_TRIPS_COLUMNS"], [
            "Timestamp", "Date", "Unit", "Driver", "Jurisdiction",
            "Start Odometer", "End Odometer", "Miles", "Notes",
        ])



class FakeSheetBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.s = _exec_equipment_helpers()
        self.book = FakeSpreadsheet(sheet1_header=self.s["FRAT_COLUMNS"])
        self.sheet1_before = [list(r) for r in self.book.sheet1.rows]

    def _assert_frat_untouched(self):
        self.assertEqual(self.book.sheet1.rows, self.sheet1_before)
        self.assertEqual(self.book.sheet1.writes, [])

    def test_creates_and_seeds_equipment_tab_only_when_missing(self):
        ws, created = self.s["ensure_equipment_worksheet"](self.book)
        self.assertTrue(created)
        self.assertEqual(ws.row_values(1), self.s["EQUIPMENT_COLUMNS"])
        records = self.s["load_equipment_records"](self.book)
        self.assertEqual(len(records), 30)
        self.assertIn("Equipment", self.book.added)
        self.assertEqual([r["Name"] for r in records], self.s["OFFICIAL_EQUIPMENT_NAMES"])
        self.assertTrue(all(r["Registration Expire Date"] == "" and r["Annual Maint Date"] == "" and r["Tonnage Wt Expire Date"] == "" for r in records))
        applies_yes = [r["Name"] for r in records if r["Tonnage Applies"] == "Yes"]
        self.assertEqual(set(applies_yes), set(self.s["TONNAGE_DEFAULT_UNITS"]))

        second, created_again = self.s["ensure_equipment_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertIs(second, ws)
        self.assertEqual(len(self.s["load_equipment_records"](self.book)), 30)
        self.assertEqual(self.book.added.count("Equipment"), 1)
        self._assert_frat_untouched()

    def test_replaces_placeholder_seed_with_official_list(self):
        self.book.sheets["Equipment"] = FakeWorksheet("Equipment", [
            ["Unit ID", "Name", "Type", "Active"],
            ["TRK-01", "Truck 1 (placeholder)", "Truck", "Yes"],
        ])
        ws, created = self.s["ensure_equipment_worksheet"](self.book)
        self.assertFalse(created)
        records = self.s["load_equipment_records"](self.book)
        self.assertEqual([r["Unit ID"] for r in records], self.s["OFFICIAL_EQUIPMENT_NAMES"])
        self.assertEqual(ws.row_values(1), self.s["EQUIPMENT_COLUMNS"])
        self._assert_frat_untouched()

    def test_does_not_overwrite_existing_equipment_names(self):
        existing = FakeWorksheet("Equipment", [
            ["Unit ID", "Name", "Type", "Active"],
            ["HELI2", "Heli2", "Truck", "Yes"],
        ])
        self.book.sheets["Equipment"] = existing
        ws, created = self.s["ensure_equipment_worksheet"](self.book)
        self.assertFalse(created)
        records = self.s["load_equipment_records"](self.book)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["Unit ID"], "HELI2")
        self.assertEqual(records[0]["Name"], "Heli2")
        self.assertEqual(records[0]["Type"], "Truck")
        # Missing info/date columns are added blank; existing values are kept.
        self.assertEqual(records[0]["Registration Expire Date"], "")
        self.assertEqual(records[0]["Annual Maint Date"], "")
        self.assertEqual(records[0]["Tonnage Wt Expire Date"], "")
        self.assertIn("Registration Expire Date", ws.row_values(1))
        self.assertIn("Annual Maint Date", ws.row_values(1))
        self.assertIn("Tonnage Wt Expire Date", ws.row_values(1))
        self.assertIn("Tonnage Applies", ws.row_values(1))
        self.assertEqual(self.book.added, [])
        self._assert_frat_untouched()

    def test_squawks_tab_gets_header_only_and_saves_rows(self):
        ws, created = self.s["ensure_squawks_worksheet"](self.book)
        self.assertTrue(created)
        self.assertEqual(ws.rows, [self.s["SQUAWK_COLUMNS"]])
        unit = {"Unit ID": "TRK-01", "Name": "Truck 1 (placeholder)", "Type": "Truck"}
        record = self.s["build_squawk_record"](
            unit, "Ronald A Cline", _pacific("2026-11-10 08:20:00"),
            "Mechanical", "Grounded-Do not use", "Won't start", "10.2",
        )
        self.s["save_squawk_record"](record, self.book)
        self.assertEqual(len(ws.rows), 2)
        self.assertEqual(ws.rows[1][0], "2026-11-10 08:20:00")
        self.assertEqual(ws.rows[1][self.s["SQUAWK_COLUMNS"].index("Status")], "Open")
        self.assertEqual(len(self.s["load_squawk_records"](self.book)), 1)
        self._assert_frat_untouched()
        self.assertNotIn("Sheet1", self.book.added)

    def test_resolve_updates_only_matching_open_squawk(self):
        self.s["ensure_squawks_worksheet"](self.book)
        unit = {"Unit ID": "CAR-01", "Name": "Car 1 (placeholder)", "Type": "Vehicle"}
        first = self.s["build_squawk_record"](
            unit, "Carl Mulvaney", _pacific("2026-11-10 08:21:00"),
            "Electrical", "Low", "Radio display dim",
        )
        second = self.s["build_squawk_record"](
            unit, "Carl Mulvaney", _pacific("2026-11-10 08:22:00"),
            "Body", "Medium", "Dented bumper",
        )
        self.s["save_squawk_record"](first, self.book)
        self.s["save_squawk_record"](second, self.book)
        self.s["resolve_squawk"](
            "2026-11-10 08:21:00", "CAR-01", "Anthony Root", "Bulb replaced",
            _pacific("2026-11-10 09:00:00"), self.book,
        )
        rows = self.s["load_squawk_records"](self.book)
        self.assertEqual(rows[0]["Status"], "Resolved")
        self.assertEqual(rows[0]["Resolved By"], "Anthony Root")
        self.assertEqual(rows[0]["Resolved Date"], "2026-11-10 09:00:00")
        self.assertEqual(rows[0]["Notes"], "Bulb replaced")
        self.assertEqual(rows[1]["Status"], "Open")
        self.assertEqual(rows[1]["Resolved By"], "")
        self._assert_frat_untouched()

    def test_resolve_requires_name(self):
        self.s["ensure_squawks_worksheet"](self.book)
        with self.assertRaisesRegex(ValueError, "Resolved By"):
            self.s["resolve_squawk"]("2026-11-10 08:21:00", "CAR-01", "  ", spreadsheet=self.book)

    def test_update_equipment_writes_only_matching_row_by_header(self):
        from datetime import date
        # Column order is intentionally different from EQUIPMENT_COLUMNS.
        cols = [
            "Name", "Active", "Unit ID", "Notes", "Year", "Type", "Make/Model",
            "VIN/Serial", "Plate/N-number", "Registration Expire Date",
            "Annual Maint Date", "Tonnage Applies", "Tonnage Wt Expire Date",
        ]
        self.book.sheets["Equipment"] = FakeWorksheet("Equipment", [
            cols,
            ["Heli1", "Yes", "Heli1", "", "", "", "", "", "", "", "", "", ""],
            ["Heli2", "Yes", "Heli2", "old note", "", "", "", "", "", "", "", "Yes", "2026-01-01"],
            ["Heli3", "Yes", "Heli3", "leave me", "2010", "", "", "", "", "", "", "Yes", ""],
        ])
        self.s["ensure_squawks_worksheet"](self.book)
        squawks_before = [list(r) for r in self.book.sheets["Squawks"].rows]
        squawks_writes_before = list(self.book.sheets["Squawks"].writes)
        header_before = list(self.book.sheets["Equipment"].rows[0])
        heli3_before = list(self.book.sheets["Equipment"].rows[3])

        self.s["update_equipment_record"]("Heli2", {
            "Unit ID": "SHOULD-NOT-CHANGE",
            "Name": "SHOULD-NOT-CHANGE",
            "Year": "2018",
            "Make/Model": "Test Model",
            "Type": "Vehicle",
            "Active": "Yes",
            "VIN/Serial": "SN123",
            "Plate/N-number": "ABC123",
            "Notes": "Phone edit",
            "Registration Expire Date": date(2027, 3, 1),
            "Annual Maint Date": "2026-04-15",
            "Tonnage Applies": "Yes",
            "Tonnage Wt Expire Date": date(2027, 6, 1),
            "Not A Column": "ignore me",
        }, self.book)

        records = self.s["records_from_worksheet"](self.book.sheets["Equipment"], self.s["EQUIPMENT_COLUMNS"])
        heli2 = next(r for r in records if r["Unit ID"] == "Heli2")
        self.assertEqual(heli2["Name"], "Heli2")
        self.assertEqual(heli2["Unit ID"], "Heli2")
        self.assertEqual(heli2["Year"], "2018")
        self.assertEqual(heli2["Make/Model"], "Test Model")
        self.assertEqual(heli2["Type"], "Vehicle")
        self.assertEqual(heli2["VIN/Serial"], "SN123")
        self.assertEqual(heli2["Plate/N-number"], "ABC123")
        self.assertEqual(heli2["Notes"], "Phone edit")
        self.assertEqual(heli2["Registration Expire Date"], "2027-03-01")
        self.assertEqual(heli2["Annual Maint Date"], "2026-04-15")
        self.assertEqual(heli2["Tonnage Applies"], "Yes")
        self.assertEqual(heli2["Tonnage Wt Expire Date"], "2027-06-01")
        self.assertEqual(self.book.sheets["Equipment"].rows[0], header_before)
        self.assertFalse(any(w[0] == "update_cell" and w[1] == 1 for w in self.book.sheets["Equipment"].writes))
        self.assertEqual(self.book.sheets["Equipment"].rows[3], heli3_before)
        self.assertEqual(self.book.sheets["Squawks"].rows, squawks_before)
        self.assertEqual(self.book.sheets["Squawks"].writes, squawks_writes_before)
        self._assert_frat_untouched()

    def test_update_equipment_leaves_tonnage_date_when_not_in_fields(self):
        cols = self.s["EQUIPMENT_COLUMNS"]
        row = {c: "" for c in cols}
        row.update({"Unit ID": "Heli2", "Name": "Heli2", "Active": "Yes", "Tonnage Applies": "Yes", "Tonnage Wt Expire Date": "2026-08-01"})
        self.book.sheets["Equipment"] = FakeWorksheet("Equipment", [cols, [row[c] for c in cols]])
        self.s["update_equipment_record"]("Heli2", {"Tonnage Applies": "No", "Year": "2019"}, self.book)
        records = self.s["records_from_worksheet"](self.book.sheets["Equipment"], cols)
        self.assertEqual(records[0]["Tonnage Applies"], "No")
        self.assertEqual(records[0]["Year"], "2019")
        self.assertEqual(records[0]["Tonnage Wt Expire Date"], "2026-08-01")
        self.assertEqual(records[0]["Name"], "Heli2")
        self._assert_frat_untouched()

    def test_update_equipment_rejects_missing_unit(self):
        cols = self.s["EQUIPMENT_COLUMNS"]
        row = {c: "" for c in cols}
        row.update({"Unit ID": "Heli1", "Name": "Heli1", "Active": "Yes"})
        self.book.sheets["Equipment"] = FakeWorksheet("Equipment", [cols, [row[c] for c in cols]])
        with self.assertRaisesRegex(ValueError, "Unit ID"):
            self.s["update_equipment_record"]("  ", {"Year": "2018"}, self.book)
        with self.assertRaisesRegex(RuntimeError, "Could not find that unit"):
            self.s["update_equipment_record"]("MissingUnit", {"Year": "2018"}, self.book)
        self.assertEqual(self.book.sheets["Equipment"].rows[1][cols.index("Year")], "")
        self._assert_frat_untouched()


    def test_safety_meetings_tab_saves_and_updates_discussion_only(self):
        from datetime import date
        # Pre-seed FRAT, Equipment, and Squawks so we can prove those headers stay put.
        self.s["ensure_equipment_worksheet"](self.book)
        self.s["ensure_squawks_worksheet"](self.book)
        equipment_before = [list(r) for r in self.book.sheets["Equipment"].rows]
        squawks_before = [list(r) for r in self.book.sheets["Squawks"].rows]
        equipment_writes = list(self.book.sheets["Equipment"].writes)
        squawks_writes = list(self.book.sheets["Squawks"].writes)

        ws, created = self.s["ensure_safety_meetings_worksheet"](self.book)
        self.assertTrue(created)
        self.assertEqual(ws.row_values(1), self.s["safety_meeting_columns"]())
        second, created_again = self.s["ensure_safety_meetings_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertIs(second, ws)

        earlier = self.s["build_safety_meeting_record"](
            date(2026, 10, 1), "Ronald A Cline", "Ron, Carl",
            {
                "Aircraft Fire Extinguishers": {"done": True, "note": "Cabin bottle OK"},
                "PPE": {"done": False, "note": ""},
            },
            "Talked about winter ops.",
            _pacific("2026-10-01 09:00:00"),
        )
        later = self.s["build_safety_meeting_record"](
            date(2026, 11, 10), "Anthony Root", "",
            {"Review Equipment": {"done": True, "note": "List reviewed"}},
            "Discussed equipment squawks.",
            _pacific("2026-11-10 08:00:00"),
        )
        self.assertEqual(earlier["Aircraft Fire Extinguishers Done"], "Yes")
        self.assertEqual(earlier["Aircraft Fire Extinguishers Note"], "Cabin bottle OK")
        self.assertEqual(earlier["PPE Done"], "")
        self.assertEqual(earlier["Review Employee Licenses / Certificates Done"], "")
        self.s["save_safety_meeting_record"](earlier, self.book)
        self.s["save_safety_meeting_record"](later, self.book)
        rows = self.s["load_safety_meeting_records"](self.book)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Meeting Date"], "2026-10-01")
        self.assertEqual(rows[1]["Meeting Date"], "2026-11-10")
        self.assertEqual(rows[1]["Recorded By"], "Anthony Root")
        self.assertEqual(rows[1]["Review Equipment Done"], "Yes")
        self.assertEqual(rows[1]["Discussion Notes"], "Discussed equipment squawks.")

        self.s["update_safety_meeting_discussion"](
            "2026-11-10 08:00:00", "Discussed equipment squawks. Added follow-up.", self.book
        )
        rows = self.s["load_safety_meeting_records"](self.book)
        self.assertEqual(rows[0]["Discussion Notes"], "Talked about winter ops.")
        self.assertEqual(rows[1]["Discussion Notes"], "Discussed equipment squawks. Added follow-up.")
        self.assertEqual(rows[1]["Review Equipment Done"], "Yes")
        self.assertEqual(rows[1]["Meeting Date"], "2026-11-10")
        # Only the Discussion Notes cell on that row was updated after the two appends.
        discussion_col = self.s["safety_meeting_columns"]().index("Discussion Notes") + 1
        cell_writes = [w for w in ws.writes if w[0] == "update_cell"]
        self.assertTrue(any(w[1] == 3 and w[2] == discussion_col for w in cell_writes))
        self.assertFalse(any(w[1] == 1 for w in cell_writes))  # header row unchanged after create
        self.assertFalse(any(w[1] == 2 for w in cell_writes))  # earlier meeting untouched

        self.assertEqual(self.book.sheets["Equipment"].rows, equipment_before)
        self.assertEqual(self.book.sheets["Squawks"].rows, squawks_before)
        self.assertEqual(self.book.sheets["Equipment"].writes, equipment_writes)
        self.assertEqual(self.book.sheets["Squawks"].writes, squawks_writes)
        self.assertEqual(self.book.sheets["Equipment"].rows[0], self.s["EQUIPMENT_COLUMNS"])
        self.assertEqual(self.book.sheets["Squawks"].rows[0], self.s["SQUAWK_COLUMNS"])
        self._assert_frat_untouched()
        sorted_rows = sorted(rows, key=self.s["_safety_meeting_sort_key"], reverse=True)
        self.assertEqual([r["Timestamp"] for r in sorted_rows], ["2026-11-10 08:00:00", "2026-10-01 09:00:00"])


    def test_safety_meeting_viewer_filters_and_pdf_are_one_page(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import fitz

        earlier = self.s["build_safety_meeting_record"](
            date(2026, 10, 15), "Anthony Root",
            self.s["format_safety_meeting_attendees"](["Ron Cline"], "Visitor One"),
            {"PPE": {"done": True, "note": "Gloves restocked"}},
            "October notes.",
            when=datetime(2026, 10, 15, 8, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        later = self.s["build_safety_meeting_record"](
            date(2026, 11, 10), "Ronald A Cline",
            self.s["format_safety_meeting_attendees"](["Ron Cline", "Carl Mulvaney"], "Guest Pilot"),
            {"Aircraft Fire Extinguishers": {"done": True, "note": "Cabin bottle OK"}},
            "Talked about winter ops.",
            when=datetime(2026, 11, 10, 9, 30, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        self.s["ensure_safety_meetings_worksheet"](self.book)
        header_before = list(self.book.sheets["Safety Meetings"].rows[0])
        frat_before = [list(r) for r in self.book.sheet1.rows]
        frat_writes = list(self.book.sheet1.writes)
        self.s["save_safety_meeting_record"](earlier, self.book)
        self.s["save_safety_meeting_record"](later, self.book)
        rows = self.s["load_safety_meeting_records"](self.book)

        checked, other = self.s["parse_safety_meeting_attendees"](later["Attendees"])
        self.assertEqual(checked, ["Ron Cline", "Carl Mulvaney"])
        self.assertEqual(other, "Guest Pilot")
        self.assertTrue(self.s["safety_meeting_item_done"](later, "Aircraft Fire Extinguishers"))
        self.assertFalse(self.s["safety_meeting_item_done"](later, "PPE"))
        self.assertEqual(self.s["safety_meeting_years"](rows), [2026])
        self.assertEqual(self.s["safety_meeting_months_for_year"](rows, 2026), [10, 11])
        november = self.s["filter_safety_meetings"](rows, year=2026, month=11)
        self.assertEqual([r["Meeting Date"] for r in november], ["2026-11-10"])
        newest_first = self.s["filter_safety_meetings"](rows)
        self.assertEqual([r["Meeting Date"] for r in newest_first], ["2026-11-10", "2026-10-15"])
        self.assertEqual(self.s["safety_meeting_pdf_filename"](later), "CVH_Monthly_Safety_Meeting_2026-11-10.pdf")

        logo = self.s["safety_meeting_report_logo_path"]()
        self.assertTrue(logo)
        self.assertTrue(logo.endswith("flaglogo.png") or logo.endswith("flaglogo_report.png"))
        pdf = self.s["build_safety_meeting_pdf"](later, logo_path="/workspace/invoices/logo/flaglogo.png")
        self.assertGreater(len(pdf), 1000)
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = fitz.open(stream=pdf, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        extracted = "\n".join(page.get_text() for page in doc)
        self.assertIn("Monthly Safety Meeting", extracted)
        self.assertIn("Central Valley Helicopters", extracted)
        self.assertIn("2026-11-10", extracted)
        self.assertIn("Ronald A Cline", extracted)
        self.assertIn("Aircraft Fire Extinguishers", extracted)
        self.assertIn("Done / Reviewed", extracted)
        self.assertIn("Cabin bottle OK", extracted)
        self.assertIn("Review Equipment", extracted)
        self.assertIn("Not reviewed", extracted)
        self.assertIn("Ron Cline", extracted)
        self.assertIn("Carl Mulvaney", extracted)
        self.assertIn("Guest Pilot", extracted)
        self.assertIn("Talked about winter ops.", extracted)
        self.assertEqual(self.book.sheets["Safety Meetings"].rows[0], header_before)
        self.assertEqual(self.book.sheet1.rows, frat_before)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()
        self.assertTrue(doc[0].get_images(), "expected the flag logo on the PDF page")
        doc.close()

    def test_safety_meeting_update_rejects_missing_row(self):
        self.s["ensure_safety_meetings_worksheet"](self.book)
        with self.assertRaisesRegex(ValueError, "Timestamp"):
            self.s["update_safety_meeting_discussion"]("  ", "notes", self.book)
        with self.assertRaisesRegex(RuntimeError, "Could not find that meeting"):
            self.s["update_safety_meeting_discussion"]("1999-01-01 00:00:00", "notes", self.book)
        self._assert_frat_untouched()



    def test_readonly_safety_meeting_load_does_not_create_or_alter_tabs(self):
        frat_before = [list(r) for r in self.book.sheet1.rows]
        frat_writes = list(self.book.sheet1.writes)
        rows = self.s["load_safety_meeting_records_readonly"](self.book)
        self.assertEqual(rows, [])
        self.assertNotIn("Safety Meetings", self.book.sheets)
        self.assertEqual(self.book.added, [])
        self._assert_frat_untouched()
        self.assertEqual(self.book.sheet1.rows, frat_before)
        self.assertEqual(self.book.sheet1.writes, frat_writes)

        ws, created = self.s["ensure_safety_meetings_worksheet"](self.book)
        self.assertTrue(created)
        header = list(ws.rows[0])
        writes_after_ensure = list(ws.writes)
        rows_after_ensure = [list(r) for r in ws.rows]
        loaded = self.s["load_safety_meeting_records_readonly"](self.book)
        self.assertEqual(loaded, [])
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(ws.rows, rows_after_ensure)
        self.assertEqual(ws.writes, writes_after_ensure)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self.assertEqual(self.book.added.count("Safety Meetings"), 1)

        from datetime import date
        record = self.s["build_safety_meeting_record"](
            date(2026, 11, 10), "Ronald A Cline", "Ron Cline", {}, "November notes.",
        )
        self.s["save_safety_meeting_record"](record, self.book)
        writes_after_save = list(ws.writes)
        rows_after_save = [list(r) for r in ws.rows]
        loaded = self.s["load_safety_meeting_records_readonly"](self.book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Meeting Date"], "2026-11-10")
        self.assertEqual(ws.writes, writes_after_save)
        self.assertEqual(ws.rows, rows_after_save)
        self._assert_frat_untouched()


    def test_readonly_annual_status_load_does_not_create_or_alter_tabs(self):
        from datetime import date
        frat_writes = list(self.book.sheet1.writes)
        self.assertEqual(self.s["load_aircraft_maint_records_readonly"](self.book), [])
        self.assertEqual(self.s["load_n480ml_maint_records_readonly"](self.book), [])
        self.assertIsNone(self.s["load_latest_annual_record_readonly"]("N893PC", self.book))
        self.assertIsNone(self.s["load_latest_annual_record_readonly"]("N480ML", self.book))
        self.assertNotIn("Aircraft Maint", self.book.sheets)
        self.assertNotIn("N480ML Maint", self.book.sheets)
        statuses = self.s["dom_annual_statuses"](self.book, today=date(2026, 11, 10))
        self.assertEqual(statuses, {"N893PC": None, "N480ML": None})
        self.assertNotIn("Aircraft Maint", self.book.sheets)
        self.assertNotIn("N480ML Maint", self.book.sheets)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()

        self.s["ensure_aircraft_maint_worksheet"](self.book)
        self.s["ensure_n480ml_maint_worksheet"](self.book)
        ac = self.book.sheets["Aircraft Maint"]
        n480 = self.book.sheets["N480ML Maint"]
        ac_header, n480_header = list(ac.rows[0]), list(n480.rows[0])
        ac_writes, n480_writes = list(ac.writes), list(n480.writes)
        self.assertEqual(self.s["load_aircraft_maint_records_readonly"](self.book, "N893PC"), [])
        self.assertEqual(self.s["load_n480ml_maint_records_readonly"](self.book), [])
        self.assertEqual(ac.rows[0], ac_header)
        self.assertEqual(n480.rows[0], n480_header)
        self.assertEqual(ac.writes, ac_writes)
        self.assertEqual(n480.writes, n480_writes)

        good = self.s["build_aircraft_maint_record"](
            "N893PC", date(2026, 11, 10), "1190", "1105", date(2027, 3, 1), "1160", "Ronald A Cline",
        )
        self.s["save_aircraft_maint_record"](good, self.book)
        ac_writes = list(ac.writes)
        ac_rows = [list(r) for r in ac.rows]
        loaded = self.s["load_aircraft_maint_records_readonly"](self.book, "N893PC")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(self.s["aircraft_annual_status"]("N893PC", loaded[0], today=date(2026, 11, 10)), "ok")
        self.assertEqual(ac.writes, ac_writes)
        self.assertEqual(ac.rows, ac_rows)
        self._assert_frat_untouched()

    def test_aircraft_maint_tab_appends_only_and_computes_next(self):
        from datetime import date
        self.s["ensure_equipment_worksheet"](self.book)
        self.s["ensure_squawks_worksheet"](self.book)
        self.s["ensure_safety_meetings_worksheet"](self.book)
        equipment_before = [list(r) for r in self.book.sheets["Equipment"].rows]
        squawks_before = [list(r) for r in self.book.sheets["Squawks"].rows]
        safety_before = [list(r) for r in self.book.sheets["Safety Meetings"].rows]
        equipment_writes = list(self.book.sheets["Equipment"].writes)
        squawks_writes = list(self.book.sheets["Squawks"].writes)
        safety_writes = list(self.book.sheets["Safety Meetings"].writes)

        ws, created = self.s["ensure_aircraft_maint_worksheet"](self.book)
        self.assertTrue(created)
        self.assertEqual(ws.row_values(1), self.s["AIRCRAFT_MAINT_COLUMNS"])
        second, created_again = self.s["ensure_aircraft_maint_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertIs(second, ws)

        record = self.s["build_aircraft_maint_record"](
            "N893PC", date(2026, 11, 10), "1190", "1105", date(2027, 3, 1), "1160",
            "Ronald A Cline", _pacific("2026-11-10 09:00:00"),
        )
        self.assertEqual(record["Aircraft"], "N893PC")
        self.assertEqual(record["Entry Date"], "2026-11-10")
        self.assertEqual(record["Hobbs"], "1190")
        self.assertEqual(record["Last 100 Hr"], "1105")
        self.assertEqual(record["Next 100 Hr"], "1205")
        self.assertEqual(record["Annual Due Date"], "2027-03-01")
        self.assertEqual(record["Last Oil Change"], "1160")
        self.assertEqual(record["Next Oil Change"], "1210")
        self.assertEqual(record["Entered By"], "Ronald A Cline")
        self.s["save_aircraft_maint_record"](record, self.book)
        later = self.s["build_aircraft_maint_record"](
            "N893PC", date(2026, 11, 10), "1200", "1105", date(2027, 3, 1), "1160",
            "Anthony Root", _pacific("2026-11-10 10:00:00"),
        )
        self.s["save_aircraft_maint_record"](later, self.book)
        rows = self.s["load_aircraft_maint_records"](self.book, aircraft_id="N893PC")
        self.assertEqual(len(rows), 2)
        latest = self.s["latest_aircraft_maint_record"](rows)
        self.assertEqual(latest["Timestamp"], "2026-11-10 10:00:00")
        self.assertEqual(latest["Hobbs"], "1200")
        self.assertEqual(latest["Next 100 Hr"], "1205")
        self.assertEqual(latest["Next Oil Change"], "1210")
        self.assertEqual(ws.rows[0], self.s["AIRCRAFT_MAINT_COLUMNS"])
        self.assertEqual(self.book.sheets["Equipment"].rows, equipment_before)
        self.assertEqual(self.book.sheets["Squawks"].rows, squawks_before)
        self.assertEqual(self.book.sheets["Safety Meetings"].rows, safety_before)
        self.assertEqual(self.book.sheets["Equipment"].writes, equipment_writes)
        self.assertEqual(self.book.sheets["Squawks"].writes, squawks_writes)
        self.assertEqual(self.book.sheets["Safety Meetings"].writes, safety_writes)
        self._assert_frat_untouched()

    def test_build_aircraft_maint_rejects_aircraft_without_profile(self):
        from datetime import date
        with self.assertRaisesRegex(ValueError, "No maintenance profile"):
            self.s["build_aircraft_maint_record"](
                "N999XX", date(2026, 11, 10), "100", "0", None, "0", "Ronald A Cline",
            )
        self.assertNotIn("Aircraft Maint", self.book.sheets)
        self._assert_frat_untouched()


    def test_n480ml_maint_uses_separate_tab_and_leaves_existing_headers_alone(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo

        self.s["ensure_aircraft_maint_worksheet"](self.book)
        aircraft_ws = self.book.sheets["Aircraft Maint"]
        aircraft_header = list(aircraft_ws.rows[0])
        aircraft_writes = list(aircraft_ws.writes)
        frat_before = [list(r) for r in self.book.sheet1.rows]
        frat_writes = list(self.book.sheet1.writes)

        cols = self.s["n480ml_maint_columns"]()
        self.assertEqual(cols[:7], [
            "Timestamp", "Aircraft", "Entry Date", "Hobbs",
            "Last 100 Hr", "Next 100 Hr", "Grease Hobbs",
        ])
        self.assertIn("Grease 25 Done", cols)
        self.assertIn("Grease 25 Initials", cols)
        self.assertIn("Grease 25 Hobbs/Date", cols)
        self.assertIn("Grease 50 Done", cols)
        self.assertIn("Grease 75 Done", cols)
        self.assertIn("Grease 100 Done", cols)
        self.assertIn("Grease 100 Initials", cols)
        self.assertIn("Grease 100 Hobbs/Date", cols)
        self.assertNotIn("Annual Due Date", cols)
        self.assertNotIn("Last Oil Change", cols)
        self.assertEqual(self.s["grease_due_hobbs"]("1000", 25), 1025)
        self.assertEqual(self.s["grease_due_hobbs"]("1000", 50), 1050)
        self.assertEqual(self.s["grease_due_hobbs"]("1000", 75), 1075)
        self.assertEqual(self.s["grease_due_hobbs"]("1000", 100), 1100)
        self.assertEqual(self.s["hobbs_flag"]("1014", "1025", 10), "ok")
        self.assertEqual(self.s["hobbs_flag"]("1015", "1025", 10), "soon")
        self.assertEqual(self.s["hobbs_flag"]("1025", "1025", 10), "expired")
        # Grease uses a 2-hour window: 5 hours out is still good; 2 hours out is amber.
        self.assertEqual(self.s["hobbs_flag"]("1020", "1025", 2), "ok")
        self.assertEqual(self.s["hobbs_flag"]("1022", "1025", 2), "ok")
        self.assertEqual(self.s["hobbs_flag"]("1023", "1025", 2), "soon")
        self.assertEqual(self.s["hobbs_flag"]("1025", "1025", 2), "expired")
        kind, html = self.s["hobbs_status_markup"]("25 Hr", None, "1000", 10)
        self.assertIsNone(kind)
        self.assertIn("Not set", html)
        self.assertIn("#6b7280", html)

        ws, created = self.s["ensure_n480ml_maint_worksheet"](self.book)
        self.assertTrue(created)
        self.assertEqual(ws.rows[0], cols)
        self.assertEqual(self.book.sheets["Aircraft Maint"].rows[0], aircraft_header)
        self.assertEqual(self.book.sheets["Aircraft Maint"].writes, aircraft_writes)

        ws2, created2 = self.s["ensure_n480ml_maint_worksheet"](self.book)
        self.assertFalse(created2)
        self.assertIs(ws2, ws)
        self.assertEqual(ws.rows[0], cols)

        when = datetime(2026, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        first = self.s["build_n480ml_maint_record"](
            date(2026, 11, 10), "1020", "1000", "1000", "Ronald A Cline",
            checkpoints={25: {"done": True, "initials": "RC", "hobbs": "1020", "when": when}},
            when=when,
        )
        self.assertEqual(first["Aircraft"], "N480ML")
        self.assertEqual(first["Next 100 Hr"], "1100")
        self.assertEqual(first["Grease Hobbs"], "1000")
        self.assertEqual(first["Grease 25 Done"], "Yes")
        self.assertEqual(first["Grease 25 Initials"], "RC")
        self.assertEqual(first["Grease 25 Hobbs/Date"], "1020 / 2026-11-10")
        self.assertEqual(first["Grease 50 Done"], "")
        self.s["save_n480ml_maint_record"](first, spreadsheet=self.book)

        later = datetime(2026, 11, 10, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        second = self.s["build_n480ml_maint_record"](
            date(2026, 11, 10), "1200", "1100", "1200", "Ronald A Cline",
            when=later,
        )
        self.assertEqual(second["Grease Hobbs"], "1200")
        self.assertEqual(second["Next 100 Hr"], "1200")
        self.assertEqual(second["Grease 25 Done"], "")
        self.assertEqual(second["Grease 50 Done"], "")
        self.s["save_n480ml_maint_record"](second, spreadsheet=self.book)

        rows = self.s["load_n480ml_maint_records"](self.book)
        self.assertEqual(len(rows), 2)
        latest = self.s["latest_aircraft_maint_record"](rows)
        self.assertEqual(latest["Timestamp"], "2026-11-10 10:00:00")
        self.assertEqual(latest["Grease Hobbs"], "1200")
        self.assertFalse(self.s["is_grease_checkpoint_done"](latest, 25))

        checked_at = datetime(2026, 11, 10, 11, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.s["update_n480ml_grease_checkpoint"](
            latest["Timestamp"], 25, "AR", "1200", when=checked_at, spreadsheet=self.book,
        )
        rows = self.s["load_n480ml_maint_records"](self.book)
        first_row, second_row = rows
        self.assertEqual(first_row["Grease 25 Done"], "Yes")
        self.assertEqual(first_row["Grease 25 Initials"], "RC")
        self.assertEqual(first_row["Grease 25 Hobbs/Date"], "1020 / 2026-11-10")
        self.assertEqual(second_row["Grease 25 Done"], "Yes")
        self.assertEqual(second_row["Grease 25 Initials"], "AR")
        self.assertEqual(second_row["Grease 25 Hobbs/Date"], "1200 / 2026-11-10")
        self.assertEqual(second_row["Grease 50 Done"], "")
        self.assertEqual(second_row["Hobbs"], "1200")
        self.assertEqual(second_row["Grease Hobbs"], "1200")
        self.assertTrue(self.s["is_grease_checkpoint_done"](second_row, 25))
        done_kind_html = self.s["grease_done_markup"]("25 Hr", second_row, 25)
        self.assertIn("✓ Done", done_kind_html)
        self.assertIn("AR", done_kind_html)
        self.assertIn("1200 / 2026-11-10", done_kind_html)
        self.assertIn("#6b7280", done_kind_html)

        n480_header = list(self.book.sheets["N480ML Maint"].rows[0])
        self.assertEqual(n480_header, cols)
        self.assertEqual(self.book.sheets["Aircraft Maint"].rows[0], aircraft_header)
        self.assertEqual(self.book.sheets["Aircraft Maint"].writes, aircraft_writes)
        self.assertEqual(self.book.sheet1.rows, frat_before)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()
        self.assertEqual(set(self.book.sheets), {"Sheet1", "Aircraft Maint", "N480ML Maint"})

    def test_n480ml_ensure_does_not_alter_an_existing_custom_header(self):
        ws = self.book.add_worksheet("N480ML Maint", 20, 8)
        ws.append_row(["Timestamp", "Aircraft", "Custom"])
        writes = list(ws.writes)
        out, created = self.s["ensure_n480ml_maint_worksheet"](self.book)
        self.assertFalse(created)
        self.assertIs(out, ws)
        self.assertEqual(ws.rows[0], ["Timestamp", "Aircraft", "Custom"])
        self.assertEqual(ws.writes, writes)
        self._assert_frat_untouched()
        self.assertNotIn("Aircraft Maint", self.book.sheets)




    def test_ifta_tabs_trips_fuel_summary_and_pdf_leave_existing_headers_alone(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import fitz
        import csv
        from io import StringIO

        self.assertEqual(self.s["IFTA_UNITS"], ("Heli2",))
        self.assertTrue(self.s["unit_has_ifta"]({"Unit ID": "Heli2", "Name": "Heli2"}))
        self.assertTrue(self.s["unit_has_ifta"]("Heli2"))
        self.assertFalse(self.s["unit_has_ifta"]({"Unit ID": "Heli1", "Name": "Heli1"}))
        self.assertFalse(self.s["unit_has_ifta"]("Heli3"))
        self.assertEqual(self.s["parse_ifta_jurisdiction"]("WA — Washington"), "WA")
        self.assertEqual(self.s["parse_ifta_jurisdiction"]("Washington"), "WA")
        self.assertEqual(self.s["parse_ifta_jurisdiction"]("bc"), "BC")
        self.assertEqual(self.s["ifta_trip_miles"]("10000", "10450"), 450)
        self.assertIsNone(self.s["ifta_trip_miles"]("10000", ""))
        gallons, price, total = self.s["ifta_fuel_amounts"]("100", "4.50", "")
        self.assertEqual(gallons, 100)
        self.assertEqual(price, 4.5)
        self.assertEqual(total, 450)
        gallons, price, total = self.s["ifta_fuel_amounts"]("50", "", "200")
        self.assertEqual(price, 4)
        self.assertEqual(total, 200)
        start, end = self.s["ifta_quarter_range"](2026, 1)
        self.assertEqual((start, end), (date(2026, 1, 1), date(2026, 3, 31)))
        start, end = self.s["ifta_quarter_range"](2026, 4)
        self.assertEqual((start, end), (date(2026, 10, 1), date(2026, 12, 31)))

        with self.assertRaisesRegex(ValueError, "0 or greater"):
            self.s["build_ifta_trip_record"](
                date(2026, 11, 10), "Heli2", "Anthony Root", "WA", "200", "100", "",
            )
        with self.assertRaisesRegex(ValueError, "required"):
            self.s["build_ifta_trip_record"](
                date(2026, 11, 10), "Heli2", "Anthony Root", "WA", "200", "", "",
            )

        # Existing tabs must stay untouched when IFTA tabs are created and written.
        self.s["ensure_equipment_worksheet"](self.book)
        self.s["ensure_squawks_worksheet"](self.book)
        self.s["ensure_safety_meetings_worksheet"](self.book)
        self.s["ensure_aircraft_maint_worksheet"](self.book)
        snapshots = {}
        for title in ("Equipment", "Squawks", "Safety Meetings", "Aircraft Maint"):
            ws = self.book.sheets[title]
            snapshots[title] = (list(ws.rows[0]), list(ws.rows), list(ws.writes))
        frat_before = [list(r) for r in self.book.sheet1.rows]
        frat_writes = list(self.book.sheet1.writes)

        trips_ws, created_trips = self.s["ensure_ifta_trips_worksheet"](self.book)
        fuel_ws, created_fuel = self.s["ensure_ifta_fuel_worksheet"](self.book)
        self.assertTrue(created_trips)
        self.assertTrue(created_fuel)
        self.assertEqual(trips_ws.rows[0], self.s["IFTA_TRIPS_COLUMNS"])
        self.assertEqual(fuel_ws.rows[0], self.s["IFTA_FUEL_COLUMNS"])
        trips2, created_trips2 = self.s["ensure_ifta_trips_worksheet"](self.book)
        self.assertFalse(created_trips2)
        self.assertIs(trips2, trips_ws)

        when = datetime(2026, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        trip = self.s["build_ifta_trip_record"](
            date(2026, 11, 10), "Heli2", "Anthony Root", "WA — Washington",
            "10000", "10450", "Ellensburg to Yakima", when=when,
        )
        self.assertEqual(trip["Miles"], "450")
        self.assertEqual(trip["Jurisdiction"], "WA")
        self.assertEqual(trip["Unit"], "Heli2")
        self.s["save_ifta_trip_record"](trip, self.book)

        or_trip = self.s["build_ifta_trip_record"](
            date(2026, 11, 11), "Heli2", "Ronald A Cline", "OR",
            "10450", "10600", "", when=datetime(2026, 11, 11, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        self.assertEqual(or_trip["Miles"], "150")
        self.s["save_ifta_trip_record"](or_trip, self.book)

        fuel = self.s["build_ifta_fuel_record"](
            date(2026, 11, 10), "Heli2", "WA", "100", "4.50", "",
            "Shell Ellensburg", True, "", when=when,
        )
        self.assertEqual(fuel["Gallons"], "100.000")
        self.assertEqual(fuel["Price/Gal"], "4.500")
        self.assertEqual(fuel["Total Cost"], "450.00")
        self.assertEqual(fuel["Receipt #"], "Yes")
        self.s["save_ifta_fuel_record"](fuel, self.book)
        or_fuel = self.s["build_ifta_fuel_record"](
            date(2026, 11, 11), "Heli2", "OR", "40", "", "180",
            "Chevron", False, "",
            when=datetime(2026, 11, 11, 10, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        self.assertEqual(or_fuel["Receipt #"], "No")
        self.assertEqual(or_fuel["Price/Gal"], "4.500")
        self.assertEqual(or_fuel["Total Cost"], "180.00")
        self.s["save_ifta_fuel_record"](or_fuel, self.book)

        trips = self.s["load_ifta_trip_records"](self.book, unit_id="Heli2")
        fuel_rows = self.s["load_ifta_fuel_records"](self.book, unit_id="Heli2")
        self.assertEqual(len(trips), 2)
        self.assertEqual(len(fuel_rows), 2)
        summary = self.s["build_ifta_quarterly_summary"](trips, fuel_rows, 2026, 4, unit_id="Heli2")
        self.assertEqual(summary["unit_total_miles"], 600)
        self.assertEqual(summary["unit_total_gallons"], 140)
        self.assertAlmostEqual(summary["unit_mpg"], 600 / 140)
        self.assertEqual(summary["fleet_total_miles"], 600)
        self.assertEqual(summary["fleet_total_gallons"], 140)
        by_code = {row["Jurisdiction"]: row for row in summary["unit_rows"]}
        self.assertEqual(by_code["WA"]["Miles"], 450)
        self.assertEqual(by_code["WA"]["Gallons"], 100)
        self.assertEqual(by_code["OR"]["Miles"], 150)
        self.assertEqual(by_code["OR"]["Gallons"], 40)
        q1 = self.s["build_ifta_quarterly_summary"](trips, fuel_rows, 2026, 1, unit_id="Heli2")
        self.assertEqual(q1["unit_total_miles"], 0)
        self.assertEqual(q1["unit_total_gallons"], 0)

        csv_text = self.s["build_ifta_summary_csv"](summary)
        rows = list(csv.reader(StringIO(csv_text)))
        self.assertEqual(rows[0], ["Year", "Quarter", "Scope", "Unit", "Jurisdiction", "Miles", "Gallons", "MPG"])
        self.assertTrue(any(row[4] == "WA" and row[2] == "Unit" for row in rows[1:]))
        self.assertTrue(any(row[4] == "TOTAL" and row[2] == "Fleet" for row in rows[1:]))
        self.assertEqual(self.s["ifta_summary_pdf_filename"](summary), "CVH_IFTA_Heli2_Q4_2026.pdf")

        pdf = self.s["build_ifta_summary_pdf"](summary, logo_path="/workspace/invoices/logo/flaglogo.png")
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = fitz.open(stream=pdf, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        extracted = "\n".join(page.get_text() for page in doc)
        self.assertIn("IFTA Quarterly Summary", extracted)
        self.assertIn("Central Valley Helicopters", extracted)
        self.assertIn("Heli2", extracted)
        self.assertIn("Washington", extracted)
        self.assertIn("Oregon", extracted)
        self.assertIn("Fleet", extracted)
        self.assertTrue(doc[0].get_images(), "expected the flag logo on the PDF page")
        doc.close()

        self.assertEqual(self.book.sheets["IFTA Trips"].rows[0], self.s["IFTA_TRIPS_COLUMNS"])
        self.assertEqual(self.s["IFTA_RECEIPT_COLUMN"], "Receipt #")
        self.assertEqual(self.s["IFTA_FUEL_COLUMNS"][8], "Receipt #")
        self.assertEqual(self.book.sheets["IFTA Fuel"].rows[0], self.s["IFTA_FUEL_COLUMNS"])
        self.assertEqual(self.book.sheets["IFTA Fuel"].rows[1][self.s["IFTA_FUEL_COLUMNS"].index("Receipt #")], "Yes")
        self.assertEqual(self.book.sheets["IFTA Fuel"].rows[2][self.s["IFTA_FUEL_COLUMNS"].index("Receipt #")], "No")
        for title, (header, rows_before, writes_before) in snapshots.items():
            self.assertEqual(self.book.sheets[title].rows[0], header)
            self.assertEqual(self.book.sheets[title].writes, writes_before)
        self.assertEqual(self.book.sheet1.rows, frat_before)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()



    def test_yearly_items_save_and_readonly_load_leave_headers_alone(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        frat_writes = list(self.book.sheet1.writes)
        self.assertEqual(self.s["load_yearly_item_records_readonly"](self.book), [])
        self.assertNotIn("Yearly Items", self.book.sheets)
        statuses = self.s["yearly_group_statuses"]([], 2026)
        self.assertEqual(statuses["Winterizing"], "expired")
        self.assertEqual(statuses["Fuel Systems"], "expired")
        self.assertEqual(statuses["Annual Policies & Procedures (SMS)"], "expired")
        self.assertEqual(statuses["Training"], "expired")
        self.assertNotIn("Yearly Items", self.book.sheets)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()

        when = datetime(2026, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        record = self.s["build_yearly_item_record"](
            2026, "Training", "Pilot Training - N893PC", date(2026, 9, 12),
            "Ron Cline", "Annual review", when=when,
        )
        self.s["save_yearly_item_record"](record, self.book)
        self.assertIn("Yearly Items", self.book.sheets)
        ws = self.book.sheets["Yearly Items"]
        self.assertEqual(ws.rows[0], self.s["YEARLY_ITEMS_COLUMNS"])
        self.assertEqual(ws.rows[1][ws.rows[0].index("Group")], "Training")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Item")], "Pilot Training - N893PC")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Year")], "2026")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Date Done")], "2026-09-12")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Done By")], "Ron Cline")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Notes")], "Annual review")
        header = list(ws.rows[0])
        writes_after_save = list(ws.writes)
        loaded = self.s["load_yearly_item_records_readonly"](self.book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Item"], "Pilot Training - N893PC")
        self.assertTrue(self.s["yearly_item_is_done"](loaded, 2026, "Training", "Pilot Training - N893PC"))
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(ws.writes, writes_after_save)
        second, created_again = self.s["ensure_yearly_items_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertEqual(second.rows[0], header)
        self.assertNotIn("Equipment", self.book.sheets)
        self.assertNotIn("IFTA Fuel", self.book.sheets)
        self._assert_frat_untouched()

    def test_yearly_items_ensure_does_not_alter_an_existing_custom_header(self):
        ws = self.book.add_worksheet("Yearly Items", 20, 8)
        custom = ["Timestamp", "Year", "Group", "Item", "Date Done", "Done By", "Notes", "Extra"]
        ws.append_row(custom)
        writes = list(ws.writes)
        out, created = self.s["ensure_yearly_items_worksheet"](self.book)
        self.assertFalse(created)
        self.assertIs(out, ws)
        self.assertEqual(ws.rows[0], custom)
        self.assertEqual(ws.writes, writes)
        self._assert_frat_untouched()

    def test_ifta_fuel_have_receipt_does_not_alter_existing_header(self):
        from datetime import date
        header = [
            "Timestamp", "Date", "Unit", "Jurisdiction", "Gallons",
            "Price/Gal", "Total Cost", "Vendor/Location", "Receipt #", "Notes",
        ]
        ws = self.book.add_worksheet("IFTA Fuel", 20, 10)
        ws.append_row(header)
        writes_after_header = list(ws.writes)
        record = self.s["build_ifta_fuel_record"](
            date(2026, 11, 10), "Heli2", "WA", "20", "4", "",
            "Shell", True, "note",
        )
        self.s["save_ifta_fuel_record"](record, self.book)
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(ws.rows[1][header.index("Receipt #")], "Yes")
        # Header cells were not updated after the initial append.
        self.assertFalse(any(w[0] == "update_cell" and w[1] == 1 for w in ws.writes[len(writes_after_header):]))
        loaded = self.s["load_ifta_fuel_records"](self.book, unit_id="Heli2")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Receipt #"], "Yes")
        self.assertEqual(self.s["ifta_have_receipt_display"](loaded[0]["Receipt #"]), "✓")
        self._assert_frat_untouched()

    def test_ifta_ensure_does_not_alter_an_existing_custom_header(self):
        ws = self.book.add_worksheet("IFTA Trips", 20, 8)
        ws.append_row(["Timestamp", "Date", "Custom"])
        writes = list(ws.writes)
        out, created = self.s["ensure_ifta_trips_worksheet"](self.book)
        self.assertFalse(created)
        self.assertIs(out, ws)
        self.assertEqual(ws.rows[0], ["Timestamp", "Date", "Custom"])
        self.assertEqual(ws.writes, writes)
        self._assert_frat_untouched()
        self.assertNotIn("IFTA Fuel", self.book.sheets)
        self.assertNotIn("Equipment", self.book.sheets)

def equipment_offline_app():
    """Same offline FRAT stub, plus an in-memory spreadsheet for Equipment/Squawks."""
    tree = ast.parse(SOURCE)
    stub = r'''
class WorksheetNotFound(Exception):
    pass

class OfflineWorksheet:
    def __init__(self, title="FRAT", rows=None):
        self.title = title
        self.rows = [list(r) for r in (rows or [])]
    def row_values(self, row):
        rows = self.rows if self.title != "FRAT" else st.session_state.get("_test_rows", self.rows)
        return list(rows[row - 1]) if 0 < row <= len(rows) else []
    def append_row(self, row, **kwargs):
        if self.title == "FRAT":
            if "_test_rows" not in st.session_state:
                st.session_state["_test_rows"] = []
            st.session_state["_test_rows"].append(row)
            return
        self.rows.append(list(row))
    def get_all_values(self):
        return [list(r) for r in self.rows]
    def get_all_records(self):
        return []
    def update_cell(self, row, col, value):
        while len(self.rows) < row:
            self.rows.append([])
        current = self.rows[row - 1]
        while len(current) < col:
            current.append("")
        current[col - 1] = value

class OfflineSpreadsheet:
    def __init__(self):
        self.sheets = {"Sheet1": OfflineWorksheet("FRAT")}
    @property
    def sheet1(self):
        return self.sheets["Sheet1"]
    def worksheet(self, title):
        if title not in self.sheets:
            raise WorksheetNotFound("Worksheet not found: " + title)
        return self.sheets[title]
    def add_worksheet(self, title, rows=0, cols=0):
        ws = OfflineWorksheet(title)
        self.sheets[title] = ws
        return ws

def _gsheets_spreadsheet():
    if "_workbook" not in st.session_state:
        st.session_state["_workbook"] = OfflineSpreadsheet()
    return st.session_state["_workbook"]

def _gsheets_worksheet():
    return _gsheets_spreadsheet().sheet1

def frat_sheet_url():
    return "https://docs.google.com/spreadsheets/d/offline-test/edit"
'''
    skip = {"_gsheets_spreadsheet", "_gsheets_worksheet", "frat_sheet_url"}
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in skip)]
    return stub + "\n" + ast.unparse(tree)


class HeaderAndEquipmentPageTests(unittest.TestCase):
    def test_equipment_list_has_one_squawk_button_per_item_and_form(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))
        at.button(key="nav_equipment").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Equipment Squawks" in (t.value or "") for t in at.title))
        squawk_buttons = [b for b in at.button if b.label == "Squawk"]
        info_buttons = [b for b in at.button if b.label == "INFO"]
        self.assertEqual(len(squawk_buttons), 30)
        self.assertEqual(len(info_buttons), 30)
        ifta_buttons = [b for b in at.button if b.label == "IFTA"]
        self.assertEqual(len(ifta_buttons), 1)
        action_labels = [b.label for b in at.button if b.label in {"INFO", "IFTA", "Squawk"}]
        heli2_start = action_labels.index("INFO") + 2  # Heli1 INFO, Heli1 Squawk, then Heli2 INFO
        self.assertEqual(action_labels[0:2], ["INFO", "Squawk"])
        self.assertEqual(action_labels[2:5], ["INFO", "IFTA", "Squawk"])
        self.assertEqual(action_labels[5:7], ["INFO", "Squawk"])
        names = [m.value for m in at.markdown if m.value and m.value.startswith("**") and m.value.endswith("**")]
        official = [
            "Heli1", "Heli2", "Heli3", "Heli4", "F250", "F350", "PW", "Ram", "FS Truck",
            "C8000", "S1", "Boomer", "Inter Fueler", "Bounder", "Bus", "Equinox", "Tesla", "Mercedes", "Sienna",
            "R44 Trailer", "Enstrom Heli Trailer", "Heli Hauler", "Pod", "Dump Trailer",
            "Fuel Trailer", "Bobcat", "Forklift", "Lift", "JD Tractor", "Grasshopper",
        ]
        listed = [n[2:-2] for n in names if n[2:-2] in official]
        self.assertEqual(listed[:30], official)
        self.assertFalse(any((getattr(s, "value", "") or "").startswith("Trucks") for s in at.subheader))
        info_buttons[0].click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value and str(t.value).startswith("Info — Heli1") for t in at.subheader))
        info_md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Registration Expire Date", info_md)
        self.assertIn("Annual Maint Date", info_md)
        self.assertIn("Not set", info_md)
        self.assertNotIn("Tonnage Wt Expire Date", info_md)
        # Heli2 is the second unit and should show the tonnage date field (blank / Not set).
        info_buttons = [b for b in at.button if b.label == "INFO"]
        info_buttons[1].click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value and str(t.value).startswith("Info — Heli2") for t in at.subheader))
        info_md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Tonnage Wt Expire Date", info_md)
        self.assertIn("Not set", info_md)
        squawk_buttons = [b for b in at.button if b.label == "Squawk"]
        squawk_buttons[0].click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value and t.value.startswith("New squawk —") for t in at.subheader))
        at.selectbox(key="Reported by") if False else None
        reporter = next(s for s in at.selectbox if s.label == "Reported by")
        reporter.select("Ronald A Cline")
        category = next(s for s in at.selectbox if s.label == "Category")
        category.select("Mechanical")
        severity = next(s for s in at.selectbox if s.label == "Severity")
        severity.select("Low")
        desc = next(t for t in at.text_area if t.label == "Description")
        desc.set_value("Oil leak at filter housing")
        at.button(key="FormSubmitter:equipment_squawk_form-Save squawk") if False else None
        save = next(b for b in at.button if b.label == "Save squawk")
        save.click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved squawk" in (s.value or "") for s in at.success))
        self.assertTrue(any("1 open squawk" in (w.value or "") for w in at.warning))
        book = at.session_state["_workbook"]
        self.assertEqual(len(book.sheets["Squawks"].rows), 2)
        self.assertEqual(book.sheets["Sheet1"].rows, [])

    def test_header_placeholders_and_frat_still_reachable(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_monthly_safety").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Monthly Safety Meeting" for t in at.title))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        self.assertTrue(any(d.label == "Meeting Date" for d in at.date_input))
        self.assertTrue(any(b.label == "Save meeting" for b in at.button))
        at.button(key="nav_yearly_items").click().run()
        self.assertTrue(any(t.value == "Yearly Items" for t in at.title))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        labels = [b.label for b in at.button]
        self.assertIn("Winterizing", labels)
        self.assertIn("Fuel Systems", labels)
        self.assertIn("Annual Policies & Procedures (SMS)", labels)
        self.assertIn("Training", labels)
        self.assertLess(labels.index("Winterizing"), labels.index("Fuel Systems"))
        self.assertLess(labels.index("Fuel Systems"), labels.index("Annual Policies & Procedures (SMS)"))
        self.assertLess(labels.index("Annual Policies & Procedures (SMS)"), labels.index("Training"))
        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertNotIn("Yearly Items", book.sheets)
        at.button(key="nav_dom").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "DOM" for t in at.title))
        self.assertEqual(
            [m.value for m in at.markdown if m.value in ("**N893PC**", "**N480ML**")],
            ["**N893PC**", "**N480ML**"],
        )
        annual = [b for b in at.button if (b.label or "").startswith("Annual/100 Hr")]
        self.assertEqual(len(annual), 2)
        self.assertTrue(all((b.label or "").endswith("No data") for b in annual))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        # Existing FRAT path remains one tap away.
        next(b for b in at.button if b.label == "🛩️ Pilot").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))
        frat_visible = any("FRAT" in (getattr(x, "value", None) or getattr(x, "label", None) or "") for x in list(at.tabs) + list(at.subheader) + list(at.title))
        self.assertTrue(frat_visible)

    def test_monthly_safety_meeting_form_saves_and_edits_notes_on_fake_sheet(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_monthly_safety").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Monthly Safety Meeting" for t in at.title))
        self.assertTrue(any(d.label == "Meeting Date" for d in at.date_input))
        self.assertTrue(any("Recorded By" in (s.label or "") for s in at.selectbox))
        self.assertFalse(any(t.label == "Attendees (optional)" for t in at.text_input))
        attendee_labels = [c.label for c in at.checkbox if c.label != "Done / Reviewed"]
        self.assertEqual(attendee_labels, [
            "Ron Cline",
            "Anthony Root",
            "Carl Mulvaney",
            "Barry Markham",
            "Gary Grant",
            "Robert Rackley",
            "Skylar Fingerle",
        ])
        self.assertTrue(any(t.label == "Other attendees (optional)" for t in at.text_input))
        names = " ".join(m.value or "" for m in at.markdown)
        for item in (
            "Aircraft Fire Extinguishers",
            "Review Equipment",
            "Review Employee Licenses / Certificates",
            "First Aid Kits",
            "PPE",
        ):
            self.assertIn(item, names)
        self.assertEqual(sum(1 for c in at.checkbox if c.label == "Done / Reviewed"), 5)
        self.assertTrue(any(t.label == "Discussion notes for this meeting" for t in at.text_area))
        radios = list(at.radio)
        self.assertTrue(radios, "expected View / Record radio")
        radios[0].set_value("View meetings").run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("No meetings recorded yet." in (i.value or "") for i in at.info))
        next(r for r in at.radio).set_value("Record a meeting").run()
        self.assertFalse(list(at.exception))

        next(d for d in at.date_input if d.label == "Meeting Date").set_value(date(2026, 11, 10))
        next(s for s in at.selectbox if "Recorded By" in (s.label or "")).select("Ronald A Cline")
        next(c for c in at.checkbox if c.label == "Ron Cline").check()
        next(c for c in at.checkbox if c.label == "Carl Mulvaney").check()
        next(t for t in at.text_input if t.label == "Other attendees (optional)").set_value("Guest Pilot")
        next(c for c in at.checkbox if c.label == "Done / Reviewed").check()
        notes = [t for t in at.text_input if t.label == "Note (optional)"]
        notes[0].set_value("Cabin bottle OK")
        next(t for t in at.text_area if t.label == "Discussion notes for this meeting").set_value("Talked about winter ops.")
        next(b for b in at.button if b.label == "Save meeting").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved safety meeting for 2026-11-10" in (s.value or "") for s in at.success))
        self.assertFalse(list(at.expander))
        self.assertTrue(any(s.label == "Year" for s in at.selectbox))
        self.assertTrue(any(s.label == "Month" for s in at.selectbox))
        self.assertTrue(any(s.label == "Meeting" for s in at.selectbox))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("**Meeting Date:** 2026-11-10", md)
        self.assertIn("**Recorded By:** Ronald A Cline", md)
        self.assertIn("**Aircraft Fire Extinguishers:** Done / Reviewed — Cabin bottle OK", md)
        self.assertIn("**Review Equipment:** Not reviewed", md)
        self.assertIn("**Review Employee Licenses / Certificates:** Not reviewed", md)
        self.assertIn("**First Aid Kits:** Not reviewed", md)
        self.assertIn("**PPE:** Not reviewed", md)
        self.assertIn("✓ Ron Cline", md)
        self.assertIn("✓ Carl Mulvaney", md)
        self.assertIn("**Other attendees:** Guest Pilot", md)
        self.assertTrue(any(b.label == "Download PDF" for b in list(at.button) + list(at.download_button)))
        book = at.session_state["_workbook"]
        self.assertIn("Safety Meetings", book.sheets)
        rows = book.sheets["Safety Meetings"].rows
        self.assertEqual(len(rows), 2)  # header + one meeting
        header = rows[0]
        data = rows[1]
        self.assertEqual(data[header.index("Meeting Date")], "2026-11-10")
        self.assertEqual(data[header.index("Recorded By")], "Ronald A Cline")
        self.assertEqual(data[header.index("Attendees")], "Ron Cline, Carl Mulvaney, Guest Pilot")
        self.assertEqual(data[header.index("Aircraft Fire Extinguishers Done")], "Yes")
        self.assertEqual(data[header.index("Aircraft Fire Extinguishers Note")], "Cabin bottle OK")
        self.assertEqual(data[header.index("Discussion Notes")], "Talked about winter ops.")
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertNotIn("Equipment", book.sheets)
        self.assertNotIn("Squawks", book.sheets)
        self.assertEqual(set(book.sheets), {"Sheet1", "Safety Meetings"})

        disc = next(t for t in at.text_area if t.label == "Discussion Notes")
        disc.set_value("Talked about winter ops. Added follow-up.")
        next(b for b in at.button if b.label == "Save discussion notes").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Updated discussion notes" in (s.value or "") for s in at.success))
        data = book.sheets["Safety Meetings"].rows[1]
        self.assertEqual(data[header.index("Discussion Notes")], "Talked about winter ops. Added follow-up.")
        self.assertEqual(data[header.index("Aircraft Fire Extinguishers Done")], "Yes")
        self.assertEqual(len(book.sheets["Safety Meetings"].rows), 2)


    def test_safety_meeting_viewer_filters_month_and_keeps_headers(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_monthly_safety").click().run()
        self.assertFalse(list(at.exception))
        next(d for d in at.date_input if d.label == "Meeting Date").set_value(date(2026, 10, 15))
        next(s for s in at.selectbox if "Recorded By" in (s.label or "")).select("Anthony Root")
        next(c for c in at.checkbox if c.label == "Ron Cline").check()
        next(t for t in at.text_area if t.label == "Discussion notes for this meeting").set_value("October notes.")
        next(b for b in at.button if b.label == "Save meeting").click().run()
        self.assertFalse(list(at.exception))
        next(r for r in at.radio).set_value("Record a meeting").run()
        next(d for d in at.date_input if d.label == "Meeting Date").set_value(date(2026, 11, 10))
        next(s for s in at.selectbox if "Recorded By" in (s.label or "")).select("Ronald A Cline")
        next(c for c in at.checkbox if c.label == "Carl Mulvaney").check()
        next(t for t in at.text_input if t.label == "Other attendees (optional)").set_value("Guest Pilot")
        next(t for t in at.text_area if t.label == "Discussion notes for this meeting").set_value("November notes.")
        next(b for b in at.button if b.label == "Save meeting").click().run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("**Meeting Date:** 2026-11-10", md)
        self.assertIn("November notes.", " ".join(t.value or "" for t in at.text_area))
        month = next(s for s in at.selectbox if s.label == "Month")
        month.select(10).run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("**Meeting Date:** 2026-10-15", md)
        self.assertIn("**Recorded By:** Anthony Root", md)
        self.assertIn("October notes.", " ".join(t.value or "" for t in at.text_area))
        self.assertIn("✓ Ron Cline", md)
        self.assertNotIn("2026-11-10", md)
        book = at.session_state["_workbook"]
        header = book.sheets["Safety Meetings"].rows[0]
        self.assertEqual(header[0:4], ["Timestamp", "Meeting Date", "Recorded By", "Attendees"])
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertNotIn("Equipment", book.sheets)
        self.assertNotIn("Squawks", book.sheets)
        self.assertNotIn("Aircraft Maint", book.sheets)



    def test_monthly_safety_header_and_month_strip_colors(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(".st-key-nav_monthly_safety", md)
        self.assertIn("#b91c1c", md)
        self.assertNotIn("background-color:#15803d", md.replace(" ", ""))

        at.button(key="nav_monthly_safety").click().run()
        self.assertFalse(list(at.exception))
        next(r for r in at.radio).set_value("View meetings").run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("No meetings recorded yet." in (i.value or "") for i in at.info))
        self.assertTrue(any("Green = meeting recorded. Red = no meeting yet. Gray = future month." in (c.value or "") for c in at.caption))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("safety-month-strip", md)
        for label in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"):
            self.assertIn(label, md)
        self.assertIn("#b91c1c", md)
        self.assertIn("#6b7280", md)
        self.assertNotIn("#15803d", md)
        self.assertIn(".st-key-nav_monthly_safety", md)
        self.assertIn("#b91c1c", md)

        next(r for r in at.radio).set_value("Record a meeting").run()
        self.assertFalse(list(at.exception))
        next(d for d in at.date_input if d.label == "Meeting Date").set_value(date(2026, 3, 12))
        next(s for s in at.selectbox if "Recorded By" in (s.label or "")).select("Ronald A Cline")
        next(c for c in at.checkbox if c.label == "Ron Cline").check()
        next(t for t in at.text_area if t.label == "Discussion notes for this meeting").set_value("March notes.")
        next(b for b in at.button if b.label == "Save meeting").click().run()
        self.assertFalse(list(at.exception))

        # March meeting is not the current Pacific month, so the header stays red.
        md = " ".join((m.value or "").replace(" ", "") for m in at.markdown)
        self.assertIn("background-color:#b91c1c", md)
        self.assertNotIn("background-color:#15803d", md)
        strip = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("safety-month-strip", strip)
        self.assertIn("#15803d", strip)
        self.assertIn("#b91c1c", strip)
        self.assertIn("#6b7280", strip)

        next(r for r in at.radio).set_value("Record a meeting").run()
        next(d for d in at.date_input if d.label == "Meeting Date").set_value(date(2026, 11, 10))
        next(s for s in at.selectbox if "Recorded By" in (s.label or "")).select("Ronald A Cline")
        next(c for c in at.checkbox if c.label == "Carl Mulvaney").check()
        next(t for t in at.text_area if t.label == "Discussion notes for this meeting").set_value("November notes.")
        next(b for b in at.button if b.label == "Save meeting").click().run()
        self.assertFalse(list(at.exception))
        md_compact = " ".join((m.value or "").replace(" ", "") for m in at.markdown)
        self.assertIn("background-color:#15803d", md_compact)
        self.assertIn(".st-key-nav_monthly_safety", " ".join(m.value or "" for m in at.markdown))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("safety-month-strip", md)
        for label in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"):
            self.assertIn(label, md)
        self.assertGreaterEqual(md.count("#15803d"), 2)
        self.assertIn("#b91c1c", md)
        self.assertIn("#6b7280", md)
        self.assertTrue(any(s.label == "Year" for s in at.selectbox))
        self.assertNotIn("Equipment", at.session_state["_workbook"].sheets)
        self.assertEqual(at.session_state["_workbook"].sheets["Sheet1"].rows, [])

    def test_heli2_ifta_page_saves_trip_and_fuel_and_shows_summary(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_equipment").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(len([b for b in at.button if b.label == "IFTA"]), 1)
        at.button(key="ifta_btn_Heli2").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "IFTA" for t in at.title))
        self.assertTrue(any(t.value == "Heli2" for t in at.subheader))
        self.assertTrue(any(b.label == "Back" for b in at.button))
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertTrue(any(s.label == "Driver" for s in at.selectbox))
        driver = next(s for s in at.selectbox if s.label == "Driver")
        self.assertEqual(list(driver.options), [
            "Robert Rackley",
            "Barry Markham",
            "Anthony Root",
            "Carl Mulvaney",
            "Ron Cline",
            "Gary Grant",
        ])
        self.assertTrue(any(s.label == "Jurisdiction" for s in at.selectbox))
        labels = [t.label for t in at.text_input]
        self.assertIn("Start Odometer", labels)
        self.assertIn("End Odometer", labels)
        self.assertNotIn("Gallons", labels)
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 10))
        next(s for s in at.selectbox if s.label == "Driver").select("Anthony Root")
        jur = next(s for s in at.selectbox if s.label == "Jurisdiction")
        self.assertTrue(str(jur.value).startswith("WA"))
        next(t for t in at.text_input if t.label == "Start Odometer").set_value("10000")
        next(t for t in at.text_input if t.label == "End Odometer").set_value("10450")
        at.run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("**Miles:** 450", md)
        next(t for t in at.text_input if t.label == "Notes").set_value("Ellensburg to Yakima")
        next(b for b in at.button if b.label == "Save trip").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved IFTA trip for Heli2" in (s.value or "") for s in at.success))
        book = at.session_state["_workbook"]
        self.assertIn("IFTA Trips", book.sheets)
        self.assertIn("IFTA Fuel", book.sheets)
        self.assertEqual(len(book.sheets["IFTA Fuel"].rows), 1)  # header only until a fuel save
        trip_header = book.sheets["IFTA Trips"].rows[0]
        trip = book.sheets["IFTA Trips"].rows[1]
        self.assertEqual(trip[trip_header.index("Unit")], "Heli2")
        self.assertEqual(trip[trip_header.index("Date")], "2026-11-10")
        self.assertEqual(trip[trip_header.index("Driver")], "Anthony Root")
        self.assertEqual(trip[trip_header.index("Jurisdiction")], "WA")
        self.assertEqual(trip[trip_header.index("Miles")], "450")
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertNotIn("Safety Meetings", book.sheets)
        self.assertNotIn("Aircraft Maint", book.sheets)

        next(r for r in at.radio).set_value("Fuel purchase log").run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.label == "Gallons" for t in at.text_input))
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 10))
        next(t for t in at.text_input if t.label == "Gallons").set_value("100")
        next(t for t in at.text_input if t.label == "Price/Gal").set_value("4.50")
        at.run()
        labels = [t.label for t in at.text_input]
        self.assertIn("Vendor/Location", labels)
        self.assertNotIn("Receipt #", labels)
        self.assertTrue(any(c.label == "Have receipt" for c in at.checkbox))
        next(t for t in at.text_input if t.label == "Vendor/Location").set_value("Shell Ellensburg")
        next(c for c in at.checkbox if c.label == "Have receipt").check()
        next(b for b in at.button if b.label == "Save fuel purchase").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved IFTA fuel purchase for Heli2" in (s.value or "") for s in at.success))
        fuel_header = book.sheets["IFTA Fuel"].rows[0]
        self.assertEqual(fuel_header, [
            "Timestamp", "Date", "Unit", "Jurisdiction", "Gallons",
            "Price/Gal", "Total Cost", "Vendor/Location", "Receipt #", "Notes",
        ])
        fuel = book.sheets["IFTA Fuel"].rows[1]
        self.assertEqual(fuel[fuel_header.index("Unit")], "Heli2")
        self.assertEqual(fuel[fuel_header.index("Gallons")], "100.000")
        self.assertEqual(fuel[fuel_header.index("Price/Gal")], "4.500")
        self.assertEqual(fuel[fuel_header.index("Total Cost")], "450.00")
        self.assertEqual(fuel[fuel_header.index("Vendor/Location")], "Shell Ellensburg")
        self.assertEqual(fuel[fuel_header.index("Receipt #")], "Yes")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("**Have receipt:** ✓", md)
        self.assertNotIn("Receipt #", md)
        self.assertEqual(book.sheets["Sheet1"].rows, [])

        next(r for r in at.radio).set_value("Quarterly summary").run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("WA — Washington", md)
        self.assertIn("450.0 mi", md)
        self.assertIn("100.000 gal", md)
        self.assertIn("Fleet total", md)
        self.assertTrue(any(b.label == "Download CSV" for b in list(at.button) + list(at.download_button)))
        self.assertTrue(any(b.label == "Download PDF" for b in list(at.button) + list(at.download_button)))
        # Opening IFTA must not change Equipment or Squawks headers.
        if "Equipment" in book.sheets:
            self.assertEqual(book.sheets["Equipment"].rows[0][0:4], ["Unit ID", "Name", "Type", "Active"])
        if "Squawks" in book.sheets:
            self.assertEqual(book.sheets["Squawks"].rows[0][0], "Timestamp")



    def test_yearly_items_page_buttons_colors_and_saves_on_fake_sheet(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_yearly_items").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Yearly Items" for t in at.title))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        self.assertTrue(any(s.label == "Year" for s in at.selectbox))
        self.assertTrue(any(t.value == "History" for t in at.subheader))
        self.assertTrue(any("No yearly items recorded for 2026." in (i.value or "") for i in at.info))
        for label in (
            "Winterizing",
            "Fuel Systems",
            "Annual Policies & Procedures (SMS)",
            "Training",
        ):
            self.assertTrue(any(b.label == label for b in at.button), label)
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(".st-key-yearly_group_Winterizing", md)
        self.assertIn(".st-key-yearly_group_Fuel_Systems", md)
        self.assertIn(".st-key-yearly_group_Annual_Policies_Procedures_SMS", md)
        self.assertIn(".st-key-yearly_group_Training", md)
        compact = md.replace(" ", "")
        self.assertIn("background-color:#b91c1c", compact)
        book = at.session_state["_workbook"]
        self.assertNotIn("Yearly Items", book.sheets)
        self.assertEqual(book.sheets["Sheet1"].rows, [])

        at.button(key="yearly_group_Fuel_Systems").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Fuel Systems" for t in at.subheader))
        self.assertTrue(any(b.label == "Back" for b in at.button))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Tanks", md)
        self.assertIn("Not done yet", md)
        self.assertIn("#b91c1c", md)
        next(s for s in at.selectbox if s.label == "Done By").select("Gary Grant")
        next(d for d in at.date_input if d.label == "Date Done").set_value(date(2026, 11, 1))
        notes = [t for t in at.text_input if t.label == "Notes (optional)"]
        if notes:
            notes[0].set_value("Fall service")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved Tanks for 2026." in (s.value or "") for s in at.success))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("#15803d", md)
        self.assertIn("2026-11-01", md)
        self.assertIn("Gary Grant", md)
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))
        compact = " ".join((m.value or "").replace(" ", "") for m in at.markdown)
        self.assertIn("background-color:#15803d", compact)
        self.assertIn("background-color:#b91c1c", compact)
        hist = " ".join(m.value or "" for m in at.markdown) + " " + " ".join(i.value or "" for i in at.info)
        # History should list Tanks
        self.assertIn("Tanks", " ".join(m.value or "" for m in at.markdown))
        self.assertIn("Gary Grant", " ".join(m.value or "" for m in at.markdown))

        at.button(key="yearly_group_Annual_Policies_Procedures_SMS").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Annual Policies & Procedures (SMS)" for t in at.subheader))
        sms_md = " ".join(m.value or "" for m in at.markdown)
        self.assertTrue("Annual SMS policies" in sms_md and "procedures review" in sms_md)
        next(s for s in at.selectbox if s.label == "Done By").select("Ron Cline")
        next(d for d in at.date_input if d.label == "Date Done").set_value(date(2026, 10, 20))
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))

        at.button(key="yearly_group_Training").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Training" for t in at.subheader))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("WPS Mixer/Loader", md)
        self.assertIn("**Pilot Training**", md)
        self.assertIn("N480ML", md)
        self.assertIn("N893PC", md)
        # Fill the N480ML form (second Done By after WPS).
        by_boxes = [s for s in at.selectbox if s.label == "Done By"]
        self.assertEqual(len(by_boxes), 3)
        by_boxes[1].select("Anthony Root")
        date_boxes = [d for d in at.date_input if d.label == "Date Done"]
        date_boxes[1].set_value(date(2026, 9, 1))
        save_btns = [b for b in at.button if b.label == "Save"]
        self.assertEqual(len(save_btns), 3)
        save_btns[1].click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved Pilot Training - N480ML for 2026." in (s.value or "") for s in at.success))
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))

        at.button(key="yearly_group_Winterizing").click().run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        for item in ("Office irrigation system", "Trucks", "Rinse Pad", "Pod", "Heli hauler", "Bounder"):
            self.assertIn(item, md)
        by_boxes = [s for s in at.selectbox if s.label == "Done By"]
        self.assertEqual(len(by_boxes), 6)
        by_boxes[1].select("Ron Cline")
        date_boxes = [d for d in at.date_input if d.label == "Date Done"]
        date_boxes[1].set_value(date(2026, 10, 15))
        note_boxes = [t for t in at.text_input if t.label == "Notes (optional)"]
        note_boxes[1].set_value("Antifreeze added")
        [b for b in at.button if b.label == "Save"][1].click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved Trucks for 2026." in (s.value or "") for s in at.success))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("2026-10-15", md)
        self.assertIn("Ron Cline", md)
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))

        # Winterizing and Training still incomplete (red); Fuel Systems and SMS complete (green).
        compact = " ".join((m.value or "").replace(" ", "") for m in at.markdown)
        self.assertIn("background-color:#15803d", compact)
        self.assertIn("background-color:#b91c1c", compact)
        history = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Trucks", history)
        self.assertIn("Tanks", history)
        self.assertIn("Pilot Training", history)
        self.assertIn("N480ML", history)
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))

        rows = book.sheets["Yearly Items"].rows
        header = rows[0]
        self.assertEqual(header, [
            "Timestamp", "Year", "Group", "Item", "Date Done", "Done By", "Notes",
        ])
        items = {row[header.index("Item")]: row for row in rows[1:]}
        self.assertEqual(items["Tanks"][header.index("Group")], "Fuel Systems")
        self.assertEqual(items["Tanks"][header.index("Done By")], "Gary Grant")
        self.assertEqual(items["Annual SMS policies & procedures review"][header.index("Group")], "Annual Policies & Procedures (SMS)")
        self.assertEqual(items["Pilot Training - N480ML"][header.index("Group")], "Training")
        self.assertEqual(items["Pilot Training - N480ML"][header.index("Done By")], "Anthony Root")
        self.assertEqual(items["Trucks"][header.index("Notes")], "Antifreeze added")
        self.assertEqual(len(rows), 5)  # header + 4 saves
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertNotIn("Equipment", book.sheets)
        self.assertNotIn("Safety Meetings", book.sheets)
        self.assertEqual(set(book.sheets), {"Sheet1", "Yearly Items"})

    def test_dom_annual_buttons_color_by_saved_status(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_dom").click().run()
        self.assertFalse(list(at.exception))
        n893 = at.button(key="dom_annual_N893PC")
        n480 = at.button(key="dom_annual_N480ML")
        self.assertEqual(n893.label, "Annual/100 Hr — No data")
        self.assertEqual(n480.label, "Annual/100 Hr — No data")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(".st-key-dom_annual_N893PC", md)
        self.assertIn(".st-key-dom_annual_N480ML", md)
        compact = md.replace(" ", "")
        self.assertIn("background-color:#6b7280", compact)
        self.assertNotIn("Aircraft Maint", at.session_state["_workbook"].sheets)
        self.assertNotIn("N480ML Maint", at.session_state["_workbook"].sheets)
        self.assertEqual(at.session_state["_workbook"].sheets["Sheet1"].rows, [])

        n893.click().run()
        self.assertFalse(list(at.exception))
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1190")
        next(t for t in at.text_input if t.label == "Last 100 Hr (Hobbs)").set_value("1105")
        next(t for t in at.text_input if t.label == "Last Oil Change (Hobbs)").set_value("1160")
        next(d for d in at.date_input if d.label == "Annual Due Date").set_value(date(2027, 3, 1))
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.button(key="dom_annual_N893PC").label, "Annual/100 Hr")
        self.assertEqual(at.button(key="dom_annual_N480ML").label, "Annual/100 Hr — No data")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn(".st-key-dom_annual_N893PC", md)
        self.assertIn("#15803d", md)
        self.assertIn(".st-key-dom_annual_N480ML", md)
        self.assertIn("#6b7280", md)

        at.button(key="dom_annual_N480ML").click().run()
        self.assertFalse(list(at.exception))
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1025")
        next(t for t in at.text_input if t.label == "Last 100 Hr Hobbs").set_value("1000")
        next(t for t in at.text_input if t.label == "Grease Hobbs").set_value("1000")
        at.run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("1025", md)
        self.assertIn(" — due", md)
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.button(key="dom_annual_N893PC").label, "Annual/100 Hr")
        self.assertEqual(at.button(key="dom_annual_N480ML").label, "Annual/100 Hr")
        md = " ".join(m.value or "" for m in at.markdown)
        compact = md.replace(" ", "")
        self.assertIn("background-color:#15803d", compact)
        self.assertIn("background-color:#b91c1c", compact)
        self.assertIn(".st-key-dom_annual_N893PC", md)
        self.assertIn(".st-key-dom_annual_N480ML", md)
        self.assertIn("Aircraft Maint", at.session_state["_workbook"].sheets)
        self.assertIn("N480ML Maint", at.session_state["_workbook"].sheets)
        self.assertEqual(at.session_state["_workbook"].sheets["Sheet1"].rows, [])

        # Amber: 100 Hr within 10 hours on N893PC, grease within 2 hours on a new N480ML cycle.
        at.button(key="dom_annual_N893PC").click().run()
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1198")
        next(t for t in at.text_input if t.label == "Last 100 Hr (Hobbs)").set_value("1105")
        next(t for t in at.text_input if t.label == "Last Oil Change (Hobbs)").set_value("1160")
        next(d for d in at.date_input if d.label == "Annual Due Date").set_value(date(2027, 3, 1))
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.button(key="dom_annual_N893PC").label, "Annual/100 Hr")
        compact = " ".join((m.value or "").replace(" ", "") for m in at.markdown)
        self.assertIn("background-color:#b45309", compact)
        self.assertIn("background-color:#b91c1c", compact)

    def test_dom_annual_n893pc_form_and_n480ml_placeholder(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_dom").click().run()
        self.assertFalse(list(at.exception))
        annual = [b for b in at.button if (b.label or "").startswith("Annual/100 Hr")]
        self.assertEqual(len(annual), 2)
        self.assertTrue(all((b.label or "").endswith("No data") for b in annual))
        at.button(key="dom_annual_N893PC").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "DOM" for t in at.title))
        self.assertTrue(any(t.value == "Annual/100 Hr — N893PC" for t in at.subheader))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        labels = [t.label for t in at.text_input]
        self.assertIn("Current Hobbs", labels)
        self.assertIn("Last 100 Hr (Hobbs)", labels)
        self.assertIn("Last Oil Change (Hobbs)", labels)
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertTrue(any(d.label == "Annual Due Date" for d in at.date_input))
        self.assertTrue(any(s.label == "Entered By" for s in at.selectbox))
        self.assertTrue(any(b.label == "Save" for b in at.button))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Next 100 Hr", md)
        self.assertIn("Next Oil Change", md)
        next(b for b in at.button if b.label == "Back").click().run()
        self.assertFalse(list(at.exception))
        annual = [b for b in at.button if (b.label or "").startswith("Annual/100 Hr")]
        self.assertEqual(len(annual), 2)
        self.assertTrue(all((b.label or "").endswith("No data") for b in annual))
        at.button(key="dom_annual_N480ML").click().run()
        self.assertTrue(any(t.value == "Annual/100 Hr — N480ML" for t in at.subheader))
        self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        n480_labels = [t.label for t in at.text_input]
        self.assertIn("Current Hobbs", n480_labels)
        self.assertIn("Last 100 Hr Hobbs", n480_labels)
        self.assertIn("Grease Hobbs", n480_labels)
        self.assertNotIn("Last Oil Change (Hobbs)", n480_labels)
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertFalse(any(d.label == "Annual Due Date" for d in at.date_input))
        self.assertTrue(any(s.label == "Entered By" for s in at.selectbox))
        self.assertTrue(any(b.label == "Save" for b in at.button))
        n480_md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Next 100 Hr", n480_md)
        self.assertIn("25 Hr", n480_md)
        self.assertIn("50 Hr", n480_md)
        self.assertIn("75 Hr", n480_md)
        self.assertIn("100 Hr", n480_md)
        self.assertNotIn("Last Oil Change", n480_md)
        self.assertNotIn("Next Oil Change", n480_md)
        self.assertNotIn("Annual Due Date", n480_md)
        blob = " ".join(str(getattr(x, "value", "") or getattr(x, "label", "") or "") for x in list(at.markdown) + list(at.text_input) + list(at.number_input) + list(at.selectbox))
        self.assertNotIn("Tach", blob)

    def test_n893pc_annual_form_saves_on_fake_sheet_and_recalculates_next(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_dom").click().run()
        at.button(key="dom_annual_N893PC").click().run()
        self.assertFalse(list(at.exception))
        next(t for t in at.text_input if t.label == "Last 100 Hr (Hobbs)").set_value("1105")
        next(t for t in at.text_input if t.label == "Last Oil Change (Hobbs)").set_value("1160")
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1190")
        at.run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("1205", md)
        self.assertIn("1210", md)
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 10))
        next(d for d in at.date_input if d.label == "Annual Due Date").set_value(date(2027, 3, 1))
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved Annual/100 Hr entry for N893PC" in (s.value or "") for s in at.success))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("1205", md)
        self.assertIn("1210", md)
        self.assertIn("2027-03-01", md)
        book = at.session_state["_workbook"]
        self.assertIn("Aircraft Maint", book.sheets)
        rows = book.sheets["Aircraft Maint"].rows
        self.assertEqual(len(rows), 2)
        header = rows[0]
        data = rows[1]
        self.assertEqual(header, [
            "Timestamp", "Aircraft", "Entry Date", "Hobbs",
            "Last 100 Hr", "Next 100 Hr", "Annual Due Date",
            "Last Oil Change", "Next Oil Change", "Entered By",
        ])
        self.assertEqual(data[header.index("Aircraft")], "N893PC")
        self.assertEqual(data[header.index("Entry Date")], "2026-11-10")
        self.assertEqual(data[header.index("Hobbs")], "1190")
        self.assertEqual(data[header.index("Last 100 Hr")], "1105")
        self.assertEqual(data[header.index("Next 100 Hr")], "1205")
        self.assertEqual(data[header.index("Annual Due Date")], "2027-03-01")
        self.assertEqual(data[header.index("Last Oil Change")], "1160")
        self.assertEqual(data[header.index("Next Oil Change")], "1210")
        self.assertEqual(data[header.index("Entered By")], "Ronald A Cline")
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertNotIn("Equipment", book.sheets)
        self.assertNotIn("Squawks", book.sheets)
        self.assertNotIn("Safety Meetings", book.sheets)
        self.assertNotIn("N480ML Maint", book.sheets)
        self.assertTrue(any(e.label and "Hobbs 1190" in e.label for e in at.expander))


    def test_n480ml_annual_form_saves_marks_checkpoint_and_starts_new_cycle(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_dom").click().run()
        at.button(key="dom_annual_N480ML").click().run()
        self.assertFalse(list(at.exception))
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1020")
        next(t for t in at.text_input if t.label == "Last 100 Hr Hobbs").set_value("1000")
        next(t for t in at.text_input if t.label == "Grease Hobbs").set_value("1000")
        at.run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("1100", md)
        self.assertIn("1025", md)
        self.assertIn("1050", md)
        self.assertIn("1075", md)
        # 1020 vs grease due 1025 is 5 hours out, so still green under the 2-hour window.
        self.assertNotIn("within 10 hours", md)
        self.assertNotIn("within 2 hours", md)
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 10))
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved Annual/100 Hr entry for N480ML" in (s.value or "") for s in at.success))
        book = at.session_state["_workbook"]
        self.assertIn("N480ML Maint", book.sheets)
        self.assertNotIn("Aircraft Maint", book.sheets)
        self.assertNotIn("Safety Meetings", book.sheets)
        rows = book.sheets["N480ML Maint"].rows
        self.assertEqual(len(rows), 2)
        header = rows[0]
        data = rows[1]
        self.assertEqual(data[header.index("Aircraft")], "N480ML")
        self.assertEqual(data[header.index("Entry Date")], "2026-11-10")
        self.assertEqual(data[header.index("Hobbs")], "1020")
        self.assertEqual(data[header.index("Last 100 Hr")], "1000")
        self.assertEqual(data[header.index("Next 100 Hr")], "1100")
        self.assertEqual(data[header.index("Grease Hobbs")], "1000")
        self.assertEqual(data[header.index("Grease 25 Done")], "")
        self.assertEqual(data[header.index("Entered By")], "Ronald A Cline")
        at.checkbox(key="n480_latest_greased_25_N480ML").check()
        at.text_input(key="n480_latest_initials_25_N480ML").set_value("RC")
        next(b for b in at.button if b.label == "Save grease checks").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved grease checks for N480ML" in (s.value or "") for s in at.success))
        rows = book.sheets["N480ML Maint"].rows
        self.assertEqual(len(rows), 2)
        data = rows[1]
        self.assertEqual(data[header.index("Grease 25 Done")], "Yes")
        self.assertEqual(data[header.index("Grease 25 Initials")], "RC")
        self.assertIn("1020 / ", data[header.index("Grease 25 Hobbs/Date")])
        self.assertEqual(data[header.index("Grease 50 Done")], "")
        self.assertEqual(data[header.index("Hobbs")], "1020")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("✓ Done", md)
        self.assertIn("RC", md)
        next(t for t in at.text_input if t.label == "Current Hobbs").set_value("1200")
        next(t for t in at.text_input if t.label == "Last 100 Hr Hobbs").set_value("1100")
        next(t for t in at.text_input if t.label == "Grease Hobbs").set_value("1200")
        at.run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("1225", md)
        self.assertIn("1250", md)
        self.assertIn("1275", md)
        self.assertIn("1300", md)
        next(s for s in at.selectbox if s.label == "Entered By").select("Ronald A Cline")
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        rows = book.sheets["N480ML Maint"].rows
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], header)
        self.assertEqual(rows[1][header.index("Grease 25 Done")], "Yes")
        self.assertEqual(rows[1][header.index("Grease 25 Initials")], "RC")
        self.assertEqual(rows[2][header.index("Grease Hobbs")], "1200")
        self.assertEqual(rows[2][header.index("Next 100 Hr")], "1200")
        self.assertEqual(rows[2][header.index("Grease 25 Done")], "")
        self.assertEqual(rows[2][header.index("Grease 50 Done")], "")
        self.assertNotIn("Aircraft Maint", book.sheets)
        self.assertEqual(book.sheets["Sheet1"].rows, [])

    def test_info_edit_form_is_phone_friendly_and_saves_on_fake_sheet(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_equipment").click().run()
        self.assertFalse(list(at.exception))
        info_buttons = [b for b in at.button if b.label == "INFO"]
        info_buttons[0].click().run()
        self.assertTrue(any(t.value and str(t.value).startswith("Info — Heli1") for t in at.subheader))
        next(b for b in at.button if b.label == "Edit").click().run()
        self.assertFalse(list(at.exception))
        text_labels = [t.label for t in at.text_input]
        self.assertNotIn("Unit ID", text_labels)
        self.assertNotIn("Name", text_labels)
        for expected in ("Year", "Make/Model", "VIN/Serial", "Plate/N-number"):
            self.assertIn(expected, text_labels)
        self.assertTrue(any(t.label == "Notes" for t in at.text_area))
        date_labels = [d.label for d in at.date_input]
        self.assertIn("Registration Expire Date", date_labels)
        self.assertIn("Annual Maint Date", date_labels)
        self.assertNotIn("Tonnage Wt Expire Date", date_labels)
        select_labels = [s.label for s in at.selectbox]
        self.assertIn("Type", select_labels)
        self.assertIn("Active", select_labels)
        self.assertIn("Tonnage Applies", select_labels)
        self.assertTrue(any(b.label == "Save" for b in at.button))
        self.assertTrue(any(b.label == "Cancel" for b in at.button))
        next(b for b in at.button if b.label == "Cancel").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value and str(t.value).startswith("Info — Heli1") for t in at.subheader))
        self.assertTrue(any(b.label == "Edit" for b in at.button))
        self.assertFalse(any(b.label == "Save" for b in at.button))

        info_buttons = [b for b in at.button if b.label == "INFO"]
        info_buttons[1].click().run()
        next(b for b in at.button if b.label == "Edit").click().run()
        self.assertFalse(list(at.exception))
        date_labels = [d.label for d in at.date_input]
        self.assertIn("Tonnage Wt Expire Date", date_labels)
        next(t for t in at.text_input if t.label == "Year").set_value("2018")
        next(t for t in at.text_input if t.label == "Make/Model").set_value("Test Model")
        next(d for d in at.date_input if d.label == "Registration Expire Date").set_value(date(2027, 3, 1))
        next(b for b in at.button if b.label == "Save").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved updates for Heli2" in (s.value or "") for s in at.success))
        self.assertTrue(any(t.value and str(t.value).startswith("Info — Heli2") for t in at.subheader))
        info_md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("2018", info_md)
        self.assertIn("Test Model", info_md)
        self.assertIn("2027-03-01", info_md)
        book = at.session_state["_workbook"]
        eq = book.sheets["Equipment"]
        header = eq.rows[0]
        heli2 = eq.rows[2]
        self.assertEqual(heli2[header.index("Year")], "2018")
        self.assertEqual(heli2[header.index("Make/Model")], "Test Model")
        self.assertEqual(heli2[header.index("Registration Expire Date")], "2027-03-01")
        self.assertEqual(heli2[header.index("Unit ID")], "Heli2")
        self.assertEqual(heli2[header.index("Name")], "Heli2")
        self.assertEqual(book.sheets["Sheet1"].rows, [])
        self.assertEqual(len(book.sheets["Squawks"].rows), 1)

    def test_existing_offline_frat_app_still_loads(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(offline_app(), default_timeout=30).run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))


if __name__ == "__main__":
    unittest.main()
