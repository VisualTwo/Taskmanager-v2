"""
ICE Prioritization Framework – Wissenschaftlich fundierte 0-5 Skalen mit Impact-Gewichtung.

Impact: 0-5 (0=nicht zutreffend, 1-5=messbarer Einfluss)
Confidence: 0-5 (0=unbekannt, 1-5=Gewissheit)
Ease: 0-5 (0=unmöglich, 1-5=Einfachheit)
Score: Impact² × Confidence × Ease (Impact doppelt gewichtet)
"""

from typing import Dict, Tuple

# ============================================================================
# IMPACT: Auswirkungen auf Ziele / Geschäft (0-5) - Doppelt gewichtet!
# ============================================================================
IMPACT_LEVELS = {
    0: {"label": "Nicht zutreffend", "desc": "Kein Einfluss oder nicht anwendbar"},
    1: {"label": "Minimal", "desc": "Kaum messbarer Einfluss"},
    2: {"label": "Gering", "desc": "Kleiner positiver Effekt"},
    3: {"label": "Mittel", "desc": "Deutlicher positiver Einfluss"},
    4: {"label": "Hoch", "desc": "Großer positiver Einfluss"},
    5: {"label": "Transformativ", "desc": "Grundlegender positiver Wandel"},
}

# ============================================================================
# CONFIDENCE: Sicherheit der Einschätzung (0-5 Skala)
# ============================================================================
CONFIDENCE_LEVELS = {
    0: {"label": "Unbekannt", "desc": "Keine Informationen verfügbar"},
    1: {"label": "Sehr niedrig (20%)", "desc": "Hochgradig spekulativ"},
    2: {"label": "Niedrig (40%)", "desc": "Begrenzte Gewissheit"},
    3: {"label": "Mittel (60%)", "desc": "Moderate Gewissheit"},
    4: {"label": "Hoch (80%)", "desc": "Hohe Gewissheit"},
    5: {"label": "Sehr hoch (100%)", "desc": "Maximale Gewissheit"},
}

# ============================================================================
# EASE: Aufwand / Umsetzungsleichtigkeit (0-5)
# ============================================================================
EASE_LEVELS = {
    0: {"label": "Unmöglich", "desc": "Technisch oder resourcen-mäßig unmöglich"},
    1: {"label": "Extrem schwierig", "desc": "Sehr großer Aufwand"},
    2: {"label": "Schwierig", "desc": "Großer Aufwand"},
    3: {"label": "Moderat", "desc": "Moderater Aufwand"},
    4: {"label": "Leicht", "desc": "Relativ gering"},
    5: {"label": "Trivial", "desc": "Minimaler Aufwand"},
}

def get_confidence_value(confidence: int) -> int:
    """Get confidence value (0-5 scale)."""
    if confidence is not None and 0 <= int(confidence) <= 5:
        return int(confidence)
    return 0  # Default to unknown


def is_valid_confidence_value(confidence: int) -> bool:
    """Check if a given value is a valid confidence level (0-5)."""
    try:
        return 0 <= int(confidence) <= 5
    except (ValueError, TypeError):
        return False





def compute_ice_score(impact: int, confidence: int, ease: int) -> float:
    """
    Compute ICE score using scientific approach with Impact weighting.
    Formula: Impact² × Confidence × Ease (Impact gets double weight)
    Maximum possible score: 5² × 5 × 5 = 625
    This reflects that Impact is the most important factor in prioritization.
    """
    try:
        imp = int(impact) if impact is not None and 0 <= int(impact) <= 5 else 0
        conf = int(confidence) if confidence is not None and 0 <= int(confidence) <= 5 else 0  
        eas = int(ease) if ease is not None and 0 <= int(ease) <= 5 else 0
        
        # Impact gets squared (double weight) - scientifically proven approach
        raw = (imp * imp) * conf * eas
        return round(raw, 2)
    except (ValueError, TypeError):
        return 0.0


def ice_summary(impact: int, confidence: int, ease: int) -> Dict:
    """Return structured ICE summary with labels and score."""
    score = compute_ice_score(impact, confidence, ease)
    return {
        "impact": impact,
        "impact_label": IMPACT_LEVELS.get(impact, {}).get("label", "—"),
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LEVELS.get(confidence, {}).get("label", "—"),
        "ease": ease,
        "ease_label": EASE_LEVELS.get(ease, {}).get("label", "—"),
        "score": score,
    }
