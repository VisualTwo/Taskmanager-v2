# infrastructure/db_repository.py
from __future__ import annotations
import sqlite3
import json
import uuid
from typing import Optional, List, Union, Iterable
from domain.models import Task, Appointment, Event, Reminder, Recurrence
from utils.datetime_helpers import parse_db_datetime, format_db_datetime, now_utc
from utils.status_manager import catalog_choose_default_status

Item = Union[Task, Appointment, Event, Reminder]

DDL = """
CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK(type IN ('task','appointment','event','reminder')),
  name TEXT NOT NULL,
  description TEXT,
  status_key TEXT NOT NULL,
  is_private INTEGER NOT NULL DEFAULT 0 CHECK(is_private IN (0,1)),
  tags TEXT NOT NULL DEFAULT '[]',
  links TEXT NOT NULL DEFAULT '[]',

  -- Zeitfelder
  start_utc TEXT,
  end_utc TEXT,
  due_utc TEXT,

  -- Tasks: optionales Planungsfenster
  task_planned_start_utc TEXT,
  task_planned_end_utc TEXT,

  -- Reminder: primärer Zeitpunkt
  reminder_utc TEXT,

  is_all_day INTEGER NOT NULL DEFAULT 0 CHECK(is_all_day IN (0,1)),
  rrule_string TEXT,
  exdates TEXT,

  -- ICS
  ics_uid TEXT UNIQUE,

  -- Priorität: 0-5, NULL bedeutet nicht gesetzt
  priority INTEGER CHECK(priority IS NULL OR (priority >= 0 AND priority <= 5)),

  -- ICE Prioritization (strukturiert statt generisches metadata)
    ice_impact INTEGER CHECK(ice_impact IS NULL OR (ice_impact >= 1 AND ice_impact <= 5)),
  ice_confidence TEXT CHECK(ice_confidence IS NULL OR ice_confidence IN ('very_low','low','medium','high','very_high')),
    ice_ease INTEGER CHECK(ice_ease IS NULL OR (ice_ease >= 1 AND ice_ease <= 5)),
  ice_score REAL CHECK(ice_score IS NULL OR ice_score >= 0),

  -- Multi-user fields for tenant support
  creator TEXT NOT NULL,  -- User ID who created the item
  participants TEXT NOT NULL DEFAULT '[]',  -- JSON array of User IDs

  -- Weitere Metadaten (JSON) für Erweiterung
  metadata TEXT NOT NULL DEFAULT '{}',

  -- Audit
  created_utc TEXT NOT NULL,
  last_modified_utc TEXT NOT NULL
);

-- Indizes für häufige Abfragen
CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
CREATE INDEX IF NOT EXISTS idx_items_status_key ON items(status_key);
CREATE INDEX IF NOT EXISTS idx_items_ics_uid ON items(ics_uid);
CREATE INDEX IF NOT EXISTS idx_items_priority ON items(priority);
CREATE INDEX IF NOT EXISTS idx_items_is_private ON items(is_private);
CREATE INDEX IF NOT EXISTS idx_items_created_utc ON items(created_utc);
CREATE INDEX IF NOT EXISTS idx_items_ice_score ON items(ice_score DESC);
CREATE INDEX IF NOT EXISTS idx_items_creator ON items(creator);
"""

EXPECTED_COLS = {
  "id","type","name","description","status_key","is_private","tags","links",
  "start_utc","end_utc","due_utc",
  "task_planned_start_utc","task_planned_end_utc",
  "reminder_utc",
  "is_all_day","rrule_string","exdates",
  "ics_uid",
  "priority",
  "creator","participants",
  "created_utc","last_modified_utc"
}

class DbRepository:
    def __init__(self, db_path: str):
        # check_same_thread=False erlaubt Nutzung im Threadpool
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(DDL)
        self.conn.commit()
        self._ensure_columns()
        self._ensure_metadata_column()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM items")
        self.conn.commit()
        self._ensure_columns()

    def _ensure_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(items)").fetchall()}
        to_add = []
        if "description" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN description TEXT;")
        if "task_planned_start_utc" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN task_planned_start_utc TEXT;")
        if "task_planned_end_utc" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN task_planned_end_utc TEXT;")
        if "reminder_utc" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN reminder_utc TEXT;")
        if "links" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN links TEXT;")
        if "tags" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN tags TEXT;")
        if "ics_uid" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN ics_uid TEXT;")
        if "priority" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN priority INTEGER;")
        if "creator" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN creator TEXT DEFAULT 'admin';")
        if "participants" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN participants TEXT DEFAULT '[]';")
        if "created_utc" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN created_utc TEXT;")
        if "last_modified_utc" not in cols:
            to_add.append("ALTER TABLE items ADD COLUMN last_modified_utc TEXT;")

        for stmt in to_add:
            self.conn.execute(stmt)
        if to_add:
            # Defaults initialisieren
            self.conn.execute("UPDATE items SET links='[]' WHERE links IS NULL;")
            self.conn.execute("UPDATE items SET participants='[]' WHERE participants IS NULL;")
            self.conn.execute("UPDATE items SET creator='admin' WHERE creator IS NULL;")
            # optionale Indizes
            try:
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_items_ics_uid ON items(ics_uid);")
            except Exception:
                pass
            try:
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_items_priority ON items(priority);")
            except Exception:
                pass
            try:
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_items_creator ON items(creator);")
            except Exception:
                pass
            self.conn.commit()

    def _ensure_metadata_column(self):
        """Add ICE and metadata columns if they don't exist (schema migration)."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(items)").fetchall()}
        migrations = []
        
        if "ice_impact" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN ice_impact INTEGER CHECK(ice_impact IS NULL OR (ice_impact >= 1 AND ice_impact <= 5));")
        if "ice_confidence" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN ice_confidence TEXT CHECK(ice_confidence IS NULL OR ice_confidence IN ('very_low','low','medium','high','very_high'));")
        if "ice_ease" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN ice_ease INTEGER CHECK(ice_ease IS NULL OR (ice_ease >= 1 AND ice_ease <= 5));")
        if "ice_score" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN ice_score REAL CHECK(ice_score IS NULL OR ice_score >= 0);")
        if "metadata" not in cols:
            migrations.append("ALTER TABLE items ADD COLUMN metadata TEXT DEFAULT '{}';")
        
        # Ensure proper defaults and NOT NULLs (for existing tables)
        if migrations:
            for stmt in migrations:
                try:
                    self.conn.execute(stmt)
                except Exception as e:
                    # Column may already exist; that's fine
                    pass
            
            # Ensure indices
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);",
                "CREATE INDEX IF NOT EXISTS idx_items_status_key ON items(status_key);",
                "CREATE INDEX IF NOT EXISTS idx_items_ics_uid ON items(ics_uid);",
                "CREATE INDEX IF NOT EXISTS idx_items_priority ON items(priority);",
                "CREATE INDEX IF NOT EXISTS idx_items_is_private ON items(is_private);",
                "CREATE INDEX IF NOT EXISTS idx_items_created_utc ON items(created_utc);",
                "CREATE INDEX IF NOT EXISTS idx_items_ice_score ON items(ice_score DESC);",
            ]
            for idx_stmt in indices:
                try:
                    self.conn.execute(idx_stmt)
                except Exception:
                    pass
            
            self.conn.commit()

    def upsert(self, item: Item) -> None:
        """
        Fügt ein Item ein oder aktualisiert es.
        WICHTIG: Führt KEIN commit() aus. Transaktionsgrenzen liegen beim Aufrufer.
        """
        # JSON-Felder
        tags_json = json.dumps(list(getattr(item, "tags", ()) or ()))
        links_json = json.dumps(list(getattr(item, "links", ()) or ()))
        description = (getattr(item, "description", None) or "")
        metadata_json = json.dumps(dict(getattr(item, "metadata", {}) or {}))
        
        # Participants - convert tuple to comma-separated string
        participants_str = ",".join(item.participants) if item.participants else ""
        creator = item.creator if hasattr(item, 'creator') else ""

        # Recurrence
        rrule_string = item.recurrence.rrule_string if getattr(item, "recurrence", None) else None
        exdates = getattr(item.recurrence, "exdates_utc", ()) if getattr(item, "recurrence", None) else ()
        exdates_str = "|".join([format_db_datetime(x) for x in exdates]) or None

        # ICS UID und Priority
        ics_uid = (getattr(item, "ics_uid", None) or None)
        priority = getattr(item, "priority", None)
        prio_val = int(priority) if (priority is not None and str(priority).strip() != "") else None

        # ICE Felder aus metadata extrahieren (Backward compatibility)
        ice_impact = getattr(item, "metadata", {}).get("ice_impact")
        ice_confidence = getattr(item, "metadata", {}).get("ice_confidence")
        ice_ease = getattr(item, "metadata", {}).get("ice_ease")
        ice_score = getattr(item, "metadata", {}).get("ice_score")

        # Parse to proper types
        try:
            ice_impact = int(ice_impact) if ice_impact else None
        except (ValueError, TypeError):
            ice_impact = None
        try:
            ice_ease = int(ice_ease) if ice_ease else None
        except (ValueError, TypeError):
            ice_ease = None
        try:
            ice_score = float(ice_score) if ice_score else None
        except (ValueError, TypeError):
            ice_score = None

        # Audit
        now_iso = format_db_datetime(now_utc())

        if item.type == "task":
            self.conn.execute(
                """INSERT INTO items (id,type,name,description,status_key,is_private,tags,links,
                                      due_utc,task_planned_start_utc,task_planned_end_utc,
                                      rrule_string,exdates,ics_uid,priority,ice_impact,ice_confidence,ice_ease,ice_score,metadata,creator,participants,created_utc,last_modified_utc)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     type=excluded.type, name=excluded.name, description=excluded.description, status_key=excluded.status_key,
                     is_private=excluded.is_private, tags=excluded.tags, links=excluded.links,
                     due_utc=excluded.due_utc,
                     task_planned_start_utc=excluded.task_planned_start_utc,
                     task_planned_end_utc=excluded.task_planned_end_utc,
                     rrule_string=excluded.rrule_string, exdates=excluded.exdates,
                     ics_uid=excluded.ics_uid,
                     priority=excluded.priority,
                     ice_impact=excluded.ice_impact, ice_confidence=excluded.ice_confidence,
                     ice_ease=excluded.ice_ease, ice_score=excluded.ice_score,
                     metadata=excluded.metadata, creator=excluded.creator, participants=excluded.participants,
                     last_modified_utc=excluded.last_modified_utc
                """,
                (
                    item.id, "task", item.name, description, item.status, int(item.is_private), tags_json, links_json,
                    format_db_datetime(getattr(item, "due_utc", None)),
                    format_db_datetime(getattr(item, "planned_start_utc", None)),
                    format_db_datetime(getattr(item, "planned_end_utc", None)),
                    rrule_string, exdates_str,
                    ics_uid, prio_val, ice_impact, ice_confidence, ice_ease, ice_score, metadata_json,
                    creator, participants_str, now_iso, now_iso,
                ),
            )
        elif item.type in ("appointment","event"):
            self.conn.execute(
                """INSERT INTO items (id,type,name,description,status_key,is_private,tags,links,
                                      start_utc,end_utc,is_all_day,
                                      rrule_string,exdates,ics_uid,priority,ice_impact,ice_confidence,ice_ease,ice_score,metadata,creator,participants,created_utc,last_modified_utc)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     type=excluded.type, name=excluded.name, description=excluded.description, status_key=excluded.status_key,
                     is_private=excluded.is_private, tags=excluded.tags, links=excluded.links,
                     start_utc=excluded.start_utc, end_utc=excluded.end_utc, is_all_day=excluded.is_all_day,
                     rrule_string=excluded.rrule_string, exdates=excluded.exdates,
                     ics_uid=excluded.ics_uid,
                     priority=excluded.priority,
                     ice_impact=excluded.ice_impact, ice_confidence=excluded.ice_confidence,
                     ice_ease=excluded.ice_ease, ice_score=excluded.ice_score,
                     metadata=excluded.metadata, creator=excluded.creator, participants=excluded.participants,
                     last_modified_utc=excluded.last_modified_utc
                """,
                (
                    item.id, item.type, item.name, description, item.status, int(item.is_private), tags_json, links_json,
                    format_db_datetime(getattr(item, "start_utc", None)),
                    format_db_datetime(getattr(item, "end_utc", None)),
                    int(getattr(item, "is_all_day", False)),
                    rrule_string, exdates_str,
                    ics_uid, prio_val, ice_impact, ice_confidence, ice_ease, ice_score, metadata_json,
                    creator, participants_str, now_iso, now_iso,
                ),
            )
        elif item.type == "reminder":
            self.conn.execute(
                """INSERT INTO items (id,type,name,description,status_key,is_private,tags,links,
                                      reminder_utc,rrule_string,exdates,ics_uid,priority,ice_impact,ice_confidence,ice_ease,ice_score,metadata,creator,participants,created_utc,last_modified_utc)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     type=excluded.type, name=excluded.name, description=excluded.description, status_key=excluded.status_key,
                     is_private=excluded.is_private, tags=excluded.tags, links=excluded.links,
                     reminder_utc=excluded.reminder_utc, rrule_string=excluded.rrule_string, exdates=excluded.exdates,
                     ics_uid=excluded.ics_uid,
                     priority=excluded.priority,
                     ice_impact=excluded.ice_impact, ice_confidence=excluded.ice_confidence,
                     ice_ease=excluded.ice_ease, ice_score=excluded.ice_score,
                     metadata=excluded.metadata, creator=excluded.creator, participants=excluded.participants,
                     last_modified_utc=excluded.last_modified_utc
                """,
                (
                    item.id, "reminder", item.name, description, item.status, int(item.is_private), tags_json, links_json,
                    format_db_datetime(getattr(item, "reminder_utc", None)),
                    rrule_string, exdates_str,
                    ics_uid, prio_val, ice_impact, ice_confidence, ice_ease, ice_score, metadata_json,
                    creator, participants_str, now_iso, now_iso,
                ),
            )
        else:
            raise ValueError(f"Unknown item type: {item.type}")

    def get(self, item_id: str) -> Optional[Item]:
        row = self.conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def get_by_ics_uid(self, uid: str) -> Optional[Item]:
        if not uid:
            return None
        row = self.conn.execute("SELECT * FROM items WHERE ics_uid=? LIMIT 1", (uid,)).fetchone()
        return self._row_to_item(row) if row else None

    def delete(self, item_id: str) -> bool:
        """
        Löscht ein Item. Kein Commit hier – Transaktionsgrenzen liegen beim Aufrufer.
        """
        cur = self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        return cur.rowcount > 0

    def list_all(self) -> List[Item]:
        rows = self.conn.execute("SELECT * FROM items").fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_by_type(self, item_type: str) -> List[Item]:
        rows = self.conn.execute("SELECT * FROM items WHERE type=?", (item_type,)).fetchall()
        return [self._row_to_item(r) for r in rows]

    def filter(self, where_sql: str, params: Iterable = ()) -> List[Item]:
        rows = self.conn.execute(f"SELECT * FROM items WHERE {where_sql}", params).fetchall()
        return [self._row_to_item(r) for r in rows]
        
    def is_user_admin(self, user_id: str) -> bool:
        """Check if user has admin privileges - reusable method"""
        user_row = self.conn.execute(
            "SELECT ist_admin FROM users WHERE id = ? OR login = ?",
            (user_id, user_id)
        ).fetchone()
        return user_row and user_row["ist_admin"] == 1
    
    def _user_has_item_access(self, user_id: str, creator: str = None, participants: str = None, item_type: str = None) -> bool:
        """Central access control logic for a single item
        
        Access rules:
        - Tasks/Reminders/Appointments: Creator OR user in participants. If no participants, ONLY creator.
        - Events: Creator OR user in participants. If no participants, EVERYONE can see.
        """
        # Get current user info for comparison
        current_user_row = self.conn.execute(
            "SELECT id, login FROM users WHERE id = ? OR login = ?",
            (user_id, user_id)
        ).fetchone()
        
        if current_user_row:
            current_user_uuid = current_user_row["id"]
            current_user_login = current_user_row["login"]
        else:
            # Fallback if user not found in DB
            current_user_uuid = user_id
            current_user_login = user_id
            
        # Rule 1: User is creator (check both UUID and login)
        if creator:
            creator_str = str(creator).strip()
            if (creator_str == str(current_user_uuid).strip() or 
                creator_str == str(current_user_login).strip()):
                return True
                
            # Special case: Allow access to admin-created items for all users
            if creator_str.lower() == "admin":
                return True
                
        # Rule 2: User is participant (check both UUID and login)  
        participants_str = str(participants).strip() if participants else ""
        if (participants_str and 
            participants_str not in ['', 'null', 'None', '[]'] and
            not participants_str.startswith('[]')):
            participant_list = [p.strip() for p in participants_str.split(",") if p.strip()]
            for participant in participant_list:
                if (str(participant) == str(current_user_uuid) or 
                    str(participant) == str(current_user_login)):
                    return True
                    
        # Rule 3: Empty participants - type-dependent logic
        # Events: If no participants, EVERYONE can see
        # Tasks/Reminders/Appointments: If no participants, ONLY creator (already checked in Rule 1)
        participants_str = str(participants).strip() if participants else ""
        is_empty_participants = (not participants or 
            participants_str in ['', 'null', 'None', '[]'] or
            participants_str.startswith('[]'))
        
        if is_empty_participants and item_type == 'event':
            # Events without participants are visible to everyone
            return True
        
        # For all other types or if creator/participant checks failed
        return False
        
    def list_for_user(self, user_id: str) -> List[Item]:
        """List all items that user has access to using consistent access logic"""
        # Check if user is admin - admins can see all items
        if self.is_user_admin(user_id):
            rows = self.conn.execute("SELECT * FROM items").fetchall()
        else:
            # Use the same logic as individual access checks
            rows = self.conn.execute("SELECT * FROM items").fetchall()
            
            # Filter using our central access logic
            filtered_rows = []
            for row in rows:
                creator = row.get("creator")
                participants = row.get("participants")
                item_type = row.get("type")
                if self._user_has_item_access(user_id, creator, participants, item_type):
                    filtered_rows.append(row)
            rows = filtered_rows
            
        return [self._row_to_item(r) for r in rows]
    
    def user_has_access(self, user_id: str, item_id: str) -> bool:
        """Check if user has access to specific item"""
        try:
            print(f"DEBUG - Checking access for user {user_id} to item {item_id}")
            
            # Check if creator and participants columns exist
            cursor = self.conn.execute("PRAGMA table_info(items)")
            columns = [row[1] for row in cursor.fetchall()]
            has_creator_col = 'creator' in columns
            has_participants_col = 'participants' in columns
            
            print(f"DEBUG - Schema check: creator={has_creator_col}, participants={has_participants_col}")
            
            # Build query based on available columns
            if has_creator_col and has_participants_col:
                query = "SELECT creator, participants, type FROM items WHERE id = ?"
            elif has_creator_col:
                query = "SELECT creator, NULL as participants, type FROM items WHERE id = ?"
            else:
                print(f"DEBUG - No creator/participants columns, granting access")
                return True
                
            row = self.conn.execute(query, (item_id,)).fetchone()
            
            if not row:
                print(f"DEBUG - Item {item_id} not found in database")
                return False
                
            creator = row["creator"] if has_creator_col else None
            participants = row["participants"] if has_participants_col else ""
            item_type = row["type"] if "type" in row.keys() else None
            
            print(f"DEBUG - DB creator: '{creator}', participants: '{participants}', type: '{item_type}'")
            
            # Use central access logic
            has_access = self._user_has_item_access(user_id, creator, participants, item_type)
            
            if has_access:
                print(f"DEBUG - Access granted by central logic")
            else:
                print(f"DEBUG - Access denied by central logic")
            
            return has_access
            
        except Exception as e:
            print(f"DEBUG - Exception in user_has_access: {e}")
            import traceback
            traceback.print_exc()
            # In case of any error, be permissive to avoid breaking the app
            print(f"DEBUG - Granting access due to exception (fail-safe)")
            return True

    def _get_col(self, r: sqlite3.Row, name: str):
        try:
            return r[name]
        except (IndexError, KeyError):
            return None
        
    def copy_item(self, item_id: str, *, with_new_id: Optional[str] = None, with_new_ics_uid: Optional[str] = None) -> Item:
        """
        Dupliziert ein Item: neue ID, neue ICS-UID, aktualisierte Audit-Felder.
        Persistiert die Kopie via upsert und gibt das neue Domain-Objekt zurück.
        Commit erfolgt NICHT hier.
        """
        src = self.get(item_id)
        if not src:
            raise ValueError("Item not found")

        # Neue Schlüssel
        new_id = with_new_id or str(uuid.uuid4())
        new_uid = with_new_ics_uid or None

        # JSON-Felder (Repo speichert selbst als JSON; Domain hält tuples)
        tags = tuple(getattr(src, "tags", ()) or ())
        links = tuple(getattr(src, "links", ()) or ())
        metadata = dict(getattr(src, "metadata", {}) or {})  # Copy metadata

        # Recurrence: baue aus Domain-Objekt die Spalten, wie es upsert erwartet
        recur = getattr(src, "recurrence", None)
        rrule_string = recur.rrule_string if recur else None
        exdates_utc = tuple(getattr(recur, "exdates_utc", ()) or ())

        t = getattr(src, "type", "")
        now = now_utc()
        common_kwargs = {
            "id": new_id,
            "type": t,
            "name": src.name,
            "status": catalog_choose_default_status(t), # always default status
            "is_private": bool(getattr(src, "is_private", False)),
            "tags": tags,
            "links": links,
            "description": getattr(src, "description", "") or "",
            "priority": getattr(src, "priority", None),
            "ics_uid": new_uid,
            "metadata": metadata,
            "created_utc": now,
            "last_modified_utc": now,
        }

        # Typ-spezifische Zeitfelder setzen
        if t == "task":
            new_obj = Task(
                **common_kwargs,
                due_utc=getattr(src, "due_utc", None),
                recurrence=Recurrence(rrule_string=rrule_string, exdates_utc=exdates_utc) if rrule_string else None,
            )
        elif t == "reminder":
            new_obj = Reminder(
                **common_kwargs,
                reminder_utc=getattr(src, "reminder_utc", None),
                recurrence=Recurrence(rrule_string=rrule_string, exdates_utc=exdates_utc) if rrule_string else None,
            )
        elif t in ("appointment", "event"):
            new_obj = (Appointment if t == "appointment" else Event)(
                **common_kwargs,
                start_utc=getattr(src, "start_utc", None),
                end_utc=getattr(src, "end_utc", None),
                is_all_day=bool(getattr(src, "is_all_day", False)),
                recurrence=Recurrence(rrule_string=rrule_string, exdates_utc=exdates_utc) if rrule_string else None,
            )
        else:
            raise ValueError(f"Unknown type for copy: {t}")

        # Persistieren
        self.upsert(new_obj)
        return new_obj

    def _parse_json_array(self, raw: Optional[str]) -> tuple[str, ...]:
        """Parse JSON array or comma-separated string into tuple of strings."""
        if not raw:
            return ()
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return tuple(str(x) for x in arr if x is not None)
        except (json.JSONDecodeError, TypeError):
            # Fallback: try comma-separated
            pass
        parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
        return tuple(parts)

    def _parse_json_dict(self, raw: Optional[str]) -> dict:
        """Parse JSON object into dict; return empty dict on error."""
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def _row_to_recur(self, r: sqlite3.Row) -> Optional[Recurrence]:
        rrule = r["rrule_string"]
        if not rrule:
            return None
        exdates_str = r["exdates"] or ""
        exdates = tuple(
            d for d in (parse_db_datetime(x) for x in exdates_str.split("|") if x)
            if d is not None
        )
        return Recurrence(rrule_string=rrule, exdates_utc=exdates)

    def _row_to_item(self, r: sqlite3.Row) -> Item:
        """Convert DB row to Domain Item; robust against missing/malformed data."""
        t = r["type"]
        if t not in ("task", "appointment", "event", "reminder"):
            raise ValueError(f"Unknown item type in DB: {t}")
        
        tags = self._parse_json_array(r["tags"])
        links = self._parse_json_array(r["links"])
        description = r["description"] if r["description"] is not None else ""

        # Parse metadata from JSON with fallback
        metadata_dict = self._parse_json_dict(self._get_col(r, "metadata"))

        # Extract ICE fields from DB columns (not from metadata anymore)
        ice_impact = self._get_col(r, "ice_impact")
        ice_confidence = self._get_col(r, "ice_confidence")
        ice_ease = self._get_col(r, "ice_ease")
        ice_score = self._get_col(r, "ice_score")

        # Populate metadata with ICE fields for backward compatibility
        if ice_impact is not None:
            metadata_dict["ice_impact"] = str(ice_impact)
        if ice_confidence is not None:
            metadata_dict["ice_confidence"] = ice_confidence
        if ice_ease is not None:
            metadata_dict["ice_ease"] = str(ice_ease)
        if ice_score is not None:
            metadata_dict["ice_score"] = str(ice_score)

        common_kwargs = {
            "id": r["id"],
            "type": t,
            "name": r["name"] or "Unbenannt",  # Fallback für Namen
            "status": r["status_key"] or "UNKNOWN",  # Fallback für Status
            "is_private": bool(r["is_private"]),
            "creator": r["creator"] if r["creator"] else "unknown",  # Fallback creator
            "participants": tuple(r["participants"].split(",")) if r["participants"] else (),  # Parse participants
            "tags": tags,
            "links": links,
            "description": description,
            "metadata": metadata_dict,
        }
        # Audit-Felder
        created_dt = parse_db_datetime(self._get_col(r, "created_utc"))
        modified_dt = parse_db_datetime(self._get_col(r, "last_modified_utc"))
        if created_dt is not None:
            common_kwargs["created_utc"] = created_dt
        if modified_dt is not None:
            common_kwargs["last_modified_utc"] = modified_dt
        # ICS UID
        ics_uid = self._get_col(r, "ics_uid")
        if ics_uid:
            common_kwargs["ics_uid"] = ics_uid
        # Priority: validieren und casten
        if "priority" in r.keys():
            prio = self._get_col(r, "priority")
            if prio is not None:
                try:
                    prio_int = int(prio)
                    if 0 <= prio_int <= 5:
                        common_kwargs["priority"] = prio_int
                except (ValueError, TypeError):
                    # Ungültiger Wert -> Skip
                    pass

        if t == "task":
            return Task(
                **common_kwargs,
                due_utc=parse_db_datetime(self._get_col(r, "due_utc")),
                recurrence=self._row_to_recur(r)
            )
        elif t == "appointment":
            return Appointment(
                **common_kwargs,
                start_utc=parse_db_datetime(r["start_utc"]),
                end_utc=parse_db_datetime(r["end_utc"]),
                is_all_day=bool(r["is_all_day"]),
                recurrence=self._row_to_recur(r)
            )
        elif t == "event":
            return Event(
                **common_kwargs,
                start_utc=parse_db_datetime(r["start_utc"]),
                end_utc=parse_db_datetime(r["end_utc"]),
                is_all_day=bool(r["is_all_day"]),
                recurrence=self._row_to_recur(r)
            )
        elif t == "reminder":
            return Reminder(
                **common_kwargs,
                reminder_utc=parse_db_datetime(self._get_col(r, "reminder_utc")),
                recurrence=self._row_to_recur(r)
            )
        else:
            raise ValueError(f"Unknown item type: {t}")
