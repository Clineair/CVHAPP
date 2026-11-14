"""Harness script for test_timesheet_resend_ui.py. Not a test. Stubs SMTP and the audit sheet."""
import ast, os, sys, time
import streamlit as st
import timesheet_mail, timesheet_company_mail
time_module = time
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")) as _f:
    src = _f.read()
tree = ast.parse(src)
want = {"show_timesheet_email_section", "timesheet_email_can_send", "timesheet_email_subject", "timesheet_email_body",
        "timesheet_email_block_reason", "apply_timesheet_send_result", "build_timesheet_mail_audit_record"}
ns = {"st": st, "time_module": time, "timesheet_mail": timesheet_mail, "timesheet_company_mail": timesheet_company_mail}
H = "h1"
rec = {"Employee": os.environ.get("RESEND_UI_EMPLOYEE", "Ron Cline"), "Week Of": "2026-11-08", "Initials": "RC", "Content Hash": H, "Entry ID": "E1"}
audit_rows = st.session_state.setdefault("rows", [])
sent = st.session_state.setdefault("sent", [])
logged = st.session_state.setdefault("logged", [])
ns.update({
    "_cell": lambda v: "" if v is None else str(v).strip(),
    "_mail_runtime_secrets": lambda: {"timesheet_company_mail": {"enabled": True, "backend": "gmail_smtp", "username": "clineair891@gmail.com", "password": "pw"}},
    "employee_has_anthony_timesheet": lambda e: e == "Anthony Root",
    "timesheet_verified_pin_employee": lambda s=None: os.environ.get("RESEND_UI_EMPLOYEE", "Ron Cline"),
    "timesheet_access_state": lambda *a, **k: "allowed",
    "_timesheet_pin_failures": lambda: {},
    "timesheet_initials_match_current": lambda a, b: True,
    "anthony_timesheet_pdf_filename": lambda p: "a.pdf",
    "timesheet_pdf_filename": lambda p: "ron.pdf",
    "load_timesheet_mail_records_readonly": lambda: list(audit_rows),
    "TIMESHEET_EMAIL_TO": "patti@x.com",
    "employee_has_timesheet": lambda e: True,
})
ns["timesheet_company_mail"] = type("M", (), {})()
real = timesheet_company_mail
for n in dir(real):
    if not n.startswith("__"):
        setattr(ns["timesheet_company_mail"], n, getattr(real, n))
def fake_send(preview, pdf, fn, **kw):
    sent.append(kw.get("allow_resend"))
    return real.send_company_timesheet(preview, pdf, fn, smtp_send=lambda u,p,m: sent.append(m["Subject"]), **kw)
ns["timesheet_company_mail"].send_company_timesheet = fake_send
ns["timesheet_company_mail"].employee_reply_to = lambda e, s=None: ""
ns["timesheet_company_mail"].from_header = lambda e, s=None: "co@x.com"
def fake_apply(record, result, pin_employee=None, **kw):
    logged.append((result.get("status"), result.get("updated_copy")))
    audit_rows.append({"Employee": record["Employee"], "Week Of": record["Week Of"], "Content Hash": record["Content Hash"],
        "Status": result["status"], "Idempotency Key": result["idempotency_key"], "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S PST")})
ns["apply_timesheet_send_result"] = fake_apply
mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want - {"apply_timesheet_send_result"}], type_ignores=[])
exec(compile(mod, "app", "exec"), ns)
ns["timesheet_email_can_send"] = ns["timesheet_email_can_send"]
ns["show_timesheet_email_section"](os.environ.get("RESEND_UI_EMPLOYEE", "Ron Cline"), rec, saved=rec, form_ok=True, prefix="p_", pdf_bytes=b"%PDF-1.4 x")
st.write("sent=" + repr(sent) + " logged=" + repr(logged))

