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
import bnsf_voice  # noqa: E402

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


class NotSprayedTests(unittest.TestCase):
    def test_parses_digit_and_spoken_mileposts(self):
        self.assertEqual(dr.parse_not_sprayed_speech("MP 112.4")["mp"], 112.4)
        self.assertEqual(dr.parse_not_sprayed_speech("milepost one twelve point four")["mp"], 112.4)
        self.assertEqual(dr.parse_not_sprayed_speech("112 point 4")["mp"], 112.4)
        self.assertEqual(dr.parse_not_sprayed_speech("mile post one hundred twelve point four")["mp"], 112.4)
        spoken = dr.parse_not_sprayed_speech("trees over the track at milepost one twelve point four")
        self.assertEqual(spoken["mp"], 112.4)
        self.assertEqual(spoken["reason"], "trees over the track at")
        plain = dr.parse_not_sprayed_speech("trees over the track")
        self.assertIsNone(plain["mp"])
        self.assertEqual(plain["reason"], "trees over the track")

    def test_spoken_milepost_overrides_gps_and_keeps_transcript(self):
        row = dr.capture_not_sprayed_fix(
            lat=45.0,
            lon=-108.0,
            now=_pt(2026, 7, 16, 14, 14),
            aircraft="Enstrom N480ML",
            points=[dr.bw.MilepostPoint("Montana", "Laurel", 100.2, 45.0, -108.0)],
        )
        self.assertEqual(row["MP"], "100.2")
        self.assertEqual(row["MP source"], "GPS")
        self.assertEqual(row["Aircraft"], "N480ML")
        self.assertEqual(row["Status"], "Pending review")
        self.assertEqual(row["Time"], "2:14 PM")
        updated = dr.apply_spoken_milepost(row, "MP 112.4 trees over the track")
        self.assertEqual(updated["MP"], "112.4")
        self.assertEqual(updated["MP source"], "Spoken")
        self.assertEqual(updated["GPS MP"], "100.2")
        self.assertEqual(updated["Reason"], "trees over the track")
        self.assertEqual(updated["Transcript"], "MP 112.4 trees over the track")
        self.assertEqual(updated["Status"], "Pending review")

    def test_mark_mp_row_has_time_and_no_reason(self):
        row = dr.capture_not_sprayed_fix(
            lat=45.0,
            lon=-108.0,
            now=_pt(2026, 7, 16, 9, 5),
            points=[dr.bw.MilepostPoint("Montana", "Laurel", 88.0, 45.0, -108.0)],
        )
        self.assertEqual(row["MP"], "88.0")
        self.assertEqual(row["MP source"], "GPS")
        self.assertEqual(row["Reason"], "")
        self.assertEqual(row["Transcript"], "")
        self.assertEqual(row["Aircraft"], "N480ML")
        self.assertEqual(row["Status"], "Pending review")

    def test_not_sprayed_round_trip_and_report_output(self):
        report, _notice = sample_report()
        row = dr.apply_spoken_milepost(
            dr.capture_not_sprayed_fix(now=_pt(2026, 7, 16, 14, 14), aircraft="N480ML"),
            "milepost one twelve point four signal wires",
        )
        report["not_sprayed"] = [row]
        record = dr.report_to_record(report, when=_pt(2026, 7, 16, 16, 0))
        stored = json.loads(record["Not sprayed"])
        self.assertEqual(stored[0]["MP"], "112.4")
        self.assertEqual(stored[0]["MP source"], "Spoken")
        back = dr.record_to_report(record)
        self.assertEqual(back["not_sprayed"][0]["Reason"], "signal wires")
        self.assertEqual(back["not_sprayed"][0]["Transcript"], "milepost one twelve point four signal wires")
        filled = dr.spray_rows_with_not_sprayed(report["spray_rows"], report["not_sprayed"])
        self.assertEqual(report["spray_rows"][2]["Notes"], "Buffered crossing")
        empty_index = next(i for i, item in enumerate(report["spray_rows"]) if not any(item.values()))
        self.assertEqual(empty_index, 3)
        self.assertIn("signal wires", filled[empty_index]["Notes"])
        self.assertEqual(filled[empty_index]["MP ST"], "112.4")
        self.assertEqual(filled[2]["Notes"], "Buffered crossing")

        data = dr.build_daily_report_pdf(report)
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        self.assertIn("NOT SPRAYED", text)
        self.assertIn("112.4", text)
        self.assertIn("signal wires", text)
        self.assertIn("N480ML", text)
        self.assertIn("Pending review", text)

        from docx import Document
        document = Document(io.BytesIO(dr.fill_daily_report_docx(report)))
        blob = "\n".join(p.text for p in document.paragraphs)
        self.assertIn("signal wires", blob)
        self.assertIn("112.4", blob)

    def test_speech_stays_off_without_a_key_and_errors_hide_the_key(self):
        calls = []

        def poster(audio, settings):
            calls.append(settings["api_key"])
            raise RuntimeError("nope " + settings["api_key"])

        self.assertIsNone(dr.transcribe_not_sprayed_clip(b"clip", secrets={}, http_post=poster))
        self.assertEqual(calls, [])
        self.assertFalse(dr.speech_settings({"bnsf_speech": {"enabled": True, "api_key": ""}})["enabled"])
        secrets = {"bnsf_speech": {"enabled": True, "api_key": "sk-test-should-not-appear"}}
        self.assertTrue(dr.speech_settings(secrets)["enabled"])
        with self.assertRaises(ValueError) as caught:
            dr.transcribe_not_sprayed_clip(b"clip", secrets=secrets, http_post=poster)
        self.assertNotIn("sk-test-should-not-appear", str(caught.exception))
        self.assertEqual(calls, ["sk-test-should-not-appear"])

        def ok(audio, settings):
            return "milepost one twelve point four trees"
        heard = dr.transcribe_not_sprayed_clip(b"clip", secrets=secrets, http_post=ok)
        self.assertEqual(dr.parse_not_sprayed_speech(heard)["mp"], 112.4)


class NavigationAndSprayGateTests(unittest.TestCase):
    LABELS = [
        "N893PC – Robinson R44 Raven II (SN 14940)",
        "N480ML – Enstrom 480 Turbine (SN 5032)",
    ]

    def test_bnsf_button_waits_for_aircraft_and_far_137(self):
        hidden = {"button": False, "pages": False}
        self.assertEqual(dr.pilot_menu_bnsf("", "Part 137", opened=True), hidden)
        self.assertEqual(dr.pilot_menu_bnsf("Enstrom 480", "Part 91", opened=True), hidden)
        self.assertEqual(dr.pilot_menu_bnsf("Enstrom 480", "Part 135", opened=True), hidden)
        self.assertEqual(dr.pilot_menu_bnsf("Enstrom 480", "Part 133", opened=True), hidden)
        self.assertEqual(dr.pilot_menu_bnsf("Robinson R44 Raven II", "Part 137", opened=False), {"button": True, "pages": False})
        self.assertEqual(dr.pilot_menu_bnsf("Enstrom 480", "Part 137", opened=True), {"button": True, "pages": True})

    def test_chosen_aircraft_is_carried_into_bnsf(self):
        robinson = dr.bnsf_aircraft_label("N893PC", self.LABELS)
        enstrom = dr.bnsf_aircraft_label("N480ML", self.LABELS)
        self.assertIn("N893PC", robinson)
        self.assertNotIn("N480ML", robinson)
        self.assertIn("N480ML", enstrom)
        self.assertEqual(dr.aircraft_id(robinson), "N893PC")
        self.assertEqual(dr.aircraft_id(enstrom), "N480ML")
        report = dr.gather_daily_report("Ron Cline", aircraft=robinson, now=_pt(2026, 7, 16, 12, 0), county_lookup=lambda *a: "")
        self.assertEqual(report["Aircraft"], "N893PC")

    def test_voice_and_mark_only_while_spraying_review_stays_open(self):
        now = _pt(2026, 7, 16, 8, 0)
        store = {}
        self.assertFalse(dr.spraying_in_progress(dr.get_ops_clocks(store, "Ron Cline", now=now)))
        self.assertEqual(dr.not_sprayed_actions(False)["note"], "Available while spraying.")
        self.assertFalse(dr.not_sprayed_actions(False)["capture"])
        self.assertTrue(dr.not_sprayed_actions(False)["review"])
        started = dr.start_bnsf_spray(store, "Ron Cline", now=now)
        self.assertEqual(started["bnsf_start"], "8:00 AM")
        self.assertEqual(started["bnsf_end"], "")
        self.assertTrue(dr.spraying_in_progress(started))
        self.assertTrue(dr.not_sprayed_actions(True)["capture"])
        self.assertEqual(dr.not_sprayed_actions(True)["note"], "")
        stopped = dr.stop_bnsf_spray(store, "Ron Cline", now=_pt(2026, 7, 16, 11, 30))
        self.assertEqual(stopped["bnsf_end"], "11:30 AM")
        self.assertFalse(dr.spraying_in_progress(stopped))
        self.assertTrue(dr.not_sprayed_actions(dr.spraying_in_progress(stopped))["review"])
        again = dr.start_bnsf_spray(store, "Ron Cline", now=_pt(2026, 7, 16, 13, 0))
        self.assertEqual(again["bnsf_end"], "")
        self.assertTrue(dr.spraying_in_progress(again))


class VoiceCommandTests(unittest.TestCase):
    def _points(self):
        return [
            dr.bw.MilepostPoint("Montana", "Laurel", 112.4, 45.0, -108.0),
            dr.bw.MilepostPoint("Montana", "Laurel", 118.2, 45.2, -108.2),
        ]

    def _step(self, session, text, kind="utterance", when=None, lat=None, lon=None):
        return bnsf_voice.apply_voice_command(
            session,
            text,
            kind=kind,
            now=when,
            lat=lat,
            lon=lon,
            points=self._points(),
            aircraft="N480ML",
        )

    def test_command_variants_and_noise(self):
        self.assertEqual(bnsf_voice.match_voice_command("Activate Milepost"), "activate")
        self.assertEqual(bnsf_voice.match_voice_command("uh activate the mile post please"), "activate")
        self.assertEqual(bnsf_voice.match_voice_command("activate mp"), "activate")
        self.assertEqual(bnsf_voice.match_voice_command("Start"), "start")
        self.assertEqual(bnsf_voice.match_voice_command("ok stop now"), "stop")
        self.assertEqual(bnsf_voice.match_voice_command("cancel that"), "cancel")
        self.assertIsNone(bnsf_voice.match_voice_command("the wind is loud near the stop sign"))

    def test_activate_start_stop_reason_save_and_loop(self):
        session, outcome = self._step(bnsf_voice.new_voice_session(), "", kind="power-on")
        self.assertEqual(outcome["phase"], "listening")
        self.assertIn("activate milepost", outcome["speak"].lower())

        session, outcome = self._step(session, "activate mile post")
        self.assertEqual(outcome["phase"], "armed")
        self.assertEqual(outcome["speak"], "Milepost armed.")
        self.assertIsNone(outcome["row"])

        session, outcome = self._step(session, "Start", when=_pt(2026, 7, 16, 14, 14), lat=45.0, lon=-108.0)
        self.assertEqual(outcome["phase"], "tracking")
        self.assertIn("112.4", outcome["speak"])
        self.assertIn("Start", outcome["speak"])
        self.assertEqual(session["start"]["MP"], "112.4")
        self.assertEqual(session["start"]["Time"], "2:14 PM")

        session, outcome = self._step(session, "stop", when=_pt(2026, 7, 16, 14, 22), lat=45.2, lon=-108.2)
        self.assertEqual(outcome["phase"], "reason")
        self.assertIn("118.2", outcome["speak"])
        self.assertIn("Why not sprayed?", outcome["speak"])

        session, outcome = self._step(session, "trees over the track", kind="pause")
        row = outcome["row"]
        self.assertEqual(outcome["phase"], "listening")
        self.assertEqual(outcome["speak"], "Saved.")
        self.assertEqual(row["MP Start"], "112.4")
        self.assertEqual(row["MP End"], "118.2")
        self.assertEqual(row["MP"], "112.4 to 118.2")
        self.assertEqual(row["Time Start"], "2:14 PM")
        self.assertEqual(row["Time End"], "2:22 PM")
        self.assertEqual(row["Reason"], "trees over the track")
        self.assertIn("activate mile post", row["Transcript"])
        self.assertIn("trees over the track", row["Transcript"])
        self.assertEqual(row["Aircraft"], "N480ML")
        self.assertEqual(row["Status"], "Pending review")
        self.assertEqual(row["MP source"], "GPS")

        session, outcome = self._step(session, "activate milepost")
        self.assertEqual(outcome["phase"], "armed")
        self.assertIsNone(outcome["row"])

    def test_cancel_and_commands_out_of_order_do_not_save(self):
        session, _ = self._step(bnsf_voice.new_voice_session(), "", kind="power-on")
        session, outcome = self._step(session, "start", when=_pt(2026, 7, 16, 9, 0), lat=45.0, lon=-108.0)
        self.assertTrue(outcome["ignored"])
        self.assertIsNone(outcome["row"])
        self.assertEqual(outcome["phase"], "listening")

        session, outcome = self._step(session, "stop")
        self.assertTrue(outcome["ignored"])
        self.assertIsNone(outcome["row"])

        session, outcome = self._step(session, "wind noise over the rotor")
        self.assertTrue(outcome["ignored"])

        session, _ = self._step(session, "activate milepost")
        session, outcome = self._step(session, "stop")
        self.assertTrue(outcome["ignored"])
        self.assertEqual(outcome["speak"], "Say start.")
        self.assertIsNone(outcome["row"])

        session, _ = self._step(session, "start", when=_pt(2026, 7, 16, 9, 1), lat=45.0, lon=-108.0)
        session, outcome = self._step(session, "cancel")
        self.assertEqual(outcome["speak"], "Cancelled.")
        self.assertEqual(outcome["phase"], "listening")
        self.assertIsNone(outcome["row"])
        self.assertIsNone(session.get("start"))

        session, _ = self._step(session, "activate milepost")
        session, _ = self._step(session, "start", when=_pt(2026, 7, 16, 9, 2), lat=45.0, lon=-108.0)
        session, outcome = self._step(session, "activate mile post")
        self.assertEqual(outcome["phase"], "armed")
        self.assertIsNone(session.get("start"))
        self.assertIsNone(outcome["row"])

    def test_stretch_shows_on_spray_notes_and_pdf(self):
        session, _ = self._step(bnsf_voice.new_voice_session(), "", kind="power-on")
        session, _ = self._step(session, "activate milepost")
        session, _ = self._step(session, "start", when=_pt(2026, 7, 16, 14, 14), lat=45.0, lon=-108.0)
        session, _ = self._step(session, "stop", when=_pt(2026, 7, 16, 14, 22), lat=45.2, lon=-108.2)
        _session, outcome = self._step(session, "signal wires", kind="pause")
        row = outcome["row"]
        report, _notice = sample_report()
        report["not_sprayed"] = [row]
        filled = dr.spray_rows_with_not_sprayed(report["spray_rows"], report["not_sprayed"])
        empty_index = next(i for i, item in enumerate(report["spray_rows"]) if not any(item.values()))
        expected = "Start: MP 112.4, Stop: MP 118.2. signal wires"
        self.assertEqual(filled[empty_index]["MP ST"], "112.4")
        self.assertEqual(filled[empty_index]["MP END"], "118.2")
        self.assertEqual(filled[empty_index]["Notes"], expected)
        self.assertEqual(report["spray_rows"][2]["Notes"], "Buffered crossing")

        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(dr.build_daily_report_pdf(report))).pages)
        self.assertIn("NOT SPRAYED", text)
        self.assertIn(expected, text)
        self.assertIn("Pending review", text)
        from docx import Document
        blob = "\n".join(p.text for p in Document(io.BytesIO(dr.fill_daily_report_docx(report))).paragraphs)
        self.assertIn(expected, blob)

    def test_tenth_mile_rounding_interpolation_and_exact_line(self):
        self.assertEqual(dr.format_not_sprayed_mp(9), "9.0")
        self.assertEqual(dr.format_not_sprayed_mp("9"), "9.0")
        self.assertEqual(dr.format_not_sprayed_mp(9.26), "9.3")
        self.assertEqual(dr.format_not_sprayed_mp(9.24), "9.2")
        self.assertEqual(
            dr.not_sprayed_stretch_text(9, 11.2, "trees over the track"),
            "Start: MP 9.0, Stop: MP 11.2. trees over the track",
        )
        self.assertEqual(
            dr.not_sprayed_stretch_text("9.3", "11.2", "signal wires"),
            "Start: MP 9.3, Stop: MP 11.2. signal wires",
        )

        lat_per_mile = 1.0 / 69.172
        points = [
            dr.bw.MilepostPoint("Montana", "Laurel", 9, 47.0, -108.0),
            dr.bw.MilepostPoint("Montana", "Laurel", 10, 47.0 + lat_per_mile, -108.0),
        ]
        on_post = dr.bw.locate_milepost(47.0, -108.0, points=points)
        self.assertEqual(on_post.milepost, 9.0)
        self.assertEqual(dr.format_not_sprayed_mp(on_post.milepost), "9.0")
        third = dr.bw.locate_milepost(47.0 + 0.3 * lat_per_mile, -108.0, points=points)
        self.assertEqual(third.milepost, 9.3)
        almost = dr.bw.locate_milepost(47.0 + 0.26 * lat_per_mile, -108.0, points=points)
        self.assertEqual(almost.milepost, 9.3)
        low = dr.bw.locate_milepost(47.0 + 0.24 * lat_per_mile, -108.0, points=points)
        self.assertEqual(low.milepost, 9.2)

        start = dr.capture_not_sprayed_fix(lat=47.0 + 0.3 * lat_per_mile, lon=-108.0, now=_pt(2026, 7, 16, 9, 0), points=points)
        stop = dr.capture_not_sprayed_fix(lat=47.0 + 0.8 * lat_per_mile, lon=-108.0, now=_pt(2026, 7, 16, 9, 10), points=points)
        self.assertEqual(start["MP"], "9.3")
        self.assertEqual(stop["MP"], "9.8")
        row = bnsf_voice.build_stretch_row(start, stop, "MP 9 trees", "MP 9 trees", aircraft="N480ML")
        self.assertEqual(row["MP Start"], "9.0")
        self.assertEqual(row["MP source"], "Spoken")
        self.assertEqual(row["GPS MP"], "9.3 to 9.8")
        self.assertEqual(row["Reason"], "trees")
        self.assertEqual(dr.not_sprayed_stretch_text(row["MP Start"], row["MP End"], row["Reason"]), "Start: MP 9.0, Stop: MP 9.8. trees")

    def test_browser_support_messages(self):
        self.assertEqual(bnsf_voice.voice_support_message({"recognition": True, "platform": "android-chrome"}), "")
        self.assertIn("Safari", bnsf_voice.voice_support_message({"recognition": True, "platform": "ios-safari", "standalone": True}))
        message = bnsf_voice.voice_support_message({"recognition": False, "platform": "other"})
        self.assertIn("Not sprayed (voice)", message)
        self.assertIn("Mark MP", message)
        help_text = bnsf_voice.VOICE_COMMAND_HELP
        self.assertIn("not reliable", help_text)
        self.assertIn("Android Chrome", help_text)
        self.assertIn("Samsung Internet", help_text)
        self.assertIn("Wake Lock", help_text)
        self.assertIn("home-screen", help_text)
        self.assertIn("Bluetooth", help_text)


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
