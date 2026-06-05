#!/usr/bin/env python3
"""One-shot Upload-Tool: schiebt lokale data/<slug>/pdf/-Bäume nach R2.

STATUS: Die initiale Migration ist abgeschlossen. Dieses Skript wird im
laufenden Betrieb NICHT benötigt — Redakteure laden direkt über die
R2-Dashboard-UI hoch (Anleitung im privaten Doku-Repo).

Wann es DOCH gebraucht wird:
  • Disaster Recovery — bei Restore aus einem lokalen PDF-Backup
  • Massen-Import (z.B. neue Gemeinde mit vielen Altbestand-PDFs)
  • Eigentests vor Schema-Änderungen

Schema im R2-Bucket:
    <slug>/<rest>      — wobei <rest> die Pfad-Struktur unter data/<slug>/pdf/
                         übernimmt (z.B. "DKB/01 Liturgie/file.pdf").

Setup einmalig:
    pip install boto3
    export R2_ACCOUNT_ID="…"
    export R2_ACCESS_KEY_ID="…"
    export R2_SECRET_ACCESS_KEY="…"
    export R2_BUCKET="kopten-de-files"

Verwendung:
    python3 migrate_pdfs_to_r2.py --dry-run       # Vorschau
    python3 migrate_pdfs_to_r2.py                 # Echter Upload
    python3 migrate_pdfs_to_r2.py --slug kroeffelbach  # nur eine Gemeinde
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import boto3
    from botocore.config import Config
except ImportError:
    print("Bitte zuerst 'pip install boto3' ausführen.", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def make_s3():
    needed = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [v for v in needed if not os.environ.get(v)]
    if missing:
        print(f"Fehlende ENV-Variablen: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)

    endpoint = f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def collect_pdfs(slug_filter: str | None = None):
    """Yields (local_path, r2_key) for every PDF under data/<slug>/pdf/."""
    if not DATA_DIR.is_dir():
        return
    for slug_dir in sorted(DATA_DIR.iterdir()):
        if not slug_dir.is_dir():
            continue
        if slug_filter and slug_dir.name != slug_filter:
            continue
        pdf_root = slug_dir / "pdf"
        if not pdf_root.is_dir():
            continue
        for pdf in sorted(pdf_root.rglob("*.pdf")):
            rel = pdf.relative_to(pdf_root)
            key = f"{slug_dir.name}/{rel.as_posix()}"
            yield pdf, key


def upload_one(s3, bucket, path: Path, key: str) -> tuple[str, str | None]:
    try:
        s3.upload_file(
            str(path),
            bucket,
            key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "CacheControl": "public, max-age=86400",
            },
        )
        return key, None
    except Exception as e:
        return key, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Nur auflisten, nichts hochladen")
    parser.add_argument("--slug", help="Nur diese Gemeinde migrieren")
    parser.add_argument("--workers", type=int, default=6, help="parallele Upload-Threads")
    args = parser.parse_args()

    bucket = os.environ.get("R2_BUCKET", "kopten-de-files")
    items = list(collect_pdfs(args.slug))

    if not items:
        print("Keine PDFs gefunden.")
        return

    total_size = sum(p.stat().st_size for p, _ in items)
    print(f"{len(items)} PDF(s), gesamt {total_size / (1024*1024):.1f} MB")
    print(f"Bucket: {bucket}")

    if args.dry_run:
        print("\n--dry-run aktiv. Beispiel-Zuordnungen:")
        for p, k in items[:5]:
            print(f"  {p}  →  {k}")
        if len(items) > 5:
            print(f"  ... {len(items) - 5} weitere")
        return

    s3 = make_s3()
    print(f"\nLade hoch mit {args.workers} Threads ...")

    done = 0
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(upload_one, s3, bucket, p, k): k for p, k in items}
        for fut in as_completed(futs):
            key, err = fut.result()
            done += 1
            if err:
                errors.append((key, err))
                print(f"  ✗ [{done}/{len(items)}] {key}  ({err})")
            else:
                print(f"  ✓ [{done}/{len(items)}] {key}")

    print(f"\nFertig. {done - len(errors)} ok, {len(errors)} Fehler.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
