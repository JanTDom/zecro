"""Coarse but observed colour and image morphology of a reference page.

This is intentionally geometric. A textured rectangle is only a photo
hypothesis; no person, story or editorial role is inferred from pixels.
"""
from __future__ import annotations

from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


def _regions(mask: list[list[bool]], kind: str) -> list[dict[str, Any]]:
    rows, cols = len(mask), len(mask[0])
    seen: set[tuple[int, int]] = set()
    regions = []
    for y in range(rows):
        for x in range(cols):
            if not mask[y][x] or (y, x) in seen:
                continue
            todo = [(y, x)]
            seen.add((y, x))
            points = []
            while todo:
                cy, cx = todo.pop()
                points.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < rows and 0 <= nx < cols and mask[ny][nx] and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        todo.append((ny, nx))
            if len(points) < 2:
                continue
            x0, x1 = min(p[1] for p in points), max(p[1] for p in points) + 1
            y0, y1 = min(p[0] for p in points), max(p[0] for p in points) + 1
            regions.append({"type": kind, "frame": {"x": round(x0 / cols, 4), "y": round(y0 / rows, 4),
                                                       "w": round((x1 - x0) / cols, 4),
                                                       "h": round((y1 - y0) / rows, 4)},
                            "occupied_cells": len(points), "confidence": .55})
    return sorted(regions, key=lambda r: r["occupied_cells"], reverse=True)


def measure_visual_signature(image: Any) -> dict[str, Any]:
    if np is None or image is None:
        return {"evidence_level": "unavailable", "photo_regions": [], "color_regions": []}
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    if rgb.ndim != 3 or min(rgb.shape[:2]) < 48:
        return {"evidence_level": "unavailable", "photo_regions": [], "color_regions": []}
    height, width = rgb.shape[:2]
    gray = rgb.mean(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    rows, cols = 12, 8
    photos = [[False for _ in range(cols)] for _ in range(rows)]
    colors = [[False for _ in range(cols)] for _ in range(rows)]
    whitespace = [[False for _ in range(cols)] for _ in range(rows)]
    photo_scores = []
    chroma_scores = []
    for y in range(rows):
        y0, y1 = round(y * height / rows), round((y + 1) * height / rows)
        for x in range(cols):
            x0, x1 = round(x * width / cols), round((x + 1) * width / cols)
            patch = gray[y0:y1, x0:x1]
            cp = chroma[y0:y1, x0:x1]
            midtones = float(((patch > .16) & (patch < .86)).mean())
            tonal = float(patch.std())
            horizontal = float(np.abs(np.diff(patch, axis=1)).mean()) if patch.shape[1] > 1 else 0.0
            vertical = float(np.abs(np.diff(patch, axis=0)).mean()) if patch.shape[0] > 1 else 0.0
            chromatic = float((cp > .20).mean())
            texture = min(1.0, .5 * midtones + 1.6 * tonal + 2.0 * min(horizontal, vertical))
            photos[y][x] = midtones > .25 and tonal > .11 and horizontal > .018 and vertical > .018
            colors[y][x] = chromatic > .38
            whitespace[y][x] = float((patch > .91).mean()) > .82
            photo_scores.append(round(texture, 3))
            chroma_scores.append(round(chromatic, 3))
    bands = []
    active = None
    for y in range(rows + 1):
        colored = y < rows and sum(colors[y]) >= 5
        if colored and active is None:
            active = y
        elif not colored and active is not None:
            bands.append({"y": round(active / rows, 4), "h": round((y - active) / rows, 4)})
            active = None
    return {"evidence_level": "measured-coarse", "method": "rgb-tile-morphology-v1",
            "semantic_roles_verified": False, "grid": [cols, rows],
            "photo_regions": _regions(photos, "photo-hypothesis"),
            "color_regions": _regions(colors, "chromatic-panel"),
            "whitespace_regions": _regions(whitespace, "whitespace"),
            "chromatic_bands": bands,
            "photo_tile_share": round(sum(sum(row) for row in photos) / (rows * cols), 4),
            "chromatic_tile_share": round(sum(sum(row) for row in colors) / (rows * cols), 4),
            "photo_scores": photo_scores, "chroma_scores": chroma_scores}
