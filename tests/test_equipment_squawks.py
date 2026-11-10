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
        "GREASE_CHECKPOINT_OFFSETS", "N480ML_MAINT_SHEET_TITLE",
        "EQUIPMENT_INFO_COLUMNS", "EQUIPMENT_COLUMNS", "EQUIPMENT_EDIT_COLUMNS", "SQUAWK_COLUMNS", "EQUIPMENT_TYPES",
        "SQUAWK_CATEGORIES", "SQUAWK_SEVERITIES", "SEVERITY_GROUNDED", "STATUS_OPEN",
        "STATUS_RESOLVED", "REPORTERS", "ACTIVE_VALUES", "HEADER_PAGES",
        "OFFICIAL_EQUIPMENT_NAMES", "REGISTRATION_EXPIRE_COL", "ANNUAL_MAINT_COL",
        "TONNAGE_APPLIES_COL", "TONNAGE_EXPIRE_COL", "TONNAGE_DEFAULT_UNITS", "DATE_STATUS_COLORS",
        "DOM_AIRCRAFT", "DOM_ACTION_ANNUAL",
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
        "aircraft_maint_profile", "parse_hobbs", "format_hobbs", "next_hobbs",
        "hobbs_flag", "hobbs_status_markup", "ensure_aircraft_maint_worksheet",
        "load_aircraft_maint_records", "latest_aircraft_maint_record",
        "build_aircraft_maint_record", "save_aircraft_maint_record",
        "grease_offsets_for", "grease_checkpoint_label", "grease_checkpoint_columns",
        "n480ml_maint_columns", "grease_due_hobbs", "format_grease_hobbs_date",
        "is_grease_checkpoint_done", "grease_done_markup",
        "ensure_n480ml_maint_worksheet", "load_n480ml_maint_records",
        "build_n480ml_maint_record", "save_n480ml_maint_record",
        "update_n480ml_grease_checkpoint",
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
        self.assertNotIn("oil_interval", n480)



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
        self.assertTrue(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        at.button(key="nav_dom").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "DOM" for t in at.title))
        self.assertEqual(
            [m.value for m in at.markdown if m.value in ("**N893PC**", "**N480ML**")],
            ["**N893PC**", "**N480ML**"],
        )
        annual = [b for b in at.button if b.label == "Annual/100 Hr"]
        self.assertEqual(len(annual), 2)
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

    def test_dom_annual_n893pc_form_and_n480ml_placeholder(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_dom").click().run()
        self.assertFalse(list(at.exception))
        annual = [b for b in at.button if b.label == "Annual/100 Hr"]
        self.assertEqual(len(annual), 2)
        annual[0].click().run()
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
        annual = [b for b in at.button if b.label == "Annual/100 Hr"]
        self.assertEqual(len(annual), 2)
        annual[1].click().run()
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
        [b for b in at.button if b.label == "Annual/100 Hr"][0].click().run()
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
        [b for b in at.button if b.label == "Annual/100 Hr"][1].click().run()
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
        self.assertIn("within 10 hours", md)
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
