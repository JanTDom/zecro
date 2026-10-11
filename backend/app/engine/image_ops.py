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

def extract_alpha_contour(
    image_path: str,
    target_w_mm: float,
    target_h_mm: float,
    threshold: int = 128,
    tolerance_mm: float = 1.5,
    min_component_ratio: float = 0.01,
) -> List[List[float]]:
    """Vectorise the real alpha mask with holes and concavities preserved.

    OpenCV's connected contour hierarchy replaces the former left/right ray
    approximation.  An unavailable or invalid asset returns an empty contour;
    callers then keep the image rectangular and expose the unavailable status.
    """
    try:
        import cv2
        img = Image.open(image_path).convert("RGBA")
        alpha = np.asarray(img.getchannel("A"))
        height, width = alpha.shape
        binary = np.where(alpha > int(threshold), 255, 0).astype(np.uint8)
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        areas = [float(cv2.contourArea(c)) for c in contours]
        total = max(1.0, float(width * height))
        roots = [i for i, area in enumerate(areas) if area / total >= float(min_component_ratio) and (hierarchy is None or hierarchy[0][i][3] < 0)]
        if not roots:
            roots = [max(range(len(contours)), key=lambda i: areas[i])]
        sx, sy = float(target_w_mm) / width, float(target_h_mm) / height
        result: list[list[float]] = []
        for root in roots:
            epsilon = max(0.25, float(tolerance_mm) / max(sx, sy))
            approx = cv2.approxPolyDP(contours[root], epsilon, True).reshape(-1, 2)
            outer = [[round(float(x) * sx, 2), round(float(y) * sy, 2)] for x, y in approx]
            if len(outer) >= 3:
                result.extend(outer)
                # Preserve hole rings as a separator marker understood by
                # SVG/IDML exporters.  Each ring begins with None in the
                # internal representation and is flattened at render time.
                child = hierarchy[0][root][2] if hierarchy is not None else -1
                while child is not None and child >= 0:
                    hole = cv2.approxPolyDP(contours[child], epsilon, True).reshape(-1, 2)
                    result.extend([[round(float(x) * sx, 2), round(float(y) * sy, 2)] for x, y in hole])
                    child = hierarchy[0][child][0] if hierarchy is not None else -1
        return result if len(result) >= 3 else []
    except Exception:
        return []

def resolve_asset_path(asset_ref: Optional[str]) -> Optional[Path]:
    """Resolve local/Supabase assets for contour extraction and preflight."""
    from .renderers.production_utils import local_asset

    return local_asset(asset_ref)

def generate_default_silhouette_contour(w_mm: float, h_mm: float) -> List[List[float]]:
    """
    Generates an organic cutout silhouette contour (head/shoulders or product silhouette).
    """
    norm_profile = [
        (0.20, 1.00),
        (0.15, 0.70),
        (0.25, 0.40),
        (0.35, 0.20),
        (0.50, 0.05),
        (0.65, 0.20),
        (0.75, 0.40),
        (0.85, 0.70),
        (0.80, 1.00)
    ]
    return [[round(u * w_mm, 2), round(v * h_mm, 2)] for u, v in norm_profile]

def offset_contour_polygon(contour_mm: List[List[float]], offset_mm: float) -> List[List[float]]:
    """Offset a contour using a geometric buffer, retaining concavities."""
    if not contour_mm or len(contour_mm) < 3:
        return contour_mm
    try:
        from shapely.geometry import Polygon
        buffered = Polygon([(float(x), float(y)) for x, y in contour_mm]).buffer(float(offset_mm), join_style=1)
        if buffered.is_empty:
            return []
        ring = list(buffered.exterior.coords)
        return [[round(float(x), 2), round(float(y), 2)] for x, y in ring]
    except Exception:
        # Geometry libraries are optional in offline deployments.  Do not
        # invent a silhouette; return the measured contour unchanged and let
        # preflight mark the offset as unavailable.
        return [list(point) for point in contour_mm]

def contour_to_css_polygon(contour_mm: List[List[float]], frame_w_mm: float, frame_h_mm: float) -> str:
    """
    Converts mm contour to CSS shape-outside / clip-path polygon percentage string.
    """
    if not contour_mm or frame_w_mm <= 0 or frame_h_mm <= 0:
        return "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)"

    pct_points = []
    for x, y in contour_mm:
        px = max(0.0, min(100.0, (x / frame_w_mm) * 100.0))
        py = max(0.0, min(100.0, (y / frame_h_mm) * 100.0))
        pct_points.append(f"{px:.1f}% {py:.1f}%")

    return f"polygon({', '.join(pct_points)})"

def contour_to_svg_path(contour_mm: List[List[float]]) -> str:
    """
    Converts mm contour points to an SVG path 'd' attribute string.
    """
    if not contour_mm:
        return ""
    d_parts = [f"M {contour_mm[0][0]:.2f} {contour_mm[0][1]:.2f}"]
    for p in contour_mm[1:]:
        d_parts.append(f"L {p[0]:.2f} {p[1]:.2f}")
    d_parts.append("Z")
    return " ".join(d_parts)
