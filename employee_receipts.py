"""Employee receipts: photo read-back, the Receipts tab, totals, and Patti's summary mail.

No Streamlit imports, so tests and the bi-weekly script can use it directly.
The Streamlit page lives in app.py (show_employee_receipts).

Storage
- Photos and PDFs go to Google Drive through the receipts Apps Script web app
  (apps_script/receipt_upload), one subfolder per employee, so the original is
  kept for an audit. The sheet row links to that Drive file.
- One row per receipt in the "Receipts" tab of the CVH FRAT Log spreadsheet.
  The tab is created on the first save. No other tab is written, and the FRAT
  log header is never touched.

Mail
- The summary goes from the company Gmail mailbox (clineair891@gmail.com,
  [timesheet_company_mail], Gmail app password) to Patti
  (patti@centralvalleyheli.com, or [timesheet_mail].recipient).
- Automatic bi-weekly sending is OFF unless [receipts_mail].auto_send = true.
"""
from __future__ import annotations

import base64
import hashlib
import io
import re
import ssl
import uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from zoneinfo import ZoneInfo

import timesheet_company_mail as company_mail
import timesheet_mail as tm

PACIFIC = ZoneInfo("America/Los_Angeles")

# ── Two menus. Edit these lists to add, remove, or reorder choices. ──
# Job: who the receipt is charged to. The first three match the timesheet hour columns.
RECEIPT_JOBS = (
    "CVH",
    "BNSF",
    "Forestry",
    "Other",
)
# Expense type: what was bought.
RECEIPT_EXPENSE_TYPES = (
    "Fuel",
    "Parts",
    "Meals",
    "Lodging",
    "Supplies",
    "Other",
)

# People who may open the "Receipts summary" office page (EMPLOYEES -> Receipts summary)
# after their PIN. Patti is an office PIN user (timesheet_pin.PIN_OFFICE_USERS), not an employee.
RECEIPTS_OFFICE_USERS = ("Ron Cline", "Patti")

RECEIPTS_SHEET_TITLE = "Receipts"
RECEIPTS_COLUMNS = [
    "Saved At",
    "Entry ID",
    "Employee",
    "Date",
    "Amount",
    "Receipt Number",
    "Vendor",
    "Purpose",
    "Job",
    "Expense Type",
    "Photo Link",
    "Photo File",
    "Notes",
]
RECEIPTS_MAIL_SHEET_TITLE = "Receipts Mail"
RECEIPTS_MAIL_COLUMNS = [
    "Timestamp",
    "Period Start",
    "Period End",
    "Trigger",
    "Sent By",
    "Status",
    "To",
    "From",
    "Receipts",
    "Total",
    "Idempotency Key",
    "Detail",
]

RECEIPT_UPLOAD_SECTION = "receipts"
RECEIPT_MAIL_SECTION = "receipts_mail"
RECEIPT_MAX_BYTES = 15 * 1024 * 1024
RECEIPT_UPLOAD_TYPES = ("jpg", "jpeg", "png", "webp", "heic", "heif", "pdf")
RECEIPT_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
    "pdf": "application/pdf",
}

# Bi-weekly periods run Sunday through Saturday of the following week,
# counted from this Sunday. Change it to line up with the pay period.
RECEIPTS_PERIOD_ANCHOR = date(2026, 11, 15)
RECEIPTS_PERIOD_DAYS = 14

UPLOAD_NOT_SET_UP_NOTE = (
    "Receipt photo storage is not set up yet, so this photo was NOT saved to "
    "Google Drive. Keep the paper receipt and tell the office. Add [receipts] "
    "apps_script_url and upload_token in Streamlit secrets to turn it on."
)
UPLOAD_FAILED_NOTE = (
    "The receipt photo could not be saved to Google Drive. The receipt row was "
    "saved with the file name only. Keep the paper receipt and tell the office."
)
OCR_UNAVAILABLE_NOTE = (
    "This app cannot read photos on this server yet, so fill in the fields by hand."
)
NOT_READ_NOTE = "Could not read this receipt. Fill in the fields by hand."
READ_NOTE = "Filled in from the receipt. Check every field before you save."
MAIL_NOT_READY_MESSAGE = "email not set up yet - ask the office"
DISPLAY_NAME = "CVH Receipts"

STATUS_SENT = tm.TIMESHEET_MAIL_STATUS_SENT
STATUS_DENIED = tm.TIMESHEET_MAIL_STATUS_DENIED
STATUS_UNCERTAIN = tm.TIMESHEET_MAIL_STATUS_UNCERTAIN
STATUS_DUPLICATE = tm.TIMESHEET_MAIL_STATUS_DUPLICATE
STATUS_SKIPPED = "Skipped"


def _cell(value):
    if value is None:
        return ""
    return str(value).strip()


def _section(secrets, name):
    return tm.timesheet_secret_section(secrets, name)


def _flag(section, key):
    if section is None:
        return False
    try:
        if key not in section:
            return False
        value = section[key]
    except Exception:
        return False
    if value is True:
        return True
    return _cell(value).lower() == "true"


def now_pacific():
    return datetime.now(PACIFIC)


def _as_pacific(when):
    if when is None:
        return now_pacific()
    if when.tzinfo is None:
        return when.replace(tzinfo=PACIFIC)
    return when.astimezone(PACIFIC)


def format_saved_at(when=None):
    when = _as_pacific(when)
    return when.strftime("%Y-%m-%d %H:%M:%S ") + (when.tzname() or "PT")


def new_entry_id(when=None):
    when = _as_pacific(when)
    return "RC-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


# ── Amounts and dates ──

_AMOUNT_RE = re.compile(r"(?<![\d.])\$?\s*(\d{1,3}(?:,\d{3})+|\d+)[.,](\d{2})(?!\d)")


def parse_amount(value):
    """Return a float for "$1,234.56", "12.5", or 12; None for blank or bad input."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if value >= 0 else None
    text = _cell(value).replace("$", "").replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 0 or number != number or number > 1_000_000:
        return None
    return round(number, 2)


def format_amount(value):
    number = parse_amount(value)
    if number is None:
        return ""
    return "%.2f" % number


def format_money(value):
    number = parse_amount(value) or 0.0
    return "${:,.2f}".format(number)


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _safe_date(year, month, day):
    try:
        year = int(year)
        if year < 100:
            year += 2000
        result = date(year, int(month), int(day))
    except (TypeError, ValueError):
        return None
    if result.year < 2000 or result.year > 2100:
        return None
    return result


def parse_receipt_date(value):
    """Parse a stored or typed date. Returns a date or None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _cell(value)
    if not text:
        return None
    found = find_dates(text)
    return found[0] if found else None


_DATE_PATTERNS = (
    (re.compile(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b"), ("m", "d", "y")),
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b"), ("M", "d", "y")),
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"), ("d", "M", "y")),
)


def find_dates(text):
    """Every plausible date in text, in the order found."""
    found = []
    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text or ""):
            parts = dict(zip(order, match.groups()))
            month = parts.get("m")
            if "M" in parts:
                month = _MONTHS.get(parts["M"][:4].lower().rstrip(".")) or _MONTHS.get(parts["M"][:3].lower())
                if not month:
                    continue
            parsed = _safe_date(parts.get("y"), month, parts.get("d"))
            if parsed is not None:
                found.append((match.start(), parsed))
    found.sort(key=lambda item: item[0])
    return [d for _pos, d in found]


# ── Reading a receipt ──

_TOTAL_WORDS = re.compile(
    r"\b(grand\s*total|total\s*due|amount\s*due|balance\s*due|total|amount|sale|charged?|visa|mastercard|debit|credit)\b",
    re.I,
)
_NOT_TOTAL_WORDS = re.compile(r"\b(sub\s*-?\s*total|tax|tip|change|cash\s*back|savings?|discount|you\s+saved)\b", re.I)
_NUMBER_RE = re.compile(
    r"\b(?:receipt|invoice|inv|order|trans(?:action)?|ticket|ref(?:erence)?|confirmation|check|chk|auth)"
    r"\s*(?:no\.?|num(?:ber)?|#|id)?\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{2,24})",
    re.I,
)


def _amounts_in(line):
    values = []
    for match in _AMOUNT_RE.finditer(line or ""):
        whole = match.group(1).replace(",", "")
        try:
            values.append(round(float(whole + "." + match.group(2)), 2))
        except ValueError:
            continue
    return values


def find_total(text):
    """Best guess at the receipt total: the last amount on a TOTAL line, else the largest amount."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    best = None
    for idx, line in enumerate(lines):
        if not _TOTAL_WORDS.search(line) or _NOT_TOTAL_WORDS.search(line):
            continue
        amounts = _amounts_in(line)
        if not amounts and idx + 1 < len(lines):
            amounts = _amounts_in(lines[idx + 1])
        if amounts:
            candidate = amounts[-1]
            if best is None or re.search(r"total", line, re.I):
                best = candidate if best is None else max(best, candidate)
    if best is not None:
        return best
    every = [a for line in lines for a in _amounts_in(line)]
    return max(every) if every else None


def find_receipt_number(text):
    for match in _NUMBER_RE.finditer(text or ""):
        token = match.group(1).strip("-")
        if any(ch.isdigit() for ch in token):
            return token
    return ""


def find_vendor(text):
    for line in (text or "").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip(" *-=#|")
        letters = sum(ch.isalpha() for ch in cleaned)
        if letters >= 3 and letters >= len(cleaned) * 0.5 and not find_dates(cleaned):
            return cleaned[:60]
    return ""


def parse_receipt_text(text):
    """Fields read from receipt text. Missing ones are left out."""
    fields = {}
    dates = find_dates(text)
    if dates:
        fields["date"] = dates[0]
    total = find_total(text)
    if total is not None:
        fields["amount"] = "%.2f" % total
    number = find_receipt_number(text)
    if number:
        fields["number"] = number
    vendor = find_vendor(text)
    if vendor:
        fields["vendor"] = vendor
    return fields


def upload_extension(filename, data=b""):
    name = _cell(filename).lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in RECEIPT_MIME_TYPES:
        return ext
    sniffed = sniff_kind(data)
    return sniffed or ""


def sniff_kind(data):
    data = bytes(data or b"")[:16]
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"heif"):
        return "heic"
    return ""


def mime_type_for(ext):
    return RECEIPT_MIME_TYPES.get(_cell(ext).lower(), "application/octet-stream")


def extract_pdf_text(data):
    """Text from a PDF with pypdf, the same reader the BL2 bulletin pre-fill uses."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(bytes(data)))
    parts = []
    for page in reader.pages[:5]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def ocr_available():
    """True when pytesseract and the tesseract program are both installed."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def _prepare_image(data):
    from PIL import Image, ImageOps
    image = Image.open(io.BytesIO(bytes(data)))
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    longest = max(image.size)
    if longest > 2400:
        scale = 2400.0 / longest
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    elif longest < 1000:
        scale = 1000.0 / max(1, longest)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    return ImageOps.autocontrast(image)


def extract_image_text(data):
    import pytesseract
    return pytesseract.image_to_string(_prepare_image(data), config="--psm 6")


def read_receipt(data, filename="", ocr=None, pdf_reader=None):
    """Return (fields, note) for a photo or PDF. Never raises.

    ocr and pdf_reader can be injected in tests.
    """
    data = bytes(data or b"")
    if not data:
        return {}, ""
    ext = upload_extension(filename, data)
    try:
        if ext == "pdf":
            text = (pdf_reader or extract_pdf_text)(data)
        elif ext in ("heic", "heif"):
            return {}, "This phone saved the photo as HEIC, which the app cannot read. " + NOT_READ_NOTE
        else:
            if ocr is None:
                if not ocr_available():
                    return {}, OCR_UNAVAILABLE_NOTE
                ocr = extract_image_text
            text = ocr(data)
    except Exception:
        return {}, NOT_READ_NOTE
    fields = parse_receipt_text(text or "")
    if not fields:
        return {}, NOT_READ_NOTE
    return fields, READ_NOTE


def fingerprint(data):
    data = bytes(data or b"")
    if not data:
        return ""
    return hashlib.sha256(data).hexdigest()[:16]


# ── Drive upload through the receipts Apps Script ──

def upload_config(secrets):
    """Return (apps_script_url, upload_token) or ("", ""). Never logs the values."""
    section = _section(secrets, RECEIPT_UPLOAD_SECTION)
    if section is None:
        return "", ""
    try:
        url = _cell(section["apps_script_url"]) if "apps_script_url" in section else ""
        token = _cell(section["upload_token"]) if "upload_token" in section else ""
    except Exception:
        return "", ""
    if not url or not token or "replace-with" in url or "replace-with" in token:
        return "", ""
    return url, token


def _token(value, fallback):
    text = "".join(ch if (ch.isalnum() or ch == "-") else "-" for ch in _cell(value))
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-") or fallback


def drive_filename(employee, receipt_date, amount, ext, when=None):
    """YYYY-MM-DD_Employee_Amount_HHMMSS.ext, using the receipt date when known."""
    when = _as_pacific(when)
    day = parse_receipt_date(receipt_date) or when.date()
    money = format_amount(amount).replace(".", "-") or "0-00"
    ext = _cell(ext).lower() or "jpg"
    return "_".join((
        day.isoformat(),
        _token(employee, "Employee"),
        money,
        when.strftime("%H%M%S"),
    )) + "." + ext


def _response_json(resp):
    try:
        payload = resp.json() if hasattr(resp, "json") else None
    except Exception:
        payload = None
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError("Receipt upload was not accepted")
    link = _cell(payload.get("url"))
    file_id = _cell(payload.get("fileId"))
    if link:
        return link
    if file_id:
        return "https://drive.google.com/file/d/" + file_id + "/view"
    raise RuntimeError("Receipt upload did not return a file link")


def _looks_like_json(resp):
    try:
        content_type = _cell((getattr(resp, "headers", None) or {}).get("Content-Type")).lower()
    except Exception:
        content_type = ""
    return "json" in content_type or _cell(getattr(resp, "text", "")).startswith("{")


def upload_via_apps_script(data, filename, mime_type, employee, url, token, session=None):
    """POST the file and follow Apps Script's 302 the same way the BL2 uploader does."""
    import requests as requests_lib
    from urllib.parse import urljoin

    if not data or not filename or not url or not token:
        raise ValueError("A file, filename, Apps Script URL, and token are required")
    if len(data) > RECEIPT_MAX_BYTES:
        raise ValueError("Receipt file is larger than 15 MB")
    payload = {
        "token": token,
        "employee": _cell(employee),
        "filename": filename,
        "mimeType": mime_type,
        "base64": base64.b64encode(bytes(data)).decode("ascii"),
    }
    client = session or requests_lib
    resp = client.post(url, json=payload, timeout=60, allow_redirects=False)
    if _looks_like_json(resp):
        if hasattr(resp, "raise_for_status"):
            resp.raise_for_status()
        return _response_json(resp)
    if getattr(resp, "status_code", None) in (301, 302, 303, 307, 308):
        headers = getattr(resp, "headers", None) or {}
        location = headers.get("Location") or headers.get("location")
        if not location:
            raise RuntimeError("Receipt upload redirected without a Location")
        location = urljoin(url, location)
        if resp.status_code in (307, 308):
            resp = client.post(location, json=payload, timeout=60, allow_redirects=True)
        else:
            resp = client.get(location, timeout=60, allow_redirects=True)
    if hasattr(resp, "raise_for_status"):
        resp.raise_for_status()
    return _response_json(resp)


def store_receipt_file(data, original_name, employee, receipt_date, amount, secrets, when=None, uploader=None, session=None):
    """Return (photo_link, stored_filename, notice). Never raises.

    photo_link is the Drive URL, or empty when the upload is not set up or failed.
    """
    data = bytes(data or b"")
    if not data:
        return "", "", ""
    ext = upload_extension(original_name, data) or "jpg"
    stored = drive_filename(employee, receipt_date, amount, ext, when=when)
    url, token = upload_config(secrets)
    if not url or not token:
        return "", stored, UPLOAD_NOT_SET_UP_NOTE
    if len(data) > RECEIPT_MAX_BYTES:
        return "", stored, UPLOAD_FAILED_NOTE
    try:
        link = _cell((uploader or upload_via_apps_script)(
            data, stored, mime_type_for(ext), employee, url, token, session=session,
        ))
    except Exception:
        return "", stored, UPLOAD_FAILED_NOTE
    if not link.startswith("http"):
        return "", stored, UPLOAD_FAILED_NOTE
    return link, stored, ""


# ── Records ──

def validate_receipt(fields):
    """List of problems that block saving. Empty list means OK."""
    problems = []
    if parse_receipt_date(fields.get("date")) is None:
        problems.append("Enter the receipt date.")
    amount = parse_amount(fields.get("amount"))
    if amount is None or amount <= 0:
        problems.append("Enter the amount, like 42.50.")
    if not _cell(fields.get("purpose")):
        problems.append("Enter the purpose.")
    return problems


def build_receipt_record(employee, fields, job, expense_type, photo_link="", photo_file="", when=None, entry_id=None):
    when = _as_pacific(when)
    job = _cell(job)
    expense_type = _cell(expense_type)
    if job not in RECEIPT_JOBS:
        raise ValueError("Choose a job from the list")
    if expense_type not in RECEIPT_EXPENSE_TYPES:
        raise ValueError("Choose an expense type from the list")
    receipt_date = parse_receipt_date(fields.get("date"))
    return {
        "Saved At": format_saved_at(when),
        "Entry ID": entry_id or new_entry_id(when),
        "Employee": _cell(employee),
        "Date": receipt_date.isoformat() if receipt_date else "",
        "Amount": format_amount(fields.get("amount")),
        "Receipt Number": _cell(fields.get("number")),
        "Vendor": _cell(fields.get("vendor")),
        "Purpose": _cell(fields.get("purpose")),
        "Job": job,
        "Expense Type": expense_type,
        "Photo Link": _cell(photo_link),
        "Photo File": _cell(photo_file),
        "Notes": _cell(fields.get("notes")),
    }


def _worksheet_or_none(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except Exception as exc:
        name = type(exc).__name__
        message = str(exc).lower()
        if name in {"WorksheetNotFound", "NotFound"} or ("worksheet" in message and "not found" in message):
            return None
        raise


def _ensure_tab(spreadsheet, title, columns):
    """Create this tab with a header on first use. Leaves an existing header alone."""
    ws = _worksheet_or_none(spreadsheet, title)
    if ws is None:
        ws = spreadsheet.add_worksheet(title=title, rows=500, cols=max(len(columns), 12))
        ws.append_row(list(columns), value_input_option="RAW")
        return ws, True
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        ws.append_row(list(columns), value_input_option="RAW")
        return ws, True
    return ws, False


def ensure_receipts_worksheet(spreadsheet):
    return _ensure_tab(spreadsheet, RECEIPTS_SHEET_TITLE, RECEIPTS_COLUMNS)


def save_receipt_record(record, spreadsheet):
    """Append one receipt to the Receipts tab only."""
    ws, _created = ensure_receipts_worksheet(spreadsheet)
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Receipts worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Receipts)"


def _records(ws, columns):
    values = ws.get_all_values()
    if not values:
        return []
    header = [_cell(c) for c in values[0]]
    out = []
    for row in values[1:]:
        if not any(_cell(c) for c in row):
            continue
        rec = {c: "" for c in columns}
        for idx, col in enumerate(header):
            if col:
                rec[col] = _cell(row[idx]) if idx < len(row) else ""
        out.append(rec)
    return out


def load_receipts_readonly(spreadsheet, employee=None):
    """Read the Receipts tab without creating it. Optionally one employee only."""
    ws = _worksheet_or_none(spreadsheet, RECEIPTS_SHEET_TITLE)
    if ws is None:
        return []
    records = _records(ws, RECEIPTS_COLUMNS)
    if employee:
        records = [r for r in records if _cell(r.get("Employee")) == _cell(employee)]
    return sort_receipts(records)


def sort_receipts(records):
    """Newest receipt date first, then newest save."""
    return sorted(
        list(records or []),
        key=lambda r: (_cell(r.get("Date")), _cell(r.get("Saved At"))),
        reverse=True,
    )


def saved_date(record):
    """Pacific calendar date the row was saved."""
    return parse_receipt_date(_cell(record.get("Saved At"))[:10])


# ── Periods ──

def period_for(day, anchor=None):
    """(start Sunday, end Saturday) of the bi-weekly period that holds day."""
    anchor = anchor or RECEIPTS_PERIOD_ANCHOR
    if isinstance(day, datetime):
        day = _as_pacific(day).date()
    offset = (day - anchor).days // RECEIPTS_PERIOD_DAYS
    start = anchor + timedelta(days=offset * RECEIPTS_PERIOD_DAYS)
    return start, start + timedelta(days=RECEIPTS_PERIOD_DAYS - 1)


def previous_period(day, anchor=None):
    start, _end = period_for(day, anchor)
    return period_for(start - timedelta(days=1), anchor)


def summary_due_on(day, anchor=None):
    """True on the Monday right after a period ends. That is when the auto send would run."""
    if isinstance(day, datetime):
        day = _as_pacific(day).date()
    if day.weekday() != 0:
        return False
    start, _end = period_for(day, anchor)
    return (day - start).days == 1


def period_label(start, end):
    if start.year == end.year:
        return start.strftime("%b %-d") + " – " + end.strftime("%b %-d, %Y")
    return start.strftime("%b %-d, %Y") + " – " + end.strftime("%b %-d, %Y")


def in_period(record, start, end):
    """A receipt belongs to the period it was saved in (Pacific), so none is missed or counted twice."""
    day = saved_date(record)
    return day is not None and start <= day <= end


# ── Totals and summary ──

def _ordered(totals, order):
    out = {k: totals[k] for k in order if k in totals}
    for key in sorted(k for k in totals if k not in out):
        out[key] = totals[key]
    return out


def receipt_job(record):
    return _cell(record.get("Job")) or "Other"


def receipt_expense_type(record):
    return _cell(record.get("Expense Type")) or "Other"


def expense_type_totals(records):
    """{expense type: total} in RECEIPT_EXPENSE_TYPES order, only types that have receipts."""
    totals = {}
    for rec in records or []:
        key = receipt_expense_type(rec)
        totals[key] = round(totals.get(key, 0.0) + (parse_amount(rec.get("Amount")) or 0.0), 2)
    return _ordered(totals, RECEIPT_EXPENSE_TYPES)


def job_expense_totals(records):
    """{job: {"total": x, "types": {expense type: y}}} in menu order, only jobs that have receipts."""
    by_job = {}
    for rec in records or []:
        by_job.setdefault(receipt_job(rec), []).append(rec)
    out = {}
    for job, mine in _ordered(by_job, RECEIPT_JOBS).items():
        out[job] = {"total": grand_total(mine), "types": expense_type_totals(mine)}
    return out


def totals_rows(records):
    """Rows for a Job / Expense type / Total table: each job's types, then the job subtotal, then the grand total."""
    rows = []
    for job, info in job_expense_totals(records).items():
        for kind, amount in info["types"].items():
            rows.append({"Job": job, "Expense type": kind, "Total": amount})
        rows.append({"Job": job + " total", "Expense type": "", "Total": info["total"]})
    if rows:
        rows.append({"Job": "All jobs", "Expense type": "", "Total": grand_total(records)})
    return rows


def grand_total(records):
    return round(sum(parse_amount(r.get("Amount")) or 0.0 for r in records or []), 2)


def build_summary(records, start, end, employees=None):
    """Per-employee totals and line items for receipts saved in [start, end]."""
    chosen = [r for r in (records or []) if in_period(r, start, end)]
    names = []
    for name in list(employees or []) + [_cell(r.get("Employee")) for r in chosen]:
        if name and name not in names:
            names.append(name)
    people = []
    for name in names:
        mine = sort_receipts([r for r in chosen if _cell(r.get("Employee")) == name])
        if not mine:
            continue
        people.append({
            "employee": name,
            "jobs": job_expense_totals(mine),
            "types": expense_type_totals(mine),
            "total": grand_total(mine),
            "items": list(reversed(mine)),
        })
    return {
        "start": start,
        "end": end,
        "label": period_label(start, end),
        "employees": people,
        "count": len(chosen),
        "total": grand_total(chosen),
    }


def summary_subject(summary):
    return "CVH employee receipts: " + summary["label"]


def summary_text(summary):
    lines = [
        "Employee receipts saved " + summary["label"] + ".",
        "Receipts: " + str(summary["count"]) + "   Total: " + format_money(summary["total"]),
        "",
    ]
    if not summary["employees"]:
        lines.append("No receipts were saved in this period.")
    for person in summary["employees"]:
        lines.append(person["employee"] + " – " + format_money(person["total"]))
        for job, info in person["jobs"].items():
            lines.append("  " + job + ": " + format_money(info["total"]))
            for kind, amount in info["types"].items():
                lines.append("    " + kind + ": " + format_money(amount))
        lines.append("  By expense type (all jobs): " + ", ".join(
            kind + " " + format_money(amount) for kind, amount in person["types"].items()))
        lines.append("  Receipts:")
        for rec in person["items"]:
            bits = [
                rec.get("Date") or "no date",
                format_money(rec.get("Amount")),
                receipt_job(rec) + " / " + receipt_expense_type(rec),
                rec.get("Purpose") or "",
            ]
            if rec.get("Vendor"):
                bits.append(rec["Vendor"])
            if rec.get("Receipt Number"):
                bits.append("#" + rec["Receipt Number"])
            lines.append("  - " + " | ".join(b for b in bits if b))
            lines.append("    Photo: " + (rec.get("Photo Link") or "not on Drive (" + (rec.get("Photo File") or "no file") + ")"))
        lines.append("")
    lines.append("Sent by the CVH Employee Tool.")
    return "\n".join(lines)


def summary_html(summary):
    out = [
        "<p>Employee receipts saved <b>" + escape(summary["label"]) + "</b>.<br>",
        "Receipts: " + str(summary["count"]) + " &nbsp; Total: <b>" + escape(format_money(summary["total"])) + "</b></p>",
    ]
    if not summary["employees"]:
        out.append("<p>No receipts were saved in this period.</p>")
    cell = 'style="border:1px solid #ccc;padding:4px 6px;text-align:left"'
    for person in summary["employees"]:
        out.append("<h3>" + escape(person["employee"]) + " – " + escape(format_money(person["total"])) + "</h3>")
        out.append('<table style="border-collapse:collapse"><tr><th ' + cell + ">Job</th><th " + cell
                   + ">Expense type</th><th " + cell + ">Total</th></tr>")
        for job, info in person["jobs"].items():
            for kind, amount in info["types"].items():
                out.append("<tr><td " + cell + ">" + escape(job) + "</td><td " + cell + ">" + escape(kind) + "</td><td "
                           + cell + ">" + escape(format_money(amount)) + "</td></tr>")
            out.append("<tr><td " + cell + "><b>" + escape(job) + " total</b></td><td " + cell + "></td><td " + cell
                       + "><b>" + escape(format_money(info["total"])) + "</b></td></tr>")
        out.append("</table>")
        out.append("<p>By expense type (all jobs): " + escape(", ".join(
            kind + " " + format_money(amount) for kind, amount in person["types"].items())) + "</p>")
        out.append('<table style="border-collapse:collapse"><tr>' + "".join(
            "<th " + cell + ">" + h + "</th>" for h in ("Date", "Amount", "Job", "Expense type", "Purpose", "Vendor", "Receipt #", "Photo")
        ) + "</tr>")
        for rec in person["items"]:
            link = _cell(rec.get("Photo Link"))
            photo = ('<a href="' + escape(link, quote=True) + '">Open photo</a>') if link.startswith("http") else escape(
                "not on Drive" + (" (" + rec.get("Photo File") + ")" if rec.get("Photo File") else ""))
            out.append("<tr>" + "".join("<td " + cell + ">" + v + "</td>" for v in (
                escape(rec.get("Date") or ""), escape(format_money(rec.get("Amount"))), escape(receipt_job(rec)),
                escape(receipt_expense_type(rec)),
                escape(rec.get("Purpose") or ""), escape(rec.get("Vendor") or ""), escape(rec.get("Receipt Number") or ""), photo,
            )) + "</tr>")
        out.append("</table>")
    out.append("<p style=\"color:#666\">Sent by the CVH Employee Tool.</p>")
    return "".join(out)


# ── Sending ──

def mail_ready(secrets):
    """True when the company Gmail mailbox (the timesheet one) is enabled and has its app password."""
    if not company_mail.company_mail_ready(secrets):
        return False
    return company_mail.company_backend(secrets) in ("gmail_smtp", "smtp")


def auto_send_enabled(secrets):
    """Automatic bi-weekly sending. OFF unless [receipts_mail].auto_send = true."""
    return _flag(_section(secrets, RECEIPT_MAIL_SECTION), "auto_send")


def recipient(secrets):
    section = _section(secrets, RECEIPT_MAIL_SECTION)
    if section is not None:
        try:
            if "recipient" in section:
                value = tm._lower_email(section["recipient"])
                if value:
                    return value
        except Exception:
            pass
    return tm.timesheet_mail_recipient(secrets)


def idempotency_key(summary):
    return "receipts:" + summary["start"].isoformat() + ":" + summary["end"].isoformat()


def already_sent(audit_records, summary):
    key = idempotency_key(summary)
    return any(
        _cell(r.get("Idempotency Key")) == key and _cell(r.get("Status")) in (STATUS_SENT, STATUS_UNCERTAIN)
        for r in (audit_records or [])
    )


def build_message(summary, secrets, to=None, subject_prefix=""):
    address = company_mail.mailbox_address(secrets)
    msg = EmailMessage()
    msg["From"] = formataddr((DISPLAY_NAME, address))
    msg["To"] = to or recipient(secrets)
    msg["Subject"] = (subject_prefix or "") + summary_subject(summary)
    msg.set_content(summary_text(summary))
    msg.add_alternative(summary_html(summary), subtype="html")
    return msg


def _default_smtp_send(username, password, message, backend="gmail_smtp"):
    if backend == "gmail_smtp":
        return company_mail._default_gmail_smtp_send(username, password, message)
    return company_mail._default_office_smtp_send(username, password, message)


def send_summary(summary, secrets, *, trigger="Manual", audit_records=None, allow_resend=False, smtp_send=None,
                 to=None, subject_prefix=""):
    """Send the summary from the company mailbox. Inject smtp_send in tests; nothing else sends.

    to and subject_prefix are for a one-off test send. A test send ("Test" trigger) is never
    treated as the period's real send and skips the duplicate check.
    """
    to = tm._lower_email(to) if to else ""
    is_test = trigger == "Test"
    if is_test and not to:
        raise ValueError("A test send needs an explicit --to address")
    result = {
        "status": STATUS_DENIED,
        "error": "",
        "idempotency_key": ("test:" if is_test else "") + idempotency_key(summary),
        "to": to or recipient(secrets),
        "from": company_mail.mailbox_address(secrets),
        "trigger": trigger,
    }
    if not mail_ready(secrets):
        result["error"] = MAIL_NOT_READY_MESSAGE
        return result
    if trigger == "Automatic" and not auto_send_enabled(secrets):
        result["status"] = STATUS_SKIPPED
        result["error"] = "Automatic receipts email is off."
        return result
    if not is_test and already_sent(audit_records, summary) and not allow_resend:
        result["status"] = STATUS_DUPLICATE
        result["error"] = "This period's receipts summary was already sent."
        return result
    section = _section(secrets, company_mail.COMPANY_SECTION)
    address = company_mail.mailbox_address(secrets)
    username = company_mail._login_username(section, address)
    password = company_mail._secret_text(section, "password")
    backend = company_mail.company_backend(secrets)
    try:
        message = build_message(summary, secrets, to=to or None, subject_prefix=subject_prefix)
        if smtp_send is not None:
            smtp_send(username, password, message)
        else:
            _default_smtp_send(username, password, message, backend=backend)
        result["status"] = STATUS_SENT
    except Exception as exc:
        text = tm.sanitize_mail_error(exc, extra=(password,))
        lowered = text.lower()
        if "535" in lowered or "auth" in lowered:
            result["status"] = STATUS_DENIED
            result["error"] = "The company mailbox rejected the login. Ask the office."
        else:
            result["status"] = STATUS_UNCERTAIN
            result["error"] = "The company mailbox did not return a clear result. Check the Sent folder."
        if password and password in result["error"]:
            result["error"] = result["error"].replace(password, "[redacted]")
    return result


def build_mail_audit_record(summary, result, when=None, sent_by=""):
    return {
        "Timestamp": format_saved_at(when),
        "Period Start": summary["start"].isoformat(),
        "Period End": summary["end"].isoformat(),
        "Trigger": _cell(result.get("trigger")),
        "Sent By": _cell(sent_by) or ("Schedule" if result.get("trigger") == "Automatic" else ""),
        "Status": _cell(result.get("status")),
        "To": _cell(result.get("to")),
        "From": _cell(result.get("from")),
        "Receipts": str(summary["count"]),
        "Total": "%.2f" % summary["total"],
        "Idempotency Key": _cell(result.get("idempotency_key")),
        "Detail": _cell(result.get("error")),
    }


def load_mail_audit_readonly(spreadsheet):
    ws = _worksheet_or_none(spreadsheet, RECEIPTS_MAIL_SHEET_TITLE)
    if ws is None:
        return []
    return _records(ws, RECEIPTS_MAIL_COLUMNS)


def save_mail_audit_record(record, spreadsheet):
    ws, _created = _ensure_tab(spreadsheet, RECEIPTS_MAIL_SHEET_TITLE, RECEIPTS_MAIL_COLUMNS)
    header = [_cell(c) for c in ws.row_values(1)]
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")


def run_scheduled_send(spreadsheet, secrets, today=None, smtp_send=None, force_period=None):
    """What the bi-weekly job runs. Returns (status, detail). Sends only when every gate is open."""
    today = today or now_pacific().date()
    if not auto_send_enabled(secrets):
        return STATUS_SKIPPED, "Automatic receipts email is off ([receipts_mail].auto_send is not true)."
    if force_period is None and not summary_due_on(today):
        return STATUS_SKIPPED, "Not a send day. The next send is the Monday after the period ends."
    start, end = force_period or previous_period(today)
    records = load_receipts_readonly(spreadsheet)
    summary = build_summary(records, start, end)
    audit = load_mail_audit_readonly(spreadsheet)
    result = send_summary(summary, secrets, trigger="Automatic", audit_records=audit, smtp_send=smtp_send)
    if result["status"] in (STATUS_SENT, STATUS_UNCERTAIN, STATUS_DENIED):
        save_mail_audit_record(build_mail_audit_record(summary, result), spreadsheet)
    return result["status"], result.get("error") or summary["label"]
