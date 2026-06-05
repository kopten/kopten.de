#!/usr/bin/env python3
"""Build-time geocoding for gemeinden.

Resolves every gemeinde address from data/kopten_gemeinden.xml to lat/lng
using OpenStreetMap Nominatim (free, rate-limited to 1 req/sec).

Output: data/gemeinden-coords.json, a {id: {lat, lng}} map.

Runs incrementally — entries already in the JSON are skipped. To force
re-resolution of one gemeinde, delete its entry from the JSON and rerun.

Usage:
    python3 geocode_gemeinden.py
    python3 geocode_gemeinden.py --force      # re-geocode everything
    python3 geocode_gemeinden.py --id koeln   # only one entry

The browser (js/gemeinden.js) loads this JSON and uses the cached
coordinates — no Google Geocoding API calls per page view.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
XML_FILE = ROOT / "data" / "kopten_gemeinden.xml"
JSON_FILE = ROOT / "data" / "gemeinden-coords.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "kopten.de geocode build (contact: info@kopten.de)"
REQUEST_INTERVAL_SEC = 1.1  # Nominatim policy: max 1 req/sec, leave buffer


def load_xml_entries() -> list[dict]:
    tree = ET.parse(XML_FILE)
    out = []
    for g in tree.getroot().findall("gemeinde"):
        gid = g.get("id")
        addr = g.find("adresse")
        if addr is None:
            continue
        strasse = (addr.findtext("strasse") or "").strip()
        plz = (addr.findtext("plz") or "").strip()
        ort = (addr.findtext("ort") or "").strip()
        out.append({"id": gid, "strasse": strasse, "plz": plz, "ort": ort})
    return out


def load_cache() -> dict:
    if JSON_FILE.is_file():
        return json.loads(JSON_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def nominatim_lookup(query: str) -> dict | None:
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "de,lu,at,ch",   # include neighbouring countries
        "addressdetails": 0,
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ! request failed: {e}", file=sys.stderr)
        return None
    if not data:
        return None
    return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}


def clean(s: str) -> str:
    """Strip parenthetical hints, OT prefixes, en-dash variants."""
    import re
    s = re.sub(r"\s*\([^)]*\)", "", s)        # remove "(bei Dortmund)" etc.
    s = re.sub(r"\bOT\s+", "", s)              # remove "OT" Ortsteil marker
    s = re.sub(r"\s*[–—-]\s*", ", ", s)        # "Seeland – OT X" → "Seeland, X"
    return re.sub(r"\s+", " ", s).strip()


def geocode_entry(entry: dict) -> dict | None:
    """Try most specific query first, then progressively widen."""
    strasse = clean(entry["strasse"])
    plz = entry["plz"]
    ort = clean(entry["ort"])

    queries = []
    if strasse and plz and ort:
        queries.append(f"{strasse}, {plz} {ort}")
    if plz and ort:
        queries.append(f"{plz} {ort}")
    if ort:
        queries.append(ort)

    for q in queries:
        result = nominatim_lookup(q)
        if result:
            result["query"] = q
            return result
        time.sleep(REQUEST_INTERVAL_SEC)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-geocode entries that are already in the cache")
    parser.add_argument("--id", help="Only geocode this gemeinde id")
    args = parser.parse_args()

    if not XML_FILE.is_file():
        print(f"XML not found: {XML_FILE}", file=sys.stderr)
        return 1

    entries = load_xml_entries()
    if args.id:
        entries = [e for e in entries if e["id"] == args.id]
        if not entries:
            print(f"No entry with id={args.id}", file=sys.stderr)
            return 1

    cache = load_cache()
    new_count = 0
    skipped = 0
    failed = []
    last_request = 0.0

    for entry in entries:
        gid = entry["id"]
        if not args.force and gid in cache:
            skipped += 1
            continue

        # Rate limit between calls
        elapsed = time.time() - last_request
        if elapsed < REQUEST_INTERVAL_SEC:
            time.sleep(REQUEST_INTERVAL_SEC - elapsed)

        print(f"▸ {gid}: geocoding …", end=" ", flush=True)
        result = geocode_entry(entry)
        last_request = time.time()

        if result is None:
            print("FAILED")
            failed.append(gid)
            continue

        cache[gid] = {"lat": result["lat"], "lng": result["lng"]}
        new_count += 1
        print(f"({result['lat']:.4f}, {result['lng']:.4f})")

        # Save after every successful entry — safe against interruption
        save_cache(cache)

    print(f"\nDone. {new_count} new, {skipped} skipped from cache.")
    if failed:
        print(f"Failed ({len(failed)}): {', '.join(failed)}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
