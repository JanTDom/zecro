import math
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional
from pathlib import Path

def simplify_douglas_peucker(points: List[Tuple[float, float]], tolerance: float) -> List[Tuple[float, float]]:
    """
    Ramer-Douglas-Peucker algorithm to reduce the number of points in a 2D polygon contour.
    """
    if len(points) <= 2:
        return points

    p1 = points[0]
    p2 = points[-1]

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    line_len = math.hypot(dx, dy)

    max_dist = 0.0
    index = 0

    for i in range(1, len(points) - 1):
        p = points[i]
        if line_len == 0.0:
            dist = math.hypot(p[0] - p1[0], p[1] - p1[1])
        else:
            # 2D cross product for perpendicular distance
            dist = abs(dx * (p1[1] - p[1]) - dy * (p1[0] - p[0])) / line_len
        if dist > max_dist:
            max_dist = dist
            index = i

    if max_dist > tolerance:
        left = simplify_douglas_peucker(points[:index + 1], tolerance)
        right = simplify_douglas_peucker(points[index:], tolerance)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]

Ring = List[List[float]]


def extract_alpha_rings(
    image_path: str,
    target_w_mm: float,
    target_h_mm: float,
    threshold: int = 128,
    tolerance_mm: float = 1.0,
    min_component_ratio: float = 0.01,
    min_hole_ratio: float = 0.002,
) -> List[dict]:
    """Vectorise a real alpha mask into polygons with holes.

    Returns ``[{"outer": ring, "holes": [ring, ...], "area_mm2": float}, ...]``
    sorted by area (largest first).  Coordinates are millimetres relative to
    the frame.  Holes are the enclosed background regions (e.g. the gap
    between an arm on the hip and the torso).  An unreadable asset or missing
    OpenCV returns ``[]`` — callers keep the photo rectangular.
    """
    try:
        import cv2
        with Image.open(image_path) as source:
            img = source.convert("RGBA")
        alpha = np.asarray(img.getchannel("A"))
        height, width = alpha.shape
        binary = np.where(alpha > int(threshold), 255, 0).astype(np.uint8)
        # Close pin-holes so matting noise does not become fake holes.
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if not contours or hierarchy is None:
            return []
        hier = hierarchy[0]
        total = float(width * height)
        sx, sy = float(target_w_mm) / width, float(target_h_mm) / height
        epsilon = max(0.5, float(tolerance_mm) / max(sx, sy))

        def ring_mm(contour) -> Ring:
            approx = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
            return [[round(float(x) * sx, 2), round(float(y) * sy, 2)] for x, y in approx]

        polygons: List[dict] = []
        for index, contour in enumerate(contours):
            if hier[index][3] >= 0:  # a hole, handled through its parent
                continue
            area = float(cv2.contourArea(contour))
            if area / total < float(min_component_ratio):
                continue
            outer = ring_mm(contour)
            if len(outer) < 3:
                continue
            holes: List[Ring] = []
            child = int(hier[index][2])
            while child >= 0:
                if float(cv2.contourArea(contours[child])) / total >= float(min_hole_ratio):
                    hole = ring_mm(contours[child])
                    if len(hole) >= 3:
                        holes.append(hole)
                child = int(hier[child][0])
            polygons.append({"outer": outer, "holes": holes, "area_mm2": round(area * sx * sy, 2)})
        polygons.sort(key=lambda item: item["area_mm2"], reverse=True)
        return polygons
    except Exception:
        return []


def extract_alpha_contour(
    image_path: str,
    target_w_mm: float,
    target_h_mm: float,
    threshold: int = 128,
    tolerance_mm: float = 1.0,
    min_component_ratio: float = 0.01,
) -> List[List[float]]:
    """Outer ring of the largest real alpha component (concavities kept).

    Holes are available through :func:`extract_alpha_rings`.  Never returns a
    synthetic silhouette: no mask means ``[]``.
    """
    rings = extract_alpha_rings(image_path, target_w_mm, target_h_mm, threshold, tolerance_mm, min_component_ratio)
    return rings[0]["outer"] if rings else []


def resolve_asset_path(asset_ref: Optional[str]) -> Optional[Path]:
    """Resolve local/Supabase assets for contour extraction and preflight."""
    from .renderers.production_utils import local_asset

    return local_asset(asset_ref)


def offset_contour_polygon(contour_mm: List[List[float]], offset_mm: float, holes: Optional[List[Ring]] = None) -> List[List[float]]:
    """Offset the outer ring with a geometric buffer (concavities retained).

    Text wrap needs the outside ring; holes shrink by the same buffer and are
    returned by :func:`offset_rings`.  Without Shapely the measured contour is
    returned unchanged (never an invented shape).
    """
    rings = offset_rings(contour_mm, offset_mm, holes or [])
    return rings["outer"] if rings else [list(point) for point in (contour_mm or [])]


def offset_rings(outer: List[List[float]], offset_mm: float, holes: List[Ring]) -> Optional[dict]:
    if not outer or len(outer) < 3:
        return None
    try:
        from shapely.geometry import Polygon
        poly = Polygon([(float(x), float(y)) for x, y in outer], [[(float(x), float(y)) for x, y in h] for h in holes if len(h) >= 3])
        if not poly.is_valid:
            poly = poly.buffer(0)
        buffered = poly.buffer(float(offset_mm), join_style=1)
        if buffered.is_empty:
            return None
        if buffered.geom_type == "MultiPolygon":
            buffered = max(buffered.geoms, key=lambda g: g.area)
        rnd = lambda coords: [[round(float(x), 2), round(float(y), 2)] for x, y in list(coords)[:-1]]
        return {"outer": rnd(buffered.exterior.coords), "holes": [rnd(i.coords) for i in buffered.interiors]}
    except Exception:
        return None


def contour_to_css_polygon(contour_mm: List[List[float]], frame_w_mm: float, frame_h_mm: float) -> str:
    """Convert an mm ring to a CSS ``polygon()`` in frame percentages."""
    if not contour_mm or frame_w_mm <= 0 or frame_h_mm <= 0:
        return "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)"
    pct_points = []
    for x, y in contour_mm:
        px = max(0.0, min(100.0, (x / frame_w_mm) * 100.0))
        py = max(0.0, min(100.0, (y / frame_h_mm) * 100.0))
        pct_points.append(f"{px:.1f}% {py:.1f}%")
    return f"polygon({', '.join(pct_points)})"


def contour_to_css_path(outer: List[List[float]], holes: Optional[List[Ring]], frame_w_mm: float, frame_h_mm: float, scale: float = 1.0) -> str:
    """CSS ``clip-path: path(evenodd, ...)`` with holes, in CSS px (mm*scale)."""
    d = contour_to_svg_path(outer, holes, scale=scale)
    return f"path(evenodd, '{d}')" if d else "none"


def contour_to_svg_path(contour_mm: List[List[float]], holes: Optional[List[Ring]] = None, scale: float = 1.0) -> str:
    """SVG path ``d``; holes become extra sub-paths (use fill-rule evenodd)."""
    if not contour_mm:
        return ""
    parts: List[str] = []
    for ring in [contour_mm, *(holes or [])]:
        if len(ring) < 3:
            continue
        parts.append(f"M {ring[0][0]*scale:.2f} {ring[0][1]*scale:.2f}")
        parts.extend(f"L {p[0]*scale:.2f} {p[1]*scale:.2f}" for p in ring[1:])
        parts.append("Z")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# One crop truth for every renderer
# ---------------------------------------------------------------------------

def cover_crop_box(src_w: Optional[float], src_h: Optional[float], frame_w: float, frame_h: float,
                   focal: Optional[List[float]] = None) -> List[float]:
    """Normalised source crop ``[left, top, right, bottom]`` that fills the
    frame without distortion ("cover"), centred on the focal point."""
    if not src_w or not src_h or frame_w <= 0 or frame_h <= 0:
        return [0.0, 0.0, 1.0, 1.0]
    fx, fy = (focal or [0.5, 0.5])[:2]
    src_ratio, frame_ratio = float(src_w) / float(src_h), float(frame_w) / float(frame_h)
    if src_ratio > frame_ratio:          # source wider: crop left/right
        span = frame_ratio / src_ratio
        left = min(max(0.0, fx - span / 2), 1.0 - span)
        return [round(left, 5), 0.0, round(left + span, 5), 1.0]
    span = src_ratio / frame_ratio       # source taller: crop top/bottom
    top = min(max(0.0, fy - span / 2), 1.0 - span)
    return [0.0, round(top, 5), 1.0, round(top + span, 5)]


def crop_pixels(size: Tuple[int, int], crop_box: Optional[List[float]]) -> Tuple[int, int, int, int]:
    w, h = size
    l, t, r, b = crop_box or [0.0, 0.0, 1.0, 1.0]
    return (int(round(l * w)), int(round(t * h)), max(int(round(l * w)) + 1, int(round(r * w))), max(int(round(t * h)) + 1, int(round(b * h))))


def extract_cropped_rings(mask_path: str, frame_w_mm: float, frame_h_mm: float, crop_box: Optional[List[float]], **kwargs) -> List[dict]:
    """Vectorise the part of the alpha mask that is visible after the crop."""
    if not crop_box or list(crop_box) == [0.0, 0.0, 1.0, 1.0]:
        return extract_alpha_rings(mask_path, frame_w_mm, frame_h_mm, **kwargs)
    try:
        import tempfile, os
        with Image.open(mask_path) as source:
            cropped = source.convert("RGBA").crop(crop_pixels(source.size, crop_box))
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            cropped.save(tmp)
            return extract_alpha_rings(tmp, frame_w_mm, frame_h_mm, **kwargs)
        finally:
            os.unlink(tmp)
    except Exception:
        return []


def photo_cutout_geometry(image, frame_w_mm: float, frame_h_mm: float) -> dict:
    """Crop + real cutout geometry for a story image placed in a frame.

    Returns ``{"crop_box", "contour", "holes", "status"}``.  The contour comes
    only from a real alpha mask (``alpha_mask_url``) or from a contour stored
    in normalised image space (0..100) at upload.  No mask → no contour.
    """
    crop = cover_crop_box(getattr(image, "width_px", None), getattr(image, "height_px", None), frame_w_mm, frame_h_mm,
                          getattr(image, "focal_point", None))
    mask = resolve_asset_path(getattr(image, "alpha_mask_url", None))
    if mask:
        rings = extract_cropped_rings(str(mask), frame_w_mm, frame_h_mm, crop)
        if rings:
            return {"crop_box": crop, "contour": rings[0]["outer"], "holes": rings[0]["holes"], "status": "mask"}
    stored = getattr(image, "contour_polygon", None)
    if stored and len(stored) >= 3:
        l, t, r, b = crop
        sw, sh = max(1e-6, r - l), max(1e-6, b - t)
        def tx(ring):
            return [[round(((p[0] / 100.0) - l) / sw * frame_w_mm, 2), round(((p[1] / 100.0) - t) / sh * frame_h_mm, 2)] for p in ring]
        holes = [tx(h) for h in (getattr(image, "contour_holes", None) or [])]
        return {"crop_box": crop, "contour": tx(stored), "holes": holes, "status": "stored_contour"}
    return {"crop_box": crop, "contour": None, "holes": [], "status": "no_mask"}
