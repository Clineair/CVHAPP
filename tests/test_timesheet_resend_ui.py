"""UI check for the "Send an updated copy to Patti" option.

Runs the real show_timesheet_email_section from app.py with an injected SMTP stub
and an in-memory audit list. No mail is sent and no Sheets are touched.
"""
import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

SCRIPT = str(Path(__file__).resolve().parent / "resend_ui_script.py")


def _run(employee="Ron Cline"):
    os.environ["RESEND_UI_EMPLOYEE"] = employee
    at = AppTest.from_file(SCRIPT)
    at.run()
    return at


class ResendUiTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("RESEND_UI_EMPLOYEE", None)

    def test_first_send_has_no_resend_checkbox(self):
        at = _run()
        self.assertFalse(at.exception)
        self.assertEqual([c.label for c in at.checkbox], [])
        self.assertFalse(at.button[0].disabled)

    def test_resend_flow_checkbox_label_subject_audit_and_double_tap(self):
        at = _run()
        at.button[0].click().run()
        self.assertEqual(at.session_state["logged"], [("Sent", False)])
        at.run()
        # Warning stays and Send stays off until the explicit checkbox is ticked.
        self.assertIn("already sent", at.caption[0].value)
        self.assertTrue(at.button[0].disabled)
        self.assertEqual([c.label for c in at.checkbox], ["Send an updated copy to Patti"])
        at.checkbox[0].check().run()
        self.assertFalse(at.button[0].disabled)
        self.assertTrue(at.button[0].label.startswith("Send updated copy to"))
        self.assertTrue(any("(updated copy)" in m.value for m in at.markdown if "Subject" in m.value))
        at.button[0].click().run()
        self.assertEqual(at.session_state["logged"], [("Sent", False), ("Sent", True)])
        subjects = [x for x in at.session_state["sent"] if isinstance(x, str)]
        self.assertTrue(subjects[-1].endswith("(updated copy)"))
        # An immediate second tap does not send again.
        at.run()
        self.assertTrue(at.button[0].disabled)
        self.assertEqual(len(at.session_state["logged"]), 2)

    def test_anthony_can_send_an_updated_copy_too(self):
        at = _run("Anthony Root")
        self.assertFalse(at.exception)
        at.button[0].click().run()
        at.run()
        self.assertTrue(at.button[0].disabled)
        self.assertEqual([c.label for c in at.checkbox], ["Send an updated copy to Patti"])
        at.checkbox[0].check().run()
        self.assertFalse(at.button[0].disabled)
        at.button[0].click().run()
        self.assertEqual(at.session_state["logged"], [("Sent", False), ("Sent", True)])


if __name__ == "__main__":
    unittest.main()
