"""tools/send_receipts_summary.py with mocks only. No Sheets, no mail."""
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import employee_receipts as er  # noqa: E402
import send_receipts_summary as tool  # noqa: E402
from test_employee_receipts import Book  # noqa: E402

MAIL = {"enabled": True, "backend": "gmail_smtp", "username": "clineair891@gmail.com", "password": "pw-test"}


def _book():
    row = {"Saved At": "2026-11-16 08:00:00 PST", "Entry ID": "1", "Employee": "Carl Mulvaney", "Date": "2026-11-16",
           "Amount": "10.00", "Purpose": "p", "Job": "CVH", "Expense Type": "Fuel", "Photo File": "f"}
    return Book({"Receipts": [er.RECEIPTS_COLUMNS, [row.get(c, "") for c in er.RECEIPTS_COLUMNS]]})


def _args(**kw):
    base = dict(auto=False, dry_run=False, test_send=False, send=False, to=None, period_start=None, today=None,
                secrets="", password_env="X")
    base.update(kw)
    return types.SimpleNamespace(**base)


class ToolTests(unittest.TestCase):
    def _run(self, secrets, **kw):
        out, sent = [], []
        book = kw.pop("book", None) or _book()
        code = tool.run(_args(**kw), spreadsheet=book, secrets=secrets,
                        smtp_send=lambda u, p, m: sent.append((m["To"], m["Subject"])), out=out.append)
        return code, out, sent, book

    def test_auto_off_sends_nothing(self):
        code, out, sent, book = self._run({"timesheet_company_mail": MAIL}, auto=True)
        self.assertEqual((code, sent, book.writes), (0, [], []))
        self.assertTrue(out[-1].startswith("OFF"))

    def test_auto_not_due(self):
        s = {"timesheet_company_mail": MAIL, "receipts_mail": {"auto_send": True}}
        import unittest.mock as mock
        with mock.patch.object(er, "now_pacific", return_value=er._as_pacific(__import__("datetime").datetime(2026, 11, 23, 7, 30))):
            code, out, sent, book = self._run(s, auto=True)
        self.assertEqual((code, sent, book.writes), (0, [], []))
        self.assertTrue(out[-1].startswith("NOT DUE"))

    def test_auto_due_sends_once_and_logs(self):
        s = {"timesheet_company_mail": MAIL, "receipts_mail": {"auto_send": True}}
        import unittest.mock as mock
        from datetime import datetime
        with mock.patch.object(er, "now_pacific", return_value=er._as_pacific(datetime(2026, 11, 30, 7, 30))):
            code, out, sent, book = self._run(s, auto=True)
            self.assertEqual(code, 0)
            self.assertTrue(out[-1].startswith("SENT Nov 15 – Nov 28, 2026"))
            self.assertEqual(sent, [("patti@centralvalleyheli.com", "CVH employee receipts: Nov 15 – Nov 28, 2026")])
            code, out, sent2, _ = self._run(s, auto=True, book=book)
        self.assertEqual(code, 0)
        self.assertTrue(out[-1].startswith("ALREADY SENT"))
        self.assertEqual(sent2, [])

    def test_auto_mailbox_error_exits_1(self):
        s = {"timesheet_company_mail": dict(MAIL, password=""), "receipts_mail": {"auto_send": True}}
        import unittest.mock as mock
        from datetime import datetime
        with mock.patch.object(er, "now_pacific", return_value=er._as_pacific(datetime(2026, 11, 30, 7, 30))):
            code, out, sent, _ = self._run(s, auto=True)
        self.assertEqual((code, sent), (1, []))
        self.assertTrue(out[-1].startswith("ERROR:"))

    def test_dry_run_never_sends_or_writes(self):
        s = {"timesheet_company_mail": MAIL, "receipts_mail": {"auto_send": True}}
        code, out, sent, book = self._run(s, dry_run=True, today="2026-11-30")
        self.assertEqual((code, sent, book.writes), (0, [], []))
        self.assertIn("would do: SEND", out[-1])
        code, out, _, _ = self._run({"timesheet_company_mail": MAIL}, dry_run=True, today="2026-11-20")
        self.assertIn("OFF (if switched on: NOT DUE)", out[-1])

    def test_test_send_override_prefix_and_not_logged(self):
        code, out, sent, book = self._run({"timesheet_company_mail": MAIL}, test_send=True, to="clineair891@gmail.com",
                                          period_start="2026-11-20")
        self.assertEqual(code, 0)
        self.assertEqual(sent, [("clineair891@gmail.com", "TEST: CVH employee receipts: Nov 15 – Nov 28, 2026")])
        self.assertEqual(book.writes, [])
        self.assertTrue(out[-1].startswith("TEST SENT"))
        code, out, sent, _ = self._run({"timesheet_company_mail": MAIL}, test_send=True)
        self.assertEqual((code, sent), (1, []))

    def test_password_from_env_not_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write('[timesheet_company_mail]\nenabled = true\nbackend = "gmail_smtp"\nusername = "clineair891@gmail.com"\n')
        s = tool.load_secrets(f.name, "APPPW", environ={"APPPW": "from-env"})
        self.assertEqual(s["timesheet_company_mail"]["password"], "from-env")
        self.assertTrue(er.mail_ready(s))
        self.assertFalse(er.auto_send_enabled(s))

    def test_today_only_for_dry_run(self):
        self.assertEqual(tool.main(["--auto", "--today", "2026-11-30"]), 1)


if __name__ == "__main__":
    unittest.main()
