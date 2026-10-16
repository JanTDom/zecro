"""Magazine cover and opening-spread morphologies.

A magazine is not a tabloid with fewer elements.  These grammars rely on a
leading photograph, deliberate negative space, cover lines that respond to the
silhouette or gaze direction, an elegant serif/sans pairing and controlled
contrast.  Proportions come from ``TitleDNA.cover_grammar["magazine_morphologies"]``
(explicit editorial starting values otherwise).

Cover lines may sit on the photograph only in its *negative space*: the
composer measures the luminance of the actual pixels under the line, picks the
ink with the higher contrast and records the ratio.  When the region is busy
or the source is unavailable, the line gets a plate instead.  The hard gate
re-checks both conditions (``photo_negative_space`` constraint).
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, Relation, SceneGraph
from .display_headline import compose_display_headline
from .page_mood import mood_form, relative_luminance, resolve_page_mood

DEFAULTS: dict[str, dict[str, Any]] = {
    "portrait_cover": {"masthead_mm": 46.0, "line_column_share": .38, "headline_share": .20, "min_contrast": 4.5},
    "detail_still_life": {"masthead_mm": 40.0, "photo_share": .56, "photo_aspect": 1.0, "line_gap_mm": 6.0},
    "reportage_cover": {"masthead_mm": 38.0, "photo_share": .60, "strip_mm": 46.0},
    "typographic_cover": {"masthead_mm": 34.0, "type_share": .46, "photo_share": .40},
    "opening_spread": {"body_columns": 2},
}
CATALOG = ("portrait_cover", "detail_still_life", "reportage_cover", "typographic_cover")
NEGATIVE_SPACE_CONSTRAINT = "photo_negative_space"


def params(dna, name: str) -> dict[str, Any]:
    grammar = getattr(dna, "cover_grammar", None) or {}
    return {**DEFAULTS[name], **((grammar.get("magazine_morphologies") or {}).get(name) or {})}


def is_magazine(dna) -> bool:
    family = (getattr(dna, "cover_grammar", None) or {}).get("family")
    return family == "editorial_cover" or getattr(dna, "archetype", None) == "editorial_magazine"


def _print_ok(dna, image, width_mm: float) -> bool:
    return bool(image and image.width_px and image.width_px >= width_mm * dna.photo_rules.min_dpi / 25.4 * .95)


def feasible(dna, material) -> dict[str, str]:
    stories = sorted(material.stories, key=lambda s: -s.importance)
    if not stories or not is_magazine(dna):
        return {}
    lead_image = (stories[0].images or [None])[0]
    out = {"typographic_cover": "okładka typograficzna nie wymaga dużego zdjęcia"}
    if lead_image:
        out["detail_still_life"] = "zdjęcie główne jako detal z przestrzenią negatywną"
        width = dna.format.trim_w_mm - dna.format.margin_left_mm - dna.format.margin_right_mm
        if _print_ok(dna, lead_image, width):
            out["reportage_cover"] = "rozdzielczość na pełną szerokość łamu"
        from .tabloid_morphologies import analysis
        data = analysis(lead_image)
        person = int(data.get("face_count") or 0) >= 1 or data.get("subject_kind") == "person"
        box = data.get("subject_box")
        free = max(float(box[1]), 1.0 - float(box[3])) if box and len(box) == 4 else .0
        # Cover lines need real negative space beside the figure.
        if person and free >= .30 and _print_ok(dna, lead_image, dna.format.trim_w_mm + 2 * dna.format.bleed_mm):
            out["portrait_cover"] = "fotoedytor potwierdził postać; rozdzielczość na spad"
    return out


def _side_of_lines(image) -> str:
    """Cover lines go where the subject is not, toward its gaze if known."""
    from .tabloid_morphologies import analysis, column_side
    data = analysis(image)
    box = data.get("subject_box")
    if box and len(box) == 4:
        # Lines go to the wider free side of the subject box.
        left_free, right_free = float(box[1]), 1.0 - float(box[3])
        if abs(left_free - right_free) > .06:
            return "left" if left_free > right_free else "right"
    fx = float((image.focal_point or [.5, .5])[0])
    if abs(fx - .5) > .08:
        return "left" if fx > .5 else "right"
    return column_side(image) or "left"


def measure_region(image, element: Element, frame: Frame) -> Optional[dict[str, float]]:
    """Mean luminance and texture of the photo pixels under ``frame``."""
    from .image_ops import resolve_asset_path
    path = resolve_asset_path(image.url)
    if not path or not element.crop_box:
        return None
    try:
        from PIL import Image, ImageStat
        with Image.open(path) as source:
            w, h = source.size
            l, t, r, b = element.crop_box
            fx0 = (frame.x - element.frame.x) / element.frame.w
            fy0 = (frame.y - element.frame.y) / element.frame.h
            fx1 = (frame.x + frame.w - element.frame.x) / element.frame.w
            fy1 = (frame.y + frame.h - element.frame.y) / element.frame.h
            box = (int((l + (r - l) * max(0, fx0)) * w), int((t + (b - t) * max(0, fy0)) * h),
                   int((l + (r - l) * min(1, fx1)) * w), int((t + (b - t) * min(1, fy1)) * h))
            if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                return None
            region = source.crop(box).convert("L")
            region.thumbnail((200, 200))
            stat = ImageStat.Stat(region)
            return {"mean": stat.mean[0] / 255.0, "std": stat.stddev[0] / 255.0}
    except Exception:
        return None


def _contrast(lum_a: float, lum_b: float) -> float:
    hi, lo = max(lum_a, lum_b), min(lum_a, lum_b)
    return (hi + .05) / (lo + .05)


class _Mag:
    def __init__(self, dna, material, genes, name):
        from .plan_composer import _Ctx
        self.dna, self.material, self.genes, self.name = dna, material, genes, name
        self.ctx = _Ctx(dna, material, genes)
        fmt = dna.format
        self.trim_w, self.trim_h, self.bleed = fmt.trim_w_mm, fmt.trim_h_mm, fmt.bleed_mm
        self.left, self.top = fmt.margin_left_mm, fmt.margin_top_mm
        self.right, self.bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
        self.width = self.right - self.left
        self.p = params(dna, name)
        self.form = mood_form(dna, resolve_page_mood(material).name)
        self.stories = sorted([s.model_copy(deep=True) for s in material.stories], key=lambda s: -s.importance)
        self.used: list[str] = []
        self.decisions: list[dict[str, Any]] = []
        self.contrast: dict[str, float] = {}
        self.subject_boxes: dict[str, list[float]] = {}
        self.pal = dna.palette

    def fit(self, story, field, x, y, w, h, size, **kw):
        from .tabloid_morphologies import _Cover
        return _Cover.fit(self, story, field, x, y, w, h, size, **kw)  # same source-bound fitting

    def masthead(self, *, color, height=None, over_photo=False) -> Element:
        from .plan_composer import PT
        mh = float(height or self.p.get("masthead_mm", 40.0))
        plan = compose_display_headline(self.material.masthead_title, width_mm=self.width, height_mm=mh,
                                        preferred_size_pt=min(150.0, mh / PT * .92), minimum_size_pt=24.0,
                                        font_families=[self.ctx.family("logo")], max_lines=1)
        logo = self.ctx.text("logo", None, "masthead", self.left, self.top, self.width, mh,
                             plan.font_size_pt if plan else 60.0, value=self.material.masthead_title,
                             color=color, align="center")
        logo.z = 8 if over_photo else 2
        if getattr(self.dna, "logo_profile", None) and self.dna.logo_profile.asset_ref:
            logo.image_url, logo.content_ref = self.dna.logo_profile.asset_ref, "masthead.logo"
        return logo

    def photo(self, story, image, x, y, w, h, *, bleed=False):
        element = self.ctx.photo(story, image, x, y, w, h, "crop")
        from .tabloid_morphologies import analysis
        box = analysis(image).get("subject_box")
        if box and len(box) == 4 and element.crop_box:
            l, t, r, b = element.crop_box
            def mx(u): return x + w * (float(u) - l) / max(1e-6, r - l)
            def my(v): return y + h * (float(v) - t) / max(1e-6, b - t)
            self.subject_boxes[element.id] = [round(mx(box[1]), 2), round(my(box[0]), 2),
                                              round(mx(box[3]), 2), round(my(box[2]), 2)]
        if bleed:
            element.treatment = "full-bleed"
            element.transgressions = [*(element.transgressions or []), "bleed-off"]
        self.used.append(story.id)
        return element

    def line_on_photo(self, story, field, photo_el, image, x, y, w, h, size, *, words=None, minimum=9.0,
                      bold=False, dominant=False):
        """Cover line over the photograph's negative space (measured)."""
        frame = Frame(x=x, y=y, w=w, h=h)
        stats = measure_region(image, photo_el, frame)
        if stats and stats["std"] <= .16:
            dark, light = "#111111", "#ffffff"
            on_dark = _contrast(relative_luminance(light), stats["mean"] ** 2.2)
            on_light = _contrast(relative_luminance(dark), stats["mean"] ** 2.2)
            ink, ratio = (light, on_dark) if on_dark >= on_light else (dark, on_light)
            if ratio >= float(self.p.get("min_contrast", 4.5)) or (dominant and ratio >= 3.0):
                element = self.fit(story, field, x, y, w, h, size, color=ink, words=words, minimum=minimum,
                                   dominant=dominant)
                if element is not None:
                    element.constraints.append(NEGATIVE_SPACE_CONSTRAINT)
                    element.z = 7
                    if bold:
                        element.style.font_weight = "bold"
                    self.contrast[element.id] = round(ratio, 2)
                return element
        # Busy or unmeasurable region: a quiet plate keeps the line legible.
        element = self.fit(story, field, x, y, w, h, size, color=self.pal.primary, bg=self.pal.background,
                           words=words, minimum=minimum, dominant=dominant)
        if element is not None:
            # The plate is only as tall as the measured copy (no empty boxes).
            need = self.ctx.need(element.text_content, w, element.role, element.style.font_size_pt) + 2
            element.frame.h = min(element.frame.h, max(6.0, need))
            element.constraints.append(NEGATIVE_SPACE_CONSTRAINT)
            element.z = 7
            if bold:
                element.style.font_weight = "bold"
            self.contrast[element.id] = round(_contrast(relative_luminance(self.pal.primary),
                                                        relative_luminance(self.pal.background)), 2)
            self.decisions.append({"decision": "cover_line_plate", "story_ref": story.id,
                                   "reason": "zbyt niespokojne tło zdjęcia" if stats else "brak pliku do pomiaru kontrastu"})
        return element

    def finish(self, extra: dict[str, Any], *, spread: bool = False) -> SceneGraph:
        from .plan_composer import PT
        from .tabloid_morphologies import topology_signature
        ctx, dna, fmt = self.ctx, self.dna, self.dna.format
        used = [s for s in self.stories if s.id in set(self.used)]
        for story in self.stories:
            if story.id not in self.used:
                ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                                "reason": "Temat pozostaje w wydaniu; poza okładką tej morfologii"})
            members = [el.id for el in ctx.elements if el.story_ref == story.id]
            if members:
                ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
        required = ("headline",) if not spread else ("headline", "body")
        missing = [f"{s.id}.{field}" for s in used for field in required
                   if getattr(s, field, None) and not any(el.content_ref == f"{s.id}.{field}" for el in ctx.elements)]
        width = fmt.trim_w_mm * (2 if spread else 1)
        scene = SceneGraph(
            page=PageMeta(trim=[width, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm, safe_margin_mm=min(self.left, self.top),
                          grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                                "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                          title_dna_ref=dna.id, page_zone="spread" if spread else "front_page"),
            elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
            metadata={"generator": "plan_composer", "architecture": "editorial_cover" if not spread else "magazine_opening_spread",
                      "layout_mode": "magazine", "cover_morphology": self.name,
                      "page_zone": "spread" if spread else "front_page", "page_count": 2 if spread else 1,
                      "single_page_width_mm": fmt.trim_w_mm, "negative_space_contrast": self.contrast,
                      "photo_subject_boxes": self.subject_boxes,
                      "photo_driven_decisions": self.decisions, "morphology_params": self.p,
                      "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                      "style_blend": self.material.style_blend.model_dump(), "text_threads": {}, **extra})
        from .frame_fill import finalize_text_frames
        finalize_text_frames(scene, self.dna, self.material)
        scene.metadata["topology"] = topology_signature(scene)
        return scene


def _cover_lines(mag: _Mag, stories, x, y, w, h, *, align="left", color=None):
    """Stacked cover lines measured with the real fonts; equal gaps between groups."""
    from .content_engine import rewrite_source_bound_copy
    stories = [s for s in stories if s is not None]
    if not stories:
        return
    head_size = min(24.0, mag.dna.typography.scales.headline_s)
    groups = []
    for story in stories:
        body = story.body or ""
        if body and len(body.split()) > 16:
            body, _ = rewrite_source_bound_copy(story.body, role="body", target_words=16,
                                                locked_passages=getattr(story, "locked_passages", []))
        head_h = mag.ctx.need(story.headline, w, "headline", head_size) + 1
        body_h = mag.ctx.need(body, w, "body", 9.4) + 1 if body else 0.0
        groups.append((story, body, head_h, body_h))
    total = sum(g[2] + g[3] + 1.5 for g in groups)
    while total > h and head_size > 13:
        head_size *= .92
        groups = [(st, b, mag.ctx.need(st.headline, w, "headline", head_size) + 1, bh) for st, b, _, bh in groups]
        total = sum(g[2] + g[3] + 1.5 for g in groups)
    gap = max(3.0, (h - total) / max(1, len(groups) - 1)) if len(groups) > 1 else 0.0
    gap = min(gap, 24.0)
    yy = y
    for index, (story, body, head_h, body_h) in enumerate(groups):
        head = mag.ctx.text("headline", story, "headline", x, yy, w, head_h, head_size, color=color or mag.pal.primary)
        if head is not None:
            head.style.align, head.style.font_weight = align, "bold"
        yy += head_h + .5
        if body:
            element = mag.ctx.text("body", story, "body", x, yy, w, body_h, 9.4, value=body, color=color or mag.pal.text)
            if element is not None:
                element.style.align = "left" if align == "left" else align
            yy += body_h
        mag.used.append(story.id)
        if index < len(groups) - 1:
            mag.ctx.rule(x if align != "right" else x + w * .7, yy + gap / 2 - .3, w * .3, f"line-{story.id}")
        yy += gap + 1


def _portrait_cover(mag: _Mag) -> SceneGraph:
    s, p = mag.stories, mag.p
    lead, image = s[0], s[0].images[0]
    side = _side_of_lines(image)
    mag.decisions.append({"decision": "cover_lines_side", "side": side,
                          "reason": "przestrzeń negatywna po stronie przeciwnej do motywu / w kierunku spojrzenia"})
    photo = mag.photo(lead, image, -mag.bleed, -mag.bleed, mag.trim_w + 2 * mag.bleed, mag.trim_h + 2 * mag.bleed, bleed=True)
    photo.importance = .96
    stats = measure_region(image, photo, Frame(x=mag.left, y=mag.top, w=mag.width, h=float(p["masthead_mm"])))
    ink = "#ffffff" if (stats is None or stats["mean"] < .55) else mag.pal.primary
    mag.masthead(color=ink, over_photo=True)
    mag.decisions.append({"decision": "masthead_ink", "ink": ink,
                          "reason": f"zmierzona jasność tła {stats['mean']:.2f}" if stats else "brak pomiaru — biel"})
    col_w = mag.width * float(p["line_column_share"])
    box = mag.subject_boxes.get(photo.id)
    if box:
        free_mm = (box[0] - mag.left - 4) if side == "left" else (mag.right - box[2] - 4)
        col_w = max(40.0, min(col_w, free_mm))
    col_x = mag.left if side == "left" else mag.right - col_w
    head_h = mag.trim_h * float(p["headline_share"])
    head_y = mag.bottom - head_h
    plan = compose_display_headline(lead.headline, width_mm=col_w, height_mm=head_h,
                                    preferred_size_pt=min(64.0, mag.dna.typography.scales.headline_xl),
                                    minimum_size_pt=24.0, font_families=[mag.ctx.family("headline")], max_lines=4)
    if plan:
        used = len(plan.lines) * plan.font_size_pt * 1.06 * .352778 + 2
        head_y, head_h = mag.bottom - used, used
    mag.line_on_photo(lead, "headline", photo, image, col_x, head_y, col_w, head_h,
                      plan.font_size_pt if plan else min(44.0, mag.dna.typography.scales.headline_l),
                      minimum=22.0, bold=True, dominant=True)
    if lead.kicker:
        mag.line_on_photo(lead, "kicker", photo, image, col_x, head_y - 9, col_w, 7, 9.5, minimum=8.0)
    lines_top = mag.top + float(p["masthead_mm"]) + 8
    lines_h = head_y - 12 - lines_top
    for index, story in enumerate(s[1:4]):
        slot = lines_h / max(1, len(s[1:4]))
        mag.line_on_photo(story, "headline", photo, image, col_x, lines_top + index * slot, col_w, slot * .62,
                          min(20.0, mag.dna.typography.scales.headline_s * .8), minimum=11.0, bold=True)
        mag.used.append(story.id)
    return mag.finish({"cover_lines_side": side})


def _detail_still_life(mag: _Mag) -> SceneGraph:
    s, p = mag.stories, mag.p
    lead, image = s[0], s[0].images[0]
    mag.masthead(color=mag.pal.primary)
    y = mag.top + float(p["masthead_mm"]) + 6
    photo_w = mag.width * float(p["photo_share"])
    photo_h = photo_w / float(p["photo_aspect"])
    side = _side_of_lines(image)
    photo_x = mag.right - photo_w if side == "left" else mag.left
    photo = mag.photo(lead, image, photo_x, y, photo_w, photo_h)
    photo.importance = .96
    col_w = mag.width - photo_w - 8
    col_x = mag.left if side == "left" else mag.right - col_w
    _cover_lines(mag, s[1:4], col_x, y, col_w, photo_h, align="right" if side == "left" else "left")
    remaining = mag.bottom - (y + photo_h)
    hy = y + photo_h + max(float(p["line_gap_mm"]), (remaining - 62) / 2)
    if lead.kicker:
        kicker = mag.fit(lead, "kicker", mag.left, hy, mag.width, 7, 9.4, color=mag.pal.secondary)
        if kicker is not None:
            kicker.text_content = kicker.text_content.upper()
            kicker.style.align = "center"
        hy += 8
    head = mag.fit(lead, "headline", mag.left + mag.width * .08, hy, mag.width * .84, 34,
                   min(46.0, mag.dna.typography.scales.headline_l * 1.1), color=mag.pal.primary, minimum=24.0, dominant=True)
    if head is not None:
        head.style.align = "center"
    lead_text = lead.deck or lead.lead
    if lead_text:
        deck = mag.fit(lead, "deck" if lead.deck else "lead", mag.left + mag.width * .18, hy + 36, mag.width * .64, 16, 11.0,
                       color=mag.pal.text, words=24, minimum=9.0)
        if deck is not None:
            deck.style.align = "center"
    mag.decisions.append({"decision": "negative_space", "reason": "detal na tle papieru; świadoma pustka wokół zdjęcia"})
    return mag.finish({"cover_lines_side": side})


def _reportage_cover(mag: _Mag) -> SceneGraph:
    s, p = mag.stories, mag.p
    lead, image = s[0], s[0].images[0]
    mag.masthead(color=mag.pal.primary)
    y = mag.top + float(p["masthead_mm"]) + 4
    strip_h = float(p["strip_mm"])
    photo_h = (mag.bottom - y - strip_h - 6) * .78
    photo = mag.photo(lead, image, mag.left, y, mag.width, photo_h)
    photo.importance = .96
    hy = y + photo_h + 3
    if lead.kicker:
        k = mag.fit(lead, "kicker", mag.left, hy, mag.width * .5, 6.5, 9.0, color=mag.pal.secondary)
        if k is not None:
            k.text_content = k.text_content.upper()
        hy += 7.5
    head_h = mag.bottom - strip_h - 4 - hy
    mag.fit(lead, "headline", mag.left, hy, mag.width * .78, head_h,
            min(48.0, mag.dna.typography.scales.headline_l * 1.15), color=mag.pal.primary, minimum=22.0, dominant=True)
    sy = mag.bottom - strip_h
    mag.ctx.rule(mag.left, sy - 2, mag.width, "reportage-strip")
    rest = s[1:3]
    inset_story = next((x for x in rest if x.images), None)
    text_w = mag.width - (strip_h * 1.3 + 4 if inset_story else 0)
    _cover_lines(mag, rest, mag.left, sy, text_w, strip_h)
    if inset_story:
        mag.photo(inset_story, inset_story.images[0], mag.right - strip_h * 1.3, sy, strip_h * 1.3, strip_h)
    return mag.finish({})


def _typographic_cover(mag: _Mag) -> SceneGraph:
    s, p = mag.stories, mag.p
    lead = s[0]
    mag.masthead(color=mag.pal.primary)
    y = mag.top + float(p["masthead_mm"]) + 6
    type_h = (mag.bottom - y) * float(p["type_share"])
    head = mag.ctx.text if False else None
    plan = compose_display_headline(lead.headline, width_mm=mag.width, height_mm=type_h,
                                    preferred_size_pt=min(150.0, mag.dna.typography.scales.mega * 1.6),
                                    minimum_size_pt=40.0, font_families=[mag.ctx.family("headline")],
                                    case_options=("normal", "upper"), min_lines=2, max_lines=4)
    if plan:
        head = mag.ctx.text("headline", lead, "headline", mag.left, y, mag.width,
                            min(type_h, len(plan.lines) * plan.font_size_pt * 1.06 * .352778 + 2), plan.font_size_pt,
                            value=plan.text, color=mag.pal.primary, dominant=True)
        head.style.font_family, head.style.case = plan.font_family, plan.case
        if any(getattr(t, "id", None) == "extreme-scale" for t in (mag.dna.transgressions or [])):
            head.transgressions.append("extreme-scale")
    else:
        head = mag.fit(lead, "headline", mag.left, y, mag.width, type_h, 60.0, color=mag.pal.primary, dominant=True, minimum=30.0)
    mag.used.append(lead.id)
    cy = y + (head.frame.h if head else type_h) + 6
    image = (lead.images or [None])[0]
    remaining = mag.bottom - cy
    if image:
        pw = mag.width * float(p["photo_share"])
        mag.photo(lead, image, mag.right - pw, cy, pw, min(remaining, pw * 1.25))
        col_w = mag.width - pw - 8
    else:
        col_w = mag.width
    lead_text = lead.deck or lead.lead
    if lead_text:
        mag.fit(lead, "deck" if lead.deck else "lead", mag.left, cy, col_w, 22, 12.5, color=mag.pal.text, words=30, minimum=9.5)
        cy += 26
    _cover_lines(mag, s[1:4], mag.left, cy, col_w, mag.bottom - cy)
    return mag.finish({})


BUILDERS = {"portrait_cover": _portrait_cover, "detail_still_life": _detail_still_life,
            "reportage_cover": _reportage_cover, "typographic_cover": _typographic_cover}


def compose(dna, material, genes: dict, name: str) -> SceneGraph:
    return BUILDERS[name](_Mag(dna, material, genes, name))


def compose_opening_spread(dna, material, genes: dict) -> SceneGraph:
    """Opening spread: verso = leading photograph to the bleed, recto = title,
    standfirst and the start of the body in two columns."""
    mag = _Mag(dna, material, genes, "opening_spread")
    lead = mag.stories[0]
    image = (lead.images or [None])[0]
    w, h, b = mag.trim_w, mag.trim_h, mag.bleed
    if image:
        photo = mag.photo(lead, image, -b, -b, w + b, h + 2 * b, bleed=True)
        photo.importance = .96
    x0 = w + mag.left
    width = w - mag.left - (w - mag.right)
    y = mag.top + 12
    if lead.kicker:
        k = mag.fit(lead, "kicker", x0, y, width, 7, 9.6, color=mag.pal.secondary)
        if k is not None:
            k.text_content = k.text_content.upper()
        y += 10
    head = mag.fit(lead, "headline", x0, y, width, 70, min(54.0, dna.typography.scales.headline_xl), color=mag.pal.primary,
                   minimum=26.0, dominant=True)
    y += (head.frame.h if head else 70) + 4
    lead_text = lead.deck or lead.lead
    if lead_text:
        mag.fit(lead, "deck" if lead.deck else "lead", x0, y, width, 30, 13.0, color=mag.pal.text, words=48, minimum=10.0)
        y += 34
    mag.ctx.rule(x0, y, width * .25, "opening")
    y += 5
    if lead.body:
        from .content_engine import rewrite_source_bound_copy
        from .copyfit import estimate_text_capacity
        cols = int(mag.p["body_columns"]) if width > 120 else 1
        size, text = float(dna.typography.scales.body), lead.body
        height = mag.bottom - y
        def fits(value: str) -> bool:
            rep_ = estimate_text_capacity(value, width, height, cols, size, mag.ctx.leading("body", size),
                                          font_family=mag.ctx.family("body"), gutter_mm=mag.ctx.gutter)
            return rep_.estimated_lines <= rep_.capacity_lines
        target = len(text.split())
        while not fits(text) and target > 20:
            target = int(target * .85)
            text, info = rewrite_source_bound_copy(lead.body, role="body", target_words=target,
                                                   locked_passages=getattr(lead, "locked_passages", []))
            mag.ctx.fit.append({"action": "opening_spread_reduction", "story_ref": lead.id, "to_words": target,
                                "reason": "Ciąg dalszy tekstu na kolejnych stronach"})
        mag.ctx.text("body", lead, "body", x0, y, width, height, size, cols=cols, value=text, color=mag.pal.text)
    mag.used.append(lead.id)
    return mag.finish({"spread_role": "opening"}, spread=True)
