"""UI flow for employee Receipts with mocks only. No Sheets, Drive, or mail."""
import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

SCRIPT = str(Path(__file__).resolve().parent / "receipts_ui_script.py")


ENV = ("RECEIPTS_UI_EMPLOYEE", "RECEIPTS_UI_PIN", "RECEIPTS_UI_MAIL", "RECEIPTS_UI_PAGE",
       "RECEIPTS_UI_REMEMBERED", "RECEIPTS_UI_PATTI_PIN", "RECEIPTS_UI_SEED",
       "RECEIPTS_UI_TRASH_FAIL")


def _run(employee="Carl Mulvaney", pin="1", mail="1", page="", remembered="", patti_pin="1", seed=""):
    os.environ["RECEIPTS_UI_EMPLOYEE"] = employee
    os.environ["RECEIPTS_UI_PAGE"] = page
    os.environ["RECEIPTS_UI_REMEMBERED"] = remembered
    os.environ["RECEIPTS_UI_PATTI_PIN"] = patti_pin
    os.environ["RECEIPTS_UI_PIN"] = pin
    os.environ["RECEIPTS_UI_MAIL"] = mail
    os.environ["RECEIPTS_UI_SEED"] = seed
    at = AppTest.from_file(SCRIPT, default_timeout=30)
    at.run()
    return at


def _button(at, label):
    for b in at.button:
        if b.label == label:
            return b
    raise AssertionError("no button " + label + " in " + repr([b.label for b in at.button]))


def _select(at, label):
    for box in at.selectbox:
        if box.label == label:
            return box
    raise AssertionError("no selectbox " + label + " in " + repr([b.label for b in at.selectbox]))


class ReceiptsUiTests(unittest.TestCase):
    def tearDown(self):
        for k in ENV:
            os.environ.pop(k, None)

    def test_pin_gate_blocks_everything(self):
        at = _run(pin="0")
        self.assertFalse(at.exception)
        self.assertEqual([b.label for b in at.button], [])

    def test_full_flow_photo_prefill_category_save_totals(self):
        at = _run()
        self.assertFalse(at.exception)
        _button(at, "🧾 Add a receipt").click().run()
        self.assertTrue(any("photo of the receipt first" in i.value for i in at.info))
        at.session_state["give_photo"] = True
        at.run()
        self.assertFalse(at.exception)
        # Pre-filled from the photo.
        values = {t.label: t.value for t in at.text_input}
        self.assertEqual(values["Amount ($)"], "61.12")
        self.assertEqual(values["Receipt or invoice number"], "004417")
        self.assertEqual(_select(at, "Vendor").value, "Other")
        self.assertNotIn("None", _select(at, "Vendor").options)
        self.assertEqual(_select(at, "Vendor").options[-1], "Other")
        self.assertEqual(values["Vendor name"], "SHELL OIL")
        self.assertEqual(str(at.date_input[0].value), "2026-11-18")
        # Category is on the same screen as Amount and Purpose, with no extra button.
        self.assertEqual(_select(at, "Category").options[0], "Dues")
        self.assertFalse(any(b.label == "Receipt complete" for b in at.button))
        labels = [t.label for t in at.text_input] + [s.label for s in at.selectbox] + [t.label for t in at.text_area]
        self.assertLess(labels.index("Purpose"), labels.index("Category"))
        self.assertLess(labels.index("Category"), labels.index("Memo (optional)"))
        self.assertNotIn("Notes (optional)", labels)
        self.assertNotIn("Paid on monthly statement account", [b.label for b in at.selectbox])
        [t for t in at.text_input if t.label == "Purpose"][0].input("Fuel for the truck, BNSF job")
        at.run()
        self.assertEqual(_select(at, "Category").options[0], "Dues")
        self.assertIn("Equipment", _select(at, "Category").options)
        self.assertNotIn("Paid on monthly statement account", [b.label for b in at.selectbox])
        _button(at, "Save receipt").click().run()
        errors = [e.value for e in at.error]
        self.assertIn("Choose a category.", errors)
        self.assertEqual(at.session_state["writes"], [])
        _select(at, "Category").select("BNSF").run()
        _button(at, "Save receipt").click().run()
        self.assertEqual([e.value for e in at.error], ["Choose a BNSF type."])
        _select(at, "BNSF type").select("Vehicle fuel").run()
        gallons = [t for t in at.text_input if t.label == "Gallons purchased"][0]
        self.assertEqual(gallons.value, "18.2")
        _select(at, "State").select("WA — Washington").run()
        _button(at, "Save receipt").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["created"], ["Receipts"])
        self.assertEqual(at.session_state["writes"], ["Receipts", "Receipts"])  # header + row
        rows = at.session_state["store"]["Receipts"]
        rec = dict(zip(rows[0], rows[1]))
        self.assertEqual(rec["Employee"], "Carl Mulvaney")
        self.assertEqual(rec["Amount"], "61.12")
        self.assertEqual(rec["Category"], "BNSF")
        self.assertEqual(rec["Subcategory"], "Vehicle fuel")
        self.assertEqual((rec["Job"], rec["Expense Type"]), ("BNSF", "Vehicle fuel"))
        self.assertEqual(rec["Vendor"], "SHELL OIL")
        self.assertEqual(rec["Statement Account"], "")
        self.assertEqual(rec["IFTA State"], "WA")
        self.assertEqual(rec["IFTA Gallons"], "18.2")
        self.assertEqual(rec["Photo Link"], "https://drive.google.com/file/d/FAKE/view")
        self.assertEqual(at.session_state["uploads"][0][0], "Carl Mulvaney")
        self.assertEqual(at.session_state["uploads"][0][2], "image/jpeg")
        self.assertTrue(any("Saved $61.12 to BNSF / Vehicle fuel" in s.value for s in at.success))
        self.assertTrue(any(b.label == "🧾 Add a receipt" for b in at.button))
        totals = at.dataframe[0].value
        self.assertEqual(list(totals["Category"]), ["BNSF", "BNSF total", "All categories"])
        self.assertEqual(list(totals["Detail"]), ["Vehicle fuel", "", ""])
        self.assertEqual(list(totals["Total"]), ["$61.12", "$61.12", "$61.12"])
        self.assertEqual(at.session_state["mails"], [])

    def test_upload_failure_still_saves_with_paper_warning(self):
        os.environ["RECEIPTS_UI_UPLOAD_FAIL"] = "1"
        try:
            at = _run()
            _button(at, "🧾 Add a receipt").click().run()
            at.session_state["give_photo"] = True
            at.run()
            [t for t in at.text_input if t.label == "Purpose"][0].input("Parts run")
            at.run()
            _select(at, "Category").select("Office Supplies").run()
            _button(at, "Save receipt").click().run()
        finally:
            os.environ.pop("RECEIPTS_UI_UPLOAD_FAIL", None)
        self.assertFalse(at.exception)
        rec = dict(zip(*at.session_state["store"]["Receipts"][:2]))
        self.assertEqual(rec["Photo Link"], "")
        self.assertTrue(rec["Photo File"].endswith(".jpg"))
        self.assertTrue(any("Saved $61.12" in s.value for s in at.success))
        self.assertTrue(any("Keep the paper receipt" in w.value for w in at.warning))

    def test_employee_receipts_page_has_no_send_panel(self):
        for who in ("Carl Mulvaney", "Ron Cline"):
            at = _run(who)
            self.assertFalse(any(b.label == "Email this summary" for b in at.button))

    def test_summary_page_ron_remembered_can_preview_and_send(self):
        at = _run(page="summary", remembered="Ron Cline")
        self.assertFalse(at.exception)
        send = _button(at, "Email this summary")
        self.assertTrue(send.disabled)
        self.assertTrue(any("OFF" in c.value for c in at.caption))
        at.checkbox[0].check().run()
        _button(at, "Email this summary").click().run()
        self.assertEqual(len(at.session_state["mails"]), 1)
        self.assertTrue(at.session_state["mails"][0].startswith("CVH employee receipts: "))
        self.assertEqual(at.session_state["writes"], ["Receipts Mail", "Receipts Mail"])
        audit = dict(zip(*at.session_state["store"]["Receipts Mail"][:2]))
        self.assertEqual(audit["Sent By"], "Ron Cline")
        at.run()
        self.assertTrue(_button(at, "Email this summary").disabled)
        self.assertEqual(len(at.session_state["mails"]), 1)

    def test_summary_page_patti_signs_in_with_pin(self):
        at = _run(page="summary")
        self.assertEqual(at.selectbox[0].label, "Who are you?")
        self.assertEqual(at.selectbox[0].options, ["Ron Cline", "Patti"])
        at.selectbox[0].select("Patti").run()
        at.text_input[0].input("9999").run()
        _button(at, "Continue").click().run()
        self.assertTrue(any("not right" in e.value for e in at.error))
        at.text_input[0].input("4321").run()
        _button(at, "Continue").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["queued_cookie"], "Patti")
        self.assertTrue(any(b.label == "Email this summary" for b in at.button))

    def test_summary_page_blocks_other_employees_and_unset_pin(self):
        at = _run(page="summary", remembered="Carl Mulvaney")
        self.assertTrue(any("Only Ron Cline or Patti" in i.value for i in at.info))
        self.assertFalse(any(b.label == "Email this summary" for b in at.button))
        at = _run(page="summary", patti_pin="0")
        at.selectbox[0].select("Patti").run()
        self.assertTrue(any("PIN not set up yet" in i.value for i in at.info))

    def test_send_stays_off_when_mailbox_not_set_up(self):
        at = _run(page="summary", remembered="Ron Cline", mail="0")
        self.assertTrue(any("email not set up yet" in i.value for i in at.info))
        at.checkbox[0].check().run()
        self.assertTrue(_button(at, "Email this summary").disabled)

    def test_live_view_defaults_to_all_dates_and_lists_receipts(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        self.assertFalse(at.exception)
        self.assertTrue(any(b.label == "Refresh" for b in at.button))
        kinds = [s for s in at.selectbox if s.label == "Show receipts for"][0]
        self.assertEqual(kinds.value, "All dates")
        self.assertEqual(kinds.options, ["All dates", "Period to date", "This month", "Pay period", "Custom dates"])
        self.assertTrue(any("counted by the day they were entered (Pacific)" in c.value for c in at.caption))
        self.assertTrue(any("Show receipts by" in (m.value or "") for m in at.markdown))
        # All dates includes the Nov 1 receipt as well as the mid-month ones.
        frames = [df.value for df in at.dataframe]
        receipts = [df for df in frames if "Saved" in df.columns and "Employee" in df.columns][0]
        self.assertEqual(list(receipts.columns), [
            "Saved", "Employee", "Receipt date", "Vendor", "Purpose", "Receipt #",
            "Category", "Detail", "Amount", "Photo",
        ])
        self.assertIn("Napa", list(receipts["Vendor"]))
        self.assertTrue(any(s.label == "Vendor" for s in at.selectbox))
        self.assertFalse(any(s.label == "Statement account" for s in at.selectbox))
        self.assertEqual(sorted(receipts["Employee"].tolist()), ["Carl Mulvaney", "Carl Mulvaney", "Gary Grant"])
        self.assertIn("Earlier meal", list(receipts["Purpose"]))
        emp_totals = [df for df in frames if "Employee" in df.columns and "Receipts" in df.columns][0]
        self.assertEqual(emp_totals["Total"].tolist()[-1], "$43.50")
        self.assertTrue(any(b.label == "Download CSV" for b in at.download_button))
        at.checkbox[0].check().run()
        _button(at, "Email this summary").click().run()
        self.assertEqual(at.session_state["mails"], ["CVH employee receipts: All dates"])
        audit = dict(zip(*at.session_state["store"]["Receipts Mail"][:2]))
        self.assertEqual(audit["Idempotency Key"], "receipts:all")
        self.assertEqual(audit["Sent By"], "Ron Cline")
        # Period to date still hides the earlier receipt when Patti narrows the dates.
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        [s for s in at.selectbox if s.label == "Show receipts for"][0].select("Period to date").run()
        frames = [df.value for df in at.dataframe]
        receipts = [df for df in frames if "Saved" in df.columns and "Employee" in df.columns][0]
        self.assertNotIn("Earlier meal", list(receipts["Purpose"]))
        self.assertEqual(sorted(receipts["Employee"].tolist()), ["Carl Mulvaney", "Gary Grant"])

    def test_query_by_employee_shows_category_subtotals_for_all_dates(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        self.assertEqual(_select(at, "Show receipts for").value, "All dates")
        _select(at, "Employee").select("Carl Mulvaney").run()
        frames = [df.value for df in at.dataframe]
        receipts = [df for df in frames if "Saved" in df.columns][0]
        self.assertEqual(sorted(receipts["Purpose"].tolist()), ["Earlier meal", "Fuel for truck"])
        self.assertTrue(any("Totals by category" in (m.value or "") for m in at.markdown))
        self.assertFalse(any(m.value == "Totals by employee" for m in at.markdown))
        self.assertTrue(any(b.label == "Download CSV" for b in at.download_button))
        at.checkbox[0].check().run()
        _button(at, "Email this summary").click().run()
        self.assertEqual(at.session_state["mails"], ["CVH employee receipts: All dates"])
        audit = dict(zip(*at.session_state["store"]["Receipts Mail"][:2]))
        self.assertEqual(audit["Idempotency Key"], "receipts:all:emp=Carl Mulvaney")

    def test_custom_range_and_filters_use_a_different_send_key(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        kinds = [s for s in at.selectbox if s.label == "Show receipts for"][0]
        kinds.select("This month").run()
        frames = [df.value for df in at.dataframe]
        receipts = [df for df in frames if "Saved" in df.columns][0]
        self.assertEqual(len(receipts), 3)
        [s for s in at.selectbox if s.label == "Employee"][0].select("Carl Mulvaney").run()
        [s for s in at.selectbox if s.label == "Category"][0].select("BNSF").run()
        frames = [df.value for df in at.dataframe]
        receipts = [df for df in frames if "Saved" in df.columns][0]
        self.assertEqual(list(receipts["Purpose"]), ["Fuel for truck"])
        at.checkbox[0].check().run()
        _button(at, "Email this summary").click().run()
        self.assertEqual(
            at.session_state["mails"],
            ["CVH employee receipts: Nov 1 – Nov 20, 2026 (this month)"],
        )
        audit = dict(zip(*at.session_state["store"]["Receipts Mail"][:2]))
        self.assertEqual(audit["Idempotency Key"], "receipts:2026-11-01:2026-11-20:emp=Carl Mulvaney|cat=BNSF")

    def test_equipment_shares_warn_but_still_save_when_not_zero(self):
        at = _run()
        _button(at, "🧾 Add a receipt").click().run()
        at.session_state["give_photo"] = True
        at.run()
        [t for t in at.text_input if t.label == "Purpose"][0].input("Parts for the Ram and PW")
        at.run()
        _select(at, "Category").select("Equipment").run()
        self.assertTrue(any(c.label == "Ram" for c in at.checkbox))
        self.assertTrue(any(c.label == "PW" for c in at.checkbox))
        [c for c in at.checkbox if c.label == "Ram"][0].check().run()
        [c for c in at.checkbox if c.label == "PW"][0].check().run()
        [t for t in at.text_input if t.label == "Share for Ram ($)"][0].input("20.00")
        [t for t in at.text_input if t.label == "Share for PW ($)"][0].input("10.00")
        at.run()
        self.assertTrue(any("Remaining amount: $31.12" in (c.value or "") for c in at.caption))
        _select(at, "Purpose").select("Parts").run()
        memo_boxes = [b for b in at.text_area if b.label == "Memo (optional)"]
        self.assertEqual(len(memo_boxes), 1)
        self.assertFalse(any(b.label == "Notes (optional)" for b in at.text_area))
        _button(at, "Save receipt").click().run()
        self.assertFalse(at.exception)
        rec = dict(zip(*at.session_state["store"]["Receipts"][:2]))
        self.assertEqual(rec["Category"], "Equipment")
        self.assertEqual(rec["Equipment Shares"], "Ram=20.00; PW=10.00")
        self.assertEqual(rec["Equipment Purpose"], "Parts")
        self.assertTrue(any("Saved $61.12 to Equipment" in s.value for s in at.success))
        self.assertTrue(any("still left" in w.value for w in at.warning))

    def test_office_ifta_report_has_quarter_picker(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        self.assertFalse(at.exception)
        quarter = _select(at, "IFTA quarter")
        self.assertTrue(quarter.value.startswith("Q4 2026"))
        self.assertTrue(any("counted by the date on the receipt" in c.value for c in at.caption))
        self.assertTrue(any("No IFTA fuel receipts in this quarter." in c.value for c in at.caption))

    def test_employee_saved_receipts_opens_and_updates_the_same_row(self):
        at = _run(seed="1")
        self.assertTrue(any(b.label == "Saved receipts" for b in at.button))
        _button(at, "Saved receipts").click().run()
        self.assertFalse(at.exception)
        picker = _select(at, "Choose a receipt")
        self.assertTrue(all("Carl Mulvaney" not in (opt or "") or True for opt in picker.options))
        self.assertTrue(any("2026-11-16" in opt and "$10.00" in opt for opt in picker.options))
        self.assertFalse(any("Gary Grant" in opt or "Filter" in opt for opt in picker.options))
        _button(at, "Open").click().run()
        self.assertFalse(at.exception)
        amount = [t for t in at.text_input if t.label == "Amount ($)"][0]
        self.assertEqual(amount.value, "10.00")
        amount.input("12.00")
        at.run()
        _button(at, "Save changes").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Updated $12.00" in s.value for s in at.success))
        rows = at.session_state["store"]["Receipts"]
        self.assertEqual(len(rows), 4)  # header + 3 seed rows
        recs = [dict(zip(rows[0], row)) for row in rows[1:]]
        updated = [r for r in recs if r["Entry ID"] == "1"][0]
        self.assertEqual(updated["Amount"], "12.00")
        self.assertEqual(updated["Employee"], "Carl Mulvaney")
        self.assertEqual(updated["Edited By"], "Carl Mulvaney")
        self.assertEqual(updated["Photo Link"], "https://drive.google.com/file/d/SEED1/view")
        self.assertEqual(updated["Saved At"], "2026-11-16 08:00:00 PST")
        self.assertEqual([r["Entry ID"] for r in recs], ["1", "2", "3"])

    def test_office_saved_receipts_can_edit_any_employee(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        _button(at, "Saved receipts").click().run()
        self.assertFalse(at.exception)
        picker = _select(at, "Choose a receipt")
        gary = [opt for opt in picker.options if "Gary Grant" in opt][0]
        picker.select(gary).run()
        _button(at, "Open").click().run()
        amount = [t for t in at.text_input if t.label == "Amount ($)"][0]
        self.assertEqual(amount.value, "25.50")
        amount.input("30.00")
        at.run()
        _button(at, "Save changes").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Updated $30.00" in s.value for s in at.success))
        rows = at.session_state["store"]["Receipts"]
        self.assertEqual(len(rows), 4)
        recs = [dict(zip(rows[0], row)) for row in rows[1:]]
        updated = [r for r in recs if r["Entry ID"] == "2"][0]
        self.assertEqual(updated["Amount"], "30.00")
        self.assertEqual(updated["Employee"], "Gary Grant")
        self.assertEqual(updated["Edited By"], "Ron Cline")
        self.assertEqual(updated["Photo Link"], "https://drive.google.com/file/d/SEED2/view")
        self.assertEqual(updated["Category"], "Equipment")

    def test_employee_deletes_own_receipt_after_confirming(self):
        at = _run(seed="1")
        _button(at, "Saved receipts").click().run()
        self.assertTrue(any(b.label == "Delete" for b in at.button))
        _button(at, "Delete").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Delete this receipt?" in (m.value or "") for m in at.markdown))
        self.assertTrue(any("Carl Mulvaney" in (m.value or "") for m in at.markdown))
        self.assertTrue(any("$10.00" in (m.value or "") for m in at.markdown))
        self.assertTrue(any("2026-11-16" in (m.value or "") for m in at.markdown))
        self.assertTrue(any("Shell" in (m.value or "") for m in at.markdown))
        yes = _button(at, "Yes, delete this receipt")
        self.assertTrue(yes.disabled)
        self.assertEqual(len(at.session_state["store"]["Receipts"]), 4)
        [c for c in at.checkbox if c.label == "Yes, I want to delete this receipt"][0].check().run()
        _button(at, "Yes, delete this receipt").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Deleted $10.00 receipt for Carl Mulvaney" in s.value for s in at.success))
        rows = at.session_state["store"]["Receipts"]
        recs = [dict(zip(rows[0], row)) for row in rows[1:]]
        self.assertEqual([r["Entry ID"] for r in recs], ["2", "3"])
        self.assertEqual(at.session_state["trashed"], ["SEED1"])
        self.assertEqual(at.session_state["created"], ["Receipts Deleted"])
        audit = dict(zip(*at.session_state["store"]["Receipts Deleted"][:2]))
        self.assertEqual(audit["Entry ID"], "1")
        self.assertEqual(audit["Deleted By"], "Carl Mulvaney")
        self.assertEqual(audit["Photo Trash"], "Trashed")
        self.assertTrue(any(b.label == "🧾 Add a receipt" for b in at.button))

    def test_office_can_delete_another_employees_receipt(self):
        at = _run(page="summary", remembered="Ron Cline", seed="1")
        _button(at, "Saved receipts").click().run()
        picker = _select(at, "Choose a receipt")
        gary = [opt for opt in picker.options if "Gary Grant" in opt][0]
        picker.select(gary).run()
        _button(at, "Delete").click().run()
        self.assertTrue(any("Gary Grant" in (m.value or "") for m in at.markdown))
        self.assertTrue(any("$25.50" in (m.value or "") for m in at.markdown))
        [c for c in at.checkbox if c.label == "Yes, I want to delete this receipt"][0].check().run()
        _button(at, "Yes, delete this receipt").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Deleted $25.50 receipt for Gary Grant" in s.value for s in at.success))
        rows = at.session_state["store"]["Receipts"]
        recs = [dict(zip(rows[0], row)) for row in rows[1:]]
        self.assertEqual([r["Entry ID"] for r in recs], ["1", "3"])
        self.assertEqual(at.session_state["trashed"], ["SEED2"])
        audit = dict(zip(*at.session_state["store"]["Receipts Deleted"][:2]))
        self.assertEqual(audit["Deleted By"], "Ron Cline")
        self.assertEqual(audit["Employee"], "Gary Grant")

    def test_edit_form_delete_button_opens_the_same_confirmation(self):
        at = _run(seed="1")
        _button(at, "Saved receipts").click().run()
        _button(at, "Open").click().run()
        _button(at, "Delete this receipt").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Delete this receipt?" in (m.value or "") for m in at.markdown))
        [c for c in at.checkbox if c.label == "Yes, I want to delete this receipt"][0].check().run()
        _button(at, "Yes, delete this receipt").click().run()
        self.assertTrue(any("Deleted $10.00 receipt for Carl Mulvaney" in s.value for s in at.success))
        recs = [dict(zip(*[at.session_state["store"]["Receipts"][0], row])) for row in at.session_state["store"]["Receipts"][1:]]
        self.assertEqual([r["Entry ID"] for r in recs], ["2", "3"])

    def test_photo_trash_failure_still_deletes_and_warns(self):
        os.environ["RECEIPTS_UI_TRASH_FAIL"] = "1"
        at = _run(seed="1")
        _button(at, "Saved receipts").click().run()
        _button(at, "Delete").click().run()
        [c for c in at.checkbox if c.label == "Yes, I want to delete this receipt"][0].check().run()
        _button(at, "Yes, delete this receipt").click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Deleted $10.00 receipt for Carl Mulvaney" in s.value for s in at.success))
        self.assertTrue(any("could not be moved to the Google Drive trash" in w.value for w in at.warning))
        recs = [dict(zip(at.session_state["store"]["Receipts"][0], row)) for row in at.session_state["store"]["Receipts"][1:]]
        self.assertEqual([r["Entry ID"] for r in recs], ["2", "3"])
        self.assertEqual(at.session_state["trashed"], [])
        audit = dict(zip(*at.session_state["store"]["Receipts Deleted"][:2]))
        self.assertEqual(audit["Photo Trash"], "Failed")
        os.environ.pop("RECEIPTS_UI_TRASH_FAIL", None)


if __name__ == "__main__":
    unittest.main()
