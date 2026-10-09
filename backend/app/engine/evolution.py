import random
import copy
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from ..models.schemas import (
    TitleDNA, PageInputMaterial, SceneGraph, Candidate,
    Element, Frame, ElementStyle, TextWrap, Relation, PageMeta, StoryInput
)
from .grammar import LayoutGrammar
from .solver import GridSolver
from .critic import LayoutCritic
from .image_ops import generate_default_silhouette_contour, extract_alpha_contour
from .zone_solver import compose_page

class LayoutGenome:
    def __init__(self, dna: TitleDNA, style_blend: Optional[Any] = None):
        cols = dna.grid.columns
        style_blend = style_blend or dna.style_blend
        photo_bias = float(getattr(style_blend, "dense_to_photo", 0.5))
        tabloid_bias = float(getattr(style_blend, "opinion_to_tabloid", 0.35))
        # Typographic and structural gene chromosome
        self.hl_col_start: int = random.randint(0, max(0, cols - 3))
        self.hl_col_span: int = random.randint(3, cols - self.hl_col_start)
        scale_choices = [0.9, 1.0, 1.15, 1.35] if tabloid_bias >= 0.35 else [0.9, 1.0, 1.0, 1.15]
        self.hl_scale_mult: float = random.choice(scale_choices)
        rotation_choices = [0.0, 0.0, 0.0, -3.5, 3.5] if tabloid_bias >= 0.45 else [0.0, 0.0, 0.0, -2.0, 2.0]
        self.hl_rotation_deg: float = random.choice(rotation_choices)

        if random.random() < photo_bias:
            self.photo_placement: str = random.choice(["top_hero", "inline_side", "bottom_anchor", "cutout_overlap"])
        else:
            self.photo_placement = random.choice(["inline_side", "bottom_anchor", "top_hero"])
        self.photo_col_span: int = random.randint(2, min(4, cols))
        self.photo_col_start: int = random.randint(0, max(0, cols - self.photo_col_span))
        self.photo_height_ratio: float = random.uniform(0.22, 0.38)
        treatment_choices = ["crop", "cutout", "framed"] if photo_bias >= 0.35 else ["crop", "crop", "framed"]
        self.photo_treatment: str = random.choice(treatment_choices)
        self.photo_wrap_mode: str = "contour" if self.photo_treatment == "cutout" else "bounding_box"

        self.body_columns: int = random.randint(2, max(2, min(4, cols)))
        self.transgressions: List[str] = []

        # Randomly activate allowed transgressions within budget
        if self.hl_scale_mult > 1.2:
            self.transgressions.append("extreme-scale")
        if abs(self.hl_rotation_deg) > 1.0:
            self.transgressions.append("diagonal-break")
        if self.photo_treatment == "cutout":
            self.transgressions.append("cutout-wrap")

    def mutate(self, dna: TitleDNA, mutation_rate: float = 0.3):
        cols = dna.grid.columns
        if random.random() < mutation_rate:
            self.hl_col_span = random.randint(2, cols)
            self.hl_col_start = random.randint(0, max(0, cols - self.hl_col_span))

        if random.random() < mutation_rate:
            self.hl_scale_mult = random.choice([0.9, 1.0, 1.2, 1.4])

        if random.random() < mutation_rate:
            self.hl_rotation_deg = random.choice([0.0, -4.0, 4.0]) if dna.page_energy_budget >= 0.7 else 0.0

        if random.random() < mutation_rate:
            self.photo_treatment = "cutout" if (dna.photo_rules.allow_cutout and random.random() < 0.5) else "crop"
            self.photo_wrap_mode = "contour" if self.photo_treatment == "cutout" else "bounding_box"

        if random.random() < mutation_rate:
            self.photo_placement = random.choice(["top_hero", "inline_side", "bottom_anchor", "cutout_overlap"])

        if random.random() < mutation_rate:
            self.photo_col_span = random.randint(2, min(4, cols))
            self.photo_col_start = random.randint(0, max(0, cols - self.photo_col_span))

    def crossover(self, other: "LayoutGenome", dna: TitleDNA) -> "LayoutGenome":
        child = LayoutGenome(dna)
        child.hl_col_start = self.hl_col_start if random.random() < 0.5 else other.hl_col_start
        child.hl_col_span = self.hl_col_span if random.random() < 0.5 else other.hl_col_span
        child.hl_scale_mult = self.hl_scale_mult if random.random() < 0.5 else other.hl_scale_mult
        child.hl_rotation_deg = self.hl_rotation_deg if random.random() < 0.5 else other.hl_rotation_deg
        child.photo_placement = self.photo_placement if random.random() < 0.5 else other.photo_placement
        child.photo_col_span = self.photo_col_span if random.random() < 0.5 else other.photo_col_span
        child.photo_col_start = self.photo_col_start if random.random() < 0.5 else other.photo_col_start
        child.photo_treatment = self.photo_treatment if random.random() < 0.5 else other.photo_treatment
        child.photo_wrap_mode = self.photo_wrap_mode if random.random() < 0.5 else other.photo_wrap_mode
        child.body_columns = self.body_columns if random.random() < 0.5 else other.body_columns
        return child


class EvolutionaryLayoutGenerator:
    def __init__(self, dna: TitleDNA, corpus_features: Optional[List[Dict[str, Any]]] = None, preference_weights: Optional[Dict[str, float]] = None):
        self.dna = dna
        self.grammar = LayoutGrammar(dna)
        self.critic = LayoutCritic(dna, corpus_features, preference_weights)
        self.solver = GridSolver(dna)

    def decode_genome_to_scene_graph(self, genome: LayoutGenome, material: PageInputMaterial) -> SceneGraph:
        """
        Translates an abstract genome configuration into a concrete, structured SceneGraph.
        """
        if material.page_zone != "front_page":
            return compose_page(self.dna, material, {
                "variation": genome.hl_scale_mult / 1.35,
                "photo_ratio": genome.photo_height_ratio,
            })

        cols = self.dna.grid.columns
        fmt = self.dna.format
        g = self.dna.grid

        elements: List[Element] = []
        reading_order: List[str] = []
        relations: List[Relation] = []

        # Folio Banner
        folio_h_mm = 16.0
        folio_y_mm = fmt.margin_top_mm

        masthead_elem = Element(
            id="elem-masthead",
            role="logo",
            importance=1.0,
            content_ref="masthead",
            text_content=material.masthead_title or self.dna.name.upper(),
            frame=Frame(
                x=fmt.margin_left_mm,
                y=folio_y_mm,
                w=self.grammar.span_to_w_mm(cols),
                h=folio_h_mm,
                unit="mm"
            ),
            z=10,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("headline", "serif"),
                font_size_pt=32.0,
                font_weight="bold",
                align="center",
                color=self.dna.palette.primary,
                border_width_mm=1.0,
                border_color=self.dna.palette.primary,
                padding_mm=2.0
            )
        )
        elements.append(masthead_elem)
        reading_order.append(masthead_elem.id)

        dateline_text = f"{material.section_name or 'PAGE ONE'}  |  {material.issue_date or 'DAILY EDITION'}  |  {material.issue_number or 'NO. 1'}"
        folio_sub_elem = Element(
            id="elem-folio-sub",
            role="folio",
            importance=0.3,
            content_ref="folio.dateline",
            text_content=dateline_text,
            frame=Frame(
                x=fmt.margin_left_mm,
                y=folio_y_mm + folio_h_mm + 1.0,
                w=self.grammar.span_to_w_mm(cols),
                h=6.0,
                unit="mm"
            ),
            z=5,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("sans", "sans-serif"),
                font_size_pt=8.5,
                font_weight="bold",
                case="upper",
                align="justify",
                color=self.dna.palette.text,
                border_width_mm=0.5,
                border_color=self.dna.palette.primary
            )
        )
        elements.append(folio_sub_elem)

        content_top_y = folio_y_mm + folio_h_mm + 9.0
        stories = material.stories or []
        if not stories:
            stories = [
                StoryInput(
                    id="story-default",
                    kicker="INTELLIGENT COMPOSITION",
                    headline="AUTONOMOUS AESTHETIC ENGINE DELIVERS EXPERT NEWSPAPER ART DIRECTION",
                    lead="Evolutionary algorithms and deep preference modeling bring creative editorial tension to automated page design.",
                    body="By leveraging multi-objective fitness evaluation alongside strict modular constraint enforcement, the generative system crafts expressive, balanced layouts.",
                    importance=1.0
                )
            ]

        lead_story = sorted(stories, key=lambda s: s.importance, reverse=True)[0]
        sub_stories = sorted(stories, key=lambda s: s.importance, reverse=True)[1:]
        lead_members = []

        cur_y = content_top_y

        # Photo calculation
        photo_info = lead_story.images[0] if lead_story.images else None
        photo_h_mm = min(110.0, max(55.0, (fmt.trim_h_mm - content_top_y) * genome.photo_height_ratio))
        photo_w_mm = self.grammar.span_to_w_mm(genome.photo_col_span)
        photo_x_mm = self.grammar.col_to_x_mm(genome.photo_col_start)

        photo_id = None
        if photo_info and genome.photo_placement in ["top_hero", "cutout_overlap", "inline_side"]:
            photo_id = f"photo-{lead_story.id}"
            photo_treatment = photo_info.treatment or genome.photo_treatment
            contour = None
            if photo_treatment == "cutout":
                contour = photo_info.contour_polygon
                if contour is None and photo_info.alpha_mask_url and Path(photo_info.alpha_mask_url).exists():
                    contour = extract_alpha_contour(photo_info.alpha_mask_url, photo_w_mm, photo_h_mm)
                contour = contour or generate_default_silhouette_contour(photo_w_mm, photo_h_mm)

            p_y = cur_y if genome.photo_placement == "top_hero" else (cur_y + 35.0)
            photo_elem = Element(
                id=photo_id,
                role="photo",
                importance=photo_info.importance,
                content_ref=f"{lead_story.id}.photo",
                image_url=photo_info.url,
                frame=Frame(
                    x=photo_x_mm,
                    y=p_y,
                    w=photo_w_mm,
                    h=photo_h_mm,
                    unit="mm"
                ),
                z=4,
                treatment=photo_treatment,
                contour_points=contour,
                text_wrap=TextWrap(
                    mode=genome.photo_wrap_mode if photo_treatment == "cutout" else "bounding_box",
                    offset_mm=self.dna.photo_rules.text_wrap_offset_mm
                ),
                focal_point=photo_info.focal_point or [0.5, 0.4],
                mask_ref=photo_info.alpha_mask_url,
                source_dpi=photo_info.dpi,
                transgressions=["cutout-wrap"] if photo_treatment == "cutout" else []
            )
            elements.append(photo_elem)
            lead_members.append(photo_id)

            if genome.photo_placement == "top_hero":
                cur_y += photo_h_mm + 5.0

        # Kicker
        if lead_story.kicker:
            kicker_id = f"kicker-{lead_story.id}"
            kicker_elem = Element(
                id=kicker_id,
                role="kicker",
                importance=lead_story.importance * 0.9,
                content_ref=f"{lead_story.id}.kicker",
                text_content=lead_story.kicker,
                frame=Frame(
                    x=fmt.margin_left_mm,
                    y=cur_y,
                    w=self.grammar.span_to_w_mm(genome.hl_col_span),
                    h=6.0,
                    unit="mm"
                ),
                z=2,
                style=ElementStyle(
                    font_family=self.dna.typography.fonts.get("sans", "sans-serif"),
                    font_size_pt=self.dna.typography.scales.kicker,
                    font_weight="bold",
                    case="upper",
                    align="left",
                    color=self.dna.palette.secondary
                )
            )
            elements.append(kicker_elem)
            reading_order.append(kicker_id)
            lead_members.append(kicker_id)
            cur_y += 6.5

        # Headline
        hl_id = f"hl-{lead_story.id}"
        hl_w_mm = self.grammar.span_to_w_mm(genome.hl_col_span)
        hl_x_mm = self.grammar.col_to_x_mm(genome.hl_col_start)
        hl_font_size = self.dna.typography.scales.headline_l * genome.hl_scale_mult
        hl_h_mm = max(24.0, (hl_font_size * 0.75) * (3 if len(lead_story.headline) > 50 else 2))

        hl_elem = Element(
            id=hl_id,
            role="headline",
            importance=lead_story.importance,
            content_ref=f"{lead_story.id}.headline",
            text_content=lead_story.headline,
            frame=Frame(
                x=hl_x_mm,
                y=cur_y,
                w=hl_w_mm,
                h=hl_h_mm,
                unit="mm",
                rotation_deg=genome.hl_rotation_deg
            ),
            z=3,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("headline", "serif"),
                font_size_pt=round(hl_font_size, 1),
                line_height_pt=round(hl_font_size * 1.05, 1),
                font_weight="bold",
                align="left",
                color=self.dna.palette.primary
            ),
            transgressions=genome.transgressions,
            constraints=["must_dominate"]
        )
        elements.append(hl_elem)
        reading_order.append(hl_id)
        lead_members.append(hl_id)
        cur_y += hl_h_mm + 4.0

        # Lead text
        lead_w_mm = self.grammar.span_to_w_mm(min(cols, max(2, genome.hl_col_span)))
        if lead_story.lead:
            lead_id = f"lead-{lead_story.id}"
            lead_elem = Element(
                id=lead_id,
                role="lead",
                importance=lead_story.importance * 0.85,
                content_ref=f"{lead_story.id}.lead",
                text_content=lead_story.lead,
                frame=Frame(
                    x=fmt.margin_left_mm,
                    y=cur_y,
                    w=lead_w_mm,
                    h=26.0,
                    unit="mm"
                ),
                z=2,
                style=ElementStyle(
                    font_family=self.dna.typography.fonts.get("body", "serif"),
                    font_size_pt=self.dna.typography.scales.lead,
                    line_height_pt=self.dna.typography.scales.lead * 1.25,
                    font_weight="600",
                    align="left",
                    color=self.dna.palette.primary
                )
            )
            elements.append(lead_elem)
            reading_order.append(lead_id)
            lead_members.append(lead_id)
            cur_y += 28.0

        # Body Text
        body_id = f"body-{lead_story.id}"
        body_w_mm = self.grammar.span_to_w_mm(genome.body_columns)
        body_h_mm = max(45.0, (fmt.trim_h_mm - fmt.margin_bottom_mm - cur_y) * 0.85)

        body_elem = Element(
            id=body_id,
            role="body",
            importance=lead_story.importance * 0.7,
            content_ref=f"{lead_story.id}.body",
            text_content=lead_story.body,
            frame=Frame(
                x=fmt.margin_left_mm,
                y=cur_y,
                w=body_w_mm,
                h=body_h_mm,
                unit="mm"
            ),
            z=1,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("body", "serif"),
                font_size_pt=self.dna.typography.scales.body,
                line_height_pt=self.dna.typography.scales.body * 1.20,
                align="justify",
                columns=max(1, genome.body_columns)
            )
        )
        elements.append(body_elem)
        reading_order.append(body_id)
        lead_members.append(body_id)

        relations.append(Relation(
            type="belongs_to_story",
            members=lead_members,
            story=lead_story.id
        ))

        # Secondary stories sidebar (if columns remain)
        if sub_stories and cols > genome.body_columns:
            rem_col_start = genome.body_columns
            rem_span = cols - rem_col_start
            sidebar_x = self.grammar.col_to_x_mm(rem_col_start)
            sidebar_w = self.grammar.span_to_w_mm(rem_span)
            side_y = content_top_y

            for sub in sub_stories:
                sub_hl_id = f"hl-{sub.id}"
                sub_hl = Element(
                    id=sub_hl_id,
                    role="headline",
                    importance=sub.importance,
                    content_ref=f"{sub.id}.headline",
                    text_content=sub.headline,
                    frame=Frame(
                        x=sidebar_x,
                        y=side_y,
                        w=sidebar_w,
                        h=20.0,
                        unit="mm"
                    ),
                    z=2,
                    style=ElementStyle(
                        font_family=self.dna.typography.fonts.get("headline", "serif"),
                        font_size_pt=self.dna.typography.scales.headline_s,
                        line_height_pt=self.dna.typography.scales.headline_s * 1.1,
                        font_weight="bold",
                        align="left",
                        color=self.dna.palette.primary,
                        border_width_mm=0.5,
                        border_color=self.dna.palette.secondary
                    )
                )
                elements.append(sub_hl)

                sub_body_id = f"body-{sub.id}"
                sub_body = Element(
                    id=sub_body_id,
                    role="body",
                    importance=sub.importance * 0.7,
                    content_ref=f"{sub.id}.body",
                    text_content=sub.lead or (sub.body[:250] + "..."),
                    frame=Frame(
                        x=sidebar_x,
                        y=side_y + 22.0,
                        w=sidebar_w,
                        h=60.0,
                        unit="mm"
                    ),
                    z=1,
                    style=ElementStyle(
                        font_family=self.dna.typography.fonts.get("body", "serif"),
                        font_size_pt=self.dna.typography.scales.body,
                        line_height_pt=self.dna.typography.scales.body * 1.15,
                        align="left",
                        columns=1
                    )
                )
                elements.append(sub_body)
                side_y += 88.0

        # Carry editorial provenance from the material into every generated
        # text/photo element.  Geometry remains independently editable, while
        # a renderer can still trace a frame back to story/source/claim data.
        stories_by_id = {story.id: story for story in material.stories}
        for element in elements:
            if element.content_ref and "." in element.content_ref:
                story_id = element.content_ref.split(".", 1)[0]
                story = stories_by_id.get(story_id)
                if story:
                    element.story_ref = story.id
                    element.source_refs = list(getattr(story, "source_refs", []) or [])
                    element.claim_refs = list(getattr(story, "claim_refs", []) or [])
                    element.content_revision_ref = getattr(story, "content_revision_ref", None)
                    element.locked = bool(
                        getattr(story, "locked_passages", [])
                        and any(locked and locked in (element.text_content or "") for locked in story.locked_passages)
                    )
                    element.approval_status = getattr(story, "approval_status", None)

        page_meta = PageMeta(
            trim=[fmt.trim_w_mm, fmt.trim_h_mm],
            bleed_mm=fmt.bleed_mm,
            safe_margin_mm=min(fmt.margin_left_mm, fmt.margin_top_mm),
            grid={"cols": g.columns, "gutter_mm": g.gutter_mm, "baseline_mm": self.grammar.baseline_mm, "rows": g.rows},
            title_dna_ref=self.dna.id,
            page_zone=material.page_zone
        )

        return SceneGraph(
            page=page_meta,
            elements=elements,
            reading_order=reading_order,
            relations=relations,
            metadata={
                "generator": "evolutionary_generator",
                "page_zone": material.page_zone,
                "zone_template": {
                    "front_page": "masthead_teaser_dominant",
                    "spread": "verso_recto_threaded",
                    "back_page": "closing_poster_or_sport",
                }[material.page_zone],
                "text_threading": material.page_zone == "spread",
            }
        )

    def _disable_transgressions(self, scene_graph: SceneGraph) -> SceneGraph:
        """Remove optional expressive effects from a production candidate.

        ``GenerationRequest.allow_transgressions`` is an explicit caller
        choice.  Clearing only the catalog labels would be insufficient,
        because the critic also detects implicit effects (rotations, cutout
        contours, and bleed treatments).  Normalize both representations before
        scoring so a disabled request cannot accidentally emit one of them.
        """
        for element in scene_graph.elements:
            element.transgressions = []
            if abs(element.frame.rotation_deg) > 0.0:
                element.frame.rotation_deg = 0.0
            # ``extreme-scale`` is represented by the headline size rather
            # than geometry.  The regular genome range tops out at 1.15x;
            # clamp larger values after removing its catalog label.
            if element.role == "headline" and element.style and element.style.font_size_pt:
                max_regular_size = self.dna.typography.scales.headline_l * 1.15
                if element.style.font_size_pt > max_regular_size:
                    element.style.font_size_pt = max_regular_size
                    if element.style.line_height_pt:
                        element.style.line_height_pt = max_regular_size * 1.05
            if element.role == "photo" and element.treatment in {"cutout", "full-bleed"}:
                element.treatment = "crop"
                element.contour_points = None
                if element.text_wrap is not None:
                    element.text_wrap.mode = "bounding_box"
        return scene_graph

    def generate(
        self,
        material: PageInputMaterial,
        num_candidates: int = 8,
        population_size: int = 24,
        generations: int = 10,
        seed: Optional[int] = None,
        allow_transgressions: bool = True,
    ) -> List[Tuple[SceneGraph, Any]]:
        """
        Runs evolutionary exploration (multi-objective fitness + novelty + diversity).
        Returns top `num_candidates` distinct valid layouts.
        """
        if seed is not None:
            random.seed(seed)
        # 1. Initialize population.  The blend is a bias for exploration; it
        # never bypasses the grammar or critic gate.
        population: List[LayoutGenome] = [LayoutGenome(self.dna, material.style_blend) for _ in range(population_size)]

        evaluated_population = []

        for gen in range(generations):
            evaluated_population = []
            for genome in population:
                sg = self.decode_genome_to_scene_graph(genome, material)
                if not allow_transgressions:
                    sg = self._disable_transgressions(sg)
                crit_result = self.critic.evaluate(sg)

                # Solver repair if hard gate failed
                if not crit_result.hard_gate.passed:
                    sg = self.solver.solve(material, seed_transgressions=(random.random() < 0.5))
                    if not allow_transgressions:
                        sg = self._disable_transgressions(sg)
                    crit_result = self.critic.evaluate(sg)

                evaluated_population.append((genome, sg, crit_result))

            # Sort by total fitness score descending
            evaluated_population.sort(key=lambda x: x[2].total_fitness, reverse=True)

            # Selection: top 50% elites
            elites = evaluated_population[:population_size // 2]

            # Reproduction: Crossover & Mutation for next generation
            next_gen: List[LayoutGenome] = [copy.deepcopy(e[0]) for e in elites]

            while len(next_gen) < population_size:
                p1 = random.choice(elites)[0]
                p2 = random.choice(elites)[0]
                child = p1.crossover(p2, self.dna)
                child.mutate(self.dna, mutation_rate=0.35)
                next_gen.append(child)

            population = next_gen

        # Diversity selection for final output set
        # Select candidates that maximize both fitness and pairwise layout diversity
        selected_candidates: List[Tuple[SceneGraph, Any]] = []
        used_feature_vectors: List[List[float]] = []

        for genome, sg, crit in evaluated_population:
            if len(selected_candidates) >= num_candidates:
                break

            fv = self.critic.extract_layout_feature_vector(sg)

            # Ensure diversity from already selected candidates
            is_diverse = True
            for ufv in used_feature_vectors:
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(fv, ufv)))
                if dist < 0.12:  # too similar to an already selected candidate
                    is_diverse = False
                    break

            if is_diverse or len(selected_candidates) < (num_candidates // 2):
                # Record diversity score
                div_score = 1.0
                if used_feature_vectors:
                    min_d = min(math.sqrt(sum((a - b) ** 2 for a, b in zip(fv, ufv))) for ufv in used_feature_vectors)
                    div_score = min(1.0, min_d / 0.4)
                crit.diversity_in_run = round(div_score, 3)

                selected_candidates.append((sg, crit))
                used_feature_vectors.append(fv)

        # Fallback to fill up if strict diversity pruned too many
        if len(selected_candidates) < num_candidates:
            for genome, sg, crit in evaluated_population:
                if len(selected_candidates) >= num_candidates:
                    break
                if not any(id(sg) == id(item[0]) or sg.elements == item[0].elements for item in selected_candidates):
                    selected_candidates.append((sg, crit))

        while len(selected_candidates) < num_candidates:
            fallback_genome = LayoutGenome(self.dna, material.style_blend)
            fallback_sg = self.decode_genome_to_scene_graph(fallback_genome, material)
            if not allow_transgressions:
                fallback_sg = self._disable_transgressions(fallback_sg)
            crit = self.critic.evaluate(fallback_sg)
            if not crit.hard_gate.passed:
                fallback_sg = self.solver.solve(material, seed_transgressions=(random.random() < 0.5))
                if not allow_transgressions:
                    fallback_sg = self._disable_transgressions(fallback_sg)
                crit = self.critic.evaluate(fallback_sg)
            selected_candidates.append((fallback_sg, crit))

        return selected_candidates[:num_candidates]
