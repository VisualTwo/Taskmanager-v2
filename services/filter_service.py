# services/filter_service.py
from __future__ import annotations
from typing import Iterable, List, Optional, Set, Mapping, Any
from domain.models import BaseItem


def _norm_s(s: Optional[str]) -> str:
    return (s or "").strip()


def _norm_lower(s: Optional[str]) -> str:
    return _norm_s(s).lower()


def _iter_lower(seq: Optional[Iterable[str]]) -> List[str]:
    return [ (x or "").strip().lower() for x in (seq or []) if (x or "").strip() ]


def filter_items(
    items: Iterable[BaseItem],
    *,
    text: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    types: Optional[Iterable[str]] = None,
    status_keys: Optional[Iterable[str]] = None,   # Variante 1: Liste von Status-Keys (ODER)
    include_private: bool = True,
    priority: Optional[int] = None,
    min_priority: Optional[int] = None,
    require_all_terms: bool = False,               # wenn True: alle Suchbegriffe müssen matchen
) -> List[BaseItem]:
    """
    Filtert Items anhand:
    - include_private: private Einträge ein-/ausblenden.
    - types: erlaubte Typen (ODER über die Liste).
    - status_keys: erlaubte Status-Keys (ODER über die Liste, typübergreifend).
    - tags: alle angegebenen Tags müssen im Item enthalten sein (UND).
    - text: Freitext in name, description, tags, status, type, metadata (key:value), links.
    - require_all_terms: bei True werden alle whitespace-getrennten Begriffe verlangt (UND).
    - priority: exakte Priorität 0..5.
    """
    print(f"[FILTER] Received min_priority={min_priority}")
    text_q = _norm_lower(text)
    text_terms = [t for t in text_q.split() if t] if require_all_terms and text_q else []
    tags_set: Optional[Set[str]] = set(_iter_lower(tags)) if tags else None
    type_set: Optional[Set[str]] = set(_iter_lower(types)) if types else None
    status_set: Optional[Set[str]] = set(_iter_lower(status_keys)) if status_keys else None

    # Priority robust begrenzen (0..5), sonst ignorieren
    prio_ok: Optional[int] = priority if isinstance(priority, int) and 0 <= priority <= 5 else None

    def build_haystack(it: BaseItem) -> str:
        name = _norm_lower(getattr(it, "name", ""))
        desc = _norm_lower(getattr(it, "description", ""))
        tags_join = " ".join(_iter_lower(getattr(it, "tags", ())))
        # metadata als key:value Paare
        meta: Mapping[str, Any] = getattr(it, "metadata", {}) or {}
        meta_join = " ".join(f"{_norm_lower(k)}:{_norm_lower(str(v))}" for k, v in meta.items())
        # Links optional in Freitextsuche aufnehmen
        links = getattr(it, "links", ()) or ()
        links_join = " ".join(_iter_lower(links))
        return " ".join([name, desc, tags_join, meta_join, links_join]).strip()

    def match(it: BaseItem) -> bool:
        # Privatsphäre
        if not include_private and bool(getattr(it, "is_private", False)):
            return False

        # Typ (ODER über Liste)
        if type_set:
            if _norm_lower(getattr(it, "type", "")) not in type_set:
                return False

        # Status (ODER über Liste, typübergreifend)
        if status_set:
            if _norm_lower(getattr(it, "status", "")) not in status_set:
                return False

        # Tags (UND)
        if tags_set:
            item_tags = set(_iter_lower(getattr(it, "tags", ())))
            if not tags_set.issubset(item_tags):
                return False

        # Priorität (exakte Übereinstimmung)
        if prio_ok is not None:
            item_prio = getattr(it, "priority", None)
            if item_prio is None or item_prio != prio_ok:
                return False
        
        # Mindestpriorität
        if min_priority is not None:
            item_prio = getattr(it, "priority", None)
            print(f"[FILTER] Item {getattr(it, 'name', '?')}: prio={item_prio}, min={min_priority}")

            if item_prio is not None and item_prio < min_priority:
                print(f"[FILTER] → FILTERED OUT (too low)")
                return False

        # Freitext
        if text_q:
            hay = build_haystack(it)
            if require_all_terms:
                for term in text_terms:
                    if term not in hay:
                        return False
            else:
                if text_q not in hay:
                    return False

        return True

    result = [it for it in items if match(it)]
    print(f"[FILTER] Returned {len(result)} items")
    return result
