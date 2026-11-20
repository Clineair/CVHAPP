"""Bi-weekly receipts summary to Patti, run from the box (or by hand).

    python tools/send_receipts_summary.py --auto                 # the Monday routine
    python tools/send_receipts_summary.py --dry-run [--today D]  # what --auto would do; sends nothing, writes nothing
    python tools/send_receipts_summary.py --test-send --to ADDR [--period-start YYYY-MM-DD]

--auto sends only when ALL of these are true, and logs the result to the Receipts Mail tab:
  * [receipts_mail] auto_send = true in the secrets file (the on/off switch)
  * the company Gmail mailbox has its app password
  * today (Pacific) is the Monday right after a two-week period ends
  * that period is not already in the Receipts Mail tab as Sent (or Uncertain)
--test-send mails one copy to --to with "TEST: " in front of the subject. It does not
check or write the Receipts Mail tab, so it never blocks the real send.

Secrets: a TOML file in the Streamlit secrets format (default
/workspace/secrets/receipts_summary_secrets.toml, override with --secrets or
CVH_SECRETS_FILE). If [timesheet_company_mail] has no password there, it is read
from the environment variable named by --password-env (default CVH_TIMESHEET_GMAIL_APPPW).
Nothing secret is printed.

Output: the last line starts with one of
  SENT, NOT DUE, OFF, ALREADY SENT, DRY RUN, TEST SENT, ERROR:
Exit code 0 for everything except ERROR (1).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import employee_receipts as er  # noqa: E402
import timesheet_company_mail as company_mail  # noqa: E402

DEFAULT_SECRETS = "/workspace/secrets/receipts_summary_secrets.toml"
DEFAULT_PASSWORD_ENV = "CVH_TIMESHEET_GMAIL_APPPW"
TEST_PREFIX = "TEST: "


def load_secrets(path, password_env=DEFAULT_PASSWORD_ENV, environ=None):
    import tomllib
    with open(path, "rb") as handle:
        secrets = tomllib.load(handle)
    environ = os.environ if environ is None else environ
    section = secrets.setdefault(company_mail.COMPANY_SECTION, {})
    if not str(section.get("password") or "").strip() and password_env and environ.get(password_env):
        section["password"] = environ[password_env]
    return secrets


def open_spreadsheet(secrets):
    import gspread
    gc = gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
    sheet_id = secrets.get("frat_sheet_id")
    return gc.open_by_key(sheet_id) if sheet_id else gc.open(secrets.get("frat_sheet_name") or "CVH FRAT Log")


def plan(spreadsheet, secrets, today):
    """What --auto would do today. Reads only."""
    start, end = er.previous_period(today)
    summary = er.build_summary(er.load_receipts_readonly(spreadsheet), start, end)
    audit = er.load_mail_audit_readonly(spreadsheet)
    if not er.summary_due_on(today):
        outcome = "NOT DUE"
    elif er.already_sent(audit, summary):
        outcome = "ALREADY SENT"
    elif not er.mail_ready(secrets):
        outcome = "ERROR: company mailbox not set up"
    else:
        outcome = "SEND"
    if not er.auto_send_enabled(secrets):
        return summary, "OFF (if switched on: " + outcome + ")"
    return summary, outcome


def _next_due(today):
    day = today
    for _ in range(15):
        if er.summary_due_on(day) and day >= today:
            return day
        day = date.fromordinal(day.toordinal() + 1)
    return None


def run(args, spreadsheet=None, secrets=None, smtp_send=None, out=print):
    today = date.fromisoformat(args.today) if args.today else er.now_pacific().date()
    if secrets is None:
        secrets = load_secrets(args.secrets, args.password_env)
    if spreadsheet is None:
        spreadsheet = open_spreadsheet(secrets)
    if args.test_send:
        if not args.to:
            out("ERROR: --test-send needs --to")
            return 1
        start = date.fromisoformat(args.period_start) if args.period_start else er.period_for(today)[0]
        start, end = er.period_for(start)
        summary = er.build_summary(er.load_receipts_readonly(spreadsheet), start, end)
        result = er.send_summary(summary, secrets, trigger="Test", to=args.to, subject_prefix=TEST_PREFIX,
                                 smtp_send=smtp_send)
        if result["status"] == er.STATUS_SENT:
            out("TEST SENT " + summary["label"] + " to " + result["to"] + " (" + str(summary["count"])
                + " receipts, " + er.format_money(summary["total"]) + "); not logged")
            return 0
        out("ERROR: " + (result.get("error") or result["status"]))
        return 1
    if args.dry_run:
        summary, outcome = plan(spreadsheet, secrets, today)
        nxt = _next_due(today)
        out("Today (Pacific): " + today.isoformat())
        out("Automatic sending: " + ("ON" if er.auto_send_enabled(secrets) else "OFF"))
        out("Due today: " + ("yes" if er.summary_due_on(today) else "no")
            + ("; next send day " + nxt.isoformat() if nxt else ""))
        out("Period: " + summary["label"] + " (" + str(summary["count"]) + " receipts, "
            + er.format_money(summary["total"]) + ")")
        out("To: " + er.recipient(secrets) + "   From: " + company_mail.mailbox_address(secrets))
        out("Mailbox ready: " + ("yes" if er.mail_ready(secrets) else "no"))
        out("Subject: " + er.summary_subject(summary))
        out("DRY RUN: --auto would do: " + outcome + ". Nothing sent, nothing written.")
        return 0
    # --auto
    if not er.auto_send_enabled(secrets):
        out("OFF: automatic receipts email is switched off ([receipts_mail] auto_send is not true)")
        return 0
    if not er.summary_due_on(today):
        out("NOT DUE: " + today.isoformat() + " is not the Monday after a period ends")
        return 0
    status, detail = er.run_scheduled_send(spreadsheet, secrets, today=today, smtp_send=smtp_send)
    if status == er.STATUS_SENT:
        out("SENT " + detail)
        return 0
    if status == er.STATUS_DUPLICATE:
        out("ALREADY SENT: " + detail)
        return 0
    if status == er.STATUS_SKIPPED:
        out("NOT DUE: " + detail)
        return 0
    out("ERROR: " + status + " - " + detail)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Receipts summary email to Patti.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--auto", action="store_true", help="Send if today is a send day and it is switched on.")
    mode.add_argument("--dry-run", action="store_true", help="Show what --auto would do. Sends nothing.")
    mode.add_argument("--test-send", action="store_true", help="Send one TEST copy to --to. Not logged.")
    mode.add_argument("--send", action="store_true", help=argparse.SUPPRESS)  # old name for --auto
    parser.add_argument("--to", help="Recipient for --test-send.")
    parser.add_argument("--period-start", help="Any day in the period for --test-send (default: current period).")
    parser.add_argument("--today", help="Pretend today is YYYY-MM-DD (Pacific). For --dry-run checks.")
    parser.add_argument("--secrets", default=os.environ.get("CVH_SECRETS_FILE", DEFAULT_SECRETS))
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
    args = parser.parse_args(argv)
    if args.send:
        args.auto = True
    if args.today and not args.dry_run:
        print("ERROR: --today is only for --dry-run")
        return 1
    try:
        return run(args)
    except Exception as exc:  # never print secrets; type and a short message only
        text = str(exc)
        for name in (args.password_env,):
            value = os.environ.get(name or "")
            if value and value in text:
                text = text.replace(value, "[redacted]")
        print("ERROR: " + type(exc).__name__ + ": " + text[:200])
        return 1


if __name__ == "__main__":
    sys.exit(main())
