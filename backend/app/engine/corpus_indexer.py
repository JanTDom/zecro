"""Corpus feature extraction and TitleDNA archetypes.

The corpus is used as a *style reference* for the generator and critic.  This
module deliberately stores measurements (grid, type rhythm and image/text
balance), rather than page templates.  A page can therefore be compared for
novelty without ever being copied by the layout generator.

The implementation has no dependency on a PDF renderer or a vision model.  It
uses inexpensive image projections when Pillow is available and deterministic
format priors as a fallback.  That makes indexing useful in a local install and
keeps uploads such as a small/invalid PDF from breaking the API.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:  # Pillow is optional for a minimal API installation.
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - exercised only in minimal deployments
    Image = None
    ImageOps = None

try:  # numpy makes projections fast, but the fallback is intentionally usable.
    import numpy as np
except Exception:  # pragma: no cover - numpy is present in the supported image
    np = None

from ..models.schemas import (
    FormatDNA,
    GridDNA,
    PaletteDNA,
    PhotoRulesDNA,
    StyleBlend,
    TitleDNA,
    TransgressionDef,
    TypographyDNA,
    TypographyScaleDNA,
)


# These are the five global families described by the project specification.
# The aliases make the API tolerant of English/Polish names and early clients
# that used the category names as identifiers.
ARCHETYPE_IDS: Tuple[str, ...] = (
    "quality_press",
    "editorial_magazine",
    "tv_guide",
    "tabloid",
    "mass_market",
)

ARCHETYPE_ALIASES: Dict[str, str] = {
    "opinion_daily": "quality_press",
    "quality": "quality_press",
    "serious_press": "quality_press",
    "dziennik_opinii": "quality_press",
    "poważne_opiniotwórcze": "quality_press",
    "magazine": "editorial_magazine",
    "magazines": "editorial_magazine",
    "magazyn": "editorial_magazine",
    "magazyny": "editorial_magazine",
    "tv": "tv_guide",
    "tv_guides": "tv_guide",
    "tv_guidy": "tv_guide",
    "tabloids": "tabloid",
    "tabloidy": "tabloid",
    "bulwar": "tabloid",
    "mid_market": "mass_market",
    "mid-market": "mass_market",
    "mass": "mass_market",
    "masowa": "mass_market",
    "posrednie_masowe": "mass_market",
}

CATEGORY_TO_ARCHETYPE: Dict[str, str] = {
    "1_powazne_opiniotworcze": "quality_press",
    "2_magazyny": "editorial_magazine",
    "3_tv_guidy": "tv_guide",
    "4_tabloidy_bulwarowe": "tabloid",
    "5_posrednie_masowe": "mass_market",
}

ZONE_ALIASES: Dict[str, str] = {
    "1_pierwsza_strona": "front",
    "pierwsza_strona": "front",
    "front": "front",
    "front_page": "front",
    "okladka": "front",
    "2_srodek_rozkladowki": "inside",
    "srodek_rozkladowki": "inside",
    "inside": "inside",
    "spread": "inside",
    "spreads": "inside",
    "3_ostatnia_strona": "back",
    "ostatnia_strona": "back",
    "back": "back",
    "back_page": "back",
}

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".tif",
    ".tiff",
    ".pdf",
    ".idml",
    ".svg",
}

_FORMAT_PRIORS: Dict[str, Dict[str, float]] = {
    "broadsheet": {"w": 350.0, "h": 500.0, "columns": 6, "gutter": 4.5, "baseline": 10.5, "body": 9.5, "headline": 4.8, "photo": 25.0},
    "berliner": {"w": 315.0, "h": 470.0, "columns": 5, "gutter": 4.0, "baseline": 10.0, "body": 9.3, "headline": 4.5, "photo": 29.0},
    "magazine": {"w": 210.0, "h": 280.0, "columns": 4, "gutter": 5.0, "baseline": 10.5, "body": 10.0, "headline": 4.2, "photo": 48.0},
    "magazine_newsmag": {"w": 210.0, "h": 280.0, "columns": 4, "gutter": 5.0, "baseline": 10.5, "body": 10.0, "headline": 4.2, "photo": 46.0},
    "tv_guide": {"w": 210.0, "h": 280.0, "columns": 8, "gutter": 2.5, "baseline": 9.0, "body": 8.3, "headline": 3.2, "photo": 35.0},
    "tabloid": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 5.6, "photo": 52.0},
    "tabloid_broadsheet": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 5.5, "photo": 50.0},
    "tabloid_local": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 5.2, "photo": 48.0},
    "tabloid_supermarket": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 5.6, "photo": 54.0},
    "compact": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 4.8, "photo": 36.0},
    "compact_broadsheet": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 4.8, "photo": 36.0},
    "broadsheet_compact": {"w": 315.0, "h": 470.0, "columns": 5, "gutter": 4.0, "baseline": 10.0, "body": 9.3, "headline": 4.6, "photo": 33.0},
    "berliner_compact": {"w": 315.0, "h": 470.0, "columns": 5, "gutter": 4.0, "baseline": 10.0, "body": 9.3, "headline": 4.6, "photo": 34.0},
    "tabloid_free": {"w": 280.0, "h": 390.0, "columns": 5, "gutter": 3.5, "baseline": 9.5, "body": 9.0, "headline": 5.2, "photo": 43.0},
    "nordisch_broadsheet": {"w": 350.0, "h": 500.0, "columns": 6, "gutter": 4.5, "baseline": 10.5, "body": 9.5, "headline": 4.8, "photo": 27.0},
}


def _canonical_archetype(value: str) -> str:
    key = str(value or "").strip().lower().replace(" ", "_")
    if key in CATEGORY_TO_ARCHETYPE:
        return CATEGORY_TO_ARCHETYPE[key]
    return ARCHETYPE_ALIASES.get(key, key if key in ARCHETYPE_IDS else "mass_market")


def _canonical_zone(value: str) -> str:
    key = str(value or "").strip().lower()
    return ZONE_ALIASES.get(key, "inside")


def _safe_float(value: Any, default: float) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _metadata_for(path: Path) -> Dict[str, Any]:
    """Read the nearest title metadata without making it a hard requirement."""
    for parent in (path.parent, *path.parents):
        metadata_path = parent / "metadata.json"
        if metadata_path.exists():
            try:
                value = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
            except (OSError, ValueError, TypeError):
                return {}
    return {}


def _category_for(path: Path) -> Tuple[str, str]:
    for part in path.parts:
        if part in CATEGORY_TO_ARCHETYPE:
            return part, CATEGORY_TO_ARCHETYPE[part]
    return "", "mass_market"


def _zone_for(path: Path) -> str:
    for part in reversed(path.parts):
        if part in ZONE_ALIASES:
            return _canonical_zone(part)
    # Keep uploaded pages useful even when a caller does not use the canonical
    # corpus folders.  Filename hints are intentionally conservative.
    name = path.name.lower()
    if re.search(r"(?:^|[_-])(?:p1|front|cover)(?:[_-]|\.|$)", name):
        return "front"
    if re.search(r"(?:last|back|p8)(?:[_-]|\.|$)", name):
        return "back"
    return "inside"


def _format_prior(format_preset: str, archetype: str) -> Dict[str, float]:
    prior = _FORMAT_PRIORS.get(format_preset, _FORMAT_PRIORS["compact"]).copy()
    if archetype == "editorial_magazine" and format_preset in {"standard", "compact"}:
        prior.update(_FORMAT_PRIORS["magazine"])
    elif archetype == "tv_guide" and format_preset == "standard":
        prior.update(_FORMAT_PRIORS["tv_guide"])
    elif archetype == "quality_press" and format_preset == "standard":
        prior.update(_FORMAT_PRIORS["broadsheet"])
    return prior


def _pdf_dimensions(path: Path) -> Tuple[Optional[float], Optional[float]]:
    """Read the first PDF MediaBox in points without requiring a PDF package."""
    try:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(path))
        page = document[0]
        dimensions = page.get_size()
        page.close()
        document.close()
        return float(dimensions[0]), float(dimensions[1])
    except Exception:
        pass
    try:
        data = path.read_bytes()[:2_000_000]
        match = re.search(rb"/MediaBox\s*\[\s*[-+0-9.]+\s+[-+0-9.]+\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]", data)
        if not match:
            return None, None
        return float(match.group(1)), float(match.group(2))
    except (OSError, ValueError, TypeError):
        return None, None


def _pdf_vector_metrics(path: Path) -> Dict[str, Any]:
    """Read actual type sizes, font names and object geometry from a PDF.

    PDF text objects do not identify editorial roles. The distribution is
    evidence about visible type scale, not a claim that the largest text is a
    headline rather than the masthead.
    """
    try:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(path))
        page = document[0]
        text_sizes: list[float] = []
        font_names: Counter[str] = Counter()
        image_regions: list[dict[str, float]] = []
        page_w, page_h = page.get_size()
        for obj in page.get_objects():
            if isinstance(obj, pdfium.PdfTextObj):
                bounds = obj.get_bounds()
                matrix = obj.get_matrix()
                size = math.hypot(matrix.c, matrix.d) * obj.get_font_size()
                if 4 <= size <= 200 and bounds[2] - bounds[0] > 5:
                    text_sizes.append(round(size * 2) / 2)
                    try:
                        font_names[obj.get_font().get_family_name()] += 1
                    except Exception:
                        pass
            elif isinstance(obj, pdfium.PdfImage):
                bounds = obj.get_bounds()
                x0, y0, x1, y1 = bounds
                area = max(0.0, x1 - x0) * max(0.0, y1 - y0) / max(1.0, page_w * page_h)
                if area >= .004:
                    image_regions.append({"x": round(max(0.0, x0 / page_w), 4),
                                          "y": round(max(0.0, 1 - y1 / page_h), 4),
                                          "w": round(min(1.0, (x1 - x0) / page_w), 4),
                                          "h": round(min(1.0, (y1 - y0) / page_h), 4)})
        page.close()
        document.close()
        body = Counter(size for size in text_sizes if 7 <= size <= 14)
        display = sorted(size for size in text_sizes if 18 <= size <= 100)
        body_mode = body.most_common(1)[0][0] if body else None
        display_p75 = display[min(len(display) - 1, int(len(display) * .75))] if display else None
        return {"evidence_level": "measured-vector", "text_object_count": len(text_sizes),
                "body_mode_pt": body_mode, "display_p75_pt": display_p75,
                "font_families": dict(font_names.most_common(16)),
                "type_histogram_pt": dict(Counter(str(size) for size in text_sizes).most_common()),
                "image_regions": image_regions[:64], "image_object_count": len(image_regions)}
    except Exception:
        return {"evidence_level": "unavailable", "text_object_count": 0,
                "font_families": {}, "type_histogram_pt": {}, "image_regions": []}


def _load_thumbnail(path: Path) -> Tuple[Any, Optional[int], Optional[int], Optional[float]]:
    """Return a small grayscale image and source dimensions/dpi."""
    if Image is None:
        return None, None, None, None
    if path.suffix.lower() == ".pdf":
        try:
            import pypdfium2 as pdfium
            document = pdfium.PdfDocument(str(path))
            page = document[0]
            width_pt, height_pt = page.get_size()
            scale = min(640 / width_pt, 900 / height_pt)
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            page.close()
            document.close()
            return image, image.width, image.height, None
        except Exception:
            return None, None, None, None
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
        return None, None, None, None
    try:
        with Image.open(path) as original:
            width, height = original.size
            dpi = None
            if isinstance(original.info, dict) and original.info.get("dpi"):
                dpi = _safe_float(original.info["dpi"][0], 0.0) or None
            # Resize while the source is still in its native mode.  Pillow can
            # use JPEG's decoder-side downsampling here; converting a 100MP
            # scan to grayscale first makes a full-corpus index needlessly
            # expensive.
            if path.suffix.lower() in {".jpg", ".jpeg"} and hasattr(original, "draft"):
                # Ask libjpeg for a decoder-side 1/2, 1/4 or 1/8 rendition.
                # This is substantially cheaper than materialising a multi-
                # megapixel scan before thumbnailing it.
                try:
                    original.draft("RGB", (640, 900))
                except Exception:
                    pass
            image = original.copy()
            image.thumbnail((640, 900), Image.Resampling.BILINEAR, reducing_gap=3.0)
            image = ImageOps.exif_transpose(image).convert("RGB")
            return image, width, height, dpi
    except Exception:
        return None, None, None, None


def _array_from_image(image: Any) -> Any:
    if image is None or np is None:
        return None
    try:
        return np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    except Exception:
        return None


def _smooth(values: Any, radius: int = 3) -> Any:
    if np is None or values is None or len(values) < 2:
        return values
    width = max(1, int(radius) * 2 + 1)
    kernel = np.ones(width, dtype=np.float32) / width
    return np.convolve(values, kernel, mode="same")


def _detect_columns(array: Any, prior: Mapping[str, float]) -> Tuple[int, float, float]:
    """Estimate columns, gutter and confidence from vertical ink projections."""
    fallback = int(round(prior.get("columns", 5)))
    fallback_gutter = float(prior.get("gutter", 4.0))
    if array is None or np is None or getattr(array, "ndim", 0) != 2:
        return fallback, fallback_gutter, 0.0
    h, w = array.shape
    if w < 40 or h < 40:
        return fallback, fallback_gutter, 0.0
    # Ignore outer margins and detect stable white vertical valleys.  Text and
    # photos both count as ink, while a gutter remains a long, quiet valley.
    left, right = int(w * 0.03), max(int(w * 0.97), int(w * 0.03) + 1)
    crop = array[:, left:right]
    ink = (crop < 0.72).mean(axis=0)
    baseline = float(np.percentile(ink, 35))
    quiet = _smooth(ink) <= max(0.035, baseline * 0.52)
    min_gap = max(2, int(w * 0.008))
    runs: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for idx, is_quiet in enumerate(quiet):
        if is_quiet and start is None:
            start = idx
        elif not is_quiet and start is not None:
            if idx - start >= min_gap:
                runs.append((start, idx))
            start = None
    if start is not None and len(quiet) - start >= min_gap:
        runs.append((start, len(quiet)))
    # Remove tiny gaps and page margins, then cap to a practical newspaper grid.
    usable = [(a, b) for a, b in runs if 0.01 * w <= a <= 0.94 * w and (b - a) <= 0.12 * w]
    if 1 <= len(usable) <= 11:
        columns = len(usable) + 1
        gap_px = statistics.median([b - a for a, b in usable])
        gutter = max(1.0, min(14.0, gap_px / max(1.0, w) * prior.get("w", 280.0)))
        confidence = min(1.0, 0.45 + len(usable) / 16.0)
        # Avoid treating a large image's internal quiet area as a 12-column grid.
        if abs(columns - fallback) > 3 and confidence < 0.72:
            return fallback, fallback_gutter, confidence * 0.6
        return columns, round(gutter, 2), round(confidence, 3)
    return fallback, fallback_gutter, 0.0


def _detect_type_metrics(array: Any, prior: Mapping[str, float]) -> Dict[str, Any]:
    """Estimate baseline and a compact type histogram from horizontal runs."""
    body = float(prior.get("body", 9.0))
    headline_ratio = float(prior.get("headline", 4.5))
    if array is None or np is None or getattr(array, "ndim", 0) != 2:
        return {
            "body_size_pt": body,
            "headline_scale_ratio": headline_ratio,
            "caption_size_pt": max(6.0, body - 1.5),
            "baseline_grid_pt": float(prior.get("baseline", 10.0)),
            "histogram_pt": {str(round(body, 1)): 0.55, str(round(body * headline_ratio, 1)): 0.2},
            "confidence": 0.0,
        }
    h, w = array.shape
    ink_rows = (array < 0.70).mean(axis=1)
    occupied = _smooth(ink_rows, 2) > 0.035
    runs: List[int] = []
    run = 0
    for val in occupied:
        if val:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    runs = [r for r in runs if r >= 1]
    if not runs:
        return _detect_type_metrics(None, prior)
    median_px = max(1.0, float(statistics.median(runs)))
    # A normal text line is roughly 1.25 body points high in a raster preview.
    body_est = max(6.5, min(13.0, body * (median_px / max(1.0, median_px))))
    # Large connected runs are usually masthead/headline bands.  Keep the prior
    # ratio conservative: raster projections cannot identify font families.
    large = [r for r in runs if r >= median_px * 2.1]
    ratio = headline_ratio if not large else max(headline_ratio, min(8.5, max(2.8, max(large) / median_px * 1.7)))
    # Baseline is inferred from the modal distance between row runs, in pixels,
    # then anchored to a print-friendly 8–13 pt range.
    baseline = float(prior.get("baseline", 10.0))
    if len(runs) > 4:
        baseline = max(7.5, min(13.0, median_px * 2.2))
    hist = {
        str(round(max(6.5, body_est - 1.5), 1)): 0.12,
        str(round(body_est, 1)): 0.58,
        str(round(body_est * ratio, 1)): 0.20,
        str(round(body_est * min(8.5, ratio * 1.45), 1)): 0.10,
    }
    return {
        "body_size_pt": round(body_est, 2),
        "headline_scale_ratio": round(ratio, 3),
        "caption_size_pt": round(max(5.5, body_est - 1.6), 2),
        "baseline_grid_pt": round(baseline, 2),
        "histogram_pt": hist,
        "confidence": round(min(1.0, len(runs) / 30.0), 3),
    }


def _estimate_photo_coverage(array: Any, prior: Mapping[str, float]) -> Tuple[float, float]:
    """Estimate image coverage using local texture/variance on a 12x18 grid."""
    fallback = max(0.0, min(100.0, float(prior.get("photo", 30.0))))
    if array is None or np is None or getattr(array, "ndim", 0) != 2:
        return fallback, 0.0
    h, w = array.shape
    if h < 24 or w < 24:
        return fallback, 0.0
    votes = 0
    cells = 0
    for row in range(12):
        y0, y1 = int(row * h / 12), int((row + 1) * h / 12)
        for col in range(8):
            x0, x1 = int(col * w / 8), int((col + 1) * w / 8)
            block = array[y0:y1, x0:x1]
            if block.size == 0:
                continue
            cells += 1
            variance = float(np.std(block))
            # Text blocks contain repeated thin dark strokes.  Photographs have
            # stronger local tonal variation and occupy more pixels vertically.
            dark = float((block < 0.72).mean())
            edge_y = float(np.abs(np.diff(block, axis=0)).mean()) if block.shape[0] > 1 else 0.0
            if variance > 0.16 and edge_y > 0.035 and 0.08 < dark < 0.92:
                votes += 1
    if not cells:
        return fallback, 0.0
    coverage = votes / cells * 100.0
    # A low-contrast scan can make every textured cell fail the conservative
    # classifier.  Preserve a bounded prior in that case; a genuinely blank
    # page (global standard deviation near zero) still reports 0% coverage.
    if votes == 0 and float(np.std(array)) > 0.10:
        coverage = fallback * 0.50
    # Mix a weak prior in when the scan is too low contrast to segment reliably.
    confidence = min(1.0, cells / 60.0)
    coverage = coverage * confidence + fallback * (1.0 - confidence) * 0.35
    return round(max(0.0, min(100.0, coverage)), 2), round(confidence, 3)


def _feature_vector(columns: int, gutter: float, baseline: float, headline_ratio: float, body: float, photo: float, zone: str, text_coverage: float) -> List[float]:
    zone_value = {"front": 0.0, "inside": 0.5, "back": 1.0}.get(zone, 0.5)
    # Keep ten dimensions for compatibility with LayoutCritic's corpus novelty
    # metric.  Every component is normalized to a stable 0..1 range.
    return [
        round(max(0.0, min(1.0, columns / 12.0)), 4),
        round(max(0.0, min(1.0, gutter / 14.0)), 4),
        round(max(0.0, min(1.0, baseline / 16.0)), 4),
        round(max(0.0, min(1.0, headline_ratio / 8.5)), 4),
        round(max(0.0, min(1.0, body / 14.0)), 4),
        round(max(0.0, min(1.0, photo / 100.0)), 4),
        round(max(0.0, min(1.0, text_coverage / 100.0)), 4),
        round(zone_value, 4),
        round(max(0.0, min(1.0, (headline_ratio - 2.0) / 7.0)), 4),
        round(max(0.0, min(1.0, photo / 100.0 * (1.0 - text_coverage / 100.0))), 4),
    ]


def infer_page_strategy(
    *,
    columns: int,
    photo_coverage_pct: float,
    text_coverage_pct: float,
    headline_scale_ratio: float,
    zone: str,
    structure: Optional[Mapping[str, Any]] = None,
    evidence_level: str = "aggregate",
) -> Dict[str, Any]:
    """Infer a transparent editorial strategy from measured page evidence.

    The result is a vocabulary for the art director, not a copied template.
    Later segmentation/VLM signals can extend ``features`` without changing
    the generator contract.
    """
    whitespace = max(0.0, 1.0 - (float(photo_coverage_pct) + float(text_coverage_pct)) / 100.0)
    structure = structure or {}
    lower_half = _safe_float(structure.get("occupied_lower_half_ratio"), 0.0)
    region_count = int(_safe_float(structure.get("region_count"), 0))
    if photo_coverage_pct >= 55.0 and headline_scale_ratio >= 4.8:
        strategy_id = "visual-opener"
        intent = "zdjęcie otwiera stronę, tytuł jest krótką i mocną obietnicą"
    elif photo_coverage_pct >= 34.0 and headline_scale_ratio >= 5.2:
        strategy_id = "dominant-hero"
        intent = "jedna dominanta prowadzi stronę, reszta pełni funkcję kontrapunktu"
    elif photo_coverage_pct <= 18.0 and text_coverage_pct >= 70.0 and columns >= 6:
        strategy_id = "dense-classic"
        intent = "gęsta strona informacyjna, hierarchia wynika z typografii i rytmu kolumn"
    elif region_count >= 3 and lower_half < 0.06 and whitespace >= 0.22:
        strategy_id = "top-loaded-opener"
        intent = "strona skupia wejście w górze i świadomie zostawia oddech po kulminacji"
    elif whitespace >= 0.18 or (photo_coverage_pct >= 25.0 and columns <= 5):
        strategy_id = "modular-rhythm"
        intent = "moduły i biel tworzą kilka kontrolowanych punktów wejścia"
    else:
        strategy_id = "balanced-grid"
        intent = "zrównoważona siatka łączy dominującą historię z regularnymi skrótami"
    relations = [f"zone:{zone}", f"strategy:{strategy_id}"]
    if photo_coverage_pct >= 34.0:
        relations.append("photo:editorial-anchor")
    if headline_scale_ratio >= 5.0:
        relations.append("headline:dominant-scale")
    if whitespace >= 0.18:
        relations.append("white-space:active")
    if columns >= 6:
        relations.append("body:dense-column-rhythm")
    topology = structure.get("relations") or []
    relation_counts = Counter(str(item.get("relation")) for item in topology if isinstance(item, Mapping))
    if relation_counts.get("stacked", 0) > relation_counts.get("side_by_side", 0):
        relations.append("topology:stacked")
    elif relation_counts.get("side_by_side", 0) > 0:
        relations.append("topology:split")
    if relation_counts.get("overlap", 0) > 0:
        relations.append("topology:overlap")
    return {
        "id": strategy_id,
        "intent": intent,
        # Aggregate priors are useful, but cannot claim the confidence of
        # measured spatial evidence. This prevents old records from masquerading
        # as a VLM/segmentation diagnosis.
        "confidence": round(min(0.96 if evidence_level == "measured-coarse" else 0.72,
                                 (0.58 if evidence_level == "aggregate" else 0.48) +
                                 (0.12 if photo_coverage_pct > 0 else 0.0) +
                                 (0.08 if headline_scale_ratio > 3 else 0.0) +
                                 (0.10 if evidence_level == "measured-coarse" and region_count else 0.0)), 3),
        "evidence_level": evidence_level,
        "relations": relations,
        "features": {
            "photo_coverage_pct": round(float(photo_coverage_pct), 3),
            "text_coverage_pct": round(float(text_coverage_pct), 3),
            "whitespace_ratio": round(whitespace, 4),
            "headline_scale_ratio": round(float(headline_scale_ratio), 3),
            "columns": int(columns),
            "zone": zone,
            "region_count": region_count,
            "occupied_lower_half_ratio": round(lower_half, 4),
            "topology_relations": dict(relation_counts),
        },
    }


def extract_page_features(path: Path | str, file_type: Optional[str] = None, *, category: Optional[str] = None, title_id: Optional[str] = None, zone: Optional[str] = None) -> Dict[str, Any]:
    """Extract a stable, JSON-serializable feature record for one page.

    The function is intentionally safe for malformed files.  It always returns
    the canonical keys consumed by the critic and adds richer nested fields for
    calibration and inspection.
    """
    source = Path(path)
    metadata = _metadata_for(source)
    inferred_category, archetype = _category_for(source)
    category = category or inferred_category
    archetype = _canonical_archetype(metadata.get("archetype", category or archetype))
    format_preset = str(metadata.get("format_preset", "standard"))
    prior = _format_prior(format_preset, archetype)
    canonical_zone = _canonical_zone(zone or _zone_for(source))

    image, width_px, height_px, dpi = _load_thumbnail(source)
    pdf_w, pdf_h = _pdf_dimensions(source) if source.suffix.lower() == ".pdf" else (None, None)
    if width_px is None and pdf_w and pdf_h:
        width_px, height_px = int(round(pdf_w)), int(round(pdf_h))
    array = _array_from_image(image)
    from .corpus_visual import measure_visual_signature
    visual_signature = measure_visual_signature(image)
    pdf_vector = _pdf_vector_metrics(source) if source.suffix.lower() == ".pdf" else None

    columns, gutter, grid_confidence = _detect_columns(array, prior)
    type_metrics = _detect_type_metrics(array, prior)
    if pdf_vector and pdf_vector.get("body_mode_pt") and pdf_vector.get("display_p75_pt"):
        body = float(pdf_vector["body_mode_pt"])
        type_metrics["body_size_pt"] = body
        type_metrics["headline_scale_ratio"] = round(float(pdf_vector["display_p75_pt"]) / body, 3)
        type_metrics["histogram_pt"] = pdf_vector["type_histogram_pt"]
        type_metrics["confidence"] = 1.0
        type_metrics["evidence_level"] = "measured-vector"
    else:
        # Raster projections locate bands but cannot identify a true font
        # point size or distinguish a masthead from the story headline.
        type_metrics["evidence_level"] = "format-prior"
        type_metrics["confidence"] = 0.0
    photo_coverage, photo_confidence = _estimate_photo_coverage(array, prior)
    text_coverage = round(max(0.0, min(100.0, 100.0 - photo_coverage - 8.0)), 2)
    if array is None:
        text_coverage = round(100.0 - photo_coverage, 2)
    headline_ratio = type_metrics["headline_scale_ratio"]
    body_size = type_metrics["body_size_pt"]
    baseline = type_metrics["baseline_grid_pt"]

    # Preserve physical dimensions where available, otherwise expose the
    # deterministic format prior used by the archetype calibrator.
    trim_w = prior["w"]
    trim_h = prior["h"]
    if pdf_w and pdf_h:
        trim_w = round(pdf_w * 25.4 / 72.0, 2)
        trim_h = round(pdf_h * 25.4 / 72.0, 2)

    record: Dict[str, Any] = {
        "path": source.as_posix(),
        "file_name": source.name,
        "file_type": (str(file_type).lower().lstrip(".") if file_type else source.suffix.lower().lstrip(".") or "unknown"),
        "title_id": title_id or metadata.get("id") or (source.parent.parent.name if source.parent.name in ZONE_ALIASES else source.parent.name),
        "title_name": metadata.get("name", ""),
        "country": metadata.get("country", ""),
        "category": category,
        "archetype": archetype,
        "archetype_id": archetype,
        "format_preset": format_preset,
        "zone": canonical_zone,
        "page_zone": canonical_zone,
        "strefa": canonical_zone,
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
        "trim_w_mm": round(trim_w, 2),
        "trim_h_mm": round(trim_h, 2),
        "columns": columns,
        "dominant_columns": columns,
        "column_count": columns,
        "gutter_mm": round(gutter, 2),
        "grid": {
            "columns": columns,
            "gutter_mm": round(gutter, 2),
            "baseline_grid_pt": round(baseline, 2),
            "baseline_mm": round(baseline * 0.352778, 3),
            "confidence": grid_confidence,
        },
        "baseline_grid_pt": round(baseline, 2),
        "baseline_mm": round(baseline * 0.352778, 3),
        "typography": type_metrics,
        "headline_scale_ratio": round(headline_ratio, 3),
        "body_size_pt": round(body_size, 2),
        "type_scale_histogram": type_metrics["histogram_pt"],
        "photo_coverage_pct": photo_coverage,
        "photo_coverage": photo_coverage / 100.0,
        "text_coverage_pct": text_coverage,
        "photo_detection_confidence": photo_confidence,
        "avg_transgressions_per_page": round(0.35 + photo_coverage / 100.0 * 1.65, 3),
        "pdf_vector": pdf_vector,
        "visual_signature": visual_signature,
        "measurement_evidence": {"typography": type_metrics["evidence_level"],
                                 "structure": "measured-coarse" if array is not None else "unavailable",
                                 "semantic_roles_verified": False},
    }
    record["vector"] = _feature_vector(columns, gutter, baseline, headline_ratio, body_size, photo_coverage, canonical_zone, text_coverage)
    # Preserve spatial evidence separately from the ten-dimensional novelty
    # vector. The vector is intentionally backward-compatible; the signature
    # lets the art director distinguish a top-loaded opener from a dense page
    # with the same aggregate coverage.
    try:
        from .corpus_knowledge import extract_spatial_structure
        record["structural_signature"] = extract_spatial_structure(array)
    except Exception:
        # Indexing a page must remain available in a minimal runtime. An
        # unavailable signature is explicitly labelled by the helper and never
        # presented as measured evidence.
        record["structural_signature"] = {"evidence_level": "unavailable", "confidence": 0.0, "regions": [], "spatial_vector": []}
    record["strategy"] = infer_page_strategy(
        columns=columns,
        photo_coverage_pct=photo_coverage,
        text_coverage_pct=text_coverage,
        headline_scale_ratio=headline_ratio,
        zone=canonical_zone,
        structure=record["structural_signature"],
        evidence_level=str(record["structural_signature"].get("evidence_level", "aggregate")),
    )
    # Flat alias for SQL and API consumers that do not expand nested JSON.
    record["strategy_id"] = record["strategy"]["id"]
    return record


def _iter_corpus_pages(root: Path) -> Iterable[Path]:
    """Yield audited publication pages from the canonical five categories.

    The repository also contains raw Wukadka production assets under
    ``corpus/wukadka``.  Those are source materials, not the 1041-page style
    corpus, so indexing is restricted to the five catalogued category folders.
    """
    audit_path = root / "CORPUS_AUDIT.json"
    audited: dict[str, dict] | None = None
    if audit_path.is_file():
        try:
            manifest = json.loads(audit_path.read_text(encoding="utf-8"))
            audited = {str(row["path"]): row for row in manifest.get("rows", []) if isinstance(row, dict) and row.get("path")}
        except (OSError, ValueError, TypeError):
            audited = None
    for category in sorted(CATEGORY_TO_ARCHETYPE):
        category_dir = root / category
        if not category_dir.is_dir():
            continue
        for path in sorted(category_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS - {".idml", ".svg"}:
                # A page belongs to an explicit zone.  Files such as metadata
                # or unrelated source assets are skipped.
                if any(part in ZONE_ALIASES for part in path.parts):
                    if audited is not None:
                        row = audited.get(path.relative_to(root).as_posix())
                        if not row or row.get("verdict") != "accepted" or row.get("title_matches_folder") != "yes":
                            continue
                        if _canonical_zone(row.get("page_zone_guess")) != _zone_for(path):
                            continue
                        # The audit correctly describes this as a promotional
                        # supplement. It is not a Daily Mirror front-page
                        # exemplar even though the folder was marked "yes".
                        if "daily_mirror/1_pierwsza_strona/wwd-mirror-promo-mag" in path.as_posix():
                            continue
                    yield path


def _mean(values: Sequence[float], default: float = 0.0) -> float:
    return float(statistics.fmean(values)) if values else default


def _distribution(values: Sequence[str]) -> Dict[str, float]:
    if not values:
        return {}
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    total = float(len(values))
    return {key: round(value / total, 4) for key, value in sorted(counts.items())}


def _transgressions_for(archetype: str) -> List[TransgressionDef]:
    """Build the allowed-transgression catalog for one archetype."""
    common = [
        TransgressionDef(id="overlap-scrim", name="Overlap with contrast scrim", applies_to=["headline", "photo", "band"], effect="overlap", cost=0.22, max_per_page=1, precondition="photo_coverage >= 0.2"),
        TransgressionDef(id="cutout-wrap", name="Cutout contour and text wrap", applies_to=["photo", "body", "lead"], effect="text_wrap", cost=0.20, max_per_page=2, precondition="photo_coverage >= 0.25"),
    ]
    if archetype == "quality_press":
        return common[:1] + [TransgressionDef(id="grid-break", name="Measured grid break", applies_to=["headline", "infobox"], effect="span_columns", cost=0.16, max_per_page=1, precondition="importance >= 0.8")]
    if archetype == "editorial_magazine":
        return common + [TransgressionDef(id="bleed-off", name="Photo bleed off trim", applies_to=["photo", "band"], effect="bleed", cost=0.30, max_per_page=2), TransgressionDef(id="diagonal-break", name="Editorial diagonal", applies_to=["headline", "photo"], effect="rotate", cost=0.26, max_per_page=1, range=[-7, 7])]
    if archetype == "tv_guide":
        return [common[0], TransgressionDef(id="module-break", name="Program module break", applies_to=["infobox", "photo"], effect="span_columns", cost=0.12, max_per_page=2)]
    if archetype == "tabloid":
        return common + [TransgressionDef(id="bleed-off", name="Hero image bleed", applies_to=["photo", "band"], effect="bleed", cost=0.28, max_per_page=2), TransgressionDef(id="extreme-scale", name="Extreme dominant scale", applies_to=["headline", "photo"], effect="scale", cost=0.34, max_per_page=1, precondition="importance >= 0.85"), TransgressionDef(id="diagonal-break", name="Dynamic diagonal", applies_to=["headline", "photo"], effect="rotate", cost=0.27, max_per_page=1, range=[-9, 9])]
    return common + [TransgressionDef(id="grid-break", name="Controlled modular break", applies_to=["headline", "infobox"], effect="span_columns", cost=0.16, max_per_page=1)]


def _make_dna(archetype: str, stats: Optional[Mapping[str, Any]] = None) -> TitleDNA:
    archetype = _canonical_archetype(archetype)
    stats = stats or {}
    spec: Dict[str, Any] = {
        "quality_press": {"name": "Dziennik opinii", "format": "broadsheet", "cols": 6, "gutter": 4.5, "baseline": 10.5, "body": 9.5, "headline": 36.0, "photo": 24, "energy": 0.65, "fonts": ("headline", "body")},
        "editorial_magazine": {"name": "Magazyn redakcyjny", "format": "magazine", "cols": 4, "gutter": 5.0, "baseline": 10.5, "body": 10.0, "headline": 42.0, "photo": 48, "energy": 1.0, "fonts": ("headline", "body")},
        "tv_guide": {"name": "Program TV i poradnik", "format": "tv_guide", "cols": 8, "gutter": 2.5, "baseline": 9.0, "body": 8.3, "headline": 25.0, "photo": 35, "energy": 0.7, "fonts": ("sans", "body")},
        "tabloid": {"name": "Tabloid", "format": "tabloid", "cols": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 48.0, "photo": 52, "energy": 1.2, "fonts": ("sans", "sans")},
        "mass_market": {"name": "Prasa masowa / pośrednia", "format": "compact", "cols": 5, "gutter": 4.0, "baseline": 9.5, "body": 9.0, "headline": 34.0, "photo": 36, "energy": 0.85, "fonts": ("headline", "body")},
    }[archetype]
    prior = _format_prior(spec["format"], archetype)
    count = int(stats.get("page_count", 0) or 0)
    cols = int(round(_safe_float(stats.get("columns_mean"), spec["cols"]))) if count else spec["cols"]
    gutter = _safe_float(stats.get("gutter_mm_mean"), spec["gutter"])
    baseline = _safe_float(stats.get("baseline_grid_pt_mean"), spec["baseline"])
    body = _safe_float(stats.get("body_size_pt_mean"), spec["body"])
    photo = _safe_float(stats.get("photo_coverage_pct_mean"), spec["photo"])
    headline = _safe_float(stats.get("headline_size_pt_mean"), spec["headline"])
    scales = TypographyScaleDNA(
        mega=round(headline * 2.0, 1), headline_xl=round(headline * 1.45, 1), headline_l=round(headline, 1), headline_m=round(headline * 0.78, 1), headline_s=round(headline * 0.61, 1), lead=round(body * 1.42, 1), body=round(body, 1), caption=round(max(6.0, body * 0.79), 1), kicker=round(max(8.0, body * 0.94), 1), byline=round(max(7.0, body * 0.88), 1), pullquote=round(headline * 0.53, 1)
    )
    headline_font, body_font = spec["fonts"]
    typo = TypographyDNA(
        fonts={"headline": "Playfair Display, Georgia, serif" if headline_font == "headline" else "Roboto Condensed, Arial Narrow, sans-serif" if archetype == "tabloid" else "Inter, Helvetica Neue, sans-serif", "body": "PT Serif, Times New Roman, serif" if body_font == "body" else "Inter, Helvetica Neue, sans-serif", "sans": "Inter, Helvetica Neue, sans-serif"},
        scales=scales,
    )
    # The page-level coverage is kept in metadata for downstream blending; the
    # base TitleDNA contract remains intentionally small and renderer-friendly.
    dna = TitleDNA(
        name=spec["name"],
        version=1,
        format=FormatDNA(trim_w_mm=prior["w"], trim_h_mm=prior["h"], bleed_mm=3.0, margin_top_mm=15.0 if archetype != "tabloid" else 12.0, margin_bottom_mm=15.0, margin_left_mm=12.0, margin_right_mm=12.0),
        grid=GridDNA(columns=max(1, min(24, cols)), gutter_mm=max(0.5, gutter), baseline_grid_pt=max(3.0, baseline), rows=14 if archetype in {"quality_press", "mass_market"} else 12, row_gutter_mm=3.5 if archetype in {"tabloid", "tv_guide"} else 4.0),
        typography=typo,
        palette=(PaletteDNA(primary="#172b4d", secondary="#e1262f", accent="#f7d735", background="#ffffff", text="#17212b", tint_bg="#fff1c1", scrim="rgba(0,0,0,0.65)") if archetype == "tabloid" else PaletteDNA(primary="#111111", secondary="#c91818" if archetype == "mass_market" else "#52616b", accent="#d4af37", background="#fcfbf7", text="#1f1f1f", tint_bg="#f3efe6", scrim="rgba(0,0,0,0.65)")),
        photo_rules=PhotoRulesDNA(allow_cutout=archetype != "tv_guide", allow_full_bleed=archetype in {"editorial_magazine", "tabloid"}, default_treatment="cutout" if archetype == "tabloid" else "crop", min_dpi=220 if archetype == "quality_press" else 180, max_photos_per_page=2 if archetype == "tv_guide" else 5, text_wrap_offset_mm=3.0 if archetype == "tv_guide" else 3.5),
        transgressions=_transgressions_for(archetype),
        page_energy_budget=max(0.0, min(2.0, _safe_float(stats.get("energy_budget"), spec["energy"]))),
    )
    # Keep the family label and continuous controls in the DNA itself.  These
    # are editable data, not renderer templates, and the generator consumes the
    # same values when exploring layouts.
    blend = {
        "quality_press": StyleBlend(opinion_to_tabloid=0.10, classical_to_avantgarde=0.20, dense_to_photo=0.25),
        "editorial_magazine": StyleBlend(opinion_to_tabloid=0.45, classical_to_avantgarde=0.60, dense_to_photo=0.72),
        "tv_guide": StyleBlend(opinion_to_tabloid=0.40, classical_to_avantgarde=0.15, dense_to_photo=0.35),
        "tabloid": StyleBlend(opinion_to_tabloid=0.90, classical_to_avantgarde=0.75, dense_to_photo=0.82),
        "mass_market": StyleBlend(opinion_to_tabloid=0.58, classical_to_avantgarde=0.40, dense_to_photo=0.55),
    }[archetype]
    dna.archetype = archetype
    dna.style_blend = blend
    dna.corpus_stats = dict(stats)
    dna.cover_grammar = {
        "tabloid": {"family": "popular_collage", "masthead_band_mm": 39, "teaser_share": 0.15, "hero_photo_share": 0.47,
                    "headline_band_share": 0.17, "hero_photo_width_share": 0.55, "card_colors": ["#f7d735", "#b9dce8"],
                    "headline_color": "#ffffff", "display_color": "#e1262f", "information_density": "teaser_led",
                    "poster_morphology": "asymmetric_hero_rail", "poster_skyline_height_mm": 36,
                    "poster_rail_width_share": .285, "poster_headline_max_height_mm": 77,
                    "poster_teaser_font_candidates": ["Gotham XNarrow", "Nimbus Sans D", "Roboto Condensed"],
                    "poster_portrait_focal_y": .34,
                    "type_led_skyline_height_mm": 38,
                    "type_led_masthead_height_mm": 39,
                    "type_led_photo_width_share": .41,
                    "type_led_bottom_height_mm": 47,
                    "type_led_skyline_split": .54,
                    "type_led_bottom_split": .43,
                    "type_led_headline_color": "#17212b",
                    "display_font_candidates": ["Gotham XNarrow", "Tungsten", "AmsiProNarw-Black", "Heading Compressed Pro",
                                                "TitlingGothicFB Comp", "Nimbus Sans D", "Roboto Condensed", "Oswald"],
                    "display_case_options": ["normal", "upper"],
                    "display_outline_color": "#172b4d", "display_outline_width_pt": .5,
                    "display_shadow_color": "#4b1420", "display_shadow_offset_x_pt": .8,
                    "display_shadow_offset_y_pt": .8,
                    # Story colour planes per emotion; masthead stays brand-owned.
                    "mood_palettes": {
                        "entertainment": {"strong": "#d81b72", "deep": "#24124a", "light": "#ffd23f"},
                        "celebratory": {"strong": "#e1262f", "deep": "#172b4d", "light": "#f2b705"},
                    },
                    "morphology_catalog": ["diagonal_hero_entry", "dual_scale_collage", "photo_dominant_strip",
                                           "directional_tension", "type_behind_subject", "stacked_rail_cover", "dense_mosaic"],
                    "display_wide_font_candidates": ["Arial Black", "Helvetica Neue LT Pro", "Nimbus Sans D",
                                                     "Myriad Pro"],
                    "morphologies": {
                        "diagonal_hero_entry": {"skyline_mm": 30, "strip_mm": 60, "strip_shares": [.40, .27, .33]},
                        "dual_scale_collage": {"major_share": .64, "minor_height_share": .62, "overlap_mm": 14},
                        "photo_dominant_strip": {"skyline_mm": 30, "strip_mm": 60, "step_mm": [9, 3, 6]},
                        "directional_tension": {"photo_share": .58, "strip_mm": 58},
                        "type_behind_subject": {"type_share": .34, "cover_share": .45},
                    }},
        "editorial_magazine": {"family": "editorial_cover", "photo_dominance": 0.68, "cover_line_count": 3, "negative_space": 0.20},
        "tv_guide": {"family": "service_grid", "module_count": 6, "navigation_band": True, "accent_count": 3,
                     "navigation_colors": ["#d62828", "#1d4e89", "#2a9d8f", "#e9a800", "#7b2cbf", "#ef6f00"],
                     "hour_bands": [[6, 12, "Rano"], [12, 18, "Popołudnie"], [18, 24, "Wieczór"], [24, 30, "Noc"]],
                     "max_stations": 5},
        "quality_press": {"family": "hierarchical_grid", "photo_dominance": 0.24, "column_rhythm": "dense"},
        "mass_market": {"family": "balanced_grid", "photo_dominance": 0.36, "column_rhythm": "mixed"},
    }[archetype]
    return dna


def aggregate_archetype_features(pages: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate page measurements by one of the five global archetypes."""
    groups: Dict[str, List[Mapping[str, Any]]] = {key: [] for key in ARCHETYPE_IDS}
    for page in pages:
        key = _canonical_archetype(str(page.get("archetype") or page.get("category") or "mass_market"))
        if key in groups:
            groups[key].append(page)
    profiles: Dict[str, Dict[str, Any]] = {}
    for key in ARCHETYPE_IDS:
        rows = groups[key]
        vectors = [row.get("vector", []) for row in rows if isinstance(row.get("vector"), list)]
        vector_mean = [round(_mean([float(v[i]) for v in vectors if len(v) > i]), 4) for i in range(10)] if vectors else []
        zone_counts = _distribution([str(row.get("zone", "inside")) for row in rows])
        strategy_distribution = _distribution([
            str((row.get("strategy") or {}).get("id") or row.get("strategy_id") or "balanced-grid")
            for row in rows
        ])
        strategy_profiles: Dict[str, Dict[str, Any]] = {}
        for strategy_id, share in strategy_distribution.items():
            strategy_rows = [
                row for row in rows
                if str((row.get("strategy") or {}).get("id") or row.get("strategy_id") or "balanced-grid") == strategy_id
            ]
            strategy_profiles[strategy_id] = {
                "share": share,
                "sample_count": len(strategy_rows),
                "photo_coverage_pct_mean": round(_mean([_safe_float(row.get("photo_coverage_pct"), 35.0) for row in strategy_rows], 35.0), 3),
                "text_coverage_pct_mean": round(_mean([_safe_float(row.get("text_coverage_pct"), 60.0) for row in strategy_rows], 60.0), 3),
                "headline_scale_ratio_mean": round(_mean([_safe_float(row.get("headline_scale_ratio"), 4.5) for row in strategy_rows], 4.5), 3),
                "columns_mean": round(_mean([_safe_float(row.get("columns"), 5.0) for row in strategy_rows], 5.0), 3),
                "zones": _distribution([str(row.get("zone", "inside")) for row in strategy_rows]),
            }
        base = _make_dna(key)
        vector_type_rows = [row for row in rows if (row.get("measurement_evidence") or {}).get("typography") == "measured-vector"]
        # A single title's PDF fonts cannot define a whole genre. Keep its
        # measurements available per title, but use the explicit base prior
        # until at least three independent titles have vector type evidence.
        calibrated_type = len({row.get("title_id") for row in vector_type_rows}) >= 3
        type_rows = vector_type_rows if calibrated_type else []
        stats = {
            "page_count": len(rows),
            "title_count": len({row.get("title_id") for row in rows if row.get("title_id")}),
            "columns_mean": round(_mean([_safe_float(row.get("columns"), 5.0) for row in rows], _FORMAT_PRIORS["compact"]["columns"]), 3),
            "gutter_mm_mean": round(_mean([_safe_float(row.get("gutter_mm"), 4.0) for row in rows], 4.0), 3),
            "baseline_grid_pt_mean": round(_mean([_safe_float(row.get("baseline_grid_pt"), 10.0) for row in rows], 10.0), 3),
            "body_size_pt_mean": round(_mean([_safe_float(row.get("body_size_pt"), 9.0) for row in type_rows], base.typography.scales.body), 3),
            "headline_scale_ratio_mean": round(_mean([_safe_float(row.get("headline_scale_ratio"), 4.5) for row in type_rows], base.typography.scales.headline_l / base.typography.scales.body), 3),
            "headline_size_pt_mean": round(_mean([_safe_float(row.get("body_size_pt"), 9.0) * _safe_float(row.get("headline_scale_ratio"), 4.5) for row in type_rows], base.typography.scales.headline_l), 3),
            "photo_coverage_pct_mean": round(_mean([_safe_float(row.get("photo_coverage_pct"), 30.0) for row in rows], 30.0), 3),
            "text_coverage_pct_mean": round(_mean([_safe_float(row.get("text_coverage_pct"), 60.0) for row in rows], 60.0), 3),
            "avg_transgressions_per_page": None,
            "typography_evidence": "measured-vector" if calibrated_type else "editorial-prior",
            "typography_title_count": len({row.get("title_id") for row in vector_type_rows}),
            "transgression_evidence": "editorial-prior",
        }
        stats["energy_budget"] = base.page_energy_budget
        profiles[key] = {
            "id": key,
            "name": _make_dna(key).name,
            "page_count": len(rows),
            "title_count": stats["title_count"],
            "stats": stats,
            "zone_distribution": zone_counts,
            "strategy_distribution": strategy_distribution,
            "strategy_profiles": strategy_profiles,
            "mean_vector": vector_mean,
            "title_dna": _make_dna(key, stats).model_dump(mode="json"),
        }
    return profiles


def build_generation_guidance(
    pages: Iterable[Mapping[str, Any]],
    *,
    archetype: Optional[str] = None,
    zone: Optional[str] = None,
) -> Dict[str, Any]:
    """Summarize measured corpus knowledge for one generation run.

    The generator receives statistics and normalized targets, never source
    templates.  Filtering by the project's archetype and page zone keeps a
    front page from inheriting the density of an unrelated TV-guide interior.
    """
    rows = [page for page in pages if isinstance(page, Mapping) and page.get("style_eligible", True)]
    wanted_arch = _canonical_archetype(archetype) if archetype else None
    wanted_zone = _canonical_zone(zone) if zone else None
    filtered = []
    for page in rows:
        page_arch = _canonical_archetype(str(page.get("archetype") or page.get("archetype_id") or page.get("category") or "mass_market"))
        page_zone = _canonical_zone(str(page.get("zone") or page.get("page_zone") or "inside"))
        if wanted_arch and page_arch != wanted_arch:
            continue
        if wanted_zone and page_zone != wanted_zone:
            continue
        filtered.append(page)
    if not filtered:
        # A TV-guide interior or another genre cannot stand in for a missing
        # tabloid front. Surface the evidence gap instead of laundering an
        # unrelated average into a precise style rule.
        return {"sample_count": 0, "used_fallback": False,
                "archetype": wanted_arch, "zone": wanted_zone,
                "evidence_gap": "no_matching_verified_pages"}
    used_fallback = False

    def mean(key: str, default: float) -> float:
        values = [_safe_float(page.get(key), default) for page in filtered]
        return round(sum(values) / max(1, len(values)), 4)

    columns = mean("columns", mean("dominant_columns", 5.0))
    photo_pct = mean("photo_coverage_pct", mean("photo_coverage", 35.0))
    text_pct = mean("text_coverage_pct", 60.0)
    type_rows = [page for page in filtered if (page.get("measurement_evidence") or {}).get("typography") == "measured-vector"]
    type_titles = len({page.get("title_id") for page in type_rows})
    calibrated_type = type_titles >= 3
    base = _make_dna(wanted_arch or "mass_market")
    body_size = round(_mean([_safe_float(page.get("body_size_pt"), base.typography.scales.body) for page in type_rows],
                            base.typography.scales.body), 4) if calibrated_type else base.typography.scales.body
    headline_ratio = round(_mean([_safe_float(page.get("headline_scale_ratio"), 4.5) for page in type_rows],
                                 base.typography.scales.headline_l / base.typography.scales.body), 4) if calibrated_type else round(base.typography.scales.headline_l / base.typography.scales.body, 4)
    transgression_rate = None
    strategy_distribution = _distribution([
        str((page.get("strategy") or {}).get("id") or page.get("strategy_id") or "balanced-grid")
        for page in filtered
    ])
    strategy_profiles: Dict[str, Dict[str, Any]] = {}
    for strategy_id, share in strategy_distribution.items():
        strategy_rows = [
            page for page in filtered
            if str((page.get("strategy") or {}).get("id") or page.get("strategy_id") or "balanced-grid") == strategy_id
        ]
        strategy_profiles[strategy_id] = {
            "share": share,
            "sample_count": len(strategy_rows),
            "photo_coverage_pct_mean": round(_mean([_safe_float(row.get("photo_coverage_pct"), photo_pct) for row in strategy_rows], photo_pct), 3),
            "text_coverage_pct_mean": round(_mean([_safe_float(row.get("text_coverage_pct"), text_pct) for row in strategy_rows], text_pct), 3),
            "headline_scale_ratio_mean": round(_mean([_safe_float(row.get("headline_scale_ratio"), 4.5) for row in strategy_rows], 4.5), 3),
            "columns_mean": round(_mean([_safe_float(row.get("columns"), columns) for row in strategy_rows], columns), 3),
            "lower_half_occupancy_mean": round(_mean([
                _safe_float((row.get("structural_signature") or {}).get("occupied_lower_half_ratio"), 0.0)
                for row in strategy_rows
            ], 0.0), 4),
            "measured_structure_share": round(_mean([
                1.0 if (row.get("structural_signature") or {}).get("evidence_level") == "measured-coarse" else 0.0
                for row in strategy_rows
            ], 0.0), 4),
        }
    guidance = {
        "sample_count": len(filtered),
        "used_fallback": used_fallback,
        "archetype": wanted_arch,
        "zone": wanted_zone,
        "columns_mean": columns,
        "gutter_mm_mean": mean("gutter_mm", 4.0),
        "baseline_grid_pt_mean": mean("baseline_grid_pt", 10.0),
        "body_size_pt_mean": body_size,
        "headline_scale_ratio_mean": headline_ratio,
        "photo_coverage_pct_mean": photo_pct,
        "text_coverage_pct_mean": text_pct,
        "whitespace_ratio_mean": round(max(0.0, 1.0 - (photo_pct + text_pct) / 100.0), 4),
        "avg_transgressions_per_page": transgression_rate,
        "energy_budget": base.page_energy_budget,
        "typography_evidence": "measured-vector" if calibrated_type else "editorial-prior",
        "typography_title_count": type_titles,
        "transgression_evidence": "editorial-prior",
        "strategy_distribution": strategy_distribution,
        "strategy_profiles": strategy_profiles,
        "evidence_levels": _distribution([
            str((page.get("knowledge_evidence") or {}).get("level") or (
                (page.get("structural_signature") or {}).get("evidence_level") or "legacy-aggregate"
            ))
            for page in filtered
        ]),
        "measured_structure_share": round(_mean([
            1.0 if (page.get("structural_signature") or {}).get("evidence_level") == "measured-coarse" else 0.0
            for page in filtered
        ], 0.0), 4),
    }
    return guidance


def create_archetype_dnas(stats: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Dict[str, TitleDNA]:
    """Return the five editable base TitleDNA profiles.

    ``stats`` may be the ``profiles`` value returned by
    :func:`aggregate_archetype_features`; absent data uses stable editorial
    priors.  Returned models are independent objects and safe to mutate.
    """
    stats = stats or {}
    result = {}
    for key in ARCHETYPE_IDS:
        profile = stats.get(key, {}) if isinstance(stats, Mapping) else {}
        profile_stats = profile.get("stats", profile) if isinstance(profile, Mapping) else {}
        result[key] = _make_dna(key, profile_stats)
    return result


def get_archetype_profiles(stats: Optional[Mapping[str, Mapping[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Serialize base archetypes for API/UI consumption."""
    dnas = create_archetype_dnas(stats)
    output = []
    for key in ARCHETYPE_IDS:
        dna = dnas[key]
        output.append({"id": key, "name": dna.name, "dna": dna.model_dump(mode="json"), "aliases": [alias for alias, target in ARCHETYPE_ALIASES.items() if target == key]})
    return output


class CorpusIndexer:
    """Indexer facade used by scripts and API endpoints."""

    def __init__(self, root: Path | str | None = None):
        if root is None:
            # backend/app/engine/corpus_indexer.py -> repository root
            root = Path(__file__).resolve().parents[3] / "corpus"
        self.root = Path(root).expanduser().resolve()

    def scan(self) -> List[Dict[str, Any]]:
        audit_path = self.root / "CORPUS_AUDIT.json"
        audit = {}
        if audit_path.is_file():
            manifest = json.loads(audit_path.read_text(encoding="utf-8"))
            audit = {str(row.get("path")): row for row in manifest.get("rows", []) if isinstance(row, dict)}
        pages = []
        for path in _iter_corpus_pages(self.root):
            page = extract_page_features(path)
            evidence = audit.get(path.relative_to(self.root).as_posix(), {})
            era = evidence.get("era")
            modern = era in {"2000s", "2010s", "2020s"}
            reason = str(evidence.get("reason") or "").lower()
            special_issue = any(term in reason for term in (
                "dodatku", "wydania specjalnego", "special edition", "magazynu promocyjnego",
            ))
            page["source_audit"] = {"verdict": evidence.get("verdict"), "title_matches_folder": evidence.get("title_matches_folder"),
                                     "era": era, "page_zone_guess": evidence.get("page_zone_guess"),
                                     "special_issue": special_issue, "reason": evidence.get("reason")}
            page["style_eligible"] = modern and not special_issue if audit else True
            pages.append(page)
        return pages

    def build(self, *, persist_path: Optional[Path | str] = None) -> Dict[str, Any]:
        pages = self.scan()
        for page in pages:
            # The snapshot is bundled with production. Developer-machine
            # absolute paths are neither portable nor suitable for API data.
            page["path"] = Path(page["path"]).relative_to(self.root).as_posix()
        profiles = aggregate_archetype_features([page for page in pages if page.get("style_eligible", True)])
        index: Dict[str, Any] = {
            "version": "3.0.0",
            "root": self.root.as_posix(),
            "source_digest": hashlib.sha256(json.dumps(pages, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "page_count": len(pages),
            "title_count": len({p.get("title_id") for p in pages if p.get("title_id")}),
            "categories": {category: sum(1 for p in pages if p.get("category") == category) for category in sorted(CATEGORY_TO_ARCHETYPE)},
            "zones": {zone: sum(1 for p in pages if p.get("zone") == zone) for zone in ("front", "inside", "back")},
            "pages": pages,
            "archetypes": profiles,
        }
        if persist_path:
            target = Path(persist_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return index


def load_feature_index(path: Path | str | None = None) -> List[Dict[str, Any]]:
    """Load the measured global corpus vectors without rescanning page assets.

    The generated feature index is deliberately a plain JSON artifact so a
    local installation can use novelty search immediately at generation time.
    Missing or stale indexes degrade to an empty list; the explicit index API
    can rebuild them when the corpus changes.
    """
    target = Path(path) if path else Path(__file__).resolve().parents[3] / "corpus" / "FEATURE_INDEX.json"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        pages = payload.get("pages", []) if isinstance(payload, dict) else []
        return [page for page in pages if isinstance(page, dict) and isinstance(page.get("vector"), list)]
    except (OSError, ValueError, TypeError):
        return []


def build_corpus_index(root: Path | str | None = None, *, persist_path: Optional[Path | str] = None) -> Dict[str, Any]:
    resolved_root = Path(root) if root is not None else Path(__file__).resolve().parents[3] / "corpus"
    return CorpusIndexer(resolved_root).build(persist_path=persist_path)


# Friendly aliases used by scripts and integrations developed against the
# original prompt terminology.
index_corpus = build_corpus_index
generate_archetypes = create_archetype_dnas
get_title_dna_archetypes = create_archetype_dnas
make_archetype_dnas = create_archetype_dnas
build_archetype_profiles = get_archetype_profiles


__all__ = [
    "ARCHETYPE_IDS",
    "ARCHETYPE_ALIASES",
    "CATEGORY_TO_ARCHETYPE",
    "CorpusIndexer",
    "aggregate_archetype_features",
    "build_generation_guidance",
    "build_corpus_index",
    "build_archetype_profiles",
    "create_archetype_dnas",
    "extract_page_features",
    "generate_archetypes",
    "get_archetype_profiles",
    "get_title_dna_archetypes",
    "index_corpus",
    "load_feature_index",
    "make_archetype_dnas",
]
