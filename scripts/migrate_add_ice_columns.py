#!/usr/bin/env python3
"""Migration helper: add ICE columns and backfill from `metadata`.

Usage:
  python scripts/migrate_add_ice_columns.py --db taskman.db [--backup]

This script is safe to run multiple times.
"""
import argparse
import sqlite3
import json
import shutil
import sys
from pathlib import Path


ALTER_STMTS = {
    "ice_impact": "ALTER TABLE items ADD COLUMN ice_impact INTEGER CHECK(ice_impact IS NULL OR (ice_impact >= 1 AND ice_impact <= 10));",
    "ice_confidence": "ALTER TABLE items ADD COLUMN ice_confidence TEXT CHECK(ice_confidence IS NULL OR ice_confidence IN ('very_low','low','medium','high','very_high'));",
    "ice_ease": "ALTER TABLE items ADD COLUMN ice_ease INTEGER CHECK(ice_ease IS NULL OR (ice_ease >= 1 AND ice_ease <= 10));",
    "ice_score": "ALTER TABLE items ADD COLUMN ice_score REAL CHECK(ice_score IS NULL OR ice_score >= 0);",
    "metadata": "ALTER TABLE items ADD COLUMN metadata TEXT DEFAULT '{}';",
}


def ensure_columns(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    added = []
    for name, stmt in ALTER_STMTS.items():
        if name not in cols:
            try:
                conn.execute(stmt)
                added.append(name)
            except Exception as e:
                print(f"Warning: failed to add column {name}: {e}")
    # Create index for ice_score if possible
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_ice_score ON items(ice_score DESC);")
    except Exception as e:
        print(f"Warning: could not create idx_items_ice_score: {e}")
    conn.commit()
    return added


def backfill_from_metadata(conn):
    cur = conn.execute("SELECT id, metadata FROM items")
    updates = []
    for row in cur.fetchall():
        iid = row[0]
        meta_text = row[1] or '{}'
        try:
            meta = json.loads(meta_text)
        except Exception:
            meta = {}
        changed = False
        vals = {
            'ice_impact': None,
            'ice_confidence': None,
            'ice_ease': None,
            'ice_score': None,
        }
        if isinstance(meta, dict):
            if 'ice_impact' in meta:
                try:
                    vals['ice_impact'] = int(meta.get('ice_impact'))
                except Exception:
                    vals['ice_impact'] = None
            if 'ice_confidence' in meta:
                vals['ice_confidence'] = meta.get('ice_confidence')
            if 'ice_ease' in meta:
                try:
                    vals['ice_ease'] = int(meta.get('ice_ease'))
                except Exception:
                    vals['ice_ease'] = None
            if 'ice_score' in meta:
                try:
                    vals['ice_score'] = float(meta.get('ice_score'))
                except Exception:
                    vals['ice_score'] = None

        # Only update when at least one value present
        if any(v is not None for v in vals.values()):
            updates.append((vals['ice_impact'], vals['ice_confidence'], vals['ice_ease'], vals['ice_score'], iid))

    if not updates:
        return 0

    upd_sql = "UPDATE items SET ice_impact=?, ice_confidence=?, ice_ease=?, ice_score=? WHERE id=?"
    conn.executemany(upd_sql, updates)
    conn.commit()
    return len(updates)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="taskman.db", help="Path to SQLite DB")
    p.add_argument("--backup", action='store_true', help="Create a .bak copy before migrating")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    if args.backup:
        bak = db_path.with_suffix(db_path.suffix + '.bak')
        print(f"Creating backup: {bak}")
        shutil.copy2(db_path, bak)

    conn = sqlite3.connect(str(db_path))

    try:
        added = ensure_columns(conn)
        if added:
            print(f"Added columns: {', '.join(added)}")
        else:
            print("No new columns needed.")

        n = backfill_from_metadata(conn)
        print(f"Backfilled {n} rows from metadata into ICE columns.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
