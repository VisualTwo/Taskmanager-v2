import functools
from datetime import datetime, timezone, date, timedelta, time, tzinfo # tzinfo importiert
from dateutil import parser as dateutil_parser
from typing import Optional, Union, cast
import logging

# Zeitzonen-Setup
_local_tz: Optional[tzinfo] = None  
_uses_pytz_local = False

try:  
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  
    _zoneinfo_available = True  
except ImportError:  
    _zoneinfo_available = False  
    logging.debug("zoneinfo Modul nicht verfügbar (Python < 3.9?).")  

try:  
    import pytz  
    _pytz_available = True  
except ImportError:  
    _pytz_available = False  
    logging.debug("pytz Modul nicht verfügbar.")  

try:  
    import tzlocal  
    _tzlocal_available = True  
except ImportError:  
    _tzlocal_available = False  
    logging.debug("tzlocal Modul nicht verfügbar.")  

if _tzlocal_available:  
    try:  
        _local_tz_candidate = tzlocal.get_localzone()  
        # Sicherstellen, dass es ein tzinfo-Objekt ist  
        if isinstance(_local_tz_candidate, tzinfo):  
            _local_tz = _local_tz_candidate  
            if _pytz_available and isinstance(_local_tz, pytz.tzinfo.BaseTzInfo):  
                _uses_pytz_local = True  
                logging.info(f"Lokale Zeitzone via tzlocal (pytz Backend) ermittelt: {_local_tz.zone}")  
            else: # ZoneInfo oder anderes tzinfo kompatibles Objekt  
                _uses_pytz_local = False  
                tz_name = getattr(_local_tz, 'key', str(_local_tz)) # .key für ZoneInfo  
                logging.info(f"Lokale Zeitzone via tzlocal (zoneinfo/datetime Backend) ermittelt: {tz_name}")  
        else:  
            logging.warning(f"tzlocal.get_localzone() gab unerwarteten Typ zurück: {type(_local_tz_candidate)}. Versuche Fallback.")  
            _local_tz = None  
    except Exception as e:  
        logging.warning(f"Fehler beim Ermitteln der lokalen Zeitzone via tzlocal: {e}. Versuche Fallback.")  
        _local_tz = None  

if _local_tz is None:  
    fallback_tz_name = 'Europe/Berlin'  
    if _zoneinfo_available:  
        try:  
            _local_tz = ZoneInfo(fallback_tz_name)  
            _uses_pytz_local = False  
            logging.info(f"Verwende Fallback-Zeitzone (zoneinfo): {fallback_tz_name}")  
        except ZoneInfoNotFoundError:  
            logging.warning(f"Fallback-Zeitzone '{fallback_tz_name}' (zoneinfo) nicht gefunden.")  
            _local_tz = None # explizit None setzen für nächsten Check  

    if _local_tz is None and _pytz_available: # Nur wenn zoneinfo fehlschlug oder nicht da war  
        try:  
            _local_tz = pytz.timezone(fallback_tz_name)  
            _uses_pytz_local = True # Da wir pytz.timezone verwenden  
            logging.info(f"Verwende Fallback-Zeitzone (pytz): {fallback_tz_name}")  
        except pytz.UnknownTimeZoneError:  
            logging.warning(f"Fallback-Zeitzone '{fallback_tz_name}' (pytz) nicht gefunden.")  
            _local_tz = None # explizit None setzen  

if _local_tz is None:  
    logging.error("Konnte keine lokale Zeitzone ermitteln. Verwende UTC als Fallback für lokale Zeit!")  
    _local_tz = timezone.utc  
    _uses_pytz_local = False # Da timezone.utc kein pytz-Objekt ist  

# Konstanten für einfachen Zugriff exportieren  
LOCAL_TIMEZONE: tzinfo = _local_tz # Ist jetzt definitiv tzinfo, nicht Optional[tzinfo]  
UTC: tzinfo = timezone.utc

# Helper-Funktionen

def _make_aware_with_specific_tz(dt_naive: datetime, tz_to_apply: tzinfo) -> Optional[datetime]:  
    """  
    Macht ein naives datetime-Objekt mit der spezifisch übergebenen Zeitzone aware.  
    Behandelt pytz-Besonderheiten (localize) vs. standard (replace).  
    """  
    if not isinstance(dt_naive, datetime) or dt_naive.tzinfo is not None:  
        logging.error(f"_make_aware_with_specific_tz erwartet ein naives datetime, erhielt: {dt_naive}")  
        return None  

    try:  
        # Prüfen, ob die *zu applizierende* Zone pytz ist  
        is_pytz_zone = _pytz_available and isinstance(tz_to_apply, cast(type, pytz.tzinfo.BaseTzInfo))  

        if is_pytz_zone:  
            # Sicherstellen, dass tz_to_apply die Methoden von pytz.tzinfo.BaseTzInfo hat  
            pytz_tz_to_apply = cast(pytz.tzinfo.BaseTzInfo, tz_to_apply)  
            try:  
                return pytz_tz_to_apply.localize(dt_naive, is_dst=None)  
            except pytz.AmbiguousTimeError:  
                logging.warning(f"Zeit '{dt_naive}' ist mehrdeutig in Zone '{pytz_tz_to_apply}'. Wähle Standard (is_dst=False).")  
                return pytz_tz_to_apply.localize(dt_naive, is_dst=False)  
            except pytz.NonExistentTimeError:  
                logging.error(f"Zeit '{dt_naive}' existiert nicht in Zone '{pytz_tz_to_apply}'.")  
                return None  
        else: # ZoneInfo, timezone.utc etc.  
            return dt_naive.replace(tzinfo=tz_to_apply)  
    except Exception as e:  
        logging.error(f"Fehler in _make_aware_with_specific_tz für {dt_naive} mit Zone {tz_to_apply}: {e}", exc_info=True)  
        return None

def localize_naive(dt_naive: datetime) -> Optional[datetime]:  
    """  
    Macht ein naives datetime-Objekt mithilfe der ermittelten LOCAL_TIMEZONE aware.  
    """  
    if not isinstance(dt_naive, datetime) or dt_naive.tzinfo is not None:  
        logging.error(f"localize_naive erwartet ein naives datetime, erhielt aber: {dt_naive} ({type(dt_naive)})")  
        return None  
    # LOCAL_TIMEZONE ist jetzt nie None  
    return _make_aware_with_specific_tz(dt_naive, LOCAL_TIMEZONE)

def ensure_aware(dt: datetime, assume_tz: Optional[tzinfo] = None) -> Optional[datetime]:  
    """  
    Stellt sicher, dass ein datetime-Objekt timezone-aware ist.  
    Naive Objekte werden mit der angegebenen Zeitzone (Standard: lokale TZ) aware gemacht.  
    """  
    if not isinstance(dt, datetime):  
        logging.error(f"ensure_aware erwartet datetime, erhielt aber: {type(dt)}")  
        return None  

    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:  
        return dt # Bereits aware  

    resolved_tz = assume_tz if assume_tz is not None else LOCAL_TIMEZONE  
    # resolved_tz wird hier nie None sein, da LOCAL_TIMEZONE immer gesetzt ist.  

    return _make_aware_with_specific_tz(dt, resolved_tz)

def local_to_utc(local_dt: Optional[datetime]) -> Optional[datetime]:  
    """  
    Konvertiert ein lokales datetime (naiv oder aware) sicher in UTC.  
    Naive Objekte werden zuerst mit der lokalen Zeitzone aware gemacht.  
    Wenn das Eingabeobjekt bereits aware und UTC ist, wird es direkt zurückgegeben.  
    """  
    if local_dt is None:  
        logging.debug("<<< local_to_utc: Output = None (Input was None)")  
        return None  

    logging.debug(f">>> local_to_utc: Input = {local_dt.isoformat()} (Type: {type(local_dt)}, tz: {local_dt.tzinfo})")  

    # Optimierung: Wenn bereits aware und UTC, direkt zurückgeben  
    if local_dt.tzinfo is not None and local_dt.tzinfo.utcoffset(local_dt) == timedelta(0):  
        logging.debug("<<< local_to_utc: Input ist bereits UTC. Direkte Rückgabe.")  
        return local_dt  

    # Stelle sicher, dass es aware ist und die lokale Zeitzone hat (wenn es nicht schon UTC war)  
    aware_local_dt = ensure_aware(local_dt, assume_tz=LOCAL_TIMEZONE)  

    if aware_local_dt is None:  
        logging.error(f"local_to_utc: Konnte Eingabe {local_dt} nicht aware machen.")  
        logging.debug("<<< local_to_utc: Output = None (ensure_aware failed)")  
        return None  

    try:  
        utc_dt = aware_local_dt.astimezone(UTC)  
        logging.debug(f"<<< local_to_utc: Output = {utc_dt.isoformat()} (tz: {utc_dt.tzinfo})")  
        return utc_dt  
    except Exception as e:  
        logging.error(f"local_to_utc: Fehler bei Konvertierung von {aware_local_dt} zu UTC: {e}", exc_info=True)  
        logging.debug("<<< local_to_utc: Output = None (Conversion failed)")  
        return None  

def utc_to_local(utc_dt: Optional[datetime]) -> Optional[datetime]:  
    """  
    Konvertiert ein UTC datetime (naiv oder aware) sicher in die lokale Zeitzone.  
    Naive Objekte werden als UTC interpretiert.  
    """  
    if utc_dt is None:  
        return None  

    # Sicherstellen, dass utc_dt aware und UTC ist  
    if not hasattr(utc_dt, 'tzinfo') or utc_dt.tzinfo is None:  
        logging.debug(f"utc_to_local: Input '{utc_dt}' war naiv. Interpretiere als UTC.")  
        utc_dt = utc_dt.replace(tzinfo=UTC)  
    elif utc_dt.tzinfo.utcoffset(utc_dt) != timedelta(0):  
         logging.warning(f"utc_to_local: Input '{utc_dt}' war aware, aber nicht UTC ({utc_dt.tzinfo}). Konvertiere zu UTC.")  
         utc_dt = utc_dt.astimezone(UTC)  
    # Nach diesem Block ist utc_dt garantiert aware und UTC.  

    # LOCAL_TIMEZONE ist nie None  
    try:  
        local_dt = utc_dt.astimezone(LOCAL_TIMEZONE)  
        return local_dt  
    except Exception as e:  
        logging.error(f"utc_to_local: Fehler bei Konvertierung von {utc_dt} zu lokal ({LOCAL_TIMEZONE}): {e}", exc_info=True)  
        return None  

@functools.lru_cache(maxsize=1024) # Cache für die letzten 1024 einzigartigen Zeitstempel-Strings
def parse_db_datetime(datetime_str: Optional[str]) -> Optional[datetime]:  
    """  
    Parst einen Datums-/Zeit-String aus der Datenbank.  
    Erwartet entweder ISO 8601 Format (mit Offset) oder einen naiven String  
    im Format '%Y-%m-%d %H:%M:%S', der UTC repräsentiert.  
    Gibt ein aware datetime-Objekt in UTC zurück oder None bei Fehler/None-Input.  
    """  
    if not datetime_str:  
        return None  

    try:
        # Versuch 1: Mit dateutil.parser (behandelt Offsets und verschiedene Formate robust)  
        # dateutil.parser ist bereits am Anfang importiert  
        parsed_dt = dateutil_parser.parse(datetime_str)  

        if parsed_dt.tzinfo is None:
            logging.debug(f"parse_db_datetime: Naiven DB-String '{datetime_str}' geparst. Interpretiere als UTC.")  
            return parsed_dt.replace(tzinfo=UTC)  
        else:
            logging.debug(f"parse_db_datetime: Aware DB-String '{datetime_str}' geparst. Konvertiere zu UTC (falls nicht schon).")  
            return parsed_dt.astimezone(UTC)

    except Exception as e: # Andere Fehler mit dateutil  
        logging.error(f"parse_db_datetime: Fehler beim Parsen des DB-Strings '{datetime_str}': {e}", exc_info=True)  
        return None

def parse_ics_datetime_to_utc(v) -> datetime | None:
    """
    Konvertiert icalendar vDDDTypes (DATE, DATE-TIME, ggf. TZ-aware) nach UTC.
    Unterstützt:
      - date (ganztägig): interpretiert als 00:00 UTC am jeweiligen Tag
      - naive datetime: als UTC interpretiert
      - tz-aware datetime: nach UTC konvertiert
      - icalendar Prop mit .dt Attribut
    """
    if v is None:
        return None

    # icalendar-Felder besitzen oft das .dt-Attribut mit Python date/datetime
    if hasattr(v, "dt"):
        v = v.dt

    # Ganztägig (reines date-Objekt)
    if isinstance(v, datetime) is False and hasattr(v, "year") and hasattr(v, "month") and hasattr(v, "day"):
        # Behandle als UTC Mitternacht
        return datetime(int(v.year), int(v.month), int(v.day), 0, 0, 0, tzinfo=ZoneInfo("UTC"))

    if isinstance(v, datetime):
        if v.tzinfo is None:
            # naive -> als UTC interpretieren
            return v.replace(tzinfo=ZoneInfo("UTC"))
        # tz-aware -> nach UTC
        return v.astimezone(ZoneInfo("UTC"))

    # Fallback: Stringformate wie 20250123T101500Z
    try:
        s = str(v).strip()
        if s.endswith("Z"):
            # UTC
            dt = datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
            return dt
        # YYYYMMDD ohne Zeit -> als 00:00 UTC
        if len(s) == 8 and s.isdigit():
            dt = datetime.strptime(s, "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))
            return dt
        # Versuche weitere Varianten mit Offset (einfacher Fallback: als UTC interpretieren)
        try:
            # 2025-01-23T10:15:00
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(ZoneInfo("UTC"))
        except Exception:
            pass
    except Exception:
        pass
    return None

def format_db_datetime(dt: Optional[datetime]) -> Optional[str]:  
    """  
    Formatiert ein datetime-Objekt (aware oder naiv) als UTC-String  
    im ISO 8601 Format (YYYY-MM-DDTHH:MM:SS.ffffff+ZZ:ZZ) für die Speicherung in der DB.  
    Naive Objekte werden als LOKALE Zeit interpretiert und nach UTC konvertiert.  
    """  
    if dt is None:  
        return None  

    # Sicherstellen, dass wir ein aware UTC datetime haben  
    # local_to_utc ist hier passend, da dt von verschiedenen Quellen kommen kann  
    # (z.B. eine lokale Benutzereingabe oder ein bereits aware datetime)  
    utc_dt = local_to_utc(dt) # Diese Funktion wandelt naive dt (als lokal angenommen) zu UTC um  

    if utc_dt is None:  
        logging.error(f"format_db_datetime: Konnte Eingabe {dt} nicht nach UTC konvertieren.")  
        return None  

    # datetime.isoformat() erzeugt das gewünschte Format
    formatted_str = utc_dt.isoformat()  
    logging.debug(f"<<< format_db_datetime: Output ISO String = '{formatted_str}'")  
    return formatted_str

def parse_date(date_str: Optional[str]) -> Optional[date]:  
    """Parst ein Datum (ohne Zeit) aus einem String ('%Y-%m-%d' oder '%d.%m.%Y')."""  
    if not date_str:  
        return None  
    try:  
        return date.fromisoformat(date_str) # YYYY-MM-DD  
    except (ValueError, TypeError):  
        try:  
            return datetime.strptime(date_str, "%d.%m.%Y").date()  
        except (ValueError, TypeError):  
            logging.warning(f"Konnte Datum '{date_str}' nicht parsen (Format YYYY-MM-DD oder DD.MM.YYYY erwartet).")  
            return None  

def parse_datetime(datetime_input: Union[str, datetime, date, None]) -> Optional[datetime]:
    """  
    Parst einen Datetime-String oder konvertiert ein date/datetime-Objekt  
    in ein aware UTC datetime Objekt.  
    Naive geparste/übergebene Zeiten werden als LOKAL interpretiert.  
    """  
    if datetime_input is None:  
        return None
    
    dt_to_convert: Optional[datetime] = None  

    if isinstance(datetime_input, str):  
        try:  
            # Nur Strings werden mit dateutil.parser geparst  
            dt_to_convert = dateutil_parser.parse(datetime_input)  
        except (ValueError, TypeError) as e: # TypeError kann von parse kommen, wenn der String sehr ungewöhnlich ist  
            logging.warning(f"parse_datetime: dateutil.parser konnte String '{datetime_input}' nicht parsen: {e}")  
            return None  
        except OverflowError as e: # Für Daten außerhalb des gültigen Bereichs  
            logging.warning(f"parse_datetime: Datum außerhalb des gültigen Bereichs für String '{datetime_input}': {e}")  
            return None
        except ImportError as e:  
                logging.error(f"parse_datetime: ImportError während des Parsens von '{datetime_input}': {e}", exc_info=True)  
                return None  
        except Exception as e_parse: # Fängt andere unerwartete Fehler spezifisch vom Parsen  
            logging.error(f"parse_datetime: Unerwarteter Fehler beim Parsen des Strings '{datetime_input}': {e_parse}", exc_info=True)  
            return None  
    elif isinstance(datetime_input, datetime):  
        # Wenn es bereits ein datetime-Objekt ist, direkt verwenden  
        dt_to_convert = datetime_input  
    elif isinstance(datetime_input, date):  
        # Wenn es ein date-Objekt ist, zu datetime konvertieren (Mitternacht)  
        # Dieses naive datetime wird von local_to_utc als lokale Zeit interpretiert  
        dt_to_convert = datetime.combine(datetime_input, time.min)  
    else:  
        # Behandelt alle anderen unerwarteten Typen  
        logging.warning(f"parse_datetime: Ungültiger Input-Typ '{type(datetime_input)}' für Wert '{datetime_input}'. Erwartet str, datetime oder date.")  
        return None
    
    if dt_to_convert is None:  
        # Dieser Log-Eintrag sollte nur erscheinen, wenn es einen Logikfehler oben gibt.  
        logging.error(f"parse_datetime: dt_to_convert ist unerwartet None nach Typüberprüfung für Input '{datetime_input}'.")  
        return None  

    # Konvertiere das resultierende datetime-Objekt (dt_to_convert) nach UTC  
    try:  
        utc_dt = local_to_utc(dt_to_convert)  
        return utc_dt  
    except Exception as e_utc:  
        logging.error(f"parse_datetime: Fehler bei der Konvertierung nach UTC für '{dt_to_convert}': {e_utc}", exc_info=True)  
        return None

def format_display_datetime(dt_utc: Optional[datetime], fmt: str = "%d.%m.%Y %H:%M") -> str:  
    """  
    Formatiert ein UTC datetime für die Anzeige in der lokalen Zeitzone.  
    Args:  
        dt_utc: Das aware UTC datetime Objekt oder ein naives Objekt (wird als UTC angenommen).  
        fmt: Das gewünschte Ausgabeformat (strftime-Syntax).  
    Returns:  
        Der formatierte String oder "" bei Fehlern/None-Input.  
    """  
    if dt_utc is None:  
        return ""  

    local_dt = utc_to_local(dt_utc)  

    if local_dt is None:  
        # Konvertierung zu lokal fehlgeschlagen. Log wurde in utc_to_local geschrieben.  
        # Versuche, die Eingabe zumindest als UTC darzustellen.  
        # Stelle sicher, dass dt_utc aware und UTC ist (falls es naiv als UTC reinkam)  
        aware_utc_dt = ensure_aware(dt_utc, assume_tz=UTC)  

        if aware_utc_dt:  
            try:  
                return f"{aware_utc_dt.strftime(fmt)} (UTC)"  
            except Exception as e:  
                logging.error(f"Fehler beim Formatieren des UTC Fallbacks {aware_utc_dt}: {e}")  
                return "Formatfehler (UTC)"  
        else:  
            logging.warning(f"format_display_datetime: Konnte Eingabe {dt_utc} weder zu lokal noch zu aware UTC konvertieren.")  
            return "Ungültiges Datum"  
    try:  
        return local_dt.strftime(fmt)  
    except Exception as e:  
        logging.error(f"Fehler beim Formatieren von lokalem datetime {local_dt} mit Format '{fmt}': {e}", exc_info=True)  
        return "Formatierungsfehler"  

def ensure_utc(dt: Union[datetime, date, None]) -> Optional[datetime]:  
    """  
    Stellt sicher, dass ein datetime oder date Objekt als aware UTC datetime zurückgegeben wird.  
    - `date`-Objekte werden zu `datetime` (00:00:00) konvertiert.  
    - Naive `datetime`-Objekte werden als LOKALE Zeit interpretiert und nach UTC konvertiert.  
    - Aware `datetime`-Objekte werden nach UTC konvertiert (falls nicht schon UTC).  
    """  
    logging.debug(f">>> ensure_utc: Input = {repr(dt)} (Type: {type(dt)})")  
    if dt is None:  
        return None  

    dt_datetime: datetime  
    if isinstance(dt, date) and not isinstance(dt, datetime):  
        logging.debug(f"ensure_utc: Input war date, konvertiere zu datetime (00:00:00 lokal): {dt}")  
        dt_datetime = datetime.combine(dt, time.min) # Wird als naiv behandelt, dann von local_to_utc als lokal interpretiert  
    elif isinstance(dt, datetime):  
        dt_datetime = dt  
    else:  
        logging.error(f"ensure_utc erwartet datetime oder date, erhielt aber: {type(dt)}")  
        return None
    logging.debug(f"ensure_utc: Rufe local_to_utc auf mit: {repr(dt_datetime)} (Type: {type(dt_datetime)})")  
    return local_to_utc(dt_datetime)

def add_minutes(dt: datetime, minutes: int) -> Optional[datetime]:
    """Fügt Minuten zu einem datetime hinzu."""
    if not isinstance(dt, datetime):
        logging.error(f"add_minutes erwartet datetime, erhielt {type(dt)}")
        return None
    try:
        return dt + timedelta(minutes=minutes)
    except OverflowError:
        logging.error(f"Fehler (Overflow) beim Addieren von {minutes} Minuten zu {dt}")
        return None

def start_of_day(dt: datetime, target_tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """
    Gibt den Beginn des Tages (00:00:00) für ein datetime-Objekt
    in der angegebenen Ziel-Zeitzone zurück. Standard ist die lokale Zeitzone.
    """
    if not isinstance(dt, datetime): 
        return None
    resolved_tz = target_tz if target_tz is not None else LOCAL_TIMEZONE
    if resolved_tz is None:
        logging.error("Keine gültige Zeitzone für start_of_day verfügbar.")
        return None

    try:
        dt_aware = ensure_aware(dt, assume_tz=LOCAL_TIMEZONE) # Eingabe als lokal annehmen, wenn naiv
        if dt_aware is None: 
            return None
        dt_in_target_tz = dt_aware.astimezone(resolved_tz)
        start = dt_in_target_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        return start
    except Exception as e:
        logging.error(f"Fehler in start_of_day für {dt} in Zone {resolved_tz}: {e}", exc_info=True)
        return None

def end_of_day(dt: datetime, target_tz: Optional[tzinfo] = None) -> Optional[datetime]:
    """
    Gibt das Ende des Tages (23:59:59.999999) für ein datetime-Objekt
    in der angegebenen Ziel-Zeitzone zurück. Standard ist die lokale Zeitzone.
    """
    if not isinstance(dt, datetime): 
        return None
    resolved_tz = target_tz if target_tz is not None else LOCAL_TIMEZONE
    if resolved_tz is None:
        logging.error("Keine gültige Zeitzone für end_of_day verfügbar.")
        return None
    try:
        dt_aware = ensure_aware(dt, assume_tz=LOCAL_TIMEZONE) # Eingabe als lokal annehmen, wenn naiv
        if dt_aware is None: 
            return None
        dt_in_target_tz = dt_aware.astimezone(resolved_tz)
        end = dt_in_target_tz.replace(hour=23, minute=59, second=59, microsecond=999999)
        return end
    except Exception as e:
        logging.error(f"Fehler in end_of_day für {dt} in Zone {resolved_tz}: {e}", exc_info=True)
        return None

def today_local() -> Optional[datetime]:
    """Gibt das aktuelle Datum/Zeit als aware datetime in lokaler Zeitzone zurück."""
    if LOCAL_TIMEZONE is None:
        logging.error("LOCAL_TIMEZONE nicht initialisiert in today_local.")
        return None
    try:
        return datetime.now(LOCAL_TIMEZONE)
    except Exception as e:
        logging.error(f"Fehler beim Holen der lokalen Zeit ({LOCAL_TIMEZONE}): {e}", exc_info=True)
        return None

def now_utc() -> datetime:
    """Gibt das aktuelle UTC datetime zurück."""
    return datetime.now(UTC)

def strip_timezone(dt: datetime) -> Optional[datetime]:
    """Entfernt die Zeitzonen-Info von einem datetime und gibt ein naives Objekt zurück."""
    if not isinstance(dt, datetime):
        return None
    return dt.replace(tzinfo=None)

def is_past(dt_to_check: Optional[datetime]) -> bool:
    """
    Prüft, ob das gegebene datetime (aware oder naiv) in der Vergangenheit liegt.
    Naive Objekte werden als LOKALE Zeit interpretiert.
    """
    if dt_to_check is None:
        return False
    dt_utc = ensure_utc(dt_to_check)
    if dt_utc is None:
         logging.warning(f"is_past: Konnte {dt_to_check} nicht sicher nach UTC konvertieren. Gehe von 'nicht vergangen' aus.")
         return False
    return dt_utc < now_utc()

def format_local_weekday(dt: Optional[datetime], fmt: str = "%a, %d.%m.%Y %H:%M") -> str:
    if not dt: return ""
    try:
        s = dt.astimezone(ZoneInfo("Europe/Berlin")).strftime(fmt)
        # Eng -> De Kurzformen
        return (s.replace("Mon", "Mo").replace("Tue", "Di").replace("Wed", "Mi")
                 .replace("Thu", "Do").replace("Fri", "Fr").replace("Sat", "Sa").replace("Sun", "So"))
    except Exception:
        return ""
