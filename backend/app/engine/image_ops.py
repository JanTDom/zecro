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
    tolerance_mm: float = 1.5
) -> List[List[float]]:
    """
    Extracts a vector contour polygon from an image with alpha transparency.
    Returns normalized coordinates relative to frame in mm [[x_mm, y_mm], ...].
    """
    try:
        img = Image.open(image_path).convert("RGBA")
        alpha = np.array(img.split()[-1])
        h, w = alpha.shape

        # Binary mask
        mask = (alpha > threshold).astype(np.uint8)

        # Sample contour along vertical and horizontal rays
        step_y = max(1, h // 40)
        left_edges = []
        right_edges = []

        for y in range(0, h, step_y):
            row = mask[y, :]
            active = np.where(row > 0)[0]
            if len(active) > 0:
                x_left = active[0]
                x_right = active[-1]
                left_edges.append((float(x_left), float(y)))
                right_edges.append((float(x_right), float(y)))

        if not left_edges:
            return generate_default_silhouette_contour(target_w_mm, target_h_mm)

        # Combine clockwise loop
        raw_contour = left_edges + list(reversed(right_edges))
        raw_contour.append(raw_contour[0])

        # Convert pixel to mm
        scale_x = target_w_mm / float(w)
        scale_y = target_h_mm / float(h)
        mm_points = [(p[0] * scale_x, p[1] * scale_y) for p in raw_contour]

        # Simplify
        simplified = simplify_douglas_peucker(mm_points, tolerance_mm)
        return [[round(x, 2), round(y, 2)] for x, y in simplified]

    except Exception:
        # Fallback if file not accessible
        return generate_default_silhouette_contour(target_w_mm, target_h_mm)


def resolve_asset_path(asset_ref: Optional[str]) -> Optional[Path]:
    """Resolve a local asset reference while keeping remote URLs untouched.

    Segmenters only run on files available to the local process.  API uploads
    provide an absolute path; ``None`` is returned for HTTP/data references so
    callers can use a deterministic fallback contour.
    """
    if not asset_ref or asset_ref.startswith(("http://", "https://", "data:", "inline:")):
        return None
    path = Path(asset_ref).expanduser()
    return path if path.is_file() else None

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
    """
    Offsets/dilates a polygon outwards by offset_mm for text wrap runaround.
    """
    if not contour_mm or len(contour_mm) < 3:
        return contour_mm

    cx = sum(p[0] for p in contour_mm) / len(contour_mm)
    cy = sum(p[1] for p in contour_mm) / len(contour_mm)

    offset_poly = []
    for x, y in contour_mm:
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)
        if dist > 0.001:
            scale = (dist + offset_mm) / dist
            nx = cx + dx * scale
            ny = cy + dy * scale
        else:
            nx = x + offset_mm
            ny = y + offset_mm
        offset_poly.append([round(nx, 2), round(ny, 2)])

    return offset_poly

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
