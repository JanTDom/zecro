"""Aesthetics and Visual Perception Engine for Press and Editorial Layouts.

Synthesizes three world-class paradigms:
1. Xerox PARC Aesthetic Measures (Stephen Harrington et al.):
   - Optical mass and visual balance (moments of visual weight about page axes)
   - Visual equilibrium (optical centre vs geometric centre)
   - Gestalt alignment rhythm (simplicity of vertical and horizontal structural lines)
2. Sophi.io (The Globe and Mail / Naviga):
   - Trapped whitespace detection (distinguishing intentional outer margin/air
     from accidental interior voids trapped between content blocks)
3. Poynter Institute Eyetrack Research (Mario Garcia, Pegie Stark):
   - Unambiguous visual entry point (anchor dominant)
   - Gaze vector alignment (subjects looking inwards towards copy, never outward into the trim)
   - Bottom visual anchor (grounding the page to prevent floating/unsettled perception)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict
from ..models.schemas import Element, Frame, SceneGraph


# Optical density factors per role and treatment (visual weight per mm^2)
ROLE_DENSITY = {
    "photo": 1.0,           # heavy visual mass, high contrast
    "logo": 0.85,          # strong brand identity
    "band": 0.80,          # solid colour plate/tint block
    "plate": 0.80,
    "kicker": 0.70,        # uppercase, bold accent
    "headline": 0.65,      # display typography
    "jump_line": 0.40,
    "deck": 0.40,
    "lead": 0.35,
    "caption": 0.30,
    "byline": 0.25,
    "body": 0.22,          # light grey texture in visual perception
    "folio": 0.15,
    "rule": 0.20,
}


@dataclass
class AestheticReport:
    balance_score: float             # 0..1 (1.0 = perfect lateral balance)
    equilibrium_score: float       # 0..1 (1.0 = optical centre at optimal ~45% height)
    rhythm_score: float            # 0..1 (1.0 = clean, unified alignment axes)
    trapped_whitespace_cm2: float  # cm^2 of trapped interior white space
    trapped_whitespace_score: float# 0..1 (1.0 = no trapped interior void)
    entry_point_score: float       # 0..1 (1.0 = unambiguous dominant entry point)
    gaze_alignment_score: float    # 0..1 (1.0 = subjects look inwards towards copy)
    bottom_anchor_score: float     # 0..1 (1.0 = solidly anchored footer)
    total_aesthetic_index: float   # 0..1 weighted master index
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


def element_optical_weight(elem: Element) -> float:
    """Calculates the perceptual visual weight (mass) of an element in arbitrary units."""
    f = elem.frame
    area = max(0.0, f.w * f.h)
    density = ROLE_DENSITY.get(elem.role, 0.3)

    if elem.role == "photo":
        # Full bleed and cutouts carry distinct visual impact
        if elem.treatment == "cutout":
            density *= 1.15
        elif elem.treatment == "full-bleed":
            density *= 1.05
    elif elem.role in ("headline", "kicker"):
        fs = (elem.style.font_size_pt if elem.style else None) or 14.0
        # Larger display type exerts disproportionately higher gravitational pull
        density *= min(2.5, max(0.8, math.sqrt(fs / 14.0)))

    return area * density


def calculate_visual_balance(sg: SceneGraph) -> Tuple[float, float, float]:
    """Calculates Xerox PARC lateral balance and optical centre.

    Returns:
        (balance_score, optical_cx, optical_cy)
        balance_score in [0..1], 1.0 being balanced left-to-right.
    """
    pw, ph = float(sg.page.trim[0]), float(sg.page.trim[1])
    cx, cy = pw / 2.0, ph / 2.0

    total_weight = 0.0
    weighted_x = 0.0
    weighted_y = 0.0

    for elem in sg.elements:
        if "decorative_background" in (elem.constraints or []):
            continue
        w = element_optical_weight(elem)
        if w <= 0:
            continue
        total_weight += w
        elem_cx = elem.frame.x + elem.frame.w / 2.0
        elem_cy = elem.frame.y + elem.frame.h / 2.0
        weighted_x += w * elem_cx
        weighted_y += w * elem_cy

    if total_weight <= 0:
        return 1.0, cx, cy

    opt_x = weighted_x / total_weight
    opt_y = weighted_y / total_weight

    # Lateral balance: normalized horizontal displacement from centre
    lateral_delta = abs(opt_x - cx) / (pw / 2.0)
    balance_score = max(0.0, 1.0 - lateral_delta * 1.5)

    return round(balance_score, 3), round(opt_x, 2), round(opt_y, 2)


def calculate_visual_equilibrium(opt_y: float, page_h: float) -> float:
    """Psychological optical centre in classic editorial design sits at ~44-46% of page height.

    A layout whose optical mass sits slightly above vertical geometric centre feels
    natural and stable; one whose mass sits too low feels heavy and sinking.
    """
    ideal_y = page_h * 0.45
    delta = abs(opt_y - ideal_y) / (page_h * 0.45)
    return round(max(0.0, 1.0 - delta), 3)


def calculate_alignment_rhythm(sg: SceneGraph, tol_mm: float = 2.0) -> Tuple[float, int, int]:
    """Measures Gestalt alignment simplicity (Xerox PARC alignment count).

    Pages with fewer, clear vertical and horizontal alignment lines feel disciplined and calm;
    pages with myriad scattered coordinates feel accidental.
    """
    x_coords: List[float] = []
    y_coords: List[float] = []

    content_elements = [
        e for e in sg.elements
        if e.role in ("photo", "headline", "body", "lead", "band", "plate", "kicker")
        and e.frame.w >= 10.0 and e.frame.h >= 5.0
        and not getattr(e.frame, "rotation_deg", 0)
        and not getattr(e.frame, "skew_y_deg", 0)
    ]

    if len(content_elements) < 3:
        return 1.0, 0, 0

    for e in content_elements:
        f = e.frame
        x_coords.extend([f.x, f.x + f.w])
        y_coords.extend([f.y, f.y + f.h])

    def cluster_coords(coords: List[float]) -> int:
        coords.sort()
        clusters = 0
        last = -999.0
        for c in coords:
            if c - last > tol_mm:
                clusters += 1
                last = c
        return clusters

    num_x_lines = cluster_coords(x_coords)
    num_y_lines = cluster_coords(y_coords)
    n = len(content_elements)

    # Ideal ratio: alignment lines should be significantly fewer than 2 * element count
    # (indicating strong column grid adherence and shared baseline/cap edges).
    max_lines = max(1.0, 2.0 * n)
    ratio_x = min(1.0, num_x_lines / max_lines)
    ratio_y = min(1.0, num_y_lines / max_lines)
    rhythm = max(0.0, 1.0 - (ratio_x * 0.5 + ratio_y * 0.5))

    return round(rhythm, 3), num_x_lines, num_y_lines


def detect_trapped_whitespace(sg: SceneGraph, grid_step_mm: float = 6.0) -> Tuple[float, List[Dict[str, float]]]:
    """Detects Sophi.io-style trapped interior whitespace pockets.

    Trapped whitespace occurs when an empty cell is enclosed on opposite sides by content,
    isolated from the outer margins. Outer margins and bleed edges are NOT trapped.
    """
    pw, ph = float(sg.page.trim[0]), float(sg.page.trim[1])
    cols = max(10, int(pw / grid_step_mm))
    rows = max(15, int(ph / grid_step_mm))
    cell_w = pw / cols
    cell_h = ph / rows
    cell_area_cm2 = (cell_w * cell_h) / 100.0

    # 0 = empty, 1 = occupied
    grid = [[0 for _ in range(cols)] for _ in range(rows)]

    for e in sg.elements:
        if "decorative_background" in (e.constraints or []):
            continue
        if e.role in ("rule", "folio") and (e.frame.w < 2.0 or e.frame.h < 2.0):
            continue
        f = e.frame
        c0 = max(0, min(cols - 1, int(f.x / cell_w)))
        c1 = max(0, min(cols - 1, int((f.x + f.w) / cell_w)))
        r0 = max(0, min(rows - 1, int(f.y / cell_h)))
        r1 = max(0, min(rows - 1, int((f.y + f.h) / cell_h)))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                grid[r][c] = 1

    # Flood-fill from outer perimeter to identify open whitespace connected to borders
    # 2 = connected to exterior margin/bleed (safe whitespace)
    visited = [[False for _ in range(cols)] for _ in range(rows)]
    queue: List[Tuple[int, int]] = []

    for c in range(cols):
        if grid[0][c] == 0:
            queue.append((0, c)); visited[0][c] = True
        if grid[rows - 1][c] == 0:
            queue.append((rows - 1, c)); visited[rows - 1][c] = True

    for r in range(rows):
        if grid[r][0] == 0 and not visited[r][0]:
            queue.append((r, 0)); visited[r][0] = True
        if grid[r][cols - 1] == 0 and not visited[r][cols - 1]:
            queue.append((r, cols - 1)); visited[r][cols - 1] = True

    while queue:
        r, c = queue.pop(0)
        grid[r][c] = 2
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if not visited[nr][nc] and grid[nr][nc] == 0:
                    visited[nr][nc] = True
                    queue.append((nr, nc))

    # Remaining 0s are trapped inside content boundaries!
    trapped_clusters: List[Dict[str, float]] = []
    cluster_visited = [[False for _ in range(cols)] for _ in range(rows)]

    total_trapped_cm2 = 0.0

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 0 and not cluster_visited[r][c]:
                # Discover cluster
                c_queue = [(r, c)]
                cluster_visited[r][c] = True
                cells = []
                while c_queue:
                    cr, cc = c_queue.pop(0)
                    cells.append((cr, cc))
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if not cluster_visited[nr][nc] and grid[nr][nc] == 0:
                                cluster_visited[nr][nc] = True
                                c_queue.append((nr, nc))

                cluster_cm2 = len(cells) * cell_area_cm2
                if cluster_cm2 >= 1.5:  # filter micro jitter (< 1.5 cm^2)
                    min_x = min(cc for _, cc in cells) * cell_w
                    max_x = (max(cc for _, cc in cells) + 1) * cell_w
                    min_y = min(cr for cr, _ in cells) * cell_h
                    max_y = (max(cr for cr, _ in cells) + 1) * cell_h
                    trapped_clusters.append({
                        "area_cm2": round(cluster_cm2, 1),
                        "x": round(min_x, 1),
                        "y": round(min_y, 1),
                        "w": round(max_x - min_x, 1),
                        "h": round(max_y - min_y, 1),
                    })
                    total_trapped_cm2 += cluster_cm2

    return round(total_trapped_cm2, 1), trapped_clusters


def evaluate_entry_point(sg: SceneGraph) -> Tuple[float, Optional[str]]:
    """Evaluates Poynter Eyetrack entry point clarity.

    A great front page provides exactly ONE unmistakable initial focal point.
    If two lead elements have identical visual weight, or no element dominates,
    the reader's eye wanders in confusion.
    """
    candidates: List[Tuple[float, Element]] = []
    for e in sg.elements:
        if e.role in ("photo", "headline") and e.importance >= 0.70:
            w = element_optical_weight(e)
            candidates.append((w, e))

    if not candidates:
        return 0.2, None

    candidates.sort(key=lambda t: t[0], reverse=True)
    lead_weight, lead_elem = candidates[0]

    if len(candidates) == 1:
        return 1.0, lead_elem.id

    second_weight, second_elem = candidates[1]

    # Ratio of dominant element to secondary element
    ratio = lead_weight / max(1.0, second_weight)

    # If top photo and top headline belong to the same lead story, they form a cohesive cluster
    lead_story = lead_elem.story_ref
    second_story = second_elem.story_ref
    if lead_story and second_story and lead_story == second_story:
        return 1.0, f"cluster:{lead_story}"

    if ratio >= 1.4:
        score = 1.0
    elif ratio >= 1.15:
        score = 0.8
    else:
        # Two competing dominants from different stories confuse entry
        score = 0.4

    return round(score, 2), lead_elem.id


def evaluate_gaze_direction(sg: SceneGraph) -> Tuple[float, List[str]]:
    """Evaluates Poynter Gaze Guidance rule.

    Portraits positioned on page flanks must look inwards towards the spine/centre.
    A subject on the far left looking left, or on the far right looking right, directs
    the reader's eyes out of the publication (a known editorial visual flaw).
    """
    pw = float(sg.page.trim[0])
    issues: List[str] = []
    penalties = 0.0
    evaluated = 0

    for e in sg.elements:
        if e.role != "photo":
            continue
        gaze = (getattr(e, "photo_analysis", None) or {}).get("gaze_direction")
        if not gaze or gaze in ("camera", "up", "down", "none"):
            continue

        evaluated += 1
        elem_cx = e.frame.x + e.frame.w / 2.0

        # On the left third of page, gaze looking 'left' looks off-page
        if elem_cx < pw * 0.35 and gaze == "left":
            issues.append(f"Photo {e.id} on left flank gazes off-page left; should face inwards towards copy.")
            penalties += 0.35
        # On the right third of page, gaze looking 'right' looks off-page
        elif elem_cx > pw * 0.65 and gaze == "right":
            issues.append(f"Photo {e.id} on right flank gazes off-page right; should face inwards towards copy.")
            penalties += 0.35

    score = max(0.0, 1.0 - penalties)
    return round(score, 2), issues


def evaluate_bottom_anchor(sg: SceneGraph) -> float:
    """Evaluates Poynter Bottom Anchor presence.

    A page needs grounding at its base (a strip, modular teaser box, or weighted footer)
    so content does not feel like it floats or terminates prematurely.
    """
    pw, ph = float(sg.page.trim[0]), float(sg.page.trim[1])
    footer_zone_y = ph * 0.80

    bottom_mass = 0.0
    for e in sg.elements:
        if "decorative_background" in (e.constraints or []):
            continue
        if e.frame.y + e.frame.h >= footer_zone_y:
            bottom_mass += element_optical_weight(e)

    page_area = pw * ph
    # Healthy bottom zone contains at least 8-15% of optical weight
    anchor_ratio = bottom_mass / max(1.0, page_area * 0.15)
    return round(min(1.0, max(0.2, anchor_ratio)), 2)


def evaluate_page_aesthetics(sg: SceneGraph) -> AestheticReport:
    """Calculates comprehensive aesthetic score synthesizing Xerox PARC, Sophi.io, and Poynter."""
    pw, ph = float(sg.page.trim[0]), float(sg.page.trim[1])

    # 1. Xerox PARC Balance & Equilibrium
    bal_score, opt_cx, opt_cy = calculate_visual_balance(sg)
    eq_score = calculate_visual_equilibrium(opt_cy, ph)
    rhythm_score, lines_x, lines_y = calculate_alignment_rhythm(sg)

    # 2. Sophi.io Trapped Whitespace
    trapped_cm2, trapped_clusters = detect_trapped_whitespace(sg)
    # 0 cm^2 = 1.0; 25 cm^2 trapped void drops score to 0.4
    trapped_score = max(0.0, 1.0 - (trapped_cm2 / 30.0))

    # 3. Poynter Visual Perception
    entry_score, dominant_id = evaluate_entry_point(sg)
    gaze_score, gaze_issues = evaluate_gaze_direction(sg)
    anchor_score = evaluate_bottom_anchor(sg)

    # Weighted master index
    # - Balance & Equilibrium: 25%
    # - Trapped whitespace avoidance: 25%
    # - Entry point clarity: 20%
    # - Bottom anchor: 15%
    # - Alignment rhythm: 15%
    total = (
        bal_score * 0.15
        + eq_score * 0.10
        + trapped_score * 0.25
        + entry_score * 0.20
        + anchor_score * 0.15
        + rhythm_score * 0.15
    )
    if gaze_score < 1.0:
        total *= (0.85 + 0.15 * gaze_score)

    total = round(max(0.0, min(1.0, total)), 3)

    recommendations: List[str] = []
    if trapped_cm2 > 10.0:
        recommendations.append(f"Zlikwiduj uwięzioną biel ({trapped_cm2:.1f} cm²) między modułami: rozszerz sąsiedni moduł.")
    if bal_score < 0.65:
        recommendations.append(f"Popraw równowagę optyczną (środek x={opt_cx:.1f}mm z {pw:.1f}mm): przenieś akcent na przeciwną flankę.")
    if entry_score < 0.70:
        recommendations.append("Brak wyraźnego punktu wejścia: wzmocnij skalę głównego zdjęcia lub tytułu.")
    if anchor_score < 0.60:
        recommendations.append("Słaba kotwica dolna: dół strony sprawia wrażenie niedomkniętego.")
    recommendations.extend(gaze_issues)

    details = {
        "optical_center_mm": [opt_cx, opt_cy],
        "alignment_lines": {"x": lines_x, "y": lines_y},
        "trapped_clusters": trapped_clusters,
        "entry_dominant_id": dominant_id,
        "gaze_issues": gaze_issues,
    }

    return AestheticReport(
        balance_score=bal_score,
        equilibrium_score=eq_score,
        rhythm_score=rhythm_score,
        trapped_whitespace_cm2=trapped_cm2,
        trapped_whitespace_score=round(trapped_score, 2),
        entry_point_score=entry_score,
        gaze_alignment_score=gaze_score,
        bottom_anchor_score=anchor_score,
        total_aesthetic_index=total,
        details=details,
        recommendations=recommendations,
    )
