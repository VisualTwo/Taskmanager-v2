"""
ICE Prioritization Framework – Structured Impact, Confidence, Ease definitions.

Impact: 1-10 (natural numbers)
Confidence: 5 predefined levels (very_low=0.1, low=0.3, medium=0.5, high=0.7, very_high=0.9)
Ease: 1-10 (natural numbers)
Score: Impact × Confidence × Ease (float, rounded to 2 decimals)
"""

from typing import Dict, Tuple

# ============================================================================
# IMPACT: Auswirkungen auf Ziele / Geschäft (1-10)
# ============================================================================
IMPACT_LEVELS = {
    1: {"label": "Minimal", "desc": "Kaum messbarer Einfluss"},
    2: {"label": "Sehr gering", "desc": "Sehr kleiner positiver Effekt"},
    3: {"label": "Gering", "desc": "Kleiner, aber erkennbarer Effekt"},
    4: {"label": "Niedrig", "desc": "Moderate positive Auswirkung"},
    5: {"label": "Mittel", "desc": "Deutlicher positiver Einfluss"},
    6: {"label": "Erhöht", "desc": "Guter positiver Effekt"},
    7: {"label": "Hoch", "desc": "Großer positiver Einfluss"},
    8: {"label": "Sehr hoch", "desc": "Sehr großer positiver Effekt"},
    9: {"label": "Kritisch", "desc": "Kritischer Einfluss auf Ziele"},
    10: {"label": "Transformativ", "desc": "Grundlegender positiver Wandel"},
}

# ============================================================================
# CONFIDENCE: Sicherheit der Einschätzung (Enum mit festen Werten)
# ============================================================================
CONFIDENCE_LEVELS = {
    "very_low": {"value": 0.1, "label": "Sehr niedrig (10%)", "desc": "Hochgradig spekulativ"},
    "low": {"value": 0.3, "label": "Niedrig (30%)", "desc": "Begrenzte Gewissheit"},
    "medium": {"value": 0.5, "label": "Mittel (50%)", "desc": "Moderate Gewissheit"},
    "high": {"value": 0.7, "label": "Hoch (70%)", "desc": "Hohe Gewissheit"},
    "very_high": {"value": 0.9, "label": "Sehr hoch (90%)", "desc": "Sehr großes Vertrauen"},
}

# ============================================================================
# EASE: Aufwand / Umsetzungsleichtigkeit (1-10, invers zur Komplexität)
# ============================================================================
EASE_LEVELS = {
    1: {"label": "Extrem schwierig", "desc": "Sehr großer Aufwand"},
    2: {"label": "Sehr schwierig", "desc": "Enormer Aufwand"},
    3: {"label": "Schwierig", "desc": "Großer Aufwand"},
    4: {"label": "Schwer", "desc": "Erheblicher Aufwand"},
    5: {"label": "Moderat", "desc": "Moderater Aufwand"},
    6: {"label": "Machbar", "desc": "Handhabbarer Aufwand"},
    7: {"label": "Leicht", "desc": "Relativ gering"},
    8: {"label": "Sehr leicht", "desc": "Kleiner Aufwand"},
    9: {"label": "Trivial", "desc": "Minimaler Aufwand"},
    10: {"label": "Trivial+", "desc": "Praktisch kostenlos"},
}

def get_confidence_value(key: str) -> float:
    """Map confidence key to numeric value."""
    conf = CONFIDENCE_LEVELS.get(key)
    return conf["value"] if conf else 0.5  # Default to medium


def is_valid_confidence_key(key: str) -> bool:
    """Check if a given key is a valid confidence level."""
    if key is None:
        return False
    return str(key).strip() in CONFIDENCE_LEVELS


def get_confidence_key_from_value(value: float) -> str:
    """Find closest confidence key for a given value."""
    if value is None:
        return "medium"
    for key, conf in CONFIDENCE_LEVELS.items():
        if abs(conf["value"] - value) < 0.05:  # Allow small tolerance
            return key
    # Return closest
    closest = min(CONFIDENCE_LEVELS.items(), key=lambda x: abs(x[1]["value"] - value))
    return closest[0]


def compute_ice_score(impact: int, confidence_key: str, ease: int) -> float:
    """
    Compute ICE score from impact (int), confidence (key), and ease (int).
    Handles None values gracefully by treating them as 0.
    """
    try:
        imp = int(impact) if impact else 0
        conf_value = get_confidence_value(confidence_key if confidence_key else "medium")
        eas = int(ease) if ease else 0
        raw = imp * conf_value * eas
        return round(raw, 2)
    except (ValueError, TypeError):
        return 0.0


def ice_summary(impact: int, confidence_key: str, ease: int) -> Dict:
    """Return structured ICE summary with labels and score."""
    score = compute_ice_score(impact, confidence_key, ease)
    return {
        "impact": impact,
        "impact_label": IMPACT_LEVELS.get(impact, {}).get("label", "—"),
        "confidence_key": confidence_key,
        "confidence_label": CONFIDENCE_LEVELS.get(confidence_key, {}).get("label", "—"),
        "ease": ease,
        "ease_label": EASE_LEVELS.get(ease, {}).get("label", "—"),
        "score": score,
    }
