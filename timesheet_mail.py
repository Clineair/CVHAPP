"""Per-user timesheet mail send for Gmail, Microsoft 365/Outlook/Hotmail, iCloud, and Yahoo.

This module implements official provider routes, consent binding, and send
gates. It does not start an HTTP server and does not enable sending by
itself. A separate HTTPS callback (see timesheet_mail_callback.py) must be
configured before timesheet_email_can_send can be true. Access tokens stay
in that service's shared store. SMTP app passwords are read from Secret
Manager at send time and are never written to Sheets, logs, query strings,
or the repo. Microsoft send stays available for a later roster change and
is not used by the current employees.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets as pysecrets
import smtplib
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
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
TIMESHEET_MAIL_API_TTL_SEC = 120
TIMESHEET_MAIL_CLAIM_TTL_SEC = 180
TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC = 180 * 24 * 60 * 60
TIMESHEET_SMTP_SECRET_PREFIX = "timesheet-smtp-"
TIMESHEET_MAIL_STORE_COLLECTION = "timesheet_mail_tokens"
TIMESHEET_SIGNIN_SECTION = "timesheet_employees"

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
    r"((?:access_token|refresh_token|id_token|client_secret|state_secret)(?:=|:)?\S*|"
    r"bearer\s+\S+|code=[^&\s]+|app[- ]specific password|app password)",
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


def sanitize_mail_error(exc, extra=()):
    """Return a short error string with credentials and tokens removed."""
    text = _cell(exc if isinstance(exc, str) else "%s" % exc)
    for secret in extra or ():
        secret_text = secret if isinstance(secret, str) else ""
        if len(secret_text) >= 4:
            text = text.replace(secret_text, "[redacted]")
    text = _SECRET_PATTERNS.sub("[redacted]", text)
    text = re.sub(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", "[redacted-address]", text, flags=re.I)
    return text[:300]


def scrub_audit_detail(text):
    """Short sheet-safe result text. No mailbox addresses, tokens, or passwords."""
    cleaned = sanitize_mail_error(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120]


def timesheet_mail_recipient(secrets=None):
    """Fixed recipient. Secrets override the long-standing default; send fails closed on a bad value.

    Employee mailbox addresses are never read here. When [timesheet_mail].recipient
    is absent, the historical fixed recipient is used so existing gates stay stable.
    Production should set the secret and treat that value as the only allowed To.
    """
    section = timesheet_secret_section(secrets, TIMESHEET_MAIL_SECTION)
    configured = ""
    if section is not None:
        try:
            if "recipient" in section:
                configured = _lower_email(section["recipient"])
        except Exception:
            configured = ""
    if configured:
        return configured
    return TIMESHEET_EMAIL_TO


def timesheet_employee_for_signin_email(email, secrets=None):
    """Map one verified sign-in email to one employee. Fail closed on duplicates or misses."""
    section = timesheet_secret_section(secrets, TIMESHEET_SIGNIN_SECTION)
    if section is None:
        return None
    wanted = _lower_email(email)
    if not wanted:
        return None
    matches = []
    try:
        keys = list(section.keys())
    except Exception:
        return None
    for name in keys:
        try:
            mapped = _lower_email(section[name])
        except Exception:
            continue
        if mapped and mapped == wanted:
            matches.append(_cell(name))
    if len(matches) != 1:
        return None
    return matches[0]


def timesheet_pdf_sha256(pdf_bytes):
    return hashlib.sha256(pdf_bytes or b"").hexdigest()


def timesheet_smtp_secret_id(employee, prefix=None):
    """Secret Manager id derived from the employee name. Never an email address."""
    slug = re.sub(r"[^a-z0-9]+", "-", _cell(employee).lower()).strip("-")
    if not slug:
        raise ValueError("Employee name is required for the SMTP secret id.")
    prefix = prefix or TIMESHEET_SMTP_SECRET_PREFIX
    return prefix + slug


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


def timesheet_sign_state(payload, secret, now=None, ttl=None):
    if not secret:
        raise ValueError("Mail OAuth state signing is not configured.")
    body = dict(payload)
    lifetime = TIMESHEET_MAIL_STATE_TTL_SEC if ttl is None else int(ttl)
    body["exp"] = int((now or time.time()) + lifetime)
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    sig = hmac.new(_secret_bytes(secret), raw.encode("ascii"), hashlib.sha256).hexdigest()
    return raw + "." + sig


def timesheet_sign_api_request(payload, secret, now=None):
    """HMAC body for Streamlit-to-backend redeem/send. Short-lived and replay-protected by nonce."""
    body = dict(payload or {})
    if not _cell(body.get("nonce")):
        body["nonce"] = pysecrets.token_urlsafe(24)
    if not _cell(body.get("kind")):
        raise ValueError("Mail API request kind is required.")
    return timesheet_sign_state(body, secret, now=now, ttl=TIMESHEET_MAIL_API_TTL_SEC)


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
    """In-process mail store used by tests and an explicit local override.

    Production Cloud Run must use FirestoreMailTokenStore. This class is not
    shared across instances and does not survive a restart. Tokens are keyed
    by employee name and never returned in query parameters. Refresh tokens
    are not stored. SMTP app passwords are never stored here.
    """

    def __init__(self, clock=None):
        self._items = {}
        self._pending = {}
        self._tickets = {}
        self._nonces = {}
        self._idempotency = {}
        self._clock = clock or time.time
        self._lock = threading.Lock()

    def put_pending(self, nonce, record):
        with self._lock:
            self._pending[nonce] = dict(record)
            self._pending[nonce]["exp"] = self._clock() + TIMESHEET_MAIL_STATE_TTL_SEC

    def pop_pending(self, nonce):
        with self._lock:
            rec = self._pending.pop(nonce, None)
            if not rec or rec.get("exp", 0) < self._clock():
                return None
            return rec

    def put_access(self, employee, provider, mailbox_email, access_token, expires_in=None):
        ttl = int(expires_in or TIMESHEET_MAIL_TOKEN_TTL_SEC)
        ttl = min(max(ttl, 60), TIMESHEET_MAIL_TOKEN_TTL_SEC)
        with self._lock:
            self._items[_cell(employee)] = {
                "provider": _cell(provider).lower(),
                "mailbox_email": _lower_email(mailbox_email),
                "access_token": access_token,
                "kind": "oauth",
                "exp": self._clock() + ttl,
            }

    def put_smtp_session(self, employee, provider, mailbox_email, ttl=None):
        """Record that a vaulted SMTP mailbox may send. Does not store the password."""
        lifetime = int(ttl or TIMESHEET_MAIL_TOKEN_TTL_SEC)
        lifetime = min(max(lifetime, 60), TIMESHEET_MAIL_TOKEN_TTL_SEC)
        with self._lock:
            self._items[_cell(employee)] = {
                "provider": _cell(provider).lower(),
                "mailbox_email": _lower_email(mailbox_email),
                "kind": "smtp",
                "exp": self._clock() + lifetime,
            }

    def get_access(self, employee):
        with self._lock:
            rec = self._items.get(_cell(employee))
            if not rec or rec.get("exp", 0) < self._clock():
                self._items.pop(_cell(employee), None)
                return None
            return dict(rec)

    def drop(self, employee):
        with self._lock:
            self._items.pop(_cell(employee), None)

    def issue_ticket(self, employee):
        ticket = pysecrets.token_urlsafe(32)
        with self._lock:
            self._tickets[ticket] = {"employee": _cell(employee), "exp": self._clock() + TIMESHEET_MAIL_TICKET_TTL_SEC}
        return ticket

    def redeem_ticket(self, ticket):
        with self._lock:
            rec = self._tickets.pop(_cell(ticket), None)
            if not rec or rec.get("exp", 0) < self._clock():
                return None
            access = self._items.get(rec["employee"])
            if not access or access.get("exp", 0) < self._clock():
                return None
            # Metadata only. Streamlit must not receive the access token.
            return {
                "employee": rec["employee"],
                "provider": access["provider"],
                "mailbox_email": access["mailbox_email"],
                "exp": access["exp"],
                "kind": access.get("kind") or "oauth",
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
            "kind": rec.get("kind") or "oauth",
        }

    def remember_nonce(self, nonce, exp, now=None):
        """Return True the first time a signed API nonce is seen. False on replay."""
        nonce = _cell(nonce)
        if not nonce:
            return False
        with self._lock:
            current = self._clock() if now is None else float(now)
            expired = [key for key, until in self._nonces.items() if until < current]
            for key in expired:
                self._nonces.pop(key, None)
            if nonce in self._nonces:
                return False
            self._nonces[nonce] = float(exp or 0)
            return True

    def claim_send(self, key, employee, week, content_hash, acknowledge_uncertain=False):
        """Atomically claim one employee + week + content hash send.

        Returns claimed, sent, uncertain, or in_progress. Uncertain and expired
        in-progress claims are not retried unless the caller explicitly acknowledges.
        """
        key = _cell(key)
        if not key:
            return "uncertain"
        with self._lock:
            now = self._clock()
            rec = self._idempotency.get(key)
            if rec:
                status = rec.get("status")
                if status == TIMESHEET_MAIL_STATUS_SENT:
                    return "sent"
                if status == TIMESHEET_MAIL_STATUS_UNCERTAIN:
                    if not acknowledge_uncertain:
                        return "uncertain"
                    rec["status"] = "InProgress"
                    rec["exp"] = now + TIMESHEET_MAIL_CLAIM_TTL_SEC
                    return "claimed"
                if status == "InProgress":
                    if rec.get("exp", 0) >= now:
                        return "in_progress"
                    if not acknowledge_uncertain:
                        rec["status"] = TIMESHEET_MAIL_STATUS_UNCERTAIN
                        rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                        return "uncertain"
                    rec["status"] = "InProgress"
                    rec["exp"] = now + TIMESHEET_MAIL_CLAIM_TTL_SEC
                    return "claimed"
            self._idempotency[key] = {
                "status": "InProgress",
                "employee": _cell(employee),
                "week": _cell(week),
                "content_hash": _cell(content_hash),
                "exp": now + TIMESHEET_MAIL_CLAIM_TTL_SEC,
            }
            return "claimed"

    def finish_send(self, key, status):
        """Record the provider outcome. Denied releases the claim. Uncertain stays blocked."""
        key = _cell(key)
        if not key:
            return
        with self._lock:
            rec = self._idempotency.get(key)
            now = self._clock()
            if status == TIMESHEET_MAIL_STATUS_DENIED:
                self._idempotency.pop(key, None)
                return
            if rec is None:
                rec = {
                    "employee": "",
                    "week": "",
                    "content_hash": "",
                }
                self._idempotency[key] = rec
            if status == TIMESHEET_MAIL_STATUS_SENT:
                rec["status"] = TIMESHEET_MAIL_STATUS_SENT
                rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                return
            if status == TIMESHEET_MAIL_STATUS_UNCERTAIN:
                rec["status"] = TIMESHEET_MAIL_STATUS_UNCERTAIN
                rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                return
            if status == TIMESHEET_MAIL_STATUS_DUPLICATE:
                return
            self._idempotency.pop(key, None)


def _store_doc_id(prefix, value):
    digest = hashlib.sha256(_cell(value).encode("utf-8")).hexdigest()
    return prefix + "_" + digest


def _expire_at(exp):
    return datetime.fromtimestamp(float(exp), tz=timezone.utc)


class FirestoreMailTokenStore:
    """Shared short-lived store for Cloud Run. Survives restarts and multiple instances.

    Documents live in one Firestore collection. Reads enforce exp even if a TTL
    policy is not configured yet. Access tokens and PKCE verifiers stay in this
    store; redeem and consent methods never return them. SMTP passwords are
    not written here.
    """

    def __init__(self, project, client=None, clock=None, collection=None):
        self.project = _cell(project)
        if not self.project:
            raise ValueError("Firestore token store requires a Google Cloud project id.")
        self._client = client
        self._clock = clock or time.time
        self.collection = collection or TIMESHEET_MAIL_STORE_COLLECTION

    @property
    def client(self):
        if self._client is None:
            try:
                from google.cloud import firestore
            except Exception as exc:
                raise SystemExit("google-cloud-firestore is not installed.") from exc
            self._client = firestore.Client(project=self.project)
        return self._client

    def _doc(self, doc_id):
        return self.client.collection(self.collection).document(doc_id)

    def _transact(self, fn):
        client = self.client
        runner = getattr(client, "run_transaction", None)
        if runner is not None:
            return runner(fn)
        from google.cloud import firestore
        transaction = client.transaction()
        return firestore.transactional(fn)(transaction)

    def _mutate(self, doc_id, mutator):
        def run(transaction):
            ref = self._doc(doc_id)
            snap = ref.get(transaction=transaction)
            current = snap.to_dict() if getattr(snap, "exists", False) else None
            new_value, result = mutator(current)
            if new_value is None:
                if current is not None:
                    transaction.delete(ref)
            else:
                new_value = dict(new_value)
                if "exp" in new_value and "expire_at" not in new_value:
                    new_value["expire_at"] = _expire_at(new_value["exp"])
                transaction.set(ref, new_value)
            return result
        return self._transact(run)

    def _live(self, current, now=None):
        if not current:
            return None
        if float(current.get("exp") or 0) < float(now or self._clock()):
            return None
        return current

    def put_pending(self, nonce, record):
        data = dict(record)
        data.pop("access_token", None)
        data.pop("refresh_token", None)
        data["exp"] = self._clock() + TIMESHEET_MAIL_STATE_TTL_SEC
        self._mutate(_store_doc_id("pending", nonce), lambda _current: (data, True))

    def pop_pending(self, nonce):
        def mutator(current):
            live = self._live(current)
            if not live:
                return None, None
            return None, dict(live)
        return self._mutate(_store_doc_id("pending", nonce), mutator)

    def put_access(self, employee, provider, mailbox_email, access_token, expires_in=None):
        ttl = int(expires_in or TIMESHEET_MAIL_TOKEN_TTL_SEC)
        ttl = min(max(ttl, 60), TIMESHEET_MAIL_TOKEN_TTL_SEC)
        data = {
            "employee": _cell(employee),
            "provider": _cell(provider).lower(),
            "mailbox_email": _lower_email(mailbox_email),
            "access_token": access_token,
            "kind": "oauth",
            "exp": self._clock() + ttl,
        }
        self._mutate(_store_doc_id("access", employee), lambda _current: (data, True))

    def put_smtp_session(self, employee, provider, mailbox_email, ttl=None):
        lifetime = int(ttl or TIMESHEET_MAIL_TOKEN_TTL_SEC)
        lifetime = min(max(lifetime, 60), TIMESHEET_MAIL_TOKEN_TTL_SEC)
        data = {
            "employee": _cell(employee),
            "provider": _cell(provider).lower(),
            "mailbox_email": _lower_email(mailbox_email),
            "kind": "smtp",
            "exp": self._clock() + lifetime,
        }
        self._mutate(_store_doc_id("access", employee), lambda _current: (data, True))

    def get_access(self, employee):
        def mutator(current):
            live = self._live(current)
            if not live:
                return None, None
            return live, dict(live)
        return self._mutate(_store_doc_id("access", employee), mutator)

    def drop(self, employee):
        self._mutate(_store_doc_id("access", employee), lambda _current: (None, True))

    def issue_ticket(self, employee):
        ticket = pysecrets.token_urlsafe(32)
        data = {"employee": _cell(employee), "exp": self._clock() + TIMESHEET_MAIL_TICKET_TTL_SEC}
        self._mutate(_store_doc_id("ticket", ticket), lambda _current: (data, True))
        return ticket

    def redeem_ticket(self, ticket):
        def mutator(current):
            live = self._live(current)
            if not live:
                return None, None
            return None, dict(live)
        rec = self._mutate(_store_doc_id("ticket", ticket), mutator)
        if not rec:
            return None
        access = self.get_access(rec.get("employee"))
        if not access:
            return None
        return {
            "employee": rec.get("employee"),
            "provider": access.get("provider"),
            "mailbox_email": access.get("mailbox_email"),
            "exp": access.get("exp"),
            "kind": access.get("kind") or "oauth",
        }

    def consent_metadata(self, employee):
        rec = self.get_access(employee)
        if not rec:
            return None
        return {
            "employee": _cell(employee),
            "provider": rec.get("provider"),
            "mailbox_email": rec.get("mailbox_email"),
            "exp": rec.get("exp"),
            "kind": rec.get("kind") or "oauth",
        }

    def remember_nonce(self, nonce, exp, now=None):
        nonce = _cell(nonce)
        if not nonce:
            return False
        current_time = self._clock() if now is None else float(now)

        def mutator(current):
            live = self._live(current, now=current_time)
            if live:
                return live, False
            return {"exp": float(exp or 0)}, True
        return self._mutate(_store_doc_id("nonce", nonce), mutator)

    def claim_send(self, key, employee, week, content_hash, acknowledge_uncertain=False):
        key = _cell(key)
        if not key:
            return "uncertain"

        def mutator(current):
            now = self._clock()
            rec = dict(current) if current else None
            if rec:
                status = rec.get("status")
                if status == TIMESHEET_MAIL_STATUS_SENT and float(rec.get("exp") or 0) >= now:
                    return rec, "sent"
                if status == TIMESHEET_MAIL_STATUS_UNCERTAIN and float(rec.get("exp") or 0) >= now:
                    if not acknowledge_uncertain:
                        return rec, "uncertain"
                    rec["status"] = "InProgress"
                    rec["exp"] = now + TIMESHEET_MAIL_CLAIM_TTL_SEC
                    return rec, "claimed"
                if status == "InProgress":
                    if float(rec.get("exp") or 0) >= now:
                        return rec, "in_progress"
                    if not acknowledge_uncertain:
                        rec["status"] = TIMESHEET_MAIL_STATUS_UNCERTAIN
                        rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                        return rec, "uncertain"
                    rec["status"] = "InProgress"
                    rec["exp"] = now + TIMESHEET_MAIL_CLAIM_TTL_SEC
                    return rec, "claimed"
            created = {
                "status": "InProgress",
                "employee": _cell(employee),
                "week": _cell(week),
                "content_hash": _cell(content_hash),
                "exp": now + TIMESHEET_MAIL_CLAIM_TTL_SEC,
            }
            return created, "claimed"
        return self._mutate(_store_doc_id("idem", key), mutator)

    def finish_send(self, key, status):
        key = _cell(key)
        if not key:
            return

        def mutator(current):
            now = self._clock()
            if status == TIMESHEET_MAIL_STATUS_DENIED:
                return None, True
            rec = dict(current) if current else {"employee": "", "week": "", "content_hash": ""}
            if status == TIMESHEET_MAIL_STATUS_SENT:
                rec["status"] = TIMESHEET_MAIL_STATUS_SENT
                rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                return rec, True
            if status == TIMESHEET_MAIL_STATUS_UNCERTAIN:
                rec["status"] = TIMESHEET_MAIL_STATUS_UNCERTAIN
                rec["exp"] = now + TIMESHEET_MAIL_IDEMPOTENCY_TTL_SEC
                return rec, True
            if status == TIMESHEET_MAIL_STATUS_DUPLICATE:
                return current, True
            return None, True
        self._mutate(_store_doc_id("idem", key), mutator)


class MailSendUncertain(Exception):
    """The provider may have accepted the message. Do not retry automatically."""


class MailProviderDown(Exception):
    """The provider connection failed before the message was handed off."""


class MailAuthRejected(Exception):
    """SMTP authentication failed. The password must not be included."""


class SecretAccessError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _secret_access_reason(exc):
    text = (type(exc).__name__ + " " + _cell(exc)).lower()
    if "permission" in text or "403" in text or "denied" in text:
        return "permission_denied"
    if "notfound" in text or "not found" in text or "404" in text or isinstance(exc, KeyError):
        return "not_found"
    return "unavailable"


class SecretManagerAppPasswords:
    """Read per-employee SMTP app passwords from Secret Manager at send time.

    An admin creates the secret versions later in Secret Manager. This class
    has no write path and no password-entry form. Values are never logged.
    """

    def __init__(self, project, client=None, prefix=None):
        self.project = _cell(project)
        if not self.project:
            raise ValueError("Secret Manager project id is required.")
        self._client = client
        self.prefix = prefix or TIMESHEET_SMTP_SECRET_PREFIX

    @property
    def client(self):
        if self._client is None:
            try:
                from google.cloud import secretmanager
            except Exception as exc:
                raise SystemExit("google-cloud-secret-manager is not installed.") from exc
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def secret_version_name(self, employee):
        secret_id = timesheet_smtp_secret_id(employee, prefix=self.prefix)
        return "projects/%s/secrets/%s/versions/latest" % (self.project, secret_id)

    def get_password(self, employee):
        name = self.secret_version_name(employee)
        try:
            response = self.client.access_secret_version(request={"name": name})
            data = response.payload.data
        except SecretAccessError:
            raise
        except Exception as exc:
            raise SecretAccessError(_secret_access_reason(exc)) from None
        if isinstance(data, bytes):
            text = data.decode("utf-8")
        else:
            text = _cell(data)
        text = text.strip()
        if not text:
            raise SecretAccessError("not_found")
        return text

    def exists(self, employee):
        try:
            return bool(self.get_password(employee))
        except SecretAccessError:
            return False


def timesheet_smtp_connection_spec(provider, secrets=None):
    """Official Apple or Yahoo SMTP endpoint. Ports are only 587 STARTTLS or 465 SSL."""
    provider = _cell(provider).lower()
    base = TIMESHEET_MAIL_SMTP_SPEC.get(provider)
    if not base:
        raise ValueError("Unsupported SMTP provider.")
    spec = {
        "provider": provider,
        "host": base["host"],
        "port": int(base["port"]),
        "security": "starttls",
    }
    if provider == "yahoo":
        port = 587
        section = timesheet_secret_section(secrets, TIMESHEET_SMTP_SECTION)
        try:
            if section is not None and "yahoo_port" in section:
                port = int(section["yahoo_port"])
        except Exception:
            port = 587
        if port == 465:
            spec["port"] = 465
            spec["security"] = "ssl"
        else:
            spec["port"] = 587
            spec["security"] = "starttls"
    elif provider == "icloud":
        spec["host"] = "smtp.mail.me.com"
        spec["port"] = 587
        spec["security"] = "starttls"
    if spec["host"] not in ("smtp.mail.me.com", "smtp.mail.yahoo.com"):
        raise ValueError("Unsupported SMTP host.")
    if spec["port"] not in (465, 587):
        raise ValueError("Unsupported SMTP port.")
    return spec


def _smtp_deliver(spec, username, password, message, smtp_module=None):
    """TLS SMTP send. iCloud is 587 STARTTLS. Yahoo is 587 STARTTLS or 465 SSL."""
    smtp_module = smtp_module or smtplib
    host = spec["host"]
    port = int(spec["port"])
    security = spec["security"]
    if host not in ("smtp.mail.me.com", "smtp.mail.yahoo.com") or port not in (465, 587):
        raise MailProviderDown()
    context = ssl.create_default_context()
    client = None
    started_send = False
    try:
        if security == "ssl" or port == 465:
            client = smtp_module.SMTP_SSL(host, port, timeout=30, context=context)
            client.login(username, password)
            started_send = True
            client.send_message(message)
        else:
            client = smtp_module.SMTP(host, port, timeout=30)
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            client.login(username, password)
            started_send = True
            client.send_message(message)
    except (MailSendUncertain, MailAuthRejected, MailProviderDown):
        raise
    except (TimeoutError, socket.timeout):
        raise MailSendUncertain()
    except smtplib.SMTPAuthenticationError:
        raise MailAuthRejected()
    except (ConnectionError, OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected):
        if started_send:
            raise MailSendUncertain()
        raise MailProviderDown()
    except smtplib.SMTPException:
        if started_send:
            raise MailSendUncertain()
        raise MailProviderDown()
    finally:
        if client is not None:
            try:
                client.quit()
            except Exception:
                pass


def send_via_smtp(provider, username, password, record, pdf_bytes, filename, mailer=None, to=None, secrets=None):
    """Send the previewed PDF through official TLS SMTP. Password is not returned or logged."""
    provider = _cell(provider).lower()
    if timesheet_mail_auth_mode(provider) != "smtp_app_password":
        raise ValueError("Unsupported SMTP provider.")
    if not password:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The vaulted SMTP app password is missing or revoked.",
        }
    spec = timesheet_smtp_connection_spec(provider, secrets)
    message = build_timesheet_mime(record, pdf_bytes, filename, username, to=to, secrets=secrets)
    deliver = mailer or _smtp_deliver
    try:
        deliver(spec, username, password, message)
    except MailSendUncertain:
        return {
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": "The mail provider did not confirm delivery. Check the Sent folder. The app will not retry automatically.",
        }
    except MailAuthRejected:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The mailbox rejected the vaulted app password.",
        }
    except MailProviderDown:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The mail provider is unavailable.",
        }
    except (TimeoutError, socket.timeout):
        return {
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": "The mail provider did not answer in time. Check the Sent folder. The app will not retry automatically.",
        }
    except Exception as exc:
        uncertain = isinstance(exc, (TimeoutError, socket.timeout))
        return {
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN if uncertain else TIMESHEET_MAIL_STATUS_DENIED,
            "error": sanitize_mail_error(exc, extra=(password, username)),
        }
    return {"status": TIMESHEET_MAIL_STATUS_SENT, "error": ""}


def build_timesheet_mime(record, pdf_bytes, filename, from_email, to=None, secrets=None):
    recipient = timesheet_mail_recipient(secrets)
    if to is not None and _lower_email(to) != recipient:
        raise ValueError("Timesheet email can only be addressed to " + recipient + ".")
    if not pdf_bytes or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("Only the generated timesheet PDF can be attached.")
    if pdf_bytes[:5] != b"%PDF-":
        raise ValueError("Only the generated timesheet PDF can be attached.")
    from_addr = _lower_email(from_email)
    if not from_addr:
        raise ValueError("A bound mailbox address is required.")
    msg = EmailMessage()
    msg["To"] = recipient
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


def timesheet_microsoft_send_payload(record, pdf_bytes, filename, from_email, to=None, secrets=None):
    recipient = timesheet_mail_recipient(secrets)
    if to is not None and _lower_email(to) != recipient:
        raise ValueError("Timesheet email can only be addressed to " + recipient + ".")
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("Only the generated timesheet PDF can be attached.")
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "message": {
            "subject": timesheet_email_subject(record),
            "body": {"contentType": "Text", "content": timesheet_email_body(record)},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
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
            "map, a Gmail mail OAuth client, a separate HTTPS mail callback service, "
            "and (for iCloud or Yahoo) a vaulted SMTP app-password store are configured. "
            "This app does not send mail yet."
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
    recipient = timesheet_mail_recipient(secrets)
    if to is not None and _lower_email(to) != recipient:
        return False, "Timesheet email can only be addressed to " + recipient + "."
    if initials_match is not True:
        return False, "Initial and save this week's current time-sheet content before sending."
    if not consent:
        if timesheet_mail_auth_mode(mailbox["provider"]) == "smtp_app_password":
            return False, (
                "The vaulted SMTP session for this mailbox is not ready. "
                "This app does not ask for a mail password."
            )
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


def timesheet_mail_preview(record, consent=None, filename=None, secrets=None):
    from_email = _lower_email((consent or {}).get("mailbox_email"))
    return {
        "to": timesheet_mail_recipient(secrets),
        "from": from_email,
        "subject": timesheet_email_subject(record),
        "body": timesheet_email_body(record),
        "attachment": filename or "",
        "provider": _cell((consent or {}).get("provider")),
    }


def send_via_provider(provider, access_token, record, pdf_bytes, filename, from_email, http_post=None, to=None, secrets=None):
    """POST the official send API. http_post(url, headers, json=None, timeout=) must be injected or requests."""
    recipient = timesheet_mail_recipient(secrets)
    if to is not None and _lower_email(to) != recipient:
        raise ValueError("Timesheet email can only be addressed to " + recipient + ".")
    if not access_token:
        raise ValueError("Mail authorization is missing.")
    urls = timesheet_provider_urls(provider)
    headers = {"Authorization": "Bearer " + access_token}
    if provider == "gmail":
        mime = build_timesheet_mime(record, pdf_bytes, filename, from_email, to=to, secrets=secrets)
        body = timesheet_gmail_send_payload(mime)
        headers["Content-Type"] = "application/json"
        payload = body
        json_body = payload
    elif provider == "microsoft":
        json_body = timesheet_microsoft_send_payload(record, pdf_bytes, filename, from_email, to=to, secrets=secrets)
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


def _claim_block_result(claim, key):
    if claim == "sent":
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "This exact initialed time sheet was already sent. Change and re-initial the week before sending again.",
            "idempotency_key": key,
        }
    if claim == "uncertain":
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": (
                "A previous send for this week did not get a clear result. Check your Sent folder "
                "before sending again. The app will not retry automatically."
            ),
            "idempotency_key": key,
        }
    if claim == "in_progress":
        return {
            "status": TIMESHEET_MAIL_STATUS_DUPLICATE,
            "error": "Send is already in progress or finished for this week.",
            "idempotency_key": key,
        }
    return {
        "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
        "error": "Send could not be claimed safely. The app will not retry automatically.",
        "idempotency_key": key,
    }


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
    smtp_password=None,
    smtp_mailer=None,
):
    """Send once through the official provider using a server-side token store.

    Never retries automatically on uncertain results. Audit rows and the
    store's atomic employee + week + content-hash claim both block duplicates.
    SMTP app passwords are read only for this call and are not stored.
    """
    employee = user_employee or _cell((record or {}).get("Employee"))
    consent = store.consent_metadata(employee) if store else None
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
    access = store.get_access(employee) if store else None
    provider = _cell((access or {}).get("provider")).lower()
    mode = timesheet_mail_auth_mode(provider)
    if mode == "smtp_app_password":
        if not access or access.get("kind") != "smtp":
            return {"status": TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail authorization is missing or expired.", "idempotency_key": key}
    elif not access or not access.get("access_token"):
        return {"status": TIMESHEET_MAIL_STATUS_DENIED, "error": "Mail authorization is missing or expired.", "idempotency_key": key}
    if store is not None and key and hasattr(store, "claim_send"):
        claim = store.claim_send(
            key,
            employee,
            (record or {}).get("Week Of"),
            (record or {}).get("Content Hash"),
            acknowledge_uncertain=acknowledge_uncertain,
        )
        if claim != "claimed":
            return _claim_block_result(claim, key)
    if in_flight is not None and key:
        in_flight.add(key)
    try:
        if mode == "smtp_app_password":
            try:
                if smtp_password is None:
                    raise SecretAccessError("not_found")
                password = smtp_password(employee) if callable(smtp_password) else smtp_password
            except SecretAccessError as exc:
                if exc.reason == "unavailable":
                    result = {
                        "status": TIMESHEET_MAIL_STATUS_DENIED,
                        "error": "The credential store is unavailable.",
                    }
                else:
                    result = {
                        "status": TIMESHEET_MAIL_STATUS_DENIED,
                        "error": "The vaulted SMTP app password is missing or revoked.",
                    }
            else:
                result = send_via_smtp(
                    provider,
                    access.get("mailbox_email"),
                    password,
                    record,
                    pdf_bytes,
                    filename,
                    mailer=smtp_mailer,
                    to=to,
                    secrets=secrets,
                )
        else:
            result = send_via_provider(
                access["provider"],
                access["access_token"],
                record,
                pdf_bytes,
                filename,
                access["mailbox_email"],
                http_post=http_post,
                to=to,
                secrets=secrets,
            )
    except Exception as exc:
        result = {
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": sanitize_mail_error(exc),
        }
    if store is not None and key and hasattr(store, "finish_send"):
        store.finish_send(key, result.get("status"))
    result["idempotency_key"] = key
    result["from"] = (access or {}).get("mailbox_email") or ""
    result["provider"] = provider
    result["to"] = timesheet_mail_recipient(secrets)
    result.pop("access_token", None)
    result.pop("password", None)
    if (
        mode == "oauth"
        and result.get("status") == TIMESHEET_MAIL_STATUS_DENIED
        and result.get("http_status") in (401, 403)
        and store is not None
    ):
        store.drop(employee)
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


def compact_mail_audit(audit_records, employee):
    """Audit fields the send gate needs. No mailbox addresses or tokens."""
    employee = _cell(employee)
    compact = []
    for row in audit_records or []:
        if not isinstance(row, dict):
            continue
        if employee and _cell(row.get("Employee")) not in ("", employee):
            continue
        compact.append({
            "Employee": _cell(row.get("Employee")) or employee,
            "Week Of": _cell(row.get("Week Of")),
            "Content Hash": _cell(row.get("Content Hash")),
            "Status": _cell(row.get("Status")),
            "Idempotency Key": _cell(row.get("Idempotency Key")),
        })
    return compact[-50:]


def _mail_api_url(secrets, path):
    base = timesheet_mail_backend_base(secrets)
    if not base:
        raise ValueError("The mail callback service is not configured.")
    return base + path


def _default_json_post(url, payload, timeout=35):
    import requests
    response = requests.post(
        url,
        json=payload,
        timeout=timeout,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    return response.status_code, response.text


def post_mail_api(path, signed_token, secrets, extra=None, http_post=None, timeout=35):
    """One POST to the callback service. A transport error is Uncertain and is not retried."""
    body = {"token": signed_token}
    if extra:
        body.update(extra)
    poster = http_post or _default_json_post
    try:
        status, text = poster(_mail_api_url(secrets, path), body, timeout)
    except Exception as exc:
        return {
            "ok": False,
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": "The mail service did not answer. Check the Sent folder before trying again. The app will not retry automatically.",
            "transport_error": sanitize_mail_error(exc),
        }
    try:
        data = json.loads(text or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.pop("access_token", None)
    data.pop("password", None)
    data.pop("pdf_base64", None)
    if status >= 500 or not data:
        return {
            "ok": False,
            "status": TIMESHEET_MAIL_STATUS_UNCERTAIN,
            "error": "The mail service did not return a clear result. The app will not retry automatically.",
            "http_status": status,
        }
    data["http_status"] = status
    if "status" not in data and status >= 400:
        data["status"] = TIMESHEET_MAIL_STATUS_DENIED
        data["ok"] = False
    return data


def redeem_ready_ticket_http(ticket, employee, signin_email, secrets, http_post=None, now=None):
    """Redeem a one-time ready ticket. The response is consent metadata, never an access token."""
    secret = timesheet_mail_state_secret(secrets)
    if not secret or not _cell(ticket):
        return None
    signed = timesheet_sign_api_request({
        "kind": "redeem",
        "ticket": _cell(ticket),
        "employee": _cell(employee),
        "signin_email": _lower_email(signin_email),
    }, secret, now=now)
    result = post_mail_api("/timesheet-mail/redeem", signed, secrets, http_post=http_post)
    consent = result.get("consent") if isinstance(result, dict) else None
    if not isinstance(consent, dict):
        return None
    consent.pop("access_token", None)
    consent.pop("password", None)
    if _cell(consent.get("employee")) != _cell(employee):
        return None
    return consent


def open_smtp_session_http(employee, signin_email, secrets, http_post=None, now=None):
    """Ask the backend to confirm a vaulted SMTP secret exists. The password is not returned."""
    secret = timesheet_mail_state_secret(secrets)
    if not secret:
        return None
    signed = timesheet_sign_api_request({
        "kind": "smtp-session",
        "employee": _cell(employee),
        "signin_email": _lower_email(signin_email),
    }, secret, now=now)
    result = post_mail_api("/timesheet-mail/smtp-session", signed, secrets, http_post=http_post)
    consent = result.get("consent") if isinstance(result, dict) else None
    if not isinstance(consent, dict):
        return None
    consent.pop("access_token", None)
    consent.pop("password", None)
    return consent


def submit_signed_timesheet_send(
    record,
    pdf_bytes,
    filename,
    *,
    secrets,
    signin_email,
    user_employee,
    preview_pdf_bytes=None,
    initials_match=None,
    saved_content_hash=None,
    audit_records=None,
    acknowledge_uncertain=False,
    http_post=None,
    now=None,
):
    """What the Send button calls. One signed request. Timeout becomes Uncertain with no retry.

    The signed preview hash and the PDF bytes must match. Saved initials must
    still match the current content hash. Another employee's identity is rejected
    before the request is signed.
    """
    employee = _cell((record or {}).get("Employee"))
    key = timesheet_send_idempotency_key(record) if record else ""
    if not employee or _cell(user_employee) != employee:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Only the signed-in employee can send their own initialed time sheet. This app does not send mail for others.",
            "idempotency_key": key,
        }
    if initials_match is not True:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Initial and save this week's current time-sheet content before sending.",
            "idempotency_key": key,
        }
    current_hash = _cell((record or {}).get("Content Hash"))
    saved_hash = _cell(saved_content_hash or current_hash)
    if not current_hash or saved_hash != current_hash:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "Initial and save this week's current time-sheet content before sending.",
            "idempotency_key": key,
        }
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The official generated timesheet PDF is required.",
            "idempotency_key": key,
        }
    preview = pdf_bytes if preview_pdf_bytes is None else preview_pdf_bytes
    pdf_hash = timesheet_pdf_sha256(pdf_bytes)
    preview_hash = timesheet_pdf_sha256(preview)
    if preview_hash != pdf_hash:
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "The PDF no longer matches the preview.",
            "idempotency_key": key,
        }
    secret = timesheet_mail_state_secret(secrets)
    if not secret or not timesheet_mail_backend_base(secrets):
        return {
            "status": TIMESHEET_MAIL_STATUS_DENIED,
            "error": "In-app sending is disabled until the mail callback service is configured. This app does not send mail yet.",
            "idempotency_key": key,
        }
    signed = timesheet_sign_api_request({
        "kind": "send",
        "employee": employee,
        "signin_email": _lower_email(signin_email),
        "week": _cell((record or {}).get("Week Of")),
        "content_hash": current_hash,
        "saved_content_hash": saved_hash,
        "initials": _cell((record or {}).get("Initials")),
        "initials_match": True,
        "entry_id": _cell((record or {}).get("Entry ID")),
        "filename": _cell(filename),
        "pdf_sha256": pdf_hash,
        "preview_sha256": preview_hash,
        "acknowledge_uncertain": bool(acknowledge_uncertain),
        "audit": compact_mail_audit(audit_records, employee),
    }, secret, now=now)
    result = post_mail_api(
        "/timesheet-mail/send",
        signed,
        secrets,
        extra={"pdf_base64": base64.b64encode(pdf_bytes).decode("ascii")},
        http_post=http_post,
    )
    result.setdefault("idempotency_key", key)
    result.setdefault("status", TIMESHEET_MAIL_STATUS_UNCERTAIN)
    result.pop("access_token", None)
    result.pop("password", None)
    return result
