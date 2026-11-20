"""UI flow for employee Receipts with mocks only. No Sheets, Drive, or mail."""
import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

SCRIPT = str(Path(__file__).resolve().parent / "receipts_ui_script.py")


def _run(employee="Carl Mulvaney", pin="1", mail="1"):
    os.environ["RECEIPTS_UI_EMPLOYEE"] = employee
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
        for k in ("RECEIPTS_UI_EMPLOYEE", "RECEIPTS_UI_PIN", "RECEIPTS_UI_MAIL"):
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
        # No category menu until the receipt is complete; purpose is required.
        self.assertEqual(len(at.selectbox), 0)
        _button(at, "Receipt complete").click().run()
        self.assertTrue(any("purpose" in e.value.lower() for e in at.error))
        self.assertEqual(len(at.selectbox), 0)
        [t for t in at.text_input if t.label == "Purpose"][0].input("Fuel for Heli hauler, BNSF job")
        [t for t in at.text_input if t.label == "Amount ($)"][0].input("61.12")
        at.run()
        _button(at, "Receipt complete").click().run()
        self.assertEqual(len(at.selectbox), 1)
        self.assertEqual(at.selectbox[0].label, "Allocate to category")
        self.assertIn("Fuel", at.selectbox[0].options)
        _button(at, "Save receipt").click().run()
        self.assertTrue(any("Choose a category" in e.value for e in at.error))
        self.assertEqual(at.session_state["writes"], [])
        at.selectbox[0].select("Fuel").run()
        _button(at, "Save receipt").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state["created"], ["Receipts"])
        self.assertEqual(at.session_state["writes"], ["Receipts", "Receipts"])  # header + row
        rows = at.session_state["store"]["Receipts"]
        header, row = rows[0], rows[1]
        rec = dict(zip(header, row))
        self.assertEqual(rec["Employee"], "Carl Mulvaney")
        self.assertEqual(rec["Amount"], "61.12")
        self.assertEqual(rec["Category"], "Fuel")
        self.assertEqual(rec["Photo Link"], "https://drive.google.com/file/d/FAKE/view")
        self.assertEqual(at.session_state["uploads"][0][0], "Carl Mulvaney")
        self.assertEqual(at.session_state["uploads"][0][2], "image/jpeg")
        self.assertTrue(any("Saved $61.12 to Fuel" in s.value for s in at.success))
        # Back to the start: list and category totals show the new receipt.
        self.assertTrue(any(b.label == "🧾 Add a receipt" for b in at.button))
        frames = [d.value for d in at.dataframe]
        self.assertEqual(list(frames[0]["Category"]), ["Fuel", "All categories"])
        self.assertEqual(list(frames[0]["Total"]), ["$61.12", "$61.12"])
        self.assertEqual(at.session_state["mails"], [])

    def test_office_panel_only_for_ron_and_send_needs_confirm(self):
        at = _run("Carl Mulvaney")
        self.assertFalse(any(e.label == "Receipts summary email to Patti" for e in at.expander))
        at = _run("Ron Cline")
        self.assertFalse(at.exception)
        self.assertTrue(any(e.label == "Receipts summary email to Patti" for e in at.expander))
        send = _button(at, "Send receipts summary")
        self.assertTrue(send.disabled)
        self.assertTrue(any("OFF" in c.value for c in at.caption))
        at.checkbox[0].check().run()
        send = _button(at, "Send receipts summary")
        self.assertFalse(send.disabled)
        send.click().run()
        self.assertEqual(len(at.session_state["mails"]), 1)
        self.assertTrue(at.session_state["mails"][0].startswith("CVH employee receipts: "))
        self.assertEqual(at.session_state["writes"], ["Receipts Mail", "Receipts Mail"])
        at.run()
        self.assertTrue(_button(at, "Send receipts summary").disabled)
        self.assertEqual(len(at.session_state["mails"]), 1)

    def test_send_stays_off_when_mailbox_not_set_up(self):
        at = _run("Ron Cline", mail="0")
        self.assertTrue(any("email not set up yet" in i.value for i in at.info))
        at.checkbox[0].check().run()
        self.assertTrue(_button(at, "Send receipts summary").disabled)


if __name__ == "__main__":
    unittest.main()
