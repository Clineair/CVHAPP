"""Per-user timesheet mail OAuth and send gates. No live provider or sheet writes."""
import base64
import time
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import timesheet_mail as tm
import timesheet_mail_callback as cb


def _secrets():
    return {
        "timesheet_mail": {
            "enabled": True,
            "gmail": {
                "client_id": "gmail-client",
                "client_secret": "gmail-secret",
                "redirect_uri": "https://mail-callback.example.com/timesheet-mail/callback/gmail",
            },
            "microsoft": {
                "client_id": "ms-client",
                "client_secret": "ms-secret",
                "redirect_uri": "https://mail-callback.example.com/timesheet-mail/callback/microsoft",
                "tenant": "common",
            },
        },
        "timesheet_mail_backend": {
            "public_base_url": "https://mail-callback.example.com",
            "state_secret": "test-state-secret-not-used-live",
        },
        "timesheet_employee_mail": {
            "Carl Mulvaney": {"email": "carl.mail@example.com", "provider": "gmail"},
            "Barry Markham": {"email": "barry.mail@example.com", "provider": "microsoft"},
        },
    }


def _record(employee="Carl Mulvaney", hours="8", initials="CM", entry="TS-MAIL-1"):
    return {
        "Employee": employee,
        "Week Of": "2026-11-08",
        "Sun CVH Hours": hours,
        "Initials": initials,
        "Content Hash": "hash-" + employee + "-" + hours,
        "Entry ID": entry,
        "Status": "Initialed",
    }


def _pdf():
    return b"%PDF-1.4 mock-timesheet-pdf"


def _consent(employee="Carl Mulvaney", provider="gmail", email="carl.mail@example.com", exp=None):
    return {
        "employee": employee,
        "provider": provider,
        "mailbox_email": email,
        "exp": exp or (time.time() + 1800),
    }


class TimesheetMailTests(unittest.TestCase):
    def test_setup_defaults_disabled_and_fails_closed(self):
        self.assertFalse(tm.timesheet_mail_flag_enabled({}))
        self.assertFalse(tm.timesheet_mail_secure_setup_ready({}))
        self.assertFalse(tm.timesheet_mail_secure_setup_ready({
            "timesheet_mail": {"enabled": False, "gmail": _secrets()["timesheet_mail"]["gmail"]},
            "timesheet_mail_backend": _secrets()["timesheet_mail_backend"],
        }))
        # enabled without backend is still closed
        incomplete = dict(_secrets())
        incomplete.pop("timesheet_mail_backend")
        self.assertFalse(tm.timesheet_mail_secure_setup_ready(incomplete))
        self.assertEqual(tm.timesheet_employee_mailbox_map({}), {})
        ok, reason = tm.timesheet_mail_send_gates(_record(), access_allowed=True, initials_match=True, pdf_bytes=_pdf(), filename="a.pdf")
        self.assertFalse(ok)
        self.assertIn("does not send mail", reason)

    def test_mapping_requires_provider_and_drops_duplicates(self):
        secrets = _secrets()
        mapping = tm.timesheet_employee_mailbox_map(secrets)
        self.assertEqual(mapping["Carl Mulvaney"]["provider"], "gmail")
        self.assertEqual(mapping["Barry Markham"]["provider"], "microsoft")
        self.assertNotIn("Gary Grant", mapping)
        secrets["timesheet_employee_mail"]["Carl Mulvaney"] = {"email": "shared@example.com", "provider": "gmail"}
        secrets["timesheet_employee_mail"]["Barry Markham"] = {"email": "shared@example.com", "provider": "microsoft"}
        self.assertEqual(tm.timesheet_employee_mailbox_map(secrets), {})
        secrets["timesheet_employee_mail"]["Carl Mulvaney"] = {"email": "not-an-email", "provider": "gmail"}
        self.assertNotIn("Carl Mulvaney", tm.timesheet_employee_mailbox_map(secrets))

    def test_reserved_streamlit_callback_rejected(self):
        secrets = _secrets()
        secrets["timesheet_mail"]["gmail"]["redirect_uri"] = "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/oauth2callback"
        self.assertEqual(tm.timesheet_mail_redirect_uri("gmail", secrets), "")
        secrets["timesheet_mail_backend"]["public_base_url"] = "https://example.com/oauth2callback"
        self.assertEqual(tm.timesheet_mail_backend_base(secrets), "")

    def test_authorize_url_uses_official_routes_pkce_and_no_offline_google(self):
        secrets = _secrets()
        verifier, challenge = tm.timesheet_pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        state = tm.timesheet_sign_state({"n": "abc", "employee": "Carl Mulvaney", "provider": "gmail"}, tm.timesheet_mail_state_secret(secrets))
        url = tm.timesheet_authorize_url("gmail", state, challenge, secrets, login_hint="carl.mail@example.com")
        self.assertTrue(url.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("access_type=online", url)
        self.assertIn("gmail.send", url)
        self.assertNotIn("gmail.modify", url)
        self.assertNotIn("gmail.secret", url.lower().replace("client_secret", ""))
        self.assertNotIn("gmail-secret", url)
        ms = tm.timesheet_authorize_url("microsoft", state, challenge, secrets)
        self.assertTrue(ms.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"))
        self.assertIn("Mail.Send", ms)
        self.assertNotIn("Mail.Read", ms)

    def test_state_tamper_and_expiry(self):
        secrets = _secrets()
        secret = tm.timesheet_mail_state_secret(secrets)
        token = tm.timesheet_sign_state({"n": "n1", "employee": "Carl Mulvaney"}, secret, now=1000)
        self.assertIsNone(tm.timesheet_verify_state(token + "x", secret, now=1000))
        self.assertIsNone(tm.timesheet_verify_state(token, "other-secret", now=1000))
        self.assertIsNone(tm.timesheet_verify_state(token, secret, now=1000 + tm.TIMESHEET_MAIL_STATE_TTL_SEC + 1))
        body = tm.timesheet_verify_state(token, secret, now=1001)
        self.assertEqual(body["n"], "n1")

    def test_identity_mismatch_and_missing_consent_cannot_send(self):
        secrets = _secrets()
        rec = _record()
        pdf = _pdf()
        good = _consent()
        # other employee
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Barry Markham", consent=good, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        self.assertIn("own initialed time sheet", reason)
        # unauthenticated / no access
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=good, secrets=secrets,
            initials_match=True, access_allowed=False, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        # stale initials
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=good, secrets=secrets,
            initials_match=False, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        self.assertIn("Initial and save", reason)
        # wrong recipient
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=good, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
            to="other@example.com",
        )
        self.assertFalse(ok)
        self.assertIn("patti@centralvalleyheli.com", reason)
        # mismatched mailbox
        bad_box = _consent(email="stranger@example.com")
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=bad_box, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        self.assertIn("does not match", reason)
        # mismatched provider
        bad_prov = _consent(provider="microsoft")
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=bad_prov, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        # absent consent
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=None, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        self.assertIn("A time-sheet PIN does not grant", reason)
        # expired consent
        expired = _consent(exp=time.time() - 10)
        ok, reason = tm.timesheet_mail_send_gates(
            rec, user_employee="Carl Mulvaney", consent=expired, secrets=secrets,
            initials_match=True, access_allowed=True, pdf_bytes=pdf, filename="a.pdf",
        )
        self.assertFalse(ok)
        self.assertIn("expired", reason)

    def test_successful_gmail_and_microsoft_send_and_preview(self):
        secrets = _secrets()
        rec = _record()
        store = tm.MemoryMailTokenStore()
        store.put_access("Carl Mulvaney", "gmail", "carl.mail@example.com", "g-token")
        posted = []

        def http_post(url, headers=None, json=None, timeout=30):
            posted.append({"url": url, "headers": headers, "json": json})
            self.assertNotIn("g-token", repr(json))
            self.assertEqual(headers["Authorization"], "Bearer g-token")
            self.assertTrue(url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/send"))
            raw = base64.urlsafe_b64decode(json["raw"] + "==")
            self.assertIn(b"patti@centralvalleyheli.com", raw)
            self.assertIn(b"carl.mail@example.com", raw)
            self.assertIn(b"application/pdf", raw)
            self.assertIn(b"Carl_Mulvaney_2026-11-08.pdf", raw)
            self.assertNotIn(b"other@example.com", raw)
            return 200, '{"id": "gm-1"}'

        result = tm.execute_timesheet_send(
            rec, store=store, pdf_bytes=_pdf(), filename="Carl_Mulvaney_2026-11-08.pdf",
            secrets=secrets, user_employee="Carl Mulvaney", initials_match=True,
            access_allowed=True, http_post=http_post,
        )
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(result["to"], "patti@centralvalleyheli.com")
        self.assertEqual(result["from"], "carl.mail@example.com")
        preview = tm.timesheet_mail_preview(rec, store.consent_metadata("Carl Mulvaney"), filename="Carl_Mulvaney_2026-11-08.pdf")
        self.assertEqual(preview["to"], "patti@centralvalleyheli.com")
        self.assertEqual(preview["from"], "carl.mail@example.com")
        self.assertIn("Carl_Mulvaney_2026-11-08.pdf", preview["attachment"])
        self.assertIn("reviewed and confirmed Send", preview["body"])

        store.put_access("Barry Markham", "microsoft", "barry.mail@example.com", "ms-token")
        rec_b = _record("Barry Markham", "7", "BM", "TS-MAIL-2")

        def ms_post(url, headers=None, json=None, timeout=30):
            self.assertEqual(url, "https://graph.microsoft.com/v1.0/me/sendMail")
            self.assertEqual(json["message"]["toRecipients"][0]["emailAddress"]["address"], "patti@centralvalleyheli.com")
            self.assertEqual(json["message"]["attachments"][0]["contentType"], "application/pdf")
            self.assertEqual(json["message"]["attachments"][0]["name"], "b.pdf")
            return 202, ""

        result = tm.execute_timesheet_send(
            rec_b, store=store, pdf_bytes=_pdf(), filename="b.pdf",
            secrets=secrets, user_employee="Barry Markham", initials_match=True,
            access_allowed=True, http_post=ms_post,
        )
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(result["provider"], "microsoft")

    def test_duplicate_rerun_and_uncertain_no_auto_retry(self):
        secrets = _secrets()
        rec = _record()
        store = tm.MemoryMailTokenStore()
        store.put_access("Carl Mulvaney", "gmail", "carl.mail@example.com", "g-token")
        calls = {"n": 0}

        def http_post(url, headers=None, json=None, timeout=30):
            calls["n"] += 1
            return 200, '{"id": "gm-1"}'

        first = tm.execute_timesheet_send(
            rec, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True, http_post=http_post,
        )
        self.assertEqual(first["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        audit = [{
            "Employee": "Carl Mulvaney", "Week Of": "2026-11-08",
            "Content Hash": rec["Content Hash"], "Status": tm.TIMESHEET_MAIL_STATUS_SENT,
            "Idempotency Key": first["idempotency_key"],
        }]
        second = tm.execute_timesheet_send(
            rec, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True,
            http_post=http_post, audit_records=audit,
        )
        self.assertEqual(second["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("already sent", second["error"])
        self.assertEqual(calls["n"], 1)

        in_flight = {first["idempotency_key"]}
        rerun = tm.execute_timesheet_send(
            rec, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True,
            http_post=http_post, in_flight=in_flight,
        )
        self.assertEqual(rerun["status"], tm.TIMESHEET_MAIL_STATUS_DUPLICATE)
        self.assertEqual(calls["n"], 1)

        rec2 = _record(hours="9", entry="TS-MAIL-3")
        rec2["Content Hash"] = "hash-Carl Mulvaney-9"
        store.put_access("Carl Mulvaney", "gmail", "carl.mail@example.com", "g-token")

        def boom(url, headers=None, json=None, timeout=30):
            calls["n"] += 1
            raise TimeoutError("network timeout Bearer g-token")

        uncertain = tm.execute_timesheet_send(
            rec2, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True, http_post=boom,
        )
        self.assertEqual(uncertain["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        self.assertNotIn("g-token", uncertain["error"])
        audit_u = [{
            "Employee": rec2["Employee"], "Week Of": rec2["Week Of"],
            "Content Hash": rec2["Content Hash"], "Status": tm.TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "Idempotency Key": uncertain["idempotency_key"],
        }]
        blocked = tm.execute_timesheet_send(
            rec2, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True,
            http_post=http_post, audit_records=audit_u,
        )
        self.assertEqual(blocked["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("will not retry automatically", blocked["error"])
        # Explicit acknowledgement is required; still a deliberate second click, not an automatic retry.
        allowed = tm.execute_timesheet_send(
            rec2, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Carl Mulvaney", initials_match=True, access_allowed=True,
            http_post=http_post, audit_records=audit_u, acknowledge_uncertain=True,
        )
        self.assertEqual(allowed["status"], tm.TIMESHEET_MAIL_STATUS_SENT)

    def test_bind_rejects_mismatched_mailbox_and_drops_refresh_tokens(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        pending = {"employee": "Carl Mulvaney", "provider": "gmail"}
        consent, error = tm.bind_consented_mailbox(
            store, pending,
            {"access_token": "tok", "refresh_token": "should-not-be-kept", "expires_in": 3600},
            {"email": "wrong@example.com"},
            secrets=secrets,
        )
        self.assertIsNone(consent)
        self.assertIn("does not match", error)
        self.assertIsNone(store.get_access("Carl Mulvaney"))
        consent, error = tm.bind_consented_mailbox(
            store, pending,
            {"access_token": "tok", "refresh_token": "should-not-be-kept", "expires_in": 3600},
            {"email": "Carl.Mail@example.com"},
            secrets=secrets,
        )
        self.assertTrue(consent)
        self.assertEqual(error, "")
        stored = store.get_access("Carl Mulvaney")
        self.assertEqual(stored["mailbox_email"], "carl.mail@example.com")
        self.assertNotIn("refresh_token", stored)
        # tickets return metadata only
        ticket = store.issue_ticket("Carl Mulvaney")
        meta = store.redeem_ticket(ticket)
        self.assertNotIn("access_token", meta)
        self.assertEqual(meta["mailbox_email"], "carl.mail@example.com")
        self.assertIsNone(store.redeem_ticket(ticket))  # single use

    def test_callback_exchanges_on_backend_and_redirects_without_tokens(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        start = cb.start_authorization(secrets, "Carl Mulvaney", "gmail", "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/", store=store)
        self.assertIn("accounts.google.com", start)
        # Recover nonce from pending store (only one).
        nonce = list(store._pending.keys())[0]
        state = tm.timesheet_sign_state({
            "n": nonce, "employee": "Carl Mulvaney", "provider": "gmail",
            "return": "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
        }, tm.timesheet_mail_state_secret(secrets))

        def token_fetch(payload):
            self.assertEqual(payload["url"], "https://oauth2.googleapis.com/token")
            self.assertEqual(payload["data"]["grant_type"], "authorization_code")
            self.assertIn("code_verifier", payload["data"])
            return {"access_token": "live-token-value", "expires_in": 3600, "refresh_token": "ignore-me"}

        def userinfo_fetch(url, access_token):
            self.assertEqual(url, "https://openidconnect.googleapis.com/v1/userinfo")
            self.assertEqual(access_token, "live-token-value")
            return {"email": "carl.mail@example.com", "email_verified": True}

        status, location, msg = cb.handle_provider_callback(
            secrets,
            {"code": "auth-code-value", "state": state},
            userinfo_fetch,
            token_fetch,
            store=store,
            app_base_fallback="https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
        )
        self.assertEqual(status, 302)
        self.assertEqual(msg, "ok")
        self.assertTrue(location.startswith("https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/"))
        self.assertNotIn("auth-code-value", location)
        self.assertNotIn("live-token-value", location)
        self.assertNotIn("ignore-me", location)
        self.assertIn("timesheet_mail=ready", location)
        self.assertIn("ticket=", location)
        # Replay of the same state fails.
        status2, _, msg2 = cb.handle_provider_callback(
            secrets, {"code": "auth-code-value", "state": state},
            userinfo_fetch, token_fetch, store=store,
            app_base_fallback="https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
        )
        self.assertEqual(status2, 400)
        self.assertEqual(msg2, "expired_or_replayed_state")

    def test_error_sanitizer_and_wrong_file_rejected(self):
        self.assertNotIn("secret", tm.sanitize_mail_error("boom Bearer abc.def.refresh_token=xyz"))
        self.assertIn("[redacted]", tm.sanitize_mail_error("access_token=abcd"))
        rec = _record()
        with self.assertRaisesRegex(ValueError, "generated timesheet PDF"):
            tm.build_timesheet_mime(rec, b"not-a-pdf", "a.pdf", "carl.mail@example.com")
        with self.assertRaisesRegex(ValueError, "generated timesheet PDF"):
            tm.build_timesheet_mime(rec, _pdf(), "notes.txt", "carl.mail@example.com")
        with self.assertRaisesRegex(ValueError, "patti@centralvalleyheli.com"):
            tm.build_timesheet_mime(rec, _pdf(), "a.pdf", "carl.mail@example.com", to="other@example.com")

    def test_start_link_is_signed_and_has_no_secrets(self):
        secrets = _secrets()
        link = tm.timesheet_mail_start_link(
            "Carl Mulvaney", "gmail",
            "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
            secrets,
        )
        self.assertTrue(link.startswith("https://mail-callback.example.com/timesheet-mail/start?"))
        self.assertNotIn("gmail-secret", link)
        self.assertNotIn("test-state-secret", link)
        self.assertEqual(tm.timesheet_mail_start_link("Gary Grant", "gmail", "https://app.example/", secrets), "")

    def test_icloud_and_yahoo_use_official_smtp_and_fail_closed(self):
        secrets = _secrets()
        secrets["timesheet_employee_mail"]["Skylar Fingerle"] = {
            "email": "skylar.mail@example.com", "provider": "icloud",
        }
        secrets["timesheet_employee_mail"]["Carl Mulvaney"] = {
            "email": "carl.mail@example.com", "provider": "yahoo",
        }
        self.assertEqual(tm.timesheet_mail_auth_mode("icloud"), "smtp_app_password")
        self.assertEqual(tm.timesheet_mail_auth_mode("yahoo"), "smtp_app_password")
        self.assertEqual(tm.timesheet_mail_auth_mode("gmail"), "oauth")
        self.assertEqual(tm.TIMESHEET_MAIL_SMTP_SPEC["icloud"]["host"], "smtp.mail.me.com")
        self.assertEqual(tm.TIMESHEET_MAIL_SMTP_SPEC["icloud"]["port"], 587)
        self.assertEqual(tm.TIMESHEET_MAIL_SMTP_SPEC["yahoo"]["host"], "smtp.mail.yahoo.com")
        self.assertFalse(tm.timesheet_smtp_store_configured(secrets))
        self.assertFalse(tm.timesheet_mail_provider_configured("icloud", secrets))
        self.assertFalse(tm.timesheet_mail_provider_configured("yahoo", secrets))
        # Official OAuth start is not offered for SMTP providers.
        self.assertEqual(
            tm.timesheet_mail_start_link(
                "Skylar Fingerle", "icloud",
                "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
                secrets,
            ),
            "",
        )
        with self.assertRaisesRegex(ValueError, "no public self-serve OAuth"):
            tm.timesheet_authorize_url("icloud", "state", "challenge", secrets)
        rec = _record("Skylar Fingerle")
        ok, reason = tm.timesheet_mail_send_gates(
            rec,
            user_employee="Skylar Fingerle",
            consent=None,
            initials_match=True,
            access_allowed=True,
            pdf_bytes=_pdf(),
            filename="sheet.pdf",
            secrets=secrets,
        )
        self.assertFalse(ok)
        self.assertIn("no public OAuth send API", reason)
        self.assertIn("smtp.mail.me.com", reason)
        self.assertIn("app-specific password", reason)
        self.assertIn("never in Sheets, chat, or an app form", reason)
        rec2 = _record("Carl Mulvaney")
        ok2, reason2 = tm.timesheet_mail_send_gates(
            rec2,
            user_employee="Carl Mulvaney",
            consent=None,
            initials_match=True,
            access_allowed=True,
            pdf_bytes=_pdf(),
            filename="sheet.pdf",
            secrets=secrets,
        )
        self.assertFalse(ok2)
        self.assertIn("smtp.mail.yahoo.com", reason2)
        self.assertIn("app password", reason2)
        self.assertIn("not self-serve", reason2)
        # Marking a vault hook present still does not invent or send mail here,
        # and still must not produce an OAuth start link.
        secrets["timesheet_smtp"] = {"configured": True}
        self.assertTrue(tm.timesheet_smtp_store_configured(secrets))
        self.assertEqual(
            tm.timesheet_mail_start_link(
                "Skylar Fingerle", "icloud",
                "https://cvhapp-fpzzanc7kwhapubsvkjx67.streamlit.app/",
                secrets,
            ),
            "",
        )

    def test_callback_env_secrets_and_serve_guard(self):
        import json
        self.assertIsNone(cb.secrets_from_env({}))
        self.assertIsNone(cb.secrets_from_env({"TIMESHEET_MAIL_SECRETS_JSON": "not-json"}))
        payload = {"timesheet_mail_backend": {"public_base_url": "https://mail-callback.example.com"}}
        loaded = cb.secrets_from_env({"TIMESHEET_MAIL_SECRETS_JSON": json.dumps(payload)})
        self.assertEqual(loaded["timesheet_mail_backend"]["public_base_url"], "https://mail-callback.example.com")
        with self.assertRaises(SystemExit) as raised:
            cb.main(environ={})
        self.assertIn("TIMESHEET_MAIL_ALLOW_SERVE=1", str(raised.exception))
        self.assertEqual(cb.official_http_token_fetch({}), {})
        self.assertEqual(cb.official_http_userinfo_fetch("", ""), {})




if __name__ == "__main__":
    unittest.main()
