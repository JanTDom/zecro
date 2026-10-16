"""Critic calibration from A/B pairs (Bradley–Terry on interpretable features).

The hand-written heuristic critic is a prior, not taste.  It systematically
preferred evenly tiled pages that an independent visual critic rejected as
"bulletin-like".  Instead of editing its weights by hand, this module learns
a per-archetype preference from *pairwise choices*:

* pairs judged by the separate VLM critic (``visual_pairwise`` prompt, random
  A/B order, same material and photos in both renders), and/or
* pairs chosen by human editors (the existing taste loop signals).

The model is a regularised logistic regression on standardised feature
differences.  It is only used when it has enough pairs and a leave-one-out
accuracy above a floor; otherwise the critic stays exactly as before.  The
calibration file records its provenance, so a VLM-only calibration is never
presented as human taste.  The generator never sees the weights directly; it
only receives the critic's score, as before.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Optional

from ..models.schemas import SceneGraph

CALIBRATION_DIR = Path(__file__).resolve().parent / "calibration"
MIN_PAIRS = 20
MIN_LOO_ACCURACY = .70

FEATURES = (
    "balance", "reading_gravity", "scale_rhythm", "breathing_space", "tension", "corpus_alignment",
    "hero_photo_share", "photo_count", "module_uniformity", "headline_dominance",
    "diagonal_entry", "intentional_overlap", "largest_empty_region", "colour_plane_share", "text_share",
)


def _printable(sg: SceneGraph, dna) -> tuple[float, float, float, float]:
    fmt = dna.format
    return fmt.margin_left_mm, fmt.margin_top_mm, float(sg.page.trim[0]) - fmt.margin_right_mm, float(sg.page.trim[1]) - fmt.margin_bottom_mm


def calibration_features(sg: SceneGraph, critic) -> dict[str, float]:
    """Interpretable page features in roughly 0..1, independent of labels."""
    from .critic import _largest_empty_editorial_region
    dna = critic.dna
    h = critic.evaluate_heuristics(sg)
    left, top, right, bottom = _printable(sg, dna)
    area = max(1.0, (right - left) * (bottom - top))
    photos = [e for e in sg.elements if e.role == "photo"]
    heads = [e for e in sg.elements if e.role == "headline" and e.style and e.style.font_size_pt]
    lead_ref = max(((e.importance, e.story_ref) for e in heads + photos), default=(0, None))[1]
    # Story module boxes for secondary stories: equal boxes = tiled page.
    boxes: dict[str, list[float]] = {}
    for e in sg.elements:
        if not e.story_ref or e.story_ref == lead_ref or e.role in {"rule", "folio", "logo"}:
            continue
        b = boxes.setdefault(e.story_ref, [e.frame.x, e.frame.y, e.frame.x + e.frame.w, e.frame.y + e.frame.h])
        b[0], b[1] = min(b[0], e.frame.x), min(b[1], e.frame.y)
        b[2], b[3] = max(b[2], e.frame.x + e.frame.w), max(b[3], e.frame.y + e.frame.h)
    module_areas = [max(1.0, (b[2] - b[0]) * (b[3] - b[1])) for b in boxes.values()]
    if len(module_areas) >= 2:
        mean = sum(module_areas) / len(module_areas)
        std = math.sqrt(sum((a - mean) ** 2 for a in module_areas) / len(module_areas))
        uniformity = max(0.0, 1.0 - min(1.0, std / mean))
    else:
        uniformity = 0.0
    lead_head = max((e.style.font_size_pt for e in heads if e.story_ref == lead_ref), default=0.0)
    others = [e.style.font_size_pt for e in heads if e.story_ref != lead_ref]
    dominance = min(1.0, (lead_head / max(1.0, median(others))) / 6.0) if others and lead_head else 0.0
    overlaps = sum(1 for e in sg.elements if {"overlap-scrim"} & set(e.transgressions or [])
                   or "intentional_photo_inset" in (e.constraints or [])
                   or "intentional_photo_badge" in (e.constraints or []))
    empty_area, _, _ = _largest_empty_editorial_region(sg, dna)
    planes = sum(e.frame.w * e.frame.h for e in sg.elements if e.role == "band")
    text = sum(e.frame.w * e.frame.h for e in sg.elements
               if e.role in {"headline", "deck", "lead", "body", "kicker", "caption"})
    return {
        "balance": h.visual_balance_score, "reading_gravity": h.reading_gravity_score,
        "scale_rhythm": h.rhythm_and_scale_score, "breathing_space": h.breathing_space_score,
        "tension": h.tension_adherence_score, "corpus_alignment": h.corpus_alignment_score,
        "hero_photo_share": min(1.0, max((p.frame.w * p.frame.h for p in photos), default=0.0) / area),
        "photo_count": min(1.0, len(photos) / 6.0),
        "module_uniformity": round(uniformity, 4),
        "headline_dominance": round(dominance, 4),
        "diagonal_entry": 1.0 if any(abs(e.frame.rotation_deg or 0) >= 2 for e in heads) else 0.0,
        "intentional_overlap": min(1.0, overlaps / 4.0),
        "largest_empty_region": round(empty_area, 4),
        "colour_plane_share": min(1.0, planes / area),
        "text_share": min(1.0, text / area),
    }


def _sigmoid(value: float) -> float:
    if value < -40:
        return 0.0
    if value > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def _standardise(rows: list[dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    mean = {f: sum(r[f] for r in rows) / len(rows) for f in FEATURES}
    std = {f: math.sqrt(sum((r[f] - mean[f]) ** 2 for r in rows) / len(rows)) or 1.0 for f in FEATURES}
    return mean, std


def _train(deltas: list[list[float]], *, l2: float = .5, epochs: int = 600, lr: float = .15) -> list[float]:
    """Logistic regression without bias on winner−loser deltas (label 1).

    Each pair is used in both orientations so the model is symmetric.
    """
    weights = [0.0] * len(FEATURES)
    data = [(d, 1.0) for d in deltas] + [([-v for v in d], 0.0) for d in deltas]
    n = max(1, len(data))
    for _ in range(epochs):
        grad = [l2 * w / n for w in weights]
        for x, y in data:
            p = _sigmoid(sum(w * v for w, v in zip(weights, x)))
            for i, v in enumerate(x):
                grad[i] += (p - y) * v / n
        weights = [w - lr * g for w, g in zip(weights, grad)]
    return weights


def fit_calibration(pairs: list[dict[str, Any]], *, archetype: str, source: str) -> dict[str, Any]:
    """``pairs`` rows: {"winner": features, "loser": features, "weight": confidence}."""
    usable = [p for p in pairs if p.get("winner") and p.get("loser")]
    if not usable:
        raise ValueError("no usable pairs")
    rows = [p["winner"] for p in usable] + [p["loser"] for p in usable]
    mean, std = _standardise(rows)

    def z(features):
        return [(features[f] - mean[f]) / std[f] for f in FEATURES]

    deltas = [[a - b for a, b in zip(z(p["winner"]), z(p["loser"]))] for p in usable]
    weights = _train(deltas)
    # Leave-one-out accuracy: an honest generalisation estimate for small data.
    hits = 0
    for index in range(len(deltas)):
        w = _train(deltas[:index] + deltas[index + 1:])
        hits += sum(a * b for a, b in zip(w, deltas[index])) > 0
    loo = hits / len(deltas)
    heuristic_hits = sum((p["winner"]["balance"] * .22 + p["winner"]["reading_gravity"] * .22
                          + p["winner"]["scale_rhythm"] * .18 + p["winner"]["breathing_space"] * .14
                          + p["winner"]["tension"] * .14 + p["winner"]["corpus_alignment"] * .10)
                         > (p["loser"]["balance"] * .22 + p["loser"]["reading_gravity"] * .22
                            + p["loser"]["scale_rhythm"] * .18 + p["loser"]["breathing_space"] * .14
                            + p["loser"]["tension"] * .14 + p["loser"]["corpus_alignment"] * .10)
                         for p in usable) / len(usable)
    return {
        "archetype": archetype, "source": source, "pairs": len(usable),
        "features": list(FEATURES), "mean": mean, "std": std,
        "weights": dict(zip(FEATURES, [round(w, 5) for w in weights])),
        "loo_accuracy": round(loo, 4), "heuristic_pair_accuracy": round(heuristic_hits, 4),
        "valid": len(usable) >= MIN_PAIRS and loo >= MIN_LOO_ACCURACY,
        "note": ("Kalibracja z ocen parami. Źródło VLM nie zastępuje gustu redaktora; "
                 "pary od redaktora (pętla gustu) mają pierwszeństwo w projekcie."),
    }


_CACHE: dict[str, Optional[dict[str, Any]]] = {}


def load_calibration(archetype: Optional[str]) -> Optional[dict[str, Any]]:
    if not archetype:
        return None
    if archetype not in _CACHE:
        path = CALIBRATION_DIR / f"{archetype}.json"
        data = None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
        _CACHE[archetype] = data if data and data.get("valid") else None
    return _CACHE[archetype]


def calibrated_score(calibration: dict[str, Any], features: dict[str, float]) -> float:
    value = sum(calibration["weights"][f] * (features[f] - calibration["mean"][f]) / (calibration["std"][f] or 1.0)
                for f in calibration["features"] if f in features)
    return round(_sigmoid(value), 4)


def save_calibration(data: dict[str, Any]) -> Path:
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    path = CALIBRATION_DIR / f"{data['archetype']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _CACHE.pop(data["archetype"], None)
    return path


def iter_pairs(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
