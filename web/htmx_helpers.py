def get_keys_for_status_label(label, type_status_options):
    """
    Given a status label (display name) and a dict of type_status_options,
    return all status keys (across all types) that have this label.
    """
    keys = []
    for type_opts in type_status_options.values():
        for key, display in type_opts:
            if display == label:
                keys.append(key)
    return keys
"""
Imports, App-Initialisierung und Helper Functions
werden an den Anfang der Datei verschoben, damit alle Symbole
wie app, get_repo etc. vor der Nutzung definiert sind.
"""

# --- Imports ---
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from typing import Optional
import uuid
from infrastructure.db_repository import DbRepository
from bootstrap import make_status_service
from services.filter_service import filter_items
from services.recurrence_service import expand_item
from infrastructure.ical_mapper import to_ics
from infrastructure.ical_importer import import_ics
from utils.datetime_helpers import now_utc

# --- App Initialization ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# --- Helper Functions ---
def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "false").lower() == "true"

def hx_redirect(url: str) -> Response:
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = url
    return resp

def hx_refresh() -> Response:
    resp = Response(status_code=204)
    resp.headers["HX-Refresh"] = "true"
    return resp

# Jinja-Filter: UTC -> Europe/Berlin
def format_local(dt: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    try:
        return dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
    except Exception:
        return ""

templates.env.filters["format_local"] = format_local

# Jinja-Filter für Beschreibung: '\n' → Zeilenumbruch, '\,' → Komma
def unescape_description(value):
    if not value:
        return ""
    return value.replace('\\n', '\n').replace('\\,', ',')
templates.env.filters["unescape_description"] = unescape_description

def get_repo():
    return DbRepository("taskman.db")

def get_status():
    return make_status_service()

def _parse_local_dt(s: str) -> Optional[datetime]:
    try:
        dt_local = datetime.strptime(s.strip(), "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Berlin"))
        return dt_local.astimezone(ZoneInfo("UTC"))
    except Exception:
        return None

def _type_allowed_status_keys(status, it_type: str) -> list[str]:
    catalog = getattr(status, "catalog", {}) or {}
    if it_type == "task":
        return [k for k in catalog if k.startswith("TASK_")]
    if it_type == "reminder":
        return [k for k in catalog if k.startswith("REMINDER_")]
    if it_type == "appointment":
        return [k for k in catalog if k.startswith("APPOINTMENT_")]
    if it_type == "event":
        return [k for k in catalog if k.startswith("EVENT_") or k.startswith("APPOINTMENT_")]
    return list(catalog.keys())

def _normalize_rrule_input(dtstart_local: str, rrule_line: str, exdates_local: str):
    dtstart_utc = _parse_local_dt(dtstart_local) if dtstart_local.strip() else None
    rrule_line = (rrule_line or "").strip()
    if not dtstart_utc and not rrule_line and not exdates_local.strip():
        return None, None
    rrule_string = None
    if rrule_line:
        if dtstart_utc:
            rrule_string = f"DTSTART:{dtstart_utc.strftime('%Y%m%dT%H%M%SZ')}\nRRULE:{rrule_line}"
        else:
            rrule_string = f"RRULE:{rrule_line}"
    exdates_utc = []
    if exdates_local.strip():
        for part in exdates_local.split(","):
            d = _parse_local_dt(part.strip())
            if d:
                exdates_utc.append(d)
    return rrule_string, tuple(exdates_utc) if exdates_utc else None

def _build_recurrence(rrule_string: Optional[str], exdates_utc: Optional[tuple]):
    from domain.models import Recurrence
    if not rrule_string and not exdates_utc:
        return None
    return Recurrence(rrule_string=rrule_string or "", exdates_utc=exdates_utc or ())


 # --- Übersicht / Index ---
 
# --- Item-Edit (GET/POST) ---
@app.get("/edit/{uid}", response_class=HTMLResponse)
def edit_item(
    request: Request,
    uid: str,
    repo: DbRepository = Depends(get_repo),
    status=Depends(get_status),
):
    item = repo.get(uid)
    if not item:
        return hx_redirect("/")
    return templates.TemplateResponse(request, "edit.html", {
        "request": request,
        "item": item,
        "status_options": [(k, status.get_display_name(k)) for k in _type_allowed_status_keys(status, item.type)],
    })

@app.post("/edit/{uid}", response_class=HTMLResponse)
async def save_item(
    request: Request,
    uid: str,
    repo: DbRepository = Depends(get_repo),
    status=Depends(get_status),
):
    form = await request.form()
    item = repo.get(uid)
    if not item:
        return hx_redirect("/")
    # Update fields
    item.title = form.get("title", item.title)
    item.description = form.get("description", item.description)
    item.status = form.get("status", item.status)
    item.due = _parse_local_dt(form.get("due"))
    item.start = _parse_local_dt(form.get("start"))
    item.end = _parse_local_dt(form.get("end"))
    item.rrule = _normalize_rrule_input(form.get("rrule"))
    repo.update(item)
    return hx_refresh()
@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: str | None = None,
    types: str | None = None,
    status_keys: str | None = None,
    show_private: int = 1,
    range: str | None = None,
    repo: DbRepository = Depends(get_repo),
    status=Depends(get_status),
):
    items = repo.list_all()
    types_list = types.split(",") if types else None
    status_list = status_keys.split(",") if status_keys else None
    items = filter_items(items, text=q, types=types_list, status_keys=status_list, include_private=bool(int(show_private or 1)))

    win_start = now_utc()
    if range == "7tage":
        win_end = now_utc() + timedelta(days=7)
    elif range == "heute":
        win_end = now_utc() + timedelta(hours=24)
    else:
        win_end = now_utc() + timedelta(hours=48)

    rows = [(it, expand_item(it, win_start, win_end)) for it in items]

    try:
        type_status_options = {
            t: [(k, status.get_display_name(k)) for k in _type_allowed_status_keys(status, t)]
            for t in ("task","reminder","appointment","event")
        }
    except Exception:
        type_status_options = {}

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "rows": rows,
        "type_status_options": type_status_options,
        "current_range": range or "",
    })

@app.get("/items/{item_id}/edit", response_class=HTMLResponse)
def edit_item_page(item_id: str, request: Request, repo: DbRepository = Depends(get_repo), status=Depends(get_status)):
    it = repo.get(item_id)
    if not it:
        raise HTTPException(404, "Item nicht gefunden")

    allowed = _type_allowed_status_keys(status, it.type)
    status_options = [(k, status.get_display_name(k)) for k in allowed]

    rrule_line = ""
    dtstart_local = ""
    exdates_local = ""
    if getattr(it, "recurrence", None) and it.recurrence.rrule_string:
        for line in it.recurrence.rrule_string.splitlines():
            if line.startswith("DTSTART:"):
                try:
                    dt = datetime.strptime(line.split(":",1)[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
                    dtstart_local = format_local(dt)
                except Exception:
                    pass
            if line.startswith("RRULE:"):
                rrule_line = line.split(":",1)[1]
    if getattr(it, "recurrence", None) and it.recurrence.exdates_utc:
        exdates_local = ", ".join(format_local(d) for d in it.recurrence.exdates_utc)

    return templates.TemplateResponse(request, "edit.html", {
        "request": request,
        "it": it,
        "status_options": status_options,
        "dtstart_local": dtstart_local,
        "rrule_line": rrule_line,
        "exdates_local": exdates_local,
    })

@app.post("/items/{item_id}/edit")
def edit_item_submit(
    request: Request,
    item_id: str,
    name: str = Form(...),
    status_key: str = Form(...),
    is_private: int = Form(0),
    tags: str = Form(""),
    due: str = Form(""),
    start_local: str = Form(""),
    end_local: str = Form(""),
    dtstart_local: str = Form(""),
    rrule_line: str = Form(""),
    exdates_local: str = Form(""),
    ice_impact: str = Form(None),
    ice_confidence: str = Form(None),
    ice_ease: str = Form(None),
    repo: DbRepository = Depends(get_repo),
    status=Depends(get_status),
):

    it = repo.get(item_id)
    if not it:
        raise HTTPException(404, "Item nicht gefunden")

    import logging
    logger = logging.getLogger("edit_item_submit")

    # Aktuellen User aus Header holen (nur für Logging, nicht zum Überschreiben!)
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")


    # Status normalisieren und validieren wie in server.py
    requested_status_key = status_key if (status_key or "") != "" else getattr(it, "status", None)
    requested_status_key = status.normalize_input(requested_status_key or "", it.type) if requested_status_key else requested_status_key

    allowed = _type_allowed_status_keys(status, it.type)
    if requested_status_key not in allowed:
        msg = f"Ungültiger Status für diesen Typ."
        logger.error(f"Status-Validierung fehlgeschlagen: {requested_status_key} nicht in {allowed}")
        html = templates.get_template("_alerts.html").render({"messages": [msg]})
        return HTMLResponse(content=html, status_code=422)

    # Status-Transition prüfen (wie in server.py)
    old_key = getattr(it, "status", None)
    new_key = status.normalize_input(requested_status_key or old_key, getattr(it, "type", None)) if (requested_status_key or old_key) else None
    is_recurring = bool(getattr(it, "recurrence", None))
    ok, reason = status.validate_transition(old_key, new_key, is_recurring=is_recurring)
    if not ok:
        if is_htmx(request):
            html = templates.get_template("_alerts.html").render({"messages": [reason or "Ungültiger Status für diesen Typ."]})
            return HTMLResponse(content=html, status_code=422)
        raise HTTPException(status_code=422, detail=reason or "Ungültiger Status für diesen Typ.")

    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    private_bool = bool(int(is_private))


    # ICE-Metadaten robust validieren und speichern wie in server.py
    from domain.ice_definitions import compute_ice_score
    cur_meta = dict(getattr(it, "metadata", {}) or {})
    final_impact = None
    final_confidence = None
    final_ease = None
    final_score = None
    # Impact: integer 1-5
    if ice_impact is not None:
        ice_impact_str = (ice_impact or "").strip()
        if ice_impact_str:
            try:
                imp_val = int(ice_impact_str)
                if 1 <= imp_val <= 5:
                    final_impact = imp_val
            except ValueError:
                pass
    # Confidence: accept string label or integer, always store as string label for DB, use int for calculation
    CONFIDENCE_LABEL_TO_INT = {
        "very_low": 1, "low": 2, "medium": 3, "high": 4, "very_high": 5,
        "sehr_niedrig": 1, "niedrig": 2, "mittel": 3, "hoch": 4, "sehr_hoch": 5
    }
    CONFIDENCE_INT_TO_LABEL = {v: k for k, v in CONFIDENCE_LABEL_TO_INT.items()}
    confidence_label_for_db = None
    if ice_confidence is not None:
        ice_confidence_str = (ice_confidence or "").strip()
        if ice_confidence_str:
            if ice_confidence_str in CONFIDENCE_LABEL_TO_INT:
                final_confidence = CONFIDENCE_LABEL_TO_INT[ice_confidence_str]
                confidence_label_for_db = ice_confidence_str
            else:
                try:
                    conf_val = int(ice_confidence_str)
                    if 1 <= conf_val <= 5:
                        final_confidence = conf_val
                        confidence_label_for_db = CONFIDENCE_INT_TO_LABEL[conf_val]
                except (ValueError, KeyError):
                    pass
    # Ease: integer 1-5
    if ice_ease is not None:
        ice_ease_str = (ice_ease or "").strip()
        if ice_ease_str:
            try:
                ease_val = int(ice_ease_str)
                if 1 <= ease_val <= 5:
                    final_ease = ease_val
            except ValueError:
                pass
    # ICE-Score neu berechnen (server-side validation)
    if final_impact is not None or final_confidence is not None or final_ease is not None:
        final_score = compute_ice_score(final_impact, final_confidence, final_ease)
    # Speichern in Metadaten
    if final_impact is not None:
        cur_meta["ice_impact"] = str(final_impact)
    elif ice_impact is not None and not (ice_impact or "").strip():
        cur_meta.pop("ice_impact", None)
    if final_confidence is not None:
        cur_meta["ice_confidence"] = confidence_label_for_db
    elif ice_confidence is not None and not (ice_confidence or "").strip():
        cur_meta.pop("ice_confidence", None)
    if final_ease is not None:
        cur_meta["ice_ease"] = str(final_ease)
    elif ice_ease is not None and not (ice_ease or "").strip():
        cur_meta.pop("ice_ease", None)
    if final_score is not None:
        cur_meta["ice_score"] = str(final_score)
    elif ("ice_score" in cur_meta) and (ice_impact is not None or ice_confidence is not None or ice_ease is not None):
        # explizit löschen, wenn alle Felder leer
        cur_meta.pop("ice_score", None)
    metadata = cur_meta

    # creator und participants NICHT überschreiben, sondern aus Original übernehmen
    payload = {**it.__dict__,
               "name": name,
               "status": status_key,
               "is_private": private_bool,
               "tags": tags_list,
               "metadata": metadata}

    logger.debug(f"Vor Upsert: item_id={item_id}, name={name}, status={status_key}, is_private={private_bool}, tags={tags_list}, metadata={metadata}, creator={it.creator}, participants={it.participants}")

    if it.type == "task":
        payload["due_utc"] = _parse_local_dt(due) if due.strip() else getattr(it, "due_utc", None)
    elif it.type in ("appointment","event"):
        s_utc = _parse_local_dt(start_local) if start_local.strip() else getattr(it, "start_utc", None)
        e_utc = _parse_local_dt(end_local) if end_local.strip() else getattr(it, "end_utc", None)
        if s_utc and e_utc and e_utc < s_utc:
            e_utc = s_utc + timedelta(hours=1)
        payload["start_utc"] = s_utc
        payload["end_utc"] = e_utc
    elif it.type == "reminder":
        payload["reminder_utc"] = _parse_local_dt(due) if due.strip() else getattr(it, "reminder_utc", None)

    rrule_string, exdates_utc = _normalize_rrule_input(dtstart_local, rrule_line, exdates_local)
    payload["recurrence"] = _build_recurrence(rrule_string, exdates_utc)

    it2 = it.__class__(**payload)
    repo.upsert(it2)

    if is_htmx(request):
        # Nur Occurrence-Teil zurückgeben, damit die Seite ohne Reload aktualisiert werden kann
        win_start, win_end = now_utc(), now_utc() + timedelta(days=7)
        occs = expand_item(it2, win_start, win_end)
        return templates.TemplateResponse(request, "_occurrences.html", {"request": request, "occs": occs})
    return RedirectResponse(f"/items/{item_id}/edit", status_code=303)

@app.get("/items/{item_id}/occurrences", response_class=HTMLResponse)
def item_occurrences_partial(item_id: str, request: Request, repo: DbRepository = Depends(get_repo)):
    it = repo.get(item_id)
    if not it:
        return PlainTextResponse("Not found", status_code=404)
    win_start, win_end = now_utc(), now_utc() + timedelta(days=7)
    occs = expand_item(it, win_start, win_end)
    return templates.TemplateResponse(request, "_occurrences.html", {"request": request, "occs": occs})

@app.post("/items/{item_id}/status")
def change_status(request: Request, item_id: str, new_status: str = Form(...), repo: DbRepository = Depends(get_repo), status=Depends(get_status)):
    it = repo.get(item_id)
    if it:
        allowed = _type_allowed_status_keys(status, it.type)
        if new_status not in allowed:
            new_status = it.status
        it2 = it.__class__(**{**it.__dict__, "status": new_status})
        repo.upsert(it2)
    if is_htmx(request):
        # Schicke nur 204, damit HTMX die Zelle nicht neu lädt; alternativ könnte hier ein Partial mit neuem Dropdown kommen
        return Response(status_code=204)
    return RedirectResponse("/", status_code=303)

@app.post("/items/{item_id}/due")
def set_due(request: Request, item_id: str, due: str = Form(...), repo: DbRepository = Depends(get_repo)):
    it = repo.get(item_id)
    if not it or it.type != "task":
        return RedirectResponse("/", status_code=303)
    if not due.strip():
        return RedirectResponse("/", status_code=303)
    dt_utc = _parse_local_dt(due)
    it2 = it.__class__(**{**it.__dict__, "due_utc": dt_utc})
    repo.upsert(it2)
    if is_htmx(request):
        win_start, win_end = now_utc(), now_utc() + timedelta(days=7)
        occs = expand_item(it2, win_start, win_end)
        return templates.TemplateResponse(request, "_occurrences.html", {"request": request, "occs": occs})
    return RedirectResponse("/", status_code=303)

@app.post("/items/{item_id}/start_end")
def set_start_end(
    request: Request,
    item_id: str,
    start_local: str = Form(""),
    end_local: str = Form(""),
    repo: DbRepository = Depends(get_repo),
):
    it = repo.get(item_id)
    if not it or it.type not in ("appointment", "event"):
        return RedirectResponse("/", status_code=303)

    if not start_local.strip() and not end_local.strip():
        return RedirectResponse("/", status_code=303)

    s_utc = _parse_local_dt(start_local) if start_local.strip() else getattr(it, "start_utc", None)
    e_utc = _parse_local_dt(end_local) if end_local.strip() else getattr(it, "end_utc", None)

    if s_utc and e_utc and e_utc < s_utc:
        e_utc = s_utc + timedelta(hours=1)

    it2 = it.__class__(**{**it.__dict__, "start_utc": s_utc, "end_utc": e_utc})
    repo.upsert(it2)
    if is_htmx(request):
        win_start, win_end = now_utc(), now_utc() + timedelta(days=7)
        occs = expand_item(it2, win_start, win_end)
        return templates.TemplateResponse(request, "_occurrences.html", {"request": request, "occs": occs})
    return RedirectResponse("/", status_code=303)

@app.post("/items/{item_id}/snooze")
def snooze(request: Request, item_id: str, minutes: int = Form(10), repo: DbRepository = Depends(get_repo)):
    it = repo.get(item_id)
    if it and it.type == "reminder":
        new_ts = (it.reminder_utc or now_utc()) + timedelta(minutes=int(minutes))
        it2 = it.__class__(**{**it.__dict__, "reminder_utc": new_ts})
        repo.upsert(it2)
        if is_htmx(request):
            win_start, win_end = now_utc(), now_utc() + timedelta(days=7)
            occs = expand_item(it2, win_start, win_end)
            return templates.TemplateResponse("_occurrences.html", {"request": request, "occs": occs})
    if is_htmx(request):
        return Response(status_code=204)
    return RedirectResponse("/", status_code=303)

@app.post("/items/{item_id}/delete")
def delete_item(request: Request, item_id: str, repo: DbRepository = Depends(get_repo)):
    repo.delete(item_id)
    if is_htmx(request):
        # Entferne Zeile clientseitig durch hx-swap-oob oder 204 und ein hx-target Container-Refresh
        return hx_refresh()
    return RedirectResponse("/", status_code=303)


@app.get("/export.ics")
def export_ics(repo: DbRepository = Depends(get_repo)):
    items = repo.list_all()
    body = "BEGIN:VCALENDAR\nVERSION:2.0\n" + "\n".join(to_ics(it, alarm_min=10) for it in items) + "\nEND:VCALENDAR\n"
    return StreamingResponse(
        iter([body.encode("utf-8")]),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks.ics"}
    )

@app.get("/import", response_class=HTMLResponse)
def import_page(request: Request):
    return templates.TemplateResponse(request, "import.html", {"request": request})

@app.post("/import", response_class=HTMLResponse)
async def import_upload(request: Request, file: UploadFile = File(...), repo: DbRepository = Depends(get_repo)):
    text = (await file.read()).decode("utf-8", errors="ignore")
    creator_id = request.headers.get("X-User-Id")
    if not creator_id:
        raise HTTPException(status_code=401, detail="Creator header X-User-Id is required")

    items = import_ics(text, creator=creator_id)
    for it in items:
        if not it.id:
            it = it.__class__(**{**it.__dict__, "id": str(uuid.uuid4())})
        repo.upsert(it)
    if is_htmx(request):
        return hx_redirect("/")
    return RedirectResponse("/", status_code=303)
