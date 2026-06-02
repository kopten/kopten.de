#!/usr/bin/env python3
"""One-shot rebuild: regenerates all detail pages, patches them, and refreshes the sitemap.

Run this after any change to data/kopten_gemeinden.xml.

Usage:
    python3 rebuild.py
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("Generate German detail pages",     "generate_gemeinden.py"),
    ("Generate English detail pages",    "generate_gemeinden_en.py"),
    ("Add language switcher to DE",      "add_lang_switcher.py"),
    ("Add share buttons + OG tags",      "add_share_and_og.py"),
    ("Refresh sitemap.xml",              "generate_sitemap.py"),
    ("Update worker gemeinde allowlist", "generate_worker_gemeinden.py"),
    ("Geocode new gemeinden (cache)",    "geocode_gemeinden.py"),
    ("Refresh asset ?v=<hash>",          "update_asset_versions.py"),
]

# Note: generate_diocese_pdfs.py is intentionally NOT part of rebuild.py
# and not triggered by the GitHub Actions workflow. It must be invoked
# manually when diocese PDFs need to be regenerated.

def run_step(label, script):
    path = ROOT / script
    if not path.exists():
        print(f"  ✗ {label}: script {script} not found")
        return False
    print(f"\n▸ {label}  ({script})")
    print("─" * 60)
    t0 = time.perf_counter()
    try:
        subprocess.run(
            [sys.executable, str(path)],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n  ✗ FAILED (exit {e.returncode})")
        return False
    elapsed = time.perf_counter() - t0
    print(f"  ✓ done in {elapsed:.2f}s")
    return True


def main():
    print("=" * 60)
    print("  Rebuilding all generated pages from XML data")
    print("=" * 60)

    started = time.perf_counter()
    for label, script in STEPS:
        if not run_step(label, script):
            print("\n✗ Rebuild aborted.")
            sys.exit(1)

    total = time.perf_counter() - started
    print("\n" + "=" * 60)
    print(f"  ✓ All steps completed in {total:.2f}s")
    print("=" * 60)
    print("\nNext steps:")
    print("  • Test locally:   python3 -m http.server 8080")
    print("  • Deploy:         upload all changed files to your host")


if __name__ == "__main__":
    main()
