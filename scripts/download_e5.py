"""
Download DARPA TC Engagement 5 — FiveDirections subset only — into
``data/raw/e5/``.

The full Engagement5 Drive folder (1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf) holds all
four TA1 performers (cadets, fivedirections, theia, trace) — gigabytes total.
This script enumerates the folder via ``gdown.download_folder(skip_download=True)``,
filters to:

    Data/fivedirections/     — the 338 .bin.gz chunks the project actually uses
    Ground_Truth/            — TA5.1 attack ground-truth report (PDF + DOCX)
    Engagement-5-Event-Log.md, README.md, README.pdf

…and then downloads each survivor with per-file ``gdown.download``.

Idempotent: re-runs skip files already on disk (and the right size). A
``.manifest.txt`` of sha256 hashes is written at the end for integrity.

Usage::

    python scripts/download_e5.py
    python scripts/download_e5.py --dry-run

Manual fallback (if gdown access fails):

    https://drive.google.com/drive/folders/1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf
    -> sign in -> open Data/fivedirections/ -> right-click -> Download
    -> unzip into data/raw/e5/Data/fivedirections/
    Then drop ``Ground_Truth/`` next to it and re-run scripts/ingest_e5.py.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

DRIVE_FOLDER_ID = "1okt4AYElyBohW4XiOBqmsvjwXsnUjLVf"  # Engagement5 root
DRIVE_FOLDER_URL = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "data" / "raw" / "e5"
ENUM_CACHE_DIR = REPO_ROOT / "data" / "raw" / ".gdown_enum_cache"

MANUAL_FALLBACK_NOTE = f"""
gdown could not fetch the Drive folder.

Manual fallback:
  1. Open {DRIVE_FOLDER_URL} in your browser (sign in with the Google account
     that has been granted access).
  2. Open Data/fivedirections/ — right-click -> Download. Drive will zip it.
  3. Unzip into {TARGET_DIR / 'Data' / 'fivedirections'}/
  4. Also right-click Ground_Truth/ -> Download, unzip into
     {TARGET_DIR / 'Ground_Truth'}/
  5. Re-run scripts/ingest_e5.py.
""".rstrip()


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(target: Path) -> int:
    manifest_path = target / ".manifest.txt"
    rows: list[str] = []
    count = 0
    total_bytes = 0
    for p in sorted(target.rglob("*")):
        if not p.is_file() or p.name == ".manifest.txt":
            continue
        rel = p.relative_to(target).as_posix()
        size = p.stat().st_size
        rows.append(f"{sha256(p)}  {size:>14d}  {rel}")
        count += 1
        total_bytes += size
    manifest_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"  wrote manifest: {count} files, {total_bytes / 1e6:.1f} MB total")
    return count


_HOST_RE = __import__("re").compile(r"^(ta1-fivedirections-\d+-e5-official-\d+)\.bin\.(\d+)\.gz$")


def filter_fivedirections(items, max_chunks_per_host: int | None = None):
    """Keep only files in Data/fivedirections/, Ground_Truth/, or top-level.

    If ``max_chunks_per_host`` is set, keep only the first N chunks per host
    series (numerically ordered by chunk number). The .md5sum, Ground_Truth/,
    and top-level files are always included.
    """
    fd_chunks: dict[str, list[tuple[int, object]]] = {}
    fd_other: list = []
    gt: list = []
    top: list = []

    for it in items:
        norm = it.path.replace("\\", "/")
        name = norm.rsplit("/", 1)[-1]
        if norm.startswith("Data/fivedirections/"):
            m = _HOST_RE.match(name)
            if m:
                host = m.group(1)
                chunk_n = int(m.group(2))
                fd_chunks.setdefault(host, []).append((chunk_n, it))
            else:
                # bins.md5sum or anything non-chunk
                fd_other.append(it)
        elif norm.startswith("Ground_Truth/"):
            gt.append(it)
        elif "/" not in norm:
            top.append(it)

    keep = list(fd_other) + list(gt) + list(top)
    for host, chunks in sorted(fd_chunks.items()):
        chunks.sort(key=lambda t: t[0])
        if max_chunks_per_host is not None:
            chunks = chunks[:max_chunks_per_host]
        keep.extend(it for _, it in chunks)
    return keep


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="enumerate Drive + print what would be downloaded; no fetch")
    parser.add_argument("--max-chunks-per-host", type=int, default=None,
                        help="cap chunks per fivedirections host series (smoke runs); "
                             "default = unlimited (~17 GB total)")
    args = parser.parse_args()

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    ENUM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"target directory: {TARGET_DIR}", flush=True)

    try:
        import gdown
    except ImportError:
        print("ERROR: gdown not installed. Run: pip install -e \".[dev]\"", file=sys.stderr)
        return 1

    print(f"enumerating {DRIVE_FOLDER_URL} ...", flush=True)
    try:
        all_items = gdown.download_folder(
            url=DRIVE_FOLDER_URL,
            output=str(ENUM_CACHE_DIR),
            quiet=True,
            use_cookies=True,
            skip_download=True,
        )
    except Exception as exc:
        print(f"\nERROR: gdown enumeration failed: {exc}", file=sys.stderr)
        print(MANUAL_FALLBACK_NOTE, file=sys.stderr)
        return 1

    keep = filter_fivedirections(all_items, max_chunks_per_host=args.max_chunks_per_host)
    print(f"  total items in Drive folder : {len(all_items)}", flush=True)
    print(f"  keeping (fivedirections+gt+top): {len(keep)}", flush=True)
    if args.max_chunks_per_host is not None:
        print(f"  (--max-chunks-per-host {args.max_chunks_per_host} applied)", flush=True)

    if args.dry_run:
        print()
        for it in keep[:10]:
            print(" ", it.path)
        if len(keep) > 10:
            print(f"  ... ({len(keep) - 10} more)")
        return 0

    skipped = 0
    fetched = 0
    failures: list[tuple[str, str]] = []

    for i, it in enumerate(keep, 1):
        rel_path = Path(it.path.replace("\\", "/"))
        local_path = TARGET_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already present and non-empty
        if local_path.is_file() and local_path.stat().st_size > 0:
            skipped += 1
            continue

        url = f"https://drive.google.com/uc?id={it.id}"
        print(f"[{i:>4}/{len(keep)}] downloading {rel_path.as_posix()}", flush=True)
        try:
            gdown.download(
                url=url,
                output=str(local_path),
                quiet=True,
                use_cookies=True,
                resume=True,
            )
        except Exception as exc:
            failures.append((it.path, str(exc)))
            print(f"  FAILED: {exc}", file=sys.stderr)
            continue

        if local_path.is_file() and local_path.stat().st_size > 0:
            fetched += 1
        else:
            failures.append((it.path, "downloaded file is empty/missing"))

    print()
    print(f"summary: fetched={fetched}  skipped={skipped}  failed={len(failures)}")

    if failures:
        print(f"\n{len(failures)} files failed:", file=sys.stderr)
        for path, err in failures[:5]:
            print(f"  {path}: {err}", file=sys.stderr)
        if len(failures) > 5:
            print(f"  ... ({len(failures) - 5} more)", file=sys.stderr)
        print(MANUAL_FALLBACK_NOTE, file=sys.stderr)
        return 1

    write_manifest(TARGET_DIR)
    print(f"\n[OK] {TARGET_DIR}")
    print("next step: python scripts/ingest_e5.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
