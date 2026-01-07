# Database migration: add ICE columns

This project introduced structured ICE columns (Impact, Confidence, Ease, Score) to make prioritization queryable and type-safe instead of storing these values only in a free-form `metadata` JSON field.

This document explains what the migration does, why it is needed, and how to run and verify it.

## Why

- Older databases may not have `ice_impact`, `ice_confidence`, `ice_ease`, `ice_score`, or even the `metadata` column. The application expects these columns; missing columns cause runtime errors (e.g. `sqlite3.OperationalError: no such column: ice_score`).
- We also moved from a 1–10 scale to a 1–5 scale for `impact` and `ease` to simplify input.

## What the migration does

1. Adds the following columns (if missing):
   - `ice_impact` INTEGER CHECK(1..5)
   - `ice_confidence` TEXT CHECK IN ('very_low','low','medium','high','very_high')
   - `ice_ease` INTEGER CHECK(1..5)
   - `ice_score` REAL (>= 0)
   - `metadata` TEXT DEFAULT '{}'
2. Creates the index `idx_items_ice_score` (if missing).
3. Backfills values from existing `metadata` JSON into the typed ICE columns when possible (parsing integers/float and confidence key strings).

The migration is idempotent and safe to run multiple times.

## How to run

From the repository root run (recommended with a backup):

```bash
python scripts/migrate_add_ice_columns.py --db taskman.db --backup
```

- `--db` defaults to `taskman.db` if omitted.
- `--backup` creates a `.bak` copy of the DB before applying changes; recommended for production.

## Verification

- Check that the columns exist:

```sql
PRAGMA table_info(items);
```

- Run a quick SQL check to ensure values were backfilled (example):

```sql
SELECT count(*) FROM items WHERE ice_impact IS NOT NULL OR ice_confidence IS NOT NULL OR ice_ease IS NOT NULL OR ice_score IS NOT NULL;
```

- Start the server and browse an item edit page that previously failed; errors about missing `ice_score` should be gone.

- Run the test-suite locally: `python -m pytest -q` (the project includes tests covering the migration and ICE persistence).

## Rollback

- If `--backup` was used a copy `taskman.db.bak` will be created; stop the server and restore that file if needed.

## Notes

- The application expects `impact` and `ease` values in range `1..5`; values outside that range will be ignored during validation.
- Confidence remains a keyed enum: `very_low`, `low`, `medium`, `high`, `very_high` and maps internally to numeric weights.

## Files touched

- `scripts/migrate_add_ice_columns.py` — migration script (idempotent)
- `infrastructure/db_repository.py` — DDL and runtime migration checks
- `web/templates/edit.html` & `web/server.py` — UI and server-side validation for the new scale

If you want, I can add an automated CI step to run the migration against a disposable DB and assert that the expected columns exist.
