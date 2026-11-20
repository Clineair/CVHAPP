"""UI flow for employee Receipts with mocks only. No Sheets, Drive, or mail."""
import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

SCRIPT = str(Path(__file__).resolve().parent / "receipts_ui_script.py")


ENV = ("RECEIPTS_UI_EMPLOYEE", "RECEIPTS_UI_PIN", "RECEIPTS_UI_MAIL", "RECEIPTS_UI_PAGE",
       "RECEIPTS_UI_REMEMBERED", "RECEIPTS_UI_PATTI_PIN")


def _run(employee="Carl Mulvaney", pin="1", mail="1", page="", remembered="", patti_pin="1"):
    os.environ["RECEIPTS_UI_EMPLOYEE"] = employee
    os.environ["RECEIPTS_UI_PAGE"] = page
    os.environ["RECEIPTS_UI_REMEMBERED"] = remembered
    os.environ["RECEIPTS_UI_PATTI_PIN"] = patti_pin
    os.environ["RECEIPTS_UI_PIN"] = pin
    os.environ["RECEIPTS_UI_MAIL"] = mail
    at = AppTest.from_file(SCRIPT, default_timeout=30)
    at.run()
    return at


def _button(at, label):
    for b in at.button:
        if b.label == label:
            return b
    raise AssertionError("no button " + label + " in " + repr([b.label for b in at.button]))


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
        self.assertEqual(values["Vendor (optional)"], "SHELL OIL")
        self.assertEqual(str(at.date_input[0].value), "2026-11-18")
        # No Job / Expense type menus until the receipt is complete; purpose is required.
        self.assertEqual(len(at.selectbox), 0)
        _button(at, "Receipt complete").click().run()
        self.assertTrue(any("purpose" in e.value.lower() for e in at.error))
        self.assertEqual(len(at.selectbox), 0)
        [t for t in at.text_input if t.label == "Purpose"][0].input("Fuel for Heli hauler, BNSF job")
        at.run()
        _button(at, "Receipt complete").click().run()
        self.assertEqual([b.label for b in at.selectbox], ["Job", "Expense type"])
        self.assertEqual(at.selectbox[0].options, ["CVH", "BNSF", "Forestry", "Other"])
        self.assertEqual(at.selectbox[1].options, ["Fuel", "Parts", "Meals", "Lodging", "Supplies", "Other"])
        _button(at, "Save receipt").click().run()
        errors = [e.value for e in at.error]
        self.assertIn("Choose a job.", errors)
        self.assertIn("Choose an expense type.", errors)
        self.assertEqual(at.session_state["writes"], [])
        at.selectbox[0].select("BNSF").run()
        _button(at, "Save receipt").click().run()
        self.assertEqual([e.value for e in at.error], ["Choose an expense type."])
        at.selectbox[1].select("Fuel").run()
        _button(at, "Save receipt").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["created"], ["Receipts"])
        self.assertEqual(at.session_state["writes"], ["Receipts", "Receipts"])  # header + row
        rows = at.session_state["store"]["Receipts"]
        rec = dict(zip(rows[0], rows[1]))
        self.assertEqual(rec["Employee"], "Carl Mulvaney")
        self.assertEqual(rec["Amount"], "61.12")
        self.assertEqual((rec["Job"], rec["Expense Type"]), ("BNSF", "Fuel"))
        self.assertEqual(rec["Photo Link"], "https://drive.google.com/file/d/FAKE/view")
        self.assertEqual(at.session_state["uploads"][0][0], "Carl Mulvaney")
        self.assertEqual(at.session_state["uploads"][0][2], "image/jpeg")
        self.assertTrue(any("Saved $61.12 to BNSF / Fuel" in s.value for s in at.success))
        self.assertTrue(any(b.label == "🧾 Add a receipt" for b in at.button))
        totals = at.dataframe[0].value
        self.assertEqual(list(totals["Job"]), ["BNSF", "BNSF total", "All jobs"])
        self.assertEqual(list(totals["Expense type"]), ["Fuel", "", ""])
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
            _button(at, "Receipt complete").click().run()
            at.selectbox[0].select("CVH").run()
            at.selectbox[1].select("Parts").run()
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
            self.assertFalse(any(b.label == "Send receipts summary" for b in at.button))

    def test_summary_page_ron_remembered_can_preview_and_send(self):
        at = _run(page="summary", remembered="Ron Cline")
        self.assertFalse(at.exception)
        send = _button(at, "Send receipts summary")
        self.assertTrue(send.disabled)
        self.assertTrue(any("OFF" in c.value for c in at.caption))
        at.checkbox[0].check().run()
        _button(at, "Send receipts summary").click().run()
        self.assertEqual(len(at.session_state["mails"]), 1)
        self.assertTrue(at.session_state["mails"][0].startswith("CVH employee receipts: "))
        self.assertEqual(at.session_state["writes"], ["Receipts Mail", "Receipts Mail"])
        audit = dict(zip(*at.session_state["store"]["Receipts Mail"][:2]))
        self.assertEqual(audit["Sent By"], "Ron Cline")
        at.run()
        self.assertTrue(_button(at, "Send receipts summary").disabled)
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
        self.assertTrue(any(b.label == "Send receipts summary" for b in at.button))

    def test_summary_page_blocks_other_employees_and_unset_pin(self):
        at = _run(page="summary", remembered="Carl Mulvaney")
        self.assertTrue(any("Only Ron Cline or Patti" in i.value for i in at.info))
        self.assertFalse(any(b.label == "Send receipts summary" for b in at.button))
        at = _run(page="summary", patti_pin="0")
        at.selectbox[0].select("Patti").run()
        self.assertTrue(any("PIN not set up yet" in i.value for i in at.info))

    def test_send_stays_off_when_mailbox_not_set_up(self):
        at = _run(page="summary", remembered="Ron Cline", mail="0")
        self.assertTrue(any("email not set up yet" in i.value for i in at.info))
        at.checkbox[0].check().run()
        self.assertTrue(_button(at, "Send receipts summary").disabled)


if __name__ == "__main__":
    unittest.main()
