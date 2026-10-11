import math
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import (
    SceneGraph, TitleDNA, CriticResult, CriticHardGateResult,
    CriticHeuristics, Element
)
from .transgressions import TransgressionManager
from .copyfit import estimate_text_capacity


def effective_print_dpi(elem: Element) -> Optional[float]:
    """Return the raster resolution at the element's actual print size.

    JPEG/PNG metadata commonly reports a nominal 72 DPI even for a large
    raster.  Preflight must use pixels divided by the placed frame size; the
    metadata value is only a fallback when dimensions are unavailable.
    """
    if elem.frame.w > 0 and elem.source_width_px:
        return float(elem.source_width_px) / (elem.frame.w / 25.4)
    return elem.source_dpi

class LayoutCritic:
    def __init__(self, dna: TitleDNA, corpus_features: Optional[List[Dict[str, Any]]] = None, preference_weights: Optional[Dict[str, float]] = None, corpus_guidance: Optional[Dict[str, Any]] = None):
        self.dna = dna
        self.corpus_features = corpus_features or []
        self.preference_weights = preference_weights or {}
        self.corpus_guidance = corpus_guidance or {}
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
                    elif elem.role == "headline" and fs < 14.0:
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
        if len(lead_elements) < 1:
            violations.append("Page lacks a clear dominant editorial element (no headline or photo with importance >= 0.85).")
        elif len(dominant_clusters) > 1:
            violations.append("Page has more than one dominant editorial story; hierarchy must have a single focal point.")

        # 3. Geometric Bounds & Bleed Safety
        for elem in sg.elements:
            f = elem.frame
            if f.w <= 0 or f.h <= 0:
                violations.append(f"Element {elem.id} has a non-positive frame ({f.w:.1f}x{f.h:.1f}mm).")
            # Check if text element exceeds safe margin boundaries
            if elem.role in ["headline", "body", "lead", "deck", "caption", "byline", "kicker", "band"]:
                if f.x < fmt.margin_left_mm - 2.0 or (f.x + f.w) > (page_w - fmt.margin_right_mm + 2.0):
                    violations.append(f"Text element {elem.id} ({elem.role}) breaches trim safe margins (x={f.x:.1f}, w={f.w:.1f}).")
                if f.y < fmt.margin_top_mm - 2.0 or (f.y + f.h) > (page_h - fmt.margin_bottom_mm + 2.0):
                    violations.append(f"Text element {elem.id} ({elem.role}) breaches vertical safe margins (y={f.y:.1f}, h={f.h:.1f}).")

            # Photos can bleed if treatment allows, otherwise must stay within trim + bleed
            max_x = page_w + (bleed if elem.treatment in ["full-bleed", "cutout"] else 0.0)
            max_y = page_h + (bleed if elem.treatment in ["full-bleed", "cutout"] else 0.0)
            if (f.x + f.w) > max_x + 5.0 or (f.y + f.h) > max_y + 5.0:
                violations.append(f"Element {elem.id} overflows outside page trim and bleed bounds.")

            # A newspaper column narrower than 30 mm is not printable as a
            # readable text measure.  Check the actual column measure after
            # internal gutters, not just the outer frame width.
            if elem.role in ["headline", "body", "lead", "deck", "caption", "byline", "kicker", "band"] and elem.style:
                column_count = max(1, int(elem.style.columns or 1))
                inner_gutters = max(0, column_count - 1) * fmt.margin_left_mm * 0.0
                gutter = self.dna.grid.gutter_mm
                measure = (f.w - (column_count - 1) * gutter) / column_count
                if measure < 30.0:
                    violations.append(
                        f"Text element {elem.id} has a {measure:.1f}mm column measure below the 30mm minimum."
                    )
                if elem.text_content:
                    report = estimate_text_capacity(
                        elem.text_content,
                        f.w,
                        f.h,
                        column_count,
                        elem.style.font_size_pt or self.dna.typography.scales.body,
                        elem.style.line_height_pt,
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
                if elem.text_wrap and elem.text_wrap.mode != "contour":
                    violations.append(f"Cutout photo {elem.id} must use contour text wrap.")

        # 4. Collision check outside allowed overlap scrim
        for i in range(len(sg.elements)):
            for j in range(i + 1, len(sg.elements)):
                e1 = sg.elements[i]
                e2 = sg.elements[j]
                # Skip if same element or folios/rules
                if e1.role in ["rule", "folio", "logo"] or e2.role in ["rule", "folio", "logo"]:
                    continue

                # Check bounding box overlap
                f1, f2 = e1.frame, e2.frame
                overlap_x = max(0.0, min(f1.x + f1.w, f2.x + f2.w) - max(f1.x, f2.x))
                overlap_y = max(0.0, min(f1.y + f1.h, f2.y + f2.h) - max(f1.y, f2.y))

                if overlap_x > 5.0 and overlap_y > 5.0:
                    # Allow overlap if one is photo with cutout/scrim and other is text with overlap transgression
                    is_allowed_overlap = (
                        (e1.role == "photo" or e2.role == "photo") and
                        ("overlap-scrim" in (e1.transgressions or []) or "overlap-scrim" in (e2.transgressions or []) or
                         e1.treatment == "cutout" or e2.treatment == "cutout")
                    )
                    if not is_allowed_overlap:
                        violations.append(f"Severe collision between elements '{e1.id}' ({e1.role}) and '{e2.id}' ({e2.role}).")

        # 5. Energy Budget Check
        violations.extend(self.trans_mgr.validate(sg))
        within_budget, used_energy, max_budget = self.trans_mgr.is_within_budget(sg)
        if not within_budget:
            violations.append(f"Page energy budget exceeded: {used_energy:.2f} > max allowed {max_budget:.2f}.")

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

        # Total fitness score: If hard gate fails, fitness is 0.0
        if not hard_gate.passed:
            total_fitness = 0.0
            explanation = f"Rejected: {'; '.join(hard_gate.violations[:2])}"
        else:
            w_heur = 0.60
            w_pref = 0.25 if self.preference_weights else 0.0
            w_nov = 0.15 + (0.25 if not self.preference_weights else 0.0)

            total_fitness = (
                w_heur * heuristics.composite_soft_score +
                w_nov * novelty +
                w_pref * pref_score
            )
            explanation = f"Passed: Score {total_fitness:.2f} (Balance: {heuristics.visual_balance_score:.2f}, Rhythm: {heuristics.rhythm_and_scale_score:.2f}, Novelty: {novelty:.2f})"

        return CriticResult(
            hard_gate=hard_gate,
            heuristics=heuristics,
            preference_score=round(pref_score, 3) if self.preference_weights else None,
            novelty_vs_corpus=round(novelty, 3),
            total_fitness=round(total_fitness, 3),
            explanation=explanation
        )
