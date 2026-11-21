#!/usr/bin/env python3
"""Parse BNSF division milepost KMZ files into data/bnsf_mileposts.json.gz.

Usage:
  python3 tools/build_bnsf_mileposts.py \\
      --seattle path/to/SEATTLE_Div_MP.kmz \\
      --powder-river path/to/POWDER_RIVER_Div_MP.kmz \\
      --billings path/to/BILLINGS_Div_MP.kmz \\
      --out data/bnsf_mileposts.json.gz

Only numeric milepost placemarks are kept. Waypoints (WPT*) and Oregon Trunk
\"z\" alignment points are omitted. This script does not write to Google Drive
or Sheets.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NUMERIC_MP = re.compile(r"^\d+(?:\.\d+)?$")

SOURCES = (
    ("seattle", "Seattle", "SEATTLE Div MP.kmz", "1SF_hYfk93HyXc0Z2B0A-otgYhCIUvlEZ"),
    ("powder_river", "Powder River", "POWDER RIVER Div MP.kmz", "1r96hf8nnb3Ej2bDb_LJ8Z2T_5c91RxLb"),
    ("billings", "Billings", "BILLINGS Div MP.kmz", "19X4I5Fw62WH06VI39KVcYaabqlnZrWAc"),
)


def _local(tag):
    return tag.split("}")[-1]


def _child_name(el):
    for child in el:
        if _local(child.tag) == "name":
            return (child.text or "").strip()
    return ""


def _coordinates(el):
    for child in el.iter():
        if _local(child.tag) == "coordinates" and child.text:
            pair = child.text.strip().replace("\n", " ").split()[0].split(",")
            if len(pair) >= 2:
                return float(pair[0]), float(pair[1])
    return None


def _walk(el, path, results):
    for child in list(el):
        tag = _local(child.tag)
        if tag == "Folder":
            _walk(child, path + [_child_name(child)], results)
        elif tag == "Placemark":
            results.append((path, _child_name(child), _coordinates(child)))
        elif tag == "Document":
            _walk(child, path, results)


def parse_kmz(path):
    with zipfile.ZipFile(path) as archive:
        name = next(item for item in archive.namelist() if item.lower().endswith(".kml"))
        with archive.open(name) as handle:
            tree = ET.parse(handle)
    root = tree.getroot()
    document = next(el for el in root.iter() if _local(el.tag) == "Document")
    results = []
    _walk(document, [], results)
    return results


def display_name(value):
    return str(value or "").strip().title()


def collect_points(kmz_path, division):
    points = []
    skipped = 0
    for folders, name, coords in parse_kmz(kmz_path):
        if not coords or not NUMERIC_MP.fullmatch(name or ""):
            skipped += 1
            continue
        lon, lat = coords
        subdivision = display_name(folders[-1] if folders else "")
        if not subdivision:
            skipped += 1
            continue
        points.append([
            division,
            subdivision,
            json.loads(name) if "." in name else int(name),
            round(lat, 6),
            round(lon, 6),
        ])
    return points, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seattle", required=True)
    parser.add_argument("--powder-river", required=True)
    parser.add_argument("--billings", required=True)
    parser.add_argument("--out", default="data/bnsf_mileposts.json.gz")
    args = parser.parse_args(argv)

    sources = []
    points = []
    for flag, division, filename, file_id in SOURCES:
        path = Path(getattr(args, flag))
        if not path.is_file():
            sys.exit("Missing KMZ: %s" % path)
        found, skipped = collect_points(path, division)
        points.extend(found)
        sources.append({
            "division": division,
            "file": filename,
            "drive_id": file_id,
            "points": len(found),
            "skipped": skipped,
        })
        print("%s: %s numeric mileposts, %s skipped" % (division, len(found), skipped))

    payload = {"version": 1, "sources": sources, "points": points}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    print("Wrote %s points to %s (%s bytes)" % (len(points), out, out.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
