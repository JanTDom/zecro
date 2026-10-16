"""Three-zone, content-preserving newspaper geometry solver.

The solver composes modules from editorial data and a small continuous genome.
It never retrieves a page from the corpus.  A separate critic determines whether
the result is readable and publishable.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, Relation, SceneGraph, TextWrap
from .copyfit import estimate_text_capacity
from .content_engine import rewrite_source_bound_copy
from .image_ops import extract_alpha_contour, photo_cutout_geometry, resolve_asset_path


_BOLD_ROLES = {"headline", "logo", "kicker", "lead"}


def _role_family(dna, role: str) -> str:
    key = "headline" if role in ["headline", "pullquote", "logo"] else "sans" if role in ["kicker", "byline", "caption", "folio"] else "body"
    return dna.typography.fonts.get(key, "serif")


def _font_kw(dna, role: str) -> dict:
    return {"font_family": _role_family(dna, role), "bold": role in _BOLD_ROLES, "gutter_mm": dna.grid.gutter_mm}


def _style_kw(dna, element) -> dict:
    st = element.style
    return {"font_family": (st.font_family if st else None) or _role_family(dna, element.role),
            "bold": bool(st and str(st.font_weight) in ("bold", "600", "700", "800", "900")), "gutter_mm": dna.grid.gutter_mm}


def compose_page(dna, material, genes: dict[str, Any] | None = None) -> SceneGraph:
    genes = genes or {}
    if getattr(material, "tv_schedule", None) and (
            material.page_zone != "front_page" or not material.stories):
        from .tv_listing import compose_tv_listing
        return compose_tv_listing(dna, material, genes)
    if (material.page_zone == "spread" and genes.get("cover_morphology") == "opening_spread"
            and material.stories):
        from .magazine_morphologies import compose_opening_spread, is_magazine
        lead = max(material.stories, key=lambda story: story.importance)
        if is_magazine(dna) and lead.images:
            return compose_opening_spread(dna, material, genes)
    ranked = any(getattr(s, "rank", None) not in (None, "second") for s in material.stories)
    # One-story pages keep the single-module architectures (they differ in
    # measure and photo placement); multi-story pages are composed from ranks.
    if material.page_zone != "spread" and len(material.stories) >= 2 and (len(material.stories) >= 3 or ranked) and not genes.get("legacy_modules"):
        from .plan_composer import compose_planned_page
        return compose_planned_page(dna, material, genes)
    fmt, grid = dna.format, dna.grid
    zone = material.page_zone
    page_count = 2 if zone == "spread" else 1
    single_w, page_h = fmt.trim_w_mm, fmt.trim_h_mm
    page_w = single_w * page_count
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    bottom = page_h - fmt.margin_bottom_mm
    gutter = grid.gutter_mm
    rank_order = {"lead": 0, "second": 1, "third": 2, "short": 3, "brief": 4, "column": 4, "box": 4, "teaser": 5}
    stories = sorted(material.stories, key=lambda s: (rank_order.get(getattr(s, "rank", "second"), 2), -s.importance))
    elements: list[Element] = []
    relations: list[Relation] = []
    reading_order: list[str] = []
    threads: dict[str, list[str]] = {}
    fit_adjustments: list[dict[str, Any]] = []
    photo_bias = material.style_blend.dense_to_photo
    avantgarde = material.style_blend.classical_to_avantgarde
    tabloid = material.style_blend.opinion_to_tabloid
    photo_ratio = float(genes.get("photo_ratio", .24 + photo_bias * .22))
    variant = float(genes.get("variation", .5))
    layout_mode = str(genes.get("layout_mode", "dominant-left"))

    def text(role, story, field, x, y, w, h, size, dominant=False, columns=1):
        value = getattr(story, field, None) if story and hasattr(story, field) else field
        if not value:
            return None
        eid = f"{role}-{story.id if story else len(elements)}-{len(elements)}"
        style = ElementStyle(
            font_family=dna.typography.fonts.get("headline" if role in ["headline", "pullquote", "logo"] else "sans" if role in ["kicker", "byline", "caption", "folio"] else "body", "serif"),
            font_size_pt=size, line_height_pt=size * (1.08 if role in ["headline", "logo"] else 1.2),
            font_weight="bold" if role in ["headline", "logo", "kicker", "lead"] else "normal",
            color=dna.palette.secondary if role == "kicker" else dna.palette.text,
            align="justify" if role == "body" else "left", columns=columns,
        )
        element = Element(id=eid, role=role, importance=1.0 if dominant else min(.84, story.importance if story else .25),
            content_ref=f"{story.id}.{field}" if story else role, text_content=str(value),
            frame=Frame(x=x, y=y, w=w, h=max(2., h)), style=style, z=2,
            constraints=["must_dominate"] if dominant else [],
            story_ref=story.id if story else None,
            content_revision_ref=getattr(story, "content_revision_ref", None) if story else None,
            text_plan_ref=(getattr(story, "text_plan_refs", {}) or {}).get(field) if story else None,
            source_refs=list(getattr(story, "source_refs", []) or []) if story else [],
            claim_refs=list(getattr(story, "claim_refs", []) or []) if story else [],
            locked=bool(
                story
                and getattr(story, "locked_passages", [])
                and any(locked and locked in str(value) for locked in story.locked_passages)
            ),
            approval_status=getattr(story, "approval_status", None) if story else None,
            fit_status="unknown")
        elements.append(element)
        reading_order.append(eid)
        return eid

    # Front pages have a reserved masthead and teaser band; interior spreads
    # carry a compact running header; closing pages have a section lockup.
    header_h = 18. if zone == "front_page" else 9.
    text("logo" if zone == "front_page" else "folio", None,
         material.masthead_title if zone == "front_page" else f"{material.masthead_title} · {material.section_name}",
         left, top, page_w-left-fmt.margin_right_mm, header_h,
         34. if zone == "front_page" else 10.)
    if zone == "front_page" and getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
        # Preserve the real vector asset reference in the scene graph.  The
        # preview renderers can display it while IDML packages it as a linked
        # graphic; text remains the accessible fallback label.
        logo_element = next((element for element in elements if element.role == "logo"), None)
        if logo_element is not None:
            logo_element.image_url = dna.logo_profile.asset_ref
            logo_element.content_ref = "masthead.logo"
    text("folio", None, f"{material.issue_date} | {material.issue_number} | {material.section_name}",
         left, top+header_h+1., page_w-left-fmt.margin_right_mm, 5., 7.5)
    content_y = top+header_h+9.
    if zone == "front_page" and len(stories) > 1:
        # A teaser is an explicit editorial role.  Previous versions mirrored
        # every secondary story in a band and then rendered it again below,
        # making seven-story fronts impossible to fit.  Keep one source of
        # truth: page-plan teaser slots (or the story's teaser_only flag).
        teaser_stories = [s for s in stories if getattr(s, "teaser_only", False) or getattr(s, "rank", None) == "teaser"]
        if teaser_stories:
            teaser_w = (single_w-left-fmt.margin_right_mm-(len(teaser_stories)-1)*gutter)/max(1,len(teaser_stories))
            for index, story in enumerate(teaser_stories):
                text("band", None, story.headline, left+index*(teaser_w+gutter), content_y, max(2*gutter, teaser_w), 10., 10.)
            content_y += 14.
            stories = [s for s in stories if s not in teaser_stories]

    def module(story, x, y, w, h, dominant=False, closing=False, compact=False):
        """Compose one complete editorial module from copy and geometry.

        A narrow rail may leave white space, but it never drops a supplied
        editorial field silently. Frames are sized from the same copyfit
        estimate consumed by the critic and renderers.
        """
        members: list[str] = []
        cursor = y
        content_end = y + h
        placement = str(genes.get("photo_placement", "inline_side"))
        if layout_mode == "photo-top":
            placement = "top_hero"
        elif layout_mode == "stacked" and placement == "inline_side":
            placement = "bottom_anchor"
        gutter_local = max(2.5, gutter)
        images = story.images[:dna.photo_rules.max_photos_per_page]
        image = images[0] if images else None
        photo = None

        def fit_height(value: str, width: float, size: float, columns: int = 1,
                       minimum: float = 4.0, maximum: float | None = None, role: str = "body") -> float:
            line_h = max(1.5, size * .352778 * (1.08 if size >= 18 else 1.20))
            height = max(minimum, line_h + 1.0)
            limit = max(height, maximum if maximum is not None else h)
            while height < limit:
                report = estimate_text_capacity(str(value), width, height, columns, size, line_h / .352778, **_font_kw(dna, role))
                if report.passes:
                    return round(height, 2)
                height += line_h
            return round(min(limit, height), 2)

        def append_photo(px: float, py: float, pw: float, ph: float):
            nonlocal photo
            if not image or pw <= 0 or ph <= 0:
                return
            can_cutout = bool(dna.photo_rules.allow_cutout and
                              (image.alpha_mask_url or image.contour_polygon or image.is_cutout_candidate))
            requested = image.treatment or str(genes.get("photo_treatment", "crop"))
            treatment = "cutout" if requested == "cutout" and can_cutout else "crop"
            geometry = photo_cutout_geometry(image, pw, ph)
            contour = geometry["contour"] if treatment == "cutout" else None
            holes = geometry["holes"] if treatment == "cutout" else None
            if treatment == "cutout" and not contour:
                treatment = "crop"
            photo = Element(
                id=f"photo-{story.id}", role="photo", importance=min(.92, story.importance),
                content_ref=f"{story.id}.image", image_url=image.url,
                mask_ref=image.alpha_mask_url,
                frame=Frame(x=px, y=py, w=pw, h=ph), z=4,
                treatment=treatment, contour_points=contour, contour_holes=holes or None,
                crop_box=geometry["crop_box"], source_dpi=image.dpi,
                source_width_px=image.width_px, source_height_px=image.height_px,
                text_wrap=TextWrap(mode="contour" if treatment == "cutout" else "bounding_box",
                                   offset_mm=dna.photo_rules.text_wrap_offset_mm),
                focal_point=image.focal_point,
                transgressions=["cutout-wrap"] if treatment == "cutout" else [],
                story_ref=story.id,
                source_refs=list(getattr(story, "source_refs", []) or []),
                claim_refs=list(getattr(story, "claim_refs", []) or []),
                content_revision_ref=getattr(story, "content_revision_ref", None),
                approval_status=getattr(story, "approval_status", None))
            elements.append(photo)
            members.append(photo.id)

        # Top and side placements reserve space before copy; bottom placement
        # reserves a band after the intro. This is a real reading-path choice.
        photo_w = 0.0
        text_w = w
        if image and placement in {"top_hero", "inline_side", "cutout_overlap"}:
            if placement == "top_hero":
                photo_w = w
                if image.width_px:
                    # Respect press resolution before choosing a visual
                    # architecture. A wide hero may become a centered
                    # anchored image rather than a stretched low-DPI strip.
                    photo_w = min(photo_w, image.width_px / max(1.0, dna.photo_rules.min_dpi) * 25.4 * .96)
                photo_h = min(max(22.0, h * (.22 + .16 * photo_ratio)), max(22.0, h * .42))
                append_photo(x + (w - photo_w) / 2.0, cursor, photo_w, photo_h)
                if photo is not None:
                    cursor += photo_h + gutter_local
            else:
                photo_w = min(w * (.34 + .12 * avantgarde), w - 30.0)
                if image.width_px and placement != "cutout_overlap":
                    max_print_w = image.width_px / max(1.0, dna.photo_rules.min_dpi) * 25.4 * .96
                    photo_w = min(photo_w, max_print_w)
                photo_w = max(30.0, min(w - 30.0, photo_w))
                photo_h = min(max(30.0, h * (.28 + .12 * photo_ratio)), max(30.0, h * .48))
                append_photo(x + w - photo_w, cursor, photo_w, photo_h)
                text_w = w if placement == "cutout_overlap" and photo and photo.treatment == "cutout" else max(30.0, w - photo_w - gutter_local)

        if getattr(story, "kicker", None):
            depth = fit_height(story.kicker, text_w, dna.typography.scales.kicker, minimum=4.5, role="kicker")
            eid = text("kicker", story, "kicker", x, cursor, text_w, depth, dna.typography.scales.kicker)
            if eid:
                members.append(eid); cursor += depth + (2.0 if compact else 3.0)

        headline_size = (dna.typography.scales.headline_l * (.94 + .42 * tabloid + .12 * variant)
                         if dominant else dna.typography.scales.headline_s)
        headline_size = min(headline_size, 56.0 if dominant else 25.0)
        # Measure the headline with the same copyfit estimator used by the
        # critic.  A character-count shortcut used to allocate two lines for
        # headlines that actually needed three, making every otherwise sound
        # candidate fail the hard gate before it reached the gallery.
        headline_h = max(
            8.0 if compact else 10.0,
            fit_height(story.headline, text_w, headline_size, role="headline", minimum=8.0 if compact else 10.0,
                       maximum=max(10.0, content_end - cursor)),
        )
        eid = text("headline", story, "headline", x, cursor, text_w, headline_h, headline_size, dominant)
        if eid:
            members.append(eid); cursor += headline_h + (2.0 if compact else 3.0)

        # Preserve deck, byline and lead in compact modules. Their spacing is
        # reduced, but their source content remains traceable and editable.
        for role, field, size in (("deck", "deck", dna.typography.scales.lead),
                                  ("byline", "byline", dna.typography.scales.byline),
                                  ("lead", "lead", dna.typography.scales.lead)):
            value = getattr(story, field, None)
            if not value:
                continue
            role_story = story
            if compact and role in {"deck", "lead"} and len(str(value).split()) > 20:
                # A brief/rail module gets an approved, source-bound satellite
                # variant so the field remains present and traceable.
                shortened, meta = rewrite_source_bound_copy(str(value), role=role, target_words=8, locked_passages=getattr(story, "locked_passages", []))
                role_story = story.model_copy(deep=True)
                setattr(role_story, field, shortened)
                fit_adjustments.append({"story_ref": story.id, "role": role, "action": "source_bound_shorten", "reason": "compact module budget", "metadata": meta})
                value = shortened
            minimum = 4.0 if role == "byline" else (6.0 if compact else 7.0)
            depth = fit_height(value, text_w, size, minimum=minimum, role=role)
            eid = text(role, role_story, field, x, cursor, text_w, depth, size)
            if eid:
                members.append(eid); cursor += depth + (1.5 if compact else 2.0)

        if image and placement == "bottom_anchor":
            photo_w = min(w, max(30.0, w * (.66 + .18 * photo_ratio)))
            if image.width_px:
                photo_w = min(photo_w, image.width_px / max(1.0, dna.photo_rules.min_dpi) * 25.4 * .96)
            caption_band = 8.0 if image.caption else 0.0
            photo_h = min(max(22.0, h * (.20 + .12 * photo_ratio)), max(22.0, h * .36),
                           max(22.0, h - caption_band - gutter_local))
            bottom_y = content_end - photo_h - caption_band
            append_photo(x, bottom_y, photo_w, photo_h)
            body_limit = max(cursor + 8.0, bottom_y - gutter_local)
        else:
            body_limit = content_end

        body_text = str(getattr(story, "body", "") or "")
        body_id = None
        if body_text:
            body_columns = max(1, min(grid.columns, int(text_w / 38.0)))
            if photo and photo.treatment == "cutout":
                body_columns = 1
            available = max(7.0, body_limit - cursor)
            body_story = story
            probe = estimate_text_capacity(body_text, text_w, available, body_columns, dna.typography.scales.body, dna.typography.scales.body * 1.2, **_font_kw(dna, "body"))
            if not probe.passes:
                target_words = max(8, int(probe.capacity_characters / 7.5))
                fitted, meta = rewrite_source_bound_copy(body_text, role="body", target_words=target_words, locked_passages=getattr(story, "locked_passages", []))
                # Sentence boundaries and locked passages can leave a variant
                # slightly over target; converge deterministically on a fit.
                for _ in range(3):
                    check = estimate_text_capacity(fitted, text_w, available, body_columns, dna.typography.scales.body, dna.typography.scales.body * 1.2, **_font_kw(dna, "body"))
                    if check.passes:
                        break
                    target_words = max(8, int(target_words * .72))
                    fitted, meta = rewrite_source_bound_copy(body_text, role="body", target_words=target_words, locked_passages=getattr(story, "locked_passages", []))
                if fitted and len(fitted.split()) < len(body_text.split()):
                    body_story = story.model_copy(deep=True)
                    body_story.body = fitted
                    fit_adjustments.append({"story_ref": story.id, "role": "body", "action": "source_bound_shorten", "from_words": len(body_text.split()), "to_words": len(fitted.split()), "reason": "frame overflow", "metadata": meta})
                elif getattr(story, "continue_to_page", None):
                    fit_adjustments.append({"story_ref": story.id, "role": "body", "action": "jump_line", "continuation_page": story.continue_to_page})
            body_value = body_story.body
            minimum_body = fit_height(body_value, text_w, dna.typography.scales.body, body_columns, minimum=7.0, maximum=available, role="body")
            body_h = min(available, max(minimum_body, minimum_body + (6.0 if len(body_value.split()) < 180 else 0.0)))
            body_id = text("body", body_story, "body", x, cursor, text_w, body_h,
                           dna.typography.scales.body, columns=body_columns)
            if body_id:
                members.append(body_id)
            threads[story.id] = [body_id] if body_id else []

        # Optional editorial satellites are real modules, never metadata that
        # silently disappears.  They consume a bounded part of the same slot
        # and remain linked to the owning story for IDML threading/audit.
        pullquote = getattr(story, "pullquote", None) or getattr(story, "pull_quote", None)
        if pullquote:
            quote_h = min(max(12.0, h * .18), max(12.0, content_end - cursor))
            quote_id = text("pullquote", story, pullquote, x, max(cursor, content_end - quote_h), text_w, quote_h, dna.typography.scales.pullquote)
            if quote_id:
                members.append(quote_id)
        info = getattr(story, "infobox", None)
        if info:
            info_text = "\n".join(f"{key}: {value}" for key, value in info.items())
            box_h = min(max(12.0, len(info) * 5.5), max(12.0, content_end - cursor))
            box_id = text("infobox", story, info_text, x, max(cursor, content_end - box_h), min(text_w, max(30.0, text_w * .45)), box_h, dna.typography.scales.body)
            if box_id:
                members.append(box_id)

        if image and image.caption and photo is not None:
            cap_y = (photo.frame.y + photo.frame.h + 1.0) if placement != "bottom_anchor" else photo.frame.y + photo.frame.h + 1.0
            cap_h = min(8.0, max(5.0, content_end - cap_y))
            if cap_h >= 5.0:
                cap_text = image.caption + (f" / {image.credit}" if image.credit else "")
                cap = text("caption", None, cap_text, x, cap_y, min(w, photo.frame.w), cap_h, dna.typography.scales.caption)
                if cap:
                    members.append(cap)

        relations.append(Relation(type="belongs_to_story", members=[m for m in members if m], story=story.id))

    usable_w=single_w-left-fmt.margin_right_mm
    usable_h=bottom-content_y
    if zone=="spread":
        # Verso/recto are composed in one scene graph, preserving page
        # boundaries for both preview and production export.
        if len(stories)==1:
            story=stories[0]
            midpoint=len(story.body)//2
            split=story.body.find(" ",midpoint)
            if split<0:split=midpoint
            verso=story.model_copy(deep=True);recto=story.model_copy(deep=True)
            verso.body=story.body[:split];recto.body=story.body[split:].lstrip()
            recto.id=f"{story.id}-recto";recto.headline="Ciąg dalszy";recto.kicker=None;recto.deck=None;recto.lead=None;recto.byline=None;recto.images=[];recto.image=None
            module(verso,left,content_y,usable_w,usable_h,True)
            module(recto,single_w+left,content_y,usable_w,usable_h)
            threads[story.id]=threads.pop(verso.id,[])+threads.pop(recto.id,[])
        else:
            for index,story in enumerate(stories):
                side=index%2; row=index//2;rows=math.ceil(len(stories)/2)
                depth=(usable_h-(rows-1)*gutter)/rows
                module(story,side*single_w+left,content_y+row*(depth+gutter),usable_w,depth,index==0)
    elif len(stories)>1:
        # A candidate architecture changes the editorial zones themselves.
        # Width-only mutations used to create cosmetic copies of one sidebar
        # page, so preserve the same copy while changing the reading path.
        main_ratio=.64+.14*variant
        main_w=usable_w*main_ratio-gutter/2
        side_w=usable_w-main_w-gutter
        secondary=stories[1:]
        if layout_mode == "dominant-right":
            depth=(usable_h-(len(secondary)-1)*gutter)/max(1,len(secondary))
            for index,story in enumerate(secondary):
                module(story,left,content_y+index*(depth+gutter),side_w,depth,compact=True)
            module(stories[0],left+side_w+gutter,content_y,main_w,usable_h,True,zone=="back_page")
        elif layout_mode == "stacked":
            lead_h=usable_h*(.54+.10*variant)
            module(stories[0],left,content_y,usable_w,lead_h,True,zone=="back_page")
            row_y=content_y+lead_h+gutter
            card_w=(usable_w-(len(secondary)-1)*gutter)/max(1,len(secondary))
            card_h=max(30.,usable_h-lead_h-gutter)
            for index,story in enumerate(secondary):
                module(story,left+index*(card_w+gutter),row_y,card_w,card_h,compact=True)
        elif layout_mode == "photo-top":
            # Reserve enough lower-page depth for a complete secondary
            # article. A visual opener is photo-led, not a reason to truncate
            # the rail's deck, byline, lead or body.
            lead_h=usable_h*(.52+.04*variant)
            module(stories[0],left,content_y,usable_w,lead_h,True,zone=="back_page")
            row_y=content_y+lead_h+gutter
            depth=max(30.,usable_h-lead_h-gutter)
            for index,story in enumerate(secondary):
                module(story,left+index*(side_w+gutter),row_y,side_w,depth,compact=True)
        elif layout_mode == "modular-grid":
            # Modular rhythm uses a broad lead block followed by a full-width
            # lower card row. It is deliberately distinct from the left/right
            # rail architectures even when the same copy and photo are used.
            lead_h=usable_h*(.56+.06*variant)
            module(stories[0],left,content_y,usable_w,lead_h,True,zone=="back_page")
            strip_y=content_y+lead_h+gutter
            strip_h=max(30.,usable_h-lead_h-gutter)
            strip_w=(usable_w-(len(secondary)-1)*gutter)/max(1,len(secondary))
            for index,story in enumerate(secondary):
                module(story,left+index*(strip_w+gutter),strip_y,strip_w,strip_h,compact=True)
        else:
            # dominant-left: the classical front-page reading path.
            depth=(usable_h-(len(secondary)-1)*gutter)/max(1,len(secondary))
            module(stories[0],left,content_y,main_w,usable_h,True,zone=="back_page")
            for index,story in enumerate(secondary):
                module(story,left+main_w+gutter,content_y+index*(depth+gutter),side_w,depth,compact=True)
    elif stories:
        # A single-story page still has an editorial architecture. Do not
        # return the same full-width frame five times merely because there is
        # no secondary article to form a rail.
        if layout_mode == "dominant-right":
            single_x, single_w = left + usable_w * .16, usable_w * .84
        elif layout_mode == "modular-grid":
            single_x, single_w = left, usable_w * .68
        elif layout_mode == "photo-top":
            single_x, single_w = left + usable_w * .08, usable_w * .84
        elif layout_mode == "stacked":
            single_x, single_w = left, usable_w * .92
        else:
            single_x, single_w = left, usable_w
        module(stories[0], single_x, content_y, single_w, usable_h, True, zone=="back_page")

    # Final deterministic copyfit pass covers architectures whose geometry
    # leaves a particularly short rail.  It is still source-bound and is
    # recorded as a draft adjustment; the critic remains the hard gate.
    for element in elements:
        if not element.text_content or element.role in {"logo", "folio", "rule", "caption"}:
            continue
        columns = max(1, int(element.style.columns if element.style else 1))
        size = float(element.style.font_size_pt if element.style and element.style.font_size_pt else dna.typography.scales.body)
        leading = float(element.style.line_height_pt if element.style and element.style.line_height_pt else size * 1.2)
        report = estimate_text_capacity(element.text_content, element.frame.w, element.frame.h, columns, size, leading, **_style_kw(dna, element))
        if report.passes:
            continue
        original = element.text_content
        target = max(4, int(len(original.split()) * .55))
        for _ in range(4):
            fitted, meta = rewrite_source_bound_copy(original, role=element.role if element.role in {"headline", "deck", "lead", "body", "kicker", "byline", "pullquote", "infobox", "teaser"} else "body", target_words=target)
            element.text_content = fitted
            if estimate_text_capacity(fitted, element.frame.w, element.frame.h, columns, size, leading, **_style_kw(dna, element)).passes:
                fit_adjustments.append({"element_ref": element.id, "action": "copyfit_shorten", "from_words": len(original.split()), "to_words": len(fitted.split()), "metadata": meta})
                break
            target = max(3, int(target * .7))

    rendered_refs = {str(e.content_ref) for e in elements if e.content_ref}
    missing_content_refs: list[str] = []
    for story in stories:
        for field in ("kicker", "headline", "deck", "byline", "lead", "body"):
            if getattr(story, field, None) and f"{story.id}.{field}" not in rendered_refs:
                missing_content_refs.append(f"{story.id}.{field}")
        if story.images and f"{story.id}.image" not in rendered_refs:
            missing_content_refs.append(f"{story.id}.image")

    scene = SceneGraph(page=PageMeta(trim=[page_w,page_h],bleed_mm=fmt.bleed_mm,safe_margin_mm=min(left,top),
        grid={"cols":grid.columns*page_count,"gutter_mm":gutter,"baseline_mm":grid.baseline_grid_pt*.352778,"rows":grid.rows},title_dna_ref=dna.id,page_zone=zone),
        elements=elements,relations=relations,reading_order=reading_order,metadata={
            "generator":"zone_constraint_solver","page_zone":zone,"page_count":page_count,"single_page_width_mm":single_w,
            "zone_template":{"front_page":"masthead_teaser_dominant","spread":"verso_recto_threaded","back_page":"closing_poster_or_sport"}[zone],
            "text_threads":threads,"text_threading":zone=="spread","style_blend":material.style_blend.model_dump(),
            "layout_mode": layout_mode,
            "photo_placement": str(genes.get("photo_placement", "inline_side")),
            "missing_content_refs": missing_content_refs,
            "fit_adjustments": fit_adjustments,
        })
    from .plan_composer import _polish_display_headlines
    return _polish_display_headlines(scene, dna)
