"""Employee PIN hashes and the long-lived device cookie for time sheets.

No Streamlit imports. The app stores only salted scrypt hashes in
[timesheet_pins] and signs a device cookie with [timesheet_pin].cookie_secret.
The PIN itself is never written to a cookie, a sheet, or a log.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

# Same employee keys as [timesheet_employees] and [timesheet_employee_mail].
# Ron Cline has no time sheet. Anthony Root has his own form.
PIN_EMPLOYEES = (
    "Carl Mulvaney",
    "Anthony Root",
    "Barry Markham",
    "Robert Rackley",
    "Gary Grant",
    "Skylar Fingerle",
)

PINS_SECTION = "timesheet_pins"
PIN_SECTION = "timesheet_pin"
COOKIE_NAME = "cvh_timesheet_device"
COOKIE_VERSION = 1
# Six years. Longer than five, and refreshed on later visits so a browser
# that caps cookie lifetime (Chrome's 400-day cap) can keep the phone remembered.
COOKIE_TTL_SEC = 6 * 365 * 24 * 60 * 60
COOKIE_REFRESH_AFTER_SEC = 30 * 24 * 60 * 60
MIN_COOKIE_SECRET_LEN = 16
MAX_ATTEMPTS = 5
MIN_PIN_LENGTH = 4
MAX_PIN_LENGTH = 64

SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_LEN = 16


def employee_allowed(name):
    return _cell(name) in PIN_EMPLOYEES


def _cell(value):
    if value is None:
        return ""
    return str(value).strip()


def _section(secrets, name):
    if secrets is None:
        return None
    try:
        if name in secrets:
            return secrets[name]
    except Exception:
        return None
    return None


def cookie_secret(secrets):
    """Return the HMAC secret, or empty when it is missing or too short."""
    section = _section(secrets, PIN_SECTION)
    if section is None:
        return ""
    try:
        value = section["cookie_secret"] if "cookie_secret" in section else ""
    except Exception:
        return ""
    text = value if isinstance(value, str) else _cell(value)
    if len(text.strip()) < MIN_COOKIE_SECRET_LEN:
        return ""
    return text


def pin_hash_for(secrets, employee):
    """The stored scrypt hash for one employee, or empty."""
    if not employee_allowed(employee):
        return ""
    section = _section(secrets, PINS_SECTION)
    if section is None:
        return ""
    try:
        if employee not in section:
            return ""
        value = section[employee]
    except Exception:
        return ""
    text = _cell(value)
    if not text.startswith("scrypt$"):
        return ""
    return text


def employee_pin_ready(secrets, employee):
    """True when this employee has a hash and the cookie secret exists."""
    return bool(cookie_secret(secrets) and pin_hash_for(secrets, employee))


def normalize_pin(pin):
    if not isinstance(pin, str):
        pin = "" if pin is None else str(pin)
    pin = pin.strip()
    if not pin or len(pin) > MAX_PIN_LENGTH:
        return ""
    return pin


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text):
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def make_pin_hash(pin, salt=None):
    """Salted scrypt hash. The PIN is not recoverable from the result."""
    normalized = normalize_pin(pin)
    if len(normalized) < MIN_PIN_LENGTH:
        raise ValueError("PIN must be at least %d characters." % MIN_PIN_LENGTH)
    if salt is None:
        salt = secrets.token_bytes(SALT_LEN)
    if not isinstance(salt, (bytes, bytearray)) or len(salt) < 8:
        raise ValueError("PIN salt is too short.")
    digest = hashlib.scrypt(
        normalized.encode("utf-8"),
        salt=bytes(salt),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "scrypt$%d$%d$%d$%s$%s" % (SCRYPT_N, SCRYPT_R, SCRYPT_P, _b64(salt), _b64(digest))


def _parse_pin_hash(stored):
    parts = _cell(stored).split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = _b64decode(parts[4])
        expected = _b64decode(parts[5])
    except Exception:
        return None
    # Cap cost so a bad secret cannot stall the app.
    if n < 2 ** 14 or n > 2 ** 15 or (n & (n - 1)) != 0:
        return None
    if r != SCRYPT_R or p != SCRYPT_P:
        return None
    if not 8 <= len(salt) <= 64 or not 16 <= len(expected) <= 64:
        return None
    return n, r, p, salt, expected


def verify_pin_hash(pin, stored):
    parsed = _parse_pin_hash(stored)
    normalized = normalize_pin(pin)
    if not parsed or not normalized:
        return False
    n, r, p, salt, expected = parsed
    try:
        digest = hashlib.scrypt(
            normalized.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
    except Exception:
        return False
    return hmac.compare_digest(digest, expected)


def verify_employee_pin(employee, pin, secrets):
    stored = pin_hash_for(secrets, employee)
    if not stored:
        return False
    return verify_pin_hash(pin, stored)


def attempt_pin(employee, pin, secrets, failures):
    """Check one PIN. Returns (status, failures).

    status is not_configured, locked, empty, ok, or denied.
    A locked session does not check another PIN.
    """
    failures = int(failures or 0)
    if not employee_pin_ready(secrets, employee):
        return "not_configured", failures
    if failures >= MAX_ATTEMPTS:
        return "locked", failures
    if not normalize_pin(pin):
        return "empty", failures
    if verify_employee_pin(employee, pin, secrets):
        return "ok", 0
    failures += 1
    if failures >= MAX_ATTEMPTS:
        return "locked", failures
    return "denied", failures


def _secret_bytes(secret):
    return _cell(secret).encode("utf-8")


def sign_device_cookie(employee, secret, now=None, ttl=None):
    """HMAC-signed device cookie. Payload is the employee key and expiry, never the PIN."""
    name = _cell(employee)
    if not employee_allowed(name):
        raise ValueError("That employee does not have a time sheet.")
    if len(_cell(secret).strip()) < MIN_COOKIE_SECRET_LEN:
        raise ValueError("Timesheet PIN cookie secret is not configured.")
    issued = int(now if now is not None else time.time())
    lifetime = int(COOKIE_TTL_SEC if ttl is None else ttl)
    if lifetime <= 0:
        raise ValueError("Device cookie lifetime must be positive.")
    body = {
        "v": COOKIE_VERSION,
        "employee": name,
        "iat": issued,
        "exp": issued + lifetime,
    }
    raw = base64.urlsafe_b64encode(
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")
    sig = hmac.new(_secret_bytes(secret), raw.encode("ascii"), hashlib.sha256).hexdigest()
    return raw + "." + sig


def normalize_cookie_token(value):
    text = _cell(value)
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    try:
        from urllib.parse import unquote
        text = unquote(text)
    except Exception:
        pass
    return text.strip()


def device_cookie_claims(token, secret, now=None):
    """Return the signed claims, or None when the cookie is missing, expired, or forged."""
    text = normalize_cookie_token(token)
    if not secret or not text or "." not in text:
        return None
    raw, sig = text.rsplit(".", 1)
    expected = hmac.new(_secret_bytes(secret), raw.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        body = json.loads(_b64decode(raw))
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    if int(body.get("v") or 0) != COOKIE_VERSION:
        return None
    employee = _cell(body.get("employee"))
    if not employee_allowed(employee):
        return None
    try:
        exp = int(body.get("exp") or 0)
        iat = int(body.get("iat") or 0)
    except Exception:
        return None
    if exp < int(now if now is not None else time.time()) or iat <= 0 or iat > exp:
        return None
    body["employee"] = employee
    body["exp"] = exp
    body["iat"] = iat
    return body


def verify_device_cookie(token, secret, now=None):
    claims = device_cookie_claims(token, secret, now=now)
    if not claims:
        return None
    return claims["employee"]
