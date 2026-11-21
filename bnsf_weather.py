"""BNSF weather logging for Part 137 operations.

Looks up the nearest bundled milepost, interpolates to a tenth of a mile,
fetches the closest NWS station observation (Open-Meteo fallback), and appends
a row to the BNSF Weather tab. No live Sheets writes happen unless a caller
passes a spreadsheet and asks to save.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

PACIFIC = ZoneInfo("America/Los_Angeles")
DATA_PATH = Path(__file__).resolve().parent / "data" / "bnsf_mileposts.json.gz"

BNSF_WEATHER_SHEET_TITLE = "BNSF Weather"
BNSF_WEATHER_COLUMNS = [
    "Entry ID",
    "Timestamp",
    "Date",
    "Pilot",
    "Aircraft",
    "Division",
    "Subdivision",
    "Mile marker",
    "Location",
    "Latitude",
    "Longitude",
    "Distance to track (mi)",
    "Weather source",
    "Station",
    "Station distance (mi)",
    "Wind direction",
    "Wind degrees",
    "Wind (mph)",
    "Gust (mph)",
    "Temperature (F)",
    "Notes",
    "Edited fields",
]

LOG_INTERVAL = timedelta(hours=2)
# Skip interpolation across a gap larger than this (broken/merged MP sequences).
MAX_SEGMENT_MI = 2.5
NWS_USER_AGENT = "CVHAPP (Central Valley Helicopters; https://github.com/Clineair/CVHAPP)"
NWS_TIMEOUT = 8
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
COMPASS_16 = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)
WIND_DIRECTIONS = ("Calm",) + COMPASS_16
LOCATION_RE = re.compile(
    r"^\s*(?P<sub>.+?)\s+MP\s+(?P<mp>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)

EDITABLE_FIELDS = (
    "Pilot",
    "Aircraft",
    "Division",
    "Subdivision",
    "Mile marker",
    "Location",
    "Latitude",
    "Longitude",
    "Weather source",
    "Station",
    "Station distance (mi)",
    "Wind direction",
    "Wind degrees",
    "Wind (mph)",
    "Gust (mph)",
    "Temperature (F)",
    "Notes",
)


def _cell(value):
    return str(value or "").strip()


def _as_pacific(when=None):
    when = when or datetime.now(PACIFIC)
    if when.tzinfo is None:
        return when.replace(tzinfo=PACIFIC)
    return when.astimezone(PACIFIC)


def format_timestamp(when=None):
    return _as_pacific(when).strftime("%Y-%m-%d %H:%M:%S")


def format_date(when=None):
    return _as_pacific(when).strftime("%Y-%m-%d")


def new_entry_id(when=None):
    when = _as_pacific(when)
    return "BW-" + when.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def degrees_to_compass16(degrees):
    """Map a heading in degrees to a 16-point compass label."""
    if degrees is None or degrees == "":
        return None
    try:
        heading = float(degrees) % 360.0
    except (TypeError, ValueError):
        return None
    return COMPASS_16[int((heading / 22.5) + 0.5) % 16]


def c_to_f(celsius):
    if celsius is None:
        return None
    return float(celsius) * 9.0 / 5.0 + 32.0


def speed_to_mph(value, unit_code=""):
    if value is None:
        return None
    speed = float(value)
    unit = (unit_code or "").lower()
    if "km_h" in unit or "km/h" in unit or "kmh" in unit:
        return speed * 0.621371
    if "m_s" in unit or "m/s" in unit or "/s" in unit and "m" in unit:
        return speed * 2.236936
    if "mi_h" in unit or "mile" in unit or "mph" in unit:
        return speed
    # NWS latest observation uses km/h when a unit is present; leave numeric as-is if unknown.
    return speed


def format_mph(value):
    if value is None or value == "":
        return ""
    number = float(value)
    text = ("%.1f" % number).rstrip("0").rstrip(".")
    return text


def format_temp_f(value):
    if value is None or value == "":
        return ""
    return ("%.1f" % float(value)).rstrip("0").rstrip(".")


def format_milepost(value):
    return "%.1f" % float(value)


def format_location(subdivision, milepost):
    return "%s MP %s" % (_cell(subdivision), format_milepost(milepost))


def parse_location_text(text):
    """Parse 'Yakima Valley MP 125.2' into (subdivision, milepost) or (None, None)."""
    match = LOCATION_RE.match(_cell(text))
    if not match:
        return None, None
    return _cell(match.group("sub")), float(match.group("mp"))


def haversine_mi(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles."""
    r = 3958.7613
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlmb = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _to_xy_mi(lat, lon, origin_lat, origin_lon):
    """Equirectangular miles for short segments around origin."""
    x = (float(lon) - float(origin_lon)) * math.cos(math.radians(origin_lat)) * 69.172
    y = (float(lat) - float(origin_lat)) * 69.172
    return x, y


def _project_to_segment(lat, lon, a_lat, a_lon, b_lat, b_lon):
    """Project a point onto segment AB. Returns (t, plat, plon, distance_mi)."""
    ax, ay = 0.0, 0.0
    bx, by = _to_xy_mi(b_lat, b_lon, a_lat, a_lon)
    px, py = _to_xy_mi(lat, lon, a_lat, a_lon)
    ab2 = bx * bx + by * by
    if ab2 <= 1e-12:
        t = 0.0
        plat, plon = a_lat, a_lon
    else:
        t = (px * bx + py * by) / ab2
        t_clamped = max(0.0, min(1.0, t))
        plat = a_lat + t_clamped * (b_lat - a_lat)
        plon = a_lon + t_clamped * (b_lon - a_lon)
        t = t_clamped
    return t, plat, plon, haversine_mi(lat, lon, plat, plon)


@dataclass(frozen=True)
class MilepostPoint:
    division: str
    subdivision: str
    milepost: float
    lat: float
    lon: float


@dataclass
class MilepostFix:
    division: str
    subdivision: str
    milepost: float
    location: str
    lat: float
    lon: float
    gps_lat: float
    gps_lon: float
    distance_mi: float


@dataclass
class WeatherObs:
    source: str
    source_label: str
    station: str = ""
    station_name: str = ""
    station_distance_mi: float | None = None
    wind_dir: str = ""
    wind_degrees: float | None = None
    wind_mph: float | None = None
    gust_mph: float | None = None
    temp_f: float | None = None
    observed_at: str = ""


@lru_cache(maxsize=1)
def load_mileposts(path=None):
    """Load bundled mileposts. Cached after the first read."""
    data_path = Path(path) if path else DATA_PATH
    with gzip.open(data_path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    points = []
    for row in payload.get("points") or []:
        if len(row) < 5:
            continue
        points.append(MilepostPoint(
            division=_cell(row[0]),
            subdivision=_cell(row[1]),
            milepost=float(row[2]),
            lat=float(row[3]),
            lon=float(row[4]),
        ))
    return tuple(points)


def _points_for_line(points, division, subdivision):
    same = [p for p in points if p.division == division and p.subdivision == subdivision]
    # One representative per MP, closest to the already-chosen nearest point
    # is applied later; here group by MP.
    return same


def locate_milepost(lat, lon, points=None):
    """Snap a GPS point to the nearest subdivision and interpolate to 0.1 mile."""
    if lat is None or lon is None:
        return None
    lat = float(lat)
    lon = float(lon)
    catalog = list(points if points is not None else load_mileposts())
    if not catalog:
        return None
    nearest = min(catalog, key=lambda p: haversine_mi(lat, lon, p.lat, p.lon))
    same = _points_for_line(catalog, nearest.division, nearest.subdivision)

    by_mp = {}
    for point in same:
        current = by_mp.get(point.milepost)
        # Prefer the copy of this MP that is closest to the nearest vertex
        # (handles double track / duplicate markers).
        if current is None or haversine_mi(point.lat, point.lon, nearest.lat, nearest.lon) < haversine_mi(
            current.lat, current.lon, nearest.lat, nearest.lon
        ):
            by_mp[point.milepost] = point
    mps = sorted(by_mp)
    try:
        index = mps.index(nearest.milepost)
    except ValueError:
        index = 0
    segments = []
    if index > 0:
        left, right = by_mp[mps[index - 1]], by_mp[mps[index]]
        if haversine_mi(left.lat, left.lon, right.lat, right.lon) <= MAX_SEGMENT_MI:
            segments.append((left, right))
    if index + 1 < len(mps):
        left, right = by_mp[mps[index]], by_mp[mps[index + 1]]
        if haversine_mi(left.lat, left.lon, right.lat, right.lon) <= MAX_SEGMENT_MI:
            segments.append((left, right))

    if not segments:
        distance = haversine_mi(lat, lon, nearest.lat, nearest.lon)
        mp = round(float(nearest.milepost), 1)
        return MilepostFix(
            division=nearest.division,
            subdivision=nearest.subdivision,
            milepost=mp,
            location=format_location(nearest.subdivision, mp),
            lat=nearest.lat,
            lon=nearest.lon,
            gps_lat=lat,
            gps_lon=lon,
            distance_mi=round(distance, 2),
        )

    best = None
    for left, right in segments:
        t, plat, plon, dist = _project_to_segment(lat, lon, left.lat, left.lon, right.lat, right.lon)
        mp = left.milepost + t * (right.milepost - left.milepost)
        candidate = (dist, t, plat, plon, mp, left, right)
        if best is None or dist < best[0]:
            best = candidate
    dist, t, plat, plon, mp, _left, _right = best
    mp = round(float(mp), 1)
    return MilepostFix(
        division=nearest.division,
        subdivision=nearest.subdivision,
        milepost=mp,
        location=format_location(nearest.subdivision, mp),
        lat=round(plat, 6),
        lon=round(plon, 6),
        gps_lat=lat,
        gps_lon=lon,
        distance_mi=round(dist, 2),
    )


def lookup_milepost(division, subdivision, milepost, points=None):
    """Interpolate track coordinates for a typed division/subdivision/MP."""
    if not subdivision or milepost is None or milepost == "":
        return None
    catalog = list(points if points is not None else load_mileposts())
    target = float(milepost)
    if division:
        same = [p for p in catalog if p.division == _cell(division) and p.subdivision == _cell(subdivision)]
    else:
        same = [p for p in catalog if p.subdivision == _cell(subdivision)]
    if not same:
        # Case-insensitive fallback
        sub_l = _cell(subdivision).lower()
        div_l = _cell(division).lower()
        same = [
            p for p in catalog
            if p.subdivision.lower() == sub_l and (not div_l or p.division.lower() == div_l)
        ]
    if not same:
        return None
    # If multiple divisions share a subdivision name and none was given, pick
    # the line whose MP range covers the target, else the closest MP.
    if not division:
        groups = {}
        for point in same:
            groups.setdefault(point.division, []).append(point)
        if len(groups) > 1:
            covering = [
                div for div, pts in groups.items()
                if min(p.milepost for p in pts) - 0.5 <= target <= max(p.milepost for p in pts) + 0.5
            ]
            if len(covering) == 1:
                same = groups[covering[0]]
            else:
                # Closest MP overall
                nearest = min(same, key=lambda p: abs(p.milepost - target))
                same = groups[nearest.division]
    division_name = same[0].division
    by_mp = {}
    for point in same:
        current = by_mp.get(point.milepost)
        if current is None:
            by_mp[point.milepost] = point
    mps = sorted(by_mp)
    if target <= mps[0]:
        point = by_mp[mps[0]]
        t, plat, plon = 0.0, point.lat, point.lon
        used = point.milepost
    elif target >= mps[-1]:
        point = by_mp[mps[-1]]
        t, plat, plon = 1.0, point.lat, point.lon
        used = point.milepost
    else:
        plat = plon = used = None
        for i in range(1, len(mps)):
            left_mp, right_mp = mps[i - 1], mps[i]
            if left_mp <= target <= right_mp:
                left, right = by_mp[left_mp], by_mp[right_mp]
                span = right_mp - left_mp
                t = 0.0 if span == 0 else (target - left_mp) / span
                if haversine_mi(left.lat, left.lon, right.lat, right.lon) > MAX_SEGMENT_MI:
                    # Gap: snap to the closer endpoint instead of crossing it.
                    closer = left if abs(target - left_mp) <= abs(target - right_mp) else right
                    plat, plon, used = closer.lat, closer.lon, closer.milepost
                else:
                    plat = left.lat + t * (right.lat - left.lat)
                    plon = left.lon + t * (right.lon - left.lon)
                    used = target
                break
        if plat is None:
            closer = min(same, key=lambda p: abs(p.milepost - target))
            plat, plon, used = closer.lat, closer.lon, closer.milepost
    mp = round(float(target if used == target else used), 1)
    return MilepostFix(
        division=division_name,
        subdivision=_cell(subdivision) if _cell(subdivision) else same[0].subdivision,
        milepost=round(float(target), 1),
        location=format_location(_cell(subdivision) or same[0].subdivision, target),
        lat=round(float(plat), 6),
        lon=round(float(plon), 6),
        gps_lat=round(float(plat), 6),
        gps_lon=round(float(plon), 6),
        distance_mi=0.0,
    )


def _qty(obj):
    if not isinstance(obj, dict):
        return None, ""
    return obj.get("value"), obj.get("unitCode") or ""


def wind_label(degrees, mph):
    """Return Calm when speed is zero; otherwise a 16-point compass label."""
    if mph is not None:
        try:
            if float(mph) <= 0.05:
                return "Calm"
        except (TypeError, ValueError):
            pass
    label = degrees_to_compass16(degrees)
    return label or ""


def _nws_headers():
    return {
        "User-Agent": NWS_USER_AGENT,
        "Accept": "application/geo+json, application/json",
    }


def _session_get(session, url, **kwargs):
    kwargs.setdefault("timeout", NWS_TIMEOUT)
    kwargs.setdefault("headers", _nws_headers())
    return session.get(url, **kwargs)


def fetch_nws_observation(lat, lon, session=None):
    """Nearest NWS station latest observation, or None if it cannot be used."""
    session = session or requests
    points_url = "https://api.weather.gov/points/%.4f,%.4f" % (float(lat), float(lon))
    points = _session_get(session, points_url)
    points.raise_for_status()
    props = (points.json() or {}).get("properties") or {}
    stations_url = props.get("observationStations")
    if not stations_url:
        stations_url = "https://api.weather.gov/gridpoints/%s/%s,%s/stations" % (
            props.get("gridId"), props.get("gridX"), props.get("gridY")
        )
    if not props.get("gridId") and not props.get("observationStations"):
        return None
    stations = _session_get(session, stations_url)
    stations.raise_for_status()
    features = (stations.json() or {}).get("features") or []
    if not features:
        return None

    # Try the closest few stations until one has usable temp or wind.
    ranked = []
    for feature in features:
        station_props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or [None, None]
        ident = station_props.get("stationIdentifier") or ""
        name = station_props.get("name") or ident
        slon, slat = (coords[0], coords[1]) if len(coords) >= 2 else (None, None)
        distance = None
        if slat is not None and slon is not None:
            distance = haversine_mi(lat, lon, slat, slon)
        elif isinstance(station_props.get("distance"), dict) and station_props["distance"].get("value") is not None:
            distance = float(station_props["distance"]["value"]) / 1609.344
        ranked.append((distance if distance is not None else 9999, ident, name, distance))
    ranked.sort()

    last_error = None
    for _dist, ident, name, distance in ranked[:4]:
        if not ident:
            continue
        try:
            obs_resp = _session_get(
                session,
                "https://api.weather.gov/stations/%s/observations/latest" % ident,
            )
            obs_resp.raise_for_status()
            obs = (obs_resp.json() or {}).get("properties") or {}
        except Exception as exc:
            last_error = exc
            continue
        temp_c, _ = _qty(obs.get("temperature"))
        wind_deg, _ = _qty(obs.get("windDirection"))
        wind_speed, wind_unit = _qty(obs.get("windSpeed"))
        gust, gust_unit = _qty(obs.get("windGust"))
        temp_f = c_to_f(temp_c) if temp_c is not None else None
        wind_mph = speed_to_mph(wind_speed, wind_unit) if wind_speed is not None else None
        gust_mph = speed_to_mph(gust, gust_unit) if gust is not None else None
        if temp_f is None and wind_mph is None:
            continue
        if wind_mph is not None:
            wind_mph = round(wind_mph, 1)
        if gust_mph is not None:
            gust_mph = round(gust_mph, 1)
        if temp_f is not None:
            temp_f = round(temp_f, 1)
        direction = wind_label(wind_deg, wind_mph)
        if wind_mph is not None and float(wind_mph) <= 0.05:
            wind_deg = None
        miles = round(distance, 1) if distance is not None else None
        source_label = "NWS %s" % ident
        if name and name != ident:
            source_label += " (%s)" % name
        if miles is not None:
            source_label += ", %s mi" % format_mph(miles)
        return WeatherObs(
            source="NWS",
            source_label=source_label,
            station=ident,
            station_name=name,
            station_distance_mi=miles,
            wind_dir=direction,
            wind_degrees=None if wind_deg is None else float(wind_deg),
            wind_mph=wind_mph,
            gust_mph=gust_mph,
            temp_f=temp_f,
            observed_at=_cell(obs.get("timestamp")),
        )
    if last_error and not features:
        raise last_error
    return None


def fetch_open_meteo(lat, lon, session=None):
    """Current conditions at the GPS point from Open-Meteo."""
    session = session or requests
    params = {
        "latitude": float(lat),
        "longitude": float(lon),
        "current": "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/Los_Angeles",
    }
    response = session.get(
        OPEN_METEO_URL,
        params=params,
        timeout=NWS_TIMEOUT,
        headers={"User-Agent": NWS_USER_AGENT},
    )
    response.raise_for_status()
    current = (response.json() or {}).get("current") or {}
    temp_f = current.get("temperature_2m")
    wind_mph = current.get("wind_speed_10m")
    wind_deg = current.get("wind_direction_10m")
    gust_mph = current.get("wind_gusts_10m")
    if temp_f is not None:
        temp_f = round(float(temp_f), 1)
    if wind_mph is not None:
        wind_mph = round(float(wind_mph), 1)
    if gust_mph is not None:
        gust_mph = round(float(gust_mph), 1)
    direction = wind_label(wind_deg, wind_mph)
    if wind_mph is not None and float(wind_mph) <= 0.05:
        wind_deg = None
    return WeatherObs(
        source="Open-Meteo",
        source_label="Open-Meteo (model at GPS point)",
        station="",
        station_name="",
        station_distance_mi=None,
        wind_dir=direction,
        wind_degrees=None if wind_deg is None else float(wind_deg),
        wind_mph=wind_mph,
        gust_mph=gust_mph,
        temp_f=temp_f,
        observed_at=_cell(current.get("time")),
    )


def fetch_weather(lat, lon, session=None):
    """NWS nearest-station observation, falling back to Open-Meteo."""
    session = session or requests
    nws_error = None
    try:
        obs = fetch_nws_observation(lat, lon, session=session)
        if obs is not None:
            return obs
    except Exception as exc:
        nws_error = exc
    try:
        return fetch_open_meteo(lat, lon, session=session)
    except Exception:
        if nws_error:
            raise nws_error
        raise


def parse_sheet_timestamp(value, tz=PACIFIC):
    text = _cell(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text[:19] if fmt.startswith("%Y-%m-%d %H:%M:%S") and len(text) >= 19 else text[:10], fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            return parsed
        except ValueError:
            continue
    return None


def record_date(record, tz=PACIFIC):
    text = _cell((record or {}).get("Date"))
    if text:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    stamp = parse_sheet_timestamp((record or {}).get("Timestamp"), tz=tz)
    return stamp.date() if stamp else None


def last_log_for_pilot_today(records, pilot, now=None):
    """Latest BNSF Weather row for this pilot on today's Pacific date."""
    now = _as_pacific(now)
    name = _cell(pilot)
    if not name:
        return None
    latest = None
    for record in records or []:
        if _cell(record.get("Pilot")) != name:
            continue
        if record_date(record, tz=PACIFIC) != now.date():
            continue
        stamp = parse_sheet_timestamp(record.get("Timestamp"), tz=PACIFIC)
        if stamp is None:
            continue
        if latest is None or stamp > latest:
            latest = stamp
    return latest


def format_age(delta):
    if delta is None:
        return ""
    total = int(max(0, delta.total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours and minutes:
        return "%sh %sm" % (hours, minutes)
    if hours:
        return "%sh" % hours
    return "%sm" % minutes


def due_status(records, pilot, now=None):
    """Banner state for the 2-hour weather log interval."""
    now = _as_pacific(now)
    if not _cell(pilot):
        return {
            "state": "need_pilot",
            "overdue": False,
            "message": "Select a pilot to see when the next weather log is due.",
            "last": None,
            "age_text": "",
        }
    last = last_log_for_pilot_today(records, pilot, now=now)
    if last is None:
        return {
            "state": "none",
            "overdue": False,
            "message": "No weather log yet today.",
            "last": None,
            "age_text": "",
        }
    age = now - last
    overdue = age >= LOG_INTERVAL
    age_text = format_age(age)
    if overdue:
        message = "Overdue — last weather log %s ago." % age_text
        state = "overdue"
    else:
        due_at = last + LOG_INTERVAL
        hour = due_at.strftime("%I").lstrip("0") or "12"
        due_text = hour + due_at.strftime(":%M %p")
        message = "Last weather log %s ago. Next due at %s." % (age_text, due_text)
        state = "ok"
    return {
        "state": state,
        "overdue": overdue,
        "message": message,
        "last": last,
        "age_text": age_text,
    }


def _normalize_for_compare(field, value):
    text = _cell(value)
    if field in {"Mile marker", "Latitude", "Longitude", "Wind degrees", "Wind (mph)", "Gust (mph)", "Temperature (F)", "Station distance (mi)", "Distance to track (mi)"}:
        if text == "":
            return ""
        try:
            return "%.4f" % float(text)
        except ValueError:
            return text
    return text


def edited_fields(original, current, fields=EDITABLE_FIELDS):
    """Return the names of fields the pilot changed from the auto-filled values."""
    changed = []
    original = original or {}
    current = current or {}
    for name in fields:
        if _normalize_for_compare(name, original.get(name)) != _normalize_for_compare(name, current.get(name)):
            changed.append(name)
    return changed


def build_preview(pilot, aircraft, fix=None, weather=None, notes=""):
    """Prefill form values from a milepost fix and weather observation."""
    preview = {column: "" for column in BNSF_WEATHER_COLUMNS}
    preview["Pilot"] = _cell(pilot)
    preview["Aircraft"] = _cell(aircraft)
    preview["Notes"] = _cell(notes)
    if fix is not None:
        preview["Division"] = fix.division
        preview["Subdivision"] = fix.subdivision
        preview["Mile marker"] = format_milepost(fix.milepost)
        preview["Location"] = fix.location
        preview["Latitude"] = ("%.6f" % fix.gps_lat) if fix.gps_lat is not None else ""
        preview["Longitude"] = ("%.6f" % fix.gps_lon) if fix.gps_lon is not None else ""
        preview["Distance to track (mi)"] = format_mph(fix.distance_mi)
    if weather is not None:
        preview["Weather source"] = weather.source_label or weather.source
        preview["Station"] = weather.station or weather.station_name
        if weather.station_distance_mi is not None:
            preview["Station distance (mi)"] = format_mph(weather.station_distance_mi)
        preview["Wind direction"] = weather.wind_dir or ""
        if weather.wind_degrees is not None:
            preview["Wind degrees"] = "%g" % weather.wind_degrees
        preview["Wind (mph)"] = format_mph(weather.wind_mph)
        preview["Gust (mph)"] = format_mph(weather.gust_mph)
        preview["Temperature (F)"] = format_temp_f(weather.temp_f)
    return preview


def build_record(values, original=None, when=None, entry_id=None):
    """Build one BNSF Weather row. Timestamp is always Pacific Time at save."""
    when = _as_pacific(when)
    values = values or {}
    record = {column: _cell(values.get(column)) for column in BNSF_WEATHER_COLUMNS}
    record["Entry ID"] = entry_id or new_entry_id(when)
    record["Timestamp"] = format_timestamp(when)
    record["Date"] = format_date(when)
    if record["Location"] == "" and record["Subdivision"] and record["Mile marker"]:
        try:
            record["Location"] = format_location(record["Subdivision"], record["Mile marker"])
        except (TypeError, ValueError):
            pass
    changed = edited_fields(original or {}, record)
    record["Edited fields"] = ", ".join(changed)
    return record


def _worksheet_or_none(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except Exception as exc:
        name = type(exc).__name__
        message = str(exc).lower()
        if name in {"WorksheetNotFound", "NotFound"} or ("worksheet" in message and "not found" in message):
            return None
        raise


def ensure_bnsf_weather_worksheet(spreadsheet):
    """Create the BNSF Weather tab with a header when it is missing.

    Existing BNSF Weather headers are left in place. Never writes the FRAT
    worksheet or any other tab.
    """
    columns = list(BNSF_WEATHER_COLUMNS)
    worksheet = _worksheet_or_none(spreadsheet, BNSF_WEATHER_SHEET_TITLE)
    created = False
    if worksheet is None:
        worksheet = spreadsheet.add_worksheet(
            title=BNSF_WEATHER_SHEET_TITLE,
            rows=500,
            cols=max(len(columns), 12),
        )
        worksheet.append_row(columns, value_input_option="RAW")
        created = True
    else:
        header = [_cell(col) for col in worksheet.row_values(1)]
        if not header:
            worksheet.append_row(columns, value_input_option="RAW")
            created = True
    return worksheet, created


def save_bnsf_weather_record(record, spreadsheet):
    """Append one weather log to the BNSF Weather tab only."""
    worksheet, _created = ensure_bnsf_weather_worksheet(spreadsheet)
    header = [_cell(col) for col in worksheet.row_values(1)]
    if not header:
        raise RuntimeError("BNSF Weather worksheet has no header")
    worksheet.append_row([str(record.get(col, "")) for col in header], value_input_option="RAW")
    return "Google Sheets (BNSF Weather)"


def load_bnsf_weather_records_readonly(spreadsheet):
    """Read the BNSF Weather tab without creating or changing it."""
    if spreadsheet is None:
        return []
    worksheet = _worksheet_or_none(spreadsheet, BNSF_WEATHER_SHEET_TITLE)
    if worksheet is None:
        return []
    values = worksheet.get_all_values() if hasattr(worksheet, "get_all_values") else []
    if not values:
        # Fall back to row_values style books used in tests.
        try:
            header = [_cell(col) for col in worksheet.row_values(1)]
        except Exception:
            return []
        if not header:
            return []
        records = []
        row_number = 2
        while True:
            try:
                row = worksheet.row_values(row_number)
            except Exception:
                break
            if not row:
                # Some mocks return [] past the end; stop after a blank.
                if row_number > 1 and not any(header):
                    break
                # Try a reasonable cap via a values store if present
                break
            record = {col: "" for col in BNSF_WEATHER_COLUMNS}
            for idx, col in enumerate(header):
                if col:
                    record[col] = _cell(row[idx]) if idx < len(row) else ""
            if any(_cell(v) for v in record.values()):
                records.append(record)
            row_number += 1
            if row_number > 5000:
                break
        return records
    header = [_cell(col) for col in values[0]]
    records = []
    for row in values[1:]:
        record = {col: "" for col in BNSF_WEATHER_COLUMNS}
        for idx, col in enumerate(header):
            if col:
                record[col] = _cell(row[idx]) if idx < len(row) else ""
        if any(_cell(v) for v in record.values()):
            records.append(record)
    return records


def extract_browser_location(data):
    """Pull (lat, lon) from streamlit-js-eval / geolocation component output."""
    if not data:
        return None
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        try:
            return float(data[0]), float(data[1])
        except (TypeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    coords = data.get("coords") if isinstance(data.get("coords"), dict) else data
    lat = coords.get("latitude", coords.get("lat"))
    lon = coords.get("longitude", coords.get("lon") or coords.get("lng"))
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def request_browser_location(getter=None):
    """Ask the browser for the current GPS position. Returns (lat, lon) or None."""
    if getter is None:
        try:
            from streamlit_js_eval import get_geolocation
        except ImportError:
            return None
        getter = get_geolocation
    return extract_browser_location(getter())


def divisions_and_subdivisions(points=None):
    catalog = points if points is not None else load_mileposts()
    grouped = {}
    for point in catalog:
        grouped.setdefault(point.division, set()).add(point.subdivision)
    return {division: tuple(sorted(subs)) for division, subs in grouped.items()}


def render_bnsf_ops(default_pilot="", default_aircraft="", pilots=None, aircraft=None, spreadsheet_fn=None, location_getter=None, weather_fn=None, now=None):
    """Part 137 BNSF Ops section: due banner, Log weather, confirm/edit, save.

    spreadsheet_fn is called only for reads and for a save the pilot confirms.
    Tests may pass a getter/fn to avoid the browser and live APIs.
    """
    import streamlit as st

    pilots = list(pilots or [])
    aircraft_options = list(aircraft or [])
    now = _as_pacific(now)

    st.subheader("BNSF Ops")
    st.caption(
        "Log weather at least every 2 hours while spraying. The app finds the "
        "nearest railroad milepost and the closest weather, then lets you check "
        "or edit everything before it is saved."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        pilot_index = None
        if default_pilot and default_pilot in pilots:
            pilot_index = pilots.index(default_pilot)
        elif st.session_state.get("bnsf_ops_pilot") in pilots:
            pilot_index = pilots.index(st.session_state.get("bnsf_ops_pilot"))
        pilot = st.selectbox("Pilot", pilots, index=pilot_index, placeholder="Select pilot", key="bnsf_ops_pilot")
    with col_b:
        aircraft_index = 0
        if default_aircraft and default_aircraft in aircraft_options:
            aircraft_index = aircraft_options.index(default_aircraft)
        elif st.session_state.get("bnsf_ops_aircraft") in aircraft_options:
            aircraft_index = aircraft_options.index(st.session_state.get("bnsf_ops_aircraft"))
        if aircraft_options:
            chosen_aircraft = st.selectbox("Aircraft", aircraft_options, index=min(aircraft_index, len(aircraft_options) - 1), key="bnsf_ops_aircraft")
        else:
            chosen_aircraft = st.text_input("Aircraft", value=_cell(default_aircraft), key="bnsf_ops_aircraft")

    records = []
    load_error = None
    if spreadsheet_fn is not None:
        try:
            records = load_bnsf_weather_records_readonly(spreadsheet_fn())
        except Exception as exc:
            load_error = exc
            records = []
    if load_error:
        st.warning("Could not read saved weather logs: %s" % load_error)

    status = due_status(records, pilot, now=now)
    if status["state"] == "overdue":
        st.error(status["message"])
    elif status["state"] == "none":
        st.warning(status["message"])
    elif status["state"] == "ok":
        st.info(status["message"])
    else:
        st.caption(status["message"])

    if st.button("Log weather", key="bnsf_log_weather", type="primary", use_container_width=True):
        st.session_state.bnsf_weather_logging = True
        st.session_state.pop("bnsf_weather_preview", None)
        st.session_state.pop("bnsf_weather_original", None)
        st.session_state.pop("bnsf_weather_saved", None)
        st.session_state.bnsf_weather_skip_gps = False

    if st.session_state.get("bnsf_weather_saved"):
        st.success(st.session_state.bnsf_weather_saved)

    if st.session_state.get("bnsf_weather_logging") and "bnsf_weather_preview" not in st.session_state:
        skip = st.session_state.get("bnsf_weather_skip_gps")
        coords = None
        if not skip:
            st.caption("Getting your location… Allow location access if the phone asks.")
            if st.button("Enter location by hand", key="bnsf_skip_gps"):
                st.session_state.bnsf_weather_skip_gps = True
                st.rerun()
            try:
                coords = request_browser_location(getter=location_getter)
            except Exception as exc:
                st.warning("Could not read GPS (%s). Enter the milepost by hand." % exc)
                coords = None
            if coords is None and location_getter is None and skip is False:
                # The JS component usually returns nothing on the first run.
                st.stop()
        fix = None
        weather = None
        weather_error = None
        if coords:
            try:
                fix = locate_milepost(coords[0], coords[1])
            except Exception as exc:
                st.warning("Could not match a milepost (%s). Enter it by hand." % exc)
            try:
                fetch = weather_fn or fetch_weather
                weather = fetch(coords[0], coords[1])
            except Exception as exc:
                weather_error = exc
        preview = build_preview(pilot, chosen_aircraft, fix=fix, weather=weather)
        if weather_error:
            preview["Notes"] = ""
            st.session_state.bnsf_weather_weather_error = str(weather_error)
        else:
            st.session_state.pop("bnsf_weather_weather_error", None)
        st.session_state.bnsf_weather_preview = preview
        st.session_state.bnsf_weather_original = dict(preview)
        st.rerun()

    if "bnsf_weather_preview" not in st.session_state:
        return

    if st.session_state.get("bnsf_weather_weather_error"):
        st.warning(
            "Weather could not be fetched automatically (%s). Enter wind and temperature by hand."
            % st.session_state.bnsf_weather_weather_error
        )

    st.markdown("**Check or edit this weather log**")
    st.caption("Every field can be changed before you save. Fields you change are marked as edited by hand.")
    preview = st.session_state.bnsf_weather_preview
    grouped = divisions_and_subdivisions()
    division_names = sorted(grouped)
    current_division = _cell(preview.get("Division"))
    if current_division not in division_names and division_names:
        # keep typed value in the list so the selectbox can show it
        division_names = [current_division] + division_names if current_division else division_names
    division = st.selectbox(
        "Division",
        division_names or [current_division or ""],
        index=(division_names or [""]).index(current_division) if current_division in (division_names or [""]) else 0,
        key="bnsf_form_division",
    )
    subdivs = list(grouped.get(division, ()))
    current_sub = _cell(preview.get("Subdivision"))
    if current_sub and current_sub not in subdivs:
        subdivs = [current_sub] + subdivs
    if not subdivs:
        subdivs = [current_sub or ""]
    subdivision = st.selectbox(
        "Subdivision",
        subdivs,
        index=subdivs.index(current_sub) if current_sub in subdivs else 0,
        key="bnsf_form_subdivision",
    )
    try:
        mp_default = float(preview.get("Mile marker") or 0)
    except ValueError:
        mp_default = 0.0
    mile_marker = st.number_input("Mile marker", min_value=0.0, step=0.1, format="%.1f", value=mp_default, key="bnsf_form_mp")
    location = st.text_input(
        "Location",
        value=preview.get("Location") or format_location(subdivision, mile_marker),
        key="bnsf_form_location",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        latitude = st.text_input("Latitude", value=preview.get("Latitude", ""), key="bnsf_form_lat")
    with c2:
        longitude = st.text_input("Longitude", value=preview.get("Longitude", ""), key="bnsf_form_lon")
    with c3:
        track_distance = st.text_input(
            "Distance to track (mi)",
            value=preview.get("Distance to track (mi)", ""),
            key="bnsf_form_track_dist",
        )

    dirs = list(WIND_DIRECTIONS)
    current_dir = _cell(preview.get("Wind direction")) or "Calm"
    if current_dir not in dirs:
        dirs = [current_dir] + dirs
    wind_dir = st.selectbox(
        "Wind direction",
        dirs,
        index=dirs.index(current_dir) if current_dir in dirs else 0,
        key="bnsf_form_wind_dir",
    )
    w1, w2, w3 = st.columns(3)
    with w1:
        wind_mph = st.text_input("Average wind (mph)", value=preview.get("Wind (mph)", ""), key="bnsf_form_wind_mph")
    with w2:
        gust_mph = st.text_input("Gust (mph)", value=preview.get("Gust (mph)", ""), key="bnsf_form_gust")
    with w3:
        temp_f = st.text_input("Temperature (F)", value=preview.get("Temperature (F)", ""), key="bnsf_form_temp")
    wind_degrees = st.text_input("Wind degrees", value=preview.get("Wind degrees", ""), key="bnsf_form_wind_deg")
    source = st.text_input("Weather source", value=preview.get("Weather source", ""), key="bnsf_form_source")
    s1, s2 = st.columns(2)
    with s1:
        station = st.text_input("Station", value=preview.get("Station", ""), key="bnsf_form_station")
    with s2:
        station_dist = st.text_input(
            "Station distance (mi)",
            value=preview.get("Station distance (mi)", ""),
            key="bnsf_form_station_dist",
        )
    notes = st.text_area("Notes", value=preview.get("Notes", ""), key="bnsf_form_notes")

    current_values = {
        "Pilot": _cell(pilot),
        "Aircraft": _cell(chosen_aircraft),
        "Division": _cell(division),
        "Subdivision": _cell(subdivision),
        "Mile marker": format_milepost(mile_marker) if mile_marker is not None else "",
        "Location": _cell(location) or format_location(subdivision, mile_marker),
        "Latitude": _cell(latitude),
        "Longitude": _cell(longitude),
        "Distance to track (mi)": _cell(track_distance),
        "Weather source": _cell(source),
        "Station": _cell(station),
        "Station distance (mi)": _cell(station_dist),
        "Wind direction": _cell(wind_dir),
        "Wind degrees": _cell(wind_degrees),
        "Wind (mph)": _cell(wind_mph),
        "Gust (mph)": _cell(gust_mph),
        "Temperature (F)": _cell(temp_f),
        "Notes": _cell(notes),
    }
    # Keep preview in sync so a rerun (widget change) does not revert later fields
    # to the original auto-fill after the first interaction. Session original is
    # left untouched so edited-field detection still works.
    st.session_state.bnsf_weather_preview = {**preview, **current_values}

    save_col, cancel_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", key="bnsf_form_cancel"):
            for key in (
                "bnsf_weather_logging",
                "bnsf_weather_preview",
                "bnsf_weather_original",
                "bnsf_weather_skip_gps",
                "bnsf_weather_weather_error",
            ):
                st.session_state.pop(key, None)
            st.rerun()
    with save_col:
        save_clicked = st.button("Save weather log", key="bnsf_form_save", type="primary")
    if not save_clicked:
        return
    if not current_values["Pilot"]:
        st.error("Select a pilot before saving.")
        return
    if spreadsheet_fn is None:
        st.error("Google Sheets is not configured, so the weather log was not saved.")
        return
    record = build_record(current_values, original=st.session_state.get("bnsf_weather_original"), when=now)
    try:
        save_bnsf_weather_record(record, spreadsheet_fn())
    except Exception as exc:
        st.error("Could not save the weather log: %s" % exc)
        return
    st.session_state.bnsf_weather_saved = (
        "Saved %s — %s, %s°F, wind %s %s mph."
        % (
            record["Location"] or "weather log",
            record["Timestamp"],
            record["Temperature (F)"] or "—",
            record["Wind direction"] or "—",
            record["Wind (mph)"] or "—",
        )
    )
    for key in (
        "bnsf_weather_logging",
        "bnsf_weather_preview",
        "bnsf_weather_original",
        "bnsf_weather_skip_gps",
        "bnsf_weather_weather_error",
    ):
        st.session_state.pop(key, None)
    st.rerun()

