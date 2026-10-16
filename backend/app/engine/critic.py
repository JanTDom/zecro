import math
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import (
    SceneGraph, TitleDNA, CriticResult, CriticHardGateResult,
    CriticHeuristics, Element
)
from .transgressions import TransgressionManager
from .copyfit import estimate_text_capacity
from .display_headline import has_stranded_headline_word


def _is_locked_ad(elem: Element) -> bool:
    return bool(getattr(elem, "locked", False) and "advertisement_locked" in (elem.constraints or []))


def effective_print_dpi(elem: Element) -> Optional[float]:
    """Return the raster resolution at the element's actual print size.

    JPEG/PNG metadata commonly reports a nominal 72 DPI even for a large
    raster.  Preflight must use pixels divided by the placed frame size; the
    metadata value is only a fallback when dimensions are unavailable.
    """
    if elem.frame.w > 0 and elem.frame.h > 0 and elem.source_width_px:
        crop = elem.crop_box or [0.0, 0.0, 1.0, 1.0]
        x_fraction = max(0.0, float(crop[2]) - float(crop[0])) if len(crop) >= 4 else 1.0
        width_dpi = float(elem.source_width_px) * x_fraction / (elem.frame.w / 25.4)
        if elem.source_height_px:
            y_fraction = max(0.0, float(crop[3]) - float(crop[1])) if len(crop) >= 4 else 1.0
            height_dpi = float(elem.source_height_px) * y_fraction / (elem.frame.h / 25.4)
            return min(width_dpi, height_dpi)
        return width_dpi
    return elem.source_dpi


def _face_args(style) -> Optional[dict]:
    """Exact face (weight/italic/width) only when the style asks for one."""
    if style is None or not (getattr(style, "font_style", None) or getattr(style, "font_stretch", None)
                             or str(getattr(style, "font_weight", "") or "").isdigit()):
        return None
    from .fonts import style_face_args
    return style_face_args(style)


def cutout_geometry_issue(elem: Element) -> Optional[str]:
    """Reject masks that cannot carry a deliberate editorial silhouette.

    A contour may be technically valid while containing only a tiny fragment
    of the subject.  Such masks previously produced a mostly empty colour
    field and still passed preflight.  Measure the visible contour in its
    placed frame; this is deterministic and works for local and remote assets.
    """
    points = elem.contour_points or []
    if elem.treatment != "cutout" or len(points) < 3:
        return None
    frame_area = max(1e-6, elem.frame.w * elem.frame.h)
    # Stored contours are transformed after cover cropping and may extend
    # beyond the visible frame.  Evaluate the visible portion only.
    visible = [[max(0.0, min(elem.frame.w, p[0])),
                max(0.0, min(elem.frame.h, p[1]))] for p in points]
    area = abs(sum(visible[i][0] * visible[(i + 1) % len(visible)][1]
                   - visible[(i + 1) % len(visible)][0] * visible[i][1]
                   for i in range(len(visible))) / 2)
    xs, ys = [p[0] for p in visible], [p[1] for p in visible]
    width_ratio = (max(xs) - min(xs)) / max(1e-6, elem.frame.w)
    height_ratio = (max(ys) - min(ys)) / max(1e-6, elem.frame.h)
    coverage = area / frame_area
    if coverage < .06 or width_ratio < .18 or height_ratio < .30:
        return (f"Cutout photo {elem.id} contains only a subject fragment "
                f"(coverage {coverage:.0%}, span {width_ratio:.0%} × {height_ratio:.0%}).")
    if coverage > .88:
        return f"Cutout photo {elem.id} is effectively a rectangular image ({coverage:.0%} opaque)."
    return None


def _frame_polygon(frame, shape: str = "rect"):
    """Frame outline after rotation about its centre (same as every renderer)."""
    import math
    from .shapes import shape_polygon
    x, y, w, h = frame.x, frame.y, frame.w, frame.h
    corners = shape_polygon(shape, x, y, w, h)
    skew = float(getattr(frame, "skew_y_deg", 0.0) or 0.0)
    if abs(skew) > 0.01:
        t = math.tan(math.radians(skew))
        corners = [(px, py - (px - x) * t) for px, py in corners]
    angle = float(getattr(frame, "rotation_deg", 0.0) or 0.0)
    if abs(angle) <= 0.05:
        return corners
    r = math.radians(angle)
    cx, cy = x + w / 2, y + h / 2
    cos, sin = math.cos(r), math.sin(r)
    return [(cx + (px - cx) * cos - (py - cy) * sin, cy + (px - cx) * sin + (py - cy) * cos) for px, py in corners]


def _frame_bounds(frame) -> Tuple[float, float, float, float]:
    points = _frame_polygon(frame)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _overlap_extent(f1, f2, s1: str = "rect", s2: str = "rect") -> Tuple[float, float, float]:
    """(width, height, area) of the true overlap of two possibly rotated/shaped frames."""
    if (abs(float(f1.rotation_deg or 0)) <= .05 and abs(float(f2.rotation_deg or 0)) <= .05
            and abs(float(getattr(f1, "skew_y_deg", 0) or 0)) <= .01 and abs(float(getattr(f2, "skew_y_deg", 0) or 0)) <= .01
            and s1 in (None, "rect") and s2 in (None, "rect")):
        ox = max(0.0, min(f1.x + f1.w, f2.x + f2.w) - max(f1.x, f2.x))
        oy = max(0.0, min(f1.y + f1.h, f2.y + f2.h) - max(f1.y, f2.y))
        return ox, oy, ox * oy
    from shapely.geometry import Polygon
    inter = Polygon(_frame_polygon(f1, s1 or "rect")).intersection(Polygon(_frame_polygon(f2, s2 or "rect")))
    if inter.is_empty:
        return 0.0, 0.0, 0.0
    minx, miny, maxx, maxy = inter.bounds
    return maxx - minx, maxy - miny, float(inter.area)


def _photo_inset_allowed(inset: Element, base: Element) -> Optional[str]:
    """A deliberate photo-over-photo collage is legal only when the inset
    keeps the covered photograph's subject visible.  Returns a violation."""
    ow, oh, area = _overlap_extent(inset.frame, base.frame)
    base_area = max(1e-6, base.frame.w * base.frame.h)
    if area / base_area > .20:
        return f"Photo inset {inset.id} covers {area / base_area:.0%} of {base.id} (max 20%)."
    fx, fy = (base.focal_point or [.5, .5])[:2]
    px, py = base.frame.x + base.frame.w * float(fx), base.frame.y + base.frame.h * float(fy)
    x0, y0, x1, y1 = _frame_bounds(inset.frame)
    margin = 6.0
    if x0 - margin <= px <= x1 + margin and y0 - margin <= py <= y1 + margin:
        return f"Photo inset {inset.id} covers the subject of {base.id}."
    return None


def _largest_empty_editorial_region(sg: SceneGraph, dna: TitleDNA) -> Tuple[float, float, float]:
    """Return largest empty rectangle as (area, width, height) ratios.

    This is deliberately a coarse structural gate.  It sees frames rather
    than pixels, so intentional quiet space inside a photograph or a text box
    remains part of the composition, while a forgotten page quadrant does
    not.  A 40 x 60 grid is stable across newspaper formats and inexpensive
    enough to run for every generated candidate.
    """
    page_w, page_h = float(sg.page.trim[0]), float(sg.page.trim[1])
    left = float(dna.format.margin_left_mm)
    top = float(dna.format.margin_top_mm)
    right = page_w - float(dna.format.margin_right_mm)
    bottom = page_h - float(dna.format.margin_bottom_mm)
    usable_w, usable_h = max(1.0, right - left), max(1.0, bottom - top)
    cols, rows = 40, 60
    occupied = [[False] * cols for _ in range(rows)]
    ignored_roles = {"rule", "folio"}
    for elem in sg.elements:
        if elem.role in ignored_roles or "decorative_background" in (elem.constraints or []):
            continue
        f = elem.frame
        x0 = max(0, min(cols, int(math.floor((f.x - left) / usable_w * cols))))
        x1 = max(0, min(cols, int(math.ceil((f.x + f.w - left) / usable_w * cols))))
        y0 = max(0, min(rows, int(math.floor((f.y - top) / usable_h * rows))))
        y1 = max(0, min(rows, int(math.ceil((f.y + f.h - top) / usable_h * rows))))
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                occupied[yy][xx] = True

    heights = [0] * cols
    best_area = best_w = best_h = 0
    for yy in range(rows):
        for xx in range(cols):
            heights[xx] = 0 if occupied[yy][xx] else heights[xx] + 1
        stack: list[int] = []
        for xx in range(cols + 1):
            height = heights[xx] if xx < cols else 0
            while stack and heights[stack[-1]] > height:
                idx = stack.pop()
                h = heights[idx]
                start = stack[-1] + 1 if stack else 0
                w = xx - start
                area = w * h
                if area > best_area:
                    best_area, best_w, best_h = area, w, h
            stack.append(xx)
    return best_area / (cols * rows), best_w / cols, best_h / rows

class LayoutCritic:
    def __init__(self, dna: TitleDNA, corpus_features: Optional[List[Dict[str, Any]]] = None, preference_weights: Optional[Dict[str, float]] = None, corpus_guidance: Optional[Dict[str, Any]] = None, novelty_priority: float = 1.0):
        self.dna = dna
        self.corpus_features = corpus_features or []
        self.preference_weights = preference_weights or {}
        self.use_calibration = True
        self.corpus_guidance = corpus_guidance or {}
        self.novelty_priority = max(0.0, min(2.0, float(novelty_priority)))
        self.trans_mgr = TransgressionManager(dna.transgressions, dna.page_energy_budget)

    # ---------------------------------------------------------
    # Layer 1: Hard Pass/Fail Gate
    # ---------------------------------------------------------
    def evaluate_hard_gate(self, sg: SceneGraph) -> CriticHardGateResult:
        violations = []
        fmt = self.dna.format
        # The SceneGraph owns the concrete canvas.  A spread intentionally has
        # two trim widths, so using the single-page DNA dimensions here would
        # reject every recto frame as an out-of-bounds collision.
        page_w, page_h = (float(sg.page.trim[0]), float(sg.page.trim[1]))
        bleed = fmt.bleed_mm

        # The composer declares the editorial fields it could not bind to a
        # frame. This is a hard production failure: a compact architecture
        # may reflow copy, but it may not silently discard it.
        missing_refs = list((sg.metadata or {}).get("missing_content_refs", []) or [])
        if missing_refs:
            violations.append("Page is missing required editorial content: " + ", ".join(missing_refs[:8]))

        # 1. Readability & Font Sizes
        for elem in sg.elements:
            if elem.role in ["headline", "deck", "lead", "body", "caption", "kicker", "byline", "band"]:
                fs = elem.style.font_size_pt if elem.style else None
                if fs is not None:
                    if elem.role == "body" and fs < 6.5:
                        violations.append(f"Element {elem.id} ({elem.role}) font size {fs}pt is below minimum readable 6.5pt.")
                    elif elem.role == "headline" and fs < (10.0 if "brief" in (elem.constraints or []) else 14.0):
                        violations.append(f"Headline {elem.id} font size {fs}pt is too small for prominent reading.")
                    elif elem.role == "caption" and fs < 5.5:
                        violations.append(f"Caption {elem.id} font size {fs}pt is below prepress legibility 5.5pt.")
                    elif elem.role in {"deck", "lead"} and fs < 7.0:
                        violations.append(f"Element {elem.id} ({elem.role}) is below readable support-text size 7pt.")
                    elif elem.role == "byline" and fs < 6.0:
                        violations.append(f"Byline {elem.id} is below readable metadata size 6pt.")

        # 2. Hierarchy Check (exactly one editorial dominant; the masthead is
        # chrome and does not compete with the story hierarchy).
        lead_elements = [e for e in sg.elements if e.importance >= 0.95 and e.role in ["headline", "photo"]]
        # A hero headline and its lead photo form one editorial focal cluster.
        # Counting them as two independent dominants made every photo-bearing
        # genome fail the hard gate, so evolution fell back to the same
        # deterministic text-only solver.  Keep the single-dominant rule at
        # story-cluster level: two different stories may not both dominate,
        # while a headline/photo pair for one story is a valid front-page
        # hierarchy.
        dominant_clusters = {
            (e.story_ref or (e.content_ref.split(".", 1)[0] if e.content_ref and "." in e.content_ref else e.id))
            for e in lead_elements
        }
        listing_without_pick = ((sg.metadata or {}).get("architecture") == "tv_listing"
                                and any("navigation" in (e.constraints or []) for e in sg.elements))
        if len(lead_elements) < 1 and not listing_without_pick:
            # A schedule page without a programme of the day is navigated by
            # station tabs and hour bands; every other page needs a dominant.
            violations.append("Page lacks a clear dominant editorial element (no headline or photo with importance >= 0.85).")
        elif len(dominant_clusters) > 1:
            violations.append("Page has more than one dominant editorial story; hierarchy must have a single focal point.")

        # 3. Geometric Bounds & Bleed Safety
        for elem in sg.elements:
            f = elem.frame
            if f.w <= 0 or f.h <= 0:
                violations.append(f"Element {elem.id} has a non-positive frame ({f.w:.1f}x{f.h:.1f}mm).")
            # Check if text element exceeds safe margin boundaries
            colour_plane = elem.role == "band" and not elem.text_content  # a plate may bleed
            if (elem.role in ["headline", "body", "lead", "deck", "caption", "byline", "kicker", "band"]
                    and not _is_locked_ad(elem) and not colour_plane):
                bx0, by0, bx1, by1 = _frame_bounds(f)
                if bx0 < fmt.margin_left_mm - 2.0 or bx1 > (page_w - fmt.margin_right_mm + 2.0):
                    violations.append(f"Text element {elem.id} ({elem.role}) breaches trim safe margins (x={f.x:.1f}, w={f.w:.1f}).")
                if by0 < fmt.margin_top_mm - 2.0 or by1 > (page_h - fmt.margin_bottom_mm + 2.0):
                    violations.append(f"Text element {elem.id} ({elem.role}) breaches vertical safe margins (y={f.y:.1f}, h={f.h:.1f}).")

            # Photos can bleed if treatment allows, otherwise must stay within trim + bleed
            max_x = page_w + (bleed if elem.treatment in ["full-bleed", "cutout"] else 0.0)
            max_y = page_h + (bleed if elem.treatment in ["full-bleed", "cutout"] else 0.0)
            if (f.x + f.w) > max_x + 5.0 or (f.y + f.h) > max_y + 5.0:
                violations.append(f"Element {elem.id} overflows outside page trim and bleed bounds.")

            # A newspaper column narrower than 30 mm is not printable as a
            # readable text measure.  Check the actual column measure after
            # internal gutters, not just the outer frame width.
            if (elem.role in ["headline", "body", "lead", "deck", "caption", "byline", "kicker", "band"] and elem.style
                    and not _is_locked_ad(elem) and not colour_plane):
                column_count = max(1, int(elem.style.columns or 1))
                inner_gutters = max(0, column_count - 1) * fmt.margin_left_mm * 0.0
                gutter = self.dna.grid.gutter_mm
                measure = (f.w - (column_count - 1) * gutter) / column_count
                short_label = ("label" in (elem.constraints or []) and elem.role in {"kicker", "headline", "band"}
                               and len((elem.text_content or "").split()) <= 6)
                if measure < 30.0 and not short_label:
                    # 30 mm is the minimum measure for running text; a short
                    # sticker/stamp label (≤ 6 words) is not a text column.
                    violations.append(
                        f"Text element {elem.id} has a {measure:.1f}mm column measure below the 30mm minimum."
                    )
                if elem.text_content:
                    from .shapes import text_box
                    _, _, inner_w, inner_h = text_box(elem)
                    report = estimate_text_capacity(
                        elem.text_content,
                        inner_w,
                        inner_h,
                        column_count,
                        elem.style.font_size_pt or self.dna.typography.scales.body,
                        elem.style.line_height_pt,
                        font_family=elem.style.font_family,
                        bold=str(elem.style.font_weight) in ("bold", "600", "700", "800", "900"),
                        gutter_mm=self.dna.grid.gutter_mm,
                        face_args=_face_args(elem.style),
                        tracking_em=elem.style.tracking_em or 0.0,
                    )
                    if not report.passes:
                        reason = (
                            f"overset by {report.overflow_ratio:.2f}x estimated capacity"
                            if report.overflow_ratio > 1.0
                            else "; ".join(report.warnings) or "copyfit constraints failed"
                        )
                        violations.append(
                            f"Text element {elem.id} failed copyfit: {reason}."
                        )
                    if elem.role == "headline" and elem.importance >= .95:
                        from .fonts import resolve_font
                        from .shaper import shape_text
                        display_text = elem.text_content.upper() if elem.style.case == "upper" else elem.text_content
                        fa = _face_args(elem.style) or {"weight": 700, "italic": False, "width": None}
                        path = resolve_font(elem.style.font_family, text=display_text, weight=max(700, fa["weight"]),
                                            italic=fa["italic"], width=fa["width"])
                        shaped = shape_text(display_text, width_pt=f.w * 72 / 25.4,
                                            font_size_pt=elem.style.font_size_pt or 14,
                                            font_path=path, hyphenate=False,
                                            tracking_em=elem.style.tracking_em or 0.0)
                        if has_stranded_headline_word([line.text for line in shaped.lines]):
                            violations.append(f"Headline {elem.id} leaves a single word on its final line.")

            # Source image metadata is carried by the scene graph so the
            # critic can perform a deterministic prepress gate before export.
            photo_dpi = effective_print_dpi(elem) if elem.role == "photo" else None
            if elem.role == "photo" and photo_dpi is not None and photo_dpi < self.dna.photo_rules.min_dpi:
                violations.append(
                    f"Photo {elem.id} is {photo_dpi:.0f} effective dpi; minimum is {self.dna.photo_rules.min_dpi} dpi."
                )
            if elem.role == "photo" and elem.treatment == "cutout":
                if not elem.contour_points or len(elem.contour_points) < 3:
                    violations.append(f"Cutout photo {elem.id} has no valid clipping contour.")
                else:
                    geometry_issue = cutout_geometry_issue(elem)
                    if geometry_issue:
                        violations.append(geometry_issue)
                if elem.text_wrap and elem.text_wrap.mode != "contour":
                    violations.append(f"Cutout photo {elem.id} must use contour text wrap.")

        # 4. Collision check outside allowed overlap scrim. A composed
        # multi-line display title is one editorial treatment: its first
        # line carries the transgression budget for the whole flow group.
        overlap_groups = {e.flow_group for e in sg.elements
                          if e.flow_group and "overlap-scrim" in (e.transgressions or [])}
        layered = (sg.metadata or {}).get("composition") == "layered"
        if layered:
            # Layered covers: overlap is the norm; measured rules replace
            # the box-collision test (engine/layered_rules.py).
            from .layered_rules import layered_violations
            violations.extend(layered_violations(sg))
        for i in range(0 if layered else len(sg.elements)):
            for j in range(i + 1, len(sg.elements)):
                e1 = sg.elements[i]
                e2 = sg.elements[j]
                if "decorative_background" in (e1.constraints or []) or "decorative_background" in (e2.constraints or []):
                    continue
                # Skip if same element or folios/rules
                if e1.role in ["rule", "folio", "logo"] or e2.role in ["rule", "folio", "logo"]:
                    continue

                # Check the real (rotation-aware) overlap
                f1, f2 = e1.frame, e2.frame
                overlap_x, overlap_y, _ = _overlap_extent(f1, f2, e1.shape, e2.shape)

                if overlap_x > 5.0 and overlap_y > 5.0:
                    if _is_locked_ad(e1) or _is_locked_ad(e2):
                        continue
                    if e1.role == "photo" and e2.role == "photo":
                        inset = e1 if "intentional_photo_inset" in (e1.constraints or []) else \
                            e2 if "intentional_photo_inset" in (e2.constraints or []) else None
                        if inset is not None:
                            base = e2 if inset is e1 else e1
                            problem = _photo_inset_allowed(inset, base) if inset.z > base.z else \
                                f"Photo inset {inset.id} must sit above {base.id}."
                            if problem:
                                violations.append(problem)
                            continue
                    if ("intentional_photo_badge" in (e1.constraints or [])
                            or "intentional_photo_badge" in (e2.constraints or [])):
                        # Source-bound labels may deliberately sit on a photo.
                        # They remain bounded, copyfitted scene elements; this
                        # exception does not permit arbitrary text collisions.
                        if e1.role == "photo" or e2.role == "photo":
                            continue
                    negative = e1 if "photo_negative_space" in (e1.constraints or []) else \
                        e2 if "photo_negative_space" in (e2.constraints or []) else None
                    if negative is not None and {e1.role, e2.role} & {"photo"}:
                        photo_el = e2 if negative is e1 else e1
                        ratio = float(((sg.metadata or {}).get("negative_space_contrast") or {}).get(negative.id, 0.0))
                        fx, fy = (photo_el.focal_point or [.5, .5])[:2]
                        crop = photo_el.crop_box or [0, 0, 1, 1]
                        px = photo_el.frame.x + photo_el.frame.w * (float(fx) - crop[0]) / max(1e-6, crop[2] - crop[0])
                        py = photo_el.frame.y + photo_el.frame.h * (float(fy) - crop[1]) / max(1e-6, crop[3] - crop[1])
                        nx0, ny0, nx1, ny1 = _frame_bounds(negative.frame)
                        subject = ((sg.metadata or {}).get("photo_subject_boxes") or {}).get(photo_el.id)
                        covered = 0.0
                        if subject:
                            ix = max(0.0, min(nx1, subject[2]) - max(nx0, subject[0]))
                            iy = max(0.0, min(ny1, subject[3]) - max(ny0, subject[1]))
                            covered = ix * iy / max(1e-6, (nx1 - nx0) * (ny1 - ny0))
                        if ratio < 3.0:
                            violations.append(f"Cover line {negative.id} on a photo lacks measured contrast ({ratio:.1f}:1).")
                        elif covered > .15:
                            violations.append(f"Cover line {negative.id} covers the subject of {photo_el.id} ({covered:.0%}).")
                        elif nx0 - 8 <= px <= nx1 + 8 and ny0 - 8 <= py <= ny1 + 8:
                            violations.append(f"Cover line {negative.id} covers the subject of {photo_el.id}.")
                        continue
                    # Allow overlap if one is photo with cutout/scrim and other is text with overlap transgression
                    is_allowed_overlap = (
                        (e1.role == "photo" or e2.role == "photo") and
                        ("overlap-scrim" in (e1.transgressions or []) or "overlap-scrim" in (e2.transgressions or []) or
                         e1.treatment == "cutout" or e2.treatment == "cutout" or
                         ((e1.role == "headline" and e2.role == "photo" and e1.story_ref == e2.story_ref
                           and e1.flow_group in overlap_groups) or
                          (e2.role == "headline" and e1.role == "photo" and e2.story_ref == e1.story_ref
                           and e2.flow_group in overlap_groups)))
                    )
                    if not is_allowed_overlap:
                        violations.append(f"Severe collision between elements '{e1.id}' ({e1.role}) and '{e2.id}' ({e2.role}).")

        # 4b. Frame fill: the layout decides, the copy must fill it.  Only
        # scenes that went through the fill pass carry the contract; pending
        # AI expansions are reported as copy work, not as a finished page.
        fill_meta = (sg.metadata or {}).get("frame_fill")
        if isinstance(fill_meta, dict):
            from .frame_fill import FILL_MIN, fill_ratio
            pending = {row.get("element_id") for row in (sg.metadata or {}).get("copy_requests") or []}
            for elem in sg.elements:
                if elem.id not in fill_meta or elem.id in pending or not elem.text_content:
                    continue
                if elem.role in {"body", "deck", "lead"}:
                    ratio = fill_ratio(elem, gutter_mm=self.dna.grid.gutter_mm)
                    if ratio < FILL_MIN - .03:
                        violations.append(f"Text frame {elem.id} is only {ratio:.0%} filled (min {FILL_MIN:.0%}).")
                elif elem.role == "headline" and elem.style and (elem.style.bg_color or elem.shape not in (None, "rect")):
                    row = fill_meta.get(elem.id) or {}
                    if row.get("status") == "fitted" and max(row.get("width_fill", 1), row.get("height_fill", 1)) < .80:
                        violations.append(f"Headline {elem.id} leaves its plate under-filled.")

        # 5. Energy Budget Check (box layouts; a layered cover is governed
        # by the title kit and the measured rules above)
        violations.extend(self.trans_mgr.validate(sg))
        within_budget, used_energy, max_budget = self.trans_mgr.is_within_budget(sg)
        if not within_budget and (sg.metadata or {}).get("composition") != "layered":
            violations.append(f"Page energy budget exceeded: {used_energy:.2f} > max allowed {max_budget:.2f}.")

        # Popular covers are intentionally dense.  A forgotten quadrant is a
        # production defect, not tasteful whitespace.  Keep this in the hard
        # gate so a numerically balanced but visibly unfinished page can never
        # be labelled as a correct composition.
        architecture = str((sg.metadata or {}).get("architecture", ""))
        if architecture in {"popular_collage", "popular_poster", "popular_type"}:
            empty_area, empty_w, empty_h = _largest_empty_editorial_region(sg, self.dna)
            if empty_area > 0.16 and empty_w > 0.28 and empty_h > 0.30:
                violations.append(
                    "Popular cover contains a large uncomposed empty region "
                    f"({empty_area * 100:.0f}% of the printable area)."
                )

        # Near duplicates are a hard anti-copying failure, rather than a
        # soft score that can be outweighed by visual heuristics.
        # Novelty compares the same normalized measurements as the corpus
        # index (grid, type rhythm, image/text balance and page zone), rather
        # than comparing those measurements with a geometry-only fingerprint.
        feature_vec = self.extract_corpus_feature_vector(sg)
        novelty = self.compute_novelty_vs_corpus(feature_vec)
        if self.corpus_features and novelty < 0.08:
            violations.append(f"Layout is too close to a corpus page (novelty {novelty:.2f}).")

        return CriticHardGateResult(
            passed=(len(violations) == 0),
            violations=violations
        )

    # ---------------------------------------------------------
    # Layer 2: Soft Taste Heuristics
    # ---------------------------------------------------------
    def evaluate_heuristics(self, sg: SceneGraph) -> CriticHeuristics:
        page_w, page_h = (float(sg.page.trim[0]), float(sg.page.trim[1]))
        total_page_area = page_w * page_h

        # 1. Visual Balance (Optical Center of Mass)
        # Target optical center is roughly at [0.5 * W, 0.42 * H]
        target_cx = 0.5 * page_w
        target_cy = 0.42 * page_h

        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        occupied_area = 0.0

        for elem in sg.elements:
            f = elem.frame
            elem_area = f.w * f.h
            # A frame is not ink. Long-running text may legitimately have a
            # large box, while a short brief must not make a mostly blank page
            # look densely occupied. Estimate visible ink from the same line
            # model used by the hard copyfit gate.
            if elem.text_content and elem.style and elem.role not in {"logo", "folio", "rule"}:
                report = estimate_text_capacity(
                    elem.text_content, f.w, f.h, max(1, int(elem.style.columns or 1)),
                    elem.style.font_size_pt or self.dna.typography.scales.body,
                    elem.style.line_height_pt,
                )
                ink_ratio = min(1.0, max(0.06, report.estimated_lines / max(1, report.capacity_lines)))
                elem_area *= ink_ratio
            occupied_area += elem_area
            # Weight is a function of area, importance, and visual density (photos & headlines are heavy)
            role_density = 1.5 if elem.role in ["photo", "headline"] else (1.0 if elem.role == "lead" else 0.7)
            elem_weight = elem_area * elem.importance * role_density
            elem_cx = f.x + f.w / 2.0
            elem_cy = f.y + f.h / 2.0

            total_weight += elem_weight
            weighted_x += elem_cx * elem_weight
            weighted_y += elem_cy * elem_weight

        if total_weight > 0:
            actual_cx = weighted_x / total_weight
            actual_cy = weighted_y / total_weight
            dist_norm = math.hypot((actual_cx - target_cx) / page_w, (actual_cy - target_cy) / page_h)
            balance_score = max(0.0, 1.0 - dist_norm * 2.5)
        else:
            balance_score = 0.5

        # 2. Reading Gravity Flow (Downward reading continuity)
        reading_order = sg.reading_order or [e.id for e in sg.elements if e.role in ["headline", "lead", "body"]]
        elem_map = {e.id: e for e in sg.elements}
        flow_penalties = 0.0
        step_count = 0

        for idx in range(len(reading_order) - 1):
            id_curr = reading_order[idx]
            id_next = reading_order[idx + 1]
            if id_curr in elem_map and id_next in elem_map:
                e1 = elem_map[id_curr]
                e2 = elem_map[id_next]
                # In natural western reading flow, subsequent element should be below or to the right
                dy = e2.frame.y - e1.frame.y
                if dy < -10.0:  # jump upwards is penalized
                    flow_penalties += abs(dy) / page_h
                step_count += 1

        reading_gravity_score = max(0.0, 1.0 - (flow_penalties / max(1, step_count)))

        # 3. Rhythm & Scale Contrast
        font_sizes = [e.style.font_size_pt for e in sg.elements if e.style and e.style.font_size_pt]
        if font_sizes:
            max_font = max(font_sizes)
            min_font = min(font_sizes)
            contrast_ratio = max_font / max(1.0, min_font)
            # Ideal contrast ratio between 3.0 and 8.0
            if 3.0 <= contrast_ratio <= 8.5:
                scale_score = 1.0
            else:
                scale_score = max(0.2, 1.0 - abs(contrast_ratio - 5.0) * 0.15)
        else:
            scale_score = 0.7

        # 4. Breathing Whitespace Ratio (Ideal ~ 15% to 30% whitespace)
        coverage_ratio = min(1.0, occupied_area / total_page_area)
        whitespace_ratio = 1.0 - coverage_ratio
        if 0.12 <= whitespace_ratio <= 0.35:
            space_score = 1.0
        else:
            space_score = max(0.0, 1.0 - abs(whitespace_ratio - 0.22) * 4.0)

        # 5. Tension Adherence
        used_energy, _ = self.trans_mgr.calculate_page_energy(sg)
        budget = self.dna.page_energy_budget
        tension_score = max(0.0, 1.0 - abs(used_energy - (0.75 * budget)) / max(0.1, budget))

        # 6. Alignment with measured corpus priors.  This is a style signal,
        # never a template lookup: only aggregate statistics are used.
        corpus_alignment = self.evaluate_corpus_alignment(sg)

        # Composite soft score
        composite = (
            0.22 * balance_score +
            0.22 * reading_gravity_score +
            0.18 * scale_score +
            0.14 * space_score +
            0.14 * tension_score +
            0.10 * corpus_alignment
        )

        return CriticHeuristics(
            visual_balance_score=round(balance_score, 3),
            reading_gravity_score=round(reading_gravity_score, 3),
            rhythm_and_scale_score=round(scale_score, 3),
            breathing_space_score=round(space_score, 3),
            tension_adherence_score=round(tension_score, 3),
            corpus_alignment_score=round(corpus_alignment, 3),
            composite_soft_score=round(composite, 3)
        )

    def extract_corpus_feature_vector(self, sg: SceneGraph) -> List[float]:
        """Build the canonical ten-dimensional vector used by FEATURE_INDEX."""
        page_w, page_h = float(sg.page.trim[0]), float(sg.page.trim[1])
        page_area = max(1.0, page_w * page_h)
        body = next((e for e in sg.elements if e.role == "body"), None)
        headlines = [e for e in sg.elements if e.role == "headline" and e.style and e.style.font_size_pt]
        photos = [e for e in sg.elements if e.role == "photo"]
        text_roles = {"headline", "deck", "lead", "body", "caption", "kicker", "byline", "pullquote", "infobox"}
        text_area = 0.0
        for e in sg.elements:
            if e.role not in text_roles:
                continue
            area = max(0.0, e.frame.w * e.frame.h)
            if e.text_content and e.style:
                report = estimate_text_capacity(
                    e.text_content, e.frame.w, e.frame.h, max(1, int(e.style.columns or 1)),
                    e.style.font_size_pt or self.dna.typography.scales.body,
                    e.style.line_height_pt,
                )
                area *= min(1.0, max(0.06, report.estimated_lines / max(1, report.capacity_lines)))
            text_area += area
        photo_area = sum(max(0.0, e.frame.w * e.frame.h) for e in photos)
        body_size = float(body.style.font_size_pt if body and body.style and body.style.font_size_pt else self.dna.typography.scales.body)
        headline_size = max((float(e.style.font_size_pt) for e in headlines), default=self.dna.typography.scales.headline_l)
        ratio = headline_size / max(1.0, body_size)
        photo_pct = max(0.0, min(100.0, photo_area / page_area * 100.0))
        text_pct = max(0.0, min(100.0, text_area / page_area * 100.0))
        zone_value = {"front_page": 0.0, "spread": 0.5, "back_page": 1.0}.get(sg.page.page_zone, 0.5)
        return [
            round(max(0.0, min(1.0, float(self.dna.grid.columns) / 12.0)), 4),
            round(max(0.0, min(1.0, self.dna.grid.gutter_mm / 14.0)), 4),
            round(max(0.0, min(1.0, self.dna.grid.baseline_grid_pt / 16.0)), 4),
            round(max(0.0, min(1.0, ratio / 8.5)), 4),
            round(max(0.0, min(1.0, body_size / 14.0)), 4),
            round(photo_pct / 100.0, 4),
            round(text_pct / 100.0, 4),
            round(zone_value, 4),
            round(max(0.0, min(1.0, (ratio - 2.0) / 7.0)), 4),
            round(photo_pct / 100.0 * max(0.0, 1.0 - text_pct / 100.0), 4),
        ]

    def evaluate_corpus_alignment(self, sg: SceneGraph) -> float:
        """Score distance to aggregate DNA priors from Supabase/local index."""
        guidance = self.corpus_guidance
        if not guidance or not guidance.get("sample_count"):
            return 0.5
        vector = self.extract_corpus_feature_vector(sg)
        target = [
            float(guidance.get("columns_mean", self.dna.grid.columns)) / 12.0,
            float(guidance.get("gutter_mm_mean", self.dna.grid.gutter_mm)) / 14.0,
            float(guidance.get("baseline_grid_pt_mean", self.dna.grid.baseline_grid_pt)) / 16.0,
            float(guidance.get("headline_scale_ratio_mean", 4.5)) / 8.5,
            float(guidance.get("body_size_pt_mean", self.dna.typography.scales.body)) / 14.0,
            float(guidance.get("photo_coverage_pct_mean", 35.0)) / 100.0,
            float(guidance.get("text_coverage_pct_mean", 60.0)) / 100.0,
            {"front_page": 0.0, "spread": 0.5, "back_page": 1.0}.get(sg.page.page_zone, 0.5),
            max(0.0, min(1.0, (float(guidance.get("headline_scale_ratio_mean", 4.5)) - 2.0) / 7.0)),
            float(guidance.get("photo_coverage_pct_mean", 35.0)) / 100.0 * max(0.0, 1.0 - float(guidance.get("text_coverage_pct_mean", 60.0)) / 100.0),
        ]
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, target)) / len(vector))
        return max(0.0, min(1.0, 1.0 - distance * 2.5))

    # ---------------------------------------------------------
    # Novelty & Diversity Calculation
    # ---------------------------------------------------------
    def extract_layout_feature_vector(self, sg: SceneGraph) -> List[float]:
        """
        Extracts a compact numerical layout fingerprint (positions, spans, counts, areas).
        """
        fmt = self.dna.format
        pw, ph = fmt.trim_w_mm, fmt.trim_h_mm

        hl = next((e for e in sg.elements if e.role == "headline" and e.importance >= 0.8), None)
        photo = next((e for e in sg.elements if e.role == "photo"), None)

        hl_x = (hl.frame.x / pw) if hl else 0.0
        hl_y = (hl.frame.y / ph) if hl else 0.0
        hl_w = (hl.frame.w / pw) if hl else 0.0
        hl_h = (hl.frame.h / ph) if hl else 0.0

        photo_x = (photo.frame.x / pw) if photo else 0.0
        photo_y = (photo.frame.y / ph) if photo else 0.0
        photo_w = (photo.frame.w / pw) if photo else 0.0
        photo_h = (photo.frame.h / ph) if photo else 0.0
        is_cutout = 1.0 if (photo and photo.treatment == "cutout") else 0.0

        used_energy, _ = self.trans_mgr.calculate_page_energy(sg)

        return [
            round(hl_x, 3), round(hl_y, 3), round(hl_w, 3), round(hl_h, 3),
            round(photo_x, 3), round(photo_y, 3), round(photo_w, 3), round(photo_h, 3),
            is_cutout, round(used_energy, 3)
        ]

    def extract_strategy_feature_vector(self, sg: SceneGraph) -> List[float]:
        """Semantic fingerprint used for diversity selection.

        The preference model keeps its compact ten-feature contract stable.
        Diversity needs a separate representation so a different reading
        architecture is not mistaken for a rotated copy of the same page.
        """
        metadata = sg.metadata or {}
        mode = str(metadata.get("layout_mode", ""))
        placement = str(metadata.get("photo_placement", ""))
        photo = next((e for e in sg.elements if e.role == "photo"), None)
        treatment = str(photo.treatment if photo else "none")
        dominant = next((e for e in sg.elements if e.role == "headline" and e.importance >= .95), None)
        page_w, page_h = sg.page.trim
        modes = ["dominant-left", "dominant-right", "stacked", "photo-top", "type-led", "modular-grid"]
        placements = ["top_hero", "inline_side", "bottom_anchor", "cutout_overlap"]
        treatments = ["crop", "cutout", "framed"]
        used_energy, _ = self.trans_mgr.calculate_page_energy(sg)
        return (
            [1.0 if mode == item else 0.0 for item in modes]
            + [1.0 if placement == item else 0.0 for item in placements]
            + [1.0 if treatment == item else 0.0 for item in treatments]
            + [round(min(1.0, max(0.0, used_energy / max(0.1, self.dna.page_energy_budget))), 3)]
            + [round(photo.frame.x / page_w, 3) if photo else 0.0,
               round(photo.frame.w / page_w, 3) if photo else 0.0,
               round(dominant.frame.y / page_h, 3) if dominant else 0.0,
               round(dominant.frame.w / page_w, 3) if dominant else 0.0]
        )

    def compute_novelty_vs_corpus(self, feature_vector: List[float]) -> float:
        """
        Computes minimum Euclidean distance to all corpus page feature vectors.
        Penalizes near-duplicates (distance < 0.15).
        """
        if not self.corpus_features:
            return 1.0  # Fresh original design

        min_dist = float("inf")
        fv_a = feature_vector
        for cf in self.corpus_features:
            fv_b = cf.get("vector") or []
            if len(fv_a) == len(fv_b):
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(fv_a, fv_b)))
                if dist < min_dist:
                    min_dist = dist

        # Normalize distance to 0..1 scale, where > 0.4 is completely distinct
        return min(1.0, min_dist / 0.5)

    # ---------------------------------------------------------
    # Full Critic Evaluation
    # ---------------------------------------------------------
    def evaluate(self, sg: SceneGraph) -> CriticResult:
        hard_gate = self.evaluate_hard_gate(sg)
        heuristics = self.evaluate_heuristics(sg)
        novelty = self.compute_novelty_vs_corpus(self.extract_corpus_feature_vector(sg))
        # Keep the established geometry fingerprint for the preference model;
        # only corpus novelty uses the canonical measured-index vector.
        feature_vec = self.extract_layout_feature_vector(sg)

        # Preference reward model component
        pref_score = 0.0
        if self.preference_weights:
            # Linear dot product of feature vector and learned preference weights
            for idx, w in enumerate(feature_vec):
                key = f"feat_{idx}"
                pref_score += self.preference_weights.get(key, 0.0) * w
            pref_score = 1.0 / (1.0 + math.exp(-pref_score))  # Sigmoid 0..1

        # Archetype calibration learned from A/B pairs (see critic_calibration).
        calibration_value = None
        if hard_gate.passed and self.use_calibration:
            from .critic_calibration import calibrated_score, calibration_features, load_calibration
            calibration = load_calibration(getattr(self.dna, "archetype", None))
            if calibration:
                calibration_value = calibrated_score(calibration, calibration_features(sg, self))

        # Total fitness score: If hard gate fails, fitness is 0.0
        if not hard_gate.passed:
            total_fitness = 0.0
            explanation = f"Rejected: {'; '.join(hard_gate.violations[:2])}"
        else:
            w_heur = 0.60
            w_pref = 0.25 if self.preference_weights else 0.0
            w_nov = (0.15 + (0.25 if not self.preference_weights else 0.0)) * self.novelty_priority

            w_cal = 0.0
            if calibration_value is not None:
                # The calibrated preference replaces most of the hand-written
                # prior; the prior keeps a voice for what pairs never covered.
                w_heur, w_cal = 0.30, 0.30
            total_fitness = (
                w_heur * heuristics.composite_soft_score +
                w_cal * (calibration_value or 0.0) +
                w_nov * novelty +
                w_pref * pref_score
            )
            explanation = f"Passed: Score {total_fitness:.2f} (Balance: {heuristics.visual_balance_score:.2f}, Rhythm: {heuristics.rhythm_and_scale_score:.2f}, Novelty: {novelty:.2f})"

        return CriticResult(
            hard_gate=hard_gate,
            heuristics=heuristics,
            preference_score=round(pref_score, 3) if self.preference_weights else None,
            calibrated_score=calibration_value,
            novelty_vs_corpus=round(novelty, 3),
            total_fitness=round(total_fitness, 3),
            explanation=explanation
        )
