"""Company-mailbox timesheet send. No network, no live mail, no Sheets."""
import base64
import json
import unittest
from pathlib import Path

import timesheet_company_mail as company
import timesheet_mail as tm

PDF = b"%PDF-1.4 company-timesheet"
PASSWORD = "mailbox-secret-value"
CLIENT_SECRET = "graph-client-secret-value"


def _record(employee="Carl Mulvaney"):
    return {
        "Employee": employee,
        "Week Of": "2026-11-08",
        "Initials": "CM",
        "Content Hash": "hash-" + employee,
        "Entry ID": "TS-CO-1",
    }


def _smtp_secrets(**extra):
    data = {
        "timesheet_company_mail": {
            "enabled": True,
            "backend": "gmail_smtp",
            "username": company.DEFAULT_SENDER,
            "password": PASSWORD,
        },
        "timesheet_employee_mail": {
            "Carl Mulvaney": {"email": "carl.mail@example.com", "provider": "icloud"},
        },
        "timesheet_employees": {
            "Carl Mulvaney": "carl.signin@example.com",
            "Gary Grant": "gary.signin@example.com",
        },
    }
    data.update(extra)
    return data


def _graph_secrets():
    data = _smtp_secrets()
    data["timesheet_company_mail"] = {
        "enabled": True,
        "backend": "graph",
        "tenant_id": "tenant-id",
        "client_id": "client-id",
        "client_secret": CLIENT_SECRET,
    }
    return data


def _send_kwargs(record=None, secrets=None, **extra):
    record = record or _record()
    if secrets is None and "secrets" not in extra:
        secrets = _smtp_secrets()
    payload = dict(
        secrets=secrets,
        user_employee=record["Employee"],
        initials_match=True,
        saved_content_hash=record["Content Hash"],
        access_allowed=True,
    )
    payload.update(extra)
    return record, payload


class CompanyMailSetupTests(unittest.TestCase):
    def test_missing_or_disabled_section_is_not_ready(self):
        self.assertFalse(company.company_mail_ready(None))
        self.assertFalse(company.company_mail_ready({}))
        self.assertEqual(company.NOT_READY_MESSAGE, "email not set up yet - ask the office")
        off = _smtp_secrets()
        off["timesheet_company_mail"]["enabled"] = False
        self.assertFalse(company.company_mail_ready(off))
        off["timesheet_company_mail"]["enabled"] = "true"
        self.assertTrue(company.company_mail_ready(off))
        off["timesheet_company_mail"]["password"] = ""
        self.assertFalse(company.company_mail_ready(off))
        off["timesheet_company_mail"]["password"] = PASSWORD
        off["timesheet_company_mail"]["username"] = "other@example.com"
        self.assertFalse(company.company_mail_ready(off))
        off["timesheet_company_mail"]["username"] = company.DEFAULT_SENDER
        off["timesheet_company_mail"]["sender"] = "not-an-email"
        self.assertFalse(company.company_mail_ready(off))
        off["timesheet_company_mail"]["sender"] = "other.timesheets@example.com"
        self.assertFalse(company.company_mail_ready(off))
        off["timesheet_company_mail"]["username"] = "other.timesheets@example.com"
        self.assertTrue(company.company_mail_ready(off))
        self.assertEqual(company.mailbox_address(off), "other.timesheets@example.com")
        graph = _graph_secrets()
        self.assertTrue(company.company_mail_ready(graph))
        del graph["timesheet_company_mail"]["client_secret"]
        self.assertFalse(company.company_mail_ready(graph))

    def test_reply_to_prefers_employee_mail_then_signin_map(self):
        secrets = _smtp_secrets()
        self.assertEqual(company.employee_reply_to("Carl Mulvaney", secrets), "carl.mail@example.com")
        del secrets["timesheet_employee_mail"]
        self.assertEqual(company.employee_reply_to("Gary Grant", secrets), "gary.signin@example.com")
        self.assertEqual(company.employee_reply_to("Barry Markham", secrets), "")
        self.assertEqual(company.display_name("Carl Mulvaney"), "Carl Mulvaney via CVH Timesheets")
        self.assertIn("2026-11-08", company.email_subject(_record()))
        self.assertIn("Carl Mulvaney", company.email_body(_record()))
        self.assertIn("week of 2026-11-08", company.email_body(_record()))


class CompanySmtpSendTests(unittest.TestCase):
    def test_smtp_sends_company_from_reply_to_and_pdf_without_network(self):
        sent = []

        def smtp_send(username, password, message):
            sent.append((username, password, message))

        record, kwargs = _send_kwargs()
        result = company.send_company_timesheet(record, PDF, "Carl_Mulvaney.pdf", smtp_send=smtp_send, **kwargs)
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(result["from"], company.DEFAULT_SENDER)
        self.assertEqual(result["to"], "patti@centralvalleyheli.com")
        self.assertEqual(result["provider"], "gmail_smtp")
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertEqual(len(sent), 1)
        username, password, message = sent[0]
        self.assertEqual(username, company.DEFAULT_SENDER)
        self.assertEqual(password, PASSWORD)
        self.assertEqual(message["To"], "patti@centralvalleyheli.com")
        self.assertIn(company.DEFAULT_SENDER, message["From"])
        self.assertIn("Carl Mulvaney via CVH Timesheets", message["From"])
        self.assertEqual(message["Reply-To"], "carl.mail@example.com")
        self.assertIn("Carl Mulvaney", message["Subject"])
        self.assertIn("2026-11-08", message["Subject"])
        attached = None
        filename = ""
        for part in message.walk():
            if part.get_content_type() == "application/pdf":
                attached = part.get_payload(decode=True)
                filename = part.get_filename()
        self.assertEqual(attached, PDF)
        self.assertEqual(filename, "Carl_Mulvaney.pdf")
        self.assertIn("Carl Mulvaney", message.get_body(preferencelist=("plain",)).get_content())

    def test_gates_block_send_before_the_mailbox_is_contacted(self):
        calls = []

        def smtp_send(*args):
            calls.append(args)

        record, kwargs = _send_kwargs(user_employee="Barry Markham")
        cross = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=smtp_send, **kwargs)
        self.assertEqual(cross["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("own initialed", cross["error"])
        record, kwargs = _send_kwargs(initials_match=False)
        stale = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=smtp_send, **kwargs)
        self.assertIn("Initial and save", stale["error"])
        record, kwargs = _send_kwargs(secrets={})
        closed = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=smtp_send, **kwargs)
        self.assertEqual(closed["error"], company.NOT_READY_MESSAGE)
        record, kwargs = _send_kwargs(audit_records=[{
            "Employee": "Carl Mulvaney",
            "Week Of": "2026-11-08",
            "Content Hash": "hash-Carl Mulvaney",
            "Status": tm.TIMESHEET_MAIL_STATUS_SENT,
            "Idempotency Key": tm.timesheet_send_idempotency_key(_record()),
        }])
        duplicate = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=smtp_send, **kwargs)
        self.assertIn("already sent", duplicate["error"])
        self.assertEqual(calls, [])

    def test_timeout_is_uncertain_and_password_is_not_returned(self):
        def boom(username, password, message):
            raise TimeoutError("timed out login " + password)

        record, kwargs = _send_kwargs()
        result = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=boom, **kwargs)
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertIn("will not retry automatically", result["error"])
        audit = [{
            "Employee": record["Employee"],
            "Week Of": record["Week Of"],
            "Content Hash": record["Content Hash"],
            "Status": tm.TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "Idempotency Key": result["idempotency_key"],
        }]
        calls = []
        record, kwargs = _send_kwargs(audit_records=audit, smtp_send=lambda *args: calls.append(1))
        blocked = company.send_company_timesheet(record, PDF, "a.pdf", **kwargs)
        self.assertEqual(blocked["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertEqual(calls, [])
        record, kwargs = _send_kwargs(audit_records=audit, acknowledge_uncertain=True, smtp_send=lambda *a: calls.append(1))
        again = company.send_company_timesheet(record, PDF, "a.pdf", **kwargs)
        self.assertEqual(again["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(calls, [1])

    def test_rejected_login_does_not_echo_the_password(self):
        def reject(username, password, message):
            raise OSError("535 5.7.3 authentication unsuccessful " + password)

        record, kwargs = _send_kwargs()
        result = company.send_company_timesheet(record, PDF, "a.pdf", smtp_send=reject, **kwargs)
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertIn("rejected the login", result["error"])

    def test_default_transports_do_not_open_a_network_connection(self):
        import smtplib
        seen = []

        class FakeSSL:
            def __init__(self, host, port, timeout=None, context=None):
                seen.append(("ssl", host, port))

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def login(self, username, password):
                seen.append(("login", username))

            def send_message(self, message):
                seen.append(("sent", message["From"]))

        class FakeStartTLS:
            def __init__(self, host, port, timeout=None):
                seen.append(("starttls-connect", host, port))

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def ehlo(self):
                return None

            def starttls(self, context=None):
                seen.append(("starttls",))

            def login(self, username, password):
                seen.append(("login", username))

            def send_message(self, message):
                seen.append(("sent", str(message["From"])))

        original_ssl = smtplib.SMTP_SSL
        original_smtp = smtplib.SMTP
        smtplib.SMTP_SSL = FakeSSL
        smtplib.SMTP = FakeStartTLS
        try:
            record, kwargs = _send_kwargs()
            gmail = company.send_company_timesheet(record, PDF, "a.pdf", **kwargs)
            self.assertEqual(gmail["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
            self.assertEqual(gmail["provider"], "gmail_smtp")
            self.assertIn(("ssl", "smtp.gmail.com", 465), seen)
            self.assertNotIn("cvh@centralvalleyheli.com", json.dumps(seen))
            office_secrets = _smtp_secrets()
            office_secrets["timesheet_company_mail"]["backend"] = "smtp"
            office_secrets["timesheet_company_mail"]["sender"] = "office.timesheets@example.com"
            office_secrets["timesheet_company_mail"]["username"] = "office.timesheets@example.com"
            record, kwargs = _send_kwargs(secrets=office_secrets)
            office = company.send_company_timesheet(record, PDF, "a.pdf", **kwargs)
            self.assertEqual(office["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
            self.assertEqual(office["from"], "office.timesheets@example.com")
            self.assertIn(("starttls-connect", "smtp.office365.com", 587), seen)
            self.assertIn(("starttls",), seen)
        finally:
            smtplib.SMTP_SSL = original_ssl
            smtplib.SMTP = original_smtp
        source = Path(company.__file__).read_text(encoding="utf-8")
        self.assertNotIn("cvh@centralvalleyheli.com", source)


class CompanyGraphSendTests(unittest.TestCase):
    def test_graph_token_and_sendmail_use_the_company_mailbox(self):
        calls = []

        def http_post(url, *, json_body=None, form=None, headers=None, timeout=30):
            calls.append({"url": url, "json": json_body, "form": form, "headers": headers})
            if url.endswith("/token"):
                return 200, json.dumps({"access_token": "graph-access-token"})
            return 202, ""

        record, kwargs = _send_kwargs(secrets=_graph_secrets())
        result = company.send_company_timesheet(record, PDF, "Carl.pdf", http_post=http_post, **kwargs)
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(result["from"], company.DEFAULT_SENDER)
        self.assertNotIn(CLIENT_SECRET, json.dumps(result))
        self.assertNotIn("graph-access-token", json.dumps(result))
        self.assertEqual(len(calls), 2)
        self.assertIn("/oauth2/v2.0/token", calls[0]["url"])
        self.assertEqual(calls[0]["form"]["client_secret"], CLIENT_SECRET)
        self.assertEqual(calls[0]["form"]["grant_type"], "client_credentials")
        self.assertTrue(calls[1]["url"].endswith("/users/" + company.DEFAULT_SENDER + "/sendMail"))
        self.assertTrue(calls[1]["headers"]["Authorization"].startswith("Bearer "))
        message = calls[1]["json"]["message"]
        self.assertEqual(message["from"]["emailAddress"]["address"], company.DEFAULT_SENDER)
        self.assertEqual(message["from"]["emailAddress"]["name"], "Carl Mulvaney via CVH Timesheets")
        self.assertEqual(message["replyTo"][0]["emailAddress"]["address"], "carl.mail@example.com")
        self.assertEqual(message["toRecipients"][0]["emailAddress"]["address"], "patti@centralvalleyheli.com")
        self.assertIn("Carl Mulvaney", message["subject"])
        self.assertIn("2026-11-08", message["body"]["content"])
        self.assertEqual(base64.b64decode(message["attachments"][0]["contentBytes"]), PDF)
        self.assertTrue(calls[1]["json"]["saveToSentItems"])

    def test_graph_rejection_and_outage_do_not_include_the_secret(self):
        def reject(url, *, json_body=None, form=None, headers=None, timeout=30):
            return 401, "invalid_client " + CLIENT_SECRET

        record, kwargs = _send_kwargs(secrets=_graph_secrets())
        denied = company.send_company_timesheet(record, PDF, "a.pdf", http_post=reject, **kwargs)
        self.assertEqual(denied["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertNotIn(CLIENT_SECRET, json.dumps(denied))

        def outage(url, *, json_body=None, form=None, headers=None, timeout=30):
            if url.endswith("/token"):
                return 200, json.dumps({"access_token": "tok"})
            return 503, "unavailable " + CLIENT_SECRET

        uncertain = company.send_company_timesheet(record, PDF, "a.pdf", http_post=outage, **kwargs)
        self.assertEqual(uncertain["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        self.assertNotIn(CLIENT_SECRET, json.dumps(uncertain))
        self.assertNotIn("tok", json.dumps(uncertain))


if __name__ == "__main__":
    unittest.main()
