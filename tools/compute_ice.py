#!/usr/bin/env python3
"""
tools/compute_ice.py

Ein kleines Hilfs-Skript, das `prioritization_template.csv` einliest,
Status-Mapping anwendet, `ice_score` prüft/berechnet und eine priorisierte
CSV-Ausgabe schreibt.

Usage:
    python tools/compute_ice.py \
        --in prioritization_template.csv \
        --out prioritization_output.csv

Das Skript:
- Liest CSV mit Spalten: id,type,status,title,description,impact,confidence,ease,ice_score,notes
- Mappt `status` (active/waiting/someday) auf interne Keys via `StatusManager.map_csv_status`
- Berechnet `ice_score` wenn leer oder wenn --force recalc gesetzt
- Filtert standardmäßig `status` == 'waiting' (bzw. intern gemappt auf BLOCKED/SNOOZED)
- Schreibt zwei Dateien: `prioritization_output.csv` (gefiltert, priorisiert) und
  `prioritization_all_processed.csv` (alle Zeilen mit berechnetem `mapped_status`)
"""
import csv
import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path when script is executed from a tmp dir (tests run it that way)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.status_service import StatusService
from domain.status_catalog import STATUS_DEFINITIONS

STATUS_WAITING_INTERNAL = {"TASK_BLOCKED", "REMINDER_SNOOZED"}


def parse_row(row):
    # normalize keys
    return {
        "id": row.get("id", "").strip(),
        "type": (row.get("type", "") or "").strip().lower(),
        "status": (row.get("status", "") or "").strip(),
        "title": row.get("title", ""),
        "description": row.get("description", ""),
        "impact": row.get("impact", ""),
        "confidence": row.get("confidence", ""),
        "ease": row.get("ease", ""),
        "ice_score": row.get("ice_score", ""),
        "notes": row.get("notes", ""),
    }


def safe_float(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def compute_ice(impact, confidence, ease):
    if impact is None or confidence is None or ease is None:
        return None
    return impact * confidence * ease


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="infile", required=True)
    p.add_argument("--out", dest="outfile", default="prioritization_output.csv")
    p.add_argument("--all-out", dest="all_out", default="prioritization_all_processed.csv")
    p.add_argument("--force-recalc", dest="force", action="store_true")
    args = p.parse_args()

    infile = Path(args.infile)
    out = Path(args.outfile)
    all_out = Path(args.all_out)

    if not infile.exists():
        print(f"Input file not found: {infile}")
        return

    # use domain-level StatusService to keep callers on the same API
    status_svc = StatusService(STATUS_DEFINITIONS)

    rows = []
    with infile.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(parse_row(r))

    processed = []
    for r in rows:
        if r["type"] not in ("task", "reminder"):
            # keep but mark unmapped
            mapped = None
        else:
            mapped = status_svc.map_csv_status(r.get("status", ""), item_type=r.get("type"))
        impact = safe_float(r.get("impact"))
        confidence = safe_float(r.get("confidence"))
        ease = safe_float(r.get("ease"))
        ice = safe_float(r.get("ice_score"))
        # compute if missing or forced
        if args.force or ice is None:
            ice = compute_ice(impact, confidence, ease)
        # if someday, ensure notes reflect that this was a someday/backlog item
        notes = (r.get("notes") or "")
        if mapped in ("TASK_SOMEDAY", "REMINDER_SOMEDAY"):
            if "someday" not in notes.lower():
                notes = (notes + "; Someday import") if notes else "Someday import"

        processed.append({**r, "mapped_status": mapped or "", "ice_score": ice, "notes": notes})

    # write all processed
    fieldnames = ["id", "type", "status", "mapped_status", "title", "description", "impact", "confidence", "ease", "ice_score", "notes"]
    with all_out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in processed:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    # filter: exclude waiting items
    filtered = []
    for r in processed:
        sraw = (r.get("status") or "").strip().lower()
        mapped = (r.get("mapped_status") or "")
        if sraw == "waiting" or mapped in STATUS_WAITING_INTERNAL:
            # skip
            continue
        if r.get("type") not in ("task", "reminder"):
            continue
        filtered.append(r)

    # sort by ice_score desc (None -> at end)
    def sort_key(x):
        v = x.get("ice_score")
        try:
            return -(float(v) if v is not None else -99999)
        except Exception:
            return 0

    filtered.sort(key=sort_key)

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in filtered:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"Wrote {len(filtered)} prioritized items to {out}")
    print(f"Wrote {len(processed)} total processed rows to {all_out}")


if __name__ == "__main__":
    main()
