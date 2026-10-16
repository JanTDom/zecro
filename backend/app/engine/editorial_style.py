"""Human-readable editorial intent derived from editable TitleDNA values."""

from __future__ import annotations

STYLE_POINTS = {
    "gazeta poważna i opiniotwórcza": (0.10, 0.20, 0.25),
    "gazeta lokalna": (0.32, 0.24, 0.45),
    "gazeta popularna codzienna": (0.58, 0.40, 0.55),
    "gazeta bulwarowa": (0.90, 0.75, 0.82),
    "magazyn redakcyjny": (0.45, 0.60, 0.72),
    "gazeta programowa i poradnikowa": (0.40, 0.15, 0.35),
    "gazeta biznesowa i gospodarcza": (0.16, 0.28, 0.18),
    "gazeta sportowa": (0.68, 0.55, 0.78),
    "gazeta naukowa i technologiczna": (0.22, 0.43, 0.44),
    "magazyn kultury i stylu życia": (0.42, 0.67, 0.68),
}


def editorial_style_label(blend) -> str:
    """Map continuous style controls to a plain-language AI brief."""
    def value(key):
        return blend.get(key) if isinstance(blend, dict) else getattr(blend, key, None)

    opinion = value("opinion_to_tabloid")
    avantgarde = value("classical_to_avantgarde")
    photo = value("dense_to_photo")
    if opinion is None:
        return "gazeta popularna codzienna"
    if avantgarde is None or photo is None:
        return "gazeta bulwarowa" if float(opinion) >= .5 else "gazeta poważna i opiniotwórcza"
    point = (float(opinion), float(avantgarde), float(photo))
    return min(STYLE_POINTS, key=lambda label: sum((a - b) ** 2 for a, b in zip(point, STYLE_POINTS[label])))
