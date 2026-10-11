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
from .image_ops import photo_cutout_geometry

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
    def text(self, role, story, field, x, y, w, h, size, *, cols=1, value=None, dominant=False, align=None) -> Optional[Element]:
        value = value if value is not None else (getattr(story, field, None) if story is not None else None)
        if not value:
            return None
        eid = f"{role}-{story.id if story else role}-{len(self.elements)}"
        style = ElementStyle(font_family=self.family(role), font_size_pt=round(size, 2), line_height_pt=round(self.leading(role, size), 2),
                             font_weight="bold" if self.bold(role) else "normal",
                             color=self.dna.palette.secondary if role in {"kicker", "label"} else self.dna.palette.text,
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


def compose_planned_page(dna, material, genes: Optional[dict] = None) -> SceneGraph:
    from .logo import masthead_geometry
    genes = genes or {}
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
    if teasers and zone == "front_page":
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
    return SceneGraph(page=PageMeta(trim=[page_w, page_h], bleed_mm=fmt.bleed_mm, safe_margin_mm=min(left, top),
                                    grid={"cols": grid.columns, "gutter_mm": gut, "baseline_mm": grid.baseline_grid_pt * PT, "rows": grid.rows},
                                    title_dna_ref=dna.id, page_zone=zone),
                      elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
                      metadata={"generator": "plan_composer", "page_zone": zone, "page_count": 1, "single_page_width_mm": page_w,
                                "layout_mode": gene_mode, "architecture": arch, "rail_cols": rail_cols, "masthead_mode": mg["mode"],
                                "photo_placement": "top", "missing_content_refs": missing, "underfill_mm": max(0.0, underfill), "fit_adjustments": ctx.fit,
                                "style_blend": material.style_blend.model_dump(), "text_threads": {}})
