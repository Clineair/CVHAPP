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
        "EQUIPMENT_SHEET_TITLE", "SQUAWKS_SHEET_TITLE",
        "EQUIPMENT_INFO_COLUMNS", "EQUIPMENT_COLUMNS", "SQUAWK_COLUMNS", "EQUIPMENT_TYPES",
        "SQUAWK_CATEGORIES", "SQUAWK_SEVERITIES", "SEVERITY_GROUNDED", "STATUS_OPEN",
        "STATUS_RESOLVED", "REPORTERS", "ACTIVE_VALUES", "HEADER_PAGES",
        "OFFICIAL_EQUIPMENT_NAMES", "REGISTRATION_EXPIRE_COL", "ANNUAL_MAINT_COL",
        "TONNAGE_APPLIES_COL", "TONNAGE_EXPIRE_COL", "TONNAGE_DEFAULT_UNITS", "DATE_STATUS_COLORS",
        "PARTS", "CORE_FACTORS", "PART_FACTORS", "PART_STOPS", "CONFIG_FIELDS",
        "ALL_FACTOR_KEYS", "ALL_STOP_KEYS", "FRAT_COLUMNS",
    }
    functions = {
        "_unique", "official_equipment_rows", "is_placeholder_equipment_seed",
        "_cell", "parse_equipment_date", "registration_due_date", "annual_maint_due_date",
        "date_flag", "date_flag_label", "date_status_markup", "tonnage_applies", "tonnage_due_date", "is_active_equipment",
        "is_open_squawk", "is_grounded_squawk", "squawks_for", "open_squawks_for",
        "equipment_has_grounding", "records_from_worksheet", "_worksheet_or_none",
        "_write_equipment_rows", "ensure_equipment_worksheet", "ensure_equipment_info_columns",
        "ensure_squawks_worksheet", "load_equipment_records",
        "load_squawk_records", "build_squawk_record", "save_squawk_record", "resolve_squawk",
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
        self.assertTrue(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        at.button(key="nav_yearly_items").click().run()
        self.assertTrue(any(t.value == "Yearly Items" for t in at.title))
        self.assertTrue(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        at.button(key="nav_dom").click().run()
        self.assertTrue(any(t.value == "DOM" for t in at.title))
        self.assertTrue(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))
        # Existing FRAT path remains one tap away.
        next(b for b in at.button if b.label == "🛩️ Pilot").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))
        frat_visible = any("FRAT" in (getattr(x, "value", None) or getattr(x, "label", None) or "") for x in list(at.tabs) + list(at.subheader) + list(at.title))
        self.assertTrue(frat_visible)

    def test_existing_offline_frat_app_still_loads(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_string(offline_app(), default_timeout=30).run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))


if __name__ == "__main__":
    unittest.main()
