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

    def update_cell(self, row, col, value):
        rows = self.book.tabs[self.title]
        while len(rows) < row:
            rows.append([])
        line = rows[row - 1]
        while len(line) < col:
            line.append("")
        line[col - 1] = value
        self.book.writes.append((self.title, "update_cell", row, col, value))


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
        self.assertEqual(f["gallons"], "18.2")

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

    def test_heic_is_read_when_pillow_heif_is_available(self):
        if not er.heic_available():
            self.skipTest("pillow-heif is not installed")
        import pillow_heif
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (900, 400), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        draw.text((20, 40), "SHELL OIL 57442", fill="black", font=font)
        draw.text((20, 90), "11/18/2026", fill="black", font=font)
        draw.text((20, 140), "TOTAL $61.12", fill="black", font=font)
        buf = io.BytesIO()
        pillow_heif.from_pillow(img).save(buf, format="HEIF")
        data = buf.getvalue()
        self.assertEqual(er.upload_extension("IMG_1.HEIC", data), "heic")
        fields, note = er.read_receipt(data, "IMG_1.HEIC", ocr=lambda d: FUEL_TEXT)
        self.assertEqual(note, er.READ_NOTE)
        self.assertEqual(fields["amount"], "61.12")

    def test_huge_photo_is_downscaled_before_ocr(self):
        from PIL import Image
        img = Image.new("RGB", (4000, 3000), "white")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        prepared = er._prepare_image(buf.getvalue())
        self.assertLessEqual(max(prepared.size), er.MAX_OCR_EDGE)

    def test_scanned_pdf_falls_back_to_ocr(self):
        fields, note = er.read_receipt(
            b"%PDF-1.4 scanned",
            "scan.pdf",
            pdf_reader=lambda d: "",
            pdf_renderer=lambda d: [b"\xff\xd8\xffpage"],
            ocr=lambda d: FUEL_TEXT,
        )
        self.assertEqual(note, er.READ_NOTE)
        self.assertEqual(fields["amount"], "61.12")
        self.assertEqual(fields["date"], date(2026, 11, 18))

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
                                                       "purpose": "Fuel", "vendor": "Shell"}, "BNSF", subcategory="Vehicle fuel",
                                      ifta_state="WA", ifta_gallons="18.2",
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
        self.assertEqual((saved["Job"], saved["Expense Type"]), ("BNSF", "Vehicle fuel"))
        self.assertEqual(saved["Category"], "BNSF")
        self.assertEqual(saved["Subcategory"], "Vehicle fuel")
        self.assertEqual(saved["IFTA State"], "WA")
        self.assertEqual(saved["IFTA Gallons"], "18.2")
        er.save_receipt_record(rec, book)
        self.assertEqual(book.created, ["Receipts"])
        self.assertEqual(len(book.tabs["Receipts"]), 3)

    def test_existing_header_order_is_respected(self):
        original = ["Employee", "Amount", "Job"]
        book = Book({"Receipts": [list(original)]})
        er.save_receipt_record({"Employee": "A", "Amount": "1.00", "Job": "CVH", "Date": "x", "Category": "Dues"}, book)
        header = book.tabs["Receipts"][0]
        self.assertEqual(header[:3], original)
        for col in er.RECEIPTS_ADDED_COLUMNS:
            self.assertIn(col, header)
        self.assertEqual(book.tabs["Receipts"][1][:3], ["A", "1.00", "CVH"])
        self.assertEqual(book.tabs["Receipts"][1][header.index("Category")], "Dues")

    def test_original_receipts_headers_are_appended_not_reordered(self):
        book = Book({"Receipts": [list(er.RECEIPTS_ORIGINAL_COLUMNS)]})
        er.save_receipt_record({"Employee": "A", "Amount": "1.00", "Category": "Dues"}, book)
        header = book.tabs["Receipts"][0]
        self.assertEqual(header[:len(er.RECEIPTS_ORIGINAL_COLUMNS)], list(er.RECEIPTS_ORIGINAL_COLUMNS))
        self.assertEqual(header[len(er.RECEIPTS_ORIGINAL_COLUMNS):], list(er.RECEIPTS_ADDED_COLUMNS))

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

    def test_category_required_and_from_list(self):
        f = {"date": "2026-11-18", "amount": "1", "purpose": "x", "other_comment": "misc"}
        with self.assertRaises(ValueError):
            er.build_receipt_record("A", f, "Candy")
        with self.assertRaises(ValueError):
            er.build_receipt_record("A", f, "")
        rec = er.build_receipt_record("A", f, "Other")
        self.assertEqual(rec["Category"], "Other")
        self.assertEqual(rec["Job"], "CVH")
        self.assertEqual(rec["Notes"], "misc")

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
        self.assertEqual([(r["Category"], r["Detail"]) for r in rows], [
            ("BNSF", "Parts"), ("BNSF", "Travel"), ("BNSF", "Fuel"),
            ("BNSF total", ""), ("Fuel total", ""), ("All categories", "")])
        self.assertEqual(rows[-1]["Total"], 21.5)

    def test_menus(self):
        self.assertEqual(er.RECEIPT_CATEGORIES[0], "Dues")
        self.assertIn("Licenses & Permits", er.RECEIPT_CATEGORIES)
        self.assertIn("Equipment", er.RECEIPT_CATEGORIES)
        self.assertNotIn("Repairs for Equipment", er.RECEIPT_CATEGORIES)
        self.assertEqual(er.RECEIPT_BUILDINGS, (
            "Hangar House", "Enstrom Hangar", "TS", "R44 Hangar", "Other",
        ))
        self.assertEqual(er.RECEIPT_JOB_SUBCATEGORIES, (
            "Travel", "Supplies", "Heli fuel", "Vehicle fuel", "Other",
        ))
        self.assertEqual(er.RECEIPT_FUEL_TYPES, (
            "Jet A", "AvGas", "Regular ground (gas)", "Diesel",
        ))
        self.assertEqual(er.RECEIPT_EQUIPMENT_PURPOSES, (
            "Diesel Fuel", "Gas", "JetA", "AvGas", "Parts",
        ))
        self.assertEqual(er.RECEIPT_VENDORS, (
            "Bruckners", "Mid State Co-Op", "Knudson", "Ranch & Home",
            "Kittitas County Solid Waste", "Napa", "Oxac", "Les Schwab", "Other",
        ))
        self.assertNotIn("None", er.RECEIPT_VENDORS)
        self.assertEqual(er.RECEIPT_VENDORS[-1], "Other")
        self.assertIn("Les Schwab", er.RECEIPT_STATEMENT_ACCOUNTS)
        self.assertEqual(er.RECEIPT_STATEMENT_ACCOUNTS[0], "None")
        self.assertEqual(er.RECEIPTS_OFFICE_USERS, ("Ron Cline", "Patti"))
        # Older Job / Expense type lists remain for reading saved receipts.
        self.assertEqual(er.RECEIPT_JOBS, ("CVH", "BNSF", "Forestry", "Other"))
        self.assertEqual(er.RECEIPT_EXPENSE_TYPES, ("Fuel", "Parts", "Meals", "Lodging", "Supplies", "Other"))

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
        self.assertEqual(s["employees"][0]["categories"], {
            "Fuel": {"total": 10.0, "details": {}},
            "BNSF": {"total": 4.0, "details": {"Travel": 4.0}},
        })
        text = er.summary_text(s)
        self.assertIn("Carl Mulvaney – $14.00", text)
        self.assertIn("  BNSF: $4.00\n    Travel: $4.00", text)
        self.assertIn("By category: BNSF $4.00, Fuel $10.00", text)
        self.assertIn("BNSF / Travel", text)
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


class LiveViewTests(unittest.TestCase):
    def test_period_to_date_and_this_month(self):
        day = date(2026, 11, 20)
        self.assertEqual(er.period_to_date(day), (date(2026, 11, 15), date(2026, 11, 20)))
        self.assertEqual(er.month_to_date(day), (date(2026, 11, 1), date(2026, 11, 20)))
        self.assertEqual(
            er.resolve_summary_range(er.RANGE_PERIOD_TO_DATE, today=day),
            (date(2026, 11, 15), date(2026, 11, 20)),
        )
        self.assertEqual(
            er.resolve_summary_range(er.RANGE_THIS_MONTH, today=day),
            (date(2026, 11, 1), date(2026, 11, 20)),
        )
        self.assertEqual(
            er.resolve_summary_range(er.RANGE_PAY_PERIOD, today=day, period=(date(2026, 11, 1), date(2026, 11, 14))),
            (date(2026, 11, 1), date(2026, 11, 14)),
        )
        self.assertEqual(
            er.resolve_summary_range(er.RANGE_CUSTOM, today=day, custom_start=date(2026, 11, 20), custom_end=date(2026, 11, 10)),
            (date(2026, 11, 10), date(2026, 11, 20)),
        )
        self.assertEqual(er.resolve_summary_range(er.RANGE_ALL_DATES, today=day), (None, None))
        self.assertEqual(er.SUMMARY_RANGE_CHOICES[0], er.RANGE_ALL_DATES)
        self.assertEqual(
            er.summary_range_label(date(2026, 11, 15), date(2026, 11, 20), er.RANGE_PERIOD_TO_DATE),
            "Nov 15 – Nov 20, 2026 (period to date)",
        )
        self.assertEqual(er.summary_range_label(None, None, er.RANGE_ALL_DATES), "All dates")

    def test_filters_and_employee_totals(self):
        recs = [
            _rec("Carl Mulvaney", "10", "Fuel", saved="2026-11-16 08:00:00 PST", job="BNSF"),
            _rec("Gary Grant", "7", "Parts", saved="2026-11-20 08:00:00 PST", job="CVH"),
            _rec("Carl Mulvaney", "4", "Meals", saved="2026-11-01 09:00:00 PST", job="CVH"),
        ]
        shown = er.filter_receipts(recs, date(2026, 11, 15), date(2026, 11, 20), employee="Carl Mulvaney")
        self.assertEqual(len(shown), 1)
        self.assertEqual(er.grand_total(shown), 10.0)
        all_dates = er.filter_receipts(recs, None, None, employee="Carl Mulvaney")
        self.assertEqual(len(all_dates), 2)
        self.assertEqual(er.grand_total(all_dates), 14.0)
        self.assertEqual(
            [h for h, _k in er.query_subtotal_sections(employee="Carl Mulvaney")],
            ["Totals by category", "Totals by vendor and month"],
        )
        self.assertEqual(
            [h for h, _k in er.query_subtotal_sections(vendor="Napa")],
            ["Totals by employee", "Totals by category"],
        )
        self.assertEqual(
            [h for h, _k in er.query_subtotal_sections(category="Fuel")],
            ["Totals by employee", "Totals by vendor and month"],
        )
        self.assertEqual(
            [k for _h, k in er.query_subtotal_sections()],
            ["employee", "category", "vendor"],
        )
        rows = er.employee_totals_rows(er.filter_receipts(recs, date(2026, 11, 15), date(2026, 11, 20)))
        self.assertEqual([r["Employee"] for r in rows], ["Carl Mulvaney", "Gary Grant", "All employees"])
        self.assertEqual(rows[-1]["Total"], 17.0)
        table = er.office_table_rows(shown)
        self.assertEqual(list(table[0]), list(er.OFFICE_TABLE_COLUMNS))
        self.assertEqual(table[0]["Saved"], "2026-11-16")
        self.assertIn("https://drive.google.com/file/d/X/view", er.summary_csv(shown))

    def test_dedupe_key_includes_range_and_filters(self):
        recs = [_rec("Carl Mulvaney", "10", "Fuel", saved="2026-11-16 08:00:00 PST", job="BNSF")]
        period = er.build_summary(recs, date(2026, 11, 15), date(2026, 11, 28))
        ptd = er.build_summary(recs, date(2026, 11, 15), date(2026, 11, 20), range_kind=er.RANGE_PERIOD_TO_DATE)
        filtered = er.build_summary(
            recs, date(2026, 11, 15), date(2026, 11, 28), employee="Carl Mulvaney", job="BNSF",
        )
        custom = er.build_summary(recs, date(2026, 11, 10), date(2026, 11, 20), range_kind=er.RANGE_CUSTOM)
        self.assertEqual(er.idempotency_key(period), "receipts:2026-11-15:2026-11-28")
        self.assertEqual(er.idempotency_key(ptd), "receipts:2026-11-15:2026-11-20")
        self.assertEqual(er.idempotency_key(filtered), "receipts:2026-11-15:2026-11-28:emp=Carl Mulvaney|job=BNSF")
        self.assertEqual(er.idempotency_key(custom), "receipts:2026-11-10:2026-11-20")
        all_dates = er.build_summary(recs, None, None, range_kind=er.RANGE_ALL_DATES)
        self.assertEqual(all_dates["label"], "All dates")
        self.assertEqual(er.idempotency_key(all_dates), "receipts:all")
        self.assertTrue(er.summary_text(all_dates).startswith("All employee receipts."))
        self.assertEqual(er.summary_subject(all_dates), "CVH employee receipts: All dates")
        audit = er.build_mail_audit_record(all_dates, {"status": er.STATUS_SENT, "trigger": "Manual", "idempotency_key": "receipts:all"}, sent_by="Patti")
        self.assertEqual(audit["Period Start"], "")
        self.assertEqual(audit["Period End"], "")
        self.assertEqual(audit["Idempotency Key"], "receipts:all")
        self.assertNotEqual(er.idempotency_key(period), er.idempotency_key(ptd))
        self.assertNotEqual(er.idempotency_key(period), er.idempotency_key(custom))
        self.assertNotEqual(er.idempotency_key(period), er.idempotency_key(filtered))
        self.assertNotEqual(er.idempotency_key(all_dates), er.idempotency_key(period))
        self.assertIn("Filters: Employee: Carl Mulvaney, Job: BNSF", er.summary_text(filtered))
        self.assertIn("(period to date)", er.summary_subject(ptd))
        # A later unfiltered send of the same dates still matches the old period key.
        again = er.build_summary(recs, date(2026, 11, 15), date(2026, 11, 28))
        self.assertTrue(er.already_sent([{"Idempotency Key": er.idempotency_key(period), "Status": er.STATUS_SENT}], again))
        self.assertFalse(er.already_sent([{"Idempotency Key": er.idempotency_key(period), "Status": er.STATUS_SENT}], ptd))

    def test_mail_ready_matches_timesheet_smtp_but_not_graph(self):
        import timesheet_company_mail as company_mail
        self.assertTrue(er.mail_ready(SECRETS_MAIL))
        graph = {"timesheet_company_mail": {
            "enabled": True, "backend": "graph", "sender": "clineair891@gmail.com",
            "tenant_id": "tenant", "client_id": "client", "client_secret": "secret",
        }}
        self.assertTrue(company_mail.company_mail_ready(graph))
        self.assertFalse(er.mail_ready(graph))
        self.assertFalse(er.mail_ready({"timesheet_company_mail": dict(SECRETS_MAIL["timesheet_company_mail"], enabled=False)}))


class CategoryAndIftaTests(unittest.TestCase):
    def test_legacy_rows_map_to_new_categories(self):
        self.assertEqual(er.map_legacy_category("BNSF", "Fuel"), "BNSF")
        self.assertEqual(er.map_legacy_subcategory("BNSF", "Fuel"), "Fuel")
        self.assertEqual(er.map_legacy_category("Forestry", "Supplies"), "Forestry")
        self.assertEqual(er.map_legacy_subcategory("Forestry", "Supplies"), "Supplies")
        self.assertEqual(er.map_legacy_category("CVH", "Fuel"), "Fuel")
        self.assertEqual(er.map_legacy_category("CVH", "Parts"), "Equipment")
        self.assertEqual(er.map_legacy_category("Other", "Meals"), "Travel")
        self.assertEqual(er.map_legacy_category("CVH", "Lodging"), "Travel")
        self.assertEqual(er.map_legacy_category("CVH", "Supplies"), "Shop Supplies")
        rec = _rec("A", "10", "Parts", job="CVH")
        self.assertEqual(er.receipt_category(rec), "Equipment")
        self.assertEqual(er.receipt_category({"Category": "Dues", "Job": "CVH", "Expense Type": "Other"}), "Dues")

    def test_category_totals_include_mapped_legacy_rows(self):
        recs = [_rec("A", "10", "Parts", job="BNSF"), _rec("A", "2.50", "Fuel", job="CVH"),
                _rec("A", "5", "Parts", job="BNSF"), _rec("A", "1", "Meals", job="BNSF"), _rec("A", "3", "Fuel", job="BNSF")]
        totals = er.category_totals(recs)
        self.assertEqual(totals["Fuel"]["total"], 2.5)
        self.assertEqual(totals["BNSF"]["total"], 19.0)
        self.assertEqual(totals["BNSF"]["details"], {"Parts": 15.0, "Travel": 1.0, "Fuel": 3.0})
        rows = er.totals_rows(recs)
        self.assertEqual(rows[-1], {"Category": "All categories", "Detail": "", "Total": 21.5})
        self.assertIn({"Category": "Fuel total", "Detail": "", "Total": 2.5}, rows)

    def test_equipment_shares_remaining_and_warning(self):
        shares = [("Ram", "20.00"), ("PW", "10.00")]
        self.assertEqual(er.format_equipment_shares(shares), "Ram=20.00; PW=10.00")
        self.assertEqual(er.parse_equipment_shares("Ram=20.00; PW=10.00"), [("Ram", 20.0), ("PW", 10.0)])
        self.assertEqual(er.equipment_share_remaining("61.12", shares), 31.12)
        self.assertIn("still left", er.equipment_share_warning("61.12", shares))
        self.assertEqual(er.equipment_share_warning("30.00", shares), "")
        self.assertIn("over the receipt total", er.equipment_share_warning("20.00", shares))
        self.assertEqual(
            er.equipment_names_from_records(
                [{"Unit ID": "Ram", "Name": "Ram", "Active": "Yes"}, {"Unit ID": "Old", "Name": "Old", "Active": "No"}],
                is_active=lambda r: r.get("Active") == "Yes",
                fallback=["Heli1"],
            ),
            ["Ram"],
        )
        self.assertEqual(er.equipment_names_from_records([], fallback=["Heli1", "Ram"]), ["Heli1", "Ram"])

    def test_equipment_allocation_requires_unit_and_purpose_but_not_a_zero_remainder(self):
        f = {"date": "2026-11-18", "amount": "30.00", "purpose": "parts"}
        self.assertIn("Choose at least one piece of equipment.", er.validate_receipt_allocation(f, "Equipment"))
        self.assertIn(
            "Choose a purpose for this equipment receipt.",
            er.validate_receipt_allocation(f, "Equipment", equipment_shares=[("Ram", 20)]),
        )
        self.assertEqual(
            er.validate_receipt_allocation(
                f, "Equipment", equipment_shares=[("Ram", 20)], equipment_purpose="Parts",
            ),
            [],
        )
        rec = er.build_receipt_record(
            "A", f, "Equipment", equipment_shares=[("Ram", 20), ("PW", 10)], equipment_purpose="Parts", memo="filter",
        )
        self.assertEqual(rec["Equipment Shares"], "Ram=20.00; PW=10.00")
        self.assertEqual(rec["Equipment Purpose"], "Parts")
        self.assertEqual(rec["Memo"], "filter")
        self.assertEqual((rec["Job"], rec["Expense Type"]), ("CVH", "Parts"))

    def test_other_and_building_other_need_a_comment(self):
        f = {"date": "2026-11-18", "amount": "5", "purpose": ""}
        self.assertIn("Enter a comment for this Other receipt.", er.validate_receipt_allocation(f, "Other"))
        self.assertEqual(er.validate_receipt_allocation(dict(f, purpose="misc"), "Other", other_comment=""), [])
        self.assertIn("Enter the building name.", er.validate_receipt_allocation(f, "Buildings", subcategory="Other"))
        self.assertEqual(
            er.validate_receipt_allocation(f, "Buildings", subcategory="Other", subcategory_detail="shed"),
            [],
        )

    def test_ifta_detection_and_quarter_report(self):
        self.assertTrue(er.is_ifta_fuel("Fuel", "Diesel"))
        self.assertTrue(er.is_ifta_fuel("Fuel", "Regular ground (gas)"))
        self.assertFalse(er.is_ifta_fuel("Fuel", "Jet A"))
        self.assertTrue(er.is_ifta_fuel("Equipment", "", "Diesel Fuel"))
        self.assertTrue(er.is_ifta_fuel("Equipment", "", "Gas"))
        self.assertFalse(er.is_ifta_fuel("Equipment", "", "JetA"))
        self.assertTrue(er.is_ifta_fuel("BNSF", "Vehicle fuel"))
        self.assertFalse(er.is_ifta_fuel("BNSF", "Heli fuel"))
        self.assertTrue(er.is_ifta_fuel("Forestry", "Vehicle fuel"))
        self.assertIn("gallons purchased", er.ifta_warning("Fuel", "Diesel", state="WA", gallons=""))
        self.assertEqual(er.ifta_warning("Fuel", "Diesel", state="WA", gallons="18.2"), "")
        recs = [
            dict(_rec("Carl Mulvaney", "61.12", "Fuel", job="CVH", saved="2026-11-18 10:00:00 PST", day="2026-11-18"),
                 **{"Category": "Fuel", "Subcategory": "Diesel", "IFTA State": "WA", "IFTA Gallons": "18.2"}),
            dict(_rec("Gary Grant", "40.00", "Fuel", job="BNSF", saved="2026-11-19 10:00:00 PST", day="2026-11-19"),
                 **{"Category": "BNSF", "Subcategory": "Vehicle fuel", "IFTA State": "OR", "IFTA Gallons": "10"}),
            dict(_rec("Carl Mulvaney", "9.00", "Fuel", job="CVH", saved="2026-08-01 10:00:00 PST", day="2026-08-01"),
                 **{"Category": "Fuel", "Subcategory": "Diesel", "IFTA State": "WA", "IFTA Gallons": "4"}),
            _rec("Carl Mulvaney", "20.00", "Parts", job="CVH", saved="2026-11-18 11:00:00 PST"),
        ]
        year, quarter, start, end = er.ifta_quarter(date(2026, 11, 20))
        self.assertEqual((year, quarter, start, end), (2026, 4, date(2026, 10, 1), date(2026, 12, 31)))
        chosen = er.ifta_receipts_in_quarter(recs, 2026, 4)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(er.ifta_gallons_by_state(chosen), {"OR": 10.0, "WA": 18.2})
        csv_text = er.ifta_csv(chosen, 2026, 4)
        self.assertIn("IFTA gallons Q4 2026", csv_text)
        self.assertIn("WA — Washington,18.2", csv_text)
        self.assertIn("All states,28.2", csv_text)

    def test_match_listed_vendor_is_case_and_punctuation_insensitive(self):
        self.assertEqual(er.match_listed_vendor("NAPA Auto Parts"), "Napa")
        self.assertEqual(er.match_listed_vendor("napa"), "Napa")
        self.assertEqual(er.match_listed_vendor("Mid-State Co-Op"), "Mid State Co-Op")
        self.assertEqual(er.match_listed_vendor("mid state coop"), "Mid State Co-Op")
        self.assertEqual(er.match_listed_vendor("Knudson's"), "Knudson")
        self.assertEqual(er.match_listed_vendor("Kittitas County Solid Waste"), "Kittitas County Solid Waste")
        self.assertEqual(er.match_listed_vendor("SHELL OIL"), "")
        self.assertEqual(er.match_listed_vendor("Home Depot"), "")
        self.assertEqual(er.match_listed_vendor(""), "")
        self.assertEqual(er.vendor_choice_from_text("NAPA Auto Parts"), ("Napa", ""))
        self.assertEqual(er.vendor_choice_from_text("SHELL OIL"), ("Other", "SHELL OIL"))
        self.assertEqual(er.vendor_choice_from_text(""), ("", ""))
        self.assertEqual(er.resolve_vendor("Napa", ""), "Napa")
        self.assertEqual(er.resolve_vendor("Other", "Shell Oil"), "Shell Oil")
        self.assertEqual(er.resolve_vendor("Other", ""), "")

    def test_vendor_totals_and_filter_use_statement_or_free_text(self):
        recs = [
            # Old receipt: statement vendor set, free-text vendor ignored for grouping.
            dict(_rec("A", "10", "Fuel", saved="2026-11-16 08:00:00 PST"),
                 **{"Statement Account": "Napa", "Vendor": "NAPA Auto Parts", "Category": "Shop Supplies"}),
            # Old receipt: only the statement column was filled.
            dict(_rec("A", "5", "Parts", saved="2026-11-18 08:00:00 PST"),
                 **{"Statement Account": "Napa", "Vendor": "", "Category": "Equipment"}),
            dict(_rec("B", "7", "Fuel", saved="2026-11-16 09:00:00 PST"),
                 **{"Vendor": "Bruckners", "Category": "Fuel"}),
            # Free-text vendor that is not on the list.
            dict(_rec("B", "4", "Meals", saved="2026-11-18 08:00:00 PST"), **{"Vendor": "SHELL OIL", "Category": "Travel"}),
            # No vendor at all.
            _rec("B", "3", "Meals", saved="2026-11-18 09:00:00 PST"),
        ]
        self.assertEqual(er.receipt_vendor(recs[0]), "Napa")
        self.assertEqual(er.receipt_vendor(recs[1]), "Napa")
        self.assertEqual(er.receipt_vendor(recs[2]), "Bruckners")
        self.assertEqual(er.receipt_vendor(recs[3]), "SHELL OIL")
        self.assertEqual(er.receipt_vendor(recs[4]), "")
        rows = er.vendor_totals_rows(er.filter_receipts(recs, date(2026, 11, 15), date(2026, 11, 20)))
        vendors = [r["Vendor"] for r in rows]
        self.assertIn("Napa total", vendors)
        self.assertIn("SHELL OIL total", vendors)
        self.assertIn("(no vendor) total", vendors)
        self.assertNotIn("None total", vendors)
        napa = [r for r in rows if r["Vendor"] == "Napa total"][0]
        self.assertEqual(napa["Total"], 15.0)
        shown = er.filter_receipts(
            recs, date(2026, 11, 15), date(2026, 11, 20), vendor="Napa",
        )
        self.assertEqual(er.grand_total(shown), 15.0)
        none = er.filter_receipts(
            recs, date(2026, 11, 15), date(2026, 11, 20), vendor="(no vendor)",
        )
        self.assertEqual(er.grand_total(none), 3.0)
        rec = er.build_receipt_record(
            "A", {"date": "2026-11-18", "amount": "12", "purpose": "parts", "vendor": "NAPA Auto Parts"},
            "Shop Supplies",
        )
        self.assertEqual(rec["Vendor"], "Napa")
        self.assertEqual(rec["Statement Account"], "Napa")
        other = er.build_receipt_record(
            "A", {"date": "2026-11-18", "amount": "12", "purpose": "fuel",
                  "vendor_choice": "Other", "vendor_other": "SHELL OIL"},
            "Fuel", subcategory="Diesel",
        )
        self.assertEqual(other["Vendor"], "SHELL OIL")
        self.assertEqual(other["Statement Account"], "")
        memoed = er.build_receipt_record(
            "A", {"date": "2026-11-18", "amount": "12", "purpose": "dues", "memo": "annual"},
            "Dues",
        )
        self.assertEqual(memoed["Memo"], "annual")
        self.assertEqual(memoed["Notes"], "annual")
        self.assertEqual(er.receipt_memo({"Memo": "", "Notes": "legacy", "Category": "Dues"}), "legacy")
        self.assertEqual(er.receipt_memo({"Memo": "new", "Notes": "legacy", "Category": "Dues"}), "new")
        self.assertEqual(er.receipt_memo({"Memo": "", "Notes": "comment", "Category": "Other"}), "")

    def test_gallons_parser_ignores_price_per_gallon(self):
        self.assertEqual(er.find_gallons("UNLEADED 18.2 GAL @ 3.359"), 18.2)
        self.assertEqual(er.find_gallons("Gallons purchased: 12.5"), 12.5)
        self.assertIsNone(er.find_gallons("TOTAL $61.12"))



class ReceiptEditTests(unittest.TestCase):
    def _book(self, recs):
        header = list(er.RECEIPTS_COLUMNS)
        rows = [header] + [[r.get(c, "") for c in header] for r in recs]
        return Book({"Receipts": rows})

    def test_update_rewrites_the_same_row_and_keeps_the_photo(self):
        when = datetime(2026, 11, 20, 9, 0, tzinfo=PT)
        existing = er.build_receipt_record(
            "Carl Mulvaney", {"date": date(2026, 11, 18), "amount": "61.12", "purpose": "Fuel"},
            "BNSF", subcategory="Vehicle fuel", ifta_state="WA", ifta_gallons="18.2",
            photo_link="https://drive.google.com/file/d/A/view", photo_file="a.jpg",
            when=when, entry_id="RC-1",
        )
        book = self._book([existing])
        updated = er.build_receipt_record(
            "Carl Mulvaney", {"date": date(2026, 11, 18), "amount": "70.00", "purpose": "Fuel"},
            "BNSF", subcategory="Vehicle fuel", ifta_state="WA", ifta_gallons="20",
            photo_link="", photo_file="", when=datetime(2026, 11, 20, 16, 0, tzinfo=PT), entry_id="RC-1",
        )
        merged = er.prepare_receipt_edit(existing, updated, "Carl Mulvaney", when=datetime(2026, 11, 20, 16, 0, tzinfo=PT))
        self.assertEqual(merged["Saved At"], existing["Saved At"])
        self.assertEqual(merged["Entry ID"], "RC-1")
        self.assertEqual(merged["Photo Link"], "https://drive.google.com/file/d/A/view")
        self.assertEqual(merged["Edited By"], "Carl Mulvaney")
        er.update_receipt_record(merged, book, "Carl Mulvaney", office=False, when=datetime(2026, 11, 20, 16, 0, tzinfo=PT))
        self.assertEqual(book.created, [])
        self.assertEqual(len(book.tabs["Receipts"]), 2)
        saved = dict(zip(book.tabs["Receipts"][0], book.tabs["Receipts"][1]))
        self.assertEqual(saved["Amount"], "70.00")
        self.assertEqual(saved["Saved At"], "2026-11-20 09:00:00 PST")
        self.assertEqual(saved["Entry ID"], "RC-1")
        self.assertEqual(saved["Photo Link"], "https://drive.google.com/file/d/A/view")
        self.assertEqual(saved["Edited By"], "Carl Mulvaney")
        self.assertTrue(saved["Edited At"].startswith("2026-11-20 16:00:00"))
        self.assertEqual(saved["IFTA Gallons"], "20")

    def test_employee_cannot_edit_someone_elses_receipt(self):
        rec = er.build_receipt_record(
            "Gary Grant", {"date": date(2026, 11, 18), "amount": "1", "purpose": "x"},
            "Dues", photo_link="https://drive.google.com/file/d/A/view", when=datetime(2026, 11, 20, 9, 0, tzinfo=PT),
            entry_id="RC-2",
        )
        book = self._book([rec])
        self.assertFalse(er.can_edit_receipt(rec, "Carl Mulvaney", office=False))
        self.assertTrue(er.can_edit_receipt(rec, "Patti", office=True))
        with self.assertRaises(ValueError):
            er.update_receipt_record(rec, book, "Carl Mulvaney", office=False)

    def test_office_edit_appends_edited_columns_to_an_old_header(self):
        header = list(er.RECEIPTS_ORIGINAL_COLUMNS)
        row = [""] * len(header)
        row[header.index("Saved At")] = "2026-11-18 10:00:00 PST"
        row[header.index("Entry ID")] = "RC-3"
        row[header.index("Employee")] = "Gary Grant"
        row[header.index("Date")] = "2026-11-18"
        row[header.index("Amount")] = "25.50"
        row[header.index("Purpose")] = "Filter"
        row[header.index("Job")] = "CVH"
        row[header.index("Expense Type")] = "Parts"
        row[header.index("Photo Link")] = "https://drive.google.com/file/d/SEED2/view"
        book = Book({"Receipts": [header, row]})
        updated = dict(zip(header, row), Amount="30.00", Category="Equipment", Purpose="Filter")
        updated = er.prepare_receipt_edit(dict(zip(header, row)), updated, "Ron Cline", when=datetime(2026, 11, 20, 17, 0, tzinfo=PT))
        er.update_receipt_record(updated, book, "Ron Cline", office=True, when=datetime(2026, 11, 20, 17, 0, tzinfo=PT))
        new_header = book.tabs["Receipts"][0]
        self.assertEqual(new_header[:len(er.RECEIPTS_ORIGINAL_COLUMNS)], list(er.RECEIPTS_ORIGINAL_COLUMNS))
        self.assertIn("Edited At", new_header)
        self.assertIn("Edited By", new_header)
        self.assertEqual(len(book.tabs["Receipts"]), 2)
        saved = dict(zip(new_header, book.tabs["Receipts"][1]))
        self.assertEqual(saved["Amount"], "30.00")
        self.assertEqual(saved["Edited By"], "Ron Cline")
        self.assertEqual(saved["Employee"], "Gary Grant")
        self.assertEqual(saved["Photo Link"], "https://drive.google.com/file/d/SEED2/view")

    def test_legacy_equipment_edit_does_not_require_shares(self):
        existing = _rec("A", "25.50", "Parts", job="CVH")
        existing["Entry ID"] = "RC-4"
        f = {"date": "2026-11-18", "amount": "30.00", "purpose": "Filter"}
        self.assertEqual(er.validate_receipt_allocation(f, "Equipment", existing=existing), [])
        self.assertIn("Choose at least one piece of equipment.", er.validate_receipt_allocation(f, "Equipment"))



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
        office = fn["show_receipts_summary_office"]
        self.assertIn("All dates", office)
        self.assertIn("Show receipts by", office)
        self.assertIn("query_subtotal_sections", office)
        self.assertNotIn("show_receipts_summary_office", fn["show_employee_receipts"])
        self.assertIn("st.camera_input", fn["show_receipt_entry"])
        self.assertIn("st.file_uploader", fn["show_receipt_entry"])
        self.assertIn('st.selectbox(\n        "Category"', fn["show_receipt_entry"])
        self.assertNotIn("Receipt complete", fn["show_receipt_entry"])
        entry = fn["show_receipt_entry"]
        self.assertLess(entry.find("Purpose"), entry.find('"Category"'))
        self.assertLess(entry.find('"Category"'), entry.find("Memo (optional)"))
        self.assertNotIn("Notes (optional)", entry)
        self.assertNotIn("Paid on monthly statement account", entry)
        self.assertIn('st.selectbox(\n        "Vendor"', entry)

    def test_bundled_files(self):
        self.assertIn("pytesseract", (ROOT / "requirements.txt").read_text())
        self.assertIn("tesseract-ocr", (ROOT / "packages.txt").read_text())
        gs = (ROOT / "apps_script" / "receipt_upload" / "Code.gs").read_text()
        self.assertIn("RECEIPTS_FOLDER_ID", gs)
        self.assertNotIn("setTrashed", gs)
        self.assertFalse((ROOT / ".github" / "workflows" / "receipts-summary.yml").exists())


if __name__ == "__main__":
    unittest.main()
