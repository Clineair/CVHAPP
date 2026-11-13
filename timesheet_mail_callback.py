"""Standalone HTTPS callback service for timesheet mail OAuth and send.

This is not started by the Streamlit app and is not a Streamlit route.
Deploy it on its own HTTPS host, register its redirect URI on the Gmail
send client (and a Microsoft client only if a later mailbox needs one),
and point [timesheet_mail_backend] at it.

Official flow: authorization-code + PKCE + signed state. The callback
exchanges the code on this host, stores only a short-lived access token
in the shared store, and redirects back to the Streamlit app without the
authorization code or any access token in the query string.

Streamlit redeems the opaque ticket and sends the previewed PDF with a
short-lived HMAC request. Those POST routes are the only send path.
The public OAuth routes do not accept a message and are not a mail relay.

Do not use Streamlit's reserved /oauth2callback path. Do not persist
tokens in Sheets or the repo.
"""
from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, HTTPServer

import timesheet_mail as tm

# Fallback for tests and an explicit memory override. Production serve()
# builds a Firestore store and does not use this process-local object.
STORE = tm.MemoryMailTokenStore()
POST_API_PATHS = (
    "/timesheet-mail/redeem",
    "/timesheet-mail/send",
    "/timesheet-mail/smtp-session",
)
MAX_REQUEST_BYTES = 8_000_000


def backend_public_base(secrets):
    section = tm.timesheet_secret_section(secrets, tm.TIMESHEET_MAIL_BACKEND_SECTION)
    if not section or "public_base_url" not in section:
        return ""
    return tm._cell(section["public_base_url"]).rstrip("/")


def handle_start(secrets, start_token, store=None):
    state = tm.timesheet_verify_state(start_token, tm.timesheet_mail_state_secret(secrets))
    if not state or state.get("kind") != "start":
        return 400, "", "invalid_start"
    url = start_authorization(
        secrets, state.get("employee"), state.get("provider"), state.get("return"), store=store,
    )
    return 302, url, "ok"


def start_authorization(secrets, employee, provider, app_return, store=None):

    """Create a pending PKCE session and return the provider authorize URL."""
    provider = tm._cell(provider).lower()
    mailbox = tm.timesheet_mailbox_for_employee(employee, secrets)
    if not mailbox or mailbox["provider"] != provider:
        raise ValueError("No mailbox provider is configured for this employee.")
    if not tm.timesheet_mail_provider_configured(provider, secrets):
        raise ValueError("The %s mail client is not configured." % provider)
    secret = tm.timesheet_mail_state_secret(secrets)
    nonce = __import__("secrets").token_urlsafe(24)
    verifier, challenge = tm.timesheet_pkce_pair()
    payload = {
        "n": nonce,
        "employee": tm._cell(employee),
        "provider": provider,
        "return": tm._cell(app_return).split("?")[0],
    }
    state = tm.timesheet_sign_state(payload, secret)
    (store or STORE).put_pending(nonce, {
        "employee": tm._cell(employee),
        "provider": provider,
        "verifier": verifier,
        "return": payload["return"],
    })
    return tm.timesheet_authorize_url(
        provider, state, challenge, secrets=secrets, login_hint=mailbox["email"],
    )


def handle_provider_callback(secrets, query, userinfo_fetch, token_fetch, store=None, app_base_fallback=""):
    """Exchange a provider callback (code+state) and redirect to the app without tokens.

    query is a dict of GET parameters from the official redirect_uri.
    token_fetch(payload) should POST the official token endpoint and return a dict.
    userinfo_fetch(url, access_token) should GET the official userinfo endpoint.
    """
    store = store or STORE
    params = query if isinstance(query, dict) else {}
    if params.get("error"):
        return 302, tm.app_return_url(app_base_fallback), "provider_denied"
    state = tm.timesheet_verify_state(params.get("state"), tm.timesheet_mail_state_secret(secrets))
    if not state:
        return 400, "", "invalid_state"
    pending = store.pop_pending(state.get("n"))
    if not pending:
        return 400, "", "expired_or_replayed_state"
    if pending.get("employee") != state.get("employee") or pending.get("provider") != state.get("provider"):
        return 400, "", "state_mismatch"
    code = tm._cell(params.get("code"))
    if not code:
        return 400, "", "missing_code"
    # The authorization code is used here on the callback host only.
    payload = tm.timesheet_token_exchange_payload(pending["provider"], code, pending["verifier"], secrets)
    token_response = token_fetch(payload)
    access = (token_response or {}).get("access_token")
    if not access:
        return 400, "", "token_exchange_failed"
    urls = tm.timesheet_provider_urls(pending["provider"], secrets)
    userinfo = userinfo_fetch(urls["userinfo_url"], access)
    consent, error = tm.bind_consented_mailbox(store, pending, token_response, userinfo, secrets=secrets)
    if not consent:
        return 400, "", error or "bind_failed"
    return_to = pending.get("return") or app_base_fallback
    ticket = store.issue_ticket(pending["employee"])
    return 302, tm.app_return_url(return_to, ticket=ticket), "ok"


def redeem_or_send(store, ticket=None, employee=None, send_kwargs=None):
    """Redeem a one-time ready ticket (metadata only) or send via the store."""
    if ticket:
        meta = store.redeem_ticket(ticket)
        return meta
    if send_kwargs is not None:
        return tm.execute_timesheet_send(store=store, **send_kwargs)
    if employee:
        return store.consent_metadata(employee)
    return None


HTTP_TIMEOUT_SEC = 15


def secrets_from_env(environ=None):
    """Load callback secrets from TIMESHEET_MAIL_SECRETS_JSON only. Never logs values."""
    source = environ if environ is not None else os.environ
    raw = source.get("TIMESHEET_MAIL_SECRETS_JSON") or ""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def official_http_token_fetch(payload):
    """POST the official token endpoint. Returns a dict. Does not log the body."""
    if not payload or not payload.get("url") or not payload.get("data"):
        return {}
    body = urlencode(payload["data"]).encode("utf-8")
    request = Request(payload["url"], data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def build_mail_token_store(environ=None, client=None):
    """Firestore by default so Cloud Run instances share short-lived mail state.

    TIMESHEET_MAIL_TOKEN_STORE=memory is only for tests. A missing project
    fails closed instead of silently keeping tokens in process RAM.
    """
    source = environ if environ is not None else os.environ
    kind = tm._cell(source.get("TIMESHEET_MAIL_TOKEN_STORE") or "firestore").lower()
    if kind == "memory":
        return tm.MemoryMailTokenStore()
    if kind != "firestore":
        raise SystemExit("TIMESHEET_MAIL_TOKEN_STORE must be firestore or memory.")
    project = tm._cell(source.get("GOOGLE_CLOUD_PROJECT") or source.get("TIMESHEET_MAIL_FIRESTORE_PROJECT"))
    if not project:
        raise SystemExit("Firestore token store requires GOOGLE_CLOUD_PROJECT.")
    return tm.FirestoreMailTokenStore(project=project, client=client)


def build_smtp_passwords(secrets, environ=None, client=None):
    """Secret Manager reader for SMTP app passwords. None when no project is configured."""
    source = environ if environ is not None else os.environ
    project = tm._cell(source.get("TIMESHEET_SMTP_SECRET_PROJECT") or source.get("GOOGLE_CLOUD_PROJECT"))
    section = tm.timesheet_secret_section(secrets, tm.TIMESHEET_SMTP_SECTION)
    prefix = None
    try:
        if section is not None and "project" in section:
            project = tm._cell(section["project"]) or project
        if section is not None and "prefix" in section:
            prefix = tm._cell(section["prefix"]) or None
    except Exception:
        pass
    if not project:
        return None
    return tm.SecretManagerAppPasswords(project=project, client=client, prefix=prefix)


def _json_ready(payload):
    """Drop anything that must never leave the callback host."""
    if not isinstance(payload, dict):
        return {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail request failed."}
    cleaned = dict(payload)
    for key in ("access_token", "refresh_token", "password", "pdf_base64", "client_secret", "verifier"):
        cleaned.pop(key, None)
    consent = cleaned.get("consent")
    if isinstance(consent, dict):
        consent = dict(consent)
        for key in ("access_token", "refresh_token", "password", "verifier"):
            consent.pop(key, None)
        cleaned["consent"] = consent
    return cleaned


def _read_json_body(body_bytes):
    if body_bytes is None:
        return None, (400, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail request was empty."})
    if len(body_bytes) > MAX_REQUEST_BYTES:
        return None, (413, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail request is too large."})
    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return None, (400, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail request was not valid JSON."})
    if not isinstance(body, dict):
        return None, (400, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail request was not valid JSON."})
    return body, None


def _authenticated_state(secrets, body, store, now=None):
    token = tm._cell((body or {}).get("token"))
    state = tm.timesheet_verify_state(token, tm.timesheet_mail_state_secret(secrets), now=now)
    if not state or not state.get("nonce"):
        return None, (401, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The mail request is invalid or expired.",
        })
    if store is None or not store.remember_nonce(state.get("nonce"), state.get("exp"), now=now):
        return None, (401, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "This mail request was already used.",
        })
    return state, None


def _require_same_employee(secrets, state):
    """Bind the HMAC payload to one employee.

    New Streamlit requests carry employee_key, the PIN-verified employee name.
    The HMAC check (state_secret via timesheet_verify_state) is unchanged.
    A payload that still has only signin_email is accepted so an older client
    keeps working after this callback is redeployed. The running Cloud Run
    revision from before this change does not read employee_key.
    """
    employee = tm._cell(state.get("employee"))
    employee_key = tm._cell(state.get("employee_key"))
    if employee_key:
        if employee and employee_key == employee and tm.timesheet_pin_employee_ok(employee):
            return employee, None
        return None, (403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Only the PIN-verified employee can send their own initialed time sheet. This app does not send mail for others.",
        })
    mapped = tm.timesheet_employee_for_signin_email(state.get("signin_email"), secrets)
    if not employee or not mapped or mapped != employee:
        return None, (403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Only the PIN-verified employee can send their own initialed time sheet. This app does not send mail for others.",
        })
    return employee, None


def _setup_or_closed(secrets):
    if tm.timesheet_mail_secure_setup_ready(secrets):
        return None
    return 503, {
        "ok": False,
        "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
        "error": "In-app sending is disabled until mail setup is complete. This app does not send mail yet.",
    }


def handle_redeem(secrets, body, store, now=None):
    """Return consent metadata for a one-time ticket. Never returns an access token."""
    closed = _setup_or_closed(secrets)
    if closed:
        return closed
    state, error = _authenticated_state(secrets, body, store, now=now)
    if error:
        return error
    if state.get("kind") != "redeem":
        return 403, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "The mail request is invalid or expired."}
    employee, error = _require_same_employee(secrets, state)
    if error:
        return error
    meta = store.redeem_ticket(state.get("ticket"))
    if not meta or tm._cell(meta.get("employee")) != employee:
        return 400, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The mail authorization ticket is expired or already used.",
        }
    meta.pop("access_token", None)
    meta.pop("password", None)
    return 200, {"ok": True, "consent": meta}


def handle_smtp_session(secrets, body, store, smtp_passwords=None, now=None):
    """Confirm a vaulted app password exists and record a password-free SMTP session."""
    closed = _setup_or_closed(secrets)
    if closed:
        return closed
    state, error = _authenticated_state(secrets, body, store, now=now)
    if error:
        return error
    if state.get("kind") != "smtp-session":
        return 403, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "The mail request is invalid or expired."}
    employee, error = _require_same_employee(secrets, state)
    if error:
        return error
    mailbox = tm.timesheet_mailbox_for_employee(employee, secrets)
    if not mailbox or tm.timesheet_mail_auth_mode(mailbox["provider"]) != "smtp_app_password":
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "This employee does not have a vaulted SMTP mailbox.",
        }
    if not tm.timesheet_smtp_store_configured(secrets):
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": tm.timesheet_smtp_setup_reason(mailbox["provider"]),
        }
    if smtp_passwords is None:
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The vaulted SMTP app password is missing or revoked.",
        }
    try:
        ready = smtp_passwords.exists(employee)
    except Exception:
        ready = False
    if not ready:
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The vaulted SMTP app password is missing or revoked.",
        }
    store.put_smtp_session(employee, mailbox["provider"], mailbox["email"])
    consent = store.consent_metadata(employee) or {}
    consent.pop("access_token", None)
    consent.pop("password", None)
    return 200, {"ok": True, "consent": consent}


def handle_send(secrets, body, store, http_post=None, smtp_passwords=None, smtp_mailer=None, now=None):
    """Authenticated send. Public OAuth routes must not call this."""
    closed = _setup_or_closed(secrets)
    if closed:
        return closed
    state, error = _authenticated_state(secrets, body, store, now=now)
    if error:
        return error
    if state.get("kind") != "send":
        return 403, {"ok": False, "status": tm.TIMESHEET_MAIL_STATUS_DENIED, "error": "The mail request is invalid or expired."}
    employee, error = _require_same_employee(secrets, state)
    if error:
        return error
    saved_hash = tm._cell(state.get("saved_content_hash"))
    content_hash = tm._cell(state.get("content_hash"))
    if not state.get("initials_match") or not saved_hash or saved_hash != content_hash or not tm._cell(state.get("initials")):
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Initial and save this week's current time-sheet content before sending.",
        }
    try:
        pdf = base64.b64decode(body.get("pdf_base64") or "", validate=True)
    except Exception:
        pdf = b""
    if not pdf or pdf[:5] != b"%PDF-" or len(pdf) > 6_000_000:
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The official generated timesheet PDF is required.",
        }
    digest = tm.timesheet_pdf_sha256(pdf)
    if digest != tm._cell(state.get("pdf_sha256")) or digest != tm._cell(state.get("preview_sha256")):
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The PDF no longer matches the preview.",
        }
    filename = tm._cell(state.get("filename"))
    if not filename.lower().endswith(".pdf"):
        return 403, {
            "ok": False,
            "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Only the generated timesheet PDF can be attached.",
        }
    record = {
        "Employee": employee,
        "Week Of": tm._cell(state.get("week")),
        "Content Hash": content_hash,
        "Initials": tm._cell(state.get("initials")),
        "Entry ID": tm._cell(state.get("entry_id")),
    }
    audit = state.get("audit") if isinstance(state.get("audit"), list) else []

    def password_lookup(name):
        if smtp_passwords is None:
            raise tm.SecretAccessError("not_found")
        return smtp_passwords.get_password(name)

    result = tm.execute_timesheet_send(
        record,
        store=store,
        pdf_bytes=pdf,
        filename=filename,
        secrets=secrets,
        user_employee=employee,
        initials_match=True,
        access_allowed=True,
        audit_records=audit,
        acknowledge_uncertain=bool(state.get("acknowledge_uncertain")),
        http_post=http_post,
        smtp_password=password_lookup,
        smtp_mailer=smtp_mailer,
    )
    status_name = result.get("status") or tm.TIMESHEET_MAIL_STATUS_UNCERTAIN
    http_status = 200
    if status_name == tm.TIMESHEET_MAIL_STATUS_DENIED:
        http_status = 403
    elif status_name == tm.TIMESHEET_MAIL_STATUS_DUPLICATE:
        http_status = 409
    return http_status, {
        "ok": status_name == tm.TIMESHEET_MAIL_STATUS_SENT,
        "status": status_name,
        "error": tm.scrub_audit_detail(result.get("error") or ""),
        "to": result.get("to") or tm.timesheet_mail_recipient(secrets),
        "from": result.get("from") or "",
        "provider": result.get("provider") or "",
        "idempotency_key": result.get("idempotency_key") or "",
    }


def route_request(method, path, query=None, body_bytes=None, secrets=None, store=None, http_post=None, smtp_passwords=None, smtp_mailer=None, userinfo_fetch=None, token_fetch=None, app_base_fallback="", now=None):
    """Dispatch one callback request. OAuth GET routes cannot send mail."""
    method = tm._cell(method).upper()
    path = urlparse(path or "/").path.rstrip("/") or "/"
    query = query or {}
    store = store or STORE
    if method == "GET" and path == "/healthz":
        return 200, "ok", "text"
    if not secrets:
        return 503, "callback secrets are not configured", "text"
    if path in POST_API_PATHS and method != "POST":
        return 405, "method_not_allowed", "text"
    if method == "POST":
        if path not in POST_API_PATHS:
            return 404, "not found", "text"
        body, error = _read_json_body(body_bytes if body_bytes is not None else b"")
        if error:
            status, payload = error
            return status, payload, "json"
        if path == "/timesheet-mail/redeem":
            status, payload = handle_redeem(secrets, body, store, now=now)
        elif path == "/timesheet-mail/smtp-session":
            status, payload = handle_smtp_session(secrets, body, store, smtp_passwords=smtp_passwords, now=now)
        else:
            status, payload = handle_send(
                secrets, body, store,
                http_post=http_post,
                smtp_passwords=smtp_passwords,
                smtp_mailer=smtp_mailer,
                now=now,
            )
        return status, _json_ready(payload), "json"
    if path == "/timesheet-mail/start":
        token = tm._cell(query.get("start") or query.get("token"))
        try:
            status, location, _msg = handle_start(secrets, token, store=store)
        except Exception:
            return 400, "invalid_start", "text"
        if status == 302 and location:
            return 302, location, "redirect"
        return status or 400, "invalid_start", "text"
    if path in ("/timesheet-mail/callback/gmail", "/timesheet-mail/callback/microsoft"):
        try:
            status, location, _msg = handle_provider_callback(
                secrets,
                query,
                userinfo_fetch or official_http_userinfo_fetch,
                token_fetch or official_http_token_fetch,
                store=store,
                app_base_fallback=app_base_fallback,
            )
        except Exception:
            return 400, "callback_failed", "text"
        if status == 302 and location:
            return 302, location, "redirect"
        return status or 400, "callback_failed", "text"
    return 404, "not found", "text"


def official_http_userinfo_fetch(url, access_token):
    """GET the official userinfo endpoint with the access token. Does not log it."""
    if not url or not access_token:
        return {}
    request = Request(url, method="GET")
    request.add_header("Authorization", "Bearer " + access_token)
    request.add_header("Accept", "application/json")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _first_query_value(params, key):
    values = params.get(key) or []
    if not values:
        return ""
    return values[0]


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTPS callback routes for start and provider redirects. Not a Streamlit route."""

    secrets = None
    store = None
    app_base_fallback = ""

    def log_message(self, format, *args):
        # Avoid writing query strings that may include temporary authorization codes.
        path = self.path.split("?")[0]
        if hasattr(self.server, "log_lines"):
            self.server.log_lines.append(path)

    def _redirect(self, location, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _text(self, status, body):
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status, payload):
        raw = json.dumps(_json_ready(payload)).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self, method, body_bytes=None):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        query = {key: _first_query_value(params, key) for key in params}
        secrets = self.secrets or getattr(self.server, "secrets", None) or secrets_from_env()
        store = self.store or getattr(self.server, "store", None) or STORE
        fallback = self.app_base_fallback or getattr(self.server, "app_base_fallback", "") or ""
        status, payload, kind = route_request(
            method,
            parsed.path,
            query=query,
            body_bytes=body_bytes,
            secrets=secrets,
            store=store,
            http_post=getattr(self.server, "http_post", None),
            smtp_passwords=getattr(self.server, "smtp_passwords", None),
            smtp_mailer=getattr(self.server, "smtp_mailer", None),
            app_base_fallback=fallback,
        )
        if kind == "redirect":
            self._redirect(payload, status=status)
            return
        if kind == "json":
            self._json(status, payload)
            return
        self._text(status, payload if isinstance(payload, str) else "error")

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._text(413, "Mail request is too large.")
            return
        body = self.rfile.read(length) if length else b""
        self._dispatch("POST", body)


# Backward-compatible name used by earlier local-scaffold notes.
_LocalHandler = CallbackHandler


def serve(secrets=None, host="0.0.0.0", port=None, store=None, environ=None, smtp_passwords=None, http_post=None, smtp_mailer=None):
    """Start the callback HTTP server. Call only on a dedicated HTTPS fronted host.

    The token store defaults to Firestore. Process memory is used only when
    TIMESHEET_MAIL_TOKEN_STORE=memory. SMTP passwords come from Secret Manager
    when a project id is configured.
    """
    source = environ if environ is not None else os.environ
    secrets = secrets or secrets_from_env(source)
    if not secrets:
        raise SystemExit("TIMESHEET_MAIL_SECRETS_JSON is missing or invalid.")
    if store is None:
        store = build_mail_token_store(source)
    if smtp_passwords is None:
        smtp_passwords = build_smtp_passwords(secrets, source)
    try:
        port = int(port if port is not None else source.get("PORT") or 8080)
    except (TypeError, ValueError):
        port = 8080
    server = HTTPServer((host, port), CallbackHandler)
    server.secrets = secrets
    server.store = store
    server.http_post = http_post
    server.smtp_passwords = smtp_passwords
    server.smtp_mailer = smtp_mailer
    server.app_base_fallback = backend_public_base(secrets)
    try:
        section = tm.timesheet_secret_section(secrets, tm.TIMESHEET_MAIL_BACKEND_SECTION)
        if section and "app_base_url" in section:
            server.app_base_fallback = tm._cell(section["app_base_url"]) or server.app_base_fallback
    except Exception:
        pass
    server.log_lines = []
    server.serve_forever()


def main(environ=None):
    source = environ if environ is not None else os.environ
    if source.get("TIMESHEET_MAIL_ALLOW_SERVE") == "1":
        serve(secrets=secrets_from_env(source), environ=source)
        return
    raise SystemExit(
        "Do not start this scaffold as production mail sending unless "
        "TIMESHEET_MAIL_ALLOW_SERVE=1 is set on a dedicated HTTPS host. "
        "Deploy timesheet_mail_callback with registered redirect URIs, then set "
        "[timesheet_mail_backend] in Streamlit secrets."
    )


if __name__ == "__main__":
    main()
