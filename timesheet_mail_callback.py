"""Standalone HTTPS callback service scaffold for timesheet mail OAuth.

This is not started by the Streamlit app and is not a Streamlit route.
Deploy it on its own HTTPS host, register its redirect URI on the Gmail
send client (and a Microsoft client only if a later mailbox needs one),
and point [timesheet_mail_backend] at it.

Official flow: authorization-code + PKCE + signed state. The callback
exchanges the code on this host, stores only a short-lived access token
in process memory, and redirects back to the Streamlit app without the
authorization code or any token in the query string.

Do not use Streamlit's reserved /oauth2callback path. Do not persist
tokens in Sheets or the repo. Do not run this as a general mail relay.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, HTTPServer

import timesheet_mail as tm

STORE = tm.MemoryMailTokenStore()


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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/healthz":
            self._text(200, "ok")
            return
        secrets = self.secrets or getattr(self.server, "secrets", None) or secrets_from_env()
        store = self.store or getattr(self.server, "store", None) or STORE
        fallback = self.app_base_fallback or getattr(self.server, "app_base_fallback", "") or ""
        if not secrets:
            self._text(503, "callback secrets are not configured")
            return
        params = parse_qs(parsed.query, keep_blank_values=True)
        if path == "/timesheet-mail/start":
            token = _first_query_value(params, "start") or _first_query_value(params, "token")
            try:
                status, location, _msg = handle_start(secrets, token, store=store)
            except Exception:
                self._text(400, "invalid_start")
                return
            if status == 302 and location:
                self._redirect(location)
                return
            self._text(status or 400, "invalid_start")
            return
        if path in ("/timesheet-mail/callback/gmail", "/timesheet-mail/callback/microsoft"):
            query = {key: _first_query_value(params, key) for key in params}
            try:
                status, location, _msg = handle_provider_callback(
                    secrets,
                    query,
                    official_http_userinfo_fetch,
                    official_http_token_fetch,
                    store=store,
                    app_base_fallback=fallback,
                )
            except Exception:
                self._text(400, "callback_failed")
                return
            if status == 302 and location:
                self._redirect(location)
                return
            self._text(status or 400, "callback_failed")
            return
        self._text(404, "not found")


# Backward-compatible name used by earlier local-scaffold notes.
_LocalHandler = CallbackHandler


def serve(secrets=None, host="0.0.0.0", port=None, store=None):
    """Start the callback HTTP server. Call only on a dedicated HTTPS fronted host."""
    secrets = secrets or secrets_from_env()
    if not secrets:
        raise SystemExit("TIMESHEET_MAIL_SECRETS_JSON is missing or invalid.")
    try:
        port = int(port if port is not None else os.environ.get("PORT") or 8080)
    except (TypeError, ValueError):
        port = 8080
    server = HTTPServer((host, port), CallbackHandler)
    server.secrets = secrets
    server.store = store or STORE
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
        serve(secrets=secrets_from_env(source))
        return
    raise SystemExit(
        "Do not start this scaffold as production mail sending unless "
        "TIMESHEET_MAIL_ALLOW_SERVE=1 is set on a dedicated HTTPS host. "
        "Deploy timesheet_mail_callback with registered redirect URIs, then set "
        "[timesheet_mail_backend] in Streamlit secrets."
    )


if __name__ == "__main__":
    main()
