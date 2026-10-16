"""Rank-driven page composer that fills the page from measured content demand.

Architecture (genes) decides *where* ranks go; the measured typesetter decides
*how much* space each module needs.  Surplus space goes to photos, deficits
are resolved by source-bound shortening (or the AI copy editor upstream) and
recorded in ``fit_adjustments`` — never by silently overflowing.

Architectures:
  rail-right / rail-left : lead over a row of second-rank modules, briefs in a rail
  stacked                : lead, then seconds row, then briefs as a bottom row
  lead-rail              : lead with seconds stacked in a rail (photo-led front)
"""
from __future__ import annotations
import math
from typing import Any, Optional

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, Relation, SceneGraph, TextWrap
from .copyfit import estimate_text_capacity
from .content_engine import rewrite_source_bound_copy
from .display_headline import compose_display_headline, has_stranded_headline_word
from .image_ops import photo_cutout_geometry
from .page_mood import resolve_page_mood, story_color_roles

PT = 0.352778  # mm per pt
SECOND = {"second", "third", "column", "box", "short"}
BRIEF = {"brief"}


class _Ctx:
    def __init__(self, dna, material, genes):
        self.dna, self.material, self.genes = dna, material, genes or {}
        self.elements: list[Element] = []
        self.relations: list[Relation] = []
        self.order: list[str] = []
        self.fit: list[dict] = []
        self.gutter = dna.grid.gutter_mm
        self.tabloid = float(material.style_blend.opinion_to_tabloid)
        self.photo_bias = float(material.style_blend.dense_to_photo)

    # ---------------------------------------------------------- typography
    def family(self, role: str) -> str:
        key = "headline" if role in {"headline", "pullquote", "logo"} else "sans" if role in {"kicker", "byline", "caption", "folio", "band", "label"} else "body"
        return self.dna.typography.fonts.get(key, "serif")

    def leading(self, role: str, size: float) -> float:
        return size * (1.06 if role in {"headline", "logo"} else 1.18 if role in {"lead", "deck"} else 1.2)

    def bold(self, role: str) -> bool:
        return role in {"headline", "logo", "kicker", "lead", "label", "band"}

    def need(self, text: str, w: float, role: str, size: float, cols: int = 1) -> float:
        """Height in mm needed for ``text`` at width ``w`` (measured when possible)."""
        if not text:
            return 0.0
        lead = self.leading(role, size)
        lo, hi = lead * PT, max(lead * PT * 2, 2000.0)
        rep = estimate_text_capacity(text, w, hi, cols, size, lead, font_family=self.family(role), bold=self.bold(role), gutter_mm=self.gutter)
        return round(math.ceil(rep.estimated_lines / cols) * lead * PT + 0.6, 2)

    def lines(self, text: str, w: float, role: str, size: float) -> int:
        lead = self.leading(role, size)
        return estimate_text_capacity(text, w, 5000, 1, size, lead, font_family=self.family(role), bold=self.bold(role), gutter_mm=self.gutter).estimated_lines

    # ---------------------------------------------------------- elements
    def text(self, role, story, field, x, y, w, h, size, *, cols=1, value=None, dominant=False, align=None, color=None, bg_color=None) -> Optional[Element]:
        value = value if value is not None else (getattr(story, field, None) if story is not None else None)
        if not value:
            return None
        eid = f"{role}-{story.id if story else role}-{len(self.elements)}"
        style = ElementStyle(font_family=self.family(role), font_size_pt=round(size, 2), line_height_pt=round(self.leading(role, size), 2),
                             font_weight="bold" if self.bold(role) else "normal",
                             color=color or (self.dna.palette.secondary if role in {"kicker", "label"} else self.dna.palette.text),
                             bg_color=bg_color,
                             align=align or ("justify" if role == "body" else "left"), columns=cols)
        el = Element(id=eid, role=role, importance=1.0 if dominant else min(.84, getattr(story, "importance", .3) if story else .25),
                     content_ref=f"{story.id}.{field}" if story else role, text_content=str(value), frame=Frame(x=x, y=y, w=w, h=max(2.0, h)),
                     style=style, z=2, constraints=["must_dominate"] if dominant else [], story_ref=story.id if story else None,
                     content_revision_ref=getattr(story, "content_revision_ref", None) if story else None,
                     text_plan_ref=(getattr(story, "text_plan_refs", {}) or {}).get(field) if story else None,
                     source_refs=list(getattr(story, "source_refs", []) or []) if story else [],
                     claim_refs=list(getattr(story, "claim_refs", []) or []) if story else [],
                     approval_status=getattr(story, "approval_status", None) if story else None, fit_status="PASS")
        self.elements.append(el)
        self.order.append(eid)
        return el

    def rule(self, x, y, w, sid):
        el = Element(id=f"rule-{sid}-{len(self.elements)}", role="rule", importance=.1, content_ref="rule", frame=Frame(x=x, y=y, w=w, h=0.6),
                     style=ElementStyle(border_width_mm=0.25), z=1)
        self.elements.append(el)

    def photo(self, story, image, x, y, w, h, treatment_gene: str) -> Element:
        dna = self.dna
        can_cutout = bool(dna.photo_rules.allow_cutout and (image.alpha_mask_url or image.contour_polygon))
        requested = image.treatment or treatment_gene
        treatment = "cutout" if requested == "cutout" and can_cutout else "crop"
        geo = photo_cutout_geometry(image, w, h)
        contour = geo["contour"] if treatment == "cutout" else None
        if treatment == "cutout" and not contour:
            treatment = "crop"
        el = Element(id=f"photo-{story.id}", role="photo", importance=min(.92, story.importance), content_ref=f"{story.id}.image",
                     image_url=image.url, mask_ref=image.alpha_mask_url, frame=Frame(x=x, y=y, w=w, h=h), z=4, treatment=treatment,
                     contour_points=contour, contour_holes=(geo["holes"] or None) if treatment == "cutout" else None, crop_box=geo["crop_box"],
                     source_dpi=image.dpi, source_width_px=image.width_px, source_height_px=image.height_px,
                     text_wrap=TextWrap(mode="contour" if treatment == "cutout" else "bounding_box", offset_mm=dna.photo_rules.text_wrap_offset_mm),
                     focal_point=image.focal_point, transgressions=["cutout-wrap"] if treatment == "cutout" else [], story_ref=story.id,
                     source_refs=list(getattr(story, "source_refs", []) or []))
        self.elements.append(el)
        return el

    # ---------------------------------------------------------- modules
    def headline_size(self, story, w: float, rank: str) -> float:
        sc = self.dna.typography.scales
        base = {"lead": sc.headline_xl * (0.85 + 0.35 * self.tabloid), "second": sc.headline_m, "third": sc.headline_s,
                "column": sc.headline_s, "box": sc.headline_s * .9, "short": sc.headline_s * .9, "brief": max(sc.body * 1.35, sc.headline_s * .62)}.get(rank, sc.headline_s)
        max_lines = 3 if rank == "lead" else 4 if rank in SECOND else 3
        size = base
        while size > sc.body * 1.3 and self.lines(story.headline, w, "headline", size) > max_lines:
            size *= 0.92
        return round(size, 1)

    def module_parts(self, story, w: float, rank: str) -> dict:
        sc = self.dna.typography.scales
        cols = 1 if rank in BRIEF else max(1, min(self.dna.grid.columns, int((w + self.gutter) / (self.col_w + self.gutter) + 0.25)))
        while cols > 1 and (w - (cols - 1) * self.gutter) / cols < 30.0:
            cols -= 1
        hs = self.headline_size(story, w, rank)
        parts = {"cols": cols, "hs": hs,
                 "kicker": self.need(story.kicker or "", w, "kicker", sc.kicker) if rank not in BRIEF else 0,
                 "headline": self.need(story.headline, w, "headline", hs),
                 "deck": self.need(story.deck or "", w, "deck", sc.lead) if rank not in BRIEF else 0,
                 "lead": self.need(story.lead or "", w, "lead", sc.lead * (1.0 if rank == "lead" else .92)) if rank not in BRIEF else 0,
                 "byline": self.need(story.byline or "", w, "byline", sc.byline) if rank not in BRIEF else 0}
        parts["fixed"] = sum(parts[k] + (2.0 if parts[k] else 0) for k in ("kicker", "headline", "deck", "lead", "byline"))
        parts["body"] = self.need(story.body or "", w, "body", sc.body, cols)
        img = (story.images or [None])[0]
        parts["image"] = img
        aspect = (img.width_px / img.height_px) if img and img.width_px and img.height_px else (img.aspect_ratio if img and img.aspect_ratio else 1.5)
        parts["photo_min"] = 0.0 if not img or rank in BRIEF else min(w / aspect, w * (0.5 if rank == "lead" else 0.62)) * (0.55 if rank != "lead" else 0.7)
        parts["photo_ideal"] = 0.0 if not img or rank in BRIEF else w / aspect
        parts["caption"] = self.need(((img.caption or "") + (f" / {img.credit}" if img and img.credit else "")) if img else "", w, "caption", sc.caption) if img and rank not in BRIEF else 0
        return parts

    def demand(self, story, w: float, rank: str) -> float:
        p = self.module_parts(story, w, rank)
        body_min = min(p["body"], max(18.0, p["body"] * 0.45)) if rank != "brief" else p["body"]
        return p["fixed"] + p["photo_min"] + (p["caption"] + 1.5 if p["caption"] else 0) + body_min

    def place(self, story, x: float, y: float, w: float, h: float, rank: str, *, photo_side: bool = False) -> float:
        """Compose the module inside (x,y,w,h). Returns used height."""
        sc = self.dna.typography.scales
        p = self.module_parts(story, w, rank)
        members: list[str] = []
        cur = y
        img = p["image"]
        dominant = rank == "lead"
        # surplus → photo first, body gets the rest
        avail_flex = h - p["fixed"] - (p["caption"] + 1.5 if p["caption"] else 0)
        photo_h = 0.0
        body_text = story.body or ""
        if img and rank not in BRIEF:
            want = p["photo_ideal"] if not photo_side else min(p["photo_ideal"], avail_flex)
            photo_h = max(p["photo_min"], min(want, avail_flex - min(p["body"], max(15.0, avail_flex * 0.35))))
            photo_h = max(0.0, min(photo_h, avail_flex - 12.0))
        for role, field, size in (("kicker", "kicker", sc.kicker), ("headline", "headline", p["hs"])):
            if rank in BRIEF and role == "kicker":
                continue
            hh = p[role]
            el = self.text(role, story, field, x, cur, w, hh, size, dominant=dominant and role == "headline")
            if el:
                if rank in BRIEF and role == "headline":
                    el.constraints = list(el.constraints) + ["brief"]
                members.append(el.id); cur += hh + 2.0
        photo_el = None
        top_photo = img and rank not in BRIEF and photo_h >= 12.0 and (dominant or not photo_side)
        if top_photo:
            photo_el = self.photo(story, img, x, cur, w, photo_h, str(self.genes.get("photo_treatment", "crop")))
            members.append(photo_el.id); cur += photo_h + 1.0
            if p["caption"]:
                cap = (img.caption or "") + (f" / {img.credit}" if img.credit else "")
                el = self.text("caption", None, "caption", x, cur, w, p["caption"], sc.caption, value=cap)
                el.story_ref = story.id; members.append(el.id); cur += p["caption"] + 2.0
        for role, field, size in (("deck", "deck", sc.lead), ("lead", "lead", sc.lead * (1.0 if dominant else .92)), ("byline", "byline", sc.byline)):
            if rank in BRIEF or not p[role]:
                continue
            el = self.text(role, story, field, x, cur, w, p[role], size)
            if el:
                members.append(el.id); cur += p[role] + 2.0
        body_h = max(0.0, y + h - cur)
        cols = p["cols"]
        if body_text and body_h >= self.leading("body", sc.body) * PT:
            lead = self.leading("body", sc.body)
            per_col = int(body_h / (lead * PT) + 1e-6)
            fitted, meta = body_text, None
            rep = estimate_text_capacity(fitted, w, body_h, cols, sc.body, lead, font_family=self.family("body"), gutter_mm=self.gutter)
            if not rep.passes:
                target = max(8, int(len(body_text.split()) * rep.capacity_lines / max(1, rep.estimated_lines) * 0.97))
                for _ in range(6):
                    fitted, meta = rewrite_source_bound_copy(body_text, role="body", target_words=target, locked_passages=getattr(story, "locked_passages", []))
                    rep = estimate_text_capacity(fitted, w, body_h, cols, sc.body, lead, font_family=self.family("body"), gutter_mm=self.gutter)
                    if rep.passes:
                        break
                    target = max(6, int(target * 0.9))
                self.fit.append({"element_ref": f"body-{story.id}", "action": "copyfit_shorten", "from_words": len(body_text.split()),
                                 "to_words": len(fitted.split()), "metadata": meta, "reason": "slot depth"})
            used_lines = math.ceil(rep.estimated_lines / cols)
            bh = min(body_h, used_lines * lead * PT + 0.6) if rank in BRIEF or not rep.passes else body_h
            if rank not in BRIEF:  # balance columns: frame height = tallest column
                bh = min(body_h, math.ceil(rep.estimated_lines / cols) * lead * PT + 0.6)
            el = self.text("body", story, "body", x, cur, w, bh, sc.body, cols=cols, value=fitted)
            if el:
                el.fit_status = "PASS" if rep.passes else "FAIL"
                members.append(el.id); cur += bh
        slack = y + h - cur
        if rank not in BRIEF and slack > 22 and self.genes.get("fill", True):
            quote = pick_quote(story)
            if quote:
                qs = min(self.dna.typography.scales.pullquote or 18, max(14.0, self.dna.typography.scales.lead * 1.6))
                qh = self.need(quote, w * 0.86, "pullquote", qs)
                if qh + 8 <= slack:
                    self.rule(x, cur + 2.5, w, story.id + "-q")
                    el = self.text("pullquote", story, "pullquote", x + w * 0.07, cur + 5, w * 0.86, qh, qs, value=quote, align="center")
                    if el:
                        members.append(el.id); cur += qh + 8
                        self.fit.append({"action": "pullquote_from_text", "story": story.id, "reason": "wypełnienie wolnego miejsca dosłownym cytatem"})
        self.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
        return cur - y


def pick_quote(story) -> Optional[str]:
    """Verbatim quote from the story (explicit pull quote or a quoted sentence)."""
    import re
    explicit = getattr(story, "pullquote", None) or getattr(story, "pull_quote", None)
    if explicit and explicit in (story.body or "") + (story.lead or ""):
        return explicit
    body = story.body or ""
    for m in re.finditer(r"(?:–|—)\s?([^–—\n]{25,160}?)\s?(?:–|—)", body):
        return m.group(1).strip()
    for m in re.finditer(r"„([^”]{25,180})”", body):
        return m.group(1).strip()
    return None


def _polish_display_headlines(scene: SceneGraph, dna) -> SceneGraph:
    """Repair visually stranded words before the hard critic examines a page."""
    from .fonts import resolve_font
    from .shaper import shape_text

    grammar = dna.cover_grammar or {}
    for element in scene.elements:
        if element.role != "headline" or element.importance < .95 or not element.text_content or not element.style:
            continue
        display_text = element.text_content.upper() if element.style.case == "upper" else element.text_content
        path = resolve_font(element.style.font_family, bold=True, text=display_text)
        shaped = shape_text(display_text, width_pt=element.frame.w / PT,
                            font_size_pt=element.style.font_size_pt or 14,
                            font_path=path, hyphenate=False)
        if not has_stranded_headline_word([line.text for line in shaped.lines]):
            continue
        size = float(element.style.font_size_pt or 14)
        plan = compose_display_headline(
            element.text_content, width_mm=element.frame.w, height_mm=element.frame.h,
            preferred_size_pt=size, minimum_size_pt=max(14.0, size * .65),
            font_families=[element.style.font_family, *(grammar.get("display_font_candidates") or [])],
            case_options=(element.style.case or "normal",), max_lines=3,
        )
        if plan:
            element.text_content = plan.text
            element.style.font_family = plan.font_family
            element.style.font_size_pt = plan.font_size_pt
            element.style.line_height_pt = round(plan.font_size_pt * 1.06, 2)
            scene.metadata.setdefault("fit_adjustments", []).append({
                "action": "display_headline_composition", "element_ref": element.id,
                "lines": list(plan.lines), "font": plan.font_family,
                "font_size_pt": plan.font_size_pt, "case": plan.case,
            })
    return scene


def compose_planned_page(dna, material, genes: Optional[dict] = None) -> SceneGraph:
    from .logo import masthead_geometry
    genes = genes or {}
    cover_family = (getattr(dna, "cover_grammar", {}) or {}).get("family")
    if not cover_family and getattr(dna, "archetype", None) == "tabloid":
        cover_family = "popular_collage"  # existing saved title DNA
    if (material.page_zone == "front_page" and len(material.stories) in range(2, 8)
            and cover_family == "popular_collage"
            and not (material.page_plan and getattr(material.page_plan, "geometry", "auto") == "fixed")):
        return _polish_display_headlines(_compose_popular_cover(dna, material, genes), dna)
    if (material.page_zone == "front_page" and len(material.stories) in range(2, 6)
            and (cover_family in {"editorial_cover", "service_grid"} or
                 getattr(dna, "archetype", None) in {"editorial_magazine", "tv_guide"})
            and not (material.page_plan and getattr(material.page_plan, "geometry", "auto") == "fixed")):
        from .magazine_morphologies import CATALOG as MAGAZINE_CATALOG, compose as compose_magazine, feasible, is_magazine
        morphology = str(genes.get("cover_morphology") or "")
        if is_magazine(dna) and morphology in MAGAZINE_CATALOG and morphology in feasible(dna, material):
            return _polish_display_headlines(compose_magazine(dna, material, genes, morphology), dna)
        return _polish_display_headlines(_compose_editorial_or_service_cover(dna, material, genes), dna)
    ctx = _Ctx(dna, material, genes)
    fmt, grid = dna.format, dna.grid
    zone = material.page_zone
    page_w, page_h = fmt.trim_w_mm, fmt.trim_h_mm
    left, top, right = fmt.margin_left_mm, fmt.margin_top_mm, page_w - fmt.margin_right_mm
    bottom = page_h - fmt.margin_bottom_mm
    gut = grid.gutter_mm
    usable_w = right - left
    ctx.col_w = (usable_w - (grid.columns - 1) * gut) / grid.columns
    colx = lambda c: left + c * (ctx.col_w + gut)
    spanw = lambda n: n * ctx.col_w + (n - 1) * gut
    sc = dna.typography.scales

    # ---------------- masthead (logo-aware) + folio + ears
    profile = getattr(dna, "logo_profile", None)
    mg = masthead_geometry(dna, profile, page_w, zone=zone)
    if zone == "front_page":
        mode = mg["mode"]
        mh = float(mg["h"])
        has_logo = bool(profile and getattr(profile, "asset_ref", None) and profile.aspect_ratio)
        logo_w = float(mg["w"]) if has_logo else (usable_w if mode == "horizontal" else usable_w * 0.5)
        logo_x = left + (usable_w - logo_w) / 2 if (mode == "ears" or has_logo) and mode != "side" else left
        logo = ctx.text("logo", None, "logo", logo_x, top, logo_w, mh, min(48.0, mh / PT * 0.72), value=material.masthead_title,
                        align="center" if mode == "ears" else "left")
        if profile and getattr(profile, "asset_ref", None):
            logo.image_url, logo.content_ref = profile.asset_ref, "masthead.logo"
        if mode == "ears":
            ear_w = (usable_w - logo_w) / 2 - gut
            ctx.text("folio", None, "ear_left", left, top + 2, ear_w, mh - 4, sc.caption * 1.1, value=f"{material.issue_date}\n{material.issue_number}")
            ctx.text("folio", None, "ear_right", right - ear_w, top + 2, ear_w, mh - 4, sc.caption * 1.1, value=material.section_name or "", align="right")
            y = top + mh + 2
        else:
            y = top + mh + 1
            ctx.text("folio", None, "folio", left, y, usable_w, 5, 7.5, value=f"{material.issue_date} | {material.issue_number} | {material.section_name}")
            y += 7
        ctx.rule(left, y, usable_w, "masthead"); y += 3
    else:
        ctx.text("folio", None, "folio", left, top, usable_w, 6, 8.5, value=f"{material.masthead_title} · {material.section_name} · {material.issue_date}")
        y = top + 8
        ctx.rule(left, y, usable_w, "header"); y += 3

    stories = [s.model_copy(deep=True) for s in material.stories]
    if material.page_plan and material.page_plan.slots:  # an approved plan overrides story ranks
        slot_by = {sl.story_ref: sl for sl in material.page_plan.slots}
        for s in stories:
            sl = slot_by.get(s.id)
            if sl:
                s.rank = sl.rank
                s.teaser_only = bool(sl.teaser_only) or getattr(s, "teaser_only", False)
    rank = lambda s: getattr(s, "rank", None) or ("lead" if s.importance >= .9 else "second" if s.importance >= .6 else "brief")
    teasers = [s for s in stories if getattr(s, "teaser_only", False) or rank(s) == "teaser"]
    body_stories = [s for s in stories if s not in teasers]
    leads = [s for s in body_stories if rank(s) == "lead"] or sorted(body_stories, key=lambda s: -s.importance)[:1]
    lead = leads[0] if leads else None
    seconds = [s for s in body_stories if s is not lead and rank(s) in SECOND | {"lead"}]
    briefs = [s for s in body_stories if s is not lead and s not in seconds]

    # ---------------- teaser band (each cell ≥ 2 columns)
    if teasers and zone == "front_page" and getattr(material.page_plan, "geometry", "auto") != "fixed":
        n = min(len(teasers), max(1, grid.columns // 2))
        cell = (usable_w - (n - 1) * gut) / n
        for i, t in enumerate(teasers[:n]):
            pg = getattr(t, "continue_to_page", None)
            ctx.text("band", t, "headline", left + i * (cell + gut), y, cell, 12, sc.kicker * 1.1,
                     value=t.headline + (f" — str. {pg}" if pg else ""))
        if len(teasers) > n:
            ctx.fit.append({"action": "teasers_dropped", "dropped": [t.id for t in teasers[n:]], "reason": "pasek mieści ≥2 szpalty na zapowiedź"})
        y += 14
        ctx.rule(left, y - 2, usable_w, "teasers")

    plan = material.page_plan
    fixed = bool(plan and plan.slots and getattr(plan, "geometry", "auto") == "fixed")
    gene_mode = str(genes.get("layout_mode", "dominant-left"))
    arch, rail_cols = "fixed", 0
    if fixed:
        # Editor-drawn plan: every slot is a hard rectangle on the grid.
        # Rows below the masthead share the remaining depth evenly.
        content_rows = max(1, plan.rows - plan.masthead_rows)
        row_h = (bottom - y) / content_rows
        by_id = {s.id: s for s in stories}
        for sl in sorted(plan.slots, key=lambda s: (s.row_start, s.col_start)):
            s = by_id.get(sl.story_ref)
            if s is None or sl.page_number != 1:
                continue
            c0 = max(0, min(sl.col_start, grid.columns - 1))
            span = max(1, min(sl.col_span, grid.columns - c0))
            r0 = max(0, sl.row_start - plan.masthead_rows)
            sy = y + r0 * row_h + (1.5 if r0 else 0)
            sh = sl.row_span * row_h - (3 if r0 else 1.5)
            if sl.teaser_only or sl.rank == "teaser":
                pg = getattr(s, "continue_to_page", None) or sl.continuation_page
                ctx.text("band", s, "headline", colx(c0), sy, spanw(span), min(sh, 12), sc.kicker * 1.1,
                         value=s.headline + (f" — str. {pg}" if pg else ""))
                continue
            if r0:
                ctx.rule(colx(c0), sy - 1.5, spanw(span), f"fx-{s.id}")
            ctx.place(s, colx(c0), sy, spanw(span), sh, sl.rank)
    if not fixed:
        gene_mode = str(genes.get("layout_mode", "dominant-left"))
        arch = {"dominant-left": "rail-right", "dominant-right": "rail-left", "modular-grid": "rail-right", "photo-top": "lead-rail"}.get(gene_mode, gene_mode)
        wide_rail = gene_mode == "modular-grid"
        if not briefs and arch in {"rail-right", "rail-left"} and len(seconds) >= 2 and genes.get("variation", .5) > .5:
            arch = "lead-rail"
        rail_cols = 0
        if briefs and arch in {"rail-right", "rail-left"}:
            rail_cols = 1 if (ctx.col_w >= 38 or grid.columns <= 4) else 2
            if wide_rail:
                rail_cols += 1
            rail_cols = min(rail_cols, max(1, grid.columns - 3))
        if arch == "lead-rail":
            rail_cols = max(2, round(grid.columns * 0.34)) if seconds else 0
        main_cols = grid.columns - rail_cols
        rail_left = arch == "rail-left"
        main_x = colx(rail_cols) if rail_left else left
        rail_x = left if rail_left else colx(main_cols)
        main_w, rail_w = spanw(main_cols), (spanw(rail_cols) if rail_cols else 0)
        avail_h = bottom - y

        # ---------------- rail
        if rail_cols and arch != "lead-rail":
            ry = y
            label = ctx.text("kicker", None, "rail_label", rail_x, ry, rail_w, 6, sc.kicker, value="W SKRÓCIE")
            ry += 8
            n = len(briefs)
            per = (bottom - ry - (n - 1) * 3) / max(1, n)
            for i, b in enumerate(briefs):
                used = ctx.place(b, rail_x, ry, rail_w, per, "brief")
                ry += used + 1.5
                if i < n - 1:
                    ctx.rule(rail_x, ry, rail_w, b.id); ry += 1.5
            spare = bottom - ry
            if spare > 25:
                ctx.fit.append({"action": "rail_spare", "mm": round(spare, 1), "reason": "krótkie wiadomości nie wypełniają szpalty"})
            briefs_rendered = True
        else:
            briefs_rendered = False

        # ---------------- main area: lead + seconds row (+ briefs row when no rail)
        row_items = seconds if arch != "lead-rail" else []
        bottom_briefs = briefs if not briefs_rendered else []
        def row_demand(items, r_override=None):
            if not items:
                return 0.0
            k = len(items)
            base = main_cols // k
            if base < 2:
                half = math.ceil(k / 2)
                return row_demand(items[:half], r_override) + row_demand(items[half:], r_override) + 4
            return max(ctx.demand(s, spanw(base), r_override or (rank(s) if rank(s) != "lead" else "second")) for s in items)
        seconds_need = row_demand(row_items)
        briefs_need = row_demand(bottom_briefs, "brief")
        lead_area = avail_h - (seconds_need + 6 if row_items else 0) - (briefs_need + 6 if bottom_briefs else 0)
        if lead is not None:
            lead_need = ctx.demand(lead, main_w, "lead")
            lead_h = max(lead_need, lead_area) if lead_area > lead_need else lead_area
            # don't give the lead more than its full content needs: surplus to rows
            p = ctx.module_parts(lead, main_w, "lead")
            lead_full = p["fixed"] + p["photo_ideal"] + (p["caption"] + 1.5 if p["caption"] else 0) + p["body"]
            lead_h = min(lead_h, max(lead_need, lead_full))
            used = ctx.place(lead, main_x, y, main_w, lead_h, "lead")
            ly = y + max(used, 0) + 3
            if arch == "lead-rail" and seconds:
                ry = y
                per = (bottom - y - (len(seconds) - 1) * 4) / len(seconds)
                for i, s in enumerate(seconds):
                    u = ctx.place(s, rail_x, ry, rail_w, per, rank(s) if rank(s) != "lead" else "second", photo_side=True)
                    ry += u + 2
                    if i < len(seconds) - 1:
                        ctx.rule(rail_x, ry, rail_w, s.id); ry += 2
        else:
            ly = y

        def place_row(items, y0, height, r_override=None):
            if not items:
                return y0
            k = len(items)
            total_cols = main_cols
            base, extra = divmod(total_cols, k)
            if base < 2:  # too many for one row → two rows
                half = math.ceil(k / 2)
                hh = (height - 4) / 2
                y1 = place_row(items[:half], y0, hh, r_override)
                return place_row(items[half:], y1 + 4, hh, r_override)
            c0 = rail_cols if rail_left else 0
            heights = []
            weights = [max(1.0, len((s.body or "").split()) + 25 * bool(s.images)) for s in items]
            spans = [2] * k
            free = total_cols - 2 * k
            while free > 0:  # give columns to the module with the highest demand per column
                j = max(range(k), key=lambda i: weights[i] / spans[i])
                spans[j] += 1; free -= 1
            for i, s in enumerate(items):
                span = spans[i]
                heights.append(ctx.place(s, colx(c0), y0, spanw(span), height, r_override or (rank(s) if rank(s) != "lead" else "second")))
                c0 += span
            return y0 + max(heights)

        if row_items:
            ctx.rule(main_x, ly - 1.5, main_w, "row1")
            remaining = bottom - ly - (briefs_need + 6 if bottom_briefs else 0)
            ly = place_row(row_items, ly + 1, max(remaining, seconds_need)) + 3
        if bottom_briefs:
            ctx.rule(main_x, ly - 1.5, main_w, "row2")
            ly = place_row(bottom_briefs, ly + 1, bottom - ly - 1, "brief")

    # ---------------- result
    content_bottom = max((e.frame.y + e.frame.h for e in ctx.elements if e.role not in {"rule"}), default=y)
    underfill = round(bottom - content_bottom, 1)
    if underfill > 15:
        ctx.fit.append({"action": "underfill", "mm": underfill,
                        "suggestion": "Za mało materiału na stronę: dodaj zdjęcie lub ilustrację, podnieś rangę tekstu albo dodaj tekst/ramkę. System nie dopisuje treści."})
    missing = []
    rendered = {e.content_ref for e in ctx.elements}
    for s in body_stories:
        for field in ("headline", "body"):
            if getattr(s, field, None) and f"{s.id}.{field}" not in rendered:
                missing.append(f"{s.id}.{field}")
    return _polish_display_headlines(SceneGraph(page=PageMeta(trim=[page_w, page_h], bleed_mm=fmt.bleed_mm, safe_margin_mm=min(left, top),
                                    grid={"cols": grid.columns, "gutter_mm": gut, "baseline_mm": grid.baseline_grid_pt * PT, "rows": grid.rows},
                                    title_dna_ref=dna.id, page_zone=zone),
                      elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
                      metadata={"generator": "plan_composer", "page_zone": zone, "page_count": 1, "single_page_width_mm": page_w,
                                "layout_mode": gene_mode, "architecture": arch, "rail_cols": rail_cols, "masthead_mode": mg["mode"],
                                "photo_placement": "top", "missing_content_refs": missing, "underfill_mm": max(0.0, underfill), "fit_adjustments": ctx.fit,
                                "style_blend": material.style_blend.model_dump(), "text_threads": {}}), dna)


def _cover_copy_fits(ctx: _Ctx, value: str, width: float, height: float, role: str, size: float) -> bool:
    """Use the critic's actual copyfit model, including width overflow."""
    return estimate_text_capacity(
        value, width, height, 1, size, ctx.leading(role, size),
        font_family=ctx.family(role), bold=ctx.bold(role), gutter_mm=ctx.gutter,
    ).passes


def _compose_popular_cover(dna, material, genes: dict) -> SceneGraph:
    """Generate a collage-led popular cover from ranked stories and title DNA.

    The grammar defines proportions and color roles, while the genome changes
    image alignment and teaser order. All copy remains source-bound; condensed
    cover copy is recorded as an explicit editorial reduction.
    """
    ctx = _Ctx(dna, material, genes)
    fmt = dna.format
    g = dna.cover_grammar or {"masthead_band_mm": 42, "headline_band_share": .19,
                              "hero_photo_width_share": .64, "card_colors": [dna.palette.accent, dna.palette.tint_bg]}
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    right, bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
    width = right - left
    sc = dna.typography.scales
    red, navy, yellow = dna.palette.secondary, dna.palette.primary, dna.palette.accent
    stories = [s.model_copy(deep=True) for s in material.stories]
    stories.sort(key=lambda s: -s.importance)
    lead, secondaries = stories[0], stories[1:]
    mode = str(genes.get("layout_mode", "dominant-left"))
    hero_asset = (lead.images or [None])[0]
    print_width = width * dna.photo_rules.min_dpi / 25.4
    morphology = str(genes.get("cover_morphology") or "")
    if mode == "photo-top" and morphology and morphology != "asymmetric_hero_rail":
        # Generative morphologies (diagonal entry, two-scale collage, photo
        # dominant + irregular strip, directional tension, type behind the
        # subject).  Feasibility depends on the material and photo-editor
        # observations; an infeasible gene falls back to the hero-rail grammar.
        from .tabloid_morphologies import compose_morphology, feasible_morphologies
        if morphology in feasible_morphologies(dna, material, stories):
            return compose_morphology(dna, material, genes, stories, morphology)
    if (mode == "photo-top" and len(stories) >= 5 and hero_asset and
            hero_asset.width_px and hero_asset.width_px >= print_width and dna.cover_grammar
            and all(story.images for story in stories[:5])):
        return _compose_popular_poster_cover(dna, material, genes, stories)
    lead_words = len(" ".join((lead.deck or "", lead.lead or "", lead.body or "")).split())
    if mode == "type-led" and len(stories) >= 5 and hero_asset and all(story.images for story in stories[:5]):
        # A narrow portrait rail destroys a two-person landscape news photo.
        # A type-led page also needs enough *source material* to fill its text
        # panel. A short headline and one-sentence brief leave a dead zone;
        # use the photo-led grammar instead of manufacturing filler copy.
        if (hero_asset.width_px and hero_asset.height_px and
                hero_asset.width_px / hero_asset.height_px <= 1.12 and
                hero_asset.width_px >= print_width * .52 and lead_words >= 40):
            return _compose_popular_type_cover(dna, material, genes, stories)
        if hero_asset.width_px and hero_asset.width_px >= print_width and dna.cover_grammar:
            return _compose_popular_poster_cover(dna, material, {**genes, "layout_mode": "photo-top"}, stories)
    reverse = mode in {"dominant-right", "photo-top", "rail-left"}
    if reverse:
        secondaries.reverse()
    # Give one photo-bearing secondary story its own visual module beside the
    # lead. A popular cover with only text in that rail leaves a large dead
    # zone even when its boxes technically pass copyfit and collision gates.
    rail_story = next((s for s in secondaries if s.images), None) if len(stories) >= 4 else None
    if rail_story is not None:
        secondaries.remove(rail_story)

    def fit_copy(story, field: str, x: float, y: float, w: float, h: float, size: float, *, color=None, bg=None, min_size=7.2, max_words=None):
        source = str(getattr(story, field, "") or "")
        if not source:
            return None
        role = "headline" if field == "headline" else "body" if field == "body" else field
        candidate = source
        if max_words and len(source.split()) > max_words:
            candidate, meta = rewrite_source_bound_copy(source, role=role, target_words=max_words,
                                                         locked_passages=getattr(story, "locked_passages", []))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                            "field": field, "from_words": len(source.split()), "to_words": len(candidate.split()),
                            "reason": "Zajawka na okładce; pełny tekst pozostaje w materiale źródłowym",
                            "metadata": meta})
        fit_h = max(2.0, h - 1.5)
        while size > min_size and not _cover_copy_fits(ctx, candidate, w, fit_h, role, size):
            size = round(max(min_size, size * .92), 2)
        if not _cover_copy_fits(ctx, candidate, w, fit_h, role, size):
            words = max(5, int(len(source.split()) * fit_h / max(fit_h, ctx.need(source, w, role, size)) * .9))
            for _ in range(8):
                candidate, meta = rewrite_source_bound_copy(source, role=role, target_words=words,
                                                             locked_passages=getattr(story, "locked_passages", []))
                if _cover_copy_fits(ctx, candidate, w, fit_h, role, size):
                    break
                words = max(4, int(words * .78))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                            "field": field, "from_words": len(source.split()), "to_words": len(candidate.split()),
                            "reason": "Krótka zajawka na pierwszej stronie; pełny tekst pozostaje w materiale źródłowym",
                            "metadata": meta})
        return ctx.text(role, story, field, x, y, w, h, size, value=candidate,
                        dominant=story is lead and field == "headline", color=color, bg_color=bg)

    # The nameplate starts at the top of the printable area. The issue line
    # sits under it so short covers never bury the newspaper's name.
    # The skyline is one row. Letting three or more teasers grow above the
    # masthead pushed the nameplate toward mid-page and read as a generic
    # website grid rather than a popular newspaper cover.
    top_secondaries = secondaries[:2]
    bottom_secondaries = secondaries[2:]
    rows = math.ceil(len(top_secondaries) / 2)
    teaser_h = (30 if mode == "modular-grid" else 34) if rows > 1 else (32 if mode == "stacked" else 35)
    cell_w = (width - 4) / 2
    masthead_h = max(30.0, min(45.0, float(g.get("masthead_band_mm", 39))))

    def add_masthead(at: float) -> float:
        masthead = ctx.text("logo", None, "masthead", left, at, width, masthead_h,
                            min(62.0, masthead_h / PT * .64), value=material.masthead_title,
                            color=red, align="left")
        if getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
            masthead.image_url = dna.logo_profile.asset_ref
            masthead.content_ref = "masthead.logo"
        ctx.rule(left, at + masthead_h, width, "masthead")
        return at + masthead_h + 4

    y = add_masthead(top)
    ctx.text("folio", None, "issue", left, y, width, 5.5, 8.5,
             value=f"{material.issue_date}  ·  {material.issue_number}  ·  {material.section_name}")
    y += 8
    def draw_teasers(group, at: float, height: float) -> None:
        for index, story in enumerate(group):
            row, col = divmod(index, 2)
            x, yy = left + col * (cell_w + 4), at + row * (height + 3)
            teaser_image = (story.images or [None])[0]
            copy_w = cell_w * .69 if teaser_image else cell_w - 4
            if teaser_image:
                ctx.photo(story, teaser_image, x + cell_w * .71, yy, cell_w * .29, height,
                          str(genes.get("photo_treatment", "crop")))
            if story.kicker:
                fit_copy(story, "kicker", x + 2, yy + 1, copy_w, 5.5, 8.4,
                         color="#ffffff", bg=red, min_size=8.0)
            headline_y = yy + (7 if story.kicker else 2)
            headline = fit_copy(story, "headline", x + 2, headline_y, copy_w, height * .52,
                                min(24.0, sc.headline_s), color=navy,
                                bg=yellow if index % 2 == 0 else "#b9dce8", min_size=14.0)
            if headline:
                headline.style.font_weight = "bold"
            if story.body:
                fit_copy(story, "body", x + 2, yy + height * .63, copy_w,
                         height * .31, 9.3, color=navy, min_size=8.0, max_words=18)

    draw_teasers(top_secondaries, y, teaser_h)
    y += rows * (teaser_h + 3) + 2

    # The image and the lead form one cluster. Text stays in a separate rail,
    # so this remains printable even when the image lacks a cutout mask.
    bottom_rows = math.ceil(len(bottom_secondaries) / 2)
    bottom_teaser_h = 39.0 if len(bottom_secondaries) == 1 else 32.0
    bottom_reserved = bottom_rows * (bottom_teaser_h + 3) + 3 if bottom_rows else 0.0
    headline_h = (max(54.0, min(62.0, ctx.need(lead.headline, width, "headline", 85.0) + 5.0))
                  if len(lead.headline.split()) >= 4 else
                  min(45.0, max(28.0, ctx.need(lead.headline, width, "headline", 65.0) + 5.0)))
    copy_h = 14.0
    hero_h = max(60.0, bottom - y - headline_h - copy_h - bottom_reserved - 8)
    photo_w = width * float(g.get("hero_photo_width_share", .64))
    if mode == "modular-grid":
        photo_w *= .88
    elif mode == "photo-top":
        photo_w *= 1.10
    image = (lead.images or [None])[0]
    # When the lead has no supporting rail copy and no secondary photograph,
    # a narrow hero creates a conspicuous blank column.  In that material
    # state the photograph itself is the only honest visual content, so let it
    # occupy the complete editorial width instead of inventing filler.
    full_width_hero = bool(
        image
        and rail_story is None
        and not (lead.kicker or lead.deck or lead.lead)
    )
    if full_width_hero:
        photo_w = width
    if image and image.width_px:
        # The print resolution gate is geometric: a wider frame can turn an
        # otherwise usable source photograph into an unprintable one.
        photo_w = min(photo_w, image.width_px * 25.4 / dna.photo_rules.min_dpi)
    overlay = min(24.0, headline_h * .8) if image and mode in {"photo-top", "dominant-right"} else 0.0
    hero_h += overlay
    usable_hero_h = hero_h - overlay
    text_w = width - photo_w - 4
    photo_x = left if reverse else right - photo_w
    rail_x = photo_x + photo_w + 4 if reverse else left
    if image:
        # A cutout needs another visual plane to interact with.  If it is the
        # only element in a full-width hero, the transparent canvas makes the
        # subject look tiny and accidental.  Use an emotional full-frame crop
        # here; retain cutouts for collages with a rail or colour field.
        treatment = "crop" if full_width_hero else str(genes.get("photo_treatment", "crop"))
        ctx.photo(lead, image, photo_x, y, photo_w, hero_h, treatment)
    else:
        # A missing photo is visible in the proof and remains an editorial
        # task; a synthetic image would misrepresent the reported event.
        ctx.fit.append({"action": "missing_hero_photo", "story_ref": lead.id,
                        "reason": "Dodaj zdjęcie główne, aby okładka bulwarowa miała pełną hierarchię obrazu"})
    if lead.kicker:
        fit_copy(lead, "kicker", rail_x, y + 2, text_w, 10, 13.0, color="#ffffff", bg=navy, min_size=10.0)
    deck_h = min(30.0, hero_h * .20) if lead.deck else 0.0
    if lead.deck:
        fit_copy(lead, "deck", rail_x, y + 16, text_w, deck_h, 14.0, color=navy, min_size=9.0)
    lead_end = y
    if lead.lead:
        lead_y = y + (usable_hero_h * .25 if rail_story else usable_hero_h * .54)
        if lead.deck:
            lead_y = max(lead_y, y + 16 + deck_h + 2)
        lead_h = min(18.0 if rail_story else 26.0, usable_hero_h * (.15 if rail_story else .32))
        fit_copy(lead, "lead", rail_x, lead_y, text_w,
                 lead_h,
                 11.0, color=navy, min_size=9.0)
        lead_end = lead_y + lead_h
    if rail_story is not None:
        rail_photo_y = max(y + usable_hero_h * .32, lead_end + 2)
        rail_photo_h = max(20.0, y + usable_hero_h * .78 - rail_photo_y - 2)
        ctx.photo(rail_story, rail_story.images[0], rail_x, rail_photo_y, text_w, rail_photo_h,
                  str(genes.get("photo_treatment", "crop")))
        fit_copy(rail_story, "headline", rail_x, y + usable_hero_h * .79, text_w, usable_hero_h * .12,
                 min(20.0, sc.headline_s), color=navy, min_size=13.0)
        if rail_story.body:
            fit_copy(rail_story, "body", rail_x, y + usable_hero_h * .92, text_w, usable_hero_h * .08,
                     9.0, color=navy, min_size=8.2, max_words=16)
    if image and (image.caption or image.credit) and not full_width_hero:
        caption = (image.caption or "") + (f" / {image.credit}" if image.credit else "")
        if rail_story is None:
            ctx.text("caption", None, "caption", rail_x, y + usable_hero_h - 11, text_w, 9, 6.5,
                     value=caption, color=navy)
    y += hero_h - overlay + (0 if overlay else 3)

    headline = None
    if len(lead.headline.split()) >= 4:
        display_plan = compose_display_headline(
            lead.headline, width_mm=width - 4, height_mm=headline_h - 3,
            preferred_size_pt=min(84.0, sc.headline_xl * 1.35),
            minimum_size_pt=28.0,
            font_families=[*(g.get("display_font_candidates") or []), ctx.family("headline")],
            min_lines=2, max_lines=2,
        )
        if display_plan:
            headline = ctx.text("headline", lead, "headline", left, y, width, headline_h,
                                display_plan.font_size_pt, value=display_plan.text,
                                color=yellow if overlay else "#ffffff",
                                bg_color=navy if overlay else red, dominant=True)
            headline.style.font_family = display_plan.font_family
            ctx.fit.append({"action": "display_headline_composition", "story_ref": lead.id,
                            "lines": list(display_plan.lines), "font": display_plan.font_family})
    if headline is None:
        headline = fit_copy(lead, "headline", left, y, width, headline_h,
                            min(67.0, max(sc.headline_l, 54.0)),
                            color=yellow if overlay else "#ffffff", bg=navy if overlay else red, min_size=28.0)
    if headline:
        headline.style.font_weight = "bold"
        if overlay:
            headline.z = 5
            headline.transgressions.append("overlap-scrim")
    y += headline_h + 3
    if lead.body:
        body_h = max(8.0, min(copy_h, bottom - y - bottom_reserved))
        fit_copy(lead, "body", left, y, width, body_h, max(sc.body, 10.0),
                 color=navy, min_size=9.0, max_words=32)
        y += body_h + 3
    if bottom_secondaries:
        if len(bottom_secondaries) == 1:
            # One remaining story occupies the full bottom strip. Leaving the
            # second cell empty looks unfinished and wastes a strong photo.
            story = bottom_secondaries[0]
            last_image = (story.images or [None])[0]
            image_w = min(width * .34, last_image.width_px * 25.4 / dna.photo_rules.min_dpi) if last_image and last_image.width_px else width * .34
            copy_w = width - image_w - 5 if last_image else width
            if last_image:
                ctx.photo(story, last_image, right - image_w, y, image_w, bottom_teaser_h,
                          str(genes.get("photo_treatment", "crop")))
            if story.kicker:
                fit_copy(story, "kicker", left, y + 1, copy_w, 6, 9.0,
                         color="#ffffff", bg=red, min_size=8.4)
            fit_copy(story, "headline", left, y + 9, copy_w, 18, min(28.0, sc.headline_s),
                     color=navy, min_size=17.0)
            if story.body:
                fit_copy(story, "body", left, y + 28, copy_w, max(8.0, bottom_teaser_h - 29),
                         9.3, color=navy, min_size=8.2, max_words=19)
        else:
            draw_teasers(bottom_secondaries, y, bottom_teaser_h)

    rendered = {el.content_ref for el in ctx.elements}
    missing = [f"{s.id}.{field}" for s in stories for field in ("headline", "body")
               if getattr(s, field, None) and f"{s.id}.{field}" not in rendered]
    for story in stories:
        members = [el.id for el in ctx.elements if el.story_ref == story.id]
        if members:
            ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
    photo_stories = {story.id for story in stories if story.images}
    min_photo_stories = 2 if len(stories) <= 3 else 3
    style_warnings = []
    if not image:
        style_warnings.append("Brakuje zdjęcia głównego tematu.")
    if len(photo_stories) < min_photo_stories:
        style_warnings.append(f"Do wiarygodnej okładki bulwarowej dodaj zdjęcia do co najmniej {min_photo_stories} różnych tematów; obecnie zdjęcia ma {len(photo_stories)}.")
    if len(stories) < 4:
        style_warnings.append("Okładka ma mało tematów. Dodaj kolejne krótkie zajawki, aby uzyskać typowy rytm gazety bulwarowej.")
    return SceneGraph(
        page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm,
                      safe_margin_mm=min(left, top), grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                      "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                      title_dna_ref=dna.id, page_zone="front_page"),
        elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
        metadata={"generator": "plan_composer", "architecture": "popular_collage", "layout_mode": genes.get("layout_mode", "dominant-left"),
                  "page_zone": "front_page", "page_count": 1, "single_page_width_mm": fmt.trim_w_mm,
                  "style_readiness": {"status": "needs_assets" if style_warnings else "ready", "warnings": style_warnings,
                                      "photo_story_count": len(photo_stories), "story_count": len(stories)},
                  "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                  "style_blend": material.style_blend.model_dump(), "text_threads": {}})


def _compose_popular_poster_cover(dna, material, genes: dict, stories: list) -> SceneGraph:
    """Photo-led popular grammar for print-resolution assets.

    This is a compositional family, not a traced source page.  Its color roles,
    dimensions and typography come from TitleDNA; ranked material determines
    the modules and every displayed sentence remains source-bound.
    """
    ctx = _Ctx(dna, material, genes)
    fmt = dna.format
    g = dna.cover_grammar or {}
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    right, bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
    width = right - left
    mood = resolve_page_mood(material).name
    red, navy, yellow = story_color_roles(dna, mood)
    lead = stories[0]
    satellites = stories[1:5]
    extra = stories[5:]

    def fit(story, field, x, y, w, h, size, *, color=None, bg=None, minimum=7.8, words=None, dominant=False):
        source = str(getattr(story, field, "") or "")
        if not source:
            return None
        role = "headline" if field == "headline" else "body" if field == "body" else field
        candidate = source
        if words and len(candidate.split()) > words:
            candidate, info = rewrite_source_bound_copy(source, role=role, target_words=words,
                                                        locked_passages=getattr(story, "locked_passages", []))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id, "field": field,
                            "from_words": len(source.split()), "to_words": len(candidate.split()), "metadata": info})
        while size > minimum and not _cover_copy_fits(ctx, candidate, w, h - 1, role, size):
            size = round(max(minimum, size * .92), 2)
        if not _cover_copy_fits(ctx, candidate, w, h - 1, role, size):
            budget = max(4, int(len(candidate.split()) * (h - 1) / max(h, ctx.need(candidate, w, role, size)) * .85))
            candidate, info = rewrite_source_bound_copy(source, role=role, target_words=budget,
                                                        locked_passages=getattr(story, "locked_passages", []))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id, "field": field,
                            "from_words": len(source.split()), "to_words": len(candidate.split()), "metadata": info})
        return ctx.text(role, story, field, x, y, w, h, size, value=candidate,
                        color=color, bg_color=bg, dominant=dominant)

    masthead_h = min(48.0, max(34.0, float(g.get("masthead_band_mm", 42))))
    logo_plan = compose_display_headline(
        material.masthead_title, width_mm=width - 4, height_mm=masthead_h - 2,
        preferred_size_pt=min(132.0, masthead_h / PT * .88), minimum_size_pt=18.0,
        font_families=[ctx.family("logo")], max_lines=1,
    )
    logo = ctx.text("logo", None, "masthead", left, top, width, masthead_h,
                    logo_plan.font_size_pt if logo_plan else min(91.0, masthead_h / PT * .65),
                    value=material.masthead_title,
                    color="#ffffff", bg_color=red)
    if logo and getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
        logo.image_url = dna.logo_profile.asset_ref
        logo.content_ref = "masthead.logo"
        logo.style.bg_color = None
    folio_y = top + masthead_h + 1
    ctx.text("folio", None, "issue", left, folio_y, width, 6.0, 8.5,
             value=f"{material.issue_date}  ·  {material.issue_number}  ·  {material.section_name}")

    # Popular covers use a tighter collage rhythm than article pages.  The
    # Title DNA gutter remains the upper reference, but large white channels
    # between modules make the cover read like a dashboard.
    cell_gap = max(2.0, min(3.0, dna.grid.gutter_mm * .55))
    top_y = folio_y + 9
    # A local popular cover uses a compact skyline, then an asymmetric hero
    # cluster. The earlier four-card grid left the centre looking like a web
    # dashboard and gave the lead photo no relationship to the other stories.
    top_h = max(30.0, min(45.0, float(g.get("poster_skyline_height_mm", 36.0))))
    bottom_h = min(53.0, max(46.0, width * .20))
    hero_y = top_y + top_h + 2
    lead_body_h = 8.5 if lead.body else 0.0
    hero_h = max(100.0, bottom - hero_y - bottom_h - lead_body_h - 7)
    body_y = hero_y + hero_h
    bottom_y = body_y + lead_body_h + 2

    def satellite(story, x, y, w, h, idx):
        picture = (story.images or [None])[0]
        picture_w = min(w * (.35 if idx < 2 else .45),
                        picture.width_px * 25.4 / dna.photo_rules.min_dpi) if picture and picture.width_px else w * .37
        copy_w = w - picture_w - 2 if picture else w
        if idx >= 2:
            # Bottom promos are part of the tabloid rhythm, not detached white
            # cards.  Give each copy block a strong colour plane while the
            # neighbouring photograph keeps the item factual and specific.
            promo_bg = yellow if idx % 2 == 0 else navy
            ctx.elements.append(Element(
                id=f"promo-field-{story.id}", role="band", importance=.08,
                content_ref=f"{story.id}.promo_field", frame=Frame(x=x, y=y, w=copy_w, h=h),
                style=ElementStyle(bg_color=promo_bg), z=0,
                constraints=["decorative_background"], story_ref=story.id,
            ))
        if idx == 0:
            # A continuous promo field gives the skyline an editorial block
            # rather than a small web-style label floating over white space.
            ctx.elements.append(Element(
                id=f"skyline-field-{story.id}", role="band", importance=.08,
                content_ref=f"{story.id}.skyline_field", frame=Frame(x=x, y=y, w=copy_w, h=h),
                style=ElementStyle(bg_color=yellow), z=0,
                constraints=["decorative_background"], story_ref=story.id,
            ))
        if picture:
            placed_picture = picture
            if (idx == 0 and picture.width_px and picture.height_px
                    and picture.height_px / picture.width_px > 1.25
                    and picture_w / h > 1.7
                    and list(picture.focal_point or []) == [.5, .5]):
                # The default centre crop of a portrait in a wide skyline
                # routinely cuts off the face. Keep an explicit focal point
                # untouched; only improve the default when this geometry is
                # especially risky.
                placed_picture = picture.model_copy(update={"focal_point": [.5, max(.32, min(.42, float(g.get("poster_portrait_focal_y", .34))))]})
                ctx.fit.append({"action": "portrait_skyline_focal", "story_ref": story.id,
                                "image_ref": picture.id, "focal_point": placed_picture.focal_point})
            ctx.photo(story, placed_picture, x + w - picture_w, y, picture_w, h,
                      str(genes.get("photo_treatment", "crop")))
        if story.kicker:
            fit(story, "kicker", x, y, copy_w, 6, 8.8, color="#ffffff", bg=navy if idx % 2 else red)
        head_y = y + (7 if story.kicker else 1)
        wide_skyline = idx == 0 and w >= width * .8
        headline = None
        if wide_skyline and len(story.headline.split()) >= 4:
            skyline_plan = compose_display_headline(
                story.headline, width_mm=copy_w - 2, height_mm=h - 14,
                preferred_size_pt=min(43.0, dna.typography.scales.headline_s * 1.6),
                minimum_size_pt=20.0,
                font_families=[*(g.get("poster_teaser_font_candidates") or []), ctx.family("headline")],
                min_lines=2, max_lines=2,
            )
            if skyline_plan:
                headline = ctx.text("headline", story, "headline", x, head_y, copy_w,
                                    h - 14, skyline_plan.font_size_pt,
                                    value=skyline_plan.text, color=navy, bg_color=yellow)
                headline.style.font_family = skyline_plan.font_family
        if headline is None:
            headline = fit(story, "headline", x, head_y, copy_w,
                           min(14.0, h * .53) if wide_skyline else h * (.53 if idx < 2 else .55),
                           min(35.0 if idx < 2 else 30.0, dna.typography.scales.headline_s * 1.15),
            color=("#ffffff" if idx >= 2 and idx % 2 else navy if idx != 1 else red),
            bg=yellow if idx == 0 else None, minimum=13.0)
        if headline:
            from .fonts import resolve_font
            teaser_families = g.get("poster_teaser_font_candidates") or []
            selected = next((family for family in teaser_families
                             if resolve_font(family, bold=True, text=headline.text_content)), None)
            if selected:
                headline.style.font_family = selected
            headline.style.font_weight = "bold"
            headline.style.outline_color = "#ffffff" if idx in {0, 2, 3} else navy
            headline.style.outline_width_pt = .25
        if story.body:
            body_y = y + (h - 8.0 if wide_skyline else h * (.78 if idx < 2 else .69))
            fit(story, "body", x, body_y, copy_w,
                max(6.0, h - (body_y - y) - 2.0) if wide_skyline else h * (.20 if idx < 2 else .28),
                9.8 if idx < 2 else 9.6,
                color=("#ffffff" if idx >= 2 and idx % 2 else navy),
                words=10 if idx < 2 else 13, minimum=8.0)

    satellite(satellites[0], left, top_y, width, top_h, 0)

    image = lead.images[0]
    rail_w = max(62.0, min(79.0, width * float(g.get("poster_rail_width_share", .285))))
    hero_photo_w = width - rail_w - cell_gap
    hero_cutout = bool(dna.photo_rules.allow_cutout and
                       (image.alpha_mask_url or image.contour_polygon) and
                       (image.treatment == "cutout" or
                        (image.treatment is None and genes.get("photo_treatment") == "cutout")))
    if hero_cutout:
        # Only a genuine alpha/contour unlocks this morphology. The colour
        # field is a scene object behind the isolated people, not a painted
        # rectangle baked into the photo; it remains editable in IDML.
        ctx.elements.append(Element(
            id=f"hero-field-{lead.id}", role="band", importance=.08,
            content_ref=f"{lead.id}.hero_field",
            frame=Frame(x=left, y=hero_y, w=hero_photo_w, h=hero_h),
            style=ElementStyle(bg_color=yellow), z=0,
            constraints=["decorative_background"], story_ref=lead.id,
        ))
        if lead.kicker:
            sticker = ctx.text("kicker", lead, "kicker",
                               left + hero_photo_w * .47, hero_y + 7,
                               hero_photo_w * .48, 8, 14,
                               value=lead.kicker.upper(), color="#ffffff", bg_color=red)
            sticker.z = 5
    photo_rise = min(6.0, hero_h * .03) if hero_cutout else 0.0
    hero_photo = ctx.photo(lead, image, left, hero_y - photo_rise,
                           hero_photo_w, hero_h + photo_rise,
                           "cutout" if hero_cutout else str(genes.get("photo_treatment", "crop")))
    hero_cutout = hero_photo.treatment == "cutout"
    if lead.kicker and not hero_cutout:
        hero_badge = ctx.text("kicker", lead, "kicker", left + 6, hero_y + 8,
                              min(68.0, hero_photo_w * .42), 10.0, 15.0,
                              value=lead.kicker.upper(), color="#ffffff", bg_color=red)
        hero_badge.style.font_weight = "bold"
        hero_badge.frame.rotation_deg = -2.5
        hero_badge.constraints.append("intentional_photo_badge")
        hero_badge.z = 7
    headline_h = min(float(g.get("poster_headline_max_height_mm", 77.0)), hero_h * .39)
    headline_y = hero_y + hero_h - headline_h - 12
    # A distinct second-story rail gives the cover the observed collage
    # rhythm without covering the lead faces with arbitrary decorative boxes.
    rail_story = satellites[1]
    rail_x = left + hero_photo_w + cell_gap
    rail_image = (rail_story.images or [None])[0]
    rail_safe_h = headline_y - hero_y - 3
    # The lead title now stays inside the lead photograph, so the side rail
    # can use its complete height.  A tall emotional crop plus a compact copy
    # field avoids the empty coloured shaft produced by the old safe area.
    overlay_requested = genes.get("poster_headline_treatment") == "overlay"
    rail_photo_h = (max(38.0, hero_h * .68) if overlay_requested else max(30.0, rail_safe_h * .70)) if rail_image else 0.0
    if rail_image:
        ctx.photo(rail_story, rail_image, rail_x, hero_y, rail_w,
                  rail_photo_h, str(genes.get("photo_treatment", "crop")))
    rail_copy_y = hero_y + (rail_photo_h + 1 if rail_image else 0)
    rail_bottom = (hero_y + hero_h if overlay_requested
                   else hero_y + rail_safe_h)
    ctx.elements.append(Element(
        id=f"rail-field-{rail_story.id}", role="band", importance=.08,
        content_ref=f"{rail_story.id}.rail_field",
        frame=Frame(x=rail_x, y=rail_copy_y, w=rail_w,
                    h=max(2.0, rail_bottom - rail_copy_y)),
        style=ElementStyle(bg_color=navy), z=0,
        constraints=["decorative_background"], story_ref=rail_story.id,
    ))
    if rail_story.kicker:
        fit(rail_story, "kicker", rail_x, rail_copy_y, rail_w, 8.0,
            12.5, color="#ffffff", bg=red, minimum=10.0)
        rail_copy_y += 9.0
    rail_head_h = max(14.0, min(30.0, rail_bottom - rail_copy_y - (18.0 if rail_story.body else 0.0)))
    rail_headline = fit(rail_story, "headline", rail_x, rail_copy_y, rail_w,
        rail_head_h,
        min(38.0, dna.typography.scales.headline_s * 1.28), color="#ffffff",
        minimum=13.0)
    if rail_headline:
        rail_headline.style.font_weight = "bold"
    if rail_story.body:
        fit(rail_story, "body", rail_x, rail_copy_y + rail_head_h + 1, rail_w,
            max(8.0, rail_bottom - rail_copy_y - rail_head_h - 1),
            10.2, color="#ffffff", words=11, minimum=8.4)
    preferred_headline_size = min(112.0, dna.typography.scales.headline_xl * 1.55)
    urgent_display = str(getattr(material, "editorial_mood", "")) == "urgent"
    display_source = lead.headline.upper() if urgent_display else lead.headline
    display_plan = compose_display_headline(
        display_source,
        width_mm=hero_photo_w - 8,
        height_mm=headline_h - 1,
        preferred_size_pt=preferred_headline_size,
        minimum_size_pt=28.0,
        font_families=[*(g.get("display_font_candidates") or []), ctx.family("headline")],
        case_options=tuple(g.get("display_case_options") or ["normal"]),
        max_lines=3,
    )
    overlay = bool(display_plan and len(display_plan.lines) <= 2
                   and genes.get("poster_headline_treatment") == "overlay")
    headlines = []
    if overlay:
        # Each measured line is an independent scene object. A large opaque
        # rectangle hid the reporting photograph and looked like a web card.
        # Outlines and a restrained shadow keep the words legible while the
        # picture remains visible. The title DNA still supplies fonts/colors.
        from .fonts import resolve_font
        from .shaper import width_pt
        font_path = resolve_font(display_plan.font_family, bold=True, text=display_plan.text)
        line_h = (headline_h - 2.0) / len(display_plan.lines)
        for index, line in enumerate(display_plan.lines):
            measure = width_pt(line, display_plan.font_size_pt, font_path) if font_path else display_plan.line_widths_pt[index]
            scaled_size = min(display_plan.font_size_pt * 1.30,
                              line_h / PT / 1.06,
                              display_plan.font_size_pt * (hero_photo_w - 12) / PT / max(1.0, measure) * .80)
            headline = ctx.text("headline", lead, "headline", left + 4,
                                headline_y + index * line_h, hero_photo_w - 8, line_h,
                                max(28.0, round(scaled_size, 1)), value=line,
                                color=yellow, dominant=True)
            headline.style.font_family = display_plan.font_family
            headline.style.case = display_plan.case
            headline.style.outline_color = navy
            headline.style.outline_width_pt = 1.0
            headline.style.shadow_color = "#111111"
            headline.style.shadow_offset_x_pt = 1.2
            headline.style.shadow_offset_y_pt = 1.2
            headline.z = 6
            headline.flow_group = f"display-headline-{lead.id}"
            if index == 0:
                headline.transgressions.extend(["overlap-scrim", "diagonal-break", "extreme-scale"])
                headline.frame.rotation_deg = -1.5
            headlines.append(headline)
        ctx.fit.append({"action": "display_headline_composition", "story_ref": lead.id,
                        "lines": list(display_plan.lines), "font": display_plan.font_family,
                        "case": display_plan.case, "treatment": "photo_overlay"})
    else:
        if display_plan:
            headline = ctx.text("headline", lead, "headline", left + 3, headline_y, width - 6, headline_h,
                                display_plan.font_size_pt, value=display_plan.text,
                                color=yellow, bg_color=red, dominant=True)
            headline.style.font_family = display_plan.font_family
            headline.style.case = display_plan.case
            ctx.fit.append({"action": "display_headline_composition", "story_ref": lead.id,
                            "lines": list(display_plan.lines), "font": display_plan.font_family,
                            "font_size_pt": display_plan.font_size_pt, "case": display_plan.case})
        else:
            headline = fit(lead, "headline", left + 3, headline_y, width - 6, headline_h,
                           preferred_headline_size, color=yellow, bg=red,
                           minimum=28.0, dominant=True)
        if headline:
            headlines.append(headline)
    if not overlay:
        for headline in headlines:
            # These treatments are title-DNA data and survive in the scene graph,
            # so preview and press PDF use the same display typography.
            headline.style.outline_color = g.get("display_outline_color") or navy
            headline.style.outline_width_pt = float(g.get("display_outline_width_pt", .5))
            headline.style.shadow_color = g.get("display_shadow_color") or "#4b1420"
            headline.style.shadow_offset_x_pt = float(g.get("display_shadow_offset_x_pt", .8))
            headline.style.shadow_offset_y_pt = float(g.get("display_shadow_offset_y_pt", .8))
            headline.z = 6
            headline.transgressions.extend(["overlap-scrim", "diagonal-break", "extreme-scale"])
            headline.frame.rotation_deg = -1.5 if genes.get("layout_mode") == "photo-top" else 0.0
    if lead.body:
        fit(lead, "body", left + 4, body_y, width - 8, lead_body_h, 10.0,
            color=navy, bg=yellow, minimum=9.0, words=24)

    bottom_widths = (round((width - cell_gap) * .43, 2), round((width - cell_gap) * .57, 2))
    for i, story in enumerate(satellites[2:4]):
        satellite(story, left + (bottom_widths[0] + cell_gap if i else 0), bottom_y,
                  bottom_widths[i], bottom_h, i + 2)
    for story in extra:
        ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                        "reason": "Temat pozostaje w wydaniu; poza pięcioma miejscami na pierwszej stronie"})
    for story in stories[:5]:
        for field in ("kicker", "deck", "lead"):
            if getattr(story, field, None) and not any(el.content_ref == f"{story.id}.{field}" for el in ctx.elements):
                ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id, "field": field,
                                "reason": "Pełny tekst pozostaje w materiale źródłowym"})
        members = [el.id for el in ctx.elements if el.story_ref == story.id]
        if members:
            ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
    missing = [f"{s.id}.{field}" for s in stories[:5] for field in ("headline", "body")
               if getattr(s, field, None) and not any(el.content_ref == f"{s.id}.{field}" for el in ctx.elements)]
    return SceneGraph(
        page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm,
                      safe_margin_mm=min(left, top), grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                      "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                      title_dna_ref=dna.id, page_zone="front_page"),
        elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
        metadata={"generator": "plan_composer", "architecture": "popular_poster", "layout_mode": "photo-top",
                  "cover_morphology": "subject_cutout_collage" if hero_cutout else
                                      "photo_overlay_collage" if overlay else str(g.get("poster_morphology", "asymmetric_hero_rail")),
                  "page_zone": "front_page", "page_count": 1, "single_page_width_mm": fmt.trim_w_mm,
                  "style_readiness": {"status": "ready", "warnings": [],
                                      "photo_story_count": len({story.id for story in stories if story.images}),
                                      "story_count": len(stories)},
                  "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                  "style_blend": material.style_blend.model_dump(), "text_threads": {}})


def _compose_popular_type_cover(dna, material, genes: dict, stories: list) -> SceneGraph:
    """A type-led popular cover: skyline, nameplate, giant text, portrait, briefs.

    The roles and proportions come from TitleDNA.  This is an alternative
    architecture to the photo-led poster, rather than a traced source page.
    It uses ordinary cropped photos when no genuine alpha mask is available.
    """
    ctx = _Ctx(dna, material, genes)
    fmt, g = dna.format, dna.cover_grammar or {}
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    right, bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
    width = right - left
    gap = max(3.0, dna.grid.gutter_mm)
    mood = resolve_page_mood(material).name
    red, navy, yellow = story_color_roles(dna, mood)
    lead = stories[0]
    skyline = stories[1:3]
    briefs = stories[3:5]
    skyline_h = max(32.0, min(45.0, float(g.get("type_led_skyline_height_mm", 38))))
    mast_h = max(32.0, min(48.0, float(g.get("type_led_masthead_height_mm", 39))))
    bottom_h = max(66.0, min(82.0, float(g.get("type_led_bottom_height_mm", 72))))

    def fit(story, field, x, y, w, h, size, *, color=None, bg=None, min_size=8.0, words=None, dominant=False):
        source = str(getattr(story, field, "") or "")
        if not source:
            return None
        role = "headline" if field == "headline" else "body" if field == "body" else field
        candidate = source
        if words and len(candidate.split()) > words:
            candidate, meta = rewrite_source_bound_copy(source, role=role, target_words=words,
                                                         locked_passages=getattr(story, "locked_passages", []))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                            "field": field, "from_words": len(source.split()),
                            "to_words": len(candidate.split()), "metadata": meta})
        while size > min_size and not _cover_copy_fits(ctx, candidate, w, h - 1, role, size):
            size = max(min_size, round(size * .92, 2))
        if not _cover_copy_fits(ctx, candidate, w, h - 1, role, size):
            budget = max(4, int(len(source.split()) * (h - 1) / max(h, ctx.need(source, w, role, size)) * .85))
            candidate, meta = rewrite_source_bound_copy(source, role=role, target_words=budget,
                                                         locked_passages=getattr(story, "locked_passages", []))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                            "field": field, "from_words": len(source.split()),
                            "to_words": len(candidate.split()), "metadata": meta})
        return ctx.text(role, story, field, x, y, w, h, size, value=candidate,
                        color=color, bg_color=bg, dominant=dominant)

    def compact_story(story, x, y, w, h, index):
        picture = story.images[0]
        image_w = min(w * .38, picture.width_px * 25.4 / dna.photo_rules.min_dpi)
        text_w = w - image_w - 2
        if image_w >= 20:
            placed = picture
            if picture.height_px > picture.width_px * 1.25 and list(picture.focal_point or []) == [.5, .5]:
                placed = picture.model_copy(update={"focal_point": [.5, max(.32, min(.42, float(g.get("poster_portrait_focal_y", .34))))]})
            ctx.photo(story, placed, x + w - image_w, y, image_w, h, str(genes.get("photo_treatment", "crop")))
        else:
            text_w = w
        if story.kicker:
            fit(story, "kicker", x, y, text_w, 5.4, 8.5, color="#ffffff", bg=red if index % 2 == 0 else navy)
        head_y = y + (6 if story.kicker else 1)
        headline = fit(story, "headline", x, head_y, text_w, h * .55,
                       25.0, color=navy if index % 2 == 0 else red, min_size=14.0)
        if headline:
            from .fonts import resolve_font
            headline.style.font_family = next(
                (name for name in g.get("poster_teaser_font_candidates", [])
                 if resolve_font(name, bold=True, text=headline.text_content)), headline.style.font_family)
        if story.body:
            fit(story, "body", x, y + h * .70, text_w, h * .27,
                8.5, color=navy, min_size=7.8, words=11)

    skyline_split = max(.45, min(.62, float(genes.get("type_led_skyline_split", g.get("type_led_skyline_split", .54)))))
    skyline_widths = ((width - gap) * skyline_split, (width - gap) * (1 - skyline_split))
    for i, story in enumerate(skyline):
        compact_story(story, left + (skyline_widths[0] + gap if i else 0), top,
                      skyline_widths[i], skyline_h, i)

    mast_y = top + skyline_h + 4
    logo = ctx.text("logo", None, "masthead", left, mast_y, width, mast_h,
                    min(90.0, mast_h / PT * .70), value=material.masthead_title,
                    color="#ffffff", bg_color=navy)
    if logo and getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
        logo.image_url = dna.logo_profile.asset_ref
        logo.content_ref = "masthead.logo"
        logo.style.bg_color = None
    folio_y = mast_y + mast_h + 1
    ctx.text("folio", None, "issue", left, folio_y, width, 6.0, 8.5,
             value=f"{material.issue_date}  ·  {material.issue_number}  ·  {material.section_name}")

    main_y = folio_y + 9
    bottom_y = bottom - bottom_h
    main_h = bottom_y - main_y - 4
    photo_share = max(.34, min(.48, float(genes.get("type_led_photo_share", g.get("type_led_photo_width_share", .41)))))
    photo_w = min(width * photo_share, lead.images[0].width_px * 25.4 / dna.photo_rules.min_dpi)
    text_w = width - photo_w - gap
    mask_available = bool(lead.images[0].alpha_mask_url or lead.images[0].contour_polygon)
    use_cutout = mask_available and lead.images[0].treatment != "crop"
    photo_overlap = min(10.0, photo_w * .09) if use_cutout else 0.0
    photo_raise = min(19.0, mast_h * .48) if use_cutout else 0.0
    photo_x = right - photo_w - photo_overlap
    # A real cutout can sit over a colour field. The field is its own scene
    # object, so PDF, SVG and HTML use the same geometry and palette role.
    if use_cutout:
        ctx.elements.append(Element(
            id=f"subject-field-{lead.id}", role="band", importance=.08,
            content_ref=f"{lead.id}.subject_field",
            frame=Frame(x=photo_x - 2, y=main_y + main_h * .10,
                        w=right - photo_x + 2, h=main_h * .80),
            style=ElementStyle(bg_color=yellow), z=0,
            constraints=["decorative_background"], story_ref=lead.id,
        ))
    lead_image = lead.images[0]
    if lead_image.height_px > lead_image.width_px * 1.25 and list(lead_image.focal_point or []) == [.5, .5]:
        lead_image = lead_image.model_copy(update={"focal_point": [.5, .3]})
    hero_photo = ctx.photo(lead, lead_image, photo_x, main_y - photo_raise,
                           photo_w + photo_overlap, main_h + photo_raise,
                           "cutout" if use_cutout else str(genes.get("photo_treatment", "crop")))
    if use_cutout and hero_photo.treatment == "cutout":
        ctx.fit.append({"action": "subject_breaks_masthead", "story_ref": lead.id,
                        "overlap_mm": round(photo_raise, 2),
                        "reason": "Rzeczywista maska alfa pozwala sylwetce przejść przez ramę zdjęcia"})

    if lead.kicker:
        fit(lead, "kicker", left, main_y + 4, text_w, 10.0, 15.0,
            color="#ffffff", bg=red, min_size=10.0)
    display_y = main_y + (19.0 if lead.kicker else 6.0)
    support_h = min(51.0, max(33.0, main_h * .23))
    display_h = main_h - (display_y - main_y) - support_h - 5.0
    font_candidates = list(g.get("display_font_candidates") or [ctx.family("headline")])
    if mood in {"solemn", "analytical", "practical"}:
        font_candidates = list(dict.fromkeys([ctx.family("headline"), *font_candidates]))
    plan = compose_display_headline(
        lead.headline, width_mm=text_w, height_mm=display_h,
        preferred_size_pt=min(145.0, dna.typography.scales.headline_xl * 1.95),
        minimum_size_pt=30.0,
        font_families=font_candidates,
        case_options=("normal",) if mood in {"solemn", "human", "analytical", "practical"}
                     else tuple(g.get("display_case_options") or ["normal"]),
        min_lines=2 if len(lead.headline.split()) >= 4 else 1,
        max_lines=3 if len(lead.headline.split()) <= 8 else 4,
        allow_internal_single_word=False,
    )
    story_strap_layout = bool(plan and use_cutout and len(plan.lines) == 2
                              and mood in {"urgent", "human", "celebratory"})
    if plan:
        from .shaper import width_pt
        from .fonts import resolve_font
        path = resolve_font(plan.font_family, bold=True, text=plan.text)
        line_h = min(display_h / len(plan.lines) * .60,
                     max(23.0, plan.font_size_pt * PT * 1.30))
        line_details = []
        for line_index, line in enumerate(plan.lines):
            story_strap = story_strap_layout and line_index == 1
            line_width = width if story_strap else text_w
            # Keep the two halves of one headline together. The older
            # percentage-of-page placement put deck and body *between* the
            # headline lines and left a conspicuous empty rectangle.
            strap_gap = 1.0 + (max(.45, min(.58, float(genes.get("type_led_strap_y", .52)))) - .45) * 16.0
            line_y = display_y + line_h + strap_gap if story_strap else display_y + line_index * line_h
            line_height = min(33.0, line_h * 1.15) if story_strap else line_h
            measured = width_pt(line, plan.font_size_pt, path) if path else plan.line_widths_pt[line_index]
            width_scale = line_width / PT * .96 / max(1.0, measured)
            line_size = round(min(plan.font_size_pt * 2.0,
                                  line_height / PT / 1.09,
                                  plan.font_size_pt * width_scale), 1)
            line_color = "#ffffff" if story_strap else red if line_index == 1 else g.get("type_led_headline_color", "#17212b")
            headline = ctx.text("headline", lead, "headline", left,
                                line_y, line_width, line_height,
                                line_size, value=line, color=line_color, bg_color=red if story_strap else None,
                                dominant=True)
            headline.style.font_family = plan.font_family
            headline.style.case = plan.case
            headline.style.outline_color = navy if story_strap else "#ffffff"
            headline.style.outline_width_pt = .55 if story_strap else .45
            if story_strap:
                headline.z = 6
            if line_index == 0:
                headline.transgressions.append("extreme-scale")
            line_details.append({"text": line, "font_size_pt": line_size, "color": line_color})
        ctx.fit.append({"action": "display_headline_composition", "story_ref": lead.id,
                        "lines": list(plan.lines), "font": plan.font_family,
                        "line_details": line_details, "case": plan.case})
    else:
        fit(lead, "headline", left, display_y, text_w, display_h,
            50.0, color=navy, min_size=30.0, dominant=True)
    support_y = (display_y + line_h + strap_gap + min(33.0, line_h * 1.15) + 4.0
                 if story_strap_layout else main_y + main_h - support_h)
    if lead.deck:
        fit(lead, "deck", left, support_y, text_w, 19.0, 16.0,
            color=navy, bg=yellow, min_size=9.0, words=15)
    if lead.body:
        body_y = support_y + (21.0 if lead.deck else 2.0)
        body_height = main_y + main_h - body_y - 2
        fit(lead, "body", left, body_y, text_w, max(8.0, body_height),
            10.3, color=navy, min_size=8.2, words=65)

    bottom_split = max(.38, min(.60, float(genes.get("type_led_bottom_split", g.get("type_led_bottom_split", .43)))))
    bottom_widths = ((width - gap) * bottom_split, (width - gap) * (1 - bottom_split))
    for i, story in enumerate(briefs):
        compact_story(story, left + (bottom_widths[0] + gap if i else 0), bottom_y,
                      bottom_widths[i], bottom_h, i + 2)
    for story in stories[:5]:
        for field in ("kicker", "deck", "lead"):
            if getattr(story, field, None) and not any(el.content_ref == f"{story.id}.{field}" for el in ctx.elements):
                ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                                "field": field, "reason": "Pełny tekst pozostaje w materiale źródłowym"})
        members = [el.id for el in ctx.elements if el.story_ref == story.id]
        if members:
            ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
    for story in stories[5:]:
        ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                        "reason": "Temat pozostaje w wydaniu; poza pięcioma miejscami na pierwszej stronie"})
    missing = [f"{s.id}.{field}" for s in stories[:5] for field in ("headline", "body")
               if getattr(s, field, None) and not any(el.content_ref == f"{s.id}.{field}" for el in ctx.elements)]
    return SceneGraph(
        page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm,
                      safe_margin_mm=min(left, top), grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                      "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                      title_dna_ref=dna.id, page_zone="front_page"),
        elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
        metadata={"generator": "plan_composer", "architecture": "popular_type_led", "layout_mode": "type-led",
                  "cover_morphology": "skyline_type_portrait", "page_zone": "front_page", "page_count": 1,
                  "single_page_width_mm": fmt.trim_w_mm,
                  "style_readiness": {"status": "ready", "warnings": [], "photo_story_count": 5,
                                      "story_count": len(stories)},
                  "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                  "style_blend": material.style_blend.model_dump(), "text_threads": {}})


def _compose_editorial_or_service_cover(dna, material, genes: dict) -> SceneGraph:
    """Two data-driven front-page grammars with the same scene-graph contract."""
    ctx = _Ctx(dna, material, genes)
    fmt, sc = dna.format, dna.typography.scales
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    right, bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
    width = right - left
    is_guide = (getattr(dna, "cover_grammar", {}) or {}).get("family") == "service_grid" or dna.archetype == "tv_guide"
    family = "service_grid" if is_guide else "editorial_cover"
    stories = sorted([story.model_copy(deep=True) for story in material.stories], key=lambda story: -story.importance)
    lead, seconds = stories[0], stories[1:]

    def put(story, field, x, y, w, h, size, *, color=None, bg=None, dominant=False, minimum=7.0):
        source = str(getattr(story, field, "") or "")
        if not source:
            return None
        role = "headline" if field == "headline" else "body" if field == "body" else field
        value = source
        fit_h = max(2.0, h - 1.5)
        while size > minimum and not _cover_copy_fits(ctx, value, w, fit_h, role, size):
            size = max(minimum, round(size * .90, 1))
        if not _cover_copy_fits(ctx, value, w, fit_h, role, size):
            target = max(4, int(len(source.split()) * fit_h / max(fit_h, ctx.need(source, w, role, size)) * .85))
            for _ in range(8):
                value, meta = rewrite_source_bound_copy(source, role=role, target_words=target,
                                                        locked_passages=getattr(story, "locked_passages", []))
                if _cover_copy_fits(ctx, value, w, fit_h, role, size):
                    break
                target = max(3, int(target * .75))
            ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id, "field": field,
                            "from_words": len(source.split()), "to_words": len(value.split()),
                            "reason": "Krótka zajawka na pierwszej stronie", "metadata": meta})
        return ctx.text(role, story, field, x, y, w, h, size, value=value,
                        color=color, bg_color=bg, dominant=dominant)

    brand_bg = dna.palette.primary if is_guide else None
    brand_color = "#ffffff" if is_guide else dna.palette.primary
    mast_h = 25 if is_guide else 28
    logo = ctx.text("logo", None, "masthead", left, top, width, mast_h,
                    37 if is_guide else 43, value=material.masthead_title,
                    color=brand_color, bg_color=brand_bg, align="center")
    if getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
        logo.image_url, logo.content_ref = dna.logo_profile.asset_ref, "masthead.logo"
    y = top + mast_h + 2
    ctx.text("folio", None, "issue", left, y, width, 5, 7.5,
             value=f"{material.issue_date}  ·  {material.issue_number}  ·  {material.section_name}")
    y += 8

    if is_guide:
        # A guide is navigated by sections and repeatable cards, not a single
        # poster headline. The issue's real articles supply the card copy.
        ctx.text("kicker", None, "navigation", left, y, width, 8, 10,
                 value=(material.section_name or "PRZEWODNIK").upper(),
                 color="#ffffff", bg_color=dna.palette.secondary)
        y += 11
        hero_h = min(95.0, max(62.0, (bottom - y) * .46))
        photo_w = width * .55
        reverse = str(genes.get("layout_mode", "")) == "dominant-right"
        photo_x = right - photo_w if reverse else left
        text_x = left if reverse else left + photo_w + 4
        text_w = width - photo_w - 4
        if lead.images:
            ctx.photo(lead, lead.images[0], photo_x, y, photo_w, hero_h, str(genes.get("photo_treatment", "crop")))
        if lead.kicker:
            put(lead, "kicker", text_x, y, text_w, 8, 9, color=dna.palette.secondary, minimum=8)
        put(lead, "headline", text_x, y + 11, text_w, 34, min(27, sc.headline_l),
            dominant=True, minimum=17)
        if lead.body:
            put(lead, "body", text_x, y + 49, text_w, hero_h - 51, 8.5, minimum=7.5)
        y += hero_h + 5
        rows = math.ceil(len(seconds) / 2)
        cell_w = (width - 4) / 2
        cell_h = max(34.0, (bottom - y - max(0, rows - 1) * 4) / max(1, rows))
        for i, story in enumerate(seconds):
            row, col = divmod(i, 2)
            x, yy = left + col * (cell_w + 4), y + row * (cell_h + 4)
            bg = dna.palette.tint_bg if i % 2 == 0 else "#e5edf4"
            if story.kicker:
                put(story, "kicker", x + 2, yy + 2, cell_w - 4, 7, 8.5, color=dna.palette.secondary, bg=bg, minimum=8)
            # The headline starts below the kicker; the body starts below the
            # headline's real frame (the old fixed offsets overlapped on
            # 4+ cards in a compact guide format).
            head_h = min(28.0, (cell_h - 11) * .45)
            put(story, "headline", x + 2, yy + 11, cell_w - 4, head_h,
                min(18, sc.headline_s), color=dna.palette.primary, bg=bg, minimum=13)
            if story.body:
                body_y = yy + 11 + head_h + 1
                put(story, "body", x + 2, body_y, cell_w - 4, max(7, yy + cell_h - body_y - 2),
                    8.2, color=dna.palette.text, bg=bg, minimum=7.2)
    else:
        # Magazine: restrained cover lines, one wide photographic field and
        # deliberate white space; no colored news ticker or card mosaic.
        rows = math.ceil(len(seconds) / 2)
        teaser_h = 22 if rows > 1 else 27
        cell_w = (width - 8) / 2
        for i, story in enumerate(seconds):
            row, col = divmod(i, 2)
            x, yy = left + col * (cell_w + 8), y + row * (teaser_h + 3)
            put(story, "headline", x, yy, cell_w, teaser_h * .58,
                min(17, sc.headline_s), color=dna.palette.primary, minimum=11.5)
            if story.body:
                put(story, "body", x, yy + teaser_h * .62, cell_w, teaser_h * .32,
                    7.7, minimum=7.0)
        y += rows * (teaser_h + 3) + 2
        ctx.rule(left, y, width, "cover-lines")
        y += 4
        headline_h = 37
        body_h = 19
        photo_h = max(52.0, bottom - y - headline_h - body_h - 8)
        if lead.images:
            ctx.photo(lead, lead.images[0], left, y, width, photo_h, str(genes.get("photo_treatment", "crop")))
        y += photo_h + 3
        if lead.kicker:
            put(lead, "kicker", left, y, width, 6, 8.8, color=dna.palette.secondary, minimum=8)
            y += 7
        put(lead, "headline", left, y, width, headline_h - 7, min(38, sc.headline_l),
            color=dna.palette.primary, dominant=True, minimum=22)
        y += headline_h - 4
        if lead.body:
            put(lead, "body", left, y, width, max(7, bottom - y), sc.body, minimum=7.8)

    rendered = {el.content_ref for el in ctx.elements}
    missing = [f"{story.id}.{field}" for story in stories for field in ("headline", "body")
               if getattr(story, field, None) and f"{story.id}.{field}" not in rendered]
    for story in stories:
        members = [el.id for el in ctx.elements if el.story_ref == story.id]
        if members:
            ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
    return SceneGraph(page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm,
                                    safe_margin_mm=min(left, top), grid={"cols": dna.grid.columns,
                                    "gutter_mm": dna.grid.gutter_mm, "baseline_mm": dna.grid.baseline_grid_pt * PT,
                                    "rows": dna.grid.rows}, title_dna_ref=dna.id, page_zone="front_page"),
                      elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
                      metadata={"generator": "plan_composer", "architecture": family,
                                "layout_mode": genes.get("layout_mode", "dominant-left"), "page_zone": "front_page",
                                "page_count": 1, "single_page_width_mm": fmt.trim_w_mm,
                                "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                                "style_blend": material.style_blend.model_dump(), "text_threads": {}})
