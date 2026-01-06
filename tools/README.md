tools/compute_ice.py — Usage

A small helper to compute ICE scores from `prioritization_template.csv` and produce a prioritized CSV.

Quick start

1. Ensure you are in the repository root.
2. Run:

```powershell
python tools/compute_ice.py --in prioritization_template.csv --out prioritization_output.csv --all-out prioritization_all_processed.csv --force-recalc
```

What it does
- Reads CSV with columns: `id,type,status,title,description,impact,confidence,ease,ice_score,notes`.
- Maps `status` values (`active`, `waiting`, `someday`) to internal keys using the domain `StatusService` mapping.
- Calculates `ice_score` if missing or when `--force-recalc` is set.
- Writes two outputs:
  - `--out`: filtered and prioritized list (excludes `waiting` items).
  - `--all-out`: all processed rows with `mapped_status` and calculated `ice_score`.

Notes
- `someday` items are mapped to `TASK_SOMEDAY` / `REMINDER_SOMEDAY` and the script will append a short note `Someday import` if `notes` is empty.
- The script uses the domain facade `StatusService` and the project's `STATUS_DEFINITIONS` so behavior matches the app.
