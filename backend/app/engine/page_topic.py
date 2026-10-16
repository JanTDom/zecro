"""Small, editable style nudges for the subject of one page.

The publication's DNA remains the base. These vectors affect exploration,
while facts, source text and the hard quality gate remain independent.
"""
from __future__ import annotations

from ..models.schemas import StyleBlend

# (headline energy, geometric freedom, photographic share) relative to DNA.
PAGE_TOPIC_DELTAS: dict[str, tuple[float, float, float]] = {
    "general": (0.00, 0.00, 0.00),
    "events": (0.06, 0.08, 0.14),
    "politics": (-0.06, -0.04, -0.08),
    "science": (-0.04, 0.06, -0.02),
    "celebrities": (0.14, 0.08, 0.18),
    "economy": (-0.05, -0.02, -0.10),
    "sports": (0.10, 0.08, 0.16),
    "culture": (0.02, 0.12, 0.12),
    "practical": (-0.02, -0.08, -0.06),
}

PAGE_TOPIC_LABELS = {
    "general": "temat ogólny", "events": "wydarzenia", "politics": "polityka",
    "science": "nauka", "celebrities": "gwiazdy i celebryci",
    "economy": "gospodarka", "sports": "sport", "culture": "kultura",
    "practical": "poradnik i program",
}


def apply_page_topic(blend: StyleBlend, topic: str) -> StyleBlend:
    """Adjust a page once, preserving its publication-specific base blend."""
    delta = PAGE_TOPIC_DELTAS.get(topic, PAGE_TOPIC_DELTAS["general"])
    base = (blend.opinion_to_tabloid, blend.classical_to_avantgarde, blend.dense_to_photo)
    values = [min(1.0, max(0.0, float(value) + shift)) for value, shift in zip(base, delta)]
    return StyleBlend(opinion_to_tabloid=values[0], classical_to_avantgarde=values[1], dense_to_photo=values[2])
