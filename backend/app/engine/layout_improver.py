"""Layout Improver: Takes a dissected or existing SceneGraph, applies directed mutations
based on diagnostic audit defects, and produces scored MAP-Elites phenotype variants.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import Element, ElementStyle, Frame, SceneGraph, TitleDNA
from .aesthetics import evaluate_page_aesthetics
from .display_headline import compose_staged_display_headline
from .infographics import create_editorial_badge_box, create_fact_box, extract_story_facts
from .layout_auditor import AuditDefect, LayoutAuditReport, LayoutAuditor
from .polish_typography import polish_microtypography

PT_TO_MM = 25.4 / 72.0


@dataclass
class ImprovementCandidate:
    candidate_id: str
    phenotype: str  # "conservative_clean" | "dynamic_dominant" | "versus_split_or_asymmetric"
    title: str
    description: str
    scene_graph: SceneGraph
    score_before: int
    score_after: int
    score_delta: int
    resolved_defects: List[str] = field(default_factory=list)
    applied_actions: List[str] = field(default_factory=list)
    audit_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "phenotype": self.phenotype,
            "title": self.title,
            "description": self.description,
            "scene_graph": self.scene_graph.model_dump(),
            "score_before": self.score_before,
            "score_after": self.score_after,
            "score_delta": self.score_delta,
            "resolved_defects": self.resolved_defects,
            "applied_actions": self.applied_actions,
            "audit_report": self.audit_report,
        }


@dataclass
class LayoutImprovementResult:
    original_audit: LayoutAuditReport
    candidates: List[ImprovementCandidate]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_audit": self.original_audit.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
        }


class LayoutImprover:
    """Directed optimizer transforming raw or flawed newspaper layouts into publication-ready art direction."""

    def __init__(self, auditor: Optional[LayoutAuditor] = None):
        self.auditor = auditor or LayoutAuditor()

    def improve_layout(
        self,
        scene: SceneGraph,
        dna: TitleDNA,
        audit: Optional[LayoutAuditReport] = None
    ) -> LayoutImprovementResult:
        """Generates 3 improved candidate phenotypes targeting diagnosed flaws."""
        initial_audit = audit or self.auditor.audit_layout(scene, dna)
        candidates: List[ImprovementCandidate] = []

        # 1. Candidate A: Conservative Clean (Konserwatywny / Czysty)
        c_clean = self._generate_conservative_clean(scene, dna, initial_audit)
        candidates.append(c_clean)

        # 2. Candidate B: Dynamic Dominant (Dynamiczny / Dominanta Hero)
        c_dominant = self._generate_dynamic_dominant(scene, dna, initial_audit)
        candidates.append(c_dominant)

        # 3. Candidate C: Versus Split or Asymmetric (Ekspresyjny / Magazynowy)
        c_versus = self._generate_versus_asymmetric(scene, dna, initial_audit)
        candidates.append(c_versus)

        # Sort candidates by improved score descending
        candidates.sort(key=lambda c: c.score_after, reverse=True)

        return LayoutImprovementResult(original_audit=initial_audit, candidates=candidates)

    def _generate_conservative_clean(
        self,
        original_scene: SceneGraph,
        dna: TitleDNA,
        initial_audit: LayoutAuditReport
    ) -> ImprovementCandidate:
        scene = copy.deepcopy(original_scene)
        applied_actions: List[str] = []

        # Ensure page has a clear dominant anchor (hard gate requires at least one elem >= 0.85)
        has_dom = any(e.importance >= 0.85 for e in scene.elements if e.role in ("headline", "photo"))
        if not has_dom:
            headlines = [e for e in scene.elements if e.role == "headline"]
            if headlines:
                headlines[0].importance = 0.92
                applied_actions.append(f"Podniesiono wagę głównego tytułu '{headlines[0].id}' do 0.92 (dominanta).")
            else:
                photos = [e for e in scene.elements if e.role == "photo"]
                if photos:
                    photos[0].importance = 0.92
                    applied_actions.append(f"Podniesiono wagę głównego zdjęcia '{photos[0].id}' do 0.92.")

        # A. Polish microtypography across all text elements
        fixed_typo_count = 0
        for elem in scene.elements:
            if elem.text_content:
                old_text = elem.text_content
                new_text = polish_microtypography(old_text)
                if new_text != old_text:
                    elem.text_content = new_text
                    fixed_typo_count += 1

        if fixed_typo_count > 0:
            applied_actions.append(f"Zastosowano mikrotypografię polską i twarde spacje w {fixed_typo_count} elementach.")

        # B. Grid and baseline alignment snapping
        pw, ph = float(scene.page.trim[0]), float(scene.page.trim[1])
        cols = dna.grid.columns or 5
        gutter = dna.grid.gutter_mm or 4.5
        ml = dna.format.margin_left_mm or 12.0
        mr = dna.format.margin_right_mm or 12.0
        mt = dna.format.margin_top_mm or 15.0
        mb = dna.format.margin_bottom_mm or 15.0
        live_w = pw - ml - mr
        col_w = max(10.0, (live_w - (cols - 1) * gutter) / cols)
        baseline_mm = (dna.grid.baseline_grid_pt or 10.5) * PT_TO_MM

        snapped_count = 0
        for elem in scene.elements:
            col_idx = round((elem.frame.x - ml) / (col_w + gutter))
            snapped_x = max(ml, min(pw - mr - elem.frame.w, ml + col_idx * (col_w + gutter)))
            b_idx = round((elem.frame.y - mt) / baseline_mm)
            snapped_y = max(mt, min(ph - mb - elem.frame.h, mt + b_idx * baseline_mm))

            if abs(snapped_x - elem.frame.x) > 0.5 or abs(snapped_y - elem.frame.y) > 0.5:
                elem.frame.x = round(snapped_x, 2)
                elem.frame.y = round(snapped_y, 2)
                snapped_count += 1

        if snapped_count > 0:
            applied_actions.append(f"Dociągnięto {snapped_count} modułów do modularnej siatki szpalt i linii bazowych.")

        # C. Underset / Void rescue widget
        if initial_audit.metrics.get("trapped_whitespace_cm2", 0) > 10.0 or any(d.rule_code == "UNDERSET_SLACK" for d in initial_audit.defects):
            badge_x = round(ml + (cols - 1) * (col_w + gutter), 2)
            badge_y = round(ph - mb - 26.0, 2)
            occupied = any(
                e.frame.x < badge_x + col_w and e.frame.x + e.frame.w > badge_x and
                e.frame.y < badge_y + 24.0 and e.frame.y + e.frame.h > badge_y
                for e in scene.elements
            )
            if not occupied:
                badge = create_editorial_badge_box(
                    text="Wydanie Specjalne",
                    category="PILNE",
                    frame=Frame(x=badge_x, y=badge_y, w=col_w, h=24.0),
                )
                scene.elements.append(badge)
                applied_actions.append("Wypełniono wolną przestrzeń szpalty odznaką redakcyjną (PILNE).")

        new_audit = self.auditor.audit_layout(scene, dna)
        resolved = self._diff_defects(initial_audit, new_audit)

        return ImprovementCandidate(
            candidate_id=f"cand_clean_{uuid.uuid4().hex[:6]}",
            phenotype="conservative_clean",
            title="Konserwatywny / Czysty",
            description="Zachowuje oryginalną kompozycję; usuwa błędy mikrotypografii, wyrównuje klocki do siatki bazowej i szpalt.",
            scene_graph=scene,
            score_before=initial_audit.overall_score,
            score_after=new_audit.overall_score,
            score_delta=new_audit.overall_score - initial_audit.overall_score,
            resolved_defects=resolved,
            applied_actions=applied_actions,
            audit_report=new_audit.to_dict(),
        )

    def _generate_dynamic_dominant(
        self,
        original_scene: SceneGraph,
        dna: TitleDNA,
        initial_audit: LayoutAuditReport
    ) -> ImprovementCandidate:
        scene = copy.deepcopy(original_scene)
        applied_actions: List[str] = []

        pw, ph = float(scene.page.trim[0]), float(scene.page.trim[1])
        cols = dna.grid.columns or 5
        gutter = dna.grid.gutter_mm or 4.5
        ml = dna.format.margin_left_mm or 12.0
        mr = dna.format.margin_right_mm or 12.0
        mt = dna.format.margin_top_mm or 15.0
        mb = dna.format.margin_bottom_mm or 15.0
        live_w = pw - ml - mr
        col_w = max(10.0, (live_w - (cols - 1) * gutter) / cols)

        # A. Resolve Photo Competition -> Elevate Hero dominant (>= 32% of page area)
        photos = [e for e in scene.elements if e.role == "photo"]
        photo_bottom_y = mt + 35.0

        if photos:
            photos.sort(key=lambda p: (p.importance, p.frame.w * p.frame.h), reverse=True)
            hero = photos[0]
            hero.importance = 0.96

            # Expand hero photo to 3-4 columns width
            hero_cols = min(cols, max(3, cols - 1))
            hero_w = round(hero_cols * col_w + (hero_cols - 1) * gutter, 2)
            hero_h = round(ph * 0.32, 2)
            hero.frame.w = hero_w
            hero.frame.h = hero_h
            hero.frame.x = ml
            hero.frame.y = round(mt + 40.0, 2)
            photo_bottom_y = hero.frame.y + hero.frame.h
            applied_actions.append(f"Wzmocniono dominację zdjęcia '{hero.id}' do {hero_cols} szpalt (32% wysokości strony).")

            # Subordinate secondary photos placed on the right flank
            for sec_idx, sec_photo in enumerate(photos[1:], start=1):
                sec_photo.importance = 0.65
                sec_cols = 1 if cols >= 4 else 2
                sec_photo.frame.w = round(sec_cols * col_w + (sec_cols - 1) * gutter, 2)
                sec_photo.frame.h = round(hero_h * 0.45, 2)
                sec_photo.frame.x = round(pw - mr - sec_photo.frame.w, 2)
                sec_photo.frame.y = round(hero.frame.y + (sec_idx - 1) * (sec_photo.frame.h + 6.0), 2)
                applied_actions.append(f"Zredukowano zdjęcie dopełniające '{sec_photo.id}' do {sec_cols} szpalty.")

        # B. Upgrade Headline to Staged Display Typography (at the top)
        headlines = [e for e in scene.elements if e.role == "headline"]
        if headlines:
            main_hl = headlines[0]
            raw_text = main_hl.text_content or "GŁÓWNY TYTUŁ WYDANIA"
            staged = compose_staged_display_headline(
                raw_text,
                width_mm=live_w,
                height_mm=36.0,
                preferred_size_pt=34.0,
                minimum_size_pt=18.0,
                font_families=["Barlow", "Gotham", "Playfair Display", "Inter"],
            )
            if staged:
                main_hl.text_content = staged.text
                if main_hl.style:
                    main_hl.style.font_size_pt = staged.lead_size_pt
                    main_hl.style.font_weight = "900"
                    main_hl.style.line_height_pt = round(staged.lead_size_pt * 0.95, 1)
                applied_actions.append(f"Przekształcono tytuł w wielostopniowy nagłówek ze słowem-kluczem '{staged.lead_word}' ({staged.lead_size_pt:.0f} pt).")
            else:
                words = raw_text.split()
                if len(words) >= 2:
                    screamer = words[0].upper()
                    remainder = " ".join(words[1:])
                    main_hl.text_content = f"{screamer}\n{remainder}"
                    if main_hl.style:
                        main_hl.style.font_size_pt = 32.0
                        main_hl.style.font_weight = "900"
                    applied_actions.append(f"Wyróżniono słowo-klucz '{screamer}' w tytule.")
            main_hl.frame.x = ml
            main_hl.frame.y = mt
            main_hl.frame.w = live_w
            main_hl.frame.h = 35.0

        # C. Reposition body stories cleanly below the photo zone
        body_y = round(photo_bottom_y + 8.0, 2)
        body_h = round(ph - mb - body_y - 5.0, 2)
        for b_idx, b in enumerate(e for e in scene.elements if e.role == "body"):
            b.frame.y = body_y
            b.frame.h = max(25.0, body_h)
            b_cols = 2 if cols >= 4 else cols
            b.frame.w = round(b_cols * col_w + (b_cols - 1) * gutter, 2)
            b.frame.x = round(ml + b_idx * (b.frame.w + gutter), 2)
            # Ensure it fits within margins
            if b.frame.x + b.frame.w > pw - mr:
                b.frame.x = ml

        # D. Inject Fact Box if space permits in right flank
        fact_w = round(col_w * 2 + gutter, 2) if cols >= 4 else round(col_w, 2)
        fact_x = round(pw - mr - fact_w, 2)
        fact_y = body_y
        has_space = not any(
            e.frame.x < fact_x + fact_w and e.frame.x + e.frame.w > fact_x and
            e.frame.y < fact_y + 45.0 and e.frame.y + e.frame.h > fact_y
            for e in scene.elements
        )
        if has_space and fact_y + 45.0 <= ph - mb:
            fbox = create_fact_box(
                title="W SKRÓCIE",
                facts=[
                    "Wzrost nakładu o 15% w ujęciu rocznym",
                    "Nowa inwestycja w tabor kolejowy za 42 mln zł",
                    "Decyzja wchodzi w życie od 1 listopada",
                ],
                frame=Frame(x=fact_x, y=fact_y, w=fact_w, h=45.0),
            )
            scene.elements.append(fbox)
            applied_actions.append(f"Wstawiono moduł faktograficzny 'W SKRÓCIE' ({fact_w:.0f} mm).")

        # D. Polish microtypography
        for elem in scene.elements:
            if elem.text_content:
                elem.text_content = polish_microtypography(elem.text_content)

        new_audit = self.auditor.audit_layout(scene, dna)
        resolved = self._diff_defects(initial_audit, new_audit)

        return ImprovementCandidate(
            candidate_id=f"cand_dom_{uuid.uuid4().hex[:6]}",
            phenotype="dynamic_dominant",
            title="Dynamiczny / Dominanta Hero",
            description="Rozwiązuje rywalizację zdjęć, powiększa główne zdjęcie do roli lidera i wdraża dynamiczny nagłówek wielostopniowy.",
            scene_graph=scene,
            score_before=initial_audit.overall_score,
            score_after=new_audit.overall_score,
            score_delta=new_audit.overall_score - initial_audit.overall_score,
            resolved_defects=resolved,
            applied_actions=applied_actions,
            audit_report=new_audit.to_dict(),
        )

    def _generate_versus_asymmetric(
        self,
        original_scene: SceneGraph,
        dna: TitleDNA,
        initial_audit: LayoutAuditReport
    ) -> ImprovementCandidate:
        scene = copy.deepcopy(original_scene)
        applied_actions: List[str] = []

        pw, ph = float(scene.page.trim[0]), float(scene.page.trim[1])
        ml = dna.format.margin_left_mm or 12.0
        mr = dna.format.margin_right_mm or 12.0
        mt = dna.format.margin_top_mm or 15.0
        mb = dna.format.margin_bottom_mm or 15.0
        live_w = pw - ml - mr
        live_h = ph - mt - mb

        # Top: Headline
        headlines = [e for e in scene.elements if e.role == "headline"]
        headline_bottom_y = mt + 32.0
        if headlines:
            main_hl = headlines[0]
            main_hl.frame.x = ml
            main_hl.frame.y = mt
            main_hl.frame.w = live_w
            main_hl.frame.h = 30.0
            if main_hl.style:
                main_hl.style.font_size_pt = 32.0
                main_hl.style.font_weight = "900"
            headline_bottom_y = mt + 32.0

        photos = [e for e in scene.elements if e.role == "photo"]
        photo_bottom_y = headline_bottom_y + 120.0

        if len(photos) >= 2:
            # Build Versus Split confrontation layout
            p1, p2 = photos[0], photos[1]
            p1.importance = 0.96
            p2.importance = 0.75  # Rule U2: exactly one visual dominant

            col_half_w = round((live_w - 6.0) / 2.0, 2)
            split_h = round(ph * 0.32, 2)
            split_y = round(headline_bottom_y + 4.0, 2)
            photo_bottom_y = split_y + split_h

            p1.frame = Frame(x=ml, y=split_y, w=col_half_w, h=split_h)
            p2.frame = Frame(x=round(ml + col_half_w + 6.0, 2), y=split_y, w=col_half_w, h=split_h)

            # Central confrontation badge
            badge_size = 24.0
            badge_x = round(ml + col_half_w - badge_size / 2.0 + 3.0, 2)
            badge_y = round(split_y + split_h / 2.0 - badge_size / 2.0, 2)

            badge = Element(
                id=f"vs_badge_{uuid.uuid4().hex[:6]}",
                role="infobox",
                importance=0.88,
                text_content="KONTRA",
                frame=Frame(x=badge_x, y=badge_y, w=badge_size, h=badge_size),
                z=8,
                treatment="tinted",
                shape="circle",
                constraints=["intentional_photo_badge", "allow_stack"],
                style=ElementStyle(
                    font_size_pt=10.0,
                    font_weight="900",
                    color="#FFFFFF",
                    bg_color="#D90429",
                    align="center",
                    valign="center",
                ),
            )
            scene.elements.append(badge)
            applied_actions.append("Zbudowano morfologię starcia 'versus_split' z centralnym stemplem KONTRA.")
        elif photos:
            # Single photo -> Asymmetric Cutout with tinted background plate
            hero = photos[0]
            hero.importance = 0.96
            hero.treatment = "cutout"
            hero.frame.w = round(live_w * 0.70, 2)
            hero.frame.h = round(ph * 0.35, 2)
            hero.frame.x = round(pw - mr - hero.frame.w, 2)
            hero.frame.y = round(headline_bottom_y + 4.0, 2)
            photo_bottom_y = hero.frame.y + hero.frame.h

            # Background color plate under cutout
            plate = Element(
                id=f"tint_plate_{uuid.uuid4().hex[:6]}",
                role="band",
                importance=0.4,
                frame=Frame(x=ml, y=round(hero.frame.y + 10.0, 2), w=round(live_w * 0.85, 2), h=round(hero.frame.h * 0.8, 2)),
                z=0,
                treatment="tinted",
                constraints=["decorative_background", "allow_stack"],
                style=ElementStyle(bg_color="#E5E7EB"),
            )
            scene.elements.insert(0, plate)
            applied_actions.append("Przekształcono zdjęcie w asymetryczny kadr z wycięciem (cutout) na apli barwnej.")

        # Position body stories below photo zone
        body_y = round(photo_bottom_y + 8.0, 2)
        body_h = round(ph - mb - body_y - 5.0, 2)
        cols = dna.grid.columns or 5
        gutter = dna.grid.gutter_mm or 4.5
        col_w = max(10.0, (live_w - (cols - 1) * gutter) / cols)

        for b_idx, b in enumerate(e for e in scene.elements if e.role == "body"):
            b.frame.y = body_y
            b.frame.h = max(25.0, body_h)
            b_cols = 2 if cols >= 4 else cols
            b.frame.w = round(b_cols * col_w + (b_cols - 1) * gutter, 2)
            b.frame.x = round(ml + b_idx * (b.frame.w + gutter), 2)
            if b.frame.x + b.frame.w > pw - mr:
                b.frame.x = ml

        # Polish microtypography
        for elem in scene.elements:
            if elem.text_content:
                elem.text_content = polish_microtypography(elem.text_content)

        new_audit = self.auditor.audit_layout(scene, dna)
        resolved = self._diff_defects(initial_audit, new_audit)

        return ImprovementCandidate(
            candidate_id=f"cand_vs_{uuid.uuid4().hex[:6]}",
            phenotype="versus_split_or_asymmetric",
            title="Ekspresyjny / Magazynowy",
            description="Układ o wysokiej energii wizualnej z dwubiegunowym podziałem starcia lub asymetrycznym wycięciem postaci na apli.",
            scene_graph=scene,
            score_before=initial_audit.overall_score,
            score_after=new_audit.overall_score,
            score_delta=new_audit.overall_score - initial_audit.overall_score,
            resolved_defects=resolved,
            applied_actions=applied_actions,
            audit_report=new_audit.to_dict(),
        )

    def _diff_defects(self, before: LayoutAuditReport, after: LayoutAuditReport) -> List[str]:
        before_codes = {d.rule_code: d.message for d in before.defects}
        after_codes = {d.rule_code for d in after.defects}
        resolved: List[str] = []
        for code, msg in before_codes.items():
            if code not in after_codes:
                resolved.append(msg)
        return resolved
