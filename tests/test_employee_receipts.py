"""employee_receipts.py: read-back, Drive upload, Receipts tab, totals, periods, summary mail.

Mocks only. No live Sheets writes, no Drive calls, no mail.
"""
import ast
import io
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import employee_receipts as er  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")
FUEL_TEXT = """SHELL OIL 57442
123 MAIN ST ELLENSBURG WA
11/18/2026 10:42 AM
TRANS# 004417
UNLEADED 18.2 GAL @ 3.359
SUBTOTAL 61.12
TAX 0.00
TOTAL $61.12
VISA ****1234 61.12
"""
SECRETS_MAIL = {
    "timesheet_company_mail": {"enabled": True, "backend": "gmail_smtp", "username": "clineair891@gmail.com", "password": "pw-test"},
}


class NotFound(Exception):
    pass


NotFound.__name__ = "WorksheetNotFound"


class WS:
    def __init__(self, book, title):
        self.book, self.title = book, title

    def row_values(self, n):
        rows = self.book.tabs[self.title]
        return list(rows[n - 1]) if len(rows) >= n else []

    def append_row(self, row, **kw):
        self.book.writes.append((self.title, list(row)))
        self.book.tabs[self.title].append(list(row))

    def get_all_values(self):
        return [list(r) for r in self.book.tabs[self.title]]


class Book:
    def __init__(self, tabs=None):
        self.tabs = tabs or {}
        self.writes = []
        self.created = []

    def worksheet(self, title):
        if title not in self.tabs:
            raise NotFound(title)
        return WS(self, title)

    def add_worksheet(self, title, rows, cols):
        self.tabs[title] = []
        self.created.append(title)
        return WS(self, title)


def _rec(employee, amount, kind, saved="2026-11-18 10:00:00 PST", day="2026-11-18", link="https://drive.google.com/file/d/X/view", job="CVH"):
    return {"Employee": employee, "Amount": amount, "Job": job, "Expense Type": kind, "Saved At": saved, "Date": day,
            "Purpose": "p", "Photo Link": link, "Vendor": "", "Receipt Number": "", "Photo File": "f.jpg"}


class ParseTests(unittest.TestCase):
    def test_fuel_receipt(self):
        f = er.parse_receipt_text(FUEL_TEXT)
        self.assertEqual(f["date"], date(2026, 11, 18))
        self.assertEqual(f["amount"], "61.12")
        self.assertEqual(f["number"], "004417")
        self.assertEqual(f["vendor"], "SHELL OIL 57442")

    def test_total_skips_subtotal_tax_and_uses_grand_total(self):
        text = "NAPA AUTO PARTS\nInvoice No: 88-1234\nNov 3, 2026\nSubtotal 1,200.00\nSales Tax 98.40\nTotal 1,298.40\nChange 0.00"
        f = er.parse_receipt_text(text)
        self.assertEqual(f["amount"], "1298.40")
        self.assertEqual(f["number"], "88-1234")
        self.assertEqual(f["date"], date(2026, 11, 3))

    def test_falls_back_to_largest_amount(self):
        self.assertEqual(er.find_total("coffee 3.50\nbagel 4.25\n7.75"), 7.75)

    def test_dates(self):
        self.assertEqual(er.parse_receipt_date("2026-11-20"), date(2026, 11, 20))
        self.assertEqual(er.parse_receipt_date("11/20/26"), date(2026, 11, 20))
        self.assertEqual(er.parse_receipt_date("20 Nov 2026"), date(2026, 11, 20))
        self.assertIsNone(er.parse_receipt_date("13/45/2026"))
        self.assertIsNone(er.parse_receipt_date(""))

    def test_amounts(self):
        self.assertEqual(er.parse_amount("$1,234.5"), 1234.5)
        self.assertEqual(er.format_amount("12"), "12.00")
        self.assertIsNone(er.parse_amount("-4"))
        self.assertIsNone(er.parse_amount("abc"))
        self.assertIsNone(er.parse_amount(True))

    def test_nothing_found(self):
        self.assertEqual(er.parse_receipt_text(""), {})
        fields, note = er.read_receipt(b"\xff\xd8\xff" + b"x" * 20, "a.jpg", ocr=lambda d: "")
        self.assertEqual(fields, {})
        self.assertEqual(note, er.NOT_READ_NOTE)


class ReadReceiptTests(unittest.TestCase):
    def test_image_uses_injected_ocr(self):
        fields, note = er.read_receipt(b"\xff\xd8\xff" + b"x" * 20, "image.jpg", ocr=lambda d: FUEL_TEXT)
        self.assertEqual(fields["amount"], "61.12")
        self.assertEqual(note, er.READ_NOTE)

    def test_no_ocr_falls_back_to_manual(self):
        import unittest.mock as mock
        with mock.patch.object(er, "ocr_available", return_value=False):
            fields, note = er.read_receipt(b"\x89PNG" + b"x" * 20, "a.png")
        self.assertEqual(fields, {})
        self.assertEqual(note, er.OCR_UNAVAILABLE_NOTE)

    def test_heic_is_manual(self):
        fields, note = er.read_receipt(b"\x00\x00\x00\x18ftypheic" + b"x" * 10, "IMG_1.HEIC")
        self.assertEqual(fields, {})
        self.assertIn("HEIC", note)

    def test_ocr_error_never_raises(self):
        def boom(_):
            raise RuntimeError("bad image")
        self.assertEqual(er.read_receipt(b"\xff\xd8\xff" + b"x", "a.jpg", ocr=boom), ({}, er.NOT_READ_NOTE))

    def test_real_pdf_prefill(self):
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        y = 700
        for line in FUEL_TEXT.splitlines():
            c.drawString(72, y, line)
            y -= 16
        c.save()
        fields, note = er.read_receipt(buf.getvalue(), "receipt.pdf")
        self.assertEqual(note, er.READ_NOTE)
        self.assertEqual(fields["amount"], "61.12")
        self.assertEqual(fields["date"], date(2026, 11, 18))
        self.assertEqual(fields["number"], "004417")

    @unittest.skipUnless(er.ocr_available(), "tesseract is not installed here")
    def test_real_photo_ocr(self):
        from PIL import Image, ImageDraw, ImageFont
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", 34)
        except Exception:
            font = ImageFont.load_default(size=34)
        img = Image.new("RGB", (900, 620), "white")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(FUEL_TEXT.splitlines()):
            draw.text((40, 30 + i * 62), line, fill="black", font=font)
        img = img.rotate(1.5, expand=True, fillcolor="white")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        fields, note = er.read_receipt(buf.getvalue(), "image.jpg")
        self.assertEqual(note, er.READ_NOTE)
        self.assertEqual(fields.get("amount"), "61.12")
        self.assertEqual(fields.get("date"), date(2026, 11, 18))


class UploadTests(unittest.TestCase):
    SECRETS = {"receipts": {"apps_script_url": "https://script.example/exec", "upload_token": "tok-123"}}
    WHEN = datetime(2026, 11, 20, 9, 30, 5, tzinfo=PT)

    def test_not_configured_keeps_filename_and_warns(self):
        link, stored, note = er.store_receipt_file(b"\xff\xd8\xffxx", "image.jpg", "Carl Mulvaney", "2026-11-18", "61.12", {}, when=self.WHEN)
        self.assertEqual(link, "")
        self.assertEqual(stored, "2026-11-18_Carl-Mulvaney_61-12_093005.jpg")
        self.assertEqual(note, er.UPLOAD_NOT_SET_UP_NOTE)

    def test_placeholder_secrets_count_as_not_configured(self):
        s = {"receipts": {"apps_script_url": "https://script.google.com/macros/s/replace-with-deployment-id/exec", "upload_token": "x"}}
        self.assertEqual(er.upload_config(s), ("", ""))

    def test_uploads_with_employee_and_mime(self):
        calls = []

        def up(data, filename, mime, employee, url, token, session=None):
            calls.append((filename, mime, employee, url))
            return "https://drive.google.com/file/d/ABC/view"
        link, stored, note = er.store_receipt_file(b"%PDF-1.4 x", "scan.pdf", "Gary Grant", "2026-11-18", "9", self.SECRETS, when=self.WHEN, uploader=up)
        self.assertEqual(link, "https://drive.google.com/file/d/ABC/view")
        self.assertEqual(note, "")
        self.assertEqual(calls, [("2026-11-18_Gary-Grant_9-00_093005.pdf", "application/pdf", "Gary Grant", "https://script.example/exec")])

    def test_upload_failure_does_not_raise(self):
        def up(*a, **k):
            raise ConnectionError("down")
        link, stored, note = er.store_receipt_file(b"\xff\xd8\xffxx", "a.jpg", "Gary Grant", "", "1", self.SECRETS, when=self.WHEN, uploader=up)
        self.assertEqual((link, note), ("", er.UPLOAD_FAILED_NOTE))
        self.assertTrue(stored.startswith("2026-11-20_Gary-Grant_1-00"))

    def test_apps_script_redirect_is_followed_with_get(self):
        class Resp:
            def __init__(self, code, headers=None, payload=None):
                self.status_code, self.headers, self._p, self.text = code, headers or {}, payload, ""

            def json(self):
                return self._p

            def raise_for_status(self):
                pass

        class Session:
            def __init__(self):
                self.calls = []

            def post(self, url, json=None, **kw):
                self.calls.append(("POST", url, sorted(json)))
                return Resp(302, {"Location": "https://script.googleusercontent.com/echo"})

            def get(self, url, **kw):
                self.calls.append(("GET", url))
                return Resp(200, {"Content-Type": "application/json"}, {"ok": True, "fileId": "F1"})
        s = Session()
        link = er.upload_via_apps_script(b"\xff\xd8\xffxx", "a.jpg", "image/jpeg", "Carl Mulvaney", "https://script.example/exec", "tok", session=s)
        self.assertEqual(link, "https://drive.google.com/file/d/F1/view")
        self.assertEqual(s.calls[0], ("POST", "https://script.example/exec", ["base64", "employee", "filename", "mimeType", "token"]))
        self.assertEqual(s.calls[1][0], "GET")

    def test_sniff(self):
        self.assertEqual(er.upload_extension("image", b"\x89PNG\r\n"), "png")
        self.assertEqual(er.upload_extension("x.JPEG", b""), "jpeg")
        self.assertEqual(er.mime_type_for("heic"), "image/heic")


class SheetTests(unittest.TestCase):
    def test_creates_receipts_tab_on_first_save_and_touches_nothing_else(self):
        frat_header = ["timestamp", "date", "part"]
        book = Book({"Sheet1": [list(frat_header)], "Time Sheets": [["Employee"]]})
        when = datetime(2026, 11, 20, 9, 0, tzinfo=PT)
        rec = er.build_receipt_record("Carl Mulvaney", {"date": date(2026, 11, 18), "amount": "61.12", "number": "004417",
                                                       "purpose": "Fuel", "vendor": "Shell"}, "BNSF", "Fuel",
                                      photo_link="https://drive.google.com/file/d/A/view", photo_file="a.jpg", when=when, entry_id="RC-1")
        er.save_receipt_record(rec, book)
        self.assertEqual(book.created, ["Receipts"])
        self.assertEqual(book.tabs["Receipts"][0], er.RECEIPTS_COLUMNS)
        self.assertEqual(book.tabs["Sheet1"], [frat_header])
        self.assertEqual({t for t, _ in book.writes}, {"Receipts"})
        saved = dict(zip(er.RECEIPTS_COLUMNS, book.tabs["Receipts"][1]))
        self.assertEqual(saved["Saved At"], "2026-11-20 09:00:00 PST")
        self.assertEqual(saved["Date"], "2026-11-18")
        self.assertEqual(saved["Amount"], "61.12")
        self.assertEqual((saved["Job"], saved["Expense Type"]), ("BNSF", "Fuel"))
        er.save_receipt_record(rec, book)
        self.assertEqual(book.created, ["Receipts"])
        self.assertEqual(len(book.tabs["Receipts"]), 3)

    def test_existing_header_order_is_respected(self):
        book = Book({"Receipts": [["Employee", "Amount", "Job"]]})
        er.save_receipt_record({"Employee": "A", "Amount": "1.00", "Job": "CVH", "Date": "x"}, book)
        self.assertEqual(book.tabs["Receipts"][1], ["A", "1.00", "CVH"])

    def test_read_is_read_only_and_filters_employee(self):
        book = Book()
        self.assertEqual(er.load_receipts_readonly(book), [])
        self.assertEqual(book.created, [])
        book = Book({"Receipts": [er.RECEIPTS_COLUMNS,
                                  ["2026-11-18 1 PST", "1", "Carl Mulvaney", "2026-11-18", "5.00"],
                                  ["2026-11-19 1 PST", "2", "Gary Grant", "2026-11-19", "6.00"]]})
        rows = er.load_receipts_readonly(book, employee="Gary Grant")
        self.assertEqual([r["Entry ID"] for r in rows], ["2"])
        self.assertEqual(book.writes, [])

    def test_job_and_expense_type_required_and_from_lists(self):
        f = {"date": "2026-11-18", "amount": "1", "purpose": "x"}
        with self.assertRaises(ValueError):
            er.build_receipt_record("A", f, "Candy", "Fuel")
        with self.assertRaises(ValueError):
            er.build_receipt_record("A", f, "CVH", "")
        self.assertEqual(er.build_receipt_record("A", f, "Other", "Other")["Job"], "Other")

    def test_validate(self):
        self.assertEqual(len(er.validate_receipt({})), 3)
        self.assertEqual(er.validate_receipt({"date": date(2026, 1, 1), "amount": "2", "purpose": "x"}), [])
        self.assertTrue(er.validate_receipt({"date": date(2026, 1, 1), "amount": "0", "purpose": "x"}))


class TotalsAndPeriodTests(unittest.TestCase):
    def test_totals_by_expense_type_within_each_job(self):
        recs = [_rec("A", "10", "Parts", job="BNSF"), _rec("A", "2.50", "Fuel", job="CVH"),
                _rec("A", "5", "Parts", job="BNSF"), _rec("A", "1", "Meals", job="BNSF"), _rec("A", "3", "Fuel", job="BNSF")]
        self.assertEqual(er.job_expense_totals(recs), {
            "CVH": {"total": 2.5, "types": {"Fuel": 2.5}},
            "BNSF": {"total": 19.0, "types": {"Fuel": 3.0, "Parts": 15.0, "Meals": 1.0}},
        })
        self.assertEqual(er.expense_type_totals(recs), {"Fuel": 5.5, "Parts": 15.0, "Meals": 1.0})
        self.assertEqual(er.grand_total(recs), 21.5)
        rows = er.totals_rows(recs)
        self.assertEqual([(r["Job"], r["Expense type"]) for r in rows], [
            ("CVH", "Fuel"), ("CVH total", ""), ("BNSF", "Fuel"), ("BNSF", "Parts"), ("BNSF", "Meals"),
            ("BNSF total", ""), ("All jobs", "")])
        self.assertEqual(rows[-1]["Total"], 21.5)

    def test_menus(self):
        self.assertEqual(er.RECEIPT_JOBS, ("CVH", "BNSF", "Forestry", "Other"))
        self.assertEqual(er.RECEIPT_EXPENSE_TYPES, ("Fuel", "Parts", "Meals", "Lodging", "Supplies", "Other"))
        self.assertEqual(er.RECEIPTS_OFFICE_USERS, ("Ron Cline", "Patti"))

    def test_counts_by_day_entered_not_receipt_date(self):
        old_receipt_entered_late = _rec("A", "5", "Fuel", saved="2026-11-29 07:00:00 PST", day="2026-11-10")
        self.assertFalse(er.in_period(old_receipt_entered_late, date(2026, 11, 15), date(2026, 11, 28)))
        self.assertTrue(er.in_period(old_receipt_entered_late, date(2026, 11, 29), date(2026, 12, 12)))

    def test_periods(self):
        self.assertEqual(er.RECEIPTS_PERIOD_ANCHOR.weekday(), 6)  # Sunday
        self.assertEqual(er.period_for(date(2026, 11, 20)), (date(2026, 11, 15), date(2026, 11, 28)))
        self.assertEqual(er.period_for(date(2026, 11, 29)), (date(2026, 11, 29), date(2026, 12, 12)))
        self.assertEqual(er.period_for(date(2026, 11, 14)), (date(2026, 11, 1), date(2026, 11, 14)))
        self.assertEqual(er.previous_period(date(2026, 11, 30)), (date(2026, 11, 15), date(2026, 11, 28)))

    def test_due_every_other_monday(self):
        due = [d for d in (date(2026, 11, 16), date(2026, 11, 23), date(2026, 11, 30), date(2026, 12, 7), date(2026, 12, 14))
               if er.summary_due_on(d)]
        self.assertEqual(due, [date(2026, 11, 16), date(2026, 11, 30), date(2026, 12, 14)])
        self.assertFalse(er.summary_due_on(date(2026, 12, 1)))

    def test_summary_groups_by_employee_and_period(self):
        recs = [
            _rec("Carl Mulvaney", "10", "Fuel", saved="2026-11-16 08:00:00 PST"),
            _rec("Carl Mulvaney", "4", "Meals", saved="2026-11-28 20:00:00 PST", job="BNSF"),
            _rec("Gary Grant", "7", "Parts", saved="2026-11-20 08:00:00 PST", link=""),
            _rec("Gary Grant", "99", "Parts", saved="2026-11-29 08:00:00 PST"),
        ]
        s = er.build_summary(recs, date(2026, 11, 15), date(2026, 11, 28), employees=["Ron Cline", "Carl Mulvaney", "Gary Grant"])
        self.assertEqual([p["employee"] for p in s["employees"]], ["Carl Mulvaney", "Gary Grant"])
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["total"], 21.0)
        self.assertEqual(s["employees"][0]["jobs"], {"CVH": {"total": 10.0, "types": {"Fuel": 10.0}},
                                                     "BNSF": {"total": 4.0, "types": {"Meals": 4.0}}})
        text = er.summary_text(s)
        self.assertIn("Carl Mulvaney – $14.00", text)
        self.assertIn("  BNSF: $4.00\n    Meals: $4.00", text)
        self.assertIn("By expense type (all jobs): Fuel $10.00, Meals $4.00", text)
        self.assertIn("CVH / Fuel", text)
        self.assertIn("Photo: https://drive.google.com/file/d/X/view", text)
        self.assertIn("not on Drive (f.jpg)", text)
        html = er.summary_html(s)
        self.assertIn('href="https://drive.google.com/file/d/X/view"', html)
        self.assertIn("<b>BNSF total</b>", html)
        self.assertEqual(er.summary_subject(s), "CVH employee receipts: Nov 15 – Nov 28, 2026")

    def test_summary_escapes_html(self):
        r = _rec("A", "1", "CVH")
        r["Purpose"] = "<script>x</script>"
        html = er.summary_html(er.build_summary([r], date(2026, 11, 15), date(2026, 11, 28)))
        self.assertNotIn("<script>", html)


class MailTests(unittest.TestCase):
    def _summary(self):
        return er.build_summary([_rec("Carl Mulvaney", "10", "Fuel", saved="2026-11-16 08:00:00 PST")], date(2026, 11, 15), date(2026, 11, 28))

    def test_message_from_company_gmail_to_patti(self):
        sent = []
        r = er.send_summary(self._summary(), SECRETS_MAIL, smtp_send=lambda u, p, m: sent.append((u, m)))
        self.assertEqual(r["status"], er.STATUS_SENT)
        user, msg = sent[0]
        self.assertEqual(user, "clineair891@gmail.com")
        self.assertEqual(msg["To"], "patti@centralvalleyheli.com")
        self.assertIn("clineair891@gmail.com", msg["From"])
        self.assertEqual(msg["Subject"], "CVH employee receipts: Nov 15 – Nov 28, 2026")
        self.assertEqual([p.get_content_type() for p in msg.iter_parts()], ["text/plain", "text/html"])

    def test_not_configured_never_sends(self):
        for secrets in ({}, {"timesheet_company_mail": dict(SECRETS_MAIL["timesheet_company_mail"], enabled=False)}):
            r = er.send_summary(self._summary(), secrets, smtp_send=lambda *a: self.fail("sent"))
            self.assertEqual(r["error"], er.MAIL_NOT_READY_MESSAGE)

    def test_automatic_needs_auto_send_flag(self):
        r = er.send_summary(self._summary(), SECRETS_MAIL, trigger="Automatic", smtp_send=lambda *a: self.fail("sent"))
        self.assertEqual(r["status"], er.STATUS_SKIPPED)
        self.assertFalse(er.auto_send_enabled(SECRETS_MAIL))
        self.assertFalse(er.auto_send_enabled({"receipts_mail": {"auto_send": "false"}}))
        self.assertTrue(er.auto_send_enabled({"receipts_mail": {"auto_send": True}}))

    def test_duplicate_blocked_unless_resend(self):
        s = self._summary()
        audit = [{"Idempotency Key": er.idempotency_key(s), "Status": er.STATUS_SENT}]
        r = er.send_summary(s, SECRETS_MAIL, audit_records=audit, smtp_send=lambda *a: self.fail("sent"))
        self.assertEqual(r["status"], er.STATUS_DUPLICATE)
        sent = []
        r = er.send_summary(s, SECRETS_MAIL, audit_records=audit, allow_resend=True, smtp_send=lambda *a: sent.append(1))
        self.assertEqual((r["status"], sent), (er.STATUS_SENT, [1]))

    def test_errors_hide_password(self):
        def boom(u, p, m):
            raise RuntimeError("535 auth failed for " + p)
        r = er.send_summary(self._summary(), SECRETS_MAIL, smtp_send=boom)
        self.assertEqual(r["status"], er.STATUS_DENIED)
        self.assertNotIn("pw-test", repr(r))

    def test_scheduled_run_gates(self):
        row = {"Saved At": "2026-11-16 08:00:00 PST", "Entry ID": "1", "Employee": "Carl Mulvaney", "Date": "2026-11-16",
               "Amount": "10.00", "Purpose": "p", "Job": "CVH", "Expense Type": "Fuel", "Photo File": "f"}
        book = Book({"Receipts": [er.RECEIPTS_COLUMNS, [row.get(c, "") for c in er.RECEIPTS_COLUMNS]]})
        sent = []
        smtp = lambda u, p, m: sent.append(m["Subject"])  # noqa: E731
        status, _ = er.run_scheduled_send(book, SECRETS_MAIL, today=date(2026, 11, 30), smtp_send=smtp)
        self.assertEqual((status, sent, book.writes), (er.STATUS_SKIPPED, [], []))
        on = dict(SECRETS_MAIL, receipts_mail={"auto_send": True})
        status, _ = er.run_scheduled_send(book, on, today=date(2026, 12, 7), smtp_send=smtp)
        self.assertEqual((status, sent), (er.STATUS_SKIPPED, []))
        status, _ = er.run_scheduled_send(book, on, today=date(2026, 11, 30), smtp_send=smtp)
        self.assertEqual(status, er.STATUS_SENT)
        self.assertEqual(sent, ["CVH employee receipts: Nov 15 – Nov 28, 2026"])
        self.assertEqual(book.tabs["Receipts Mail"][0], er.RECEIPTS_MAIL_COLUMNS)
        self.assertEqual(dict(zip(er.RECEIPTS_MAIL_COLUMNS, book.tabs["Receipts Mail"][1]))["Sent By"], "Schedule")
        status, _ = er.run_scheduled_send(book, on, today=date(2026, 11, 30), smtp_send=smtp)
        self.assertEqual((status, len(sent)), (er.STATUS_DUPLICATE, 1))


class OfficePinTests(unittest.TestCase):
    def test_patti_is_a_pin_identity_but_not_an_employee(self):
        import timesheet_pin as pin
        self.assertIn("Patti", pin.PIN_OFFICE_USERS)
        self.assertNotIn("Patti", pin.PIN_EMPLOYEES)
        self.assertTrue(pin.identity_allowed("Patti"))
        self.assertFalse(pin.employee_allowed("Patti"))
        secret = "test-cookie-secret-0123456789"
        token = pin.sign_device_cookie("Patti", secret, now=1_800_000_000)
        self.assertEqual(pin.verify_device_cookie(token, secret, now=1_800_000_001), "Patti")
        h = pin.make_pin_hash("4321")
        s = {"timesheet_pin": {"cookie_secret": secret}, "timesheet_pins": {"Patti": h}}
        self.assertEqual(pin.attempt_pin("Patti", "4321", s, 0), ("ok", 0))
        self.assertFalse(pin.identity_allowed("Somebody"))

    def test_patti_cannot_open_a_time_sheet(self):
        src = (ROOT / "app.py").read_text()
        self.assertIn("timesheet_pin.employee_allowed(identity) and identity == employee", src)


class WiringTests(unittest.TestCase):
    SOURCE = (ROOT / "app.py").read_text()

    def test_every_employee_page_has_receipts_behind_pin(self):
        tree = ast.parse(self.SOURCE)
        fn = {n.name: ast.get_source_segment(self.SOURCE, n) for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('show_employee_section_switch(selected) == "Receipts"', fn["show_employees_page"])
        self.assertIn("show_timesheet_pin_gate(employee", fn["show_employee_receipts"])
        self.assertIn("show_receipts_summary_page()", fn["show_employees_page"])
        self.assertIn("show_receipts_office_gate()", fn["show_receipts_summary_page"])
        self.assertNotIn("show_receipts_summary_office", fn["show_employee_receipts"])
        self.assertIn("st.camera_input", fn["show_receipt_entry"])
        self.assertIn("st.file_uploader", fn["show_receipt_entry"])

    def test_bundled_files(self):
        self.assertIn("pytesseract", (ROOT / "requirements.txt").read_text())
        self.assertIn("tesseract-ocr", (ROOT / "packages.txt").read_text())
        gs = (ROOT / "apps_script" / "receipt_upload" / "Code.gs").read_text()
        self.assertIn("RECEIPTS_FOLDER_ID", gs)
        self.assertNotIn("setTrashed", gs)
        self.assertFalse((ROOT / ".github" / "workflows" / "receipts-summary.yml").exists())


if __name__ == "__main__":
    unittest.main()
