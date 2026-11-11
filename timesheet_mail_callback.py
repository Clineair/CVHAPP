"""Standalone HTTPS callback service scaffold for timesheet mail OAuth.

This is not started by the Streamlit app and is not a Streamlit route.
Deploy it on its own HTTPS host, register its redirect URIs on the Gmail
and Microsoft OAuth clients, and point [timesheet_mail_backend] at it.

Official flow: authorization-code + PKCE + signed state. The callback
exchanges the code on this host, stores only a short-lived access token
in process memory, and redirects back to the Streamlit app without the
authorization code or any token in the query string.

Do not use Streamlit's reserved /oauth2callback path. Do not persist
tokens in Sheets or the repo. Do not run this as a general mail relay.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse
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


class _LocalHandler(BaseHTTPRequestHandler):
    """Local development only. Do not use this server in production."""

    secrets = None

    def log_message(self, format, *args):
        # Avoid writing query strings that may include temporary authorization codes.
        self.server.log_lines.append(self.path.split("?")[0])

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(501)
        self.end_headers()
        self.wfile.write(b"Configure a production HTTPS host. This built-in server is a scaffold only.")


def main():
    raise SystemExit(
        "Do not start this scaffold as production mail sending. Deploy "
        "timesheet_mail_callback on a dedicated HTTPS host with registered "
        "redirect URIs, then set [timesheet_mail_backend] in Streamlit secrets."
    )


if __name__ == "__main__":
    main()
