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
        "IFTA_UNITS", "DRIVERS", "EMPLOYEES", "IFTA_TRIPS_SHEET_TITLE", "IFTA_FUEL_SHEET_TITLE", "IFTA_TRIPS_COLUMNS", "IFTA_FUEL_COLUMNS", "IFTA_RECEIPT_COLUMN", "IFTA_DEFAULT_JURISDICTION", "IFTA_JURISDICTIONS",
        "DOM_AIRCRAFT", "DOM_ACTION_ANNUAL", "YEARLY_ITEMS_SHEET_TITLE", "YEARLY_ITEMS_COLUMNS", "YEARLY_ITEM_GROUPS", "TIME_OFF_SHEET_TITLE", "TIME_OFF_COLUMNS", "TIME_OFF_TYPES", "TIME_OFF_TYPE_FULL", "TIME_OFF_TYPE_PARTIAL", "TIME_OFF_TYPE_VACATION", "TIME_OFF_TYPE_PROJECT", "TIME_OFF_TYPE_HOLIDAY", "TIME_OFF_ALL_EMPLOYEES", "TIME_OFF_PROJECTS", "TIME_OFF_STATUS_ACTIVE", "TIME_OFF_STATUS_CANCELLED", "TIME_OFF_ACTION_CREATE", "TIME_OFF_ACTION_CANCEL", "TIME_OFF_MAX_PAST_DAYS", "TIME_OFF_MAX_FUTURE_DAYS", "TIME_OFF_MAX_SPAN_DAYS", "TIMESHEET_EMPLOYEES", "TIMESHEET_SHEET_TITLE", "TIMESHEET_DAYS", "TIMESHEET_DAY_FIELDS", "TIMESHEET_WORKED_HOUR_FIELDS", "TIMESHEET_LEAVE_FIELDS", "TIMESHEET_LEAVE_HOURS_MAX", "TIMESHEET_EMAIL_TO", "TIMESHEET_IRS_BUSINESS_MILEAGE_RATES", "TIMESHEET_IRS_MILEAGE_RATES_START", "TIMESHEET_IRS_MILEAGE_RATES_END", "TIMESHEET_IRS_MILEAGE_SOURCE_URL", "TIMESHEET_MILEAGE_SHEET_TITLE", "TIMESHEET_MILEAGE_COLUMNS", "TIMESHEET_MILEAGE_SOURCE_IRS", "TIMESHEET_MILEAGE_SOURCE_COMPANY", "TIMESHEET_MILEAGE_SOURCE_SAVED",
        "ANTHONY_TIMESHEET_EMPLOYEE", "ANTHONY_TIMESHEET_SHEET_TITLE", "ANTHONY_TIMESHEET_TEMPLATE", "ANTHONY_TIMESHEET_DAYS", "ANTHONY_TIMESHEET_DAY_FIELDS", "ANTHONY_TIMESHEET_GRID_ROWS", "ANTHONY_TIMESHEET_WEEK_ROWS", "ANTHONY_TIMESHEET_NUMERIC_FIELDS",
        "TIMESHEET_AUTH_REQUIRED_KEYS", "TIMESHEET_AUTH_SHARED_KEYS", "TIMESHEET_AUTH_PROVIDER_KEYS",
        "TIMESHEET_GOOGLE_ISSUERS", "TIMESHEET_MICROSOFT_ISSUER_PREFIXES", "TIMESHEET_EMPLOYEE_EMAILS_SECTION",
        "TIMESHEET_MAIL_SHEET_TITLE", "TIMESHEET_MAIL_COLUMNS", "TIMESHEET_MAIL_ACTION_COMPOSER",
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
        "employee_button_key",
        "employee_has_timesheet", "employee_has_official_weekly_timesheet", "employee_has_anthony_timesheet", "timesheet_week_start", "timesheet_day_dates",
        "anthony_timesheet_columns", "anthony_timesheet_template_labels", "anthony_timesheet_content_payload",
        "new_anthony_timesheet_entry_id", "build_anthony_timesheet_record",
        "ensure_anthony_timesheets_worksheet", "load_anthony_timesheet_records",
        "load_anthony_timesheet_records_readonly", "save_anthony_timesheet_record",
        "anthony_timesheet_pdf_filename", "anthony_timesheet_xlsx_filename",
        "build_anthony_timesheet_xlsx", "build_anthony_timesheet_pdf",
        "timesheet_day_column", "timesheet_columns", "timesheet_leave_columns", "timesheet_leave_hours", "timesheet_weekly_hour_totals", "timesheet_hour_total_lines", "timesheet_day_hour_breakdown", "timesheet_hour_summary_rows", "timesheet_hour_summary_display_rows", "timesheet_hour_summary_short_date", "timesheet_hour_summary_html", "timesheet_day_expander_title", "ensure_timesheet_leave_columns", "timesheet_parse_number",
        "timesheet_format_hours", "timesheet_format_money", "timesheet_format_rate", "timesheet_format_mileage_rate", "timesheet_mileage_amount",
        "timesheet_irs_business_mileage_period", "timesheet_irs_business_mileage_rate",
        "timesheet_irs_mileage_supported_range_text", "timesheet_irs_mileage_unsupported_reason",
        "timesheet_mileage_trip_is_blank", "timesheet_structured_mileage_trips",
        "timesheet_resolve_mileage_trip", "timesheet_summarize_mileage_trips",
        "timesheet_mileage_help_caption", "ensure_timesheet_mileage_worksheet",
        "load_timesheet_mileage_records_readonly", "attach_timesheet_mileage_trips",
        "save_timesheet_mileage_trips", "timesheet_mileage_trips_for_display",
        "timesheet_mileage_rate_line", "timesheet_mileage_source_note",
        "timesheet_reimb_total", "timesheet_content_payload", "timesheet_content_hash",
        "timesheet_initials_valid", "timesheet_initials_match_current",
        "new_timesheet_entry_id", "_timesheet_sort_key", "latest_timesheet_record",
        "build_timesheet_record", "ensure_timesheets_worksheet",
        "load_timesheet_records", "load_timesheet_records_readonly",
        "save_timesheet_record", "timesheet_gmail_configured",
        "timesheet_secret_section", "timesheet_section_has_keys", "timesheet_auth_configured",
        "timesheet_auth_login_providers", "timesheet_trusted_signin_issuer",
        "timesheet_employee_email_map", "timesheet_user_info", "timesheet_verified_signin_email",
        "timesheet_employee_for_identity", "timesheet_access_state", "timesheet_can_view_or_edit",
        "timesheet_email_can_send", "timesheet_email_subject", "timesheet_email_body",
        "timesheet_email_compose", "timesheet_composer_allowed", "timesheet_email_block_reason",
        "timesheet_mail_columns", "ensure_timesheet_mail_worksheet",
        "load_timesheet_mail_records_readonly", "build_timesheet_mail_audit_record",
        "save_timesheet_mail_audit_record", "timesheet_access_message",
        "timesheet_bundle_path", "timesheet_template_labels",
        "build_timesheet_xlsx", "timesheet_pdf_filename", "timesheet_xlsx_filename",
        "build_timesheet_pdf", "_timesheet_wrap_label",
        "new_time_off_entry_id", "parse_time_off_time", "format_time_off_time",
        "format_time_off_time_display", "time_off_date_bounds", "time_off_shift_month",
        "time_off_calendar_weeks", "time_off_short_name", "time_off_type_label",
        "time_off_start_date", "time_off_end_date", "time_off_span_days",
        "time_off_covers_date", "_time_off_sort_key", "time_off_entry_id",
        "time_off_is_active", "latest_time_off_record", "current_time_off_records",
        "active_time_off_records", "time_off_for_date", "time_off_for_month",
        "time_off_identity", "time_off_duplicate_active", "time_off_summary_text",
        "time_off_month_grid_markup", "time_off_applies_to_filter",
        "_append_time_off_header_column", "ensure_time_off_project_column",
        "ensure_time_off_holiday_name_column", "ensure_time_off_worksheet",
        "load_time_off_records", "load_time_off_records_readonly",
        "build_time_off_record", "build_time_off_cancel_record", "save_time_off_record",
    }
    nodes = [n for n in TREE.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name in functions)]
    from datetime import date, time as dt_time, timedelta
    import sys
    import uuid
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    import timesheet_mail
    import timesheet_company_mail
    import timesheet_pin
    scope = {"datetime": datetime, "date": date, "dt_time": dt_time, "timedelta": timedelta, "ZoneInfo": ZoneInfo, "uuid": uuid, "timesheet_mail": timesheet_mail, "timesheet_company_mail": timesheet_company_mail, "timesheet_pin": timesheet_pin, "__file__": str(APP)}
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

    def test_employees_roster_order_and_drivers_unchanged(self):
        self.assertEqual(self.s["EMPLOYEES"], [
            "Ron Cline",
            "Carl Mulvaney",
            "Anthony Root",
            "Barry Markham",
            "Robert Rackley",
            "Gary Grant",
            "Skylar Fingerle",
        ])
        self.assertEqual(self.s["DRIVERS"], [
            "Robert Rackley",
            "Barry Markham",
            "Anthony Root",
            "Carl Mulvaney",
            "Ron Cline",
            "Gary Grant",
        ])
        self.assertNotIn("Skylar Fingerle", self.s["DRIVERS"])
        self.assertEqual(self.s["employee_button_key"]("Ron Cline"), "employee_btn_Ron_Cline")
        self.assertEqual(self.s["employee_button_key"]("Skylar Fingerle"), "employee_btn_Skylar_Fingerle")
        self.assertEqual(
            self.s["HEADER_PAGES"],
            ["Monthly Safety Meeting", "Yearly Items", "Equipment", "DOM", "EMPLOYEES"],
        )



    def test_timesheet_roster_week_calcs_initials_and_exports(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import fitz
        from openpyxl import load_workbook
        from io import BytesIO
        s = self.s
        self.assertEqual(s["TIMESHEET_EMPLOYEES"], [
            "Carl Mulvaney",
            "Barry Markham",
            "Robert Rackley",
            "Gary Grant",
            "Skylar Fingerle",
        ])
        self.assertNotIn("Ron Cline", s["TIMESHEET_EMPLOYEES"])
        self.assertNotIn("Anthony Root", s["TIMESHEET_EMPLOYEES"])
        self.assertTrue(s["employee_has_timesheet"]("Carl Mulvaney"))
        self.assertTrue(s["employee_has_timesheet"]("Skylar Fingerle"))
        self.assertFalse(s["employee_has_timesheet"]("Ron Cline"))
        self.assertTrue(s["employee_has_timesheet"]("Anthony Root"))
        self.assertTrue(s["employee_has_official_weekly_timesheet"]("Carl Mulvaney"))
        self.assertFalse(s["employee_has_official_weekly_timesheet"]("Anthony Root"))
        self.assertTrue(s["employee_has_anthony_timesheet"]("Anthony Root"))
        self.assertFalse(s["employee_has_anthony_timesheet"]("Carl Mulvaney"))
        self.assertFalse(s["employee_has_anthony_timesheet"]("Ron Cline"))
        self.assertEqual(s["DRIVERS"], [
            "Robert Rackley",
            "Barry Markham",
            "Anthony Root",
            "Carl Mulvaney",
            "Ron Cline",
            "Gary Grant",
        ])
        self.assertEqual(s["TIMESHEET_EMAIL_TO"], "patti@centralvalleyheli.com")
        self.assertEqual(s["TIMESHEET_SHEET_TITLE"], "Time Sheets")
        self.assertEqual(s["TIMESHEET_DAYS"], ("Sun", "Mon", "Tues", "Wed", "Thur", "Fri", "Sat"))
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2026, 6, 30)), 0.725)
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2026, 7, 1)), 0.76)
        self.assertEqual(s["TIMESHEET_IRS_MILEAGE_RATES_END"].isoformat(), "2026-12-31")

        self.assertEqual(s["timesheet_week_start"](date(2026, 11, 11)), date(2026, 11, 8))
        self.assertEqual(s["timesheet_week_start"](date(2026, 11, 8)), date(2026, 11, 8))
        self.assertEqual(s["timesheet_week_start"](date(2026, 11, 14)), date(2026, 11, 8))
        days = s["timesheet_day_dates"](date(2026, 11, 11))
        self.assertEqual(days[0], date(2026, 11, 8))
        self.assertEqual(days[-1], date(2026, 11, 14))
        self.assertEqual(s["timesheet_mileage_amount"]("100", "0.655"), 65.50)
        self.assertEqual(s["timesheet_reimb_total"]("10", "5", "2.25"), 17.25)
        self.assertIsNone(s["timesheet_reimb_total"]("", "", ""))

        when = datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        day_values = {
            "Sun": {"Location": "Office", "CVH Hours": "8"},
            "Mon": {"Location": "Field", "CVH Hours": "8", "Perdiem Rate": "60"},
        }
        rec = s["build_timesheet_record"](
            "Carl Mulvaney", date(2026, 11, 11),
            day_values=day_values,
            mileage_trips=[{
                "Travel Date": date(2026, 11, 11),
                "Start Location": "Fresno",
                "End Location": "Farm",
                "Miles": "20",
            }],
            parts="12.50", fuel="30", other_reimb="",
            comments="Weekly note",
            signature="Carl Mulvaney", signature_date=date(2026, 11, 14),
            initials="CM",
            when=when, entry_id="TS-TEST-1", today=date(2026, 11, 11),
        )
        self.assertEqual(rec["Week Of"], "2026-11-08")
        self.assertEqual(rec["Employee"], "Carl Mulvaney")
        self.assertEqual(rec["Sun Location"], "Office")
        self.assertEqual(rec["Sun CVH Hours"], "8")
        self.assertEqual(rec["Mon Perdiem Rate"], "60.00")
        self.assertEqual(rec["Mileage Rate"], "0.76")
        self.assertEqual(rec["Mileage Amount"], "15.20")
        self.assertEqual(rec["Mileage Trips"][0]["Travel Date"], "2026-11-11")
        self.assertEqual(rec["Mileage Trips"][0]["Rate Source"], s["TIMESHEET_MILEAGE_SOURCE_IRS"])
        self.assertEqual(rec["Reimb Total"], "42.50")
        self.assertEqual(rec["Status"], "Initialed")
        self.assertTrue(s["timesheet_initials_valid"](rec))
        changed = dict(rec)
        changed["Sun CVH Hours"] = "9"
        self.assertFalse(s["timesheet_initials_valid"](changed))
        self.assertFalse(s["timesheet_initials_match_current"](rec, changed))
        self.assertTrue(s["timesheet_initials_match_current"](rec, dict(rec)))

        with self.assertRaisesRegex(ValueError, "does not have a time sheet"):
            s["build_timesheet_record"]("Ron Cline", date(2026, 11, 8), today=date(2026, 11, 11))
        with self.assertRaisesRegex(ValueError, "does not have a time sheet"):
            s["build_timesheet_record"]("Anthony Root", date(2026, 11, 8), today=date(2026, 11, 11))
        with self.assertRaisesRegex(ValueError, "must be a number"):
            s["build_timesheet_record"](
                "Gary Grant", date(2026, 11, 8),
                day_values={"Sun": {"CVH Hours": "eight"}},
                today=date(2026, 11, 11),
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            s["build_timesheet_record"](
                "Gary Grant", date(2026, 11, 8),
                mileage_miles="-1",
                today=date(2026, 11, 11),
            )

        self.assertFalse(s["timesheet_email_can_send"](rec, configured=False))
        self.assertFalse(s["timesheet_email_can_send"](rec, configured=True))
        reason = s["timesheet_email_block_reason"](rec, configured=False)
        self.assertEqual(reason, "PIN not set up yet - ask the office")
        self.assertIn("patti@centralvalleyheli.com", s["TIMESHEET_EMAIL_TO"])

        pdf = s["build_timesheet_pdf"](rec)
        self.assertTrue(pdf.startswith(b"%PDF"))
        Path("/tmp/timesheet_tpl/filled_sample.pdf").write_bytes(pdf)
        doc = fitz.open(stream=pdf, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        extracted = "\n".join(page.get_text() for page in doc)
        doc.close()
        extracted_one_line = extracted.replace("\n", " ")
        for label in s["timesheet_template_labels"](rec):
            self.assertIn(label, extracted_one_line, label)
        self.assertIn("Carl Mulvaney", extracted)
        self.assertIn("2026-11-08", extracted)
        self.assertIn("2026-11-11", extracted)
        self.assertIn("Initials: CM", extracted)
        self.assertIn("Office", extracted)
        self.assertIn("0.76", extracted_one_line)
        self.assertIn("$15.20", extracted_one_line)
        self.assertNotIn("0.65.5 based on 2023 IRS reimb rate", extracted)
        self.assertNotIn("X 0.?", extracted)

        xlsx = s["build_timesheet_xlsx"](rec)
        Path("/tmp/timesheet_tpl/filled_sample.xlsx").write_bytes(xlsx)
        wb = load_workbook(BytesIO(xlsx))
        ws = wb[wb.sheetnames[0]]
        joined = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
        for label in ("Central Valley Helicopters", "Weekly Time Sheet", "Perdiem Rates -",
                      "$60.00 per day with company paid hotel",
                      "Personal vechicle usage will be reimbursed at",
                      "IRS business rate of $0.76 per mile",
                      "Employee Signature", "Forestry #  work hours", "BNSF # work hours"):
            self.assertIn(label, joined)
        self.assertNotIn("0.65.5 based on 2023 IRS reimb rate", joined)
        self.assertNotIn("X 0.?", joined)
        self.assertIn("Carl Mulvaney", ws["B4"].value)
        self.assertIn("2026-11-08", ws["F4"].value)
        self.assertEqual(str(ws["C8"].value), "Office")
        self.assertEqual(str(ws["C9"].value), "8")
        self.assertIn("CM", joined)


    def test_timesheet_auth_mapping_composer_and_security_gates(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        from urllib.parse import unquote
        s = self.s
        when = datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        rec = s["build_timesheet_record"](
            "Carl Mulvaney", date(2026, 11, 8),
            day_values={"Sun": {"Location": "Office", "CVH Hours": "8"}},
            initials="CM",
            when=when, entry_id="TS-AUTH-1", today=date(2026, 11, 11),
        )
        stale = dict(rec)
        stale["Sun CVH Hours"] = "9"

        auth_secrets = {
            "auth": {
                "redirect_uri": "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback",
                "cookie_secret": "test-only-not-used",
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            },
            "timesheet_employees": {
                "Carl Mulvaney": "carl.timesheet@example.com",
                "Barry Markham": "barry.timesheet@example.com",
            },
        }
        empty_map = {
            "auth": auth_secrets["auth"],
            "timesheet_employees": {},
        }
        duplicate_map = {
            "auth": auth_secrets["auth"],
            "timesheet_employees": {
                "Carl Mulvaney": "shared.timesheet@example.com",
                "Barry Markham": "shared.timesheet@example.com",
            },
        }
        carl = {
            "is_logged_in": True,
            "email": "Carl.Timesheet@example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "name": "Carl Mulvaney",
            "tokens": {"access": "should-never-be-copied"},
        }
        barry = {
            "is_logged_in": True,
            "email": "barry.timesheet@example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
            "name": "Carl Mulvaney",
        }
        unverified = {
            "is_logged_in": True,
            "email": "carl.timesheet@example.com",
            "email_verified": False,
            "iss": "https://accounts.google.com",
        }
        unmapped = {
            "is_logged_in": True,
            "email": "stranger@example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
        }
        bad_issuer = {
            "is_logged_in": True,
            "email": "carl.timesheet@example.com",
            "email_verified": True,
            "iss": "https://evil.example",
        }
        logged_out = {"is_logged_in": False, "email": "carl.timesheet@example.com", "email_verified": True}

        self.assertFalse(s["timesheet_auth_configured"]({}))
        self.assertFalse(s["timesheet_auth_configured"]({"auth": {"client_id": "only-one"}}))
        self.assertTrue(s["timesheet_auth_configured"](auth_secrets))
        self.assertFalse(s["timesheet_gmail_configured"](auth_secrets))
        self.assertEqual(
            s["timesheet_employee_email_map"](auth_secrets)["Carl Mulvaney"],
            "carl.timesheet@example.com",
        )
        self.assertNotIn("Robert Rackley", s["timesheet_employee_email_map"](auth_secrets))
        self.assertEqual(s["timesheet_employee_email_map"](empty_map), {})
        self.assertEqual(s["timesheet_employee_email_map"](duplicate_map), {})
        self.assertEqual(s["timesheet_employee_for_identity"](carl, secrets=auth_secrets), "Carl Mulvaney")
        self.assertIsNone(s["timesheet_employee_for_identity"](barry, secrets=empty_map))
        self.assertIsNone(s["timesheet_verified_signin_email"](unverified))
        self.assertIsNone(s["timesheet_verified_signin_email"](bad_issuer))
        self.assertIsNone(s["timesheet_verified_signin_email"](logged_out))
        info = s["timesheet_user_info"](carl)
        self.assertNotIn("tokens", info)
        self.assertTrue(info["email_verified"])

        import timesheet_pin
        pin_secrets = {
            "auth": auth_secrets["auth"],
            "timesheet_pin": {"cookie_secret": "test-cookie-secret-0123456789"},
            "timesheet_pins": {
                "Carl Mulvaney": timesheet_pin.make_pin_hash("2468"),
                "Barry Markham": timesheet_pin.make_pin_hash("1357"),
            },
        }
        # No PIN secrets: closed with the office message. A Google user does not open it.
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=logged_out, secrets={}, pin_employee="", failures=0),
            "pins_not_configured",
        )
        self.assertEqual(s["timesheet_access_message"]("pins_not_configured"), "PIN not set up yet - ask the office")
        self.assertFalse(s["timesheet_can_view_or_edit"]("Carl Mulvaney", user=logged_out, secrets={}))
        self.assertFalse(s["timesheet_composer_allowed"](rec, user=carl, saved=rec, current=rec, secrets={}))
        self.assertFalse(s["timesheet_email_can_send"](rec, configured=True, user=carl, secrets=auth_secrets))
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=carl, secrets=auth_secrets, pin_employee="", failures=0),
            "pins_not_configured",
        )
        self.assertFalse(s["timesheet_can_view_or_edit"]("Carl Mulvaney", user=carl, secrets=auth_secrets))
        office = s["timesheet_email_block_reason"](
            rec, user=carl, saved=rec, current=rec, secrets=auth_secrets, pin_employee="",
        )
        self.assertEqual(office, "PIN not set up yet - ask the office")

        # PIN on: no cookie, another employee, and a Google account cannot view or compose.
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=logged_out, secrets=pin_secrets, pin_employee="", failures=0),
            "pin_required",
        )
        self.assertFalse(s["timesheet_can_view_or_edit"]("Carl Mulvaney", secrets=pin_secrets, pin_employee="", failures=0))
        self.assertFalse(s["timesheet_composer_allowed"](
            rec, user=logged_out, saved=rec, current=rec, secrets=pin_secrets, pin_employee="", failures=0,
        ))
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=barry, secrets=pin_secrets, pin_employee="Barry Markham", failures=0),
            "other_employee",
        )
        self.assertFalse(s["timesheet_can_view_or_edit"]("Carl Mulvaney", user=barry, secrets=pin_secrets, pin_employee="Barry Markham"))
        self.assertFalse(s["timesheet_composer_allowed"](
            rec, user=barry, saved=rec, current=rec, secrets=pin_secrets, pin_employee="Barry Markham",
        ))
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=carl, secrets=pin_secrets, pin_employee="", failures=0),
            "pin_required",
        )
        self.assertFalse(s["timesheet_can_view_or_edit"]("Carl Mulvaney", user=carl, secrets=pin_secrets))
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", secrets=pin_secrets, pin_employee="", failures=timesheet_pin.MAX_ATTEMPTS),
            "pin_locked",
        )
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", secrets=pin_secrets, pin_employee="Carl Mulvaney", failures=timesheet_pin.MAX_ATTEMPTS),
            "allowed",
        )
        # Display name must not override the email mapping. It also does not open a time sheet.
        self.assertEqual(s["timesheet_employee_for_identity"](barry, secrets=auth_secrets), "Barry Markham")
        self.assertTrue(s["timesheet_can_view_or_edit"](
            "Carl Mulvaney", user=carl, secrets=pin_secrets, pin_employee="Carl Mulvaney",
        ))
        self.assertFalse(timesheet_pin.verify_employee_pin("Barry Markham", "2468", pin_secrets))
        self.assertEqual(timesheet_pin.attempt_pin("Carl Mulvaney", "2468", pin_secrets, 0), ("ok", 0))
        self.assertEqual(timesheet_pin.attempt_pin("Carl Mulvaney", "0000", pin_secrets, 4), ("locked", 5))

        # Stale initials and wrong recipient cannot compose. Send stays false.
        self.assertTrue(s["timesheet_composer_allowed"](
            rec, user=carl, saved=rec, current=rec, secrets=pin_secrets, pin_employee="Carl Mulvaney",
        ))
        self.assertFalse(s["timesheet_composer_allowed"](
            rec, user=carl, saved=rec, current=stale, secrets=pin_secrets, pin_employee="Carl Mulvaney",
        ))
        self.assertFalse(
            s["timesheet_composer_allowed"](
                rec, user=carl, saved=rec, current=rec, secrets=pin_secrets, pin_employee="Carl Mulvaney",
                to="other@example.com",
            )
        )
        with self.assertRaisesRegex(ValueError, "can only be addressed to"):
            s["timesheet_email_compose"](rec, to="other@example.com")
        # Mailto is not the send path. In-app send stays off until company mail is enabled.
        self.assertFalse(s["timesheet_email_can_send"](rec, user=carl, secrets=pin_secrets, pin_employee="Carl Mulvaney"))
        self.assertFalse(s["timesheet_email_can_send"](
            rec, user=carl, secrets=pin_secrets, pin_employee="Carl Mulvaney",
            access_allowed=True, initials_match=True,
            pdf_bytes=b"%PDF-1.4 test", filename="sheet.pdf",
        ))
        reason = s["timesheet_email_block_reason"](
            rec, user=carl, saved=rec, current=rec, secrets=pin_secrets, pin_employee="Carl Mulvaney",
        )
        self.assertEqual(reason, "email not set up yet - ask the office")
        self.assertNotIn("attach the PDF yourself", reason)
        stale_reason = s["timesheet_email_block_reason"](
            rec, user=carl, saved=rec, current=stale, secrets=pin_secrets, pin_employee="Carl Mulvaney",
        )
        self.assertIn("Initial and save", stale_reason)

        # Readonly load must not return another employee's payroll rows.
        book = FakeSpreadsheet(sheet1_header=s["FRAT_COLUMNS"])
        s["save_timesheet_record"](rec, spreadsheet=book)
        barry_rec = s["build_timesheet_record"](
            "Barry Markham", date(2026, 11, 8),
            day_values={"Sun": {"Location": "Field", "CVH Hours": "7"}},
            initials="BM",
            when=when, entry_id="TS-AUTH-2", today=date(2026, 11, 11),
        )
        s["save_timesheet_record"](barry_rec, spreadsheet=book)
        only_carl = s["load_timesheet_records_readonly"](book, employee="Carl Mulvaney")
        self.assertEqual({row["Employee"] for row in only_carl}, {"Carl Mulvaney"})
        self.assertFalse(any(row["Employee"] == "Barry Markham" for row in only_carl))

        # Audit tab is created on first write only and leaves a custom header alone.
        custom = FakeSpreadsheet(sheet1_header=s["FRAT_COLUMNS"])
        custom.sheets[s["TIMESHEET_MAIL_SHEET_TITLE"]] = FakeWorksheet(
            s["TIMESHEET_MAIL_SHEET_TITLE"], [["Custom Mail Header", "Keep"]],
        )
        ws, created = s["ensure_timesheet_mail_worksheet"](custom)
        self.assertFalse(created)
        self.assertEqual(ws.row_values(1), ["Custom Mail Header", "Keep"])
        audit = s["build_timesheet_mail_audit_record"](rec, user=carl, when=when)
        self.assertEqual(audit["Recipient"], "patti@centralvalleyheli.com")
        self.assertEqual(audit["Action"], "Composer opened")
        self.assertEqual(audit["Status"], "Opened")
        self.assertEqual(audit["Signed-in Email"], "carl.timesheet@example.com")
        pinned = s["build_timesheet_mail_audit_record"](rec, pin_employee="Carl Mulvaney", when=when)
        self.assertEqual(pinned["Signed-in Email"], "Carl Mulvaney")
        self.assertNotIn("tokens", str(pinned))
        s["save_timesheet_mail_audit_record"](audit, spreadsheet=book)
        self.assertIn("Time Sheet Mail", book.sheets)
        self.assertEqual(book.sheets["Time Sheet Mail"].rows[0], s["TIMESHEET_MAIL_COLUMNS"])
        self.assertEqual(set(book.sheets), {"Sheet1", "Time Sheets", "Time Sheet Mail"})
        self.assertNotIn("tokens", str(audit))
        self.assertEqual(s["timesheet_employee_email_map"]({}), {})

    def test_timesheet_google_and_microsoft_identity_and_anthony_mapping(self):
        s = self.s
        named = {
            "auth": {
                "redirect_uri": "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback",
                "cookie_secret": "test-only-not-used",
                "google": {
                    "client_id": "g-id",
                    "client_secret": "g-secret",
                    "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
                },
                "microsoft": {
                    "client_id": "m-id",
                    "client_secret": "m-secret",
                    "server_metadata_url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
                },
            },
            "timesheet_employees": {
                "Anthony Root": "anthony.signin@example.com",
                "Robert Rackley": "robert.signin@example.com",
            },
        }
        self.assertTrue(s["timesheet_auth_configured"](named))
        self.assertEqual(s["timesheet_auth_login_providers"](named), ("google", "microsoft"))
        self.assertFalse(s["timesheet_auth_configured"]({
            "auth": {"redirect_uri": named["auth"]["redirect_uri"], "cookie_secret": "x"},
        }))
        self.assertFalse(s["timesheet_auth_configured"]({"auth": named["auth"]["google"]}))
        mapping = s["timesheet_employee_email_map"](named)
        self.assertEqual(mapping["Anthony Root"], "anthony.signin@example.com")
        self.assertEqual(mapping["Robert Rackley"], "robert.signin@example.com")
        self.assertNotIn("Carl Mulvaney", mapping)
        ms_user = {
            "is_logged_in": True,
            "email": "Robert.Signin@example.com",
            "email_verified": True,
            "iss": "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",
        }
        self.assertTrue(s["timesheet_trusted_signin_issuer"](ms_user["iss"]))
        self.assertTrue(s["timesheet_trusted_signin_issuer"]("https://sts.windows.net/common"))
        self.assertFalse(s["timesheet_trusted_signin_issuer"]("https://evil.example"))
        self.assertFalse(s["timesheet_trusted_signin_issuer"]("https://login.microsoftonline.com.evil.example/"))
        self.assertEqual(s["timesheet_verified_signin_email"](ms_user), "robert.signin@example.com")
        self.assertEqual(s["timesheet_employee_for_identity"](ms_user, secrets=named), "Robert Rackley")
        anthony = {
            "is_logged_in": True,
            "email": "anthony.signin@example.com",
            "email_verified": True,
            "iss": "https://accounts.google.com",
        }
        self.assertEqual(s["timesheet_employee_for_identity"](anthony, secrets=named), "Anthony Root")
        self.assertEqual(
            s["timesheet_access_state"]("Anthony Root", user=anthony, secrets=named, pin_employee="", failures=0),
            "pins_not_configured",
        )
        self.assertEqual(
            s["timesheet_access_state"]("Carl Mulvaney", user=anthony, secrets=named, pin_employee="Anthony Root", failures=0),
            "pins_not_configured",
        )
        self.assertEqual(
            s["anthony_timesheet_pdf_filename"]({"Employee": "Anthony Root", "Week Of": "2026-11-08"}),
            "Anthony_Time_Sheet_Anthony_Root_2026-11-08.pdf",
        )

    def test_timesheet_irs_mileage_rates_dates_and_exports(self):

        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import fitz
        from openpyxl import load_workbook
        from io import BytesIO
        s = self.s
        self.assertEqual(s["TIMESHEET_IRS_MILEAGE_SOURCE_URL"], "https://www.irs.gov/tax-professionals/standard-mileage-rates")
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2026, 6, 30)), 0.725)
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2026, 7, 1)), 0.76)
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2025, 12, 31)), 0.70)
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2024, 6, 1)), 0.67)
        self.assertEqual(s["timesheet_irs_business_mileage_rate"](date(2023, 7, 4)), 0.655)
        self.assertIsNone(s["timesheet_irs_business_mileage_rate"](date(2027, 1, 1)))
        self.assertIsNone(s["timesheet_irs_business_mileage_rate"](date(2010, 12, 31)))
        self.assertEqual(s["timesheet_mileage_amount"]("100", "0.76"), 76.00)
        self.assertEqual(s["timesheet_mileage_amount"]("100", "0.725"), 72.50)
        self.assertEqual(s["timesheet_format_mileage_rate"](0.76), "0.76")
        self.assertEqual(s["timesheet_format_mileage_rate"](0.725), "0.725")
        self.assertEqual(s["timesheet_format_mileage_rate"](0.70), "0.70")

        when = datetime(2026, 7, 2, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        week = date(2026, 6, 28)  # Sunday; week spans the July 1 rate change
        rec = s["build_timesheet_record"](
            "Gary Grant", week,
            mileage_trips=[
                {"Travel Date": date(2026, 6, 30), "Start Location": "Base", "End Location": "Field", "Miles": "100"},
                {"Travel Date": date(2026, 7, 1), "Start Location": "Field", "End Location": "Base", "Miles": "100"},
            ],
            initials="GG",
            when=when, entry_id="TS-MILE-1", today=date(2026, 7, 2),
        )
        self.assertEqual(rec["Week Of"], "2026-06-28")
        self.assertEqual(rec["Mileage Trips"][0]["Rate"], "0.725")
        self.assertEqual(rec["Mileage Trips"][0]["Amount"], "72.50")
        self.assertEqual(rec["Mileage Trips"][0]["Rate Source"], "IRS")
        self.assertEqual(rec["Mileage Trips"][1]["Rate"], "0.76")
        self.assertEqual(rec["Mileage Trips"][1]["Amount"], "76.00")
        self.assertEqual(rec["Mileage Amount"], "148.50")
        self.assertEqual(rec["Mileage Miles"], "200")
        self.assertEqual(rec["Mileage Rate"], "")  # mixed rates
        self.assertTrue(s["timesheet_initials_valid"](rec))
        # Using Sunday instead of the travel date would be wrong on this week.
        self.assertNotEqual(s["timesheet_irs_business_mileage_rate"](week), 0.76)

        changed_date = s["build_timesheet_record"](
            "Gary Grant", week,
            mileage_trips=[
                {"Travel Date": date(2026, 6, 30), "Start Location": "Base", "End Location": "Field", "Miles": "100"},
                {"Travel Date": date(2026, 7, 2), "Start Location": "Field", "End Location": "Base", "Miles": "100"},
            ],
            initials="GG",
            when=when, entry_id="TS-MILE-1", today=date(2026, 7, 2),
        )
        self.assertFalse(s["timesheet_initials_match_current"](rec, changed_date))
        changed_rate = s["build_timesheet_record"](
            "Gary Grant", week,
            mileage_trips=[
                {"Travel Date": date(2026, 6, 30), "Start Location": "Base", "End Location": "Field", "Miles": "100"},
                {
                    "Travel Date": date(2026, 7, 1), "Start Location": "Field", "End Location": "Base",
                    "Miles": "100", "Company Override": "0.80",
                },
            ],
            initials="GG",
            when=when, entry_id="TS-MILE-1", today=date(2026, 7, 2),
        )
        self.assertEqual(changed_rate["Mileage Trips"][1]["Rate"], "0.80")
        self.assertEqual(changed_rate["Mileage Trips"][1]["Rate Source"], s["TIMESHEET_MILEAGE_SOURCE_COMPANY"])
        self.assertEqual(changed_rate["Mileage Amount"], "152.50")
        self.assertFalse(s["timesheet_initials_match_current"](rec, changed_rate))

        with self.assertRaisesRegex(ValueError, "travel date"):
            s["build_timesheet_record"](
                "Gary Grant", week, mileage_miles="100", mileage_rate="", today=date(2026, 7, 2),
            )
        with self.assertRaisesRegex(ValueError, "not invented|not available"):
            s["build_timesheet_record"](
                "Gary Grant", date(2027, 1, 3),
                mileage_trips=[{"Travel Date": date(2027, 1, 4), "Miles": "10"}],
                today=date(2027, 1, 4),
            )
        # Company override is allowed when no IRS rate has been published yet.
        future = s["build_timesheet_record"](
            "Gary Grant", date(2027, 1, 3),
            mileage_trips=[{"Travel Date": date(2027, 1, 4), "Miles": "10", "Company Override": "0.80"}],
            today=date(2027, 1, 4),
        )
        self.assertEqual(future["Mileage Rate"], "0.80")
        self.assertEqual(future["Mileage Trips"][0]["Rate Source"], s["TIMESHEET_MILEAGE_SOURCE_COMPANY"])

        # Historic saved records keep their stored rate/amount and hash without a travel date.
        legacy_when = datetime(2023, 8, 10, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        legacy = s["build_timesheet_record"](
            "Carl Mulvaney", date(2023, 8, 6),
            mileage_start="Fresno", mileage_end="Farm",
            mileage_miles="20", mileage_rate="0.655",
            initials="CM",
            when=legacy_when, entry_id="TS-OLD-1", today=date(2023, 8, 10),
        )
        self.assertEqual(legacy["Mileage Rate"], "0.655")
        self.assertEqual(legacy["Mileage Amount"], "13.10")
        self.assertEqual(legacy.get("Mileage Trips"), [])
        self.assertTrue(s["timesheet_initials_valid"](legacy))
        self.assertTrue(s["timesheet_initials_match_current"](legacy, dict(legacy)))
        book = FakeSpreadsheet()
        source = s["save_timesheet_record"](legacy, spreadsheet=book)
        self.assertEqual(source, "Google Sheets (Time Sheets)")
        self.assertNotIn("Time Sheet Mileage", book.sheets)
        header = list(book.sheets["Time Sheets"].rows[0])
        self.assertIn("Mileage Rate", header)
        self.assertNotIn("Mileage Trips", header)
        loaded = s["load_timesheet_records_readonly"](book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Mileage Amount"], "13.10")
        self.assertEqual(loaded[0]["Mileage Rate"], "0.655")
        self.assertTrue(s["timesheet_initials_valid"](loaded[0]))
        # Existing Time Sheets header is not rewritten when a later dated trip is saved.
        dated = s["build_timesheet_record"](
            "Carl Mulvaney", date(2026, 11, 8),
            mileage_trips=[{"Travel Date": date(2026, 11, 11), "Miles": "100", "Start Location": "A", "End Location": "B"}],
            initials="CM",
            when=when, entry_id="TS-NEW-1", today=date(2026, 11, 11),
        )
        self.assertEqual(dated["Mileage Amount"], "76.00")
        dest = s["save_timesheet_record"](dated, spreadsheet=book)
        self.assertIn("Time Sheet Mileage", dest)
        self.assertEqual(book.sheets["Time Sheets"].rows[0], header)
        reloaded = s["load_timesheet_records_readonly"](book)
        new_row = [r for r in reloaded if r["Entry ID"] == "TS-NEW-1"][0]
        old_row = [r for r in reloaded if r["Entry ID"] == "TS-OLD-1"][0]
        self.assertEqual(new_row["Mileage Trips"][0]["Travel Date"], "2026-11-11")
        self.assertEqual(new_row["Mileage Trips"][0]["Amount"], "76.00")
        self.assertTrue(s["timesheet_initials_valid"](old_row))
        self.assertEqual(old_row["Mileage Amount"], "13.10")
        self.assertFalse(s["timesheet_structured_mileage_trips"](old_row))

        pdf = s["build_timesheet_pdf"](rec)
        text = " ".join(page.get_text() for page in fitz.open(stream=pdf, filetype="pdf"))
        self.assertIn("2026-06-30", text)
        self.assertIn("2026-07-01", text)
        self.assertIn("0.725", text)
        self.assertIn("72.50", text)
        self.assertIn("0.76", text)
        self.assertIn("76.00", text)
        self.assertIn("148.50", text)
        self.assertIn("later rates are not invented", text)
        self.assertNotIn("0.65.5 based on 2023 IRS reimb rate", text)
        xlsx = s["build_timesheet_xlsx"](rec)
        joined = " ".join(str(c.value) for row in load_workbook(BytesIO(xlsx)).active.iter_rows() for c in row if c.value)
        self.assertIn("2026-06-30", joined)
        self.assertIn("2026-07-01", joined)
        self.assertIn("72.50", joined)
        self.assertIn("76.00", joined)
        self.assertIn("148.50", joined)
        self.assertNotIn("0.65.5 based on 2023 IRS reimb rate", joined)
        self.assertFalse(s["timesheet_email_can_send"](rec, configured=True))


    def test_anthony_timesheet_separate_form_initials_and_exports(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        import fitz
        from openpyxl import load_workbook
        from io import BytesIO
        s = self.s
        self.assertEqual(s["ANTHONY_TIMESHEET_EMPLOYEE"], "Anthony Root")
        self.assertEqual(s["ANTHONY_TIMESHEET_SHEET_TITLE"], "Anthony Time Sheets")
        self.assertEqual(s["ANTHONY_TIMESHEET_TEMPLATE"], "anthony_timesheet_template.xlsx")
        labels = s["anthony_timesheet_template_labels"]()
        self.assertIn("Survery Hrs", labels)
        self.assertNotIn("Survey Hrs", labels)
        self.assertIn("L&I Ground Hours", labels)
        self.assertNotIn("CVH # work hours", labels)
        self.assertNotIn("Vacation Hours", labels)
        self.assertNotIn("Sick Hours", labels)
        self.assertNotIn("Vacation Hours", " ".join(s["anthony_timesheet_columns"]()))
        self.assertNotIn("Sick Hours", " ".join(s["anthony_timesheet_columns"]()))
        self.assertEqual(s["ANTHONY_TIMESHEET_GRID_ROWS"], 22)
        self.assertEqual(s["ANTHONY_TIMESHEET_WEEK_ROWS"], 7)

        when = datetime(2026, 11, 11, 9, 15, tzinfo=ZoneInfo("America/Los_Angeles"))
        day_values = {
            "Sun": {"L&I Ground Hours": "2", "Notes": "Shop"},
            "Mon": {"L&I Flight Hours": "3.5", "Spraying App Acres": "40", "Per Diem": "60"},
        }
        rec = s["build_anthony_timesheet_record"](
            "Anthony Root", date(2026, 11, 11),
            day_values=day_values,
            initials="AR",
            when=when, entry_id="ANT-TEST-1", today=date(2026, 11, 11),
        )
        self.assertEqual(rec["Employee"], "Anthony Root")
        self.assertEqual(rec["Form"], "Anthony")
        self.assertEqual(rec["Week Of"], "2026-11-08")
        self.assertEqual(rec["Sun Date"], "2026-11-08")
        self.assertEqual(rec["Sat Date"], "2026-11-14")
        self.assertEqual(rec["Sun L&I Ground Hours"], "2")
        self.assertEqual(rec["Mon L&I Flight Hours"], "3.5")
        self.assertEqual(rec["Mon Spraying App Acres"], "40")
        self.assertEqual(rec["Mon Per Diem"], "60.00")
        self.assertEqual(rec["Sun Notes"], "Shop")
        self.assertEqual(rec["Status"], "Initialed")
        self.assertTrue(s["timesheet_initials_valid"](rec))
        self.assertTrue(s["timesheet_initials_match_current"](rec, dict(rec)))
        changed = dict(rec)
        changed["Sun L&I Ground Hours"] = "4"
        self.assertFalse(s["timesheet_initials_valid"](changed))
        self.assertFalse(s["timesheet_initials_match_current"](rec, changed))

        with self.assertRaisesRegex(ValueError, "does not have Anthony's time sheet"):
            s["build_anthony_timesheet_record"]("Carl Mulvaney", date(2026, 11, 8), today=date(2026, 11, 11))
        with self.assertRaisesRegex(ValueError, "does not have Anthony's time sheet"):
            s["build_anthony_timesheet_record"]("Ron Cline", date(2026, 11, 8), today=date(2026, 11, 11))
        with self.assertRaisesRegex(ValueError, "must be a number"):
            s["build_anthony_timesheet_record"](
                "Anthony Root", date(2026, 11, 8),
                day_values={"Sun": {"L&I Ground Hours": "two"}},
                today=date(2026, 11, 11),
            )
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            s["build_anthony_timesheet_record"](
                "Anthony Root", date(2026, 11, 8),
                day_values={"Sun": {"Survery Hrs": "-1"}},
                today=date(2026, 11, 11),
            )

        self.assertFalse(s["timesheet_email_can_send"](rec, configured=False))
        self.assertFalse(s["timesheet_email_can_send"](rec, configured=True))
        reason = s["timesheet_email_block_reason"](rec, configured=False)
        self.assertEqual(reason, "PIN not set up yet - ask the office")

        book = FakeSpreadsheet()
        self.assertEqual(s["load_anthony_timesheet_records_readonly"](book), [])
        self.assertNotIn("Anthony Time Sheets", book.sheets)
        self.assertNotIn("Time Sheets", book.sheets)
        source = s["save_anthony_timesheet_record"](rec, spreadsheet=book)
        self.assertEqual(source, "Google Sheets (Anthony Time Sheets)")
        self.assertIn("Anthony Time Sheets", book.sheets)
        self.assertNotIn("Time Sheets", book.sheets)
        self.assertEqual(set(book.sheets), {"Sheet1", "Anthony Time Sheets"})
        header = book.sheets["Anthony Time Sheets"].rows[0]
        self.assertEqual(header[0], "Timestamp")
        self.assertIn("Sun Survery Hrs", header)
        self.assertIn("Sat Notes", header)
        loaded = s["load_anthony_timesheet_records_readonly"](book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Employee"], "Anthony Root")
        self.assertEqual(loaded[0]["Sun L&I Ground Hours"], "2")
        s["ensure_anthony_timesheets_worksheet"](book)
        self.assertEqual(book.sheets["Anthony Time Sheets"].rows[0], header)
        self.assertNotIn("Time Sheets", book.sheets)

        pdf = s["build_anthony_timesheet_pdf"](rec)
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = fitz.open(stream=pdf, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        extracted = "\n".join(page.get_text() for page in doc)
        doc.close()
        extracted_one_line = " ".join(extracted.split())
        for label in labels:
            self.assertIn(label, extracted_one_line, label)
        self.assertIn("Anthony Root", extracted)
        self.assertIn("2026-11-08", extracted)
        self.assertIn("Initials: AR", extracted)
        self.assertIn("Survery Hrs", extracted)
        self.assertNotIn("Survey Hrs", extracted)
        self.assertIn("Shop", extracted)
        self.assertIn("3.5", extracted)
        self.assertNotIn("CVH # work hours", extracted)
        self.assertNotIn("Personal vechicle", extracted)

        xlsx = s["build_anthony_timesheet_xlsx"](rec)
        wb = load_workbook(BytesIO(xlsx))
        self.assertEqual(wb.sheetnames, ["Sheet1", "Sheet2", "Sheet3"])
        ws = wb["Sheet1"]
        self.assertEqual(ws["A1"].value, "Employee")
        self.assertEqual(ws["B1"].value, "Anthony Root")
        self.assertEqual(ws["A4"].value, "Week of 2026-11-08")
        self.assertEqual([ws.cell(8, c).value for c in range(1, 12)], labels[2:])
        self.assertEqual(str(ws["A9"].value), "2026-11-08")
        self.assertEqual(str(ws["B9"].value), "2")
        self.assertEqual(str(ws["K9"].value), "Shop")
        self.assertEqual(str(ws["A10"].value), "2026-11-09")
        self.assertEqual(str(ws["C10"].value), "3.5")
        self.assertEqual(str(ws["D10"].value), "40")
        self.assertEqual(str(ws["J10"].value), "60.00")
        self.assertEqual(ws["H8"].value, "Survery Hrs")
        for row in range(16, 31):
            for col in range(1, 12):
                self.assertIsNone(ws.cell(row, col).value, "%s,%s" % (row, col))
        self.assertEqual(ws["A32"].value, "Initials: AR")
        joined = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
        self.assertNotIn("CVH # work hours", joined)
        self.assertNotIn("Personal vechicle", joined)
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    self.assertNotEqual(cell.data_type, "f")
        self.assertEqual(s["anthony_timesheet_pdf_filename"](rec), "Anthony_Time_Sheet_Anthony_Root_2026-11-08.pdf")
        self.assertEqual(s["anthony_timesheet_xlsx_filename"](rec), "Anthony_Time_Sheet_Anthony_Root_2026-11-08.xlsx")

    def test_time_off_records_validation_grid_and_cancel_history(self):


        from datetime import date, time, datetime, timedelta
        from zoneinfo import ZoneInfo
        s = self.s
        self.assertEqual(s["TIME_OFF_SHEET_TITLE"], "Time Off")
        self.assertEqual(s["TIME_OFF_COLUMNS"], [
            "Timestamp", "Entry ID", "Action", "Employee", "Type",
            "Start Date", "End Date", "Start Time", "End Time", "Notes", "Status",
            "Project",
            "Holiday Name",
        ])
        self.assertEqual(
            s["TIME_OFF_TYPES"],
            ("Full day off", "Partial day", "Vacation", "Project", "Company Holiday"),
        )
        self.assertEqual(s["TIME_OFF_TYPE_HOLIDAY"], "Company Holiday")
        self.assertEqual(s["TIME_OFF_ALL_EMPLOYEES"], "All employees")
        self.assertEqual(s["TIME_OFF_PROJECTS"], ("BNSF", "Forestry", "WSFW", "West", "Basin", "Other"))
        self.assertEqual(s["TIME_OFF_TYPES"][:3], ("Full day off", "Partial day", "Vacation"))
        self.assertEqual(s["DRIVERS"], [
            "Robert Rackley",
            "Barry Markham",
            "Anthony Root",
            "Carl Mulvaney",
            "Ron Cline",
            "Gary Grant",
        ])
        self.assertNotIn("Skylar Fingerle", s["DRIVERS"])
        self.assertEqual(s["EMPLOYEES"][-1], "Skylar Fingerle")

        weeks = s["time_off_calendar_weeks"](2026, 11)
        self.assertEqual(weeks[0][0], date(2026, 11, 1))
        self.assertEqual(weeks[0][0].weekday(), 6)  # Sunday
        self.assertEqual(weeks[-1][1], date(2026, 11, 30))
        self.assertEqual(s["time_off_shift_month"](2026, 1, -1), (2025, 12))
        self.assertEqual(s["time_off_shift_month"](2026, 12, 1), (2027, 1))
        self.assertEqual(s["time_off_short_name"]("Ron Cline"), "Ron C.")
        self.assertEqual(s["parse_time_off_time"]("9:00 AM"), time(9, 0))
        self.assertEqual(s["format_time_off_time"]("9:00 AM"), "09:00")
        self.assertEqual(s["format_time_off_time_display"]("13:30"), "1:30 PM PT")

        today = date(2026, 11, 10)
        when = datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        full = s["build_time_off_record"](
            "Ron Cline", "Full day off", date(2026, 11, 20),
            notes="Family event", when=when, entry_id="TO-TEST-FULL", today=today,
        )
        self.assertEqual(full["Status"], "Active")
        self.assertEqual(full["Action"], "Create")
        self.assertEqual(full["Start Date"], "2026-11-20")
        self.assertEqual(full["End Date"], "2026-11-20")
        self.assertEqual(full["Start Time"], "")
        self.assertEqual(full["Notes"], "Family event")
        self.assertEqual(full["Project"], "")
        self.assertEqual(full["Holiday Name"], "")

        partial = s["build_time_off_record"](
            "Gary Grant", "Partial day", date(2026, 11, 12),
            start_time=time(9, 0), end_time=time(13, 0),
            when=when, entry_id="TO-TEST-PART", today=today,
        )
        self.assertEqual(partial["Start Time"], "09:00")
        self.assertEqual(partial["End Time"], "13:00")

        vacation = s["build_time_off_record"](
            "Skylar Fingerle", "Vacation", date(2026, 12, 20),
            end_date=date(2026, 12, 27), when=when, entry_id="TO-TEST-VAC", today=today,
        )
        self.assertEqual(vacation["Start Date"], "2026-12-20")
        self.assertEqual(vacation["End Date"], "2026-12-27")
        self.assertTrue(s["time_off_covers_date"](vacation, date(2026, 12, 20)))
        self.assertTrue(s["time_off_covers_date"](vacation, date(2026, 12, 27)))
        self.assertTrue(s["time_off_covers_date"](vacation, date(2026, 12, 23)))
        self.assertFalse(s["time_off_covers_date"](vacation, date(2026, 12, 19)))
        self.assertFalse(s["time_off_covers_date"](vacation, date(2026, 12, 28)))
        self.assertEqual(s["time_off_span_days"](date(2026, 12, 20), date(2026, 12, 27)), 8)

        with self.assertRaisesRegex(ValueError, "Employee is required"):
            s["build_time_off_record"]("", "Full day off", today, today=today)
        with self.assertRaisesRegex(ValueError, "Employee is required"):
            s["build_time_off_record"]("Not An Employee", "Full day off", today, today=today)
        with self.assertRaisesRegex(ValueError, "Type is required"):
            s["build_time_off_record"]("Ron Cline", "Sick", today, today=today)
        with self.assertRaisesRegex(ValueError, "Project is required"):
            s["build_time_off_record"]("Ron Cline", "Project", today, today=today)
        with self.assertRaisesRegex(ValueError, "Project is required"):
            s["build_time_off_record"]("Ron Cline", "Project", today, project="Hangar", today=today)
        for name in s["TIME_OFF_PROJECTS"]:
            saved = s["build_time_off_record"](
                "Barry Markham", "Project", date(2026, 11, 16),
                project=name, when=when, entry_id="TO-TEST-" + name, today=today,
            )
            self.assertEqual(saved["Type"], "Project")
            self.assertEqual(saved["Project"], name)
            self.assertEqual(saved["Start Date"], "2026-11-16")
            self.assertEqual(saved["End Date"], "2026-11-16")
            self.assertEqual(saved["Start Time"], "")
            self.assertEqual(
                s["time_off_summary_text"](saved),
                "Barry Markham — Project – " + name + " — 2026-11-16",
            )
            self.assertEqual(s["time_off_type_label"]("Project", name), "Project – " + name)
        project = s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 16),
            project="BNSF", notes="On the line", when=when, entry_id="TO-TEST-BNSF", today=today,
        )
        other = s["build_time_off_record"](
            "Robert Rackley", "Project", date(2026, 11, 17),
            project="Other", when=when, entry_id="TO-TEST-OTHER", today=today,
        )
        one_day = s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 16),
            end_date=date(2026, 11, 16), project="BNSF", today=today,
        )
        self.assertEqual(one_day["Start Date"], "2026-11-16")
        self.assertEqual(one_day["End Date"], "2026-11-16")
        multi = s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 16),
            end_date=date(2026, 11, 18), project="West", notes="On site",
            when=when, entry_id="TO-TEST-WEST-SPAN", today=today,
        )
        self.assertEqual(multi["Type"], "Project")
        self.assertEqual(multi["Project"], "West")
        self.assertEqual(multi["Start Date"], "2026-11-16")
        self.assertEqual(multi["End Date"], "2026-11-18")
        self.assertEqual(multi["Start Time"], "")
        self.assertEqual(multi["End Time"], "")
        self.assertEqual(multi["Holiday Name"], "")
        for day in (date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)):
            self.assertTrue(s["time_off_covers_date"](multi, day))
            self.assertEqual(
                [r["Entry ID"] for r in s["time_off_for_date"]([multi], day)],
                ["TO-TEST-WEST-SPAN"],
            )
        self.assertFalse(s["time_off_covers_date"](multi, date(2026, 11, 15)))
        self.assertFalse(s["time_off_covers_date"](multi, date(2026, 11, 19)))
        self.assertEqual(
            s["time_off_summary_text"](multi),
            "Barry Markham — Project – West — 2026-11-16 to 2026-11-18 — On site",
        )
        multi_grid = s["time_off_month_grid_markup"](2026, 11, [multi], today=today)
        for day_num in (16, 17, 18):
            self.assertIn(
                "<span class='daynum'>" + str(day_num) + "</span>"
                "<div class='ev toff-proj'>Barry M. — Project – West</div>",
                multi_grid,
            )
        self.assertNotIn("<span class='daynum'>15</span><div class='ev toff-proj'>", multi_grid)
        self.assertNotIn("<span class='daynum'>19</span><div class='ev toff-proj'>", multi_grid)
        cross = s["build_time_off_record"](
            "Robert Rackley", "Project", date(2026, 11, 30),
            end_date=date(2026, 12, 2), project="Forestry",
            when=when, entry_id="TO-TEST-CROSS", today=today,
        )
        nov_cross = s["time_off_month_grid_markup"](2026, 11, [cross], today=today)
        dec_cross = s["time_off_month_grid_markup"](2026, 12, [cross], today=today)
        self.assertEqual(nov_cross.count("Project – Forestry"), 1)
        self.assertIn(
            "<span class='daynum'>30</span><div class='ev toff-proj'>Robert R. — Project – Forestry</div>",
            nov_cross,
        )
        self.assertEqual(dec_cross.count("Project – Forestry"), 2)
        self.assertIn(
            "<span class='daynum'>1</span><div class='ev toff-proj'>Robert R. — Project – Forestry</div>",
            dec_cross,
        )
        self.assertIn(
            "<span class='daynum'>2</span><div class='ev toff-proj'>Robert R. — Project – Forestry</div>",
            dec_cross,
        )
        self.assertNotIn("<span class='daynum'>3</span><div class='ev toff-proj'>", dec_cross)
        with self.assertRaisesRegex(ValueError, "End date must be on or after"):
            s["build_time_off_record"](
                "Barry Markham", "Project", date(2026, 11, 18),
                end_date=date(2026, 11, 16), project="West", today=today,
            )
        with self.assertRaisesRegex(ValueError, "Project can be at most 180 days"):
            s["build_time_off_record"](
                "Barry Markham", "Project", today,
                end_date=today + timedelta(days=s["TIME_OFF_MAX_SPAN_DAYS"]),
                project="BNSF", today=today,
            )
        max_project = s["build_time_off_record"](
            "Barry Markham", "Project", today,
            end_date=today + timedelta(days=s["TIME_OFF_MAX_SPAN_DAYS"] - 1),
            project="Basin", today=today,
        )
        self.assertEqual(
            s["time_off_span_days"](s["time_off_start_date"](max_project), s["time_off_end_date"](max_project)),
            s["TIME_OFF_MAX_SPAN_DAYS"],
        )
        with self.assertRaisesRegex(ValueError, "Full day and partial day entries use a single date"):
            s["build_time_off_record"](
                "Ron Cline", "Full day off", date(2026, 11, 16),
                end_date=date(2026, 11, 18), today=today,
            )
        with self.assertRaisesRegex(ValueError, "Full day and partial day entries use a single date"):
            s["build_time_off_record"](
                "Ron Cline", "Partial day", date(2026, 11, 16),
                end_date=date(2026, 11, 18),
                start_time=time(9, 0), end_time=time(13, 0), today=today,
            )
        with self.assertRaisesRegex(ValueError, "End date must be on or after"):
            s["build_time_off_record"](
                "Ron Cline", "Vacation", date(2026, 12, 20), end_date=date(2026, 12, 19), today=today,
            )
        with self.assertRaisesRegex(ValueError, "End time must be after start time"):
            s["build_time_off_record"](
                "Ron Cline", "Partial day", today, start_time=time(13, 0), end_time=time(9, 0), today=today,
            )
        with self.assertRaisesRegex(ValueError, "Start and end times are required"):
            s["build_time_off_record"]("Ron Cline", "Partial day", today, today=today)
        with self.assertRaisesRegex(ValueError, "within about two years"):
            s["build_time_off_record"](
                "Ron Cline", "Full day off", date(2010, 1, 1), today=today,
            )
        long_end = today + __import__("datetime").timedelta(days=s["TIME_OFF_MAX_SPAN_DAYS"])
        # span of MAX+1 days should fail; start today, end today+180 is 181 days inclusive
        with self.assertRaisesRegex(ValueError, "at most 180 days"):
            s["build_time_off_record"](
                "Ron Cline", "Vacation", today,
                end_date=today + __import__("datetime").timedelta(days=s["TIME_OFF_MAX_SPAN_DAYS"]),
                today=today,
            )

        existing = [full, partial, vacation, project, other]
        with self.assertRaisesRegex(ValueError, "already listed"):
            s["build_time_off_record"](
                "Ron Cline", "Full day off", date(2026, 11, 20),
                when=when, today=today, existing=existing,
            )
        with self.assertRaisesRegex(ValueError, "already listed"):
            s["build_time_off_record"](
                "Barry Markham", "Project", date(2026, 11, 16),
                project="BNSF", when=when, today=today, existing=existing,
            )
        forestry = s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 16),
            project="Forestry", when=when, entry_id="TO-TEST-FORESTRY", today=today, existing=existing,
        )
        self.assertEqual(forestry["Project"], "Forestry")

        markup = s["time_off_month_grid_markup"](2026, 12, existing, today=today)
        self.assertIn("Skylar F.", markup)
        self.assertIn("Vacation", markup)
        self.assertIn(">20<", markup)
        self.assertIn(">27<", markup)
        self.assertIn(">23<", markup)
        nov = s["time_off_month_grid_markup"](2026, 11, existing, today=today)
        self.assertIn("Ron C.", nov)
        self.assertIn("Gary G.", nov)
        self.assertIn("9:00 AM–1:00 PM", nov)
        self.assertNotIn("Skylar F.", nov)
        filtered = s["time_off_month_grid_markup"](2026, 11, existing, today=today, employee="Ron Cline")
        self.assertIn("Ron C.", filtered)
        self.assertNotIn("Gary G.", filtered)
        project_grid = s["time_off_month_grid_markup"](2026, 11, existing + [forestry], today=today)
        self.assertIn("Barry M. — Project – BNSF", project_grid)
        self.assertIn("Barry M. — Project – Forestry", project_grid)
        self.assertIn("Robert R. — Project – Other", project_grid)
        self.assertIn("toff-proj", project_grid)
        self.assertIn("On the line", s["time_off_summary_text"](project))

        legacy = {
            "Employee": "Ron Cline",
            "Type": "Full day off",
            "Start Date": "2026-11-20",
            "End Date": "2026-11-20",
            "Status": "Active",
            "Entry ID": "TO-OLD",
            "Action": "Create",
        }
        self.assertNotIn("Project", legacy)
        self.assertEqual(s["time_off_summary_text"](legacy), "Ron Cline — Full day off — 2026-11-20")
        legacy_grid = s["time_off_month_grid_markup"](2026, 11, [legacy], today=today)
        self.assertIn("Ron C. — Full day", legacy_grid)
        self.assertNotIn("Project –", legacy_grid)
        self.assertTrue(s["time_off_duplicate_active"]([legacy], full))
        cancelled_project = s["build_time_off_cancel_record"](project, when=datetime(2026, 11, 10, 12, 0))
        self.assertEqual(cancelled_project["Project"], "BNSF")
        self.assertEqual(cancelled_project["Type"], "Project")
        self.assertIn("Project – BNSF", s["time_off_summary_text"](cancelled_project))

        cancelled = s["build_time_off_cancel_record"](full, when=datetime(2026, 11, 10, 10, 0))
        self.assertEqual(cancelled["Entry ID"], "TO-TEST-FULL")
        self.assertEqual(cancelled["Action"], "Cancel")
        self.assertEqual(cancelled["Status"], "Cancelled")
        self.assertEqual(cancelled["Start Date"], "2026-11-20")
        all_rows = existing + [cancelled]
        current = s["current_time_off_records"](all_rows)
        latest_full = s["latest_time_off_record"](all_rows, "TO-TEST-FULL")
        self.assertEqual(latest_full["Status"], "Cancelled")
        active = s["active_time_off_records"](all_rows)
        self.assertEqual(
            [r["Entry ID"] for r in active],
            ["TO-TEST-PART", "TO-TEST-BNSF", "TO-TEST-OTHER", "TO-TEST-VAC"],
        )
        self.assertFalse(any(s["time_off_covers_date"](r, date(2026, 11, 20)) for r in active))
        with self.assertRaisesRegex(ValueError, "already cancelled"):
            s["build_time_off_cancel_record"](cancelled)

    def test_timesheet_vacation_and_sick_on_standard_sheets_only(self):
        from datetime import date, datetime
        from io import BytesIO
        from zoneinfo import ZoneInfo
        import fitz
        from openpyxl import load_workbook
        s = self.s
        self.assertEqual(s["TIMESHEET_LEAVE_FIELDS"], ("Vacation Hours", "Sick Hours"))
        self.assertEqual(s["TIMESHEET_LEAVE_HOURS_MAX"], 24)
        self.assertEqual(s["TIMESHEET_WORKED_HOUR_FIELDS"], ("CVH Hours", "Forestry Hours", "BNSF Hours"))
        fields = [field for field, _label in s["TIMESHEET_DAY_FIELDS"]]
        self.assertEqual(fields, [
            "Location", "CVH Hours", "Forestry Hours", "BNSF Hours",
            "Vacation Hours", "Sick Hours", "Perdiem Rate", "Other",
        ])
        for day in s["TIMESHEET_DAYS"]:
            self.assertIn(day + " Vacation Hours", s["timesheet_columns"]())
            self.assertIn(day + " Sick Hours", s["timesheet_columns"]())
        anthony_cols = " ".join(s["anthony_timesheet_columns"]())
        self.assertNotIn("Vacation Hours", anthony_cols)
        self.assertNotIn("Sick Hours", anthony_cols)
        self.assertNotIn("Vacation Hours", " ".join(s["anthony_timesheet_template_labels"]()))
        self.assertNotIn("Sick Hours", " ".join(s["anthony_timesheet_template_labels"]()))
        self.assertNotIn("Ron Cline", s["TIMESHEET_EMPLOYEES"])
        self.assertNotIn("Anthony Root", s["TIMESHEET_EMPLOYEES"])

        when = datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        today = date(2026, 11, 11)
        base = s["build_timesheet_record"](
            "Robert Rackley", date(2026, 11, 8),
            day_values={
                "Sun": {"CVH Hours": "8", "Forestry Hours": "1", "BNSF Hours": "1"},
                "Mon": {"CVH Hours": "30"},
            },
            initials="RR",
            when=when, entry_id="TS-LEAVE-0", today=today,
        )
        self.assertEqual(base["Sun Vacation Hours"], "0")
        self.assertEqual(base["Sun Sick Hours"], "0")
        self.assertEqual(base["Mon CVH Hours"], "30")
        self.assertEqual(s["timesheet_weekly_hour_totals"](base)["Worked Hours"], 40)
        self.assertEqual(s["timesheet_weekly_hour_totals"](base)["Vacation Hours"], 0)
        self.assertEqual(s["timesheet_weekly_hour_totals"](base)["Sick Hours"], 0)
        self.assertEqual(s["timesheet_weekly_hour_totals"](base)["Total Hours Including Paid Leave"], 40)
        explicit_zero = s["build_timesheet_record"](
            "Robert Rackley", date(2026, 11, 8),
            day_values={
                "Sun": {
                    "CVH Hours": "8", "Forestry Hours": "1", "BNSF Hours": "1",
                    "Vacation Hours": 0, "Sick Hours": "0",
                },
                "Mon": {"CVH Hours": "30"},
            },
            initials="RR",
            when=when, entry_id="TS-LEAVE-0", today=today,
        )
        self.assertEqual(s["timesheet_content_hash"](base), s["timesheet_content_hash"](explicit_zero))
        self.assertTrue(s["timesheet_initials_match_current"](base, explicit_zero))

        rec = s["build_timesheet_record"](
            "Robert Rackley", date(2026, 11, 8),
            day_values={
                "Sun": {
                    "CVH Hours": "8", "Forestry Hours": "1", "BNSF Hours": "1",
                    "Vacation Hours": "4", "Sick Hours": "2",
                },
                "Mon": {"CVH Hours": "30", "Vacation Hours": 0, "Sick Hours": 0},
                "Tues": {"Vacation Hours": "24", "Sick Hours": "0.5"},
            },
            initials="RR",
            when=when, entry_id="TS-LEAVE-1", today=today,
        )
        self.assertEqual(rec["Sun Vacation Hours"], "4")
        self.assertEqual(rec["Sun Sick Hours"], "2")
        self.assertEqual(rec["Tues Vacation Hours"], "24")
        self.assertEqual(rec["Tues Sick Hours"], "0.5")
        self.assertEqual(rec["Mon Vacation Hours"], "0")
        totals = s["timesheet_weekly_hour_totals"](rec)
        self.assertEqual(totals["Worked Hours"], 40)
        self.assertEqual(totals["Vacation Hours"], 28)
        self.assertEqual(totals["Sick Hours"], 2.5)
        self.assertEqual(totals["Total Hours Including Paid Leave"], 70.5)
        self.assertEqual(s["timesheet_weekly_hour_totals"](base)["Worked Hours"], totals["Worked Hours"])
        self.assertTrue(s["timesheet_initials_valid"](rec))
        self.assertFalse(s["timesheet_initials_match_current"](base, rec))
        edited = dict(rec)
        edited["Sun Vacation Hours"] = "5"
        self.assertFalse(s["timesheet_initials_valid"](edited))

        with self.assertRaisesRegex(ValueError, "Vacation Hours must be a number"):
            s["build_timesheet_record"](
                "Skylar Fingerle", date(2026, 11, 8),
                day_values={"Wed": {"Vacation Hours": "nope"}},
                today=today,
            )
        with self.assertRaisesRegex(ValueError, "Sick Hours cannot be negative"):
            s["build_timesheet_record"](
                "Skylar Fingerle", date(2026, 11, 8),
                day_values={"Wed": {"Sick Hours": -1}},
                today=today,
            )
        with self.assertRaisesRegex(ValueError, "cannot be more than 24"):
            s["build_timesheet_record"](
                "Gary Grant", date(2026, 11, 8),
                day_values={"Fri": {"Vacation Hours": "24.5"}},
                today=today,
            )
        capped = s["build_timesheet_record"](
            "Gary Grant", date(2026, 11, 8),
            day_values={"Fri": {"Sick Hours": "24"}},
            today=today,
        )
        self.assertEqual(capped["Fri Sick Hours"], "24")
        money = s["build_timesheet_record"](
            "Barry Markham", date(2026, 11, 8),
            day_values={"Sun": {"Vacation Hours": "8"}},
            parts="10", fuel="5", other_reimb="2.25",
            today=today,
        )
        self.assertEqual(money["Reimb Total"], "17.25")
        with self.assertRaisesRegex(ValueError, "does not have a time sheet"):
            s["build_timesheet_record"]("Ron Cline", date(2026, 11, 8), today=today)
        with self.assertRaisesRegex(ValueError, "does not have a time sheet"):
            s["build_timesheet_record"]("Anthony Root", date(2026, 11, 8), today=today)

        pdf = s["build_timesheet_pdf"](rec)
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = fitz.open(stream=pdf, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        bottoms = []
        for block in doc[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                bottoms.append(line["bbox"][3])
        self.assertTrue(bottoms)
        self.assertLess(max(bottoms), 770)
        text = "\n".join(page.get_text() for page in doc).replace("\n", " ")
        doc.close()
        for label in s["timesheet_hour_total_lines"](rec):
            self.assertIn(label, text, label)
        self.assertIn("Vacation Hours", text)
        self.assertIn("Sick Hours", text)

        xlsx = s["build_timesheet_xlsx"](rec)
        grid = load_workbook(BytesIO(xlsx)).active
        self.assertEqual(grid["B14"].value, "Vacation Hours")
        self.assertEqual(grid["B15"].value, "Sick Hours")
        self.assertEqual(str(grid["C14"].value), "4")
        self.assertEqual(str(grid["C15"].value), "2")
        self.assertEqual(str(grid["E14"].value), "24")
        self.assertEqual(str(grid["C9"].value), "8")
        joined = " ".join(str(c.value) for row in grid.iter_rows() for c in row if c.value)
        self.assertIn("Worked hours: 40", joined)
        self.assertIn("Vacation: 28", joined)
        self.assertIn("Sick: 2.5", joined)
        self.assertIn("Total hours including paid leave: 70.5", joined)
        self.assertIn("CVH # work hours", joined)
        self.assertIn("Personal vechicle usage will be reimbursed at", joined)

        old_header = [c for c in s["timesheet_columns"]() if c not in set(s["timesheet_leave_columns"]())]
        self.assertNotIn("Sun Vacation Hours", old_header)
        book = FakeSpreadsheet()
        sheet = book.add_worksheet("Time Sheets", 50, 20)
        sheet.append_row(old_header)
        sheet.append_row([
            "" if isinstance(base.get(col), (list, dict)) else str(base.get(col, ""))
            for col in old_header
        ])
        loaded = s["load_timesheet_records_readonly"](book)
        self.assertEqual(s["timesheet_leave_hours"](loaded[0].get("Sun Vacation Hours")), 0)
        self.assertEqual(s["timesheet_leave_hours"](loaded[0].get("Sat Sick Hours")), 0)
        self.assertEqual(s["timesheet_weekly_hour_totals"](loaded[0])["Worked Hours"], 40)
        self.assertEqual(s["timesheet_weekly_hour_totals"](loaded[0])["Vacation Hours"], 0)
        self.assertTrue(s["timesheet_initials_valid"](loaded[0]))
        header_before = list(sheet.rows[0])
        self.assertTrue(s["ensure_timesheet_leave_columns"](sheet))
        self.assertEqual(sheet.rows[0][:len(header_before)], header_before)
        for col in s["timesheet_leave_columns"]():
            self.assertEqual(sheet.rows[0].count(col), 1)
        self.assertEqual(sheet.rows[1][header_before.index("Sun CVH Hours")], "8")
        self.assertEqual(sheet.rows[1][header_before.index("Mon CVH Hours")], "30")
        _ws, created = s["ensure_timesheets_worksheet"](book)
        self.assertFalse(created)
        self.assertEqual(sheet.rows[0].count("Sun Vacation Hours"), 1)
        writes_after = len(sheet.writes)
        self.assertFalse(s["ensure_timesheet_leave_columns"](sheet))
        self.assertEqual(len(sheet.writes), writes_after)

        saved = s["build_timesheet_record"](
            "Robert Rackley", date(2026, 11, 15),
            day_values={"Sun": {"CVH Hours": "6", "Vacation Hours": "3", "Sick Hours": "1"}},
            initials="RR",
            when=when, entry_id="TS-LEAVE-NEW", today=date(2026, 11, 16),
        )
        s["save_timesheet_record"](saved, book)
        header = sheet.rows[0]
        self.assertEqual(header.count("Sun Vacation Hours"), 1)
        new_row = sheet.rows[-1]
        self.assertEqual(new_row[header.index("Sun Vacation Hours")], "3")
        self.assertEqual(new_row[header.index("Sun Sick Hours")], "1")
        self.assertEqual(new_row[header.index("Sun CVH Hours")], "6")
        reloaded = s["load_timesheet_records_readonly"](book)
        old = [row for row in reloaded if row["Entry ID"] == "TS-LEAVE-0"][0]
        new = [row for row in reloaded if row["Entry ID"] == "TS-LEAVE-NEW"][0]
        self.assertEqual(s["timesheet_leave_hours"](old.get("Sun Vacation Hours")), 0)
        self.assertEqual(old["Sun CVH Hours"], "8")
        self.assertTrue(s["timesheet_initials_valid"](old))
        self.assertEqual(new["Sun Vacation Hours"], "3")
        self.assertEqual(new["Sun Sick Hours"], "1")
        self.assertEqual(s["timesheet_weekly_hour_totals"](new)["Worked Hours"], 6)
        self.assertEqual(s["timesheet_weekly_hour_totals"](new)["Total Hours Including Paid Leave"], 10)
        self.assertTrue(s["timesheet_initials_valid"](new))
        self.assertEqual(book.sheet1.writes, [])
        self.assertNotIn("Anthony Time Sheets", book.sheets)

    def test_timesheet_entry_hour_summary_rows(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        s = self.s
        when = datetime(2026, 11, 11, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        today = date(2026, 11, 11)
        rec = s["build_timesheet_record"](
            "Robert Rackley", date(2026, 11, 8),
            day_values={
                "Sun": {
                    "CVH Hours": "8", "Forestry Hours": "1", "BNSF Hours": "1",
                    "Vacation Hours": "4", "Sick Hours": "2",
                },
                "Mon": {"CVH Hours": "30", "Vacation Hours": 0, "Sick Hours": 0},
                "Tues": {"Vacation Hours": "24", "Sick Hours": "0.5"},
            },
            initials="RR",
            when=when, entry_id="TS-LEAVE-1", today=today,
        )
        sun = s["timesheet_day_hour_breakdown"](rec, "Sun")
        self.assertEqual(sun, {
            "CVH": 8.0, "Forestry": 1.0, "BNSF": 1.0,
            "Vacation": 4.0, "Sick": 2.0, "Worked": 10.0, "Total": 16.0,
        })
        mon = s["timesheet_day_hour_breakdown"](rec, "Mon")
        self.assertEqual(mon["CVH"], 30.0)
        self.assertEqual(mon["Worked"], 30.0)
        self.assertEqual(mon["Total"], 30.0)
        tues = s["timesheet_day_hour_breakdown"](rec, "Tues")
        self.assertEqual(tues["Worked"], 0.0)
        self.assertEqual(tues["Vacation"], 24.0)
        self.assertEqual(tues["Sick"], 0.5)
        self.assertEqual(tues["Total"], 24.5)
        wed = s["timesheet_day_hour_breakdown"](rec, "Wed")
        self.assertEqual(wed["Total"], 0.0)
        self.assertEqual(s["timesheet_day_hour_breakdown"]({}, "Fri")["Total"], 0.0)

        dates = s["timesheet_day_dates"](date(2026, 11, 8), today=today)
        rows = s["timesheet_hour_summary_rows"](rec, dates=dates)
        self.assertEqual(len(rows), 8)
        self.assertEqual([row["Day"] for row in rows], list(s["TIMESHEET_DAYS"]) + ["Week Total"])
        self.assertEqual(rows[0]["Date"], "2026-11-08")
        self.assertEqual(rows[6]["Date"], "2026-11-14")
        self.assertEqual(rows[7]["Day"], "Week Total")
        self.assertEqual(rows[7]["Date"], "")
        week = rows[7]
        totals = s["timesheet_weekly_hour_totals"](rec)
        self.assertEqual(week["CVH"], 38.0)
        self.assertEqual(week["Forestry"], 1.0)
        self.assertEqual(week["BNSF"], 1.0)
        self.assertEqual(week["Vacation"], totals["Vacation Hours"])
        self.assertEqual(week["Sick"], totals["Sick Hours"])
        self.assertEqual(week["Worked"], totals["Worked Hours"])
        self.assertEqual(week["Total"], totals["Total Hours Including Paid Leave"])
        self.assertEqual(week["Worked"], 40)
        self.assertEqual(week["Total"], 70.5)

        blank = s["timesheet_hour_summary_rows"](None)
        self.assertEqual(len(blank), 8)
        self.assertEqual(blank[0]["Date"], "")
        self.assertEqual(blank[7]["Total"], 0.0)
        display = s["timesheet_hour_summary_display_rows"](rows)
        self.assertEqual(display[0]["Day"], "Sun 2026-11-08")
        self.assertEqual(display[0]["CVH"], "8")
        self.assertEqual(display[0]["Worked"], "10")
        self.assertEqual(display[0]["Total"], "16")
        self.assertEqual(display[2]["Day"], "Tues 2026-11-10")
        self.assertEqual(display[2]["Sick"], "0.5")
        self.assertEqual(display[2]["Total"], "24.5")
        self.assertEqual(display[3]["Day"], "Wed 2026-11-11")
        self.assertEqual(display[3]["Total"], "0")
        self.assertEqual(display[7]["Day"], "Week Total")
        self.assertEqual(display[7]["Worked"], "40")
        self.assertEqual(display[7]["Total"], "70.5")
        html = s["timesheet_hour_summary_html"](rows)
        self.assertIn("Week Total", html)
        self.assertIn(">40<", html)
        self.assertIn(">70.5<", html)
        self.assertIn("Vacation", html)
        self.assertIn("Total", html)
        self.assertIn("Vac", html)
        self.assertIn("Wkd", html)
        self.assertIn("Tot", html)
        self.assertIn("Sun", html)
        self.assertIn("11/08", html)
        self.assertEqual(s["timesheet_hour_summary_short_date"]("Sun 2026-11-08"), "Sun 11/08")
        self.assertEqual(s["timesheet_hour_summary_short_date"]("2026-11-14"), "11/14")
        self.assertIn("max-width:100%", html)
        self.assertEqual(
            s["timesheet_day_expander_title"]("Mon", date(2026, 11, 16), 8),
            "Mon  2026-11-16 — 8 hrs",
        )
        self.assertEqual(
            s["timesheet_day_expander_title"]("Tues", dates[2], tues["Total"]),
            "Tues  2026-11-10 — 24.5 hrs",
        )
        self.assertEqual(
            s["timesheet_day_expander_title"]("Wed", dates[3], 0),
            "Wed  2026-11-11",
        )


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

    def test_time_off_save_and_readonly_load_leave_headers_alone(self):
        from datetime import date, time, datetime
        from zoneinfo import ZoneInfo
        frat_writes = list(self.book.sheet1.writes)
        self.assertEqual(self.s["load_time_off_records_readonly"](self.book), [])
        self.assertNotIn("Time Off", self.book.sheets)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()

        when = datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        record = self.s["build_time_off_record"](
            "Carl Mulvaney", "Vacation", date(2026, 12, 1), end_date=date(2026, 12, 5),
            notes="Listed vacation", when=when, entry_id="TO-SHEET-1", today=date(2026, 11, 10),
        )
        self.s["save_time_off_record"](record, self.book)
        self.assertIn("Time Off", self.book.sheets)
        ws = self.book.sheets["Time Off"]
        self.assertEqual(ws.rows[0], self.s["TIME_OFF_COLUMNS"])
        self.assertEqual(ws.rows[1][ws.rows[0].index("Employee")], "Carl Mulvaney")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Type")], "Vacation")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Start Date")], "2026-12-01")
        self.assertEqual(ws.rows[1][ws.rows[0].index("End Date")], "2026-12-05")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Status")], "Active")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Project")], "")
        header = list(ws.rows[0])
        writes_after_save = list(ws.writes)
        loaded = self.s["load_time_off_records_readonly"](self.book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Employee"], "Carl Mulvaney")
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(ws.writes, writes_after_save)

        cancelled = self.s["build_time_off_cancel_record"](
            loaded[0], when=datetime(2026, 11, 10, 11, 0, tzinfo=ZoneInfo("America/Los_Angeles")),
        )
        self.s["save_time_off_record"](cancelled, self.book)
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(len(ws.rows), 3)
        self.assertEqual(ws.rows[2][ws.rows[0].index("Action")], "Cancel")
        self.assertEqual(ws.rows[2][ws.rows[0].index("Status")], "Cancelled")
        self.assertEqual(ws.rows[2][ws.rows[0].index("Entry ID")], "TO-SHEET-1")
        again = self.s["load_time_off_records_readonly"](self.book)
        latest = self.s["latest_time_off_record"](again, "TO-SHEET-1")
        self.assertEqual(latest["Status"], "Cancelled")
        self.assertEqual(self.s["active_time_off_records"](again), [])
        second, created_again = self.s["ensure_time_off_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertEqual(second.rows[0], header)
        self.assertNotIn("Equipment", self.book.sheets)
        self.assertNotIn("Yearly Items", self.book.sheets)
        self._assert_frat_untouched()

    def test_time_off_ensure_does_not_alter_an_existing_custom_header(self):
        ws = self.book.add_worksheet("Time Off", 20, 12)
        custom = list(self.s["TIME_OFF_COLUMNS"]) + ["Extra"]
        ws.append_row(custom)
        writes = list(ws.writes)
        out, created = self.s["ensure_time_off_worksheet"](self.book)
        self.assertFalse(created)
        self.assertIs(out, ws)
        self.assertEqual(ws.rows[0], custom)
        self.assertEqual(ws.writes, writes)
        self._assert_frat_untouched()

    def test_time_off_legacy_rows_keep_blank_project_and_new_rows_store_choice(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        legacy_header = [
            "Timestamp", "Entry ID", "Action", "Employee", "Type",
            "Start Date", "End Date", "Start Time", "End Time", "Notes", "Status",
        ]
        self.assertNotIn("Project", legacy_header)
        ws = self.book.add_worksheet("Time Off", 20, 12)
        ws.append_row(legacy_header + ["Extra"])
        ws.append_row([
            "2026-11-01 09:00:00", "TO-LEGACY", "Create", "Ron Cline", "Full day off",
            "2026-11-20", "2026-11-20", "", "", "Family event", "Active", "keep-me",
        ])
        loaded = self.s["load_time_off_records_readonly"](self.book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["Type"], "Full day off")
        self.assertEqual(loaded[0]["Project"], "")
        self.assertEqual(loaded[0]["Notes"], "Family event")
        self.assertEqual(
            self.s["time_off_summary_text"](loaded[0]),
            "Ron Cline — Full day off — 2026-11-20 — Family event",
        )
        header_before = list(ws.rows[0])
        self.assertTrue(self.s["ensure_time_off_project_column"](ws))
        self.assertEqual(ws.rows[0][:len(header_before)], header_before)
        self.assertEqual(ws.rows[0][-1], "Project")
        self.assertEqual(ws.rows[1][header_before.index("Extra")], "keep-me")
        self.assertEqual(ws.rows[1][header_before.index("Employee")], "Ron Cline")
        _ws, created = self.s["ensure_time_off_worksheet"](self.book)
        self.assertFalse(created)
        self.assertEqual(ws.rows[0].count("Project"), 1)
        writes_after = len(ws.writes)
        self.assertFalse(self.s["ensure_time_off_project_column"](ws))
        self.assertEqual(len(ws.writes), writes_after)

        when = datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        record = self.s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 16),
            project="Basin", notes="Listed", when=when, entry_id="TO-NEW-PROJECT",
            today=date(2026, 11, 10),
        )
        self.s["save_time_off_record"](record, self.book)
        header = ws.rows[0]
        new_row = ws.rows[-1]
        self.assertEqual(new_row[header.index("Type")], "Project")
        self.assertEqual(new_row[header.index("Project")], "Basin")
        self.assertEqual(new_row[header.index("Employee")], "Barry Markham")
        self.assertEqual(header[:len(header_before)], header_before)
        again = self.s["load_time_off_records_readonly"](self.book)
        old = self.s["latest_time_off_record"](again, "TO-LEGACY")
        new = self.s["latest_time_off_record"](again, "TO-NEW-PROJECT")
        self.assertEqual(old["Project"], "")
        self.assertEqual(old["Type"], "Full day off")
        self.assertEqual(old.get("Extra"), "keep-me")
        self.assertEqual(new["Project"], "Basin")
        self.assertEqual(new["Start Date"], "2026-11-16")
        self.assertEqual(new["End Date"], "2026-11-16")
        self.assertIn("Project – Basin", self.s["time_off_summary_text"](new))
        self.assertNotIn("Project –", self.s["time_off_summary_text"](old))
        self.assertEqual(old["Holiday Name"], "")
        self.assertEqual(new["Holiday Name"], "")
        self.assertEqual(ws.rows[0][-1], "Holiday Name")
        self.assertEqual(header[:len(header_before)], header_before)
        span = self.s["build_time_off_record"](
            "Barry Markham", "Project", date(2026, 11, 18),
            end_date=date(2026, 11, 20), project="BNSF", notes="Line",
            when=when, entry_id="TO-SPAN-PROJECT", today=date(2026, 11, 10),
        )
        self.s["save_time_off_record"](span, self.book)
        header = ws.rows[0]
        span_row = ws.rows[-1]
        self.assertEqual(span_row[header.index("Type")], "Project")
        self.assertEqual(span_row[header.index("Project")], "BNSF")
        self.assertEqual(span_row[header.index("Holiday Name")], "")
        self.assertEqual(span_row[header.index("Start Date")], "2026-11-18")
        self.assertEqual(span_row[header.index("End Date")], "2026-11-20")
        self.assertEqual(span_row[header.index("Start Time")], "")
        self.assertEqual(span_row[header.index("End Time")], "")
        loaded_span = self.s["latest_time_off_record"](
            self.s["load_time_off_records_readonly"](self.book), "TO-SPAN-PROJECT",
        )
        self.assertEqual(loaded_span["Start Date"], "2026-11-18")
        self.assertEqual(loaded_span["End Date"], "2026-11-20")
        for day in (date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 20)):
            self.assertTrue(self.s["time_off_covers_date"](loaded_span, day))
        self.assertFalse(self.s["time_off_covers_date"](loaded_span, date(2026, 11, 17)))
        self.assertFalse(self.s["time_off_covers_date"](loaded_span, date(2026, 11, 21)))
        self._assert_frat_untouched()

    def test_company_holiday_is_one_entry_for_every_employee(self):
        from datetime import date, datetime, timedelta
        from zoneinfo import ZoneInfo
        s = self.s
        today = date(2026, 11, 10)
        when = datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.assertEqual(s["TIME_OFF_TYPES"][-1], "Company Holiday")
        self.assertEqual(s["TIME_OFF_COLUMNS"][-1], "Holiday Name")
        self.assertEqual(s["TIME_OFF_COLUMNS"][-2], "Project")

        with self.assertRaisesRegex(ValueError, "Holiday name is required"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", today, end_date=today, today=today,
            )
        with self.assertRaisesRegex(ValueError, "Holiday name is required"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", today, end_date=today,
                holiday_name="   ", today=today,
            )
        with self.assertRaisesRegex(ValueError, "Employee is required"):
            s["build_time_off_record"](
                "All employees", "Full day off", today, today=today,
            )
        with self.assertRaisesRegex(ValueError, "End date is required"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", today, holiday_name="Thanksgiving", today=today,
            )
        with self.assertRaisesRegex(ValueError, "End date must be on or after"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", date(2026, 12, 26),
                end_date=date(2026, 12, 24), holiday_name="Christmas", today=today,
            )
        with self.assertRaisesRegex(ValueError, "at most 180 days"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", today,
                end_date=today + timedelta(days=s["TIME_OFF_MAX_SPAN_DAYS"]),
                holiday_name="Long break", today=today,
            )

        thanksgiving = s["build_time_off_record"](
            "All employees", "Company Holiday", date(2026, 11, 26),
            end_date=date(2026, 11, 26), holiday_name="Thanksgiving",
            when=when, entry_id="TO-HOLIDAY-1", today=today,
        )
        self.assertEqual(thanksgiving["Employee"], "All employees")
        self.assertEqual(thanksgiving["Type"], "Company Holiday")
        self.assertEqual(thanksgiving["Holiday Name"], "Thanksgiving")
        self.assertEqual(thanksgiving["Project"], "")
        self.assertEqual(thanksgiving["Start Date"], "2026-11-26")
        self.assertEqual(thanksgiving["End Date"], "2026-11-26")
        self.assertEqual(thanksgiving["Start Time"], "")
        self.assertEqual(
            s["time_off_summary_text"](thanksgiving),
            "All employees — 🎉 CVH Holiday – Thanksgiving — 2026-11-26",
        )
        self.assertEqual(
            s["time_off_type_label"]("Company Holiday", holiday_name="Thanksgiving"),
            "🎉 CVH Holiday – Thanksgiving",
        )

        christmas = s["build_time_off_record"](
            "All employees", "Company Holiday", date(2026, 12, 24),
            end_date=date(2026, 12, 26), holiday_name="Christmas",
            when=when, entry_id="TO-HOLIDAY-WEEK", today=today,
        )
        self.assertEqual(
            s["time_off_summary_text"](christmas),
            "All employees — 🎉 CVH Holiday – Christmas — 2026-12-24 to 2026-12-26",
        )
        for day in (date(2026, 12, 24), date(2026, 12, 25), date(2026, 12, 26)):
            self.assertTrue(s["time_off_covers_date"](christmas, day))
        self.assertFalse(s["time_off_covers_date"](christmas, date(2026, 12, 23)))
        self.assertFalse(s["time_off_covers_date"](christmas, date(2026, 12, 27)))

        new_year = s["build_time_off_record"](
            "All employees", "Company Holiday", date(2026, 12, 30),
            end_date=date(2027, 1, 1), holiday_name="New Year",
            when=when, entry_id="TO-HOLIDAY-NY", today=today,
        )
        ron = s["build_time_off_record"](
            "Ron Cline", "Full day off", date(2026, 12, 24),
            when=when, entry_id="TO-RON-DAY", today=today,
        )
        rows = [thanksgiving, christmas, new_year, ron]
        with self.assertRaisesRegex(ValueError, "already listed"):
            s["build_time_off_record"](
                "All employees", "Company Holiday", date(2026, 11, 26),
                end_date=date(2026, 11, 26), holiday_name="Thanksgiving",
                today=today, existing=rows,
            )
        other_name = s["build_time_off_record"](
            "All employees", "Company Holiday", date(2026, 11, 26),
            end_date=date(2026, 11, 26), holiday_name="Office closed",
            when=when, entry_id="TO-HOLIDAY-OTHER", today=today, existing=rows,
        )
        self.assertEqual(other_name["Holiday Name"], "Office closed")

        dec = s["time_off_month_grid_markup"](2026, 12, rows, today=today)
        self.assertEqual(dec.count("<div class='ev toff-hol'>"), 5)
        self.assertIn("All employees — 🎉 CVH Holiday – Christmas", dec)
        self.assertIn("All employees — 🎉 CVH Holiday – New Year", dec)
        self.assertIn("Ron C.", dec)
        self.assertNotIn("Thanksgiving", dec)
        jan = s["time_off_month_grid_markup"](2027, 1, rows, today=today)
        self.assertEqual(jan.count("<div class='ev toff-hol'>"), 1)
        self.assertIn("🎉 CVH Holiday – New Year", jan)
        self.assertNotIn("Christmas", jan)
        nov = s["time_off_month_grid_markup"](2026, 11, rows, today=today)
        self.assertEqual(nov.count("<div class='ev toff-hol'>"), 1)
        self.assertIn("🎉 CVH Holiday – Thanksgiving", nov)

        for person in s["EMPLOYEES"]:
            month_rows = s["time_off_for_month"](rows, 2026, 12, employee=person)
            self.assertIn("TO-HOLIDAY-WEEK", [r["Entry ID"] for r in month_rows])
            self.assertIn("TO-HOLIDAY-NY", [r["Entry ID"] for r in month_rows])
            shown = s["time_off_for_date"](rows, date(2026, 12, 25), employee=person)
            self.assertEqual([r["Entry ID"] for r in shown], ["TO-HOLIDAY-WEEK"])
            grid = s["time_off_month_grid_markup"](2026, 12, rows, today=today, employee=person)
            self.assertIn("🎉 CVH Holiday – Christmas", grid)
            self.assertIn("🎉 CVH Holiday – New Year", grid)
        ron_only = s["time_off_month_grid_markup"](2026, 12, rows, today=today, employee="Ron Cline")
        self.assertIn("Ron C.", ron_only)
        gary_only = s["time_off_month_grid_markup"](2026, 12, rows, today=today, employee="Gary Grant")
        self.assertNotIn("Ron C.", gary_only)
        self.assertIn("All employees — 🎉 CVH Holiday – Christmas", gary_only)
        self.assertTrue(s["time_off_applies_to_filter"](christmas, "Skylar Fingerle"))
        self.assertFalse(s["time_off_applies_to_filter"](ron, "Gary Grant"))

        escaped = s["build_time_off_record"](
            "All employees", "Company Holiday", date(2026, 11, 27),
            end_date=date(2026, 11, 27), holiday_name="Tom & Jerry",
            when=when, entry_id="TO-HOLIDAY-ESC", today=today,
        )
        escaped_grid = s["time_off_month_grid_markup"](2026, 11, [escaped], today=today)
        self.assertIn("Tom &amp; Jerry", escaped_grid)
        self.assertNotIn("Tom & Jerry", escaped_grid)

        legacy = {
            "Employee": "Ron Cline",
            "Type": "Full day off",
            "Start Date": "2026-11-20",
            "End Date": "2026-11-20",
            "Status": "Active",
            "Entry ID": "TO-OLD",
            "Action": "Create",
        }
        self.assertNotIn("Holiday Name", legacy)
        self.assertNotIn("Project", legacy)
        self.assertEqual(s["time_off_summary_text"](legacy), "Ron Cline — Full day off — 2026-11-20")
        legacy_grid = s["time_off_month_grid_markup"](2026, 11, [legacy], today=today)
        self.assertIn("Ron C. — Full day", legacy_grid)
        self.assertNotIn("CVH Holiday", legacy_grid)
        self.assertNotIn("🎉", legacy_grid)

        cancelled = s["build_time_off_cancel_record"](thanksgiving, when=datetime(2026, 11, 11, 8, 0))
        self.assertEqual(cancelled["Holiday Name"], "Thanksgiving")
        self.assertEqual(cancelled["Employee"], "All employees")
        self.assertEqual(cancelled["Status"], "Cancelled")
        active = s["active_time_off_records"]([thanksgiving, cancelled])
        self.assertEqual(active, [])
        for person in ("Ron Cline", "Gary Grant"):
            self.assertEqual(
                s["time_off_for_date"]([thanksgiving, cancelled], date(2026, 11, 26), employee=person),
                [],
            )
            cancelled_month = s["time_off_for_month"](
                [thanksgiving, cancelled], 2026, 11, employee=person, include_cancelled=True,
            )
            self.assertEqual(cancelled_month[0]["Status"], "Cancelled")
            self.assertIn("Thanksgiving", s["time_off_summary_text"](cancelled_month[0]))

        # A sheet saved before Holiday Name (and before Project) keeps its header order.
        legacy_header = [
            "Timestamp", "Entry ID", "Action", "Employee", "Type",
            "Start Date", "End Date", "Start Time", "End Time", "Notes", "Status",
        ]
        ws = self.book.add_worksheet("Time Off", 20, 12)
        ws.append_row(legacy_header + ["Extra"])
        ws.append_row([
            "2026-11-01 09:00:00", "TO-LEGACY", "Create", "Ron Cline", "Full day off",
            "2026-11-20", "2026-11-20", "", "", "Family event", "Active", "keep-me",
        ])
        loaded = s["load_time_off_records_readonly"](self.book)
        self.assertEqual(loaded[0]["Holiday Name"], "")
        self.assertEqual(loaded[0]["Project"], "")
        self.assertEqual(loaded[0]["Type"], "Full day off")
        header_before = list(ws.rows[0])
        _ws, created = s["ensure_time_off_worksheet"](self.book)
        self.assertFalse(created)
        self.assertEqual(ws.rows[0][:len(header_before)], header_before)
        self.assertEqual(ws.rows[0][-2], "Project")
        self.assertEqual(ws.rows[0][-1], "Holiday Name")
        self.assertEqual(ws.rows[1][header_before.index("Extra")], "keep-me")
        s["save_time_off_record"](christmas, self.book)
        self.assertEqual(len(ws.rows), 3)
        saved_row = ws.rows[-1]
        header = ws.rows[0]
        self.assertEqual(saved_row[header.index("Employee")], "All employees")
        self.assertEqual(saved_row[header.index("Type")], "Company Holiday")
        self.assertEqual(saved_row[header.index("Holiday Name")], "Christmas")
        self.assertEqual(saved_row[header.index("Start Date")], "2026-12-24")
        self.assertEqual(saved_row[header.index("End Date")], "2026-12-26")
        self.assertEqual(saved_row[header.index("Project")], "")
        again = s["load_time_off_records_readonly"](self.book)
        old = s["latest_time_off_record"](again, "TO-LEGACY")
        new = s["latest_time_off_record"](again, "TO-HOLIDAY-WEEK")
        self.assertEqual(old["Holiday Name"], "")
        self.assertEqual(old["Project"], "")
        self.assertEqual(old.get("Extra"), "keep-me")
        self.assertEqual(new["Holiday Name"], "Christmas")
        self.assertEqual(new["Employee"], "All employees")
        self.assertEqual(
            [r["Entry ID"] for r in s["time_off_for_date"](again, date(2026, 12, 25), employee="Anthony Root")],
            ["TO-HOLIDAY-WEEK"],
        )
        self._assert_frat_untouched()

        # A sheet that already has Project appends Holiday Name without moving Project.
        book = FakeSpreadsheet()
        project_header = legacy_header + ["Project"]
        ws2 = book.add_worksheet("Time Off", 20, 14)
        ws2.append_row(project_header)
        ws2.append_row([
            "2026-11-02 09:00:00", "TO-PROJ", "Create", "Barry Markham", "Project",
            "2026-11-16", "2026-11-16", "", "", "", "Active", "BNSF",
        ])
        self.assertFalse(s["ensure_time_off_project_column"](ws2))
        self.assertTrue(s["ensure_time_off_holiday_name_column"](ws2))
        self.assertEqual(ws2.rows[0][:len(project_header)], project_header)
        self.assertEqual(ws2.rows[0][-1], "Holiday Name")
        self.assertFalse(s["ensure_time_off_holiday_name_column"](ws2))
        loaded_project = s["load_time_off_records_readonly"](book)
        self.assertEqual(loaded_project[0]["Project"], "BNSF")
        self.assertEqual(loaded_project[0]["Holiday Name"], "")
        self.assertNotIn("CVH Holiday", s["time_off_summary_text"](loaded_project[0]))

    def test_timesheet_save_and_readonly_load_leave_headers_alone(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        frat_writes = list(self.book.sheet1.writes)
        self.assertEqual(self.s["load_timesheet_records_readonly"](self.book), [])
        self.assertNotIn("Time Sheets", self.book.sheets)
        self._assert_frat_untouched()

        when = datetime(2026, 11, 11, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        record = self.s["build_timesheet_record"](
            "Barry Markham", date(2026, 11, 8),
            day_values={"Sun": {"Location": "Yard", "CVH Hours": "4"}},
            initials="BM",
            when=when, entry_id="TS-SHEET-1", today=date(2026, 11, 11),
        )
        self.s["save_timesheet_record"](record, self.book)
        self.assertIn("Time Sheets", self.book.sheets)
        ws = self.book.sheets["Time Sheets"]
        self.assertEqual(ws.rows[0], self.s["timesheet_columns"]())
        self.assertEqual(ws.rows[1][ws.rows[0].index("Employee")], "Barry Markham")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Week Of")], "2026-11-08")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Sun Location")], "Yard")
        self.assertEqual(ws.rows[1][ws.rows[0].index("Initials")], "BM")
        header = list(ws.rows[0])
        writes_after = list(ws.writes)
        loaded = self.s["load_timesheet_records_readonly"](self.book)
        self.assertEqual(len(loaded), 1)
        latest = self.s["latest_timesheet_record"](loaded, "Barry Markham", date(2026, 11, 10))
        self.assertEqual(latest["Sun CVH Hours"], "4")
        self.assertTrue(self.s["timesheet_initials_valid"](latest))
        self.assertEqual(ws.rows[0], header)
        self.assertEqual(ws.writes, writes_after)
        second, created_again = self.s["ensure_timesheets_worksheet"](self.book)
        self.assertFalse(created_again)
        self.assertEqual(second.rows[0], header)
        self.assertNotIn("Yearly Items", self.book.sheets)
        self.assertEqual(self.book.sheet1.writes, frat_writes)
        self._assert_frat_untouched()

    def test_timesheet_ensure_does_not_alter_an_existing_custom_header(self):
        ws = self.book.add_worksheet("Time Sheets", 20, 20)
        custom = list(self.s["timesheet_columns"]()) + ["Extra"]
        ws.append_row(custom)
        writes = list(ws.writes)
        out, created = self.s["ensure_timesheets_worksheet"](self.book)
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

    def test_employees_header_navigation_and_blank_placeholders(self):
        from streamlit.testing.v1 import AppTest
        expected = [
            "Ron Cline",
            "Carl Mulvaney",
            "Anthony Root",
            "Barry Markham",
            "Robert Rackley",
            "Gary Grant",
            "Skylar Fingerle",
        ]

        def _employee_names(at):
            names = []
            for b in at.button:
                label = b.label or ""
                name = label[2:] if label.startswith("● ") else label
                if name in expected:
                    names.append(name)
            return names

        def _assert_blank_employee_body(at):
            self.assertFalse(list(at.exception))
            self.assertFalse(list(at.text_input))
            self.assertFalse(list(at.text_area))
            self.assertFalse(list(at.selectbox))
            self.assertFalse(list(at.date_input))
            self.assertFalse(list(at.checkbox))
            self.assertFalse(list(at.number_input))
            self.assertFalse(any("Coming soon - Ron to define contents" in (i.value or "") for i in at.info))

        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        self.assertTrue(any((b.label or "").endswith("EMPLOYEES") for b in at.button))
        at.button(key="nav_employees").click().run()
        _assert_blank_employee_body(at)
        self.assertTrue(any(t.value == "Employees" for t in at.title))
        self.assertTrue(any(b.label == "Calendar" for b in at.button))
        self.assertEqual(_employee_names(at), expected)
        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertEqual(set(book.sheets), {"Sheet1"})

        at.button(key="employee_btn_Ron_Cline").click().run()
        _assert_blank_employee_body(at)
        self.assertTrue(any(t.value == "Ron Cline" for t in at.title))
        self.assertTrue(any(b.label == "Calendar" for b in at.button))
        self.assertEqual(_employee_names(at), expected)
        self.assertTrue(any((b.label or "") == "● Ron Cline" for b in at.button))
        self.assertTrue(any(b.label == "Back" for b in at.button))
        at.button(key="employees_back").click().run()
        _assert_blank_employee_body(at)
        self.assertTrue(any(t.value == "Employees" for t in at.title))
        self.assertFalse(any(t.value == "Ron Cline" for t in at.title))

        at.button(key="employee_btn_Skylar_Fingerle").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Skylar Fingerle" for t in at.title))
        self.assertTrue(any(t.value == "Weekly Time Sheet" for t in at.subheader))
        self.assertTrue(any("PIN not set up yet - ask the office" in (i.value or "") for i in at.info))
        self.assertFalse(any(n.label == "Vacation Hours" for n in at.number_input))
        self.assertEqual(_employee_names(at), expected)
        # Header EMPLOYEES button returns to the list.
        at.button(key="nav_employees").click().run()
        _assert_blank_employee_body(at)
        self.assertTrue(any(t.value == "Employees" for t in at.title))
        self.assertFalse(any(t.value == "Skylar Fingerle" for t in at.title))

        # Anthony has a separate official form, not the five-person weekly sheet.
        at.button(key="employee_btn_Anthony_Root").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Anthony Root" for t in at.title))
        self.assertTrue(any(t.value == "Time Sheet" for t in at.subheader))
        self.assertFalse(any(t.value == "Weekly Time Sheet" for t in at.subheader))
        self.assertTrue(any("PIN not set up yet - ask the office" in (i.value or "") for i in at.info))
        labels = [i.label or "" for i in list(at.text_input) + list(at.text_area)]
        self.assertFalse(any("L&I Ground Hours" in lab for lab in labels))
        self.assertFalse(any("CVH # work hours" in lab for lab in labels))
        self.assertFalse(any(n.label == "Vacation Hours" for n in at.number_input))
        self.assertFalse(any(n.label == "Sick Hours" for n in at.number_input))
        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertNotIn("Anthony Time Sheets", book.sheets)
            self.assertNotIn("Time Sheets", book.sheets)
        for name, key in (
            ("Carl Mulvaney", "employee_btn_Carl_Mulvaney"),
            ("Barry Markham", "employee_btn_Barry_Markham"),
            ("Robert Rackley", "employee_btn_Robert_Rackley"),
            ("Gary Grant", "employee_btn_Gary_Grant"),
        ):
            at.button(key=key).click().run()
            self.assertFalse(list(at.exception), name)
            self.assertTrue(any(t.value == name for t in at.title), name)
            self.assertTrue(any(t.value == "Weekly Time Sheet" for t in at.subheader), name)
            self.assertTrue(any("PIN not set up yet - ask the office" in (i.value or "") for i in at.info), name)
            self.assertFalse(any(n.label == "Vacation Hours" for n in at.number_input), name)
            self.assertEqual(_employee_names(at), expected)
            self.assertTrue(any(b.label == "Back" for b in at.button))
            book = at.session_state.get("_workbook")
            if book is not None:
                self.assertNotIn("Time Sheets", book.sheets)

        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertEqual(set(book.sheets), {"Sheet1"})
        next(b for b in at.button if b.label == "🛩️ Pilot").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Pilot Performance" in (t.value or "") for t in at.title))

    def test_employees_calendar_saves_filters_and_cancels_on_fake_sheet(self):
        import re
        from datetime import date, time
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
        at.button(key="nav_employees").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(b.label == "Calendar" for b in at.button))
        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertNotIn("Time Off", book.sheets)

        at.button(key="employees_calendar").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(t.value == "Calendar" for t in at.title))
        self.assertTrue(any((b.label or "") == "● Calendar" for b in at.button))
        captions = " ".join(c.value or "" for c in at.caption)
        self.assertIn("not automatically approved leave", captions)
        self.assertIn("medical", captions.lower())
        self.assertTrue(any(b.label == "Previous" for b in at.button))
        self.assertTrue(any(b.label == "Next" for b in at.button))
        self.assertTrue(any(b.label == "Today" for b in at.button))
        self.assertTrue(any(b.label == "Refresh" for b in at.button))
        self.assertTrue(any(s.label == "Show" for s in at.selectbox))
        self.assertTrue(any(t.value == "November 2026" for t in at.subheader))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("toff-cal", md)
        self.assertIn("Sun", md)
        self.assertTrue(any(s.label == "Employee" for s in at.selectbox))
        type_box = next(s for s in at.selectbox if s.label == "Type")
        self.assertEqual(
            list(type_box.options),
            ["Full day off", "Partial day", "Vacation", "Project", "Company Holiday"],
        )
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))
        self.assertFalse(any(t.label == "Holiday name" for t in at.text_input))
        self.assertNotIn(
            "All employees",
            list(next(s for s in at.selectbox if s.label == "Employee").options),
        )
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertTrue(any("do not include medical" in (t.label or "") for t in at.text_input))
        book = at.session_state.get("_workbook")
        if book is not None:
            self.assertNotIn("Time Off", book.sheets)
            self.assertEqual(set(book.sheets), {"Sheet1"})

        next(s for s in at.selectbox if s.label == "Employee").select("Ron Cline")
        next(s for s in at.selectbox if s.label == "Type").select("Full day off").run()
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 20))
        next(t for t in at.text_input if "optional" in (t.label or "").lower()).set_value("Family event")
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved the listed time-off request." in (s.value or "") for s in at.success))
        book = at.session_state.get("_workbook")
        self.assertIn("Time Off", book.sheets)
        self.assertEqual(book.sheets["Time Off"].rows[0], [
            "Timestamp", "Entry ID", "Action", "Employee", "Type",
            "Start Date", "End Date", "Start Time", "End Time", "Notes", "Status",
            "Project",
            "Holiday Name",
        ])
        self.assertEqual(
            book.sheets["Time Off"].rows[1][book.sheets["Time Off"].rows[0].index("Project")],
            "",
        )
        self.assertEqual(
            book.sheets["Time Off"].rows[1][book.sheets["Time Off"].rows[0].index("Holiday Name")],
            "",
        )
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Ron C.", md)
        self.assertIn("Full day", md)
        self.assertIn("Ron Cline — Full day off — 2026-11-20 — Family event", md)

        # Duplicate of the same active request is rejected.
        next(s for s in at.selectbox if s.label == "Employee").select("Ron Cline")
        next(s for s in at.selectbox if s.label == "Type").select("Full day off").run()
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 20))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("already listed" in (e.value or "") for e in at.error))
        self.assertEqual(len(book.sheets["Time Off"].rows), 2)

        # Partial day
        next(s for s in at.selectbox if s.label == "Employee").select("Gary Grant")
        next(s for s in at.selectbox if s.label == "Type").select("Partial day").run()
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertFalse(any(d.label == "Start Date" for d in at.date_input))
        self.assertFalse(any(d.label == "End Date" for d in at.date_input))
        self.assertTrue(any("Start Time" in (t.label or "") for t in at.time_input))
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 12))
        next(t for t in at.time_input if "Start Time" in (t.label or "")).set_value(time(9, 0))
        next(t for t in at.time_input if "End Time" in (t.label or "")).set_value(time(13, 0))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Gary G.", md)
        self.assertIn("9:00 AM–1:00 PM", md)

        # Vacation spanning multiple days
        next(s for s in at.selectbox if s.label == "Employee").select("Skylar Fingerle")
        next(s for s in at.selectbox if s.label == "Type").select("Vacation").run()
        self.assertFalse(any(d.label == "Date" for d in at.date_input))
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 24))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 26))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Skylar F.", md)
        self.assertIn("Vacation", md)
        self.assertIn("2026-11-24 to 2026-11-26", md)

        # Employee filter hides other people
        next(s for s in at.selectbox if s.label == "Show").select("Ron Cline").run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Ron C.", md)
        self.assertNotIn("Gary G.", md)
        self.assertNotIn("Skylar F.", md)
        next(s for s in at.selectbox if s.label == "Show").select("All employees").run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Gary G.", md)
        self.assertIn("Skylar F.", md)

        at.button(key="time_off_refresh").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Refreshed from the shared list." in (s.value or "") for s in at.success))

        # Month navigation
        at.button(key="time_off_next").click().run()
        self.assertTrue(any(t.value == "December 2026" for t in at.subheader))
        at.button(key="time_off_today").click().run()
        self.assertTrue(any(t.value == "November 2026" for t in at.subheader))

        # Cancel requires confirmation and keeps history
        cancel = next(b for b in at.button if b.label == "Cancel request" and "TO-" in (b.key or ""))
        # There are multiple cancel buttons; cancel Ron's first by finding agenda order.
        # Click the first Cancel request, then confirm.
        first_cancel = next(b for b in at.button if b.label == "Cancel request")
        first_cancel.click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("kept in history" in (w.value or "") for w in at.warning))
        next(b for b in at.button if b.label == "Never mind").click().run()
        self.assertFalse(any(b.label == "Confirm cancel" for b in at.button))
        # Still active: three data rows (header + 3 creates)
        self.assertEqual(len(book.sheets["Time Off"].rows), 4)
        next(b for b in at.button if b.label == "Cancel request").click().run()
        next(b for b in at.button if b.label == "Confirm cancel").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Cancelled the listed request." in (s.value or "") for s in at.success))
        self.assertEqual(len(book.sheets["Time Off"].rows), 5)
        self.assertEqual(book.sheets["Time Off"].rows[-1][book.sheets["Time Off"].rows[0].index("Status")], "Cancelled")
        self.assertEqual(book.sheets["Time Off"].rows[-1][book.sheets["Time Off"].rows[0].index("Action")], "Cancel")
        self.assertEqual(set(book.sheets), {"Sheet1", "Time Off"})

        # Validation: partial end before start
        next(s for s in at.selectbox if s.label == "Employee").select("Anthony Root")
        next(s for s in at.selectbox if s.label == "Type").select("Partial day").run()
        next(d for d in at.date_input if d.label == "Date").set_value(date(2026, 11, 18))
        next(t for t in at.time_input if "Start Time" in (t.label or "")).set_value(time(15, 0))
        next(t for t in at.time_input if "End Time" in (t.label or "")).set_value(time(10, 0))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertTrue(any("End time must be after start time" in (e.value or "") for e in at.error))

        # Project adds a second menu and start/end dates, stored on the shared list.
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))
        next(s for s in at.selectbox if s.label == "Type").select("Project").run()
        self.assertFalse(list(at.exception))
        project_box = next(s for s in at.selectbox if s.label == "Project")
        self.assertEqual(list(project_box.options), ["BNSF", "Forestry", "WSFW", "West", "Basin", "Other"])
        self.assertTrue(any(d.label == "Start Date" for d in at.date_input))
        self.assertTrue(any(d.label == "End Date" for d in at.date_input))
        self.assertFalse(any(d.label == "Date" for d in at.date_input))
        self.assertFalse(any(t.label and "Start Time" in t.label for t in at.time_input))
        next(s for s in at.selectbox if s.label == "Employee").select("Barry Markham")
        project_box.select("BNSF")
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 16))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 16))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any("Saved the listed time-off request." in (s.value or "") for s in at.success))
        header = book.sheets["Time Off"].rows[0]
        saved = book.sheets["Time Off"].rows[-1]
        self.assertEqual(saved[header.index("Type")], "Project")
        self.assertEqual(saved[header.index("Project")], "BNSF")
        self.assertEqual(saved[header.index("Holiday Name")], "")
        self.assertEqual(saved[header.index("Employee")], "Barry Markham")
        self.assertEqual(saved[header.index("Start Date")], "2026-11-16")
        self.assertEqual(saved[header.index("End Date")], "2026-11-16")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Barry M. — Project – BNSF", md)
        self.assertIn("Barry Markham — Project – BNSF — 2026-11-16", md)
        self.assertEqual(set(book.sheets), {"Sheet1", "Time Off"})

        next(s for s in at.selectbox if s.label == "Type").select("Project").run()
        fresh_start = next(d for d in at.date_input if d.label == "Start Date")
        fresh_end = next(d for d in at.date_input if d.label == "End Date")
        self.assertEqual(fresh_start.value, fresh_end.value)
        next(s for s in at.selectbox if s.label == "Employee").select("Robert Rackley")
        next(s for s in at.selectbox if s.label == "Project").select("Other")
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 17))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 17))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Robert R. — Project – Other", md)
        self.assertIn("Robert Rackley — Project – Other — 2026-11-17", md)
        self.assertEqual(book.sheets["Time Off"].rows[-1][header.index("Project")], "Other")
        self.assertEqual(book.sheets["Time Off"].rows[-1][header.index("Start Date")], "2026-11-17")
        self.assertEqual(book.sheets["Time Off"].rows[-1][header.index("End Date")], "2026-11-17")

        next(s for s in at.selectbox if s.label == "Type").select("Project").run()
        next(s for s in at.selectbox if s.label == "Employee").select("Barry Markham")
        next(s for s in at.selectbox if s.label == "Project").select("BNSF")
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 18))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 20))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        header = book.sheets["Time Off"].rows[0]
        saved = book.sheets["Time Off"].rows[-1]
        self.assertEqual(saved[header.index("Type")], "Project")
        self.assertEqual(saved[header.index("Project")], "BNSF")
        self.assertEqual(saved[header.index("Start Date")], "2026-11-18")
        self.assertEqual(saved[header.index("End Date")], "2026-11-20")
        self.assertEqual(saved[header.index("Start Time")], "")
        self.assertEqual(saved[header.index("End Time")], "")
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("Barry Markham — Project – BNSF — 2026-11-18 to 2026-11-20", md)

        def _day_bodies(markup, day_num):
            return re.findall(
                r"<span class='daynum'>" + str(day_num) + r"</span>(.*?)</td>",
                markup,
            )
        for day_num in (18, 19, 20):
            bodies = _day_bodies(md, day_num)
            self.assertEqual(len(bodies), 1, day_num)
            self.assertIn("Barry M. — Project – BNSF", bodies[0])
        self.assertNotIn("Project – BNSF", _day_bodies(md, 17)[0])
        self.assertNotIn("Project – BNSF", _day_bodies(md, 21)[0])

        rows_before = len(book.sheets["Time Off"].rows)
        next(s for s in at.selectbox if s.label == "Type").select("Project").run()
        next(s for s in at.selectbox if s.label == "Employee").select("Gary Grant")
        next(s for s in at.selectbox if s.label == "Project").select("West")
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 22))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 21))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertTrue(any("End date must be on or after" in (e.value or "") for e in at.error))
        self.assertEqual(len(book.sheets["Time Off"].rows), rows_before)

        next(s for s in at.selectbox if s.label == "Type").select("Vacation").run()
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))
        self.assertFalse(any(t.label == "Holiday name" for t in at.text_input))
        next(s for s in at.selectbox if s.label == "Type").select("Full day off").run()
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))

        # Company Holiday is one shared entry, shown for every employee filter.
        next(s for s in at.selectbox if s.label == "Type").select("Company Holiday").run()
        self.assertFalse(list(at.exception))
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))
        employee_box = next(s for s in at.selectbox if s.label == "Employee")
        self.assertEqual(list(employee_box.options)[0], "All employees")
        self.assertEqual(employee_box.value, "All employees")
        self.assertTrue(any(t.label == "Holiday name" for t in at.text_input))
        self.assertTrue(any(d.label == "Start Date" for d in at.date_input))
        self.assertTrue(any(d.label == "End Date" for d in at.date_input))
        self.assertFalse(any(t.label and "Start Time" in t.label for t in at.time_input))
        rows_before = len(book.sheets["Time Off"].rows)
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 11, 26))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 11, 26))
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertTrue(any("Holiday name is required" in (e.value or "") for e in at.error))
        self.assertEqual(len(book.sheets["Time Off"].rows), rows_before)

        next(t for t in at.text_input if t.label == "Holiday name").set_value("Thanksgiving")
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(len(book.sheets["Time Off"].rows), rows_before + 1)
        header = book.sheets["Time Off"].rows[0]
        saved = book.sheets["Time Off"].rows[-1]
        self.assertEqual(saved[header.index("Type")], "Company Holiday")
        self.assertEqual(saved[header.index("Employee")], "All employees")
        self.assertEqual(saved[header.index("Holiday Name")], "Thanksgiving")
        self.assertEqual(saved[header.index("Start Date")], "2026-11-26")
        self.assertEqual(saved[header.index("End Date")], "2026-11-26")
        self.assertEqual(saved[header.index("Project")], "")
        self.assertEqual(
            sum(1 for row in book.sheets["Time Off"].rows[1:] if row[header.index("Type")] == "Company Holiday"),
            1,
        )
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertIn("All employees — 🎉 CVH Holiday – Thanksgiving", md)
        self.assertIn("toff-hol", md)
        for person in ("Ron Cline", "Gary Grant", "Skylar Fingerle"):
            next(s for s in at.selectbox if s.label == "Show").select(person).run()
            md = " ".join(m.value or "" for m in at.markdown)
            self.assertIn("🎉 CVH Holiday – Thanksgiving", md, person)
            self.assertIn("All employees — 🎉 CVH Holiday – Thanksgiving — 2026-11-26", md, person)
        next(s for s in at.selectbox if s.label == "Show").select("Gary Grant").run()
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertNotIn("Ron C.", md)
        self.assertNotIn("Skylar F.", md)
        next(s for s in at.selectbox if s.label == "Show").select("All employees").run()

        next(s for s in at.selectbox if s.label == "Type").select("Company Holiday").run()
        self.assertEqual(next(s for s in at.selectbox if s.label == "Employee").value, "All employees")
        next(t for t in at.text_input if t.label == "Holiday name").set_value("Christmas")
        next(d for d in at.date_input if d.label == "Start Date").set_value(date(2026, 12, 24))
        next(d for d in at.date_input if d.label == "End Date").set_value(date(2026, 12, 26))
        rows_before = len(book.sheets["Time Off"].rows)
        next(b for b in at.button if b.label == "Save request").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(len(book.sheets["Time Off"].rows), rows_before + 1)
        saved = book.sheets["Time Off"].rows[-1]
        self.assertEqual(saved[header.index("Employee")], "All employees")
        self.assertEqual(saved[header.index("Holiday Name")], "Christmas")
        self.assertEqual(saved[header.index("Start Date")], "2026-12-24")
        self.assertEqual(saved[header.index("End Date")], "2026-12-26")
        at.button(key="time_off_next").click().run()
        self.assertTrue(any(t.value == "December 2026" for t in at.subheader))
        md = " ".join(m.value or "" for m in at.markdown)
        self.assertEqual(md.count("<div class='ev toff-hol'>"), 3)
        self.assertIn("All employees — 🎉 CVH Holiday – Christmas — 2026-12-24 to 2026-12-26", md)
        self.assertNotIn("Thanksgiving", md)
        at.button(key="time_off_today").click().run()
        self.assertTrue(any(t.value == "November 2026" for t in at.subheader))

        next(s for s in at.selectbox if s.label == "Type").select("Full day off").run()
        self.assertFalse(any(t.label == "Holiday name" for t in at.text_input))
        self.assertFalse(any(s.label == "Project" for s in at.selectbox))
        self.assertTrue(any(d.label == "Date" for d in at.date_input))
        self.assertFalse(any(d.label == "Start Date" for d in at.date_input))
        self.assertFalse(any(d.label == "End Date" for d in at.date_input))
        self.assertNotIn(
            "All employees",
            list(next(s for s in at.selectbox if s.label == "Employee").options),
        )

        # Employee nav stays available; Back returns to the Employees list
        self.assertTrue(any("Ron Cline" in (b.label or "") for b in at.button))
        at.button(key="employees_calendar_back").click().run()
        self.assertTrue(any(t.value == "Employees" for t in at.title))
        self.assertFalse(any(t.value == "Calendar" for t in at.title))
        self.assertFalse(list(at.selectbox))

        # Header EMPLOYEES also closes the calendar
        at.button(key="employees_calendar").click().run()
        at.button(key="nav_employees").click().run()
        self.assertTrue(any(t.value == "Employees" for t in at.title))
        self.assertFalse(list(at.exception))

    def test_employee_timesheet_saves_exports_and_email_stays_disabled(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        import timesheet_pin
        from streamlit.runtime.secrets import secrets_singleton

        pin_map = {
            "timesheet_pin": {"cookie_secret": "test-cookie-secret-0123456789"},
            "timesheet_pins": {
                name: timesheet_pin.make_pin_hash("2468" + name[-1])
                for name in timesheet_pin.PIN_EMPLOYEES
            },
        }
        previous = secrets_singleton._programmatic_secrets
        secrets_singleton.merge_programmatic_secrets(pin_map)
        try:
            at = AppTest.from_string(equipment_offline_app(), default_timeout=30).run()
            at.session_state["timesheet_pin_employee"] = "Carl Mulvaney"
            at.button(key="nav_employees").click().run()
            at.button(key="employee_btn_Ron_Cline").click().run()
            self.assertFalse(list(at.exception))
            self.assertFalse(any(t.value == "Weekly Time Sheet" for t in at.subheader))
            at.button(key="employee_btn_Carl_Mulvaney").click().run()
            self.assertFalse(list(at.exception))
            self.assertTrue(any(t.value == "Carl Mulvaney" for t in at.title))
            self.assertTrue(any(t.value == "Weekly Time Sheet" for t in at.subheader))
            self.assertTrue(any("Name:** Carl Mulvaney" in (m.value or "") or (m.value or "") == "**Name:** Carl Mulvaney" for m in at.markdown) or any("Carl Mulvaney" in (m.value or "") and "Name" in (m.value or "") for m in at.markdown))
            self.assertTrue(any(d.label == "Week of (Sunday's Date)" for d in at.date_input))
            self.assertTrue(any(b.label == "Save week" for b in at.button))
            self.assertTrue(any(b.label == "Email to patti@centralvalleyheli.com" for b in at.button))
            email_btn = next(b for b in at.button if b.label == "Email to patti@centralvalleyheli.com")
            self.assertTrue(getattr(email_btn, "disabled", True) or email_btn.disabled)
            captions = " ".join(c.value or "" for c in at.caption)
            self.assertIn("does not send mail", captions)
            book = at.session_state.get("_workbook")
            if book is not None:
                self.assertNotIn("Time Sheets", book.sheets)

            # Fill Sunday hours and initials, save
            week_input = next(d for d in at.date_input if d.label == "Week of (Sunday's Date)")
            week_input.set_value(date(2026, 11, 8)).run()
            self.assertFalse(list(at.exception))
            loc = next(t for t in at.text_input if t.label == "Location")
            loc.set_value("Shop").run()
            cvh = next(t for t in at.text_input if t.label == "CVH # work hours")
            cvh.set_value("8")
            next(n for n in at.number_input if n.label == "Vacation Hours").set_value(4)
            next(n for n in at.number_input if n.label == "Sick Hours").set_value(2)
            next(t for t in at.text_input if t.label == "Initials (required before email)").set_value("CM")
            next(b for b in at.button if b.label == "Save week").click().run()
            self.assertFalse(list(at.exception))
            self.assertTrue(any("Saved time sheet for week of 2026-11-08" in (s.value or "") for s in at.success))
            book = at.session_state.get("_workbook")
            self.assertIn("Time Sheets", book.sheets)
            self.assertEqual(book.sheets["Time Sheets"].rows[0], book.sheets["Time Sheets"].rows[0])  # header present
            header = book.sheets["Time Sheets"].rows[0]
            row = book.sheets["Time Sheets"].rows[1]
            self.assertEqual(row[header.index("Employee")], "Carl Mulvaney")
            self.assertEqual(row[header.index("Week Of")], "2026-11-08")
            self.assertEqual(row[header.index("Sun Location")], "Shop")
            self.assertEqual(row[header.index("Sun CVH Hours")], "8")
            self.assertEqual(row[header.index("Sun Vacation Hours")], "4")
            self.assertEqual(row[header.index("Sun Sick Hours")], "2")
            self.assertEqual(row[header.index("Mon Vacation Hours")], "0")
            self.assertEqual(row[header.index("Initials")], "CM")
            md = " ".join(m.value or "" for m in at.markdown)
            self.assertIn("Worked hours: 8", md)
            self.assertNotIn("Worked hours: 14", md)
            captions = " ".join(c.value or "" for c in at.caption)
            self.assertIn("Worked hours are CVH, Forestry, and BNSF only", captions)
            self.assertIn("Sun", md)
            self.assertIn("2026-11-08", md)
            self.assertIn("Week Total", md)
            self.assertIn("Vacation", md)
            html = " ".join(m.value or "" for m in at.markdown)
            self.assertIn(">8<", html)
            self.assertIn(">4<", html)
            self.assertIn(">2<", html)
            self.assertIn(">14<", html)
            labels = [e.label for e in at.expander]
            self.assertIn("Sun  2026-11-08 — 14 hrs", labels)
            self.assertIn("Mon  2026-11-09", labels)
            self.assertEqual(set(book.sheets), {"Sheet1", "Time Sheets"})

            self.assertTrue(any(b.label == "Download PDF" for b in at.button) or any(getattr(b, "label", "") == "Download PDF" for b in at.download_button))
            self.assertTrue(any(getattr(b, "label", "") == "Download Excel" for b in at.download_button) or any(b.label == "Download Excel" for b in at.button))
            email_btn = next(b for b in at.button if b.label == "Email to patti@centralvalleyheli.com")
            self.assertTrue(email_btn.disabled)
            # Clicking a disabled button must not send or write mail.
            self.assertFalse(list(at.exception))
        finally:
            secrets_singleton._programmatic_secrets = previous
            secrets_singleton._secrets = None

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
