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
import csv
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

# ── Expense categories. Edit these lists to add, remove, or reorder choices. ──
# Older receipts used Job + Expense type. Those lists stay here so saved rows
# can still be read and totaled. New receipts use Category (and a sub-choice).
RECEIPT_JOBS = (
    "CVH",
    "BNSF",
    "Forestry",
    "Other",
)
RECEIPT_EXPENSE_TYPES = (
    "Fuel",
    "Parts",
    "Meals",
    "Lodging",
    "Supplies",
    "Other",
)

CATEGORY_DUES = "Dues"
CATEGORY_LICENSES = "Licenses & Permits"
CATEGORY_EQUIPMENT = "Equipment"
CATEGORY_BUILDINGS = "Buildings"
CATEGORY_OFFICE = "Office Supplies"
CATEGORY_SHOP = "Shop Supplies"
CATEGORY_HELIPORT = "Heliport"
CATEGORY_BNSF = "BNSF"
CATEGORY_FORESTRY = "Forestry"
CATEGORY_FUEL = "Fuel"
CATEGORY_TRAVEL = "Travel"
CATEGORY_OTHER = "Other"
RECEIPT_CATEGORIES = (
    CATEGORY_DUES,
    CATEGORY_LICENSES,
    CATEGORY_EQUIPMENT,
    CATEGORY_BUILDINGS,
    CATEGORY_OFFICE,
    CATEGORY_SHOP,
    CATEGORY_HELIPORT,
    CATEGORY_BNSF,
    CATEGORY_FORESTRY,
    CATEGORY_FUEL,
    CATEGORY_TRAVEL,
    CATEGORY_OTHER,
)
# Buildings dropdown. Add names here when a new building should appear.
RECEIPT_BUILDINGS = (
    "Hangar House",
    "Enstrom Hangar",
    "TS",
    "R44 Hangar",
    "Other",
)
# Sub-menu for BNSF and Forestry.
RECEIPT_JOB_SUBCATEGORIES = (
    "Travel",
    "Supplies",
    "Heli fuel",
    "Vehicle fuel",
    "Other",
)
# Sub-menu for the Fuel category.
RECEIPT_FUEL_TYPES = (
    "Jet A",
    "AvGas",
    "Regular ground (gas)",
    "Diesel",
)
# Purpose menu when the category is Equipment.
RECEIPT_EQUIPMENT_PURPOSES = (
    "Diesel Fuel",
    "Gas",
    "JetA",
    "AvGas",
    "Parts",
)
RECEIPT_STATEMENT_NONE = "None"
# Paid-on-monthly-statement accounts. Edit this list when vendors change.
RECEIPT_STATEMENT_ACCOUNTS = (
    RECEIPT_STATEMENT_NONE,
    "Bruckners",
    "Mid State Co-Op",
    "Knudson",
    "Ranch & Home",
    "Kittitas County Solid Waste",
    "Napa",
    "Oxac",
    "Les Schwab",
)
# IFTA member jurisdictions: 48 contiguous US states and 10 Canadian provinces.
# Same set the Equipment IFTA forms use.
IFTA_JURISDICTIONS = [
    ("AL", "Alabama"), ("AZ", "Arizona"), ("AR", "Arkansas"), ("CA", "California"),
    ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"), ("FL", "Florida"),
    ("GA", "Georgia"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"),
    ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"),
    ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
    ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"),
    ("NE", "Nebraska"), ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"),
    ("NM", "New Mexico"), ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"),
    ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"),
    ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"),
    ("WA", "Washington"), ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
    ("AB", "Alberta"), ("BC", "British Columbia"), ("MB", "Manitoba"),
    ("NB", "New Brunswick"), ("NL", "Newfoundland and Labrador"), ("NS", "Nova Scotia"),
    ("ON", "Ontario"), ("PE", "Prince Edward Island"), ("QC", "Quebec"), ("SK", "Saskatchewan"),
]
IFTA_JURISDICTION_CODES = tuple(code for code, _name in IFTA_JURISDICTIONS)
IFTA_DEFAULT_JURISDICTION = "WA"

# People who may open the "Receipts summary" office page (EMPLOYEES -> Receipts summary)
# after their PIN. Patti is an office PIN user (timesheet_pin.PIN_OFFICE_USERS), not an employee.
RECEIPTS_OFFICE_USERS = ("Ron Cline", "Patti")

RECEIPTS_SHEET_TITLE = "Receipts"
# Never reorder these original headers on a live tab. New fields are appended.
RECEIPTS_ORIGINAL_COLUMNS = [
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
RECEIPTS_ADDED_COLUMNS = [
    "Category",
    "Subcategory",
    "Subcategory Detail",
    "Equipment Shares",
    "Equipment Purpose",
    "Memo",
    "IFTA State",
    "IFTA Gallons",
    "Statement Account",
    "Edited At",
    "Edited By",
]
RECEIPTS_COLUMNS = RECEIPTS_ORIGINAL_COLUMNS + RECEIPTS_ADDED_COLUMNS
RECEIPTS_PRESERVE_ON_EDIT = ("Saved At", "Entry ID", "Employee")
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
RANGE_PERIOD_TO_DATE = "Period to date"
RANGE_THIS_MONTH = "This month"
RANGE_PAY_PERIOD = "Pay period"
RANGE_CUSTOM = "Custom dates"
SUMMARY_RANGE_CHOICES = (
    RANGE_PERIOD_TO_DATE,
    RANGE_THIS_MONTH,
    RANGE_PAY_PERIOD,
    RANGE_CUSTOM,
)
FILTER_ALL = "All"
OFFICE_TABLE_COLUMNS = (
    "Saved",
    "Employee",
    "Receipt date",
    "Vendor",
    "Purpose",
    "Receipt #",
    "Category",
    "Detail",
    "Statement account",
    "Amount",
    "Photo",
)

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


_GALLONS_AFTER_RE = re.compile(
    r"(?<![\d.])(\d{1,4}(?:\.\d{1,3})?)\s*(?:gal(?:lons?)?|gals)\b",
    re.I,
)
_GALLONS_LABEL_RE = re.compile(
    r"\b(?:gals?|gallons?)\s*(?:purchased|pumped|qty)?\s*[:#]?\s*(\d{1,4}(?:\.\d{1,3})?)\b",
    re.I,
)


def parse_gallons(value):
    """Return gallons as a float, or None for blank or bad input."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 3) if value >= 0 else None
    text = _cell(value).replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number < 0 or number != number or number > 100_000:
        return None
    return round(number, 3)


def format_gallons(value):
    number = parse_gallons(value)
    if number is None:
        return ""
    text = ("%.3f" % number).rstrip("0").rstrip(".")
    return text or "0"


def find_gallons(text):
    """Best guess at gallons purchased from receipt text."""
    found = []
    for match in _GALLONS_AFTER_RE.finditer(text or ""):
        number = parse_gallons(match.group(1))
        if number is not None:
            found.append(number)
    for match in _GALLONS_LABEL_RE.finditer(text or ""):
        number = parse_gallons(match.group(1))
        if number is not None:
            found.append(number)
    return found[0] if found else None


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
    gallons = find_gallons(text)
    if gallons is not None:
        fields["gallons"] = format_gallons(gallons)
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



# ── Categories, equipment shares, IFTA, statement accounts ──

def equipment_names_from_records(records, is_active=None, fallback=None):
    """Unit names from the Equipment page, in that page's order. Active units only.

    is_active(record) can be supplied by the app. When no records are passed,
    fallback (the official Equipment list) is used so the form still works.
    """
    names = []
    for rec in records or []:
        if is_active is not None and not is_active(rec):
            continue
        name = _cell(rec.get("Unit ID")) or _cell(rec.get("Name"))
        if name and name not in names:
            names.append(name)
    if names:
        return names
    for name in list(fallback or []):
        if _cell(name) and _cell(name) not in names:
            names.append(_cell(name))
    return names


def format_equipment_shares(shares):
    """Store allocations as 'Ram=20.00; PW=10.00'."""
    parts = []
    for name, amount in shares or []:
        name = _cell(name)
        number = parse_amount(amount)
        if not name or number is None:
            continue
        parts.append(name + "=" + format_amount(number))
    return "; ".join(parts)


def parse_equipment_shares(value):
    """List of (name, amount) from a stored Equipment Shares cell."""
    text = _cell(value)
    if not text:
        return []
    out = []
    chunks = text.replace("\n", ";").split(";")
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            name, amount = chunk.split("=", 1)
        elif ":" in chunk:
            name, amount = chunk.split(":", 1)
        else:
            continue
        number = parse_amount(amount)
        name = _cell(name)
        if name and number is not None:
            out.append((name, number))
    return out


def equipment_share_remaining(total, shares):
    """Receipt total minus the typed shares, rounded to cents."""
    total_n = parse_amount(total) or 0.0
    used = round(sum((parse_amount(amount) or 0.0) for _name, amount in (shares or [])), 2)
    return round(total_n - used, 2)


def equipment_share_warning(total, shares):
    """Warning when Equipment shares do not add up to the receipt total. Empty if they do."""
    leftover = equipment_share_remaining(total, shares)
    if leftover == 0:
        return ""
    used = round((parse_amount(total) or 0.0) - leftover, 2)
    if leftover > 0:
        return (
            "The shares add up to " + format_money(used) + ". "
            + format_money(leftover) + " is still left. You can save anyway."
        )
    return (
        "The shares add up to " + format_money(used) + ", which is "
        + format_money(-leftover) + " over the receipt total. You can save anyway."
    )


def ifta_jurisdiction_label(code):
    code = _cell(code).upper()
    for item, name in IFTA_JURISDICTIONS:
        if item == code:
            return item + " — " + name
    return code


def ifta_jurisdiction_code(value):
    text = _cell(value)
    if not text:
        return ""
    code = text.split("—")[0].split("-")[0].strip().upper()
    if code in IFTA_JURISDICTION_CODES:
        return code
    return ""


def is_ifta_fuel(category, subcategory="", equipment_purpose=""):
    """True when this receipt is ground/vehicle fuel that belongs on the IFTA report."""
    category = _cell(category)
    subcategory = _cell(subcategory)
    purpose = _cell(equipment_purpose)
    if category == CATEGORY_FUEL and subcategory in ("Regular ground (gas)", "Diesel"):
        return True
    if category == CATEGORY_EQUIPMENT and purpose in ("Diesel Fuel", "Gas"):
        return True
    if category in (CATEGORY_BNSF, CATEGORY_FORESTRY) and subcategory == "Vehicle fuel":
        return True
    return False


def receipt_date_or_saved(record):
    """Date on the receipt, or the day it was entered if that is missing."""
    return parse_receipt_date(record.get("Date")) or saved_date(record)


def ifta_quarter(day):
    """(year, quarter 1-4, start, end) for an IFTA quarter containing day."""
    if isinstance(day, datetime):
        day = _as_pacific(day).date()
    quarter = (day.month - 1) // 3 + 1
    start_month = (quarter - 1) * 3 + 1
    start = date(day.year, start_month, 1)
    if quarter == 4:
        end = date(day.year, 12, 31)
    else:
        end = date(day.year, start_month + 3, 1) - timedelta(days=1)
    return day.year, quarter, start, end


def ifta_quarter_label(year, quarter):
    return "Q" + str(int(quarter)) + " " + str(int(year))


def ifta_quarter_options(today=None, count=8):
    """Recent IFTA quarters, newest first, including the current one."""
    today = today or now_pacific().date()
    if isinstance(today, datetime):
        today = _as_pacific(today).date()
    year, quarter, start, end = ifta_quarter(today)
    options = []
    for _ in range(count):
        options.append((year, quarter, start, end))
        if quarter == 1:
            year, quarter = year - 1, 4
        else:
            quarter -= 1
        _y, _q, start, end = ifta_quarter(date(year, (quarter - 1) * 3 + 1, 1))
    return options


def map_legacy_category(job, expense_type):
    """Map an old Job + Expense type row onto the new category list."""
    job = _cell(job)
    expense_type = _cell(expense_type)
    if job in (CATEGORY_BNSF, CATEGORY_FORESTRY):
        return job
    if expense_type == "Fuel":
        return CATEGORY_FUEL
    if expense_type == "Parts":
        return CATEGORY_EQUIPMENT
    if expense_type in ("Meals", "Lodging"):
        return CATEGORY_TRAVEL
    if expense_type == "Supplies":
        return CATEGORY_SHOP
    if expense_type and expense_type in RECEIPT_CATEGORIES:
        return expense_type
    if expense_type:
        return expense_type
    return CATEGORY_OTHER


def map_legacy_subcategory(job, expense_type):
    """Sub-item for an old Job + Expense type row."""
    job = _cell(job)
    expense_type = _cell(expense_type)
    if job in (CATEGORY_BNSF, CATEGORY_FORESTRY):
        if expense_type in ("Meals", "Lodging"):
            return "Travel"
        if expense_type == "Supplies":
            return "Supplies"
        if expense_type == "Fuel":
            return "Fuel"
        return expense_type or "Other"
    if expense_type == "Fuel":
        return ""
    if expense_type == "Parts":
        return ""
    if expense_type in ("Meals", "Lodging"):
        return expense_type
    return ""


def derived_job_and_expense(category, subcategory="", equipment_purpose=""):
    """Fill the older Job and Expense Type columns on a new receipt."""
    category = _cell(category)
    subcategory = _cell(subcategory)
    purpose = _cell(equipment_purpose)
    if category in (CATEGORY_BNSF, CATEGORY_FORESTRY):
        return category, subcategory or "Other"
    if category == CATEGORY_FUEL:
        return "CVH", "Fuel"
    if category == CATEGORY_EQUIPMENT:
        if purpose in ("Diesel Fuel", "Gas", "JetA", "AvGas"):
            return "CVH", "Fuel"
        return "CVH", "Parts"
    if category == CATEGORY_TRAVEL:
        return "CVH", "Other"
    if category in (CATEGORY_OFFICE, CATEGORY_SHOP):
        return "CVH", "Supplies"
    return "CVH", category or "Other"


def receipt_category(record):
    stored = _cell(record.get("Category"))
    if stored:
        return stored
    return map_legacy_category(record.get("Job"), record.get("Expense Type"))


def receipt_subcategory(record):
    stored = _cell(record.get("Subcategory"))
    if stored:
        return stored
    if _cell(record.get("Category")):
        return ""
    return map_legacy_subcategory(record.get("Job"), record.get("Expense Type"))


def receipt_detail(record):
    """One-line sub-item for tables, email, and CSV."""
    category = receipt_category(record)
    sub = receipt_subcategory(record)
    extra = _cell(record.get("Subcategory Detail"))
    purpose = _cell(record.get("Equipment Purpose"))
    shares = format_equipment_shares(parse_equipment_shares(record.get("Equipment Shares")))
    if category == CATEGORY_EQUIPMENT:
        bits = [shares] if shares else []
        if purpose:
            bits.append(purpose)
        return " · ".join(bits)
    if category == CATEGORY_BUILDINGS:
        if sub == "Other" and extra:
            return "Other: " + extra
        return sub
    if extra and sub == "Other":
        return "Other: " + extra
    return sub


def receipt_statement_account(record):
    value = _cell(record.get("Statement Account"))
    if not value or value == RECEIPT_STATEMENT_NONE:
        return ""
    return value


def is_ifta_record(record):
    return is_ifta_fuel(
        receipt_category(record),
        receipt_subcategory(record),
        record.get("Equipment Purpose"),
    )


def ifta_state(record):
    return ifta_jurisdiction_code(record.get("IFTA State"))


def ifta_gallons(record):
    return parse_gallons(record.get("IFTA Gallons"))


def ifta_warning(category, subcategory="", equipment_purpose="", state="", gallons=""):
    """Warning when IFTA fields are missing. Does not block a save."""
    if not is_ifta_fuel(category, subcategory, equipment_purpose):
        return ""
    missing = []
    if not ifta_jurisdiction_code(state):
        missing.append("the state or province")
    if parse_gallons(gallons) is None:
        missing.append("gallons purchased")
    if not missing:
        return ""
    return "This looks like ground fuel for IFTA. Add " + " and ".join(missing) + " if you have them. You can save anyway."


def _with_current(options, current=""):
    out = list(options)
    current = _cell(current)
    if current and current not in out:
        out.append(current)
    return out


def validate_receipt_allocation(fields, category, subcategory="", subcategory_detail="",
                                equipment_shares=None, equipment_purpose="", other_comment="",
                                existing=None):
    """Problems that block saving the category step. Equipment share leftovers warn, not block.

    When editing a receipt saved under the older menus, empty equipment shares
    or a leftover sub-choice already on the row are allowed so a typo can be
    fixed without re-filling the new fields first.
    """
    problems = []
    category = _cell(category)
    current_category = receipt_category(existing) if existing else ""
    if category not in _with_current(RECEIPT_CATEGORIES, current_category):
        problems.append("Choose a category.")
        return problems
    current_sub = receipt_subcategory(existing) if existing else ""
    if category == CATEGORY_EQUIPMENT:
        shares = list(equipment_shares or [])
        had_shares = parse_equipment_shares((existing or {}).get("Equipment Shares"))
        if not shares and (had_shares or not existing):
            problems.append("Choose at least one piece of equipment.")
        current_purpose = _cell((existing or {}).get("Equipment Purpose"))
        purpose = _cell(equipment_purpose)
        allowed_purposes = _with_current(RECEIPT_EQUIPMENT_PURPOSES, current_purpose)
        if not purpose:
            if not existing or current_purpose:
                problems.append("Choose a purpose for this equipment receipt.")
        elif purpose not in allowed_purposes:
            problems.append("Choose a purpose for this equipment receipt.")
    elif category == CATEGORY_BUILDINGS:
        if _cell(subcategory) not in _with_current(RECEIPT_BUILDINGS, current_sub):
            problems.append("Choose a building.")
        elif subcategory == "Other" and not _cell(subcategory_detail) and not _cell((existing or {}).get("Subcategory Detail")):
            problems.append("Enter the building name.")
    elif category in (CATEGORY_BNSF, CATEGORY_FORESTRY):
        if _cell(subcategory) not in _with_current(RECEIPT_JOB_SUBCATEGORIES, current_sub):
            problems.append("Choose a " + category + " type.")
    elif category == CATEGORY_FUEL:
        if _cell(subcategory) not in _with_current(RECEIPT_FUEL_TYPES, current_sub):
            problems.append("Choose a fuel type.")
    elif category == CATEGORY_OTHER:
        comment = _cell(other_comment) or _cell(fields.get("notes")) or _cell(fields.get("purpose"))
        if not comment:
            problems.append("Enter a comment for this Other receipt.")
    return problems

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


def build_receipt_record(employee, fields, category, subcategory="", subcategory_detail="",
                         equipment_shares=None, equipment_purpose="", memo="",
                         statement_account="", ifta_state="", ifta_gallons="",
                         photo_link="", photo_file="", when=None, entry_id=None):
    when = _as_pacific(when)
    category = _cell(category)
    if category not in RECEIPT_CATEGORIES:
        raise ValueError("Choose a category from the list")
    subcategory = _cell(subcategory)
    subcategory_detail = _cell(subcategory_detail)
    equipment_purpose = _cell(equipment_purpose)
    memo = _cell(memo) or _cell(fields.get("memo"))
    comment = _cell(fields.get("other_comment")) or _cell(fields.get("notes"))
    job, expense_type = derived_job_and_expense(category, subcategory, equipment_purpose)
    receipt_date = parse_receipt_date(fields.get("date"))
    account = _cell(statement_account)
    if not account or account == RECEIPT_STATEMENT_NONE:
        account = ""
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
        "Notes": comment,
        "Category": category,
        "Subcategory": subcategory,
        "Subcategory Detail": subcategory_detail,
        "Equipment Shares": format_equipment_shares(equipment_shares),
        "Equipment Purpose": equipment_purpose,
        "Memo": memo,
        "IFTA State": ifta_jurisdiction_code(ifta_state),
        "IFTA Gallons": format_gallons(ifta_gallons) if parse_gallons(ifta_gallons) is not None else _cell(ifta_gallons),
        "Statement Account": account,
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


def ensure_receipts_columns(ws, columns=None):
    """Append any missing Receipts columns on the right. Never reorder existing headers."""
    columns = columns or RECEIPTS_COLUMNS
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        return False
    missing = [col for col in columns if col not in header]
    if not missing:
        return False
    start = len(header) + 1
    for offset, col in enumerate(missing):
        ws.update_cell(1, start + offset, col)
    return True


def ensure_receipts_worksheet(spreadsheet):
    ws, created = _ensure_tab(spreadsheet, RECEIPTS_SHEET_TITLE, RECEIPTS_COLUMNS)
    if not created:
        ensure_receipts_columns(ws)
    return ws, created


def save_receipt_record(record, spreadsheet):
    """Append one receipt to the Receipts tab only."""
    ws, _created = ensure_receipts_worksheet(spreadsheet)
    header = [_cell(c) for c in ws.row_values(1)]
    if not header:
        raise RuntimeError("Receipts worksheet has no header")
    ws.append_row([str(record.get(c, "")) for c in header], value_input_option="RAW")
    return "Google Sheets (Receipts)"


def receipt_entry_id(record):
    return _cell((record or {}).get("Entry ID"))


def can_edit_receipt(record, user, office=False):
    """Employees may edit their own receipts. Ron and Patti may edit any from the office page."""
    user = _cell(user)
    if not user or not receipt_entry_id(record):
        return False
    if office:
        return user in RECEIPTS_OFFICE_USERS
    return _cell(record.get("Employee")) == user


def receipt_picker_label(record, include_employee=False):
    """One-line label for the Saved receipts picker."""
    parts = []
    if include_employee:
        parts.append(_cell(record.get("Employee")) or "Unknown")
    parts.append(_cell(record.get("Date")) or "no date")
    parts.append(format_money(record.get("Amount")))
    category = receipt_category(record)
    detail = receipt_detail(record)
    parts.append(category + ((" / " + detail) if detail else ""))
    if _cell(record.get("Vendor")):
        parts.append(_cell(record.get("Vendor")))
    entry = receipt_entry_id(record)
    if entry:
        parts.append(entry)
    return " | ".join(parts)


def prepare_receipt_edit(existing, updated, edited_by, when=None):
    """Keep the original entry, employee, saved time, and Drive photo unless a new photo was stored."""
    out = dict(updated or {})
    existing = existing or {}
    for col in RECEIPTS_PRESERVE_ON_EDIT:
        out[col] = existing.get(col, "")
    if not _cell(out.get("Photo Link")) and _cell(existing.get("Photo Link")):
        out["Photo Link"] = _cell(existing.get("Photo Link"))
        out["Photo File"] = _cell(existing.get("Photo File")) or _cell(out.get("Photo File"))
    elif not _cell(out.get("Photo File")) and _cell(existing.get("Photo File")):
        out["Photo File"] = _cell(existing.get("Photo File"))
    out["Edited At"] = format_saved_at(when)
    out["Edited By"] = _cell(edited_by)
    return out


def find_receipt_row_number(ws, entry_id):
    """1-based sheet row for this Entry ID. Uses the last match if a duplicate is already there."""
    entry_id = _cell(entry_id)
    if not entry_id:
        raise ValueError("This receipt has no entry id")
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Receipts worksheet has no header")
    header = [_cell(c) for c in values[0]]
    try:
        idx = header.index("Entry ID")
    except ValueError as exc:
        raise RuntimeError("Receipts worksheet is missing the Entry ID column") from exc
    matches = []
    for row_number, row in enumerate(values[1:], start=2):
        if _cell(row[idx] if idx < len(row) else "") == entry_id:
            matches.append(row_number)
    if not matches:
        raise RuntimeError("Could not find that receipt on the Receipts tab")
    return matches[-1]


def update_receipt_record(record, spreadsheet, edited_by, office=False, when=None):
    """Update the existing Receipts row for this Entry ID. Never appends a second row."""
    entry_id = receipt_entry_id(record)
    if not entry_id:
        raise ValueError("This receipt has no entry id")
    edited_by = _cell(edited_by)
    if not edited_by:
        raise ValueError("An editor is required")
    ws, _created = ensure_receipts_worksheet(spreadsheet)
    ensure_receipts_columns(ws)
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Receipts worksheet has no header")
    header = [_cell(c) for c in values[0]]
    row_number = find_receipt_row_number(ws, entry_id)
    existing_row = values[row_number - 1]
    existing = {col: (_cell(existing_row[idx]) if idx < len(existing_row) else "") for idx, col in enumerate(header) if col}
    if not can_edit_receipt(existing, edited_by, office=office):
        raise ValueError("You can only edit your own receipts.")
    merged = prepare_receipt_edit(existing, record, edited_by, when=when)
    for col_name in header:
        if not col_name or col_name in RECEIPTS_PRESERVE_ON_EDIT:
            continue
        if col_name not in merged and col_name not in ("Edited At", "Edited By"):
            continue
        col_number = header.index(col_name) + 1
        ws.update_cell(row_number, col_number, str(merged.get(col_name, "")))
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


def period_to_date(day, anchor=None):
    """Start of the in-progress pay period through day (Pacific)."""
    if isinstance(day, datetime):
        day = _as_pacific(day).date()
    start, _end = period_for(day, anchor)
    return start, day


def month_to_date(day):
    """First day of day's calendar month through day (Pacific)."""
    if isinstance(day, datetime):
        day = _as_pacific(day).date()
    return day.replace(day=1), day


def _ordered_dates(start, end):
    if start is None or end is None:
        return start, end
    if end < start:
        return end, start
    return start, end


def resolve_summary_range(kind, today=None, period=None, custom_start=None, custom_end=None, anchor=None):
    """(start, end) for a live-view range choice. Dates are inclusive, counted by day entered."""
    today = today or now_pacific().date()
    if isinstance(today, datetime):
        today = _as_pacific(today).date()
    if kind == RANGE_PERIOD_TO_DATE:
        return period_to_date(today, anchor)
    if kind == RANGE_THIS_MONTH:
        return month_to_date(today)
    if kind == RANGE_PAY_PERIOD:
        if period:
            return period[0], period[1]
        return period_for(today, anchor)
    start, end = _ordered_dates(custom_start, custom_end)
    if start is None or end is None:
        return period_to_date(today, anchor)
    return start, end


def summary_range_label(start, end, kind=""):
    label = period_label(start, end)
    if kind == RANGE_PERIOD_TO_DATE:
        return label + " (period to date)"
    if kind == RANGE_THIS_MONTH:
        return label + " (this month)"
    return label


def _filter_value(value):
    text = _cell(value)
    if not text or text == FILTER_ALL:
        return ""
    return text


def filter_receipts(records, start, end, employee=None, category=None, subcategory=None,
                    statement_account=None, job=None, expense_type=None):
    """Receipts saved in [start, end] (Pacific), optionally narrowed by employee, category, or statement account."""
    employee = _filter_value(employee)
    category = _filter_value(category)
    subcategory = _filter_value(subcategory)
    statement_account = _filter_value(statement_account)
    job = _filter_value(job)
    expense_type = _filter_value(expense_type)
    out = [r for r in (records or []) if in_period(r, start, end)]
    if employee:
        out = [r for r in out if _cell(r.get("Employee")) == employee]
    if category:
        out = [r for r in out if receipt_category(r) == category]
    if subcategory:
        out = [r for r in out if receipt_subcategory(r) == subcategory]
    if statement_account:
        if statement_account == RECEIPT_STATEMENT_NONE:
            out = [r for r in out if not receipt_statement_account(r)]
        else:
            out = [r for r in out if receipt_statement_account(r) == statement_account]
    if job:
        out = [r for r in out if receipt_job(r) == job]
    if expense_type:
        out = [r for r in out if receipt_expense_type(r) == expense_type]
    return out


def filter_key(employee=None, category=None, subcategory=None, statement_account=None,
               job=None, expense_type=None):
    """Stable suffix for the send-dedupe key. Empty when no filters are on."""
    parts = []
    employee = _filter_value(employee)
    category = _filter_value(category)
    subcategory = _filter_value(subcategory)
    statement_account = _filter_value(statement_account)
    job = _filter_value(job)
    expense_type = _filter_value(expense_type)
    if employee:
        parts.append("emp=" + employee)
    if category:
        parts.append("cat=" + category)
    if subcategory:
        parts.append("sub=" + subcategory)
    if statement_account:
        parts.append("acct=" + statement_account)
    if job:
        parts.append("job=" + job)
    if expense_type:
        parts.append("type=" + expense_type)
    return "|".join(parts)


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


def subcategory_totals(records):
    """{detail or category: total} for one category's receipts."""
    totals = {}
    for rec in records or []:
        key = receipt_detail(rec) or receipt_category(rec)
        totals[key] = round(totals.get(key, 0.0) + (parse_amount(rec.get("Amount")) or 0.0), 2)
    return totals


def category_totals(records):
    """{category: {"total": x, "details": {sub-item: y}}} in menu order."""
    by_cat = {}
    for rec in records or []:
        by_cat.setdefault(receipt_category(rec), []).append(rec)
    out = {}
    for category, mine in _ordered(by_cat, RECEIPT_CATEGORIES).items():
        details = subcategory_totals(mine)
        # A category with no sub-item (Dues, Office Supplies, ...) does not need a detail row.
        if list(details.keys()) == [category]:
            details = {}
        out[category] = {"total": grand_total(mine), "details": details}
    return out


def totals_rows(records):
    """Rows for a Category / Detail / Total table, then each category subtotal, then the grand total."""
    rows = []
    for category, info in category_totals(records).items():
        if info["details"]:
            for kind, amount in info["details"].items():
                rows.append({"Category": category, "Detail": kind, "Total": amount})
        rows.append({"Category": category + " total", "Detail": "", "Total": info["total"]})
    if rows:
        rows.append({"Category": "All categories", "Detail": "", "Total": grand_total(records)})
    return rows


def statement_month_key(record):
    day = saved_date(record) or parse_receipt_date(record.get("Date"))
    return day.strftime("%Y-%m") if day else ""


def statement_month_label(key):
    parsed = parse_receipt_date(key + "-01") if key else None
    return parsed.strftime("%b %Y") if parsed else key


def statement_account_totals(records):
    """{account: {"total": x, "months": {YYYY-MM: y}}} including a None bucket."""
    by_acct = {}
    for rec in records or []:
        account = receipt_statement_account(rec) or RECEIPT_STATEMENT_NONE
        by_acct.setdefault(account, []).append(rec)
    order = list(RECEIPT_STATEMENT_ACCOUNTS)
    out = {}
    for account, mine in _ordered(by_acct, order).items():
        months = {}
        for rec in mine:
            key = statement_month_key(rec)
            if not key:
                continue
            months[key] = round(months.get(key, 0.0) + (parse_amount(rec.get("Amount")) or 0.0), 2)
        out[account] = {"total": grand_total(mine), "months": dict(sorted(months.items()))}
    return out


def statement_totals_rows(records):
    """Rows for Statement account / Month / Total, then each vendor subtotal, then the grand total."""
    rows = []
    grouped = statement_account_totals(records)
    for account, info in grouped.items():
        for month, amount in info["months"].items():
            rows.append({"Statement account": account, "Month": statement_month_label(month), "Total": amount})
        rows.append({"Statement account": account + " total", "Month": "", "Total": info["total"]})
    if rows:
        rows.append({"Statement account": "All statement accounts", "Month": "", "Total": grand_total(records)})
    return rows


def grand_total(records):
    return round(sum(parse_amount(r.get("Amount")) or 0.0 for r in records or []), 2)


def employee_totals_rows(records):
    """One row per employee, in first-seen order, then a grand total when there is more than one person."""
    names = []
    by_name = {}
    for rec in records or []:
        name = _cell(rec.get("Employee")) or "Unknown"
        if name not in by_name:
            names.append(name)
            by_name[name] = []
        by_name[name].append(rec)
    rows = [{"Employee": name, "Receipts": len(by_name[name]), "Total": grand_total(by_name[name])} for name in names]
    if len(rows) > 1:
        rows.append({"Employee": "All employees", "Receipts": len(records or []), "Total": grand_total(records)})
    return rows


def office_table_rows(records):
    """Rows for the live office table and CSV: saved date, employee, receipt fields, photo link."""
    rows = []
    for rec in sort_receipts(records):
        link = _cell(rec.get("Photo Link"))
        saved = _cell(rec.get("Saved At"))
        rows.append({
            "Saved": saved[:10] if saved else "",
            "Employee": _cell(rec.get("Employee")),
            "Receipt date": _cell(rec.get("Date")),
            "Vendor": _cell(rec.get("Vendor")),
            "Purpose": _cell(rec.get("Purpose")),
            "Receipt #": _cell(rec.get("Receipt Number")),
            "Category": receipt_category(rec),
            "Detail": receipt_detail(rec),
            "Statement account": receipt_statement_account(rec) or RECEIPT_STATEMENT_NONE,
            "Amount": format_money(rec.get("Amount")),
            "Photo": link if link.startswith("http") else "",
        })
    return rows


def summary_csv(records):
    """CSV of the shown office rows. Amounts keep the dollar sign used on the page."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(OFFICE_TABLE_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in office_table_rows(records):
        writer.writerow({k: row.get(k, "") for k in OFFICE_TABLE_COLUMNS})
    return buf.getvalue()


def build_summary(records, start, end, employees=None, employee=None, category=None, subcategory=None,
                  statement_account=None, job=None, expense_type=None, range_kind=""):
    """Per-employee totals and line items for receipts saved in [start, end], optionally filtered."""
    chosen = filter_receipts(
        records, start, end, employee=employee, category=category, subcategory=subcategory,
        statement_account=statement_account, job=job, expense_type=expense_type,
    )
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
            "categories": category_totals(mine),
            "jobs": job_expense_totals(mine),
            "types": expense_type_totals(mine),
            "total": grand_total(mine),
            "items": list(reversed(mine)),
        })
    return {
        "start": start,
        "end": end,
        "label": summary_range_label(start, end, range_kind),
        "range_kind": range_kind or "",
        "employee_filter": _filter_value(employee),
        "category_filter": _filter_value(category),
        "subcategory_filter": _filter_value(subcategory),
        "statement_account_filter": _filter_value(statement_account),
        "job_filter": _filter_value(job),
        "expense_type_filter": _filter_value(expense_type),
        "employees": people,
        "count": len(chosen),
        "total": grand_total(chosen),
    }


def summary_filters_label(summary):
    parts = []
    if summary.get("employee_filter"):
        parts.append("Employee: " + summary["employee_filter"])
    if summary.get("category_filter"):
        parts.append("Category: " + summary["category_filter"])
    if summary.get("subcategory_filter"):
        parts.append("Detail: " + summary["subcategory_filter"])
    if summary.get("statement_account_filter"):
        parts.append("Statement account: " + summary["statement_account_filter"])
    if summary.get("job_filter"):
        parts.append("Job: " + summary["job_filter"])
    if summary.get("expense_type_filter"):
        parts.append("Expense type: " + summary["expense_type_filter"])
    return ", ".join(parts)


def summary_subject(summary):
    return "CVH employee receipts: " + summary["label"]


def summary_text(summary):
    lines = [
        "Employee receipts saved " + summary["label"] + ".",
        "Receipts: " + str(summary["count"]) + "   Total: " + format_money(summary["total"]),
    ]
    filters = summary_filters_label(summary)
    if filters:
        lines.append("Filters: " + filters)
    lines.append("")
    if not summary["employees"]:
        lines.append("No receipts were saved in this range.")
    for person in summary["employees"]:
        lines.append(person["employee"] + " – " + format_money(person["total"]))
        for category, info in person["categories"].items():
            lines.append("  " + category + ": " + format_money(info["total"]))
            for kind, amount in info["details"].items():
                lines.append("    " + kind + ": " + format_money(amount))
        lines.append("  By category: " + ", ".join(
            category + " " + format_money(info["total"]) for category, info in person["categories"].items()))
        lines.append("  Receipts:")
        for rec in person["items"]:
            bits = [
                rec.get("Date") or "no date",
                format_money(rec.get("Amount")),
                receipt_category(rec) + ((" / " + receipt_detail(rec)) if receipt_detail(rec) else ""),
                rec.get("Purpose") or "",
            ]
            if rec.get("Vendor"):
                bits.append(rec["Vendor"])
            if rec.get("Receipt Number"):
                bits.append("#" + rec["Receipt Number"])
            if receipt_statement_account(rec):
                bits.append("Statement: " + receipt_statement_account(rec))
            lines.append("  - " + " | ".join(b for b in bits if b))
            lines.append("    Photo: " + (rec.get("Photo Link") or "not on Drive (" + (rec.get("Photo File") or "no file") + ")"))
        lines.append("")
    lines.append("Sent by the CVH Employee Tool.")
    return "\n".join(lines)


def summary_html(summary):
    out = [
        "<p>Employee receipts saved <b>" + escape(summary["label"]) + "</b>.<br>",
        "Receipts: " + str(summary["count"]) + " &nbsp; Total: <b>" + escape(format_money(summary["total"])) + "</b>",
    ]
    filters = summary_filters_label(summary)
    if filters:
        out.append("<br>Filters: " + escape(filters))
    out.append("</p>")
    if not summary["employees"]:
        out.append("<p>No receipts were saved in this range.</p>")
    cell = 'style="border:1px solid #ccc;padding:4px 6px;text-align:left"'
    for person in summary["employees"]:
        out.append("<h3>" + escape(person["employee"]) + " – " + escape(format_money(person["total"])) + "</h3>")
        out.append('<table style="border-collapse:collapse"><tr><th ' + cell + ">Category</th><th " + cell
                   + ">Detail</th><th " + cell + ">Total</th></tr>")
        for category, info in person["categories"].items():
            for kind, amount in info["details"].items():
                out.append("<tr><td " + cell + ">" + escape(category) + "</td><td " + cell + ">" + escape(kind) + "</td><td "
                           + cell + ">" + escape(format_money(amount)) + "</td></tr>")
            out.append("<tr><td " + cell + "><b>" + escape(category) + " total</b></td><td " + cell + "></td><td " + cell
                       + "><b>" + escape(format_money(info["total"])) + "</b></td></tr>")
        out.append("</table>")
        out.append("<p>By category: " + escape(", ".join(
            category + " " + format_money(info["total"]) for category, info in person["categories"].items())) + "</p>")
        out.append('<table style="border-collapse:collapse"><tr>' + "".join(
            "<th " + cell + ">" + h + "</th>" for h in ("Date", "Amount", "Category", "Detail", "Purpose", "Vendor", "Receipt #", "Statement", "Photo")
        ) + "</tr>")
        for rec in person["items"]:
            link = _cell(rec.get("Photo Link"))
            photo = ('<a href="' + escape(link, quote=True) + '">Open photo</a>') if link.startswith("http") else escape(
                "not on Drive" + (" (" + rec.get("Photo File") + ")" if rec.get("Photo File") else ""))
            out.append("<tr>" + "".join("<td " + cell + ">" + v + "</td>" for v in (
                escape(rec.get("Date") or ""), escape(format_money(rec.get("Amount"))), escape(receipt_category(rec)),
                escape(receipt_detail(rec)),
                escape(rec.get("Purpose") or ""), escape(rec.get("Vendor") or ""), escape(rec.get("Receipt Number") or ""),
                escape(receipt_statement_account(rec)), photo,
            )) + "</tr>")
        out.append("</table>")
    out.append("<p style=\"color:#666\">Sent by the CVH Employee Tool.</p>")
    return "".join(out)



# ── IFTA report (from employee receipts, by the date on the receipt) ──

IFTA_TABLE_COLUMNS = (
    "Receipt date",
    "Employee",
    "Vendor",
    "Category",
    "Detail",
    "State",
    "Gallons",
    "Amount",
    "Photo",
)


def ifta_receipts_in_quarter(records, year, quarter):
    """Ground/vehicle fuel receipts whose receipt date falls in this IFTA quarter."""
    _year, _q, start, end = ifta_quarter(date(int(year), (int(quarter) - 1) * 3 + 1, 1))
    out = []
    for rec in records or []:
        if not is_ifta_record(rec):
            continue
        day = receipt_date_or_saved(rec)
        if day is not None and start <= day <= end:
            out.append(rec)
    return sort_receipts(out)


def ifta_gallons_by_state(records):
    """{state code: gallons} in jurisdiction order, then any unknown codes."""
    totals = {}
    unknown = 0.0
    for rec in records or []:
        gallons = ifta_gallons(rec) or 0.0
        state = ifta_state(rec)
        if not state:
            unknown = round(unknown + gallons, 3)
            continue
        totals[state] = round(totals.get(state, 0.0) + gallons, 3)
    out = _ordered(totals, IFTA_JURISDICTION_CODES)
    if unknown:
        out["(no state)"] = unknown
    return out


def ifta_state_rows(records):
    rows = []
    totals = ifta_gallons_by_state(records)
    for state, gallons in totals.items():
        label = ifta_jurisdiction_label(state) if state in IFTA_JURISDICTION_CODES else state
        rows.append({"State": label, "Gallons": format_gallons(gallons)})
    if rows:
        total = round(sum(parse_gallons(r["Gallons"]) or 0.0 for r in rows), 3)
        rows.append({"State": "All states", "Gallons": format_gallons(total)})
    return rows


def ifta_table_rows(records):
    rows = []
    for rec in sort_receipts(records):
        link = _cell(rec.get("Photo Link"))
        rows.append({
            "Receipt date": _cell(rec.get("Date")),
            "Employee": _cell(rec.get("Employee")),
            "Vendor": _cell(rec.get("Vendor")),
            "Category": receipt_category(rec),
            "Detail": receipt_detail(rec),
            "State": ifta_state(rec),
            "Gallons": format_gallons(rec.get("IFTA Gallons")) if parse_gallons(rec.get("IFTA Gallons")) is not None else "",
            "Amount": format_money(rec.get("Amount")),
            "Photo": link if link.startswith("http") else "",
        })
    return rows


def ifta_csv(records, year=None, quarter=None):
    """CSV of gallons by state, then the fuel receipts in the quarter."""
    buf = io.StringIO()
    if year and quarter:
        _y, _q, start, end = ifta_quarter(date(int(year), (int(quarter) - 1) * 3 + 1, 1))
        buf.write("IFTA gallons " + ifta_quarter_label(year, quarter) + " (" + period_label(start, end) + ")\n")
    writer = csv.DictWriter(buf, fieldnames=("State", "Gallons"), lineterminator="\n")
    writer.writeheader()
    for row in ifta_state_rows(records):
        writer.writerow(row)
    buf.write("\n")
    writer = csv.DictWriter(buf, fieldnames=list(IFTA_TABLE_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in ifta_table_rows(records):
        writer.writerow({k: row.get(k, "") for k in IFTA_TABLE_COLUMNS})
    return buf.getvalue()


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
    """Dedupe key for a send. Includes the date range, and any filters, so a custom range
    or a filtered view does not clash with a different period or unfiltered send."""
    key = "receipts:" + summary["start"].isoformat() + ":" + summary["end"].isoformat()
    suffix = filter_key(
        employee=summary.get("employee_filter"),
        category=summary.get("category_filter"),
        subcategory=summary.get("subcategory_filter"),
        statement_account=summary.get("statement_account_filter"),
        job=summary.get("job_filter"),
        expense_type=summary.get("expense_type_filter"),
    )
    if suffix:
        key += ":" + suffix
    return key


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
        result["error"] = "This receipts summary was already sent."
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
