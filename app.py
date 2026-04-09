# app.py
import os
import uuid
import argparse
from datetime import timedelta
from bootstrap import make_status_service
from infrastructure.db_repository import DbRepository
from infrastructure.ical_mapper import to_ics
from infrastructure.ical_importer import import_ics
from infrastructure.console_notifier import ConsoleNotifier
from domain.models import Task, Appointment, Event, Reminder, Recurrence
from services.recurrence_service import expand_item
from services.notification_service import NotificationService
from services.scheduler_service import SchedulerService
from services.filter_service import filter_items
from utils.datetime_helpers import now_utc, format_display_datetime

def _gen_id() -> str:
    return str(uuid.uuid4())

def seed_data(repo, *, creator: str, due_delta_min: int = 8, reminder_delta_min: int = 5):
    """Seed sample data using the provided creator as owner/participant."""
    if not creator:
        raise ValueError("creator is required for seeding items")

    t1 = Task(
        id=_gen_id(),
        type="task",
        name="Bericht finalisieren",
        status="TASK_OPEN",
        is_private=False,
        due_utc=now_utc() + timedelta(minutes=due_delta_min),
        recurrence=None,
        creator=creator,
        participants=(creator,),
    )
    repo.upsert(t1)

    dtstart = (now_utc() - timedelta(days=1)).replace(second=0, microsecond=0)
    rrule_str = "\n".join([
        f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}",
        "RRULE:FREQ=WEEKLY;COUNT=5;BYDAY=WE",
    ])
    ap1 = Appointment(
        id=_gen_id(),
        type="appointment",
        name="Team Sync",
        status="APPOINTMENT_PLANNED",
        is_private=False,
        start_utc=dtstart,
        end_utc=dtstart + timedelta(hours=1),
        is_all_day=False,
        recurrence=Recurrence(rrule_string=rrule_str, exdates_utc=()),
        creator=creator,
        participants=(creator,),
    )
    repo.upsert(ap1)

    rem = Reminder(
        id=_gen_id(),
        type="reminder",
        name="Wasser trinken",
        status="REMINDER_ACTIVE",
        is_private=False,
        reminder_utc=now_utc() + timedelta(minutes=reminder_delta_min),
        recurrence=None,
        creator=creator,
        participants=(creator,),
    )
    repo.upsert(rem)

def _import_key(it) -> tuple:
    name = it.name
    if it.type == "reminder":
        # Align mit Importpräfix-Entfernung
        if name.lower().startswith("[reminder]"):
            name = name.split("]",1)[-1].strip()
        return (it.type, name, it.reminder_utc)
    if it.type == "task":
        return (it.type, name, it.due_utc if it.type == 'task' else None)
    if it.type in ("appointment","event"):
        return (it.type, name, it.start_utc, it.end_utc)
    return (it.type, name)


def apply_import(repo, path: str, *, creator: str):
    if not os.path.exists(path):
        print(f"(Warn) Import-Datei nicht gefunden: {path}")
        return 0
    if not creator:
        raise ValueError("creator is required for ICS import")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    items = import_ics(text, creator=creator)

    existing = {it.id for it in repo.list_all()}
    new, updated = 0, 0
    for it in items:
        if not it.id:
            it = it.__class__(**{**it.__dict__, "id": _gen_id()})
            repo.upsert(it)
            new += 1
        else:
            # id existiert -> update
            repo.upsert(it)
            updated += 1
    print(f"(Info) Import: neu={new}, aktualisiert={updated} aus {path}")

def cleanup_duplicates(repo):
    items = repo.list_all()
    to_delete = set()

    # 1) Appointments/Events dedupe
    seen_events = {}
    for it in items:
        if it.type in ("appointment", "event"):
            rrule = getattr(it.recurrence, "rrule_string", None) if getattr(it, "recurrence", None) else None
            key = (it.type, it.name, getattr(it, "start_utc", None), getattr(it, "end_utc", None), rrule)
            if key in seen_events:
                # wähle stabilere UID (z. B. kleinere) behalten
                keep = min(seen_events[key], it.id)
                drop = seen_events[key] if keep == it.id else it.id
                to_delete.add(drop)
                seen_events[key] = keep
            else:
                seen_events[key] = it.id

    # 2) Reminder vs Task Kollisionsregel
    rem_map = {}
    for it in items:
        if it.type == "reminder":
            key = (it.name, it.reminder_utc)
            rem_map.setdefault(key, []).append(it)

    for it in items:
        if it.type == "task":
            key = (it.name, getattr(it, "due_utc", None))
            if key in rem_map:
                # Reminder gewinnt, Task löschen
                to_delete.add(it.id)

    # 3) Reminder dedupe nach (name, reminder_utc)
    for key, group in rem_map.items():
        if len(group) > 1:
            # kleinste UID behalten
            keep = min(x.id for x in group)
            for x in group:
                if x.id != keep:
                    to_delete.add(x.id)

    # 4) Task dedupe nach (name, due_utc)
    task_groups = {}
    for it in items:
        if it.type == "task":
            key = (it.name, getattr(it, "due_utc", None))
            task_groups.setdefault(key, []).append(it)
    for key, group in task_groups.items():
        if len(group) > 1:
            keep = min(x.id for x in group)
            for x in group:
                if x.id != keep:
                    to_delete.add(x.id)

    deleted = 0
    for id_ in to_delete:
        if repo.delete(id_):
            deleted += 1
    print(f"(Info) Cleanup gelöscht: {deleted} Duplikate")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--lead", type=int, default=None, help="Reminder-Fenster in Minuten")
    p.add_argument("--seed-due-min", type=int, default=None, help="Seed: Task-Fälligkeit in Minuten ab jetzt")
    p.add_argument("--seed-rem-min", type=int, default=None, help="Seed: Reminder-Fälligkeit in Minuten ab jetzt")
    p.add_argument("--export", type=str, default="demo.ics", help="ICS-Exportdatei")
    p.add_argument("--import", dest="import_file", type=str, default=None, help="ICS-Datei importieren")
    p.add_argument("--filter-text", type=str, default=None)
    p.add_argument("--filter-tags", type=str, default=None, help="Kommagetrennte Tags")
    p.add_argument("--filter-types", type=str, default=None, help="Kommagetrennte Typen (task,appointment,event,reminder)")
    p.add_argument("--filter-status", type=str, default=None, help="Kommagetrennte Status-Keys")
    p.add_argument("--no-private", action="store_true", help="Private Einträge ausblenden")
    p.add_argument("--cleanup", action="store_true", help="Duplikate bereinigen")
    p.add_argument("--export-all", action="store_true", help="Exportiert immer alle Items, ignoriert Filter")
    return p.parse_args()

def main():
    creator = os.getenv("TASKMAN_CREATOR_ID")
    if not creator:
        raise ValueError("TASKMAN_CREATOR_ID environment variable must be set to create or import items")
    args = parse_args()
    status = make_status_service()
    repo = DbRepository("taskman.db")

    # Seed-Reset bei Bedarf
    if (args.seed_due_min is not None) or (args.seed_rem_min is not None):
        print("(Info) Reset DB for seeding with custom offsets")
        try:
            repo.clear()
        except AttributeError:
            # Fallback: harte Löschung der Datei, wenn clear nicht existiert
            db_path = "taskman.db"
        seed_data(
            repo,
            creator=creator,
            due_delta_min=args.seed_due_min if args.seed_due_min is not None else 8,
            reminder_delta_min=args.seed_rem_min if args.seed_rem_min is not None else 5,
        )
            if not creator:  # Ensure creator is required
                raise ValueError("creator is required for ICS import")
        seed_data(repo,
        apply_import(repo, args.import_file, creator=creator)
                  reminder_delta_min=args.seed_rem_min if args.seed_rem_min is not None else 5)

    # Optionaler Import
    if args.import_file:
        apply_import(repo, args.import_file)
        if args.cleanup:
            cleanup_duplicates(repo)

    # Filter vorbereiten
    types = args.filter_types.split(",") if args.filter_types else None
    tags = [t.strip() for t in args.filter_tags.split(",")] if args.filter_tags else None
    status_keys = args.filter_status.split(",") if args.filter_status else None
    items_all = repo.list_all()
    items = filter_items(items_all,
                         text=args.filter_text,
                         tags=tags,
                         types=types,
                         status_keys=status_keys,
                         include_private=not args.no_private)

    # Lead-Minuten
    lead_cfg = args.lead if args.lead is not None else int(os.getenv("LEAD_MIN", "10"))
    print(f"(Info) lead_minutes={lead_cfg}")
    notifier = ConsoleNotifier()
    ns = NotificationService(status_service=status, lead_minutes=lead_cfg)
    scheduler = SchedulerService(repo=repo, status=status, notifier=notifier, lead_minutes=lead_cfg)

    # Anzeige + Notifications
    win_start = now_utc()
    win_end = now_utc() + timedelta(hours=24)
    print("=== Items ===")
    for it in items:
        print(f"- {it.type} {it.name} [{status.get_display_name(it.status)}]")
        occs = expand_item(it, win_start, win_end)
        for occ in occs:
            if occ.item_type == "task":
                due_local = format_display_datetime(occ.due_utc, "%d.%m.%Y %H:%M")
                print(f"  • Task-Occurrence: due={due_local}")
            elif occ.item_type == "reminder":
                due_local = format_display_datetime(occ.due_utc, "%d.%m.%Y %H:%M")
                print(f"  • Reminder-Occurrence: fällig={due_local}")
            else:
                s_local = format_display_datetime(occ.start_utc, "%d.%m.%Y %H:%M")
                e_local = format_display_datetime(occ.end_utc, "%d.%m.%Y %H:%M") if occ.end_utc else ""
                print(f"  • Termin-Occurrence: {s_local} - {e_local}")

            # Optionale Live-Notification
            ref = occ.due_utc if occ.item_type in ("task","reminder") else occ.start_utc
            now = now_utc()
            win_end_debug = now + timedelta(minutes=lead_cfg)
            in_window = (ref is not None) and (now <= ref <= win_end_debug)
            ref_local = format_display_datetime(ref, "%d.%m.%Y %H:%M:%S") if ref else "None"
            now_local = format_display_datetime(now, "%d.%m.%Y %H:%M:%S")
            win_end_local = format_display_datetime(win_end_debug, "%d.%m.%Y %H:%M:%S")
            ref_utc = ref.isoformat() if ref else "None"
            print(f"    Debug: now_local={now_local}, ref_local={ref_local}, win_end_local={win_end_local}, ref_utc={ref_utc}, in_window={in_window}")

            if ns.should_notify(it.status, occ):
                print("    -> Reminder fällig (<=10 Min)!")

    # Export (optional auf gefilterte Items anwenden)
    if args.cleanup:
        cleanup_duplicates(repo)
    export_source = items_all if args.export_all else items
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\n" + "\n".join(to_ics(it, alarm_min=lead_cfg) for it in export_source) + "\nEND:VCALENDAR\n"

    with open(args.export, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"ICS exportiert nach {args.export}")

if __name__ == "__main__":
    main()
