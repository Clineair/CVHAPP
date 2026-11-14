"""Send every timesheet from the one company mailbox.

Employees never authorize Google and never type a mail password. The
Streamlit app sends when [timesheet_company_mail] exists and enabled is
true. The documented default backend is "gmail_smtp" (smtp.gmail.com:465 SSL).
"smtp" is Office 365 STARTTLS and "graph" is Microsoft Graph client
credentials. The From address defaults to the company Gmail mailbox and can
be changed with the sender secret. The Cloud Run callback is not used.
"""
from __future__ import annotations

import base64
import hashlib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

import timesheet_mail as tm

DEFAULT_SENDER = "clineair891@gmail.com"
COMPANY_SECTION = "timesheet_company_mail"
NOT_READY_MESSAGE = "email not set up yet - ask the office"
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
OFFICE_SMTP_HOST = "smtp.office365.com"
OFFICE_SMTP_PORT = 587
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
DISPLAY_SUFFIX = "via CVH Timesheets"


def _cell(value):
    return tm._cell(value)


def _lower_email(value):
    return tm._lower_email(value)


def _section(secrets):
    return tm.timesheet_secret_section(secrets, COMPANY_SECTION)


def _flag_enabled(section):
    if section is None:
        return False
    try:
        if "enabled" not in section:
            return False
        value = section["enabled"]
    except Exception:
        return False
    if value is True:
        return True
    return _cell(value).lower() == "true"


def _backend(section):
    if section is None:
        return ""
    try:
        if "backend" not in section:
            return ""
        name = _cell(section["backend"]).lower()
    except Exception:
        return ""
    if name in ("gmail_smtp", "smtp", "graph"):
        return name
    return ""


def mailbox_address(secrets=None):
    """From address. `sender` overrides the default Gmail mailbox when it is a valid address."""
    section = _section(secrets)
    if section is not None:
        try:
            if "sender" in section:
                return _lower_email(section["sender"])
        except Exception:
            return ""
    return DEFAULT_SENDER


def _secret_text(section, key):
    if section is None:
        return ""
    try:
        if key not in section:
            return ""
        return _cell(section[key])
    except Exception:
        return ""


def _login_username(section, address):
    username = _lower_email(_secret_text(section, "username"))
    if not username:
        return address
    if username != address:
        return ""
    return username


def company_mail_ready(secrets=None):
    """True only when enabled is true and the selected backend has its secrets."""
    section = _section(secrets)
    if not _flag_enabled(section):
        return False
    address = mailbox_address(secrets)
    if not address:
        return False
    backend = _backend(section)
    if backend in ("gmail_smtp", "smtp"):
        return bool(_login_username(section, address) and _secret_text(section, "password"))
    if backend == "graph":
        return bool(
            _secret_text(section, "tenant_id")
            and _secret_text(section, "client_id")
            and _secret_text(section, "client_secret")
        )
    return False


def company_backend(secrets=None):
    if not company_mail_ready(secrets):
        return ""
    return _backend(_section(secrets))


def display_name(employee):
    name = _cell(employee) or "Employee"
    return name + " " + DISPLAY_SUFFIX


def from_header(employee, secrets=None):
    return formataddr((display_name(employee), mailbox_address(secrets)))


def employee_reply_to(employee, secrets=None):
    """Employee address for Reply-To, when one is already configured.

    Prefer [timesheet_employee_mail], then [timesheet_employees]. Missing
    data does not block sending.
    """
    mailbox = tm.timesheet_mailbox_for_employee(employee, secrets)
    if mailbox and mailbox.get("email"):
        return mailbox["email"]
    section = tm.timesheet_secret_section(secrets, tm.TIMESHEET_SIGNIN_SECTION)
    if section is None:
        return ""
    name = _cell(employee)
    try:
        if name not in section:
            return ""
        value = section[name]
    except Exception:
        return ""
    if isinstance(value, str) or not hasattr(value, "keys"):
        return _lower_email(value)
    return ""


UPDATED_COPY_SUFFIX = " (updated copy)"
RESEND_COOLDOWN_SECONDS = 90
RESEND_BLOCKED_MESSAGE = "An updated copy was just sent. Wait a minute before sending another."


def email_subject(record, updated_copy=False):
    employee = _cell((record or {}).get("Employee"))
    week = _cell((record or {}).get("Week Of"))
    subject = "CVH Weekly Time Sheet — " + employee + " — week of " + week
    if updated_copy:
        subject += UPDATED_COPY_SUFFIX
    return subject


def email_body(record, updated_copy=False):
    employee = _cell((record or {}).get("Employee"))
    week = _cell((record or {}).get("Week Of"))
    note = (
        "(updated copy) This replaces the time sheet sent earlier for this week. "
        "The hours are the same. Please use this one.\n\n"
    ) if updated_copy else ""
    return (
        "Patti,\n\n"
        + note
        + "Please find the weekly time sheet for " + employee + " for the week of "
        + week + " attached.\n\n"
        "This PDF was generated by the CVH Employee Tool. " + employee
        + " reviewed it and pressed Send. It was sent from the company mailbox.\n\n"
        + employee + "\n"
    )


def build_message(record, pdf_bytes, filename, secrets=None, updated_copy=False):
    """MIME message from the company mailbox. Does not send it."""
    recipient = tm.timesheet_mail_recipient(secrets)
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("The official generated timesheet PDF is required.")
    employee = _cell((record or {}).get("Employee"))
    message = EmailMessage()
    message["To"] = recipient
    message["From"] = from_header(employee, secrets)
    reply = employee_reply_to(employee, secrets)
    if reply:
        message["Reply-To"] = reply
    message["Subject"] = email_subject(record, updated_copy)
    message.set_content(email_body(record, updated_copy))
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=_cell(filename))
    return message


def graph_payload(record, pdf_bytes, filename, secrets=None, updated_copy=False):
    """Microsoft Graph sendMail body. The PDF is only in contentBytes."""
    recipient = tm.timesheet_mail_recipient(secrets)
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        raise ValueError("The official generated timesheet PDF is required.")
    employee = _cell((record or {}).get("Employee"))
    payload = {
        "message": {
            "subject": email_subject(record, updated_copy),
            "body": {"contentType": "Text", "content": email_body(record, updated_copy)},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "from": {"emailAddress": {"address": mailbox_address(secrets), "name": display_name(employee)}},
            "attachments": [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": _cell(filename),
                "contentType": "application/pdf",
                "contentBytes": base64.b64encode(pdf_bytes).decode("ascii"),
            }],
        },
        "saveToSentItems": True,
    }
    reply = employee_reply_to(employee, secrets)
    if reply:
        payload["message"]["replyTo"] = [{"emailAddress": {"address": reply}}]
    return payload


def _deny(message, key=""):
    return {
        "status": tm.TIMESHEET_MAIL_STATUS_DENIED,
        "error": message,
        "idempotency_key": key,
        "provider": "",
        "to": "",
        "from": "",
    }


ALREADY_SENT_MESSAGE = (
    "This exact initialed time sheet was already sent. Change and re-initial the week before sending again."
)


def _same_week_content(row, record):
    return (
        _cell(row.get("Employee")) == _cell(record.get("Employee"))
        and _cell(row.get("Week Of")) == _cell(record.get("Week Of"))
        and _cell(row.get("Content Hash")) == _cell(record.get("Content Hash"))
    )


def sent_count(audit_records, record):
    """How many Sent rows exist for this employee, week and hour/initials content."""
    return sum(
        1 for row in audit_records or []
        if _cell(row.get("Status")) == tm.TIMESHEET_MAIL_STATUS_SENT and _same_week_content(row, record or {})
    )


def resend_idempotency_key(record, audit_records):
    """Distinct key per resend, so each one gets its own audit row."""
    base = tm.timesheet_send_idempotency_key(record)
    return hashlib.sha256((base + "|resend|" + str(sent_count(audit_records, record))).encode("utf-8")).hexdigest()


def _parse_audit_time(text):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    raw = _cell(text)[:19]
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    except ValueError:
        return None


def resend_too_soon(audit_records, record, now=None):
    """True when a Sent row for this content is newer than the cooldown (double-tap guard)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = now or datetime.now(tz=ZoneInfo("America/Los_Angeles"))
    for row in audit_records or []:
        if _cell(row.get("Status")) != tm.TIMESHEET_MAIL_STATUS_SENT or not _same_week_content(row, record or {}):
            continue
        when = _parse_audit_time(row.get("Timestamp"))
        if when is not None and 0 <= (now - when).total_seconds() < RESEND_COOLDOWN_SECONDS:
            return True
    return False


def send_gates(
    record,
    *,
    user_employee=None,
    secrets=None,
    initials_match=None,
    access_allowed=None,
    pdf_bytes=None,
    filename=None,
    audit_records=None,
    acknowledge_uncertain=False,
    saved_content_hash=None,
    allow_resend=False,
    now=None,
):
    """Return (ok, reason). Does not open a network connection.

    allow_resend lets a week that was already sent go out again as an
    "(updated copy)". Every other gate still applies.
    """
    if not company_mail_ready(secrets):
        return False, NOT_READY_MESSAGE
    if not record:
        return False, "A time sheet is required."
    employee = _cell(record.get("Employee"))
    if access_allowed is not True or _cell(user_employee) != employee:
        return False, "Only the PIN-verified employee can send their own initialed time sheet."
    if initials_match is not True:
        return False, "Initial and save this week's current time-sheet content before sending."
    current_hash = _cell(record.get("Content Hash"))
    if saved_content_hash is not None and _cell(saved_content_hash) != current_hash:
        return False, "Initial and save this week's current time-sheet content before sending."
    if not pdf_bytes or pdf_bytes[:5] != b"%PDF-" or not _cell(filename).lower().endswith(".pdf"):
        return False, "The official generated timesheet PDF is required."
    if tm.timesheet_already_sent(audit_records, record):
        if not allow_resend:
            return False, ALREADY_SENT_MESSAGE
        if resend_too_soon(audit_records, record, now=now):
            return False, RESEND_BLOCKED_MESSAGE
    if tm.timesheet_uncertain_send(audit_records, record) and not acknowledge_uncertain:
        return False, (
            "A previous send for this week did not get a clear result. Check the company Sent folder "
            "before sending again. The app will not retry automatically."
        )
    return True, ""


def can_send(*args, **kwargs):
    ok, _reason = send_gates(*args, **kwargs)
    return ok


def block_reason(*args, **kwargs):
    _ok, reason = send_gates(*args, **kwargs)
    return reason or "Review the message, then press Send."


def _default_gmail_smtp_send(username, password, message):
    """Gmail SSL on port 465. The password is a Google app password."""
    import smtplib
    with smtplib.SMTP_SSL(
        GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30, context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)


def _default_office_smtp_send(username, password, message):
    """Office 365 STARTTLS on port 587."""
    import smtplib
    with smtplib.SMTP(OFFICE_SMTP_HOST, OFFICE_SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


def _default_http_post(url, *, json_body=None, form=None, headers=None, timeout=30):
    import requests
    response = requests.post(
        url,
        json=json_body,
        data=form,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
    return response.status_code, response.text


def _graph_send(section, payload, http_post):
    tenant = _secret_text(section, "tenant_id")
    client_id = _secret_text(section, "client_id")
    client_secret = _secret_text(section, "client_secret")
    token_url = "https://login.microsoftonline.com/" + quote(tenant, safe="") + "/oauth2/v2.0/token"
    status, text = http_post(
        token_url,
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": GRAPH_SCOPE,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    if status in (401, 400, 403):
        return tm.TIMESHEET_MAIL_STATUS_DENIED, "The company mailbox app was rejected. Ask the office."
    if status != 200:
        return tm.TIMESHEET_MAIL_STATUS_UNCERTAIN, "The company mailbox did not return a clear result. The app will not retry automatically."
    try:
        import json
        token = json.loads(text or "{}").get("access_token") or ""
    except Exception:
        token = ""
    if not token:
        return tm.TIMESHEET_MAIL_STATUS_DENIED, "The company mailbox app was rejected. Ask the office."
    sender = mailbox_address({"timesheet_company_mail": section}) if section is not None else ""
    if not sender:
        return tm.TIMESHEET_MAIL_STATUS_DENIED, "The company mailbox is not set up. Ask the office."
    send_url = "https://graph.microsoft.com/v1.0/users/" + quote(sender, safe="@") + "/sendMail"
    send_status, _body = http_post(
        send_url,
        json_body=payload,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        timeout=30,
    )
    if send_status in (200, 202):
        return tm.TIMESHEET_MAIL_STATUS_SENT, ""
    if send_status in (401, 403):
        return tm.TIMESHEET_MAIL_STATUS_DENIED, "The company mailbox rejected the send. Ask the office."
    if send_status >= 500 or send_status == 0:
        return tm.TIMESHEET_MAIL_STATUS_UNCERTAIN, "The company mailbox did not return a clear result. The app will not retry automatically."
    return tm.TIMESHEET_MAIL_STATUS_DENIED, "The company mailbox did not accept the time sheet."


def send_company_timesheet(
    record,
    pdf_bytes,
    filename,
    *,
    secrets,
    user_employee,
    initials_match,
    saved_content_hash=None,
    audit_records=None,
    acknowledge_uncertain=False,
    access_allowed=True,
    smtp_send=None,
    http_post=None,
    allow_resend=False,
    now=None,
):
    """Send one timesheet from the company mailbox. Inject smtp_send or http_post in tests.

    Does not call the Cloud Run callback. Does not ask the employee for consent.
    """
    key = tm.timesheet_send_idempotency_key(record) if record else ""
    updated_copy = bool(
        allow_resend and record and tm.timesheet_already_sent(audit_records, record)
    )
    if updated_copy:
        key = resend_idempotency_key(record, audit_records)
    ok, reason = send_gates(
        record,
        user_employee=user_employee,
        secrets=secrets,
        initials_match=initials_match,
        access_allowed=access_allowed,
        pdf_bytes=pdf_bytes,
        filename=filename,
        audit_records=audit_records,
        acknowledge_uncertain=acknowledge_uncertain,
        saved_content_hash=saved_content_hash,
        allow_resend=allow_resend,
        now=now,
    )
    if not ok:
        result = _deny(reason, key)
        result["to"] = tm.timesheet_mail_recipient(secrets)
        result["from"] = mailbox_address(secrets)
        return result
    section = _section(secrets)
    backend = _backend(section)
    address = mailbox_address(secrets)
    recipient = tm.timesheet_mail_recipient(secrets)
    try:
        if backend in ("gmail_smtp", "smtp"):
            message = build_message(record, pdf_bytes, filename, secrets, updated_copy)
            username = _login_username(section, address)
            password = _secret_text(section, "password")
            if smtp_send is not None:
                transport = smtp_send
            elif backend == "gmail_smtp":
                transport = _default_gmail_smtp_send
            else:
                transport = _default_office_smtp_send
            transport(username, password, message)
            status = tm.TIMESHEET_MAIL_STATUS_SENT
            error = ""
        else:
            payload = graph_payload(record, pdf_bytes, filename, secrets, updated_copy)
            poster = http_post or _default_http_post
            status, error = _graph_send(section, payload, poster)
    except Exception as exc:
        secret_bits = (
            _secret_text(section, "password"),
            _secret_text(section, "client_secret"),
        )
        text = tm.sanitize_mail_error(exc, extra=secret_bits)
        lowered = text.lower()
        if "535" in lowered or "authentication" in lowered or "auth" in lowered:
            status = tm.TIMESHEET_MAIL_STATUS_DENIED
            error = "The company mailbox rejected the login. Ask the office."
        elif isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            status = tm.TIMESHEET_MAIL_STATUS_UNCERTAIN
            error = "The company mailbox did not answer in time. Check the Sent folder. The app will not retry automatically."
        else:
            status = tm.TIMESHEET_MAIL_STATUS_UNCERTAIN
            error = "The company mailbox did not return a clear result. The app will not retry automatically."
        for secret in secret_bits:
            if secret and secret in (error or ""):
                error = error.replace(secret, "[redacted]")
    return {
        "status": status,
        "error": error,
        "idempotency_key": key,
        "provider": backend,
        "to": recipient,
        "from": address,
        "updated_copy": updated_copy,
    }
