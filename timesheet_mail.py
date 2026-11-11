"""Per-user timesheet mail send for Gmail, Microsoft 365/Outlook/Hotmail, iCloud, and Yahoo.

This module implements official provider HTTP routes, consent binding, and
send gates. It does not start an HTTP server and does not enable sending
on Streamlit Community Cloud by itself. A separate HTTPS callback service
(see timesheet_mail_callback.py) is required before timesheet_email_can_send
can be true. Tokens are never written to Sheets, logs, query strings, or
the repo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets as pysecrets
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

TIMESHEET_EMAIL_TO = "patti@centralvalleyheli.com"
TIMESHEET_MAIL_OAUTH_PROVIDERS = ("gmail", "microsoft")
TIMESHEET_MAIL_SMTP_PROVIDERS = ("icloud", "yahoo")
TIMESHEET_MAIL_PROVIDERS = TIMESHEET_MAIL_OAUTH_PROVIDERS + TIMESHEET_MAIL_SMTP_PROVIDERS
TIMESHEET_MAIL_SECTION = "timesheet_mail"
TIMESHEET_EMPLOYEE_MAIL_SECTION = "timesheet_employee_mail"
TIMESHEET_MAIL_BACKEND_SECTION = "timesheet_mail_backend"
TIMESHEET_MAIL_ENABLED_KEY = "enabled"
TIMESHEET_MAIL_STATE_TTL_SEC = 600
TIMESHEET_MAIL_TOKEN_TTL_SEC = 3300  # short of a typical one-hour access token
TIMESHEET_MAIL_TICKET_TTL_SEC = 120

TIMESHEET_MAIL_GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "email",
)
TIMESHEET_MAIL_MICROSOFT_SCOPES = (
    "https://graph.microsoft.com/Mail.Send",
    "openid",
    "email",
    "profile",
)

TIMESHEET_MAIL_PROVIDERS_SPEC = {
    "gmail": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "send_url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        "scopes": TIMESHEET_MAIL_GMAIL_SCOPES,
    },
    "microsoft": {
        "authorize_template": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token_template": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        "send_url": "https://graph.microsoft.com/v1.0/me/sendMail",
        "scopes": TIMESHEET_MAIL_MICROSOFT_SCOPES,
        "default_tenant": "common",
    },
}

# Official SMTP settings from Apple and Yahoo documentation. There is no
# public self-serve OAuth send API for iCloud Mail. Yahoo's mail-w IMAP/SMTP
# OAuth is not self-serve; it requires a commercial access application.
TIMESHEET_MAIL_SMTP_SPEC = {
    "icloud": {
        "host": "smtp.mail.me.com",
        "port": 587,
        "security": "starttls",
        "username": "full_email",
        "credential": "app-specific password",
        "docs": "https://support.apple.com/en-us/102525",
        "password_docs": "https://support.apple.com/en-us/102654",
    },
    "yahoo": {
        "host": "smtp.mail.yahoo.com",
        "port": 587,
        "alt_port": 465,
        "security": "ssl-or-starttls",
        "username": "full_email",
        "credential": "app password",
        "docs": "https://help.yahoo.com/kb/account/imap-pop-yahoo-mail-sln3769.html",
        "password_docs": "https://help.yahoo.com/kb/mail/generate-password-sln15241.html",
    },
}

TIMESHEET_MAIL_CLIENT_KEYS = ("client_id", "client_secret", "redirect_uri")
TIMESHEET_SMTP_SECTION = "timesheet_smtp"
TIMESHEET_MAIL_BACKEND_KEYS = ("public_base_url", "state_secret")

TIMESHEET_MAIL_STATUS_SENT = "Sent"
TIMESHEET_MAIL_STATUS_DENIED = "Denied"
TIMESHEET_MAIL_STATUS_UNCERTAIN = "Uncertain"
TIMESHEET_MAIL_STATUS_DUPLICATE = "Duplicate blocked"
TIMESHEET_MAIL_ACTION_SEND = "Send"

_SECRET_PATTERNS = re.compile(
    r"(access_token|refresh_token|id_token|client_secret|state_secret|bearer\s+[a-z0-9._\-=]+|"
    r"code=[^&\s]+|client_secret=[^&\s]+|app.specific password|app password)",
    re.I,
)


def _cell(value):
    if value is None:
        return ""
    return str(value).strip()


def _lower_email(value):
    text = _cell(value).strip().lower()
    if not text or "@" not in text or " " in text:
        return ""
    return text


def sanitize_mail_error(exc):
    """Return a short error string with credentials and tokens removed."""
    text = _cell(exc if isinstance(exc, str) else "%s" % exc)
    text = _SECRET_PATTERNS.sub("[redacted]", text)
    return text[:300]


def timesheet_secret_section(secrets, name):
    if secrets is None:
        return None
    try:
        if name in secrets:
            return secrets[name]
    except Exception:
        return None
    return None


def timesheet_section_has_keys(section, required):
    if section is None:
        return False
    try:
        for key in required:
            if key not in section:
                return False
        return True
    except Exception:
        return False


def timesheet_mail_flag_enabled(secrets=None):
    section = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    if section is None:
        return False
    raw = None
    try:
        if TIMESHEET_MAIL_ENABLED_KEY in section:
            raw = section[TIMESHEET_MAIL_ENABLED_KEY]
    except Exception:
        return False
    return raw is True or _cell(raw).lower() in ("true", "1", "yes")


def timesheet_mail_backend_configured(secrets=None):
    return timesheet_section_has_keys(
        timesheet_secret_section(secrets, TIMESHEET_MAIL_BACKEND_SECTION),
        TIMESHEET_MAIL_BACKEND_KEYS,
    )


def timesheet_mail_auth_mode(provider):
    provider = _cell(provider).lower()
    if provider in TIMESHEET_MAIL_OAUTH_PROVIDERS:
        return "oauth"
    if provider in TIMESHEET_MAIL_SMTP_PROVIDERS:
        return "smtp_app_password"
    return ""


def timesheet_mail_provider_configured(provider, secrets=None):
    """OAuth clients need client keys. SMTP providers need a vault hook, not an app form."""
    provider = _cell(provider).lower()
    if provider in TIMESHEET_MAIL_OAUTH_PROVIDERS:
        root = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
        if root is None:
            return False
        section = None
        try:
            if provider in root:
                section = root[provider]
        except Exception:
            return False
        return timesheet_section_has_keys(section, TIMESHEET_MAIL_CLIENT_KEYS)
    if provider in TIMESHEET_MAIL_SMTP_PROVIDERS:
        return timesheet_smtp_store_configured(secrets)
    return False


def timesheet_smtp_store_configured(secrets=None):
    """True when a secrets-manager hook for SMTP app passwords is present.

    Key presence only. Values are never read here, never logged, and never
    stored in Sheets or a Streamlit form.
    """
    section = timesheet_secret_section(secrets, TIMESHEET_SMTP_SECTION)
    if section is None:
        return False
    try:
        # A store is configured when the section exists and is marked ready,
        # or when at least one employee key is present. Do not return values.
        if "configured" in section:
            flag = section["configured"]
            return flag is True or _cell(flag).lower() in ("true", "1", "yes")
        return len(list(section.keys())) > 0
    except Exception:
        return False


def timesheet_mail_clients_configured(secrets=None):
    return any(timesheet_mail_provider_configured(p, secrets) for p in TIMESHEET_MAIL_PROVIDERS)


def timesheet_mail_secure_setup_ready(secrets=None):
    """True only when the explicit enable flag, a mail client, and the callback backend keys exist."""
    return (
        timesheet_mail_flag_enabled(secrets)
        and timesheet_mail_backend_configured(secrets)
        and timesheet_mail_clients_configured(secrets)
    )


def timesheet_employee_mailbox_map(secrets=None):
    """Employee name -> {email, provider}. Empty and fail-closed if unconfigured.

    Does not invent addresses or providers. Duplicate emails fail closed.
    """
    section = timesheet_secret_section(secrets, TIMESHEET_EMPLOYEE_MAIL_SECTION)
    if section is None:
        return {}
    mapping = {}
    seen = {}
    try:
        keys = list(section.keys())
    except Exception:
        return {}
    for name in keys:
        entry = None
        try:
            entry = section[name]
        except Exception:
            continue
        email = ""
        provider = ""
        if isinstance(entry, dict) or hasattr(entry, "keys"):
            try:
                email = _lower_email(entry["email"] if "email" in entry else "")
            except Exception:
                email = ""
            try:
                provider = _cell(entry["provider"] if "provider" in entry else "").lower()
            except Exception:
                provider = ""
        else:
            # Allow "gmail:user@example.com" or just skip bare strings that have no provider.
            text = _cell(entry)
            if ":" in text:
                provider, email = text.split(":", 1)
                provider = provider.strip().lower()
                email = _lower_email(email)
        if not email or provider not in TIMESHEET_MAIL_PROVIDERS:
            continue
        mapping[_cell(name)] = {"email": email, "provider": provider}
        seen.setdefault(email, []).append(_cell(name))
    for email, names in seen.items():
        if len(names) > 1:
            for name in names:
                mapping.pop(name, None)
    return mapping


def timesheet_mailbox_for_employee(employee, secrets=None):
    return timesheet_employee_mailbox_map(secrets).get(_cell(employee))


def timesheet_provider_urls(provider, secrets=None):
    provider = _cell(provider).lower()
    spec = TIMESHEET_MAIL_PROVIDERS_SPEC.get(provider)
    if not spec:
        return None
    if provider == "gmail":
        return {
            "authorize_url": spec["authorize_url"],
            "token_url": spec["token_url"],
            "userinfo_url": spec["userinfo_url"],
            "send_url": spec["send_url"],
            "scopes": list(spec["scopes"]),
        }
    tenant = "common"
    root = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    try:
        if root and "microsoft" in root and "tenant" in root["microsoft"]:
            tenant = _cell(root["microsoft"]["tenant"]) or "common"
    except Exception:
        tenant = "common"
    if tenant not in ("common", "organizations", "consumers") and not re.match(r"^[0-9a-fA-F-]{8,}$", tenant):
        tenant = "common"
    return {
        "authorize_url": spec["authorize_template"].format(tenant=tenant),
        "token_url": spec["token_template"].format(tenant=tenant),
        "userinfo_url": spec["userinfo_url"],
        "send_url": spec["send_url"],
        "scopes": list(spec["scopes"]),
        "tenant": tenant,
    }


def timesheet_mail_redirect_uri(provider, secrets=None):
    root = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    if not root:
        return ""
    try:
        section = root[provider] if provider in root else None
        if section and "redirect_uri" in section:
            uri = _cell(section["redirect_uri"])
            parsed = urlparse(uri)
            if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
                return ""
            # Refuse to use Streamlit's reserved OIDC callback.
            if parsed.path.rstrip("/").endswith("oauth2callback"):
                return ""
            return uri
    except Exception:
        return ""
    return ""


def timesheet_pkce_pair():
    verifier = pysecrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def timesheet_mail_state_secret(secrets=None):
    section = timesheet_secret_section(secrets, TIMESHEET_MAIL_BACKEND_SECTION)
    if not section or "state_secret" not in section:
        return ""
    try:
        return section["state_secret"]
    except Exception:
        return ""


def timesheet_sign_state(payload, secret, now=None):
    if not secret:
        raise ValueError("Mail OAuth state signing is not configured.")
    body = dict(payload)
    body["exp"] = int((now or time.time()) + TIMESHEET_MAIL_STATE_TTL_SEC)
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    sig = hmac.new(_secret_bytes(secret), raw.encode("ascii"), hashlib.sha256).hexdigest()
    return raw + "." + sig


def _secret_bytes(secret):
    if isinstance(secret, bytes):
        return secret
    return _cell(secret).encode("utf-8")


def timesheet_verify_state(token, secret, now=None):
    if not secret or not token or "." not in _cell(token):
        return None
    raw, sig = _cell(token).rsplit(".", 1)
    expected = hmac.new(_secret_bytes(secret), raw.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        pad = "=" * (-len(raw) % 4)
        body = json.loads(base64.urlsafe_b64decode(raw + pad))
    except Exception:
        return None
    if int(body.get("exp") or 0) < int(now or time.time()):
        return None
    return body


def timesheet_authorize_url(provider, state, code_challenge, secrets=None, login_hint=None):
    if timesheet_mail_auth_mode(provider) != "oauth":
        raise ValueError(
            "There is no public self-serve OAuth send API for %s. Use the official SMTP "
            "app-password path via the secure mail backend, not an in-app password form."
            % provider
        )
    urls = timesheet_provider_urls(provider, secrets)
    redirect = timesheet_mail_redirect_uri(provider, secrets)
    root = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    client_id = ""
    try:
        client_id = root[provider]["client_id"]
    except Exception:
        client_id = ""
    if not urls or not redirect or not client_id:
        raise ValueError("Mail OAuth client for %s is not configured." % provider)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(urls["scopes"]),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent select_account",
    }
    # Session-only: do not request a Google refresh token.
    if provider == "gmail":
        params["access_type"] = "online"
    if provider == "microsoft":
        params["response_mode"] = "query"
    hint = _lower_email(login_hint)
    if hint:
        params["login_hint"] = hint
    return urls["authorize_url"] + "?" + urlencode(params)


def timesheet_token_exchange_payload(provider, code, code_verifier, secrets=None):
    """Official authorization-code + PKCE token request fields. No tokens in the result."""
    if not _cell(code) or not _cell(code_verifier):
        raise ValueError("Authorization code and PKCE verifier are required.")
    urls = timesheet_provider_urls(provider, secrets)
    redirect = timesheet_mail_redirect_uri(provider, secrets)
    root = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    try:
        client_id = root[provider]["client_id"]
        client_secret = root[provider]["client_secret"]
    except Exception:
        raise ValueError("Mail OAuth client for %s is not configured." % provider)
    if not urls or not redirect:
        raise ValueError("Mail OAuth client for %s is not configured." % provider)
    return {
        "url": urls["token_url"],
        "data": {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
        },
    }


def extract_mailbox_email(userinfo):
    if not userinfo or not isinstance(userinfo, dict):
        return ""
    for key in ("email", "preferred_username", "upn", "userPrincipalName"):
        email = _lower_email(userinfo.get(key))
        if email:
            return email
    return ""


def mailbox_matches_employee(employee, mailbox_email, secrets=None):
    configured = timesheet_mailbox_for_employee(employee, secrets)
    if not configured:
        return False
    return _lower_email(mailbox_email) == configured["email"]


class MemoryMailTokenStore:
    """Process-local access-token store for the callback service. Not Sheets.

    Tokens are keyed by employee name and never returned in query parameters.
    Refresh tokens are not stored. Entries expire with the access token.
    """

    def __init__(self, clock=None):
        self._items = {}
        self._pending = {}
        self._tickets = {}
        self._clock = clock or time.time

    def put_pending(self, nonce, record):
        self._pending[nonce] = dict(record)
        self._pending[nonce]["exp"] = self._clock() + TIMESHEET_MAIL_STATE_TTL_SEC

    def pop_pending(self, nonce):
        rec = self._pending.pop(nonce, None)
        if not rec or rec.get("exp", 0) < self._clock():
            return None
        return rec

    def put_access(self, employee, provider, mailbox_email, access_token, expires_in=None):
        ttl = int(expires_in or TIMESHEET_MAIL_TOKEN_TTL_SEC)
        ttl = min(max(ttl, 60), TIMESHEET_MAIL_TOKEN_TTL_SEC)
        self._items[_cell(employee)] = {
            "provider": _cell(provider).lower(),
            "mailbox_email": _lower_email(mailbox_email),
            "access_token": access_token,
            "exp": self._clock() + ttl,
        }

    def get_access(self, employee):
        rec = self._items.get(_cell(employee))
        if not rec or rec.get("exp", 0) < self._clock():
            self._items.pop(_cell(employee), None)
            return None
        return rec

    def drop(self, employee):
        self._items.pop(_cell(employee), None)

    def issue_ticket(self, employee):
        ticket = pysecrets.token_urlsafe(32)
        self._tickets[ticket] = {"employee": _cell(employee), "exp": self._clock() + TIMESHEET_MAIL_TICKET_TTL_SEC}
        return ticket

    def redeem_ticket(self, ticket):
        rec = self._tickets.pop(_cell(ticket), None)
        if not rec or rec.get("exp", 0) < self._clock():
            return None
        access = self.get_access(rec["employee"])
        if not access:
            return None
        # Return metadata only plus a handle; callers in Streamlit should
        # prefer asking the store to send rather than copying the token.
        return {
            "employee": rec["employee"],
            "provider": access["provider"],
            "mailbox_email": access["mailbox_email"],
            "exp": access["exp"],
        }

    def consent_metadata(self, employee):
        rec = self.get_access(employee)
        if not rec:
            return None
        return {
            "employee": _cell(employee),
            "provider": rec["provider"],
            "mailbox_email": rec["mailbox_email"],
            "exp": rec["exp"],
        }


def build_timesheet_mime(record, pdf_bytes, filename, from_email, to=None):
    if to is not None and _lower_email(to) != TIMESHEET_EMAIL_TO:
        raise ValueError("Timesheet email can only be addressed to " + TIMESHEET_EMAIL_TO + ".")
    if not pdf_bytes or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("Only the generated timesheet PDF can be attached.")
    if pdf_bytes[:5] != b"%PDF-":
        raise ValueError("Only the generated timesheet PDF can be attached.")
    from_addr = _lower_email(from_email)
    if not from_addr:
        raise ValueError("A bound mailbox address is required.")
    msg = EmailMessage()
    msg["To"] = TIMESHEET_EMAIL_TO
    msg["From"] = from_addr
    msg["Subject"] = timesheet_email_subject(record)
    msg.set_content(timesheet_email_body(record))
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    return msg


def timesheet_email_subject(record):
    return "CVH Weekly Time Sheet — " + _cell((record or {}).get("Employee")) + " — week of " + _cell((record or {}).get("Week Of"))


def timesheet_email_body(record):
    employee = _cell((record or {}).get("Employee"))
    week = _cell((record or {}).get("Week Of"))
    return (
        "Patti,\n\n"
        "Please find my weekly time sheet for the week of " + week + " attached.\n\n"
        "This PDF was generated by the CVH Employee Tool and sent from my authorized "
        "email account after I reviewed and confirmed Send.\n\n"
        + employee + "\n"
    )


def timesheet_gmail_send_payload(mime_message):
    raw = base64.urlsafe_b64encode(bytes(mime_message)).decode("ascii")
    return {"raw": raw}


def timesheet_microsoft_send_payload(record, pdf_bytes, filename, from_email, to=None):
    if to is not None and _lower_email(to) != TIMESHEET_EMAIL_TO:
        raise ValueError("Timesheet email can only be addressed to " + TIMESHEET_EMAIL_TO + ".")
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("Only the generated timesheet PDF can be attached.")
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "message": {
            "subject": timesheet_email_subject(record),
            "body": {"contentType": "Text", "content": timesheet_email_body(record)},
            "toRecipients": [{"emailAddress": {"address": TIMESHEET_EMAIL_TO}}],
            "from": {"emailAddress": {"address": _lower_email(from_email)}},
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentType": "application/pdf",
                "contentBytes": encoded,
            }],
        },
        "saveToSentItems": True,
    }


def timesheet_send_idempotency_key(record):
    employee = _cell((record or {}).get("Employee"))
    week = _cell((record or {}).get("Week Of"))
    digest = _cell((record or {}).get("Content Hash"))
    return hashlib.sha256(("|".join([employee, week, digest])).encode("utf-8")).hexdigest()


def timesheet_already_sent(audit_records, record):
    key = timesheet_send_idempotency_key(record)
    for row in audit_records or []:
        if _cell(row.get("Status")) != TIMESHEET_MAIL_STATUS_SENT:
            continue
        if _cell(row.get("Idempotency Key")) == key:
            return True
        if (
            _cell(row.get("Employee")) == _cell(record.get("Employee"))
            and _cell(row.get("Week Of")) == _cell(record.get("Week Of"))
            and _cell(row.get("Content Hash")) == _cell(record.get("Content Hash"))
        ):
            return True
    return False


def timesheet_uncertain_send(audit_records, record):
    key = timesheet_send_idempotency_key(record)
    for row in reversed(list(audit_records or [])):
        same = _cell(row.get("Idempotency Key")) == key or (
            _cell(row.get("Employee")) == _cell(record.get("Employee"))
            and _cell(row.get("Week Of")) == _cell(record.get("Week Of"))
            and _cell(row.get("Content Hash")) == _cell(record.get("Content Hash"))
        )
        if same and _cell(row.get("Status")) == TIMESHEET_MAIL_STATUS_UNCERTAIN:
            return True
        if same:
            return False
    return False


def classify_send_http_result(status_code, provider):
    provider = _cell(provider).lower()
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return TIMESHEET_MAIL_STATUS_UNCERTAIN
    if provider == "microsoft" and code == 202:
        return TIMESHEET_MAIL_STATUS_SENT
    if provider == "gmail" and code in (200, 202):
        return TIMESHEET_MAIL_STATUS_SENT
    if code in (401, 403):
        return TIMESHEET_MAIL_STATUS_DENIED
    if 400 <= code < 500:
        return TIMESHEET_MAIL_STATUS_DENIED
    return TIMESHEET_MAIL_STATUS_UNCERTAIN


def timesheet_smtp_setup_reason(provider):
    provider = _cell(provider).lower()
    if provider == "icloud":
        return (
            "iCloud Mail has no public OAuth send API. Apple's official method is SMTP "
            "(smtp.mail.me.com:587) with an app-specific password from account.apple.com, "
            "not the Apple Account password. Those app-specific passwords must be stored "
            "only in a secure mail-backend vault, never in Sheets, chat, or an app form. "
            "That vault is not configured, so sending stays off. This app does not send mail."
        )
    if provider == "yahoo":
        return (
            "Yahoo Mail does not offer a self-serve send API. Official options are SMTP "
            "(smtp.mail.yahoo.com:587 or 465) with a Yahoo app password, or IMAP/SMTP "
            "OAuth after Yahoo grants commercial mail-w access (not self-serve). App "
            "passwords must be stored only in a secure mail-backend vault, never in "
            "Sheets, chat, or an app form. That vault is not configured, so sending "
            "stays off. This app does not send mail."
        )
    return (
        "This mailbox provider requires a secure backend credential store that is not "
        "configured. This app does not send mail and will not ask for a mail password."
    )


def timesheet_mail_send_gates(
    record,
    *,
    user_employee=None,
    consent=None,
    secrets=None,
    saved=None,
    current=None,
    initials_match=None,
    access_allowed=None,
    pdf_bytes=None,
    filename=None,
    to=None,
    audit_records=None,
    acknowledge_uncertain=False,
):
    """Return (ok, reason). Never enables send when setup or binding is incomplete."""
    if not timesheet_mail_secure_setup_ready(secrets):
        return False, (
            "In-app sending is disabled until Google sign-in, the employee mailbox "
            "map, Gmail and/or Microsoft mail OAuth clients, and a separate HTTPS "
            "mail callback service are configured. This app does not send mail yet."
        )
    if not record:
        return False, "A time sheet is required."
    employee = _cell(record.get("Employee"))
    if access_allowed is not True:
        return False, "Only the signed-in employee can send their own initialed time sheet. This app does not send mail for others."
    if user_employee and _cell(user_employee) != employee:
        return False, "Only the signed-in employee can send their own initialed time sheet. This app does not send mail for others."
    mailbox = timesheet_mailbox_for_employee(employee, secrets)
    if not mailbox:
        return False, "No mailbox provider is configured for this employee, so sending stays off."
    if timesheet_mail_auth_mode(mailbox["provider"]) == "smtp_app_password":
        if not timesheet_smtp_store_configured(secrets):
            return False, timesheet_smtp_setup_reason(mailbox["provider"])
    elif not timesheet_mail_provider_configured(mailbox["provider"], secrets):
        return False, "The " + mailbox["provider"] + " mail client is not configured, so sending stays off."
    if to is not None and _lower_email(to) != TIMESHEET_EMAIL_TO:
        return False, "Timesheet email can only be addressed to " + TIMESHEET_EMAIL_TO + "."
    if initials_match is not True:
        return False, "Initial and save this week's current time-sheet content before sending."
    if not consent:
        if timesheet_mail_auth_mode(mailbox["provider"]) == "smtp_app_password":
            return False, timesheet_smtp_setup_reason(mailbox["provider"])
        return False, (
            "Authorize " + mailbox["provider"] + " mail send for this session. Signing in "
            "does not grant permission to send mail. Access lasts only for this short session."
        )
    if _cell(consent.get("employee")) != employee:
        return False, "Mail authorization is bound to a different employee."
    if _cell(consent.get("provider")).lower() != mailbox["provider"]:
        return False, "Mail authorization does not match the configured mailbox provider."
    if _lower_email(consent.get("mailbox_email")) != mailbox["email"]:
        return False, "The authorized mailbox does not match the configured employee address."
    if consent.get("exp") and consent.get("exp") < time.time():
        return False, "Mail authorization expired. Authorize again to send."
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-":
        return False, "The official generated timesheet PDF is required."
    if filename and not _cell(filename).lower().endswith(".pdf"):
        return False, "Only the generated timesheet PDF can be attached."
    if timesheet_already_sent(audit_records, record):
        return False, "This exact initialed time sheet was already sent. Change and re-initial the week before sending again."
    if timesheet_uncertain_send(audit_records, record) and not acknowledge_uncertain:
        return False, (
            "A previous send for this week did not get a clear result. Check your Sent folder "
            "before sending again. The app will not retry automatically."
        )
    return True, ""


def timesheet_email_can_send(*args, **kwargs):
    ok, _reason = timesheet_mail_send_gates(*args, **kwargs)
    return ok


def timesheet_mail_block_reason(*args, **kwargs):
    _ok, reason = timesheet_mail_send_gates(*args, **kwargs)
    return reason or "This app does not send mail until you review the message and press Send."


def timesheet_mail_preview(record, consent=None, filename=None):
    from_email = _lower_email((consent or {}).get("mailbox_email"))
    return {
        "to": TIMESHEET_EMAIL_TO,
        "from": from_email,
        "subject": timesheet_email_subject(record),
        "body": timesheet_email_body(record),
        "attachment": filename or "",
        "provider": _cell((consent or {}).get("provider")),
    }


def send_via_provider(provider, access_token, record, pdf_bytes, filename, from_email, http_post=None, to=None):
    """POST the official send API. http_post(url, headers, json=None, timeout=) must be injected or requests."""
    if to is not None and _lower_email(to) != TIMESHEET_EMAIL_TO:
        raise ValueError("Timesheet email can only be addressed to " + TIMESHEET_EMAIL_TO + ".")
    if not access_token:
        raise ValueError("Mail authorization is missing.")
    urls = timesheet_provider_urls(provider)
    headers = {"Authorization": "Bearer " + access_token}
    if provider == "gmail":
        mime = build_timesheet_mime(record, pdf_bytes, filename, from_email, to=to)
        body = timesheet_gmail_send_payload(mime)
        headers["Content-Type"] = "application/json"
        payload = body
        json_body = payload
    elif provider == "microsoft":
        json_body = timesheet_microsoft_send_payload(record, pdf_bytes, filename, from_email, to=to)
        headers["Content-Type"] = "application/json"
    else:
        raise ValueError("Unsupported mail provider.")
    poster = http_post or _default_http_post
    try:
        status, _response_text = poster(urls["send_url"], headers=headers, json=json_body, timeout=30)
    except Exception as exc:
        return {
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": sanitize_mail_error(exc),
        }
    result = classify_send_http_result(status, provider)
    return {"status": result, "http_status": status, "error": "" if result == TIMESHEET_MAIL_STATUS_SENT else "Send was not accepted."}


def _default_http_post(url, headers=None, json=None, timeout=30):
    # Imported lazily so tests can inject a stub and production can use requests.
    import requests
    # Do not log headers or body; they may contain tokens or PDF data.
    response = requests.post(url, headers=headers, json=json, timeout=timeout)
    return response.status_code, response.text


def execute_timesheet_send(
    record,
    *,
    store,
    pdf_bytes,
    filename,
    secrets=None,
    user_employee=None,
    saved=None,
    current=None,
    initials_match=None,
    access_allowed=None,
    to=None,
    audit_records=None,
    acknowledge_uncertain=False,
    http_post=None,
    in_flight=None,
):
    """Send once through the official provider API using a server-side token store.

    Never retries automatically on uncertain results. Rerun-safe if the same
    idempotency key is in in_flight or already marked Sent in audit_records.
    """
    consent = store.consent_metadata(user_employee or _cell((record or {}).get("Employee"))) if store else None
    ok, reason = timesheet_mail_send_gates(
        record,
        user_employee=user_employee,
        consent=consent,
        secrets=secrets,
        saved=saved,
        current=current,
        initials_match=initials_match,
        access_allowed=access_allowed,
        pdf_bytes=pdf_bytes,
        filename=filename,
        to=to,
        audit_records=audit_records,
        acknowledge_uncertain=acknowledge_uncertain,
    )
    key = timesheet_send_idempotency_key(record) if record else ""
    if in_flight is not None and key and key in in_flight:
        return {"status": TIMESHEET_MAIL_STATUS_DUPLICATE, "error": "Send is already in progress or finished for this week.", "idempotency_key": key}
    if not ok:
        return {"status": TIMESHEET_MAIL_STATUS_DENIED, "error": reason, "idempotency_key": key}
    access = store.get_access(user_employee or record.get("Employee"))
    if not access or not access.get("access_token"):
        return {"status": TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail authorization is missing or expired.", "idempotency_key": key}
    if in_flight is not None and key:
        in_flight.add(key)
    result = send_via_provider(
        access["provider"],
        access["access_token"],
        record,
        pdf_bytes,
        filename,
        access["mailbox_email"],
        http_post=http_post,
        to=to,
    )
    result["idempotency_key"] = key
    result["from"] = access["mailbox_email"]
    result["provider"] = access["provider"]
    result["to"] = TIMESHEET_EMAIL_TO
    if result.get("status") == TIMESHEET_MAIL_STATUS_DENIED and result.get("http_status") in (401, 403):
        store.drop(user_employee or record.get("Employee"))
        result["error"] = "Mail authorization was rejected or expired. Authorize again to send."
    return result


def bind_consented_mailbox(store, pending, token_response, userinfo, secrets=None):
    """Bind a freshly exchanged access token to the expected employee mailbox.

    Rejects mismatched mailbox identity. Does not persist refresh tokens.
    """
    employee = _cell((pending or {}).get("employee"))
    provider = _cell((pending or {}).get("provider")).lower()
    mailbox = extract_mailbox_email(userinfo)
    if not employee or provider not in TIMESHEET_MAIL_PROVIDERS:
        return None, "Mail authorization state was invalid."
    if not mailbox_matches_employee(employee, mailbox, secrets):
        return None, "The authorized mailbox does not match the configured employee address."
    expected_provider = (timesheet_mailbox_for_employee(employee, secrets) or {}).get("provider")
    if expected_provider and expected_provider != provider:
        return None, "Mail authorization does not match the configured mailbox provider."
    access_token = (token_response or {}).get("access_token")
    if not access_token:
        return None, "Mail authorization did not return an access token."
    expires_in = token_response.get("expires_in")
    store.put_access(employee, provider, mailbox, access_token, expires_in=expires_in)
    # Intentionally ignore refresh_token if a provider sent one.
    return store.consent_metadata(employee), ""



def timesheet_mail_backend_base(secrets=None):
    section = timesheet_secret_section(secrets, TIMESHEET_MAIL_BACKEND_SECTION)
    if not section or "public_base_url" not in section:
        return ""
    try:
        base = _cell(section["public_base_url"]).rstrip("/")
    except Exception:
        return ""
    parsed = urlparse(base)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        return ""
    if parsed.path.rstrip("/").endswith("oauth2callback"):
        return ""
    return base


def timesheet_mail_start_link(employee, provider, app_return, secrets=None):
    """Signed link to the callback service /timesheet-mail/start. No access tokens."""
    if not timesheet_mail_secure_setup_ready(secrets):
        return ""
    mailbox = timesheet_mailbox_for_employee(employee, secrets)
    provider = _cell(provider or ((mailbox or {}).get("provider"))).lower()
    if not mailbox or mailbox["provider"] != provider:
        return ""
    if timesheet_mail_auth_mode(provider) != "oauth":
        return ""
    if not timesheet_mail_provider_configured(provider, secrets):
        return ""
    secret = timesheet_mail_state_secret(secrets)
    base = timesheet_mail_backend_base(secrets)
    if not secret or not base:
        return ""
    token = timesheet_sign_state({
        "kind": "start",
        "employee": _cell(employee),
        "provider": provider,
        "return": _cell(app_return).split("?")[0],
    }, secret)
    return base + "/timesheet-mail/start?" + urlencode({"start": token})


def app_return_url(app_base_url, ticket=None):
    """Redirect back to the Streamlit app without OAuth codes or tokens."""
    base = _cell(app_base_url).split("?")[0].split("#")[0]
    if not base:
        return ""
    parsed = urlparse(base)
    if parsed.path.rstrip("/").endswith("oauth2callback"):
        raise ValueError("Must not return to Streamlit's reserved OIDC callback.")
    if ticket:
        # One-time opaque ticket only — never an access token or auth code.
        return base + ("&" if "?" in base else "?") + urlencode({"timesheet_mail": "ready", "ticket": ticket})
    return base + ("&" if "?" in base else "?") + urlencode({"timesheet_mail": "ready"})
