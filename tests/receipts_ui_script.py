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

secrets = {
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
    "show_employee_receipts", "employee_button_key", "_cell",
}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
    isinstance(t, ast.Name) and t.id in ("RECEIPTS_CACHE_TTL_SECONDS", "RECEIPT_VIEWS", "EMPLOYEES") for t in n.targets)]
ns = {
    "st": proxy, "pd": pd, "time_module": time, "datetime": datetime, "date": date, "timedelta": timedelta,
    "ZoneInfo": ZoneInfo, "employee_receipts": mod_proxy, "timesheet_company_mail": timesheet_company_mail,
    "_mail_runtime_secrets": lambda: secrets,
    "_receipts_spreadsheet": lambda: FakeBook(store),
    "show_timesheet_pin_gate": lambda employee, key: os.environ.get("RECEIPTS_UI_PIN", "1") == "1",
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "app", "exec"), ns)
ns["show_employee_receipts"](EMPLOYEE)
