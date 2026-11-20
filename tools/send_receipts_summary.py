"""Bi-weekly receipts summary to Patti. Run by the scheduled job; safe to run by hand.

    python tools/send_receipts_summary.py --secrets /path/to/secrets.toml            # preview only
    python tools/send_receipts_summary.py --secrets /path/to/secrets.toml --send     # scheduled send

Without --send nothing is mailed and no sheet is written; it prints the subject and
the summary text. With --send it mails only when ALL of these are true:
  * [receipts_mail] auto_send = true
  * [timesheet_company_mail] enabled = true with the Gmail app password
  * today (Pacific) is the Monday right after a bi-weekly period ends
  * that period was not already sent (Receipts Mail tab)
The secrets file is the same TOML as Streamlit secrets. Nothing secret is printed.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import employee_receipts as er  # noqa: E402


def load_secrets(path):
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def open_spreadsheet(secrets):
    import gspread
    gc = gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
    sheet_id = secrets.get("frat_sheet_id")
    return gc.open_by_key(sheet_id) if sheet_id else gc.open(secrets.get("frat_sheet_name") or "CVH FRAT Log")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--secrets", default=os.environ.get("CVH_SECRETS_FILE", ".streamlit/secrets.toml"))
    parser.add_argument("--send", action="store_true", help="Send if every gate is open. Default is preview only.")
    parser.add_argument("--today", help="Pretend today is YYYY-MM-DD (Pacific). For checking the schedule.")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else er.now_pacific().date()
    secrets = load_secrets(args.secrets)
    spreadsheet = open_spreadsheet(secrets)
    if args.send:
        status, detail = er.run_scheduled_send(spreadsheet, secrets, today=today)
        print("Receipts summary: " + status + " - " + detail)
        return 0 if status in (er.STATUS_SENT, er.STATUS_SKIPPED, er.STATUS_DUPLICATE) else 1
    start, end = er.previous_period(today)
    summary = er.build_summary(er.load_receipts_readonly(spreadsheet), start, end)
    print("PREVIEW ONLY. Nothing sent.")
    print("Due today: " + ("yes" if er.summary_due_on(today) else "no"))
    print("Automatic sending: " + ("ON" if er.auto_send_enabled(secrets) else "OFF"))
    print("To: " + er.recipient(secrets))
    print("Subject: " + er.summary_subject(summary))
    print()
    print(er.summary_text(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
