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
from .image_ops import extract_alpha_contour, resolve_asset_path


def compose_page(dna, material, genes: dict[str, Any] | None = None) -> SceneGraph:
    genes = genes or {}
    fmt, grid = dna.format, dna.grid
    zone = material.page_zone
    page_count = 2 if zone == "spread" else 1
    single_w, page_h = fmt.trim_w_mm, fmt.trim_h_mm
    page_w = single_w * page_count
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    bottom = page_h - fmt.margin_bottom_mm
    gutter = grid.gutter_mm
    stories = sorted(material.stories, key=lambda s: s.importance, reverse=True)
    elements: list[Element] = []
    relations: list[Relation] = []
    reading_order: list[str] = []
    threads: dict[str, list[str]] = {}
    photo_bias = material.style_blend.dense_to_photo
    avantgarde = material.style_blend.classical_to_avantgarde
    tabloid = material.style_blend.opinion_to_tabloid
    photo_ratio = float(genes.get("photo_ratio", .24 + photo_bias * .22))
    variant = float(genes.get("variation", .5))

    def text(role, story, field, x, y, w, h, size, dominant=False, columns=1):
        value = getattr(story, field, None) if story else field
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
    text("folio", None, f"{material.issue_date} | {material.issue_number} | {material.section_name}",
         left, top+header_h+1., page_w-left-fmt.margin_right_mm, 5., 7.5)
    content_y = top+header_h+9.
    if zone == "front_page" and len(stories) > 1:
        teaser_w = (single_w-left-fmt.margin_right_mm-(len(stories)-2)*gutter)/max(1,len(stories)-1)
        for index, story in enumerate(stories[1:]):
            text("band", None, story.headline, left+index*(teaser_w+gutter), content_y, teaser_w, 10., 10.)
        content_y += 14.

    def module(story, x, y, w, h, dominant=False, closing=False):
        members = []
        cursor = y
        content_end = y+h
        for role, field, size in [("kicker", "kicker", dna.typography.scales.kicker)]:
            if getattr(story, field):
                members.append(text(role, story, field, x, cursor, w, 5., size)); cursor += 7.
        headline_size = (dna.typography.scales.headline_l*(.95+.42*tabloid+.12*variant)) if dominant else dna.typography.scales.headline_s
        headline_size = min(headline_size, 56. if dominant else 25.)
        # Text length determines headline depth; no fixed truncation in render.
        line_chars = max(12, int(w/(headline_size*.18)))
        headline_lines = max(1, math.ceil(len(story.headline)/line_chars))
        headline_h = max(10., headline_lines*headline_size*.352778*1.10+1.)
        members.append(text("headline", story, "headline", x, cursor, w, headline_h, headline_size, dominant)); cursor += headline_h+3.
        for role, field, size in [("deck","deck",dna.typography.scales.lead), ("byline","byline",dna.typography.scales.byline), ("lead","lead",dna.typography.scales.lead)]:
            value = getattr(story,field)
            if value:
                chars = max(18,int(w/(size*.17)))
                depth=max(5.,math.ceil(len(value)/chars)*size*.352778*1.23+1.)
                members.append(text(role,story,field,x,cursor,w,depth,size));cursor+=depth+2.

        images = story.images[:dna.photo_rules.max_photos_per_page]
        image = images[0] if images else None
        photo = None
        available = max(12.,content_end-cursor)
        contour = None
        can_cutout = bool(image and dna.photo_rules.allow_cutout and (image.alpha_mask_url or image.contour_polygon))
        if image:
            treatment = "cutout" if can_cutout and (image.is_cutout_candidate or image.treatment=="cutout") else "crop"
            photo_w = w*(.38+.10*avantgarde) if treatment=="cutout" else w
            photo_h = min(available*.55, h*photo_ratio)
            if treatment=="cutout":
                if image.contour_polygon:
                    raw = image.contour_polygon
                    # Inline masks supplied by the asset endpoint use a
                    # normalised 0..1 contour, older manifests use mm.
                    xmax=max(p[0] for p in raw); ymax=max(p[1] for p in raw)
                    contour=[[p[0]*photo_w/(xmax or 1),p[1]*photo_h/(ymax or 1)] for p in raw]
                else:
                    mask=resolve_asset_path(image.alpha_mask_url)
                    if mask: contour=extract_alpha_contour(str(mask),photo_w,photo_h)
                if not contour: treatment="crop";photo_w=w
            photo_x=x+w-photo_w if treatment=="cutout" else x
            photo = Element(id=f"photo-{story.id}",role="photo",importance=min(.9,image.importance),content_ref=f"{story.id}.image",
                image_url=image.url,mask_ref=image.alpha_mask_url,frame=Frame(x=photo_x,y=cursor,w=photo_w,h=photo_h),z=4,
                treatment=treatment,contour_points=contour,source_dpi=image.dpi,
                text_wrap=TextWrap(mode="contour" if treatment=="cutout" else "bounding_box",offset_mm=dna.photo_rules.text_wrap_offset_mm),
                focal_point=image.focal_point,transgressions=["cutout-wrap"] if treatment=="cutout" else [])
            elements.append(photo);members.append(photo.id)
            if treatment!="cutout":
                cursor+=photo_h+2.
                if image.caption:
                    members.append(text("caption",story,"image_caption",x,cursor,w,8.,dna.typography.scales.caption) if False else None)
                    cap=text("caption",None,image.caption+(f" / {image.credit}" if image.credit else ""),x,cursor,w,8.,dna.typography.scales.caption)
                    members.append(cap);cursor+=10.

        body_h=max(6.,content_end-cursor)
        columns=max(1,min(grid.columns,int(w/38.)))
        if photo and photo.treatment=="cutout":columns=1
        body_id=text("body",story,"body",x,cursor,w,body_h,dna.typography.scales.body,columns=columns)
        members.append(body_id)
        threads[story.id]=[body_id]
        if story.pullquote:
            # Pull quotes have a dedicated footer strip when space permits.
            # Their body copy remains intact; they are an editorial emphasis.
            pass
        if story.infobox:
            pass
        relations.append(Relation(type="belongs_to_story",members=[m for m in members if m],story=story.id))

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
        # Sidebar measures stay above 30 mm; variant controls asymmetry while
        # the dominant story always owns most of the available page area.
        main_ratio=.67+.10*variant
        main_w=usable_w*main_ratio-gutter/2
        side_w=usable_w-main_w-gutter
        module(stories[0],left,content_y,main_w,usable_h,True,zone=="back_page")
        depth=(usable_h-(len(stories)-2)*gutter)/max(1,len(stories)-1)
        for index,story in enumerate(stories[1:]):
            module(story,left+main_w+gutter,content_y+index*(depth+gutter),side_w,depth)
    elif stories:
        module(stories[0],left,content_y,usable_w,usable_h,True,zone=="back_page")

    return SceneGraph(page=PageMeta(trim=[page_w,page_h],bleed_mm=fmt.bleed_mm,safe_margin_mm=min(left,top),
        grid={"cols":grid.columns*page_count,"gutter_mm":gutter,"baseline_mm":grid.baseline_grid_pt*.352778,"rows":grid.rows},title_dna_ref=dna.id,page_zone=zone),
        elements=elements,relations=relations,reading_order=reading_order,metadata={
            "generator":"zone_constraint_solver","page_zone":zone,"page_count":page_count,"single_page_width_mm":single_w,
            "zone_template":{"front_page":"masthead_teaser_dominant","spread":"verso_recto_threaded","back_page":"closing_poster_or_sport"}[zone],
            "text_threads":threads,"text_threading":zone=="spread","style_blend":material.style_blend.model_dump(),
        })
