#!/usr/bin/env python3
"""Update ?v=<hash> query strings in all HTML files based on actual asset content.

Whenever you change css/style.css, js/main.js, js/kalender.js, etc., run this
script before commit. It computes a short SHA-256 hash of each asset and
rewrites every `<link>` / `<script>` reference in HTML files to use that hash.

Result: changing an asset always invalidates browser caches automatically.

Usage:
    python3 update_asset_versions.py

This script is also part of rebuild.py (and therefore the GitHub Action).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Assets to track. Add new entries here when introducing new CSS/JS files.
ASSETS = [
    'css/style.css',
    'js/main.js',
    'js/kalender.js',
    'js/kontakt.js',
    'js/gemeinden.js',
]

HASH_LEN = 8


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_LEN]


def main() -> None:
    hashes: dict[str, str] = {}
    for asset in ASSETS:
        full = ROOT / asset
        if not full.is_file():
            print(f"  ! skipping missing asset: {asset}")
            continue
        hashes[asset] = file_hash(full)

    if not hashes:
        print("No assets found, nothing to do.")
        return

    # Build one regex per asset that matches any current ?v=...
    # Captures the asset path so the substitution preserves it verbatim.
    patterns = {
        asset: re.compile(rf'({re.escape(asset)})\?v=[A-Za-z0-9._-]+')
        for asset in hashes
    }

    updated_files = 0
    total_substitutions = 0

    for html in ROOT.rglob('*.html'):
        # Skip generated build artefacts inside virtual envs etc.
        if any(part.startswith('.') for part in html.parts):
            continue
        text = html.read_text(encoding='utf-8')
        new = text
        local_subs = 0
        for asset, hash_ in hashes.items():
            new, n = patterns[asset].subn(rf'\1?v={hash_}', new)
            local_subs += n
        if new != text:
            html.write_text(new, encoding='utf-8')
            updated_files += 1
            total_substitutions += local_subs

    print(f"Updated {updated_files} HTML file(s), {total_substitutions} reference(s) refreshed.")
    for asset, hash_ in hashes.items():
        print(f"  {asset}?v={hash_}")


if __name__ == '__main__':
    main()
