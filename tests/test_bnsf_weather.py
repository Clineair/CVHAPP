"""BNSF weather log: milepost snap, weather parse, due banner, sheet append.

Mocks only. No live Sheets writes, no Drive calls, no live weather APIs.
"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bnsf_weather as bw  # noqa: E402

PT = ZoneInfo("America/Los_Angeles")


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


class Book:
    def __init__(self, tabs=None):
        self.tabs = {title: [list(row) for row in rows] for title, rows in (tabs or {}).items()}
        self.appended = []
        self.added = []

    def worksheet(self, title):
        if title not in self.tabs:
            raise NotFound(title)
        return WS(self, title)

    def add_worksheet(self, title, rows=0, cols=0):
        self.added.append((title, rows, cols))
        self.tabs[title] = []
        return WS(self, title)


# Two-mile straight line along longitude, 1 mile apart, for interpolation tests.
# MP 125 at (47.0, -120.0), MP 126 at (47.0 + 1/69.172, -120.0) is ~1 mile north.
LAT_PER_MILE = 1.0 / 69.172
LINE = [
    bw.MilepostPoint("Seattle", "Yakima Valley", 125, 47.0, -120.0),
    bw.MilepostPoint("Seattle", "Yakima Valley", 126, 47.0 + LAT_PER_MILE, -120.0),
    bw.MilepostPoint("Seattle", "Stampede", 1, 47.2, -121.0),
    bw.MilepostPoint("Seattle", "Stampede", 2, 47.2 + LAT_PER_MILE, -121.0),
    # Same MP number on a far-away subdivision must not win if GPS is on Yakima Valley.
    bw.MilepostPoint("Billings", "Yakima Valley", 125, 46.0, -108.0),
]


def _pt(*parts):
    return datetime(*parts, tzinfo=PT)


class CompassAndUnitsTests(unittest.TestCase):
    def test_16_point_compass(self):
        self.assertEqual(bw.degrees_to_compass16(0), "N")
        self.assertEqual(bw.degrees_to_compass16(192), "SSW")
        self.assertEqual(bw.degrees_to_compass16(112.5), "ESE")
        self.assertEqual(bw.degrees_to_compass16(247.5), "WSW")
        self.assertEqual(bw.degrees_to_compass16(180), "S")
        self.assertEqual(bw.degrees_to_compass16(360), "N")
        self.assertIsNone(bw.degrees_to_compass16(None))

    def test_calm_when_speed_is_zero_even_if_degrees_are_zero(self):
        self.assertEqual(bw.wind_label(0, 0), "Calm")
        self.assertEqual(bw.wind_label(0, 0.0), "Calm")
        self.assertEqual(bw.wind_label(180, 1.5), "S")

    def test_unit_conversion(self):
        self.assertAlmostEqual(bw.c_to_f(-4.4), 24.08, places=2)
        self.assertAlmostEqual(bw.speed_to_mph(16.09344, "wmoUnit:km_h-1"), 10.0, places=2)
        self.assertAlmostEqual(bw.speed_to_mph(10, "wmoUnit:mi_h-1"), 10.0, places=2)


class MilepostTests(unittest.TestCase):
    def test_interpolate_to_a_tenth(self):
        # 20% of the way from MP 125 toward 126.
        lat = 47.0 + 0.2 * LAT_PER_MILE
        fix = bw.locate_milepost(lat, -120.0, points=LINE)
        self.assertEqual(fix.division, "Seattle")
        self.assertEqual(fix.subdivision, "Yakima Valley")
        self.assertEqual(fix.milepost, 125.2)
        self.assertEqual(fix.location, "Yakima Valley MP 125.2")
        self.assertLess(fix.distance_mi, 0.05)

    def test_halfway_is_125_5(self):
        lat = 47.0 + 0.5 * LAT_PER_MILE
        fix = bw.locate_milepost(lat, -120.0, points=LINE)
        self.assertEqual(fix.milepost, 125.5)
        self.assertEqual(fix.location, "Yakima Valley MP 125.5")

    def test_does_not_use_the_same_mp_number_on_another_division(self):
        fix = bw.locate_milepost(47.0, -120.0, points=LINE)
        self.assertEqual(fix.division, "Seattle")
        self.assertEqual(fix.subdivision, "Yakima Valley")
        self.assertEqual(fix.milepost, 125.0)

    def test_isolated_point_stays_at_the_whole_mile(self):
        points = [bw.MilepostPoint("Seattle", "Cherry Point", 8, 48.86, -122.75)]
        fix = bw.locate_milepost(48.86, -122.75, points=points)
        self.assertEqual(fix.location, "Cherry Point MP 8.0")

    def test_does_not_interpolate_across_a_huge_gap(self):
        points = [
            bw.MilepostPoint("Seattle", "Scenic", 49, 47.6, -122.3),
            bw.MilepostPoint("Seattle", "Scenic", 1651, 47.43, -120.31),
        ]
        fix = bw.locate_milepost(47.6, -122.3, points=points)
        self.assertEqual(fix.milepost, 49.0)

    def test_lookup_typed_milepost_interpolates_coordinates(self):
        fix = bw.lookup_milepost("Seattle", "Yakima Valley", 125.2, points=LINE)
        self.assertIsNotNone(fix)
        self.assertEqual(fix.location, "Yakima Valley MP 125.2")
        self.assertAlmostEqual(fix.lat, 47.0 + 0.2 * LAT_PER_MILE, places=5)

    def test_location_text_round_trip(self):
        self.assertEqual(bw.parse_location_text("Yakima Valley MP 125.2"), ("Yakima Valley", 125.2))
        self.assertEqual(bw.parse_location_text("bad"), (None, None))

    def test_bundled_data_covers_requested_states_and_ellensburg(self):
        points = bw.load_mileposts()
        self.assertGreaterEqual(len(points), 8000)
        divisions = {p.division for p in points}
        self.assertEqual(divisions, {"Seattle", "Powder River", "Billings"})
        # Ellensburg sits where Stampede and Yakima Valley meet.
        fix = bw.locate_milepost(47.0025, -120.5301, points=points)
        self.assertEqual(fix.division, "Seattle")
        self.assertIn(fix.subdivision, {"Yakima Valley", "Stampede"})
        self.assertGreaterEqual(fix.milepost, 1.0)


class WeatherFetchTests(unittest.TestCase):
    def test_nws_parse_and_unit_conversion(self):
        session = mock.Mock()

        def get(url, **kwargs):
            response = mock.Mock()
            response.raise_for_status = mock.Mock()
            if "/points/" in url:
                response.json.return_value = {
                    "properties": {
                        "gridId": "PDT",
                        "gridX": 87,
                        "gridY": 172,
                        "observationStations": "https://api.weather.gov/gridpoints/PDT/87,172/stations",
                    }
                }
            elif url.endswith("/stations"):
                response.json.return_value = {
                    "features": [
                        {
                            "geometry": {"coordinates": [-120.53132, 47.03377]},
                            "properties": {
                                "stationIdentifier": "KELN",
                                "name": "Ellensburg, Ellensburg Bowers Field",
                            },
                        }
                    ]
                }
            elif url.endswith("/observations/latest"):
                response.json.return_value = {
                    "properties": {
                        "timestamp": "2026-11-21T15:53:00+00:00",
                        "temperature": {"unitCode": "wmoUnit:degC", "value": -4.4},
                        "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": 192},
                        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 8.05},
                        "windGust": {"unitCode": "wmoUnit:km_h-1", "value": 16.09},
                    }
                }
            else:
                raise AssertionError("unexpected url %s" % url)
            return response

        session.get.side_effect = get
        obs = bw.fetch_nws_observation(47.0025, -120.5301, session=session)
        self.assertEqual(obs.source, "NWS")
        self.assertEqual(obs.station, "KELN")
        self.assertEqual(obs.wind_dir, "SSW")
        self.assertAlmostEqual(obs.temp_f, 24.1, places=1)
        self.assertAlmostEqual(obs.wind_mph, 5.0, places=1)
        self.assertAlmostEqual(obs.gust_mph, 10.0, places=0)
        self.assertIn("KELN", obs.source_label)
        self.assertIn("mi", obs.source_label)

    def test_nws_calm_observation(self):
        session = mock.Mock()

        def get(url, **kwargs):
            response = mock.Mock()
            response.raise_for_status = mock.Mock()
            if "/points/" in url:
                response.json.return_value = {
                    "properties": {"observationStations": "https://api.weather.gov/stations-list"}
                }
            elif url.endswith("stations-list"):
                response.json.return_value = {
                    "features": [{
                        "geometry": {"coordinates": [-120.53, 47.03]},
                        "properties": {"stationIdentifier": "KELN", "name": "Ellensburg"},
                    }]
                }
            else:
                response.json.return_value = {
                    "properties": {
                        "temperature": {"unitCode": "wmoUnit:degC", "value": -4.4},
                        "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": 0},
                        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 0},
                        "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None},
                    }
                }
            return response

        session.get.side_effect = get
        obs = bw.fetch_nws_observation(47.0, -120.5, session=session)
        self.assertEqual(obs.wind_dir, "Calm")
        self.assertEqual(obs.wind_mph, 0.0)
        self.assertIsNone(obs.gust_mph)
        self.assertIsNone(obs.wind_degrees)

    def test_open_meteo_parse(self):
        session = mock.Mock()
        response = mock.Mock()
        response.raise_for_status = mock.Mock()
        response.json.return_value = {
            "current": {
                "time": "2026-11-21T08:30",
                "temperature_2m": 24.7,
                "wind_speed_10m": 1.5,
                "wind_direction_10m": 192,
                "wind_gusts_10m": 1.8,
            }
        }
        session.get.return_value = response
        obs = bw.fetch_open_meteo(47.0, -120.5, session=session)
        self.assertEqual(obs.source, "Open-Meteo")
        self.assertEqual(obs.wind_dir, "SSW")
        self.assertEqual(obs.temp_f, 24.7)
        self.assertEqual(obs.wind_mph, 1.5)
        self.assertIn("Open-Meteo", obs.source_label)

    def test_fetch_weather_falls_back_when_nws_fails(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("NWS down")
        with mock.patch.object(bw, "fetch_nws_observation", side_effect=RuntimeError("NWS down")):
            with mock.patch.object(bw, "fetch_open_meteo", return_value=bw.WeatherObs(
                source="Open-Meteo", source_label="Open-Meteo (model at GPS point)", temp_f=24.7,
            )) as fallback:
                obs = bw.fetch_weather(47.0, -120.5, session=session)
        self.assertEqual(obs.source, "Open-Meteo")
        fallback.assert_called_once()

    def test_fetch_weather_falls_back_when_nws_has_no_usable_obs(self):
        with mock.patch.object(bw, "fetch_nws_observation", return_value=None):
            with mock.patch.object(bw, "fetch_open_meteo", return_value=bw.WeatherObs(
                source="Open-Meteo", source_label="Open-Meteo (model at GPS point)", temp_f=20.0,
            )):
                obs = bw.fetch_weather(47.0, -120.5, session=mock.Mock())
        self.assertEqual(obs.source, "Open-Meteo")
        self.assertEqual(obs.temp_f, 20.0)


class DueBannerTests(unittest.TestCase):
    def test_no_log_yet_today(self):
        status = bw.due_status([], "Ronald A Cline", now=_pt(2026, 11, 21, 9, 0))
        self.assertEqual(status["state"], "none")
        self.assertFalse(status["overdue"])
        self.assertIn("No weather log yet today", status["message"])

    def test_needs_a_pilot(self):
        status = bw.due_status([], "", now=_pt(2026, 11, 21, 9, 0))
        self.assertEqual(status["state"], "need_pilot")

    def test_ok_under_two_hours(self):
        records = [{
            "Pilot": "Ronald A Cline",
            "Date": "2026-11-21",
            "Timestamp": "2026-11-21 08:00:00",
        }]
        status = bw.due_status(records, "Ronald A Cline", now=_pt(2026, 11, 21, 9, 20))
        self.assertEqual(status["state"], "ok")
        self.assertFalse(status["overdue"])
        self.assertEqual(status["age_text"], "1h 20m")
        self.assertIn("1h 20m ago", status["message"])
        self.assertIn("10:00 AM", status["message"])

    def test_overdue_at_two_hours(self):
        records = [{
            "Pilot": "Ronald A Cline",
            "Date": "2026-11-21",
            "Timestamp": "2026-11-21 08:00:00",
        }]
        status = bw.due_status(records, "Ronald A Cline", now=_pt(2026, 11, 21, 10, 0))
        self.assertEqual(status["state"], "overdue")
        self.assertTrue(status["overdue"])
        self.assertIn("Overdue", status["message"])

    def test_ignores_other_pilots_and_other_days(self):
        records = [
            {"Pilot": "Anthony Root", "Date": "2026-11-21", "Timestamp": "2026-11-21 06:00:00"},
            {"Pilot": "Ronald A Cline", "Date": "2026-11-20", "Timestamp": "2026-11-20 09:00:00"},
        ]
        status = bw.due_status(records, "Ronald A Cline", now=_pt(2026, 11, 21, 9, 0))
        self.assertEqual(status["state"], "none")


class RecordAndSheetTests(unittest.TestCase):
    def test_edited_fields_are_flagged(self):
        original = bw.build_preview(
            "Ronald A Cline",
            "N893PC – Robinson R44 Raven II (SN 14940)",
            fix=bw.MilepostFix(
                "Seattle", "Yakima Valley", 125.2, "Yakima Valley MP 125.2",
                47.0, -120.0, 47.0, -120.0, 0.01,
            ),
            weather=bw.WeatherObs(
                source="NWS", source_label="NWS KELN, 1.8 mi", station="KELN",
                wind_dir="SSW", wind_degrees=192, wind_mph=5.0, gust_mph=10.0, temp_f=24.1,
            ),
        )
        current = dict(original)
        current["Wind (mph)"] = "7"
        current["Notes"] = "on-site feel is a little stronger"
        current["Mile marker"] = "125.4"
        current["Location"] = "Yakima Valley MP 125.4"
        changed = bw.edited_fields(original, current)
        self.assertIn("Wind (mph)", changed)
        self.assertIn("Notes", changed)
        self.assertIn("Mile marker", changed)
        self.assertIn("Location", changed)
        self.assertNotIn("Temperature (F)", changed)

    def test_build_record_sets_pacific_timestamp_and_date(self):
        values = {
            "Pilot": "Ronald A Cline",
            "Aircraft": "N893PC – Robinson R44 Raven II (SN 14940)",
            "Division": "Seattle",
            "Subdivision": "Yakima Valley",
            "Mile marker": "125.2",
            "Location": "Yakima Valley MP 125.2",
            "Wind direction": "SSW",
            "Wind (mph)": "5",
            "Temperature (F)": "24.1",
        }
        original = dict(values)
        values["Wind (mph)"] = "6"
        when = _pt(2026, 11, 21, 8, 41, 0)
        record = bw.build_record(values, original=original, when=when, entry_id="BW-TEST")
        self.assertEqual(record["Entry ID"], "BW-TEST")
        self.assertEqual(record["Timestamp"], "2026-11-21 08:41:00")
        self.assertEqual(record["Date"], "2026-11-21")
        self.assertEqual(record["Edited fields"], "Wind (mph)")
        self.assertTrue(record["Entry ID"].startswith("BW-") or record["Entry ID"] == "BW-TEST")

    def test_new_entry_id_prefix(self):
        entry = bw.new_entry_id(_pt(2026, 11, 21, 8, 41, 0))
        self.assertTrue(entry.startswith("BW-20261121-084100-"))
        self.assertEqual(len(entry), len("BW-20261121-084100-abcd"))

    def test_ensure_creates_only_the_bnsf_weather_tab(self):
        book = Book({"FRAT Log": [["timestamp", "pilot"]]})
        ws, created = bw.ensure_bnsf_weather_worksheet(book)
        self.assertTrue(created)
        self.assertEqual(book.added, [("BNSF Weather", 500, max(len(bw.BNSF_WEATHER_COLUMNS), 12))])
        self.assertEqual(book.tabs["BNSF Weather"][0], list(bw.BNSF_WEATHER_COLUMNS))
        self.assertEqual(book.tabs["FRAT Log"], [["timestamp", "pilot"]])
        self.assertIs(ws.book, book)

    def test_ensure_leaves_existing_header_alone(self):
        header = list(bw.BNSF_WEATHER_COLUMNS)
        book = Book({"BNSF Weather": [header, ["BW-1"]]})
        ws, created = bw.ensure_bnsf_weather_worksheet(book)
        self.assertFalse(created)
        self.assertEqual(book.added, [])
        self.assertEqual(book.appended, [])
        self.assertEqual(book.tabs["BNSF Weather"][0], header)

    def test_save_appends_to_bnsf_weather_only(self):
        header = list(bw.BNSF_WEATHER_COLUMNS)
        book = Book({"BNSF Weather": [header], "FRAT Log": [["timestamp"]]})
        record = bw.build_record(
            {
                "Pilot": "Ronald A Cline",
                "Subdivision": "Yakima Valley",
                "Mile marker": "125.2",
                "Wind direction": "Calm",
                "Temperature (F)": "24",
            },
            when=_pt(2026, 11, 21, 8, 41),
            entry_id="BW-TEST",
        )
        result = bw.save_bnsf_weather_record(record, book)
        self.assertEqual(result, "Google Sheets (BNSF Weather)")
        self.assertEqual(len(book.appended), 1)
        title, row, option = book.appended[0]
        self.assertEqual(title, "BNSF Weather")
        self.assertEqual(option, "RAW")
        self.assertEqual(row[header.index("Entry ID")], "BW-TEST")
        self.assertEqual(row[header.index("Location")], "Yakima Valley MP 125.2")
        self.assertEqual(book.tabs["FRAT Log"], [["timestamp"]])

    def test_readonly_load_does_not_create_a_tab(self):
        book = Book({"FRAT Log": [["timestamp"]]})
        records = bw.load_bnsf_weather_records_readonly(book)
        self.assertEqual(records, [])
        self.assertEqual(book.added, [])
        self.assertNotIn("BNSF Weather", book.tabs)

    def test_readonly_load_returns_rows(self):
        header = list(bw.BNSF_WEATHER_COLUMNS)
        row = [""] * len(header)
        row[header.index("Entry ID")] = "BW-1"
        row[header.index("Pilot")] = "Ronald A Cline"
        book = Book({"BNSF Weather": [header, row]})
        records = bw.load_bnsf_weather_records_readonly(book)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["Pilot"], "Ronald A Cline")

    def test_browser_location_parser(self):
        self.assertEqual(
            bw.extract_browser_location({"coords": {"latitude": 47.0, "longitude": -120.5}}),
            (47.0, -120.5),
        )
        self.assertEqual(bw.extract_browser_location({"latitude": 47.0, "longitude": -120.5}), (47.0, -120.5))
        self.assertIsNone(bw.extract_browser_location(None))
        self.assertIsNone(bw.extract_browser_location({}))


class AppHookTests(unittest.TestCase):
    def test_part_137_section_is_after_performance_and_before_frat_tabs(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ops = source.index('if part == "Part 137":')
        # The BNSF hook is the Part 137 block that calls render_bnsf_ops.
        hook = source.index("bnsf_weather.render_bnsf_ops")
        frat = source.index('st.tabs(["📋 FRAT", "🗂️ FRAT History"])')
        oge = source.index('st.metric("OGE Hover Ceiling"')
        self.assertLess(oge, hook)
        self.assertLess(hook, frat)
        self.assertIn("import bnsf_weather", source)
        # There is more than one 'if part == "Part 137"' — the hook must sit
        # in the last block immediately before the FRAT tabs.
        self.assertIn("render_bnsf_ops", source[oge:frat])
        self.assertTrue(source[source.rindex('if part == "Part 137":', 0, frat):frat].count("render_bnsf_ops") == 1)


if __name__ == "__main__":
    unittest.main()
