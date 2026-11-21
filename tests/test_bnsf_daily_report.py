"""BNSF Daily Field Report and 10-day notice. Mocks only — no live Sheets or Gmail."""
import io
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bnsf_daily_report as dr  # noqa: E402
import bnsf_notice  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")
FIXTURE = ROOT / "tests" / "fixtures_ten_day_notice_young.txt"


class NotFound(Exception):
    pass


NotFound.__name__ = "WorksheetNotFound"


class WS:
    def __init__(self, book, title):
        self.book, self.title = book, title

    def row_values(self, n):
        rows = self.book.tabs[self.title]
        return list(rows[n - 1]) if len(rows) >= n else []

    def get_all_values(self):
        return [list(row) for row in self.book.tabs[self.title]]

    def append_row(self, row, value_input_option=None):
        self.book.appended.append((self.title, list(row), value_input_option))
        self.book.tabs[self.title].append(list(row))

    def update(self, range_name, values, value_input_option=None):
        self.book.updates.append((self.title, range_name, values, value_input_option))
        if range_name == "A1" and values:
            rows = self.book.tabs[self.title]
            if rows:
                rows[0] = list(values[0])
            else:
                rows.append(list(values[0]))


class Book:
    def __init__(self, tabs=None):
        self.tabs = {title: [list(row) for row in rows] for title, rows in (tabs or {}).items()}
        self.appended = []
        self.added = []
        self.updates = []

    def worksheet(self, title):
        if title not in self.tabs:
            raise NotFound(title)
        return WS(self, title)

    def add_worksheet(self, title, rows=0, cols=0):
        self.added.append((title, rows, cols))
        self.tabs[title] = []
        return WS(self, title)


def _pt(*parts):
    return datetime(*parts, tzinfo=PT)


def _weather(pilot, when, subdivision="LAUREL", division="Montana", mp=2.0, **extra):
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "Entry ID": "BW-test",
        "Timestamp": stamp,
        "Pilot": pilot,
        "Aircraft": "N480ML",
        "Division": division,
        "Subdivision": subdivision,
        "Mile marker": "%.1f" % mp if isinstance(mp, float) else str(mp),
        "Location": "%s MP %s" % (subdivision, mp),
        "Latitude": "45.669",
        "Longitude": "-108.771",
        "Wind direction": "SW",
        "Wind (mph)": "6",
        "Temperature (F)": "78",
        "Sky condition": "Clear",
        "Precipitation": "None",
    }
    record.update(extra)
    return record


def sample_report():
    notice = bnsf_notice.load_bundled_notices()[0]
    now = _pt(2026, 7, 16, 15, 0, 0)
    logs = [
        _weather("Ron Cline", _pt(2026, 7, 16, 7, 0), mp=1.0),
        _weather("Ron Cline", _pt(2026, 7, 16, 9, 0), mp=2.0, **{"Sky condition": "Partly Cloudy", "Wind (mph)": "8", "Wind direction": "W", "Temperature (F)": "82"}),
        _weather("Ron Cline", _pt(2026, 7, 16, 11, 0), mp=3.2, **{"Temperature (F)": "86", "Wind (mph)": "10"}),
    ]
    clocks = {
        "bnsf_start": "7:12 AM",
        "bnsf_end": "3:45 PM",
        "cvh_start": "6:30 AM",
        "cvh_end": "4:15 PM",
    }
    spray = dr.empty_spray_rows()
    spray[0] = {"Time": "7:20 AM", "MP ST": "0.7", "MP END": "2.1", "MP ST 2": "2.1", "MP END 2": "0.7", "Notes": ""}
    spray[1] = {"Time": "8:05 AM", "MP ST": "2.1", "MP END": "4.3", "MP ST 2": "4.3", "MP END 2": "2.1", "Notes": ""}
    spray[2] = {"Time": "9:10 AM", "MP ST": "1.4", "MP END": "1.6", "MP ST 2": "", "MP END 2": "", "Notes": "Buffered crossing"}
    report = dr.gather_daily_report(
        "Ron Cline",
        aircraft="N480ML – Enstrom 480 Turbine (SN 5032)",
        weather_records=logs,
        clocks=clocks,
        notice=notice,
        spray_rows=spray,
        loads="8",
        hobbs_start="1234.2",
        hobbs_end="1236.8",
        video_on="Yes",
        now=now,
        county_lookup=lambda lat, lon: "Yellowstone",
    )
    return report, notice


class UnitsAndClocksTests(unittest.TestCase):
    def test_acres_are_loads_times_15(self):
        self.assertEqual(dr.acres_from_loads(8), "120")
        self.assertEqual(dr.acres_from_loads("2.5"), "37.5")
        self.assertEqual(dr.acres_from_loads(""), "")
        self.assertEqual(dr.acres_from_loads(-1), "")

    def test_flight_time_from_hobbs(self):
        self.assertEqual(dr.flight_time_hours("1234.2", "1236.8"), "2.6")
        self.assertEqual(dr.flight_time_hours("10", "9"), "")
        self.assertEqual(dr.flight_time_hours("", "10"), "")

    def test_aircraft_defaults_to_n480ml(self):
        self.assertEqual(dr.aircraft_id(""), "N480ML")
        self.assertEqual(dr.aircraft_id("N480ML – Enstrom 480 Turbine (SN 5032)"), "N480ML")
        self.assertEqual(dr.aircraft_id("N893PC – Robinson R44 Raven II (SN 14940)"), "N893PC")

    def test_clock_round_trip(self):
        when = _pt(2026, 7, 16, 7, 12, 0)
        self.assertEqual(dr.format_clock(when), "7:12 AM")
        parsed = dr.parse_clock("7:12 AM", day=when)
        self.assertEqual(parsed.hour, 7)
        self.assertEqual(parsed.minute, 12)
        self.assertEqual(dr.format_clock(parsed), "7:12 AM")
        self.assertEqual(dr.parse_clock("15:45", day=when).hour, 15)

    def test_ops_clocks_store(self):
        store = {}
        now = _pt(2026, 7, 16, 7, 12)
        dr.set_ops_clocks(store, "Ron Cline", {"bnsf_start": "7:12 AM"}, now=now)
        clocks = dr.get_ops_clocks(store, "Ron Cline", now=now)
        self.assertEqual(clocks["bnsf_start"], "7:12 AM")
        other = dr.get_ops_clocks(store, "Someone Else", now=now)
        self.assertEqual(other["bnsf_start"], "")


class NoticeParseTests(unittest.TestCase):
    def test_bundled_young_notice(self):
        notices = bnsf_notice.load_bundled_notices()
        self.assertEqual(len(notices), 1)
        notice = notices[0]
        self.assertEqual(notice["roadmaster"], "YOUNG, RUSSELL")
        self.assertEqual(notice["division"], "Montana")
        self.assertEqual(len(notice["segments"]), 9)
        self.assertIn("Triumph 22K", notice["product_mix"])
        self.assertIn("Edict RTU", notice["product_mix"])
        self.assertIn("MSM 60", notice["product_mix"])
        self.assertIn("Novita DF", notice["product_mix"])
        self.assertNotIn("Foamnomore", notice["product_mix"])

    def test_parse_fixture_text(self):
        text = FIXTURE.read_text(encoding="utf-8")
        notice = bnsf_notice.parse_ten_day_notice(text)
        self.assertEqual(notice["roadmaster"], "YOUNG, RUSSELL")
        self.assertEqual(len(notice["segments"]), 9)
        label = bnsf_notice.segment_label(notice["segments"][1])
        self.assertEqual(label, "LAUREL LS 362 (MP 0.7–4.3) ML")

    def test_notice_from_upload_text(self):
        data = FIXTURE.read_bytes()
        notice = bnsf_notice.notice_from_upload("forwarded_notice.txt", data)
        self.assertEqual(len(notice["segments"]), 9)
        self.assertEqual(notice["roadmaster"], "YOUNG, RUSSELL")

    def test_match_tightest_segment(self):
        notice = bnsf_notice.load_bundled_notices()[0]
        laurel = bnsf_notice.match_segment(notice, "LAUREL", 2.0)
        self.assertEqual(laurel["line_segment"], "362")
        self.assertEqual(laurel["subdivision"], "LAUREL")
        second = bnsf_notice.match_segment(notice, "MRL SECOND SUB", 50)
        self.assertEqual(second["line_segment"], "41")
        self.assertEqual(second["subdivision"], "MRL SECOND SUB")
        # Yard MP 13.0 is on Laurel Yard, not the wide Billings Yard 0–9998 range, when subdivision is known.
        yard = bnsf_notice.match_segment(notice, "LAUREL YARD", 13.0)
        self.assertEqual(yard["line_segment"], "736")


class GatherReportTests(unittest.TestCase):
    def test_gathers_notice_segment_mix_and_weather(self):
        report, notice = sample_report()
        self.assertEqual(report["Pilot"], "Ron Cline")
        self.assertEqual(report["Aircraft"], "N480ML")
        self.assertEqual(report["Date"], "2026-07-16")
        self.assertEqual(report["Date display"], "07/16/2026")
        self.assertEqual(report["Flight Time"], "2.6")
        self.assertEqual(report["Loads"], "8")
        self.assertEqual(report["Acres Sprayed"], "120")
        self.assertEqual(report["Division"], "Montana")
        self.assertEqual(report["BNSF Subdivision"], "LAUREL")
        self.assertEqual(report["Line Segment"], "LAUREL LS 362 (MP 0.7–4.3) ML")
        self.assertEqual(report["MP Start"], "0.7")
        self.assertEqual(report["MP End"], "4.3")
        self.assertEqual(report["County"], "Yellowstone")
        self.assertEqual(report["BNSF Time Start"], "7:12 AM")
        self.assertEqual(report["CVH Time End"], "4:15 PM")
        self.assertEqual(report["Product mix"], notice["product_mix"])
        self.assertEqual(report["Roadmaster"], "YOUNG, RUSSELL")
        self.assertEqual(report["Video ON"], "Yes")
        slots = report["weather_slots"]
        self.assertEqual(slots[0]["Time"], "7:00 AM")
        self.assertEqual(slots[0]["Sky"], "Clear")
        self.assertEqual(slots[0]["Precipitation"], "None")
        self.assertEqual(slots[1]["Temperature"], "82")
        self.assertEqual(slots[2]["MP Location"], "LAUREL MP 3.2")
        self.assertEqual(slots[3]["Time"], "")
        self.assertEqual(report["spray_rows"][0]["MP ST"], "0.7")
        self.assertEqual(report["spray_rows"][2]["Notes"], "Buffered crossing")

    def test_without_notice_uses_form_mix_and_blank_segment(self):
        now = _pt(2026, 7, 16, 12, 0)
        report = dr.gather_daily_report(
            "Ron Cline",
            weather_records=[_weather("Ron Cline", now)],
            now=now,
            county_lookup=lambda *a: "",
        )
        self.assertEqual(report["Line Segment"], "")
        self.assertIn("Foamnomore", report["Product mix"])

    def test_ignores_other_pilot_and_other_day(self):
        now = _pt(2026, 7, 16, 12, 0)
        logs = [
            _weather("Ron Cline", now, mp=2.0),
            _weather("Someone Else", now, mp=9.0),
            _weather("Ron Cline", _pt(2026, 7, 15, 12, 0), mp=8.0),
        ]
        report = dr.gather_daily_report("Ron Cline", weather_records=logs, now=now, county_lookup=lambda *a: "")
        self.assertEqual(report["MP Start"], "2.0")
        self.assertEqual(report["MP End"], "2.0")


class SheetAndDocumentTests(unittest.TestCase):
    def test_record_round_trip(self):
        report, _notice = sample_report()
        record = dr.report_to_record(report, when=_pt(2026, 7, 16, 16, 0))
        self.assertTrue(record["Entry ID"].startswith("DR-20260716-"))
        self.assertEqual(record["Line Segment"], "LAUREL LS 362 (MP 0.7–4.3) ML")
        self.assertEqual(record["Weather 1 Time"], "7:00 AM")
        self.assertEqual(record["Weather 2 Temperature"], "82")
        self.assertIn("0.7", record["Spray log"])
        back = dr.record_to_report(record)
        self.assertEqual(back["Line Segment"], report["Line Segment"])
        self.assertEqual(back["weather_slots"][1]["Temperature"], "82")
        self.assertEqual(back["spray_rows"][2]["Notes"], "Buffered crossing")
        self.assertEqual(back["Date display"], "07/16/2026")

    def test_saves_append_only_daily_report_tab(self):
        report, _ = sample_report()
        record = dr.report_to_record(report, when=_pt(2026, 7, 16, 16, 0))
        book = Book()
        dest = dr.save_daily_report_record(record, book)
        self.assertEqual(dest, "Google Sheets (BNSF Daily Reports)")
        self.assertEqual(book.added[0][0], "BNSF Daily Reports")
        self.assertEqual(book.tabs["BNSF Daily Reports"][0], list(dr.BNSF_DAILY_REPORT_COLUMNS))
        # First append is the new-tab header, second is the report row.
        self.assertEqual(len(book.appended), 2)
        saved = dict(zip(dr.BNSF_DAILY_REPORT_COLUMNS, book.appended[1][1]))
        self.assertEqual(saved["Pilot"], "Ron Cline")
        self.assertEqual(saved["Line Segment"], record["Line Segment"])
        # Saving again appends a second version row, and does not add another tab.
        dr.save_daily_report_record(record, book)
        self.assertEqual(len(book.added), 1)
        self.assertEqual(len(book.appended), 3)

    def test_saves_uploaded_notice(self):
        notice = bnsf_notice.load_bundled_notices()[0]
        book = Book()
        saved = dr.save_notice_record(notice, book, source="forwarded.txt", when=_pt(2026, 11, 21, 9, 42))
        self.assertEqual(book.added[0][0], "BNSF 10-Day Notices")
        loaded = dr.load_saved_notices(book)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["roadmaster"], "YOUNG, RUSSELL")
        self.assertEqual(len(loaded[0]["segments"]), 9)
        self.assertTrue(saved["Entry ID"].startswith("TN-"))

    def test_fills_word_form_and_uses_actual_year(self):
        report, notice = sample_report()
        data = dr.fill_daily_report_docx(report)
        self.assertTrue(data.startswith(b"PK"))
        from docx import Document
        document = Document(io.BytesIO(data))
        blob = "\n".join(p.text for p in document.paragraphs)
        self.assertIn("07/16/2026", blob)
        self.assertNotIn("/2025", blob)
        self.assertIn(notice["product_mix"], blob)
        header = "\n".join(c.text for c in document.tables[0]._cells)
        self.assertIn("Ron Cline", header)
        self.assertIn("N480ML", header)
        self.assertIn("LAUREL LS 362", header)
        self.assertIn("Yellowstone", header)
        self.assertIn("120", header)
        self.assertIn("2.6", header)
        self.assertIn("7:12 AM", header)
        self.assertIn("6:30 AM", header)
        weather = "\n".join(c.text for r in document.tables[1].rows for c in r.cells)
        self.assertIn("7:00 AM", weather)
        self.assertIn("Partly Cloudy", weather)
        spray = "\n".join(c.text for r in document.tables[2].rows for c in r.cells)
        self.assertIn("Buffered crossing", spray)
        self.assertIn("0.7", spray)

    def test_builds_pdf(self):
        report, notice = sample_report()
        data = dr.build_daily_report_pdf(report)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 2000)
        # Extract text if pypdf is available.
        try:
            from pypdf import PdfReader
        except ImportError:
            return
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("DAILY FIELD REPORT", text)
        self.assertIn("07/16/2026", text)
        self.assertIn("Ron Cline", text)
        self.assertIn("N480ML", text)
        self.assertIn("LAUREL LS 362", text)
        self.assertIn("Yellowstone", text)
        self.assertIn("Triumph 22K", text)
        self.assertIn("NPDES", text)
        self.assertEqual(len(reader.pages), 2)


class CountyLookupTests(unittest.TestCase):
    def test_lookup_county_from_nws_zone(self):
        session = mock.Mock()

        def get(url, **kwargs):
            response = mock.Mock()
            response.raise_for_status = mock.Mock()
            if "/points/" in url:
                response.json.return_value = {
                    "properties": {"county": "https://api.weather.gov/zones/county/MTC111"}
                }
            elif url.endswith("MTC111"):
                response.json.return_value = {"properties": {"name": "Yellowstone"}}
            else:
                raise AssertionError(url)
            return response

        session.get.side_effect = get
        with mock.patch.object(dr.bw, "_session_get", side_effect=lambda sess, url, **k: sess.get(url, **k)):
            self.assertEqual(dr.lookup_county(45.669, -108.771, session=session), "Yellowstone")
