from typing import List, Dict, Any, Optional
import uuid
import math
from ..models.schemas import (
    TitleDNA, PageInputMaterial, SceneGraph, PageMeta,
    Element, Frame, ElementStyle, TextWrap, Relation, StoryInput
)
from .grammar import LayoutGrammar
from .image_ops import extract_alpha_contour, generate_default_silhouette_contour
from pathlib import Path

class GridSolver:
    def __init__(self, dna: TitleDNA):
        self.dna = dna
        self.grammar = LayoutGrammar(dna)

    def solve(self, material: PageInputMaterial, seed_transgressions: bool = False) -> SceneGraph:
        """
        Deterministic grid solver that lays out the given material strictly on the modular grid.
        """
        cols = self.dna.grid.columns
        rows = self.dna.grid.rows
        fmt = self.dna.format
        g = self.dna.grid

        elements: List[Element] = []
        reading_order: List[str] = []
        relations: List[Relation] = []

        # 1. Page Folio / Masthead Banner (Row 0)
        folio_h_mm = 16.0
        folio_y_mm = fmt.margin_top_mm

        # Masthead Logo / Title
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

        # Folio Dateline Rule
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
        remaining_h = fmt.trim_h_mm - fmt.margin_bottom_mm - content_top_y

        stories = material.stories or []
        if not stories:
            # Create a placeholder story if none provided
            stories = [
                StoryInput(
                    id="story-main",
                    kicker="BREAKING EXCLUSIVE",
                    headline="HISTORIC DISCOVERY RESHAPES MODERN GENERATIVE DESIGN",
                    deck="Artificial intelligence engines achieve unprecedented typographic harmony and aesthetic precision in newsprint automation.",
                    byline="BY ALEXANDER VANE, SENIOR EDITOR",
                    lead="In a landmark milestone for computational editorial design, the newly unveiled studio balances strict modular grid constraints with high-tension expressive transgressions.",
                    body="Newspaper production has historically demanded a meticulous balance between rigid column grids and artistic spontaneity. Editorial designers have spent centuries refining baseline grids, type scales, and optical balance.\n\nWith contemporary multi-objective optimization and deep aesthetic preference modeling, layouts can now be synthesized on the fly without sacrificing typographical discipline. The engine respects gutters, margins, and column counts while selectively employing silhouetted cutouts and contour runarounds.",
                    importance=1.0
                )
            ]

        # Sort stories by editorial importance descending
        sorted_stories = sorted(stories, key=lambda s: s.importance, reverse=True)
        lead_story = sorted_stories[0]
        sub_stories = sorted_stories[1:]

        # -----------------------------------------------------------------
        # Lead Story Layout
        # -----------------------------------------------------------------
        lead_story_members = []
        cur_y = content_top_y

        # Kicker (Lead Story)
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
                    w=self.grammar.span_to_w_mm(min(cols, 4)),
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
            lead_story_members.append(kicker_id)
            cur_y += 7.0

        # Headline (Lead Story - spans almost full page or 4 cols)
        hl_span_cols = min(cols, 4 if sub_stories else cols)
        hl_h = 28.0 if len(lead_story.headline) < 40 else 38.0
        hl_id = f"hl-{lead_story.id}"
        hl_elem = Element(
            id=hl_id,
            role="headline",
            importance=lead_story.importance,
            content_ref=f"{lead_story.id}.headline",
            text_content=lead_story.headline,
            frame=Frame(
                x=fmt.margin_left_mm,
                y=cur_y,
                w=self.grammar.span_to_w_mm(hl_span_cols),
                h=hl_h,
                unit="mm"
            ),
            z=3,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("headline", "serif"),
                font_size_pt=self.dna.typography.scales.headline_l,
                line_height_pt=self.dna.typography.scales.headline_l * 1.05,
                font_weight="bold",
                align="left",
                color=self.dna.palette.primary
            ),
            constraints=["must_dominate"]
        )
        elements.append(hl_elem)
        reading_order.append(hl_id)
        lead_story_members.append(hl_id)
        cur_y += hl_h + 3.0

        # Byline (Lead Story)
        if lead_story.byline:
            byline_id = f"byline-{lead_story.id}"
            byline_elem = Element(
                id=byline_id,
                role="byline",
                importance=0.4,
                content_ref=f"{lead_story.id}.byline",
                text_content=lead_story.byline,
                frame=Frame(
                    x=fmt.margin_left_mm,
                    y=cur_y,
                    w=self.grammar.span_to_w_mm(hl_span_cols),
                    h=5.0,
                    unit="mm"
                ),
                z=2,
                style=ElementStyle(
                    font_family=self.dna.typography.fonts.get("sans", "sans-serif"),
                    font_size_pt=self.dna.typography.scales.byline,
                    font_weight="bold",
                    case="upper",
                    align="left",
                    color="#666666"
                )
            )
            elements.append(byline_elem)
            lead_story_members.append(byline_id)
            cur_y += 6.5

        # Photo for Lead Story (if available)
        main_photo = lead_story.images[0] if lead_story.images else None
        photo_id = None
        photo_w = 0.0
        photo_h = 0.0

        if main_photo:
            photo_span_cols = 3 if cols >= 5 else 2
            photo_w = self.grammar.span_to_w_mm(photo_span_cols)
            photo_h = 95.0

            treatment = main_photo.treatment or ("cutout" if (main_photo.is_cutout_candidate or seed_transgressions) else "crop")
            contour = None
            if treatment == "cutout":
                # Imported manifests may already contain a vector mask.  Keep
                # it in scene-graph coordinates; otherwise use a deterministic
                # silhouette so the preview and IDML remain structurally valid.
                contour = main_photo.contour_polygon
                if contour is None and main_photo.alpha_mask_url and Path(main_photo.alpha_mask_url).exists():
                    contour = extract_alpha_contour(main_photo.alpha_mask_url, photo_w, photo_h)
                contour = contour or generate_default_silhouette_contour(photo_w, photo_h)

            photo_id = f"photo-{lead_story.id}"
            photo_elem = Element(
                id=photo_id,
                role="photo",
                importance=main_photo.importance,
                content_ref=f"{lead_story.id}.photo",
                image_url=main_photo.url,
                frame=Frame(
                    x=fmt.margin_left_mm,
                    y=cur_y,
                    w=photo_w,
                    h=photo_h,
                    unit="mm"
                ),
                z=4,
                treatment=treatment,
                contour_points=contour,
                text_wrap=TextWrap(mode="contour" if treatment == "cutout" else "bounding_box", offset_mm=3.5),
                focal_point=main_photo.focal_point or [0.5, 0.4],
                mask_ref=main_photo.alpha_mask_url,
                source_dpi=main_photo.dpi
            )
            elements.append(photo_elem)
            lead_story_members.append(photo_id)

            # Caption
            if main_photo.caption:
                caption_id = f"cap-{photo_id}"
                cap_elem = Element(
                    id=caption_id,
                    role="caption",
                    importance=0.3,
                    content_ref=f"{lead_story.id}.caption",
                    text_content=main_photo.caption + (f" ({main_photo.credit})" if main_photo.credit else ""),
                    frame=Frame(
                        x=fmt.margin_left_mm,
                        y=cur_y + photo_h + 1.5,
                        w=photo_w,
                        h=12.0,
                        unit="mm"
                    ),
                    z=2,
                    style=ElementStyle(
                        font_family=self.dna.typography.fonts.get("sans", "sans-serif"),
                        font_size_pt=self.dna.typography.scales.caption,
                        line_height_pt=self.dna.typography.scales.caption * 1.15,
                        align="left",
                        color="#444444"
                    )
                )
                elements.append(cap_elem)
                lead_story_members.append(caption_id)

        # Lead text & Body text placement
        body_x = fmt.margin_left_mm + (photo_w + g.gutter_mm if (photo_id and cols >= 5) else 0.0)
        body_cols_avail = max(1, hl_span_cols - (3 if (photo_id and cols >= 5) else 0))
        body_w = self.grammar.span_to_w_mm(body_cols_avail)

        if lead_story.lead:
            lead_id = f"lead-{lead_story.id}"
            lead_elem = Element(
                id=lead_id,
                role="lead",
                importance=lead_story.importance * 0.85,
                content_ref=f"{lead_story.id}.lead",
                text_content=lead_story.lead,
                frame=Frame(
                    x=body_x,
                    y=cur_y,
                    w=body_w,
                    h=30.0,
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
            lead_story_members.append(lead_id)

        # Body Copy (Multi-column box)
        body_id = f"body-{lead_story.id}"
        body_y = cur_y + (32.0 if lead_story.lead else 0.0)
        body_h = max(50.0, (fmt.trim_h_mm - fmt.margin_bottom_mm - body_y) * 0.85)

        body_elem = Element(
            id=body_id,
            role="body",
            importance=lead_story.importance * 0.7,
            content_ref=f"{lead_story.id}.body",
            text_content=lead_story.body,
            frame=Frame(
                x=body_x,
                y=body_y,
                w=body_w,
                h=body_h,
                unit="mm"
            ),
            z=1,
            style=ElementStyle(
                font_family=self.dna.typography.fonts.get("body", "serif"),
                font_size_pt=self.dna.typography.scales.body,
                line_height_pt=self.dna.typography.scales.body * 1.20,
                align="justify",
                columns=max(1, body_cols_avail)
            )
        )
        elements.append(body_elem)
        reading_order.append(body_id)
        lead_story_members.append(body_id)

        relations.append(Relation(
            type="belongs_to_story",
            members=lead_story_members,
            story=lead_story.id
        ))

        # -----------------------------------------------------------------
        # Secondary Stories (Right Column / Sidebar / Bottom)
        # -----------------------------------------------------------------
        if sub_stories and cols > hl_span_cols:
            side_col_start = hl_span_cols
            side_x = self.grammar.col_to_x_mm(side_col_start)
            side_w = self.grammar.span_to_w_mm(cols - side_col_start)
            side_y = content_top_y

            for idx, sub in enumerate(sub_stories):
                sub_members = []
                # Vertical partition rule
                sub_box_h = (fmt.trim_h_mm - fmt.margin_bottom_mm - content_top_y) / len(sub_stories)

                sub_hl_id = f"hl-{sub.id}"
                sub_hl = Element(
                    id=sub_hl_id,
                    role="headline",
                    importance=sub.importance,
                    content_ref=f"{sub.id}.headline",
                    text_content=sub.headline,
                    frame=Frame(
                        x=side_x,
                        y=side_y,
                        w=side_w,
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
                sub_members.append(sub_hl_id)

                sub_body_id = f"body-{sub.id}"
                sub_body = Element(
                    id=sub_body_id,
                    role="body",
                    importance=sub.importance * 0.7,
                    content_ref=f"{sub.id}.body",
                    text_content=sub.lead or sub.body[:300] + "...",
                    frame=Frame(
                        x=side_x,
                        y=side_y + 22.0,
                        w=side_w,
                        h=sub_box_h - 26.0,
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
                sub_members.append(sub_body_id)

                relations.append(Relation(
                    type="belongs_to_story",
                    members=sub_members,
                    story=sub.id
                ))
                side_y += sub_box_h

        stories_by_id = {story.id: story for story in material.stories}
        for element in elements:
            if element.content_ref and "." in element.content_ref:
                story = stories_by_id.get(element.content_ref.split(".", 1)[0])
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

        # Page metadata
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
                "generator": "deterministic_grid_solver",
                "page_zone": material.page_zone,
                "zone_template": {
                    "front_page": "masthead_teaser_dominant",
                    "spread": "verso_recto_threaded",
                    "back_page": "closing_poster_or_sport",
                }[material.page_zone],
                "text_threading": material.page_zone == "spread",
            }
        )
