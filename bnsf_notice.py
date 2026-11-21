"""Parse and store BNSF 10-day notices (line segments and roadmaster product mix)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "bnsf_ten_day_notices.json"

_SEGMENT_RE = re.compile(
    r"^(?P<sub>.+?)\s+(?P<cc>\d{4,6})\s+(?P<ls>\d+)\s+(?P<begin>\d+(?:\.\d+)?)\s+"
    r"(?P<end>\d+(?:\.\d+)?)\s+(?P<kind>YD|ML)\b(?:\s+(?P<eng>.+))?\s*$",
    re.IGNORECASE,
)
_RATE_RE = re.compile(
    r"^(?P<product>.+?)\s+(?P<rate>\d+(?:\.\d+)?)\s*(?P<unit>(?:fl\s*)?oz/Acre|(?:fl\s*)?oz/@|oz/100|gal/Acre|gal/@)\s*$",
    re.IGNORECASE,
)
_LABEL_RE = re.compile(
    r"^(Roadmaster|Division Engineer|Division|Spray Pattern|Prescribed Acres(?: For Cost Center)?"
    r"|Estimated Work Days|Program Name|Contractor|Work Description|Subdivisions|"
    r"GPA|Comment)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def _cell(value):
    return str(value or "").strip()


def format_mp(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _cell(value)
    text = ("%.2f" % number).rstrip("0").rstrip(".")
    return text or "0"


def format_product_mix(rates):
    parts = []
    for rate in rates or []:
        product = _cell(rate.get("product"))
        amount = rate.get("rate")
        unit = _cell(rate.get("unit")) or "oz/Acre"
        if not product:
            continue
        if amount is None or amount == "":
            parts.append(product)
        else:
            try:
                amount_text = ("%.2f" % float(amount)).rstrip("0").rstrip(".")
                if "." not in amount_text:
                    amount_text = "%.2f" % float(amount)
            except (TypeError, ValueError):
                amount_text = str(amount)
            parts.append("%s: %s %s" % (product, amount_text, unit))
    return ", ".join(parts)


def segment_label(segment):
    """Single-line label for the Daily Field Report Line Segment field."""
    sub = _cell(segment.get("subdivision"))
    number = _cell(segment.get("line_segment"))
    begin = format_mp(segment.get("begin_mp"))
    end = format_mp(segment.get("end_mp"))
    kind = _cell(segment.get("kind"))
    label = "%s LS %s (MP %s–%s)" % (sub, number, begin, end)
    if kind:
        label += " %s" % kind
    return label


def _clean_label_value(text):
    return re.sub(r"\s+", " ", _cell(text)).strip(" ,")


def _parse_roadmaster(value):
    text = _clean_label_value(value)
    match = re.match(r"(?P<name>.+?)\s+(?P<ident>\d{3,6})\s*$", text)
    if match:
        return _clean_label_value(match.group("name")), match.group("ident")
    # "13731 (YOUNG, RUSSELL)"
    match = re.match(r"(?P<ident>\d{3,6})\s*\((?P<name>.+)\)\s*$", text)
    if match:
        return _clean_label_value(match.group("name")), match.group("ident")
    return text, ""


def parse_ten_day_notice(text):
    """Parse a forwarded BNSF 10-day notice email or pasted text."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # Unwrap simple email quoting
    lines = []
    for line in raw.split("\n"):
        stripped = re.sub(r"^>+\s?", "", line)
        lines.append(stripped)
    # Join wrapped header values that break mid-field
    joined = []
    for line in lines:
        if joined and re.match(r"^[A-Z][A-Z0-9:,' /.-]*$", line) and not _LABEL_RE.match(line) and not _SEGMENT_RE.match(line) and not _RATE_RE.match(line):
            # likely a continuation of the previous line (e.g. "HOWARD")
            if joined[-1].endswith(",") or joined[-1].endswith("(") or joined[-1].endswith("-"):
                joined[-1] = joined[-1] + " " + line
                continue
        joined.append(line)

    notice = {
        "id": "",
        "title": "",
        "program_name": "",
        "work_description": "",
        "contractor": "",
        "roadmaster": "",
        "roadmaster_id": "",
        "division_engineer": "",
        "division": "",
        "spray_pattern": "",
        "prescribed_acres": None,
        "gpa": None,
        "estimated_work_days": None,
        "chemical_rates": [],
        "product_mix": "",
        "segments": [],
        "no_spray_zones": [],
        "subdivisions": [],
    }
    in_rates = False
    for line in joined:
        text_line = _cell(line)
        if not text_line:
            continue
        if re.match(r"^chemical rate notes$", text_line, re.I):
            in_rates = True
            continue
        if re.match(r"^(please confirm|timely application|we appreciate|your crew leader)", text_line, re.I):
            in_rates = False
        label_match = _LABEL_RE.match(text_line)
        if label_match:
            label = label_match.group(1).lower()
            value = label_match.group(2)
            if label.startswith("roadmaster"):
                # May include mobile/email on the same line
                first = re.split(r"\s+Mobile:|\s+Email:", value, maxsplit=1)[0]
                name, ident = _parse_roadmaster(first)
                # "13731 (YOUNG, RUSSELL)" form used under Program Name
                if "roadmaster:" in text_line.lower() and "(" in value:
                    alt_name, alt_id = _parse_roadmaster(value)
                    name = name or alt_name
                    ident = ident or alt_id
                if not notice["roadmaster"]:
                    notice["roadmaster"] = name
                if ident:
                    notice["roadmaster_id"] = ident
            elif label.startswith("division engineer"):
                first = re.split(r"\s+Phone:|\s+Mobile:|\s+Email:", value, maxsplit=1)[0]
                if not notice["division_engineer"]:
                    notice["division_engineer"] = _clean_label_value(first)
            elif label == "division":
                if not notice["division"]:
                    notice["division"] = _clean_label_value(value).title()
            elif label == "spray pattern":
                notice["spray_pattern"] = _clean_label_value(value)
            elif label.startswith("prescribed acres"):
                try:
                    notice["prescribed_acres"] = float(re.search(r"[\d.]+", value).group())
                except (AttributeError, ValueError):
                    pass
            elif label == "estimated work days":
                try:
                    notice["estimated_work_days"] = int(float(re.search(r"[\d.]+", value).group()))
                except (AttributeError, ValueError, TypeError):
                    pass
            elif label == "program name":
                # "2025 Aerial Program-Montana SW (old MRL area) Engineer: TRIPP, HOWARD"
                prog = re.split(r"\s+Engineer:", value, maxsplit=1)[0]
                notice["program_name"] = _clean_label_value(prog)
                rest = value[len(prog):]
                eng = re.search(r"Engineer:\s*(.+?)(?:\s+Contractor:|$)", value)
                if eng and not notice["division_engineer"]:
                    notice["division_engineer"] = _clean_label_value(eng.group(1))
                contractor = re.search(r"Contractor:\s*(.+?)(?:\s+Roadmaster:|$)", value)
                if contractor:
                    notice["contractor"] = _clean_label_value(contractor.group(1))
                rdm = re.search(r"Roadmaster:\s*(.+?)(?:\s+Work\s+Description:|$)", value, re.I)
                if rdm:
                    name, ident = _parse_roadmaster(rdm.group(1))
                    if name:
                        notice["roadmaster"] = notice["roadmaster"] or name
                    if ident:
                        notice["roadmaster_id"] = notice["roadmaster_id"] or ident
            elif label == "contractor":
                notice["contractor"] = _clean_label_value(re.split(r"\s+Roadmaster:", value)[0])
            elif label == "work description":
                notice["work_description"] = _clean_label_value(value)
            elif label == "subdivisions":
                notice["subdivisions"] = [p.strip() for p in value.split(",") if p.strip()]
            elif label == "gpa":
                try:
                    notice["gpa"] = float(re.search(r"[\d.]+", value).group())
                except (AttributeError, ValueError):
                    pass
            elif label == "comment":
                gpa = re.search(r"GPA\s+([\d.]+)", value, re.I)
                if gpa:
                    notice["gpa"] = float(gpa.group(1))
                acres = re.search(r"Acres\s+([\d.]+)", value, re.I)
                if acres and notice["prescribed_acres"] is None:
                    notice["prescribed_acres"] = float(acres.group(1))
            in_rates = False
            continue
        if re.search(r"GPA\s+[\d.]+", text_line, re.I):
            gpa = re.search(r"GPA\s+([\d.]+)", text_line, re.I)
            if gpa:
                notice["gpa"] = float(gpa.group(1))
        seg = _SEGMENT_RE.match(text_line)
        if seg:
            notice["segments"].append({
                "subdivision": _cell(seg.group("sub")),
                "cost_center": seg.group("cc"),
                "line_segment": seg.group("ls"),
                "begin_mp": float(seg.group("begin")),
                "end_mp": float(seg.group("end")),
                "kind": seg.group("kind").upper(),
                "engineer": _clean_label_value(seg.group("eng") or ""),
            })
            continue
        rate = _RATE_RE.match(text_line)
        if rate and (in_rates or "oz" in text_line.lower()):
            notice["chemical_rates"].append({
                "product": _cell(rate.group("product")),
                "rate": float(rate.group("rate")),
                "unit": re.sub(r"\s+", " ", rate.group("unit")).replace("/@", "/Acre"),
            })
            continue

    notice["product_mix"] = format_product_mix(notice["chemical_rates"])
    if not notice["subdivisions"]:
        notice["subdivisions"] = list(dict.fromkeys(s["subdivision"] for s in notice["segments"]))
    if notice["roadmaster"] and notice["program_name"]:
        notice["title"] = "%s — RDM %s" % (notice["program_name"], notice["roadmaster"].title())
    elif notice["roadmaster"]:
        notice["title"] = "RDM %s" % notice["roadmaster"].title()
    elif notice["program_name"]:
        notice["title"] = notice["program_name"]
    ident = (notice["roadmaster_id"] or re.sub(r"[^a-z0-9]+", "-", (notice["roadmaster"] or "notice").lower()).strip("-"))
    year = ""
    year_match = re.search(r"\b(20\d{2})\b", notice["program_name"] or raw[:400])
    if year_match:
        year = year_match.group(1)
        notice["year"] = int(year)
    notice["id"] = "-".join(p for p in [year, "rdm", ident] if p)
    return notice


def extract_text_from_upload(name, data):
    """Return text from an uploaded notice (bytes) for parsing."""
    filename = _cell(name).lower()
    if not data:
        return ""
    if filename.endswith(".json"):
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return data.decode("utf-8", errors="replace")
        if isinstance(payload, dict) and (payload.get("segments") or payload.get("product_mix") or payload.get("notices")):
            return json.dumps(payload)
        return json.dumps(payload)
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception:
            return ""
    if filename.endswith(".docx"):
        try:
            import io
            from docx import Document
            document = Document(io.BytesIO(data))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" ".join(c.text for c in row.cells))
            return "\n".join(parts)
        except Exception:
            return ""
    return data.decode("utf-8", errors="replace")


def notice_from_upload(name, data):
    """Parse an uploaded file into one notice (or the first in a JSON list)."""
    filename = _cell(name).lower()
    if filename.endswith(".json"):
        try:
            payload = json.loads(data.decode("utf-8"))
            if isinstance(payload, dict) and "notices" in payload:
                notices = payload.get("notices") or []
                return notices[0] if notices else parse_ten_day_notice("")
            if isinstance(payload, dict) and (payload.get("segments") or payload.get("chemical_rates") or payload.get("roadmaster")):
                if not payload.get("product_mix"):
                    payload["product_mix"] = format_product_mix(payload.get("chemical_rates"))
                return payload
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    text = extract_text_from_upload(name, data)
    return parse_ten_day_notice(text)


@lru_cache(maxsize=1)
def load_bundled_notices(path=None):
    data_path = Path(path) if path else DATA_PATH
    if not data_path.is_file():
        return []
    with data_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return list(payload.get("notices") or [])
    if isinstance(payload, list):
        return list(payload)
    return []


def match_segment(notice, subdivision="", milepost=None):
    """Pick the tightest line segment that contains this milepost, preferring the same subdivision."""
    segments = list((notice or {}).get("segments") or [])
    if not segments:
        return None
    mp = None
    if milepost is not None and milepost != "":
        try:
            mp = float(milepost)
        except (TypeError, ValueError):
            mp = None
    if mp is None:
        return segments[0]
    sub = _cell(subdivision).lower()

    def covers(segment):
        begin, end = float(segment["begin_mp"]), float(segment["end_mp"])
        low, high = (begin, end) if begin <= end else (end, begin)
        return low - 0.05 <= mp <= high + 0.05

    def tightness(segment):
        return abs(float(segment["end_mp"]) - float(segment["begin_mp"]))

    def sub_score(segment):
        name = _cell(segment.get("subdivision")).lower()
        if not sub:
            return 1
        if name == sub:
            return 0
        if sub in name or name in sub:
            return 1
        return 2

    covered = [s for s in segments if covers(s)]
    pool = covered or segments
    pool.sort(key=lambda s: (sub_score(s), tightness(s)))
    return pool[0]
