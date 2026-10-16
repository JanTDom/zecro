"""Evidence-bearing corpus knowledge, independent of the deployment filesystem.

Raster analysis measures geometry and ink. It does not claim to recognize
stories, editorial intent, font families or people. Legacy SQL measurements
can be enriched on read, but are never upgraded to segmentation evidence.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


STRUCTURE_VERSION = "1.0"


@lru_cache(maxsize=1)
def _bundled_index() -> dict[str, Any] | None:
    from ..config import settings
    path = Path(settings.base_dir) / "corpus" / "FEATURE_INDEX.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) and payload.get("pages") else None


def ensure_bundled_index(database: Any) -> bool:
    """Upgrade a persisted production corpus when the bundled audit changes."""
    from ..config import settings
    if not all(hasattr(database, name) for name in ("get_global_corpus_index", "save_global_corpus_index")):
        return False
    bundled = _bundled_index()
    if not bundled:
        return False
    saved = database.get_global_corpus_index(include_pages=False)
    bundled_version = str(bundled.get("version") or "0")
    saved_version = str(saved.get("version") or "0") if saved else "0"
    if saved_version > bundled_version:
        return False
    if saved and saved_version == bundled_version and saved.get("source_digest") == bundled.get("source_digest"):
        return False
    deployment_index = dict(bundled)
    deployment_index["root"] = str(Path(settings.base_dir) / "corpus")
    database.save_global_corpus_index(deployment_index)
    return True


def _number(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def extract_spatial_structure(array: Any) -> dict[str, Any]:
    """Measure coarse regions, whitespace and mass in normalized coordinates.

    XY cuts use actual quiet projections. Region types are texture hypotheses,
    deliberately distinct from semantic newspaper roles. The occupancy vector
    is stable across preview resolutions and retains the *spatial* information
    that average page coverage discards.
    """
    unavailable = {
        "version": STRUCTURE_VERSION, "method": "unavailable",
        "evidence_level": "unavailable", "confidence": 0.0,
        "regions": [], "spatial_vector": [], "semantic_roles_verified": False,
    }
    if np is None or array is None or getattr(array, "ndim", 0) != 2:
        return unavailable
    h, w = array.shape
    if min(h, w) < 32:
        return unavailable
    ink = array < 0.72
    ys, xs = np.where(ink)
    if len(xs) == 0:
        return unavailable | {
            "method": "raster-xycut", "evidence_level": "measured-coarse",
            "confidence": 0.65, "ink_coverage_pct": 0.0,
            "whitespace_ratio": 1.0, "spatial_vector": [0.0] * 96,
            "occupied_lower_half_ratio": 0.0, "region_count": 0,
        }

    def quiet_runs(values, threshold, minimum):
        runs = []
        start = None
        for idx, value in enumerate(values):
            if value <= threshold and start is None:
                start = idx
            elif value > threshold and start is not None:
                if idx - start >= minimum:
                    runs.append((start, idx))
                start = None
        if start is not None and len(values) - start >= minimum:
            runs.append((start, len(values)))
        return runs

    leaves = []

    def cut(x0, y0, x1, y1, depth=0):
        block = ink[y0:y1, x0:x1]
        by, bx = np.where(block)
        if not len(bx):
            return
        x0, y0, x1, y1 = x0 + int(bx.min()), y0 + int(by.min()), x0 + int(bx.max()) + 1, y0 + int(by.max()) + 1
        block = ink[y0:y1, x0:x1]
        bh, bw = block.shape
        if depth < 4 and bh >= h * 0.08 and bw >= w * 0.10:
            candidates = []
            for axis, projection, length, page_length in (
                ("x", block.mean(axis=0), bw, w),
                ("y", block.mean(axis=1), bh, h),
            ):
                for a, b in quiet_runs(projection, 0.015, max(3, int(page_length * 0.008))):
                    if a < length * 0.10 or b > length * 0.90:
                        continue
                    # Prefer substantial separators; body interlines should not
                    # split a column into dozens of pretend editorial modules.
                    score = (b - a) / page_length
                    if axis == "y" and b - a < h * 0.012:
                        continue
                    candidates.append((score, axis, a, b))
            if candidates:
                _, axis, a, b = max(candidates)
                if axis == "x":
                    cut(x0, y0, x0 + a, y1, depth + 1)
                    cut(x0 + b, y0, x1, y1, depth + 1)
                else:
                    cut(x0, y0, x1, y0 + a, depth + 1)
                    cut(x0, y0 + b, x1, y1, depth + 1)
                return
        if bw * bh / (w * h) >= 0.004:
            leaves.append((x0, y0, x1, y1))

    cut(0, 0, w, h)
    regions = []
    for index, (x0, y0, x1, y1) in enumerate(leaves):
        patch = array[y0:y1, x0:x1]
        density = float((patch < 0.72).mean())
        midtone = float(((patch > 0.18) & (patch < 0.82)).mean())
        row_variation = float(np.std((patch < 0.72).mean(axis=1)))
        kind = "visual-region" if midtone > 0.25 and density > 0.2 else "text-region" if row_variation > 0.10 and density < 0.5 else "mixed-region"
        regions.append({
            "id": f"region-{index + 1}", "type": kind,
            "frame": {"x": round(x0 / w, 4), "y": round(y0 / h, 4), "w": round((x1 - x0) / w, 4), "h": round((y1 - y0) / h, 4)},
            "ink_density": round(density, 4), "midtone_ratio": round(midtone, 4),
            "confidence": 0.55 if kind != "mixed-region" else 0.35,
        })
    # Preserve coarse topology in addition to coverage.  These relations are
    # intentionally geometric hypotheses (above/beside/overlap), never claims
    # about story roles.  They let the strategy layer distinguish a split hero
    # from a stacked page with similar ink percentages.
    relations = []
    for left_index, left in enumerate(regions):
        lf = left["frame"]
        for right_index, right in enumerate(regions):
            if right_index <= left_index:
                continue
            rf = right["frame"]
            overlap_x = min(lf["x"] + lf["w"], rf["x"] + rf["w"]) - max(lf["x"], rf["x"])
            overlap_y = min(lf["y"] + lf["h"], rf["y"] + rf["h"]) - max(lf["y"], rf["y"])
            if overlap_x > 0.04 and overlap_y > 0.04:
                relation = "overlap"
            elif overlap_x > 0.04:
                relation = "stacked"
            elif overlap_y > 0.04:
                relation = "side_by_side"
            else:
                relation = "diagonal"
            relations.append({"source": left["id"], "target": right["id"], "relation": relation})
    spatial = []
    for row in range(12):
        for col in range(8):
            cell = ink[int(row * h / 12):int((row + 1) * h / 12), int(col * w / 8):int((col + 1) * w / 8)]
            spatial.append(round(float(cell.mean()), 4))
    largest = max(regions, key=lambda r: r["frame"]["w"] * r["frame"]["h"] * r["ink_density"], default=None)
    horizontal = quiet_runs(ink.mean(axis=1), 0.015, max(3, int(h * 0.012)))
    vertical = quiet_runs(ink.mean(axis=0), 0.015, max(3, int(w * 0.008)))
    return {
        "version": STRUCTURE_VERSION, "method": "raster-xycut",
        "evidence_level": "measured-coarse", "confidence": 0.65,
        "semantic_roles_verified": False, "regions": regions,
        "region_count": len(regions), "spatial_vector": spatial,
        "ink_coverage_pct": round(float(ink.mean()) * 100, 3),
        "whitespace_ratio": round(float(1 - ink.mean()), 4),
        "ink_centroid": [round(float(xs.mean()) / w, 4), round(float(ys.mean()) / h, 4)],
        "occupied_lower_half_ratio": round(float(ink[h // 2:].mean()), 4),
        "dominant_region": largest,
        "relations": relations[:48],
        "horizontal_separators": [[round(a / h, 4), round(b / h, 4)] for a, b in horizontal if a > h * 0.03 and b < h * 0.97],
        "vertical_separators": [[round(a / w, 4), round(b / w, 4)] for a, b in vertical if a > w * 0.03 and b < w * 0.97],
    }


def enrich_feature_record(page: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize old persisted records without inventing new observations."""
    from .corpus_indexer import _canonical_zone, infer_page_strategy

    row = deepcopy(dict(page))
    row["zone"] = _canonical_zone(str(row.get("zone") or row.get("page_zone") or "inside"))
    if "photo_coverage_pct" not in row and "photo_coverage" in row:
        ratio = _number(row["photo_coverage"])
        row["photo_coverage_pct"] = ratio * 100 if ratio <= 1 else ratio
    structure = row.get("structural_signature") or {}
    has_structure = structure.get("evidence_level") == "measured-coarse" and bool(structure.get("spatial_vector"))
    evidence = row.get("measurement_evidence") or {}
    known_image = bool(row.get("width_px") and row.get("height_px")) and str(row.get("file_type", "")).lower() not in {"pdf", "idml", "svg"}
    level = "measured-coarse" if has_structure else "legacy-aggregate" if known_image else "prior-or-unknown"
    row["knowledge_evidence"] = {
        "level": level,
        "has_spatial_structure": has_structure,
        "semantic_roles_verified": bool(structure.get("semantic_roles_verified", False)),
        "source_page_ref": str(row.get("page_id") or row.get("id") or row.get("path") or row.get("file_name") or ""),
        "limitations": [] if structure.get("semantic_roles_verified") else ["semantic_story_roles_unverified", "no_measured_font_family"],
    }
    # Legacy inference is rebuilt even if an old strategy had an optimistic
    # confidence. Existing real semantic/VLM observations may be kept explicitly.
    if not (row.get("strategy") or {}).get("semantic_roles_verified"):
        row["strategy"] = infer_page_strategy(
            columns=int(_number(row.get("columns", row.get("dominant_columns")), 5)),
            photo_coverage_pct=_number(row.get("photo_coverage_pct"), 35),
            text_coverage_pct=_number(row.get("text_coverage_pct"), 60),
            headline_scale_ratio=_number(row.get("headline_scale_ratio"), 4.5),
            zone=row["zone"],
            structure=structure if has_structure else None,
            evidence_level=level,
        )
    row["strategy_id"] = row.get("strategy", {}).get("id", "balanced-grid")
    return row


def load_corpus_knowledge(database: Any, project_id: str | None = None, *, remote_only: bool | None = None) -> dict[str, Any]:
    """Read persisted global/project knowledge; local snapshot is dev-only.

    No exception from the remote database is swallowed. A missing index is
    exposed as a diagnostic instead of silently reading a workstation file.
    """
    from ..config import settings
    from .corpus_indexer import load_feature_index

    if remote_only is None:
        remote_only = bool(settings.require_remote_db or getattr(database, "is_postgres", False))
    if remote_only:
        ensure_bundled_index(database)
    persisted = database.list_global_corpus_features()
    source = "database" if persisted else "unavailable"
    if not persisted and not remote_only:
        persisted = load_feature_index()
        if persisted:
            source = "development-snapshot"
    private = database.list_corpus_pages(project_id) if project_id else []
    pages = [enrich_feature_record(p) for p in persisted if isinstance(p, Mapping)]
    seen = {str(p.get("path") or p.get("page_id") or "") for p in pages}
    for page in private:
        features = page.extracted_features
        if not features:
            continue
        ref = str(features.get("path") or page.id)
        if ref in seen:
            continue
        seen.add(ref)
        enriched = enrich_feature_record(dict(features) | {"page_id": page.id, "project_id": project_id})
        pages.append(enriched)
    levels = Counter(p["knowledge_evidence"]["level"] for p in pages)
    return {
        "pages": pages, "source": source, "remote_only": remote_only,
        "evidence": {
            "global_pages": len(persisted), "project_pages": len(private),
            "knowledge_pages": len(pages), "levels": dict(levels),
            "structural_pages": sum(bool(p["knowledge_evidence"]["has_spatial_structure"]) for p in pages),
            "semantic_pages": sum(bool(p["knowledge_evidence"]["semantic_roles_verified"]) for p in pages),
            "warnings": ["global_corpus_unavailable"] if not persisted else [],
        },
    }
