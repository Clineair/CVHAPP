"""UI to HTTP to provider coverage for timesheet send. No live mail, Sheets, or cloud calls."""
import ast
import base64
import email
from email.header import decode_header, make_header
import hashlib
import json
import smtplib
import threading
import time
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import timesheet_mail as tm
import timesheet_mail_callback as cb

APP = Path(__file__).resolve().parents[1] / "app.py"
DOCKERFILE = Path(__file__).resolve().parents[1] / "deploy" / "timesheet-mail-callback" / "Dockerfile"
CALLBACK_REQUIREMENTS = Path(__file__).resolve().parents[1] / "deploy" / "timesheet-mail-callback" / "requirements.txt"


def _secrets():
    return {
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
        "timesheet_employees": {
            "Gary Grant": "gary.signin@example.com",
            "Robert Rackley": "robert.signin@example.com",
            "Anthony Root": "anthony.signin@example.com",
            "Carl Mulvaney": "carl.signin@example.com",
            "Skylar Fingerle": "skylar.signin@example.com",
            "Barry Markham": "barry.signin@example.com",
        },
        "timesheet_employee_mail": {
            "Gary Grant": {"email": "gary.mail@example.com", "provider": "gmail"},
            "Robert Rackley": {"email": "robert.mail@example.com", "provider": "gmail"},
            "Anthony Root": {"email": "anthony.mail@example.com", "provider": "gmail"},
            "Carl Mulvaney": {"email": "carl.mail@example.com", "provider": "icloud"},
            "Skylar Fingerle": {"email": "skylar.mail@example.com", "provider": "icloud"},
            "Barry Markham": {"email": "barry.mail@example.com", "provider": "yahoo"},
        },
        "timesheet_smtp": {"configured": True, "project": "cvh-test"},
    }


def _record(employee="Gary Grant", hours="8", initials="GG"):
    return {
        "Employee": employee,
        "Week Of": "2026-11-08",
        "Initials": initials,
        "Content Hash": "hash-" + employee + "-" + hours,
        "Entry ID": "TS-SEND-1",
        "Status": "Initialed",
    }


def _pdf(marker=b"gary"):
    return b"%PDF-1.4 timesheet " + marker


class FakeSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None
        return dict(self._data)


class FakeDoc:
    def __init__(self, client, key):
        self.client = client
        self.key = key

    def get(self, transaction=None):
        with self.client.lock:
            data = self.client.data.get(self.key)
            return FakeSnapshot(None if data is None else dict(data))


class FakeCollection:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def document(self, doc_id):
        return FakeDoc(self.client, self.name + "/" + doc_id)


class FakeTxn:
    def __init__(self, client):
        self.client = client

    def get(self, doc):
        return doc.get()

    def set(self, doc, data):
        with self.client.lock:
            self.client.data[doc.key] = dict(data)

    def delete(self, doc):
        with self.client.lock:
            self.client.data.pop(doc.key, None)


class FakeFirestore:
    def __init__(self, data=None):
        self.data = data if data is not None else {}
        self.lock = threading.RLock()

    def collection(self, name):
        return FakeCollection(self, name)

    def run_transaction(self, fn):
        with self.lock:
            return fn(FakeTxn(self))


class FakeSecretResponse:
    def __init__(self, data):
        self.payload = type("Payload", (), {"data": data})()


class FakeSecretManager:
    def __init__(self, values):
        self.values = dict(values)

    def access_secret_version(self, request):
        name = request["name"]
        if name not in self.values:
            raise Exception("NotFound 404")
        value = self.values[name]
        if isinstance(value, Exception):
            raise value
        return FakeSecretResponse(value)


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.calls = []
        FakeSMTP.instances.append(self)

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, context=None):
        if context is None:
            raise AssertionError("STARTTLS requires a TLS context")
        self.calls.append("starttls")
        return (220, b"ready")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.calls.append(("send", message))

    def quit(self):
        self.calls.append("quit")


class FakeSMTPSSL(FakeSMTP):
    def starttls(self, context=None):
        raise AssertionError("port 465 must not call STARTTLS")


class FakeSMTPModule:
    SMTP = FakeSMTP
    SMTP_SSL = FakeSMTPSSL
    SMTPAuthenticationError = smtplib.SMTPAuthenticationError
    SMTPException = smtplib.SMTPException
    SMTPConnectError = smtplib.SMTPConnectError
    SMTPServerDisconnected = smtplib.SMTPServerDisconnected


def _json_post(handler):
    def poster(url, payload, timeout):
        path = url.split(".example.com", 1)[-1]
        if "://" in path:
            path = "/" + path.split("/", 3)[-1]
        raw = json.dumps(payload).encode("utf-8")
        status, body, kind = handler(path, raw)
        if kind == "json":
            text = json.dumps(body)
        else:
            text = body if isinstance(body, str) else ""
        return status, text
    return poster


def _header(message, name):
    raw = message[name]
    if raw is None:
        return ""
    return str(make_header(decode_header(raw)))


def _mime_parts(message):
    parsed = email.message_from_bytes(bytes(message))
    pdf = None
    filename = ""
    for part in parsed.walk():
        if part.get_content_type() == "application/pdf":
            pdf = part.get_payload(decode=True)
            filename = part.get_filename() or ""
    return parsed, pdf, filename


class TimesheetSendHttpTests(unittest.TestCase):
    def setUp(self):
        FakeSMTP.instances = []

    def test_send_button_source_calls_backend_submit(self):
        tree = ast.parse(APP.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "show_timesheet_email_section")
        source = ast.get_source_segment(APP.read_text(), fn)
        self.assertIn("send_clicked = st.button", source)
        self.assertIn("if send_clicked and can_send and pdf_bytes:", source)
        self.assertIn("submit_signed_timesheet_send", source)
        self.assertIn("apply_timesheet_send_result", source)
        self.assertNotIn("mailto:", source)
        self.assertNotIn("st.text_input(\"Mail password\"", source)
        self.assertNotIn("app password", source.lower())

    def test_dockerfile_is_non_root_and_does_not_bake_serve_flag(self):
        text = DOCKERFILE.read_text()
        requirements = CALLBACK_REQUIREMENTS.read_text()
        self.assertIn("USER appuser", text)
        self.assertIn("useradd", text)
        self.assertNotIn("TIMESHEET_MAIL_ALLOW_SERVE=1", text)
        self.assertNotIn("client_secret", text)
        self.assertIn("TIMESHEET_MAIL_TOKEN_STORE=firestore", text)
        self.assertIn("--min-instances=0 --max-instances=2", text)
        self.assertIn("requests", requirements)
        self.assertIn("google-cloud-firestore", requirements)
        self.assertIn("google-cloud-secret-manager", requirements)
        self.assertIn("callback.serve()", text)

    def test_missing_firestore_project_fails_closed(self):
        with self.assertRaises(SystemExit) as raised:
            cb.build_mail_token_store({})
        self.assertIn("GOOGLE_CLOUD_PROJECT", str(raised.exception))
        with self.assertRaises(SystemExit):
            cb.serve(secrets=_secrets(), environ={})
        memory = cb.build_mail_token_store({"TIMESHEET_MAIL_TOKEN_STORE": "memory"})
        self.assertIsInstance(memory, tm.MemoryMailTokenStore)
        bare = _secrets()
        bare["timesheet_smtp"] = {"configured": True}
        self.assertIsNone(cb.build_smtp_passwords(bare, {}))
        self.assertEqual(cb.build_smtp_passwords(_secrets(), {}).project, "cvh-test")

    def test_preview_send_over_http_attaches_pdf_with_from_to_subject(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        posted = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            posted.append({"url": url, "headers": headers, "json": json})
            return 200, '{"id":"gm-1"}'

        server = HTTPServer(("127.0.0.1", 0), cb.CallbackHandler)
        server.secrets = secrets
        server.store = store
        server.http_post = gmail_post
        server.smtp_passwords = None
        server.smtp_mailer = None
        server.app_base_fallback = "https://cvhapp.example.com/"
        server.log_lines = []
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            runtime = json.loads(json.dumps(secrets))
            runtime["timesheet_mail_backend"]["public_base_url"] = "http://127.0.0.1:%s" % port
            record = _record()
            pdf = _pdf()

            def client_post(url, payload, timeout):
                raw = json.dumps(payload).encode("utf-8")
                request = Request(url, data=raw, method="POST")
                request.add_header("Content-Type", "application/json")
                try:
                    with urlopen(request, timeout=timeout) as response:
                        return response.status, response.read().decode("utf-8")
                except HTTPError as exc:
                    return exc.code, exc.read().decode("utf-8")

            result = tm.submit_signed_timesheet_send(
                record,
                pdf,
                "Gary_Grant_2026-11-08.pdf",
                secrets=runtime,
                signin_email="gary.signin@example.com",
                user_employee="Gary Grant",
                preview_pdf_bytes=pdf,
                initials_match=True,
                saved_content_hash=record["Content Hash"],
                http_post=client_post,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(result["to"], "patti@centralvalleyheli.com")
        self.assertEqual(result["from"], "gary.mail@example.com")
        self.assertEqual(len(posted), 1)
        self.assertTrue(posted[0]["url"].startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/send"))
        self.assertEqual(posted[0]["headers"]["Authorization"], "Bearer gary-access-token")
        raw = base64.urlsafe_b64decode(posted[0]["json"]["raw"] + "==")
        parsed, attached, filename = _mime_parts(email.message_from_bytes(raw))
        self.assertEqual(_header(parsed, "To"), "patti@centralvalleyheli.com")
        self.assertEqual(_header(parsed, "From"), "gary.mail@example.com")
        self.assertEqual(_header(parsed, "Subject"), tm.timesheet_email_subject(record))
        self.assertEqual(filename, "Gary_Grant_2026-11-08.pdf")
        self.assertEqual(attached, pdf)
        self.assertNotIn("gary-access-token", result.get("error", ""))
        self.assertNotIn("gary-access-token", " ".join(server.log_lines))
        self.assertNotIn("access_token", json.dumps(result))

    def test_cross_user_stale_initials_and_altered_pdf_do_not_send(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        store.put_access("Carl Mulvaney", "icloud", "carl.mail@example.com", "should-not-be-used")
        calls = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            calls.append(url)
            return 200, "{}"

        def backend(path, raw):
            return cb.route_request(
                "POST", path, body_bytes=raw, secrets=secrets, store=store, http_post=gmail_post,
            )

        record = _record()
        pdf = _pdf()
        poster = _json_post(lambda path, raw: backend(path, raw))
        cross = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets, signin_email="gary.signin@example.com",
            user_employee="Carl Mulvaney", initials_match=True, saved_content_hash=record["Content Hash"],
            http_post=poster,
        )
        self.assertEqual(cross["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("own initialed", cross["error"])
        stale = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets, signin_email="gary.signin@example.com",
            user_employee="Gary Grant", initials_match=False, saved_content_hash="old-hash",
            http_post=poster,
        )
        self.assertEqual(stale["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("Initial and save", stale["error"])
        altered_preview = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets, signin_email="gary.signin@example.com",
            user_employee="Gary Grant", initials_match=True, preview_pdf_bytes=b"%PDF-1.4 other",
            saved_content_hash=record["Content Hash"], http_post=poster,
        )
        self.assertIn("preview", altered_preview["error"].lower())
        signed = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "entry_id": record["Entry ID"],
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "acknowledge_uncertain": False,
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets))
        tampered = json.dumps({
            "token": signed,
            "pdf_base64": base64.b64encode(b"%PDF-1.4 tampered").decode("ascii"),
        }).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=tampered, secrets=secrets, store=store, http_post=gmail_post,
        )
        self.assertEqual(status, 403)
        self.assertIn("preview", payload["error"].lower())
        mismatched_identity = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Barry Markham",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets))
        body = json.dumps({"token": mismatched_identity, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=body, secrets=secrets, store=store, http_post=gmail_post,
        )
        self.assertEqual(status, 403)
        self.assertIn("own initialed", payload["error"])
        stale_signed = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": "different-saved-hash",
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets))
        body = json.dumps({"token": stale_signed, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=body, secrets=secrets, store=store, http_post=gmail_post,
        )
        self.assertEqual(status, 403)
        self.assertIn("Initial and save", payload["error"])
        self.assertEqual(calls, [])

    def test_replay_expiry_and_public_routes_are_not_a_relay(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        calls = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            calls.append(1)
            return 200, "{}"

        record = _record()
        pdf = _pdf()
        signed = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets), now=1_000)
        body = json.dumps({"token": signed, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        first, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=body, secrets=secrets, store=store,
            http_post=gmail_post, now=1_001,
        )
        second, replayed, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=body, secrets=secrets, store=store,
            http_post=gmail_post, now=1_002,
        )
        self.assertEqual(first, 200)
        self.assertEqual(payload["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(second, 401)
        self.assertIn("already used", replayed["error"])
        self.assertEqual(calls, [1])
        expired = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "signin_email": "gary.signin@example.com",
            "week": "2026-11-15",
            "content_hash": "hash-other",
            "saved_content_hash": "hash-other",
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets), now=1_000)
        expired_body = json.dumps({"token": expired, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=expired_body, secrets=secrets, store=store,
            http_post=gmail_post, now=1_000 + tm.TIMESHEET_MAIL_API_TTL_SEC + 5,
        )
        self.assertEqual(status, 401)
        self.assertIn("expired", payload["error"])
        self.assertEqual(calls, [1])
        for method, path, body_bytes in (
            ("GET", "/timesheet-mail/send", None),
            ("POST", "/timesheet-mail/callback/gmail", body),
            ("GET", "/timesheet-mail/callback/gmail", None),
            ("POST", "/timesheet-mail/start", body),
        ):
            status, _payload, _kind = cb.route_request(
                method, path, query={"code": "auth-code", "state": "nope"},
                body_bytes=body_bytes, secrets=secrets, store=store, http_post=gmail_post,
            )
            self.assertNotEqual(status, 200)
        self.assertEqual(calls, [1])
        status, payload, kind = cb.route_request("GET", "/healthz", secrets=None, store=store)
        self.assertEqual((status, payload, kind), (200, "ok", "text"))

    def test_audit_and_atomic_idempotency_block_duplicates_and_uncertain(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        calls = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            calls.append(1)
            return 200, "{}"

        record = _record()
        pdf = _pdf()
        sent_audit = [{
            "Employee": "Gary Grant",
            "Week Of": record["Week Of"],
            "Content Hash": record["Content Hash"],
            "Status": tm.TIMESHEET_MAIL_STATUS_SENT,
            "Idempotency Key": tm.timesheet_send_idempotency_key(record),
        }]

        def backend(path, raw):
            return cb.route_request(
                "POST", path, body_bytes=raw, secrets=secrets, store=store, http_post=gmail_post,
            )

        blocked = tm.submit_signed_timesheet_send(
            record, pdf, "a.pdf", secrets=secrets, signin_email="gary.signin@example.com",
            user_employee="Gary Grant", initials_match=True, saved_content_hash=record["Content Hash"],
            audit_records=sent_audit, http_post=_json_post(backend),
        )
        self.assertEqual(blocked["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("already sent", blocked["error"])
        self.assertEqual(calls, [])

        fresh = tm.MemoryMailTokenStore()
        fresh.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        entered = threading.Event()

        def slow_post(url, headers=None, json=None, timeout=30):
            calls.append(1)
            entered.set()
            time.sleep(0.2)
            return 200, "{}"

        results = []

        def send():
            results.append(tm.execute_timesheet_send(
                record, store=fresh, pdf_bytes=pdf, filename="a.pdf", secrets=secrets,
                user_employee="Gary Grant", initials_match=True, access_allowed=True, http_post=slow_post,
            ))

        first = threading.Thread(target=send)
        second = threading.Thread(target=send)
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        first.join(3)
        second.join(3)
        self.assertEqual(calls, [1])
        statuses = sorted(item["status"] for item in results)
        self.assertEqual(statuses, [tm.TIMESHEET_MAIL_STATUS_DUPLICATE, tm.TIMESHEET_MAIL_STATUS_SENT])

    def test_timeout_is_uncertain_and_not_retried(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        calls = {"n": 0}

        def boom(url, headers=None, json=None, timeout=30):
            calls["n"] += 1
            raise TimeoutError("provider timed out bearer gary-access-token")

        record = _record()
        first = tm.execute_timesheet_send(
            record, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Gary Grant", initials_match=True, access_allowed=True, http_post=boom,
        )
        self.assertEqual(first["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        self.assertNotIn("gary-access-token", first["error"])
        second = tm.execute_timesheet_send(
            record, store=store, pdf_bytes=_pdf(), filename="a.pdf", secrets=secrets,
            user_employee="Gary Grant", initials_match=True, access_allowed=True, http_post=boom,
        )
        self.assertEqual(second["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("will not retry automatically", second["error"])
        self.assertEqual(calls["n"], 1)
        client_calls = {"n": 0}

        def client_timeout(url, payload, timeout):
            client_calls["n"] += 1
            raise TimeoutError("streamlit to backend timed out")

        other = _record(hours="9")
        other["Content Hash"] = "hash-Gary Grant-9"
        result = tm.submit_signed_timesheet_send(
            other, _pdf(), "a.pdf", secrets=secrets, signin_email="gary.signin@example.com",
            user_employee="Gary Grant", initials_match=True, saved_content_hash=other["Content Hash"],
            http_post=client_timeout,
        )
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        self.assertEqual(client_calls["n"], 1)
        self.assertIn("will not retry automatically", result["error"])

    def test_revoked_secret_provider_outage_and_smtp_tls(self):
        secrets = _secrets()
        record = _record("Carl Mulvaney", initials="CM")
        pdf = _pdf(b"carl")
        passwords = tm.SecretManagerAppPasswords(project="cvh-test", client=FakeSecretManager({
            "projects/cvh-test/secrets/timesheet-smtp-carl-mulvaney/versions/latest": b"carl-app-password",
            "projects/cvh-test/secrets/timesheet-smtp-skylar-fingerle/versions/latest": Exception("PermissionDenied 403"),
        }))
        self.assertEqual(
            passwords.secret_version_name("Carl Mulvaney"),
            "projects/cvh-test/secrets/timesheet-smtp-carl-mulvaney/versions/latest",
        )
        self.assertNotIn("@", passwords.secret_version_name("Carl Mulvaney"))
        self.assertNotIn("carl-app-password", passwords.secret_version_name("Carl Mulvaney"))
        store = tm.MemoryMailTokenStore()
        store.put_smtp_session("Carl Mulvaney", "icloud", "carl.mail@example.com")
        mail_calls = []

        def record_mail(spec, username, password, message):
            mail_calls.append((spec, username, password, message))

        sent = tm.execute_timesheet_send(
            record, store=store, pdf_bytes=pdf, filename="Carl_Mulvaney_2026-11-08.pdf",
            secrets=secrets, user_employee="Carl Mulvaney", initials_match=True, access_allowed=True,
            smtp_password=passwords.get_password, smtp_mailer=record_mail,
        )
        self.assertEqual(sent["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(mail_calls[0][0]["host"], "smtp.mail.me.com")
        self.assertEqual(mail_calls[0][0]["port"], 587)
        self.assertEqual(mail_calls[0][0]["security"], "starttls")
        self.assertEqual(mail_calls[0][1], "carl.mail@example.com")
        self.assertEqual(mail_calls[0][2], "carl-app-password")
        parsed, attached, filename = _mime_parts(mail_calls[0][3])
        self.assertEqual(_header(parsed, "From"), "carl.mail@example.com")
        self.assertEqual(_header(parsed, "To"), "patti@centralvalleyheli.com")
        self.assertEqual(_header(parsed, "Subject"), tm.timesheet_email_subject(record))
        self.assertEqual(attached, pdf)
        self.assertEqual(filename, "Carl_Mulvaney_2026-11-08.pdf")
        self.assertNotIn("carl-app-password", json.dumps({k: v for k, v in sent.items()}))

        skylar = _record("Skylar Fingerle", initials="SF")
        skylar_store = tm.MemoryMailTokenStore()
        skylar_store.put_smtp_session("Skylar Fingerle", "icloud", "skylar.mail@example.com")
        revoked_calls = []
        revoked = tm.execute_timesheet_send(
            skylar, store=skylar_store, pdf_bytes=pdf, filename="a.pdf", secrets=secrets,
            user_employee="Skylar Fingerle", initials_match=True, access_allowed=True,
            smtp_password=passwords.get_password, smtp_mailer=lambda *args: revoked_calls.append(1),
        )
        self.assertEqual(revoked["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("missing or revoked", revoked["error"])
        self.assertNotIn("PermissionDenied", revoked["error"])
        self.assertEqual(revoked_calls, [])

        missing = tm.SecretManagerAppPasswords(project="cvh-test", client=FakeSecretManager({}))
        barry = _record("Barry Markham", initials="BM")
        barry_store = tm.MemoryMailTokenStore()
        barry_store.put_smtp_session("Barry Markham", "yahoo", "barry.mail@example.com")
        missing_calls = []
        missing_result = tm.execute_timesheet_send(
            barry, store=barry_store, pdf_bytes=pdf, filename="a.pdf", secrets=secrets,
            user_employee="Barry Markham", initials_match=True, access_allowed=True,
            smtp_password=missing.get_password, smtp_mailer=lambda *args: missing_calls.append(1),
        )
        self.assertEqual(missing_result["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("missing or revoked", missing_result["error"])
        self.assertEqual(missing_calls, [])

        spec = tm.timesheet_smtp_connection_spec("icloud")
        message = tm.build_timesheet_mime(record, pdf, "a.pdf", "carl.mail@example.com", secrets=secrets)
        tm._smtp_deliver(spec, "carl.mail@example.com", "carl-app-password", message, smtp_module=FakeSMTPModule)
        icloud = FakeSMTP.instances[-1]
        self.assertEqual(icloud.host, "smtp.mail.me.com")
        self.assertEqual(icloud.port, 587)
        self.assertIn("starttls", icloud.calls)
        self.assertIn(("login", "carl.mail@example.com", "carl-app-password"), icloud.calls)
        yahoo_secrets = json.loads(json.dumps(secrets))
        yahoo_secrets["timesheet_smtp"]["yahoo_port"] = 465
        yahoo_spec = tm.timesheet_smtp_connection_spec("yahoo", yahoo_secrets)
        self.assertEqual(yahoo_spec["port"], 465)
        self.assertEqual(yahoo_spec["security"], "ssl")
        tm._smtp_deliver(yahoo_spec, "barry.mail@example.com", "barry-app-password", message, smtp_module=FakeSMTPModule)
        yahoo = FakeSMTP.instances[-1]
        self.assertIsInstance(yahoo, FakeSMTPSSL)
        self.assertEqual(yahoo.host, "smtp.mail.yahoo.com")
        self.assertEqual(yahoo.port, 465)
        self.assertNotIn("starttls", yahoo.calls)
        with self.assertRaises(tm.MailProviderDown):
            tm._smtp_deliver(
                {"host": "smtp.evil.example", "port": 587, "security": "starttls"},
                "carl.mail@example.com", "pw", message, smtp_module=FakeSMTPModule,
            )

        outage_store = tm.MemoryMailTokenStore()
        outage_store.put_access("Robert Rackley", "gmail", "robert.mail@example.com", "robert-token")
        outage_calls = {"n": 0}

        def outage(url, headers=None, json=None, timeout=30):
            outage_calls["n"] += 1
            return 503, "unavailable"

        robert = _record("Robert Rackley", initials="RR")
        outage_result = tm.execute_timesheet_send(
            robert, store=outage_store, pdf_bytes=pdf, filename="a.pdf", secrets=secrets,
            user_employee="Robert Rackley", initials_match=True, access_allowed=True, http_post=outage,
        )
        self.assertEqual(outage_result["status"], tm.TIMESHEET_MAIL_STATUS_UNCERTAIN)
        again = tm.execute_timesheet_send(
            robert, store=outage_store, pdf_bytes=pdf, filename="a.pdf", secrets=secrets,
            user_employee="Robert Rackley", initials_match=True, access_allowed=True, http_post=outage,
        )
        self.assertEqual(again["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertEqual(outage_calls["n"], 1)

    def test_firestore_store_survives_restart_and_redeem_is_single_use(self):
        data = {}
        first = tm.FirestoreMailTokenStore(project="cvh-test", client=FakeFirestore(data))
        first.put_pending("nonce-1", {"employee": "Anthony Root", "provider": "gmail", "verifier": "pkce-verifier"})
        first.put_access("Anthony Root", "gmail", "anthony.mail@example.com", "anthony-token", expires_in=600)
        ticket = first.issue_ticket("Anthony Root")
        self.assertTrue(first.remember_nonce("api-nonce", time.time() + 60))
        second = tm.FirestoreMailTokenStore(project="cvh-test", client=FakeFirestore(data))
        self.assertEqual(second.get_access("Anthony Root")["access_token"], "anthony-token")
        pending = second.pop_pending("nonce-1")
        self.assertEqual(pending["verifier"], "pkce-verifier")
        third = tm.FirestoreMailTokenStore(project="cvh-test", client=FakeFirestore(data))
        self.assertIsNone(third.pop_pending("nonce-1"))
        self.assertFalse(third.remember_nonce("api-nonce", time.time() + 60))
        meta = third.redeem_ticket(ticket)
        self.assertEqual(meta["mailbox_email"], "anthony.mail@example.com")
        self.assertNotIn("access_token", meta)
        self.assertIsNone(tm.FirestoreMailTokenStore(project="cvh-test", client=FakeFirestore(data)).redeem_ticket(ticket))
        record = _record("Anthony Root", initials="AR")
        pdf = _pdf(b"anthony")
        calls = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            calls.append(headers["Authorization"])
            return 200, "{}"

        sent = tm.execute_timesheet_send(
            record, store=third, pdf_bytes=pdf, filename="a.pdf", secrets=_secrets(),
            user_employee="Anthony Root", initials_match=True, access_allowed=True, http_post=gmail_post,
        )
        self.assertEqual(sent["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        restarted = tm.FirestoreMailTokenStore(project="cvh-test", client=FakeFirestore(data))
        duplicate = tm.execute_timesheet_send(
            record, store=restarted, pdf_bytes=pdf, filename="a.pdf", secrets=_secrets(),
            user_employee="Anthony Root", initials_match=True, access_allowed=True, http_post=gmail_post,
        )
        self.assertEqual(duplicate["status"], tm.TIMESHEET_MAIL_STATUS_DENIED)
        self.assertIn("already sent", duplicate["error"])
        self.assertEqual(calls, ["Bearer anthony-token"])

    def test_redeem_returns_metadata_only_and_missing_config_does_not_send(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        ticket = store.issue_ticket("Gary Grant")
        calls = []
        status, payload, kind = cb.route_request(
            "POST", "/timesheet-mail/redeem",
            body_bytes=json.dumps({"token": tm.timesheet_sign_api_request({
                "kind": "redeem",
                "ticket": ticket,
                "employee": "Gary Grant",
                "signin_email": "gary.signin@example.com",
            }, tm.timesheet_mail_state_secret(secrets))}).encode("utf-8"),
            secrets=secrets, store=store, http_post=lambda *args, **kwargs: calls.append(1),
        )
        self.assertEqual(status, 200)
        self.assertEqual(kind, "json")
        self.assertEqual(payload["consent"]["mailbox_email"], "gary.mail@example.com")
        self.assertNotIn("access_token", json.dumps(payload))
        self.assertNotIn("gary-access-token", json.dumps(payload))
        again, _payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/redeem",
            body_bytes=json.dumps({"token": tm.timesheet_sign_api_request({
                "kind": "redeem",
                "ticket": ticket,
                "employee": "Gary Grant",
                "signin_email": "gary.signin@example.com",
            }, tm.timesheet_mail_state_secret(secrets))}).encode("utf-8"),
            secrets=secrets, store=store,
        )
        self.assertEqual(again, 400)
        self.assertEqual(calls, [])
        disabled = json.loads(json.dumps(secrets))
        disabled["timesheet_mail"]["enabled"] = False
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send",
            body_bytes=b'{"token":"x","pdf_base64":"JVBERi0="}',
            secrets=disabled, store=store, http_post=lambda *args, **kwargs: calls.append(1),
        )
        self.assertEqual(status, 503)
        self.assertIn("does not send mail", payload["error"])
        self.assertFalse(tm.timesheet_mail_flag_enabled({}))
        self.assertEqual(calls, [])

    def test_smtp_session_and_http_send_use_secret_manager_not_a_form(self):
        secrets = _secrets()
        store = tm.MemoryMailTokenStore()
        passwords = tm.SecretManagerAppPasswords(project="cvh-test", client=FakeSecretManager({
            "projects/cvh-test/secrets/timesheet-smtp-barry-markham/versions/latest": b"barry-app-password",
        }))
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/smtp-session",
            body_bytes=json.dumps({"token": tm.timesheet_sign_api_request({
                "kind": "smtp-session",
                "employee": "Barry Markham",
                "signin_email": "barry.signin@example.com",
            }, tm.timesheet_mail_state_secret(secrets))}).encode("utf-8"),
            secrets=secrets, store=store, smtp_passwords=passwords,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["consent"]["provider"], "yahoo")
        self.assertNotIn("barry-app-password", json.dumps(payload))
        self.assertNotIn("password", payload["consent"])
        captured = []

        def mailer(spec, username, password, message):
            captured.append((spec, username, password, message))

        record = _record("Barry Markham", initials="BM")
        pdf = _pdf(b"barry")
        result = tm.submit_signed_timesheet_send(
            record, pdf, "Barry_Markham_2026-11-08.pdf", secrets=secrets,
            signin_email="barry.signin@example.com", user_employee="Barry Markham",
            initials_match=True, saved_content_hash=record["Content Hash"],
            http_post=_json_post(lambda path, raw: cb.route_request(
                "POST", path, body_bytes=raw, secrets=secrets, store=store,
                smtp_passwords=passwords, smtp_mailer=mailer,
            )),
        )
        self.assertEqual(result["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(captured[0][0]["host"], "smtp.mail.yahoo.com")
        self.assertEqual(captured[0][0]["port"], 587)
        self.assertEqual(captured[0][2], "barry-app-password")
        parsed, attached, filename = _mime_parts(captured[0][3])
        self.assertEqual(_header(parsed, "From"), "barry.mail@example.com")
        self.assertEqual(_header(parsed, "To"), "patti@centralvalleyheli.com")
        self.assertEqual(_header(parsed, "Subject"), tm.timesheet_email_subject(record))
        self.assertEqual(attached, pdf)
        self.assertEqual(filename, "Barry_Markham_2026-11-08.pdf")
        self.assertNotIn("barry-app-password", json.dumps(result))
        detail = tm.scrub_audit_detail("login failed access_token=abcd for barry.mail@example.com")
        self.assertNotIn("barry.mail@example.com", detail)
        self.assertNotIn("abcd", detail)

    def test_employee_key_is_the_send_identity_and_legacy_email_still_verifies(self):
        secrets = _secrets()
        secrets.pop("timesheet_employees", None)
        store = tm.MemoryMailTokenStore()
        store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        record = _record()
        pdf = _pdf()
        calls = []

        def gmail_post(url, headers=None, json=None, timeout=30):
            calls.append(1)
            return 200, "{}"

        signed = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "employee_key": "Gary Grant",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(secrets))
        body = json.dumps({"token": signed, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=body, secrets=secrets, store=store, http_post=gmail_post,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(calls, [1])
        self.assertNotIn("signin_email", tm.timesheet_verify_state(signed, tm.timesheet_mail_state_secret(secrets)))

        mixed = _secrets()
        store2 = tm.MemoryMailTokenStore()
        store2.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        bad = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "employee_key": "Carl Mulvaney",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(mixed))
        bad_body = json.dumps({"token": bad, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=bad_body, secrets=mixed, store=store2, http_post=gmail_post,
        )
        self.assertEqual(status, 403)
        self.assertIn("own initialed", payload["error"])
        self.assertEqual(calls, [1])

        legacy_store = tm.MemoryMailTokenStore()
        legacy_store.put_access("Gary Grant", "gmail", "gary.mail@example.com", "gary-access-token")
        legacy = tm.timesheet_sign_api_request({
            "kind": "send",
            "employee": "Gary Grant",
            "signin_email": "gary.signin@example.com",
            "week": record["Week Of"],
            "content_hash": record["Content Hash"],
            "saved_content_hash": record["Content Hash"],
            "initials": "GG",
            "initials_match": True,
            "filename": "a.pdf",
            "pdf_sha256": tm.timesheet_pdf_sha256(pdf),
            "preview_sha256": tm.timesheet_pdf_sha256(pdf),
            "audit": [],
        }, tm.timesheet_mail_state_secret(mixed))
        legacy_body = json.dumps({"token": legacy, "pdf_base64": base64.b64encode(pdf).decode("ascii")}).encode("utf-8")
        status, payload, _kind = cb.route_request(
            "POST", "/timesheet-mail/send", body_bytes=legacy_body, secrets=mixed, store=legacy_store, http_post=gmail_post,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], tm.TIMESHEET_MAIL_STATUS_SENT)
        self.assertEqual(calls, [1, 1])


if __name__ == "__main__":
    unittest.main()
