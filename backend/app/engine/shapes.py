"""Shared frame geometry for non-rectangular frames.

All renderers (SVG/HTML/PDF/IDML) and the critic call these functions, so a
circle in the preview is the same circle in the press PDF and in InDesign.
Coordinates are in the caller's units (mm or pt); ``y`` grows downwards.
"""
from __future__ import annotations

import math
from typing import List, Tuple

Point = Tuple[float, float]
STARBURST_INNER = .80
SLANT_SHARE = .14


def is_rect(shape: str | None) -> bool:
    return not shape or shape == "rect"


def shape_polygon(shape: str, x: float, y: float, w: float, h: float, *, spikes: int = 16) -> List[Point]:
    if is_rect(shape):
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
    if shape in {"circle", "ellipse"}:
        n = 48
        return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    if shape == "starburst":
        pts = []
        for i in range(spikes * 2):
            r = 1.0 if i % 2 == 0 else STARBURST_INNER
            a = math.pi * i / spikes - math.pi / 2
            pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
        return pts
    if shape == "triangle_tl":
        return [(x, y), (x + w, y), (x, y + h)]
    if shape == "triangle_tr":
        return [(x, y), (x + w, y), (x + w, y + h)]
    if shape == "triangle_bl":
        return [(x, y), (x + w, y + h), (x, y + h)]
    if shape == "triangle_br":
        return [(x + w, y), (x + w, y + h), (x, y + h)]
    if shape == "slant":
        s = w * SLANT_SHARE
        return [(x + s, y), (x + w, y), (x + w - s, y + h), (x, y + h)]
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def inscribed_inset(shape: str, w: float, h: float) -> List[float]:
    """[top, right, bottom, left] inset that keeps a text box inside the shape."""
    if is_rect(shape):
        return [0.0, 0.0, 0.0, 0.0]
    if shape in {"circle", "ellipse", "starburst"}:
        k = (STARBURST_INNER if shape == "starburst" else 1.0) / math.sqrt(2)
        iw, ih = w * k, h * k
        return [(h - ih) / 2, (w - iw) / 2, (h - ih) / 2, (w - iw) / 2]
    if shape == "triangle_tl":
        return [0.0, w / 2, h / 2, 0.0]
    if shape == "triangle_tr":
        return [0.0, 0.0, h / 2, w / 2]
    if shape == "triangle_bl":
        return [h / 2, w / 2, 0.0, 0.0]
    if shape == "triangle_br":
        return [h / 2, 0.0, 0.0, w / 2]
    if shape == "slant":
        s = w * SLANT_SHARE
        return [0.0, s, 0.0, s]
    return [0.0, 0.0, 0.0, 0.0]


def text_box(element) -> Tuple[float, float, float, float]:
    """Inner text box (x, y, w, h) in mm after inset/padding."""
    f, st = element.frame, element.style
    inset = list(getattr(st, "inset_mm", None) or []) if st else []
    if len(inset) != 4:
        pad = float((st.padding_mm if st else None) or 0.0)
        inset = [pad, pad, pad, pad]
    top, right, bottom, left = inset
    return f.x + left, f.y + top, max(1.0, f.w - left - right), max(1.0, f.h - top - bottom)
