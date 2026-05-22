"""
Extract full attack ground-truth windows from the DARPA TC TA5.1 final report PDF.

The default DARPA_ATTACK_PERIODS table in the codebase contains only a single
2-minute window for E5 FiveDirections — what we could confidently parse from
informal sources. The official TA5.1 report (TA51_Final_report_E5.pdf in
data/raw/e5/Ground_Truth/) documents the full attack campaign which spans
multiple days and many distinct activities.

This script:
  1. Loads the PDF (pdfplumber if installed, else falls back to pypdf)
  2. Extracts every timestamp pattern found in the attack-related sections
     Heuristic: lines/paragraphs near keywords like "attack", "Day 1",
     "exploit", "C2", "exfiltration", "lateral", "credential"
  3. Pairs them into (start, end) windows where context makes the pairing clear
  4. Writes the extracted set to data/raw/e5/Ground_Truth/extracted_attack_windows.csv
  5. Also produces a Python snippet ready to drop into DARPA_ATTACK_PERIODS

This is INTENTIONALLY conservative: when the PDF text is ambiguous (which it
often is, because DARPA reports are not structured data), the script emits
candidate windows that a human must review before they go into the codebase.

Usage:
    python scripts/extract_e5_labels.py
    python scripts/extract_e5_labels.py --pdf data/raw/e5/Ground_Truth/TA51_Final_report_E5.pdf
    python scripts/extract_e5_labels.py --commit   # also update auto_pipeline.py
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _have_pdfplumber() -> bool:
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False


def _have_pypdf() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def extract_text(pdf_path: Path) -> list[tuple[int, str]]:
    """Return list of (page_number, text) tuples."""
    pages: list[tuple[int, str]] = []
    if _have_pdfplumber():
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages.append((i, page.extract_text() or ""))
        return pages
    if _have_pypdf():
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        for i, page in enumerate(reader.pages, start=1):
            pages.append((i, page.extract_text() or ""))
        return pages
    raise RuntimeError(
        "Neither pdfplumber nor pypdf is installed. Install one:\n"
        "  pip install pdfplumber\n"
        "or\n"
        "  pip install pypdf"
    )


# Common timestamp patterns found in DARPA TA5.1 reports
TIMESTAMP_PATTERNS = [
    # 2019-05-07 11:18:00 / 2019-05-07 11:18:00 UTC
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\b"),
    # 05/07/2019 11:18 / 05/07/2019 11:18:00
    re.compile(r"\b(\d{2}/\d{2}/20\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)\b"),
    # 11:18:00 — bare time, must be context-anchored later
    re.compile(r"\b(\d{2}:\d{2}:\d{2})\b"),
]

ATTACK_KEYWORD_PATTERN = re.compile(
    r"\b(attack|exploit|c2|c&c|exfil(?:tration)?|lateral\s+movement|"
    r"credential\s+(?:access|dump)|persistence|backdoor|beacon|"
    r"privilege\s+escalation|reconn?aissance|kill[- ]chain|injection|"
    r"victim|attacker|adversary|payload|implant|RAT|shellcode)\b",
    re.IGNORECASE,
)

HOST_PATTERN = re.compile(
    r"\b(?:host[- ]?|machine[- ]?|node[- ]?)?(?:1|2|3|one|two|three)\b",
    re.IGNORECASE,
)

DEFAULT_DATE = "2019-05-15"  # E5 campaign default (May 8-17, 2019)


def find_attack_segments(pages: list[tuple[int, str]]) -> list[dict]:
    """Find paragraphs/lines that look attack-relevant, with their timestamps."""
    candidates: list[dict] = []
    for page_no, text in pages:
        # Split into paragraphs by blank line, or sentences as fallback
        paragraphs = re.split(r"\n\s*\n", text)
        for para in paragraphs:
            if not ATTACK_KEYWORD_PATTERN.search(para):
                continue
            timestamps = []
            for pat in TIMESTAMP_PATTERNS:
                for m in pat.finditer(para):
                    timestamps.append(m.group(0))
            if not timestamps:
                continue
            host_hits = HOST_PATTERN.findall(para)
            keyword_hits = ATTACK_KEYWORD_PATTERN.findall(para)
            candidates.append({
                "page": page_no,
                "timestamps": timestamps,
                "host_mentions": host_hits[:5],
                "keywords": list(set(k.lower() for k in keyword_hits))[:8],
                "excerpt": para[:400].replace("\n", " ").strip(),
            })
    return candidates


def normalize_timestamp(raw: str, default_date: str = DEFAULT_DATE) -> str | None:
    """Normalize a raw timestamp match to 'YYYY-MM-DD HH:MM:SS' or None on failure."""
    raw = raw.strip()
    # ISO with date and time
    m = re.match(r"^(20\d{2}-\d{2}-\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)$", raw)
    if m:
        d, t = m.group(1), m.group(2)
        if len(t) == 5:
            t = t + ":00"
        return f"{d} {t}"
    # US-style date with time
    m = re.match(r"^(\d{2})/(\d{2})/(20\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)$", raw)
    if m:
        mm, dd, yy, t = m.groups()
        if len(t) == 5:
            t = t + ":00"
        return f"{yy}-{mm}-{dd} {t}"
    # Bare time -> attach default date
    m = re.match(r"^(\d{2}:\d{2}:\d{2})$", raw)
    if m:
        return f"{default_date} {m.group(1)}"
    return None


def pair_into_windows(candidates: list[dict], default_duration_seconds: int = 600) -> list[dict]:
    """Pair adjacent timestamps into (start, end) windows; if a candidate has
    only one timestamp, assume the documented activity ran for default_duration.
    """
    windows: list[dict] = []
    for c in candidates:
        ts_normalized = []
        for raw in c["timestamps"]:
            n = normalize_timestamp(raw)
            if n:
                ts_normalized.append(n)
        if not ts_normalized:
            continue
        ts_normalized = sorted(set(ts_normalized))
        if len(ts_normalized) >= 2:
            start, end = ts_normalized[0], ts_normalized[-1]
        else:
            start = ts_normalized[0]
            try:
                dt = datetime.fromisoformat(start)
                end = (dt.replace(second=min(59, dt.second + default_duration_seconds)) if False
                       else None)
            except Exception:
                end = None
            if end is None:
                # Add default_duration_seconds via timedelta
                from datetime import timedelta
                dt = datetime.fromisoformat(start)
                end = (dt + timedelta(seconds=default_duration_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        # Skip pairs where start == end (single-second markers - probably not windows)
        if start == end:
            continue
        windows.append({
            "start": start,
            "end": end,
            "page": c["page"],
            "host_mentions": c["host_mentions"],
            "keywords": c["keywords"],
            "excerpt": c["excerpt"],
        })
    return windows


def deduplicate(windows: list[dict]) -> list[dict]:
    """Drop exact-duplicate (start, end) pairs, keeping the richest context."""
    seen: dict[tuple[str, str], dict] = {}
    for w in windows:
        key = (w["start"], w["end"])
        if key not in seen:
            seen[key] = w
        else:
            # Merge keyword sets
            seen[key]["keywords"] = sorted(set(seen[key]["keywords"]) | set(w["keywords"]))
    return list(seen.values())


def emit_python_snippet(windows: list[dict]) -> str:
    """Format as a Python tuple list ready to drop into DARPA_ATTACK_PERIODS."""
    lines = ["# Extracted from TA51_Final_report_E5.pdf - REVIEW BEFORE USING",
             "# Each (start, end) is in 'YYYY-MM-DD HH:MM:SS' format (UTC).",
             "EXTRACTED_E5_FIVEDIRECTIONS = ["]
    for w in sorted(windows, key=lambda x: x["start"]):
        kw = ", ".join(w["keywords"][:5]) if w["keywords"] else "n/a"
        lines.append(f'    ("{w["start"]}", "{w["end"]}"),  # p.{w["page"]}: {kw}')
    lines.append("]")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pdf", type=Path,
                   default=REPO_ROOT / "data" / "raw" / "e5" / "Ground_Truth" / "TA51_Final_report_E5.pdf")
    p.add_argument("--out-csv", type=Path,
                   default=REPO_ROOT / "data" / "raw" / "e5" / "Ground_Truth" / "extracted_attack_windows.csv")
    p.add_argument("--out-snippet", type=Path,
                   default=REPO_ROOT / "data" / "raw" / "e5" / "Ground_Truth" / "extracted_attack_windows.py")
    args = p.parse_args()

    if not args.pdf.exists():
        print(f"ERROR: PDF not found at {args.pdf}", file=sys.stderr)
        return 1

    if not (_have_pdfplumber() or _have_pypdf()):
        print("Install pdfplumber or pypdf:", file=sys.stderr)
        print("  pip install pdfplumber", file=sys.stderr)
        return 1

    print(f"Loading {args.pdf} ...")
    pages = extract_text(args.pdf)
    print(f"  {len(pages)} pages extracted")
    total_chars = sum(len(t) for _, t in pages)
    print(f"  {total_chars:,} characters of text")

    print("\nScanning for attack-related segments with timestamps ...")
    candidates = find_attack_segments(pages)
    print(f"  {len(candidates)} candidate paragraphs found")

    print("\nPairing timestamps into windows ...")
    windows = pair_into_windows(candidates)
    windows = deduplicate(windows)
    print(f"  {len(windows)} candidate attack windows (after dedup)")

    print("\n=== TOP 20 CANDIDATES (review manually before committing) ===")
    for i, w in enumerate(sorted(windows, key=lambda x: x["start"])[:20], 1):
        print(f"\n[{i:>2}] {w['start']}  ->  {w['end']}  (p.{w['page']})")
        print(f"     keywords: {', '.join(w['keywords'][:5])}")
        print(f"     excerpt:  {w['excerpt'][:140]}...")

    # Write CSV
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start", "end", "page", "keywords", "host_mentions", "excerpt"])
        for w in sorted(windows, key=lambda x: x["start"]):
            writer.writerow([
                w["start"], w["end"], w["page"],
                ";".join(w["keywords"]),
                ";".join(w["host_mentions"]),
                w["excerpt"][:500],
            ])
    print(f"\nCSV written to: {args.out_csv}")

    # Write Python snippet
    snippet = emit_python_snippet(windows)
    args.out_snippet.write_text(snippet, encoding="utf-8")
    print(f"Python snippet: {args.out_snippet}")

    print("\nNEXT STEP:")
    print(f"  1. Review {args.out_csv} manually (these are CANDIDATES, not truth)")
    print(f"  2. Cross-check timestamps against raw events in data/raw/e5/Data/")
    print(f"  3. Replace the entry in src/sentinel_z/ingestion/auto_pipeline.py:")
    print(f"       DARPA_ATTACK_PERIODS['e5']['fivedirections']")
    print(f"     with the validated subset.")
    print(f"  4. Re-run scripts/ingest_e5.py --force to relabel windows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
