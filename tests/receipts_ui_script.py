"""Harness for test_receipts_ui.py. Not a test.

Runs the real receipts page functions from app.py with an in-memory spreadsheet,
a fake camera photo, a fake Drive uploader, and an SMTP stub. Nothing leaves the box.
"""
import ast
import os
import sys
import time
import types

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import employee_receipts  # noqa: E402
import timesheet_company_mail  # noqa: E402
import timesheet_pin  # noqa: E402
from datetime import datetime, date, timedelta  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402


class FakeWS:
    def __init__(self, title, store):
        self.title = title
        self.store = store

    def row_values(self, n):
        rows = self.store[self.title]
        return list(rows[n - 1]) if len(rows) >= n else []

    def append_row(self, row, **kw):
        self.store[self.title].append(list(row))
        st.session_state["writes"].append(self.title)

    def get_all_values(self):
        return [list(r) for r in self.store[self.title]]


class NotFound(Exception):
    pass


NotFound.__name__ = "WorksheetNotFound"


class FakeBook:
    def __init__(self, store):
        self.store = store

    def worksheet(self, title):
        if title not in self.store:
            raise NotFound(title)
        return FakeWS(title, self.store)

    def add_worksheet(self, title, rows, cols):
        self.store[title] = []
        st.session_state["created"].append(title)
        return FakeWS(title, self.store)


store = st.session_state.setdefault("store", {})
if os.environ.get("RECEIPTS_UI_SEED") == "1" and "Receipts" not in store:
    recs = [
        {"Saved At": "2026-11-16 08:00:00 PST", "Entry ID": "1", "Employee": "Carl Mulvaney",
         "Date": "2026-11-16", "Amount": "10.00", "Receipt Number": "A1", "Vendor": "Shell",
         "Purpose": "Fuel for truck", "Job": "BNSF", "Expense Type": "Fuel",
         "Photo Link": "https://drive.google.com/file/d/SEED1/view", "Photo File": "a.jpg", "Notes": ""},
        {"Saved At": "2026-11-18 10:00:00 PST", "Entry ID": "2", "Employee": "Gary Grant",
         "Date": "2026-11-17", "Amount": "25.50", "Receipt Number": "B2", "Vendor": "NAPA",
         "Purpose": "Filter", "Job": "CVH", "Expense Type": "Parts",
         "Photo Link": "https://drive.google.com/file/d/SEED2/view", "Photo File": "b.jpg", "Notes": ""},
        {"Saved At": "2026-11-01 09:00:00 PST", "Entry ID": "3", "Employee": "Carl Mulvaney",
         "Date": "2026-11-01", "Amount": "8.00", "Receipt Number": "", "Vendor": "",
         "Purpose": "Earlier meal", "Job": "CVH", "Expense Type": "Meals",
         "Photo Link": "", "Photo File": "c.jpg", "Notes": ""},
    ]
    store["Receipts"] = [employee_receipts.RECEIPTS_COLUMNS] + [
        [row.get(c, "") for c in employee_receipts.RECEIPTS_COLUMNS] for row in recs
    ]
st.session_state.setdefault("writes", [])
st.session_state.setdefault("created", [])
st.session_state.setdefault("uploads", [])
st.session_state.setdefault("mails", [])

EMPLOYEE = os.environ.get("RECEIPTS_UI_EMPLOYEE", "Carl Mulvaney")
PHOTO = b"\xff\xd8\xff\xe0" + b"fake-jpeg" * 10


class FakeShot:
    name = "image.jpg"

    def getvalue(self):
        return PHOTO


proxy = types.SimpleNamespace(**{n: getattr(st, n) for n in dir(st) if not n.startswith("__")})
proxy.camera_input = lambda *a, **k: FakeShot() if st.session_state.get("give_photo") else None
proxy.image = lambda *a, **k: None

real_store = employee_receipts.store_receipt_file


def fake_store(data, name, employee, d, amount, secrets, when=None):
    def uploader(data, filename, mime, emp, url, token, session=None):
        if os.environ.get("RECEIPTS_UI_UPLOAD_FAIL"):
            raise ConnectionError("Drive is down")
        st.session_state["uploads"].append((emp, filename, mime, len(data)))
        return "https://drive.google.com/file/d/FAKE/view"
    return real_store(data, name, employee, d, amount, secrets, when=when, uploader=uploader)


def fake_read(data, filename="", **kw):
    return {"date": date(2026, 11, 18), "amount": "61.12", "number": "004417", "vendor": "SHELL OIL"}, employee_receipts.READ_NOTE


mod_proxy = types.SimpleNamespace(**{n: getattr(employee_receipts, n) for n in dir(employee_receipts) if not n.startswith("__")})
mod_proxy.store_receipt_file = fake_store
mod_proxy.read_receipt = fake_read
real_send = employee_receipts.send_summary
mod_proxy.send_summary = lambda summary, secrets, **kw: real_send(
    summary, secrets, smtp_send=lambda u, p, m: st.session_state["mails"].append(m["Subject"]), **kw)

_hash = st.session_state.get("_patti_hash") or timesheet_pin.make_pin_hash("4321")
st.session_state["_patti_hash"] = _hash
secrets = {
    "timesheet_pin": {"cookie_secret": "test-cookie-secret-0123456789"},
    "timesheet_pins": {"Patti": _hash} if os.environ.get("RECEIPTS_UI_PATTI_PIN", "1") == "1" else {},
    "receipts": {"apps_script_url": "https://script.example/exec", "upload_token": "t0ken-for-tests"},
    "timesheet_company_mail": {"enabled": os.environ.get("RECEIPTS_UI_MAIL", "1") == "1", "backend": "gmail_smtp",
                               "username": "clineair891@gmail.com", "password": "pw-test"},
}

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")).read()
tree = ast.parse(src)
want = {
    "cached_receipt_records", "clear_receipts_cache", "receipt_records_for_view", "receipt_totals_rows",
    "receipt_table_rows", "_reset_receipt_entry", "apply_receipt_fields_to_session", "show_receipt_entry",
    "show_receipt_list", "receipt_summary_period_options", "show_receipts_summary_office",
    "show_employee_receipts", "employee_button_key", "_cell", "show_receipts_office_gate",
    "show_receipts_summary_page", "_receipts_office_filter_names",
}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Name) and t.id in ("RECEIPTS_CACHE_TTL_SECONDS", "RECEIPT_VIEWS", "EMPLOYEES") for t in n.targets)]
class FixedDateTime(datetime):
    """Keep the live-receipts UI tests on a known Pacific day (Fri Nov 20, 2026)."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 11, 20, 15, 30, tzinfo=tz or ZoneInfo("America/Los_Angeles"))


ns = {
    "st": proxy, "pd": pd, "time_module": time, "datetime": FixedDateTime, "date": date, "timedelta": timedelta,
    "ZoneInfo": ZoneInfo, "employee_receipts": mod_proxy, "timesheet_company_mail": timesheet_company_mail,
    "_mail_runtime_secrets": lambda: secrets,
    "_receipts_spreadsheet": lambda: FakeBook(store),
    "show_timesheet_pin_gate": lambda employee, key: os.environ.get("RECEIPTS_UI_PIN", "1") == "1",
    "timesheet_verified_pin_employee": lambda s=None: st.session_state.get("timesheet_pin_employee") or os.environ.get("RECEIPTS_UI_REMEMBERED", ""),
    "show_timesheet_switch_control": lambda key_prefix="": None,
    "_timesheet_pin_failures": lambda: int(st.session_state.get("timesheet_pin_failures") or 0),
    "_timesheet_queue_cookie": lambda who, secret: st.session_state.__setitem__("queued_cookie", who),
    "timesheet_access_message": lambda state: "locked",
    "timesheet_pin": timesheet_pin,
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "app", "exec"), ns)
if os.environ.get("RECEIPTS_UI_PAGE") == "summary":
    ns["show_receipts_summary_page"]()
else:
    ns["show_employee_receipts"](EMPLOYEE)
