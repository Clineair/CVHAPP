"""PIN hashes, device cookie, and lockout. No mail, Sheets, or live secrets."""
import time
import unittest

import timesheet_mail as tm
import timesheet_pin as pin


SECRET = "test-cookie-secret-0123456789"
NOW = 1_700_000_000


def _secrets(extra=None):
    data = {
        "timesheet_pin": {"cookie_secret": SECRET},
        "timesheet_pins": {
            "Carl Mulvaney": pin.make_pin_hash("2468"),
            "Anthony Root": pin.make_pin_hash("1357"),
            "Gary Grant": pin.make_pin_hash("8080"),
        },
    }
    if extra:
        data.update(extra)
    return data


class TimesheetPinTests(unittest.TestCase):
    def test_roster_matches_mail_callback_and_includes_ron(self):
        self.assertEqual(pin.PIN_EMPLOYEES, tm.TIMESHEET_PIN_EMPLOYEES)
        self.assertIn("Ron Cline", pin.PIN_EMPLOYEES)
        self.assertIn("Anthony Root", pin.PIN_EMPLOYEES)
        self.assertTrue(tm.timesheet_pin_employee_ok("Skylar Fingerle"))
        self.assertTrue(tm.timesheet_pin_employee_ok("Ron Cline"))
        self.assertEqual(pin.PIN_EMPLOYEES[0], "Ron Cline")

    def test_hash_is_salted_and_does_not_contain_the_pin(self):
        first = pin.make_pin_hash("2468")
        second = pin.make_pin_hash("2468")
        self.assertNotEqual(first, second)
        self.assertNotIn("2468", first)
        self.assertTrue(first.startswith("scrypt$16384$8$1$"))
        self.assertTrue(pin.verify_pin_hash("2468", first))
        self.assertFalse(pin.verify_pin_hash("2469", first))
        self.assertTrue(pin.verify_pin_hash(" 2468 ", first))
        self.assertFalse(pin.verify_pin_hash("24 68", first))
        self.assertFalse(pin.verify_employee_pin("Gary Grant", "2468", _secrets()))
        self.assertTrue(pin.verify_employee_pin("Carl Mulvaney", "2468", _secrets()))

    def test_missing_or_bad_setup_is_not_ready(self):
        self.assertFalse(pin.employee_pin_ready({}, "Carl Mulvaney"))
        self.assertFalse(pin.employee_pin_ready({"timesheet_pins": {}}, "Carl Mulvaney"))
        short = {"timesheet_pin": {"cookie_secret": "too-short"}, "timesheet_pins": _secrets()["timesheet_pins"]}
        self.assertFalse(pin.employee_pin_ready(short, "Carl Mulvaney"))
        self.assertEqual(pin.cookie_secret(short), "")
        self.assertFalse(pin.employee_pin_ready(_secrets(), "Ron Cline"))
        self.assertFalse(pin.employee_pin_ready(_secrets(), "Barry Markham"))
        self.assertEqual(pin.attempt_pin("Barry Markham", "2468", _secrets(), 0), ("not_configured", 0))

    def test_lockout_is_per_attempt_count_and_stops_checking(self):
        secrets = _secrets()
        status, failures = pin.attempt_pin("Carl Mulvaney", "", secrets, 0)
        self.assertEqual((status, failures), ("empty", 0))
        failures = 0
        for _ in range(pin.MAX_ATTEMPTS - 1):
            status, failures = pin.attempt_pin("Carl Mulvaney", "9999", secrets, failures)
            self.assertEqual(status, "denied")
        status, failures = pin.attempt_pin("Carl Mulvaney", "9999", secrets, failures)
        self.assertEqual((status, failures), ("locked", pin.MAX_ATTEMPTS))
        status, failures = pin.attempt_pin("Carl Mulvaney", "2468", secrets, failures)
        self.assertEqual(status, "locked")
        self.assertEqual(pin.attempt_pin("Carl Mulvaney", "2468", secrets, pin.MAX_ATTEMPTS - 1), ("ok", 0))

    def test_device_cookie_lasts_over_five_years_and_rejects_tampering(self):
        token = pin.sign_device_cookie("Carl Mulvaney", SECRET, now=NOW)
        claims = pin.device_cookie_claims(token, SECRET, now=NOW + 1)
        self.assertEqual(claims["employee"], "Carl Mulvaney")
        self.assertGreaterEqual(claims["exp"] - claims["iat"], 5 * 365 * 24 * 60 * 60)
        self.assertEqual(pin.verify_device_cookie(token, SECRET, now=NOW + pin.COOKIE_TTL_SEC - 10), "Carl Mulvaney")
        self.assertIsNone(pin.verify_device_cookie(token, SECRET, now=NOW + pin.COOKIE_TTL_SEC + 5))
        self.assertIsNone(pin.verify_device_cookie(token + "ab", SECRET, now=NOW + 1))
        self.assertIsNone(pin.verify_device_cookie(token, "another-long-secret-value", now=NOW + 1))
        self.assertIsNone(pin.verify_device_cookie('"' + token + '"', "nope-but-long-enough", now=NOW + 1))
        quoted = pin.verify_device_cookie('"' + token + '"', SECRET, now=NOW + 1)
        self.assertEqual(quoted, "Carl Mulvaney")
        self.assertEqual(
            pin.verify_device_cookie(pin.sign_device_cookie("Ron Cline", SECRET, now=NOW), SECRET, now=NOW + 1),
            "Ron Cline",
        )
        with self.assertRaises(ValueError):
            pin.sign_device_cookie("Unknown Person", SECRET, now=NOW)
        with self.assertRaises(ValueError):
            pin.sign_device_cookie("Carl Mulvaney", "short", now=NOW)

    def test_cli_prints_a_hash_line_and_refuses_unknown_names(self):
        import importlib.util
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "tools" / "make_pin_hash.py"
        spec = importlib.util.spec_from_file_location("make_pin_hash", script)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = tool.main(["--employee", "Skylar Fingerle", "--pin", "4242"])
        self.assertEqual(code, 0)
        line = stdout.getvalue().strip()
        self.assertTrue(line.startswith('"Skylar Fingerle" = "scrypt$'))
        self.assertNotIn("4242", line)
        self.assertIn("shell history", stderr.getvalue())
        self.assertEqual(tool.main(["--employee", "Unknown Person", "--pin", "4242"]), 2)
        stdout_ron = io.StringIO()
        stderr_ron = io.StringIO()
        with redirect_stdout(stdout_ron), redirect_stderr(stderr_ron):
            self.assertEqual(tool.main(["--employee", "Ron Cline", "--pin", "4242"]), 0)
        ron_line = stdout_ron.getvalue().strip()
        self.assertTrue(ron_line.startswith('"Ron Cline" = "scrypt$'))
        self.assertNotIn("4242", ron_line)
        self.assertEqual(tool.main(["--pin", "12"]), 2)


class TimesheetPinMailIdentityTests(unittest.TestCase):
    def test_send_payload_uses_employee_key_without_google_email(self):
        import json
        secrets = {
            "timesheet_mail": {
                "enabled": True,
                "recipient": "patti@centralvalleyheli.com",
                "gmail": {
                    "client_id": "gmail-client",
                    "client_secret": "gmail-secret",
                    "redirect_uri": "https://mail-callback.example.com/timesheet-mail/callback/gmail",
                },
            },
            "timesheet_mail_backend": {
                "public_base_url": "https://mail-callback.example.com",
                "state_secret": "test-state-secret-not-used-live",
                "app_base_url": "https://cvhapp.example.com/",
            },
            "timesheet_employee_mail": {
                "Gary Grant": {"email": "gary.mail@example.com", "provider": "gmail"},
            },
        }
        seen = {}

        def capture(url, payload, timeout):
            seen["payload"] = payload
            return 200, json.dumps({"ok": True, "status": tm.TIMESHEET_MAIL_STATUS_SENT})

        record = {
            "Employee": "Gary Grant",
            "Week Of": "2026-11-08",
            "Initials": "GG",
            "Content Hash": "hash-gary",
            "Entry ID": "TS-PIN-1",
        }
        pdf = b"%PDF-1.4 pin"
        result = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets,
            user_employee="Gary Grant",
            signin_email="gary.signin@example.com",
            initials_match=True,
            saved_content_hash="hash-gary",
            http_post=capture,
        )
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        body = tm.timesheet_verify_state(seen["payload"]["token"], secrets["timesheet_mail_backend"]["state_secret"])
        self.assertEqual(body["employee_key"], "Gary Grant")
        self.assertNotIn("signin_email", body)
        self.assertNotIn("gary.signin@example.com", json.dumps(body))
        mismatched = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets,
            user_employee="Gary Grant",
            employee_key="Carl Mulvaney",
            initials_match=True,
            saved_content_hash="hash-gary",
            http_post=capture,
        )
        self.assertEqual(mismatched["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("own initialed", mismatched["error"])


if __name__ == "__main__":
    unittest.main()
