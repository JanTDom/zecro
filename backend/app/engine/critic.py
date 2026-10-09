import math
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import (
    SceneGraph, TitleDNA, CriticResult, CriticHardGateResult,
    CriticHeuristics, Element
)
from .transgressions import TransgressionManager
from .copyfit import estimate_text_capacity

class LayoutCritic:
    def __init__(self, dna: TitleDNA, corpus_features: Optional[List[Dict[str, Any]]] = None, preference_weights: Optional[Dict[str, float]] = None):
        self.dna = dna
        self.corpus_features = corpus_features or []
        self.preference_weights = preference_weights or {}
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

        # 1. Readability & Font Sizes
        for elem in sg.elements:
            if elem.role in ["headline", "deck", "lead", "body", "caption", "kicker"]:
                fs = elem.style.font_size_pt if elem.style else None
                if fs is not None:
                    if elem.role == "body" and fs < 6.5:
                        violations.append(f"Element {elem.id} ({elem.role}) font size {fs}pt is below minimum readable 6.5pt.")
                    elif elem.role == "headline" and fs < 14.0:
                        violations.append(f"Headline {elem.id} font size {fs}pt is too small for prominent reading.")
                    elif elem.role == "caption" and fs < 5.5:
                        violations.append(f"Caption {elem.id} font size {fs}pt is below prepress legibility 5.5pt.")

        # 2. Hierarchy Check (exactly one editorial dominant; the masthead is
        # chrome and does not compete with the story hierarchy).
        lead_elements = [e for e in sg.elements if e.importance >= 0.95 and e.role in ["headline", "photo"]]
        if len(lead_elements) < 1:
            violations.append("Page lacks a clear dominant editorial element (no headline or photo with importance >= 0.85).")
        elif len(lead_elements) > 1:
            violations.append("Page has more than one dominant editorial element; hierarchy must have a single focal point.")

        # 3. Geometric Bounds & Bleed Safety
        for elem in sg.elements:
            f = elem.frame
            if f.w <= 0 or f.h <= 0:
                violations.append(f"Element {elem.id} has a non-positive frame ({f.w:.1f}x{f.h:.1f}mm).")
            # Check if text element exceeds safe margin boundaries
            if elem.role in ["headline", "body", "lead", "caption", "byline"]:
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
            if elem.role in ["body", "lead", "deck", "caption"] and elem.style:
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
                        violations.append(
                            f"Text element {elem.id} is overset by {report.overflow_ratio:.2f}x estimated capacity."
                        )

            # Source image metadata is carried by the scene graph so the
            # critic can perform a deterministic prepress gate before export.
            if elem.role == "photo" and elem.source_dpi is not None and elem.source_dpi < self.dna.photo_rules.min_dpi:
                violations.append(
                    f"Photo {elem.id} is {elem.source_dpi:.0f} dpi; minimum is {self.dna.photo_rules.min_dpi} dpi."
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
        feature_vec = self.extract_layout_feature_vector(sg)
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

        # Composite soft score
        composite = (
            0.25 * balance_score +
            0.25 * reading_gravity_score +
            0.20 * scale_score +
            0.15 * space_score +
            0.15 * tension_score
        )

        return CriticHeuristics(
            visual_balance_score=round(balance_score, 3),
            reading_gravity_score=round(reading_gravity_score, 3),
            rhythm_and_scale_score=round(scale_score, 3),
            breathing_space_score=round(space_score, 3),
            tension_adherence_score=round(tension_score, 3),
            composite_soft_score=round(composite, 3)
        )

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
        feature_vec = self.extract_layout_feature_vector(sg)
        novelty = self.compute_novelty_vs_corpus(feature_vec)

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
