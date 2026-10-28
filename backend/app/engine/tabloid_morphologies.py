"""Generative cover morphologies for the popular (tabloid) grammar.

A morphology is a *topology* of the page: where the dominant photograph sits,
how the display headline enters it, how secondary stories attach and which
direction the eye travels.  It is not a template:

* every proportion comes from ``TitleDNA.cover_grammar["morphologies"]`` (with
  explicit editorial starting values for older saved DNA);
* emotion of the material (``page_mood.mood_form``) sets the entry angle,
  palette, case, effects, crop tightness and teaser length;
* the photo editor's observations (``StoryImageInput.photo_analysis``: gaze /
  motion direction, headline-safe zone, focal point, cutout feasibility) decide
  sides and placements so the geometry reacts to the photograph;
* the output is an ordinary scene graph checked by the same hard gate and
  rendered by the same SVG/HTML/PDF/IDML renderers.

The VLM never sets coordinates here; it only supplies observations upstream.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, Relation, SceneGraph
from .content_engine import rewrite_source_bound_copy
from .display_headline import compose_display_headline
from .page_mood import mood_form, mood_palette, resolve_page_mood

# Editorial starting values.  Title DNA overrides them per morphology.
DEFAULTS: dict[str, dict[str, Any]] = {
    "diagonal_hero_entry": {"skyline_mm": 30.0, "strip_mm": 60.0, "strip_shares": [.40, .27, .33],
                            "headline_max_mm": 70.0, "min_abs_angle": 2.5, "sticker_angle": 4.0},
    "dual_scale_collage": {"major_share": .64, "minor_height_share": .62, "overlap_mm": 14.0,
                           "hero_share": .56, "band_mm": 48.0, "strip_shares": [.56, .44],
                           "inset_border_mm": 1.6},
    "photo_dominant_strip": {"hero_share_of_body": .70, "skyline_mm": 30.0, "strip_mm": 60.0,
                             "strip_shares": [.31, .37, .32], "step_mm": [9.0, 3.0, 6.0],
                             "headline_max_share": .38},
    "directional_tension": {"photo_share": .58, "strip_mm": 58.0, "rail_teaser_mm": 62.0},
    "type_behind_subject": {"type_share": .34, "cover_share": .45, "strip_mm": 58.0, "photo_share": .62},
    "stacked_rail_cover": {"skyline_mm": 26.0, "masthead_mm": 40.0, "rail_share": .35, "stack_share": .50,
                           "stamp_mm": 30.0},
    "dense_mosaic": {"top_row_mm": 36.0, "plate_mm": 62.0, "hero_share": .66, "bottom_mm": 62.0, "stamp_mm": 36.0},
    "versus_split": {"photo_share": .50, "strip_mm": 55.0, "badge_mm": 24.0},
}
CATALOG = tuple(DEFAULTS)


def morphology_params(dna, name: str) -> dict[str, Any]:
    grammar = getattr(dna, "cover_grammar", None) or {}
    return {**DEFAULTS[name], **((grammar.get("morphologies") or {}).get(name) or {})}


def morphology_catalog(dna) -> list[str]:
    grammar = getattr(dna, "cover_grammar", None) or {}
    listed = grammar.get("morphology_catalog")
    return [name for name in (listed or CATALOG) if name in DEFAULTS]


# ---------------------------------------------------------------- photo data
def analysis(image) -> dict[str, Any]:
    return dict(getattr(image, "photo_analysis", None) or {})


def facing(image) -> Optional[str]:
    """Direction the subject looks or moves, from the viewer's perspective."""
    data = analysis(image)
    for key in ("motion_direction", "gaze_direction"):
        if data.get(key) in {"left", "right"}:
            return str(data[key])
    return None


def column_side(image) -> Optional[str]:
    """Side of the photograph where a headline column belongs.

    The subject should look/move *into* the copy; without a direction, the
    photo editor's lateral headline-safe zone is used.
    """
    direction = facing(image)
    if direction:
        return direction
    zone = analysis(image).get("headline_safe_zone")
    return zone if zone in {"left", "right"} else None


def safe_zone(image) -> Optional[str]:
    zone = analysis(image).get("headline_safe_zone")
    return zone if zone in {"top", "bottom"} else None


def has_real_cutout(dna, image) -> bool:
    if not (dna.photo_rules.allow_cutout and image is not None):
        return False
    if analysis(image).get("cutout_feasible") is False:
        return False
    return bool(image.alpha_mask_url or image.contour_polygon)


def _print_ok(dna, image, width_mm: float) -> bool:
    if not image or not image.width_px:
        return False
    return image.width_px >= width_mm * dna.photo_rules.min_dpi / 25.4 * .95


def feasible_morphologies(dna, material, stories: Optional[list] = None) -> dict[str, str]:
    """Return ``{name: reason}`` for morphologies this material can carry."""
    stories = stories or sorted(material.stories, key=lambda s: -s.importance)
    if len(stories) < 4:
        return {}
    lead_image = (stories[0].images or [None])[0]
    fmt = dna.format
    width = fmt.trim_w_mm - fmt.margin_left_mm - fmt.margin_right_mm
    if not _print_ok(dna, lead_image, width * .58):
        return {}
    form = mood_form(dna, resolve_page_mood(material).name)
    out: dict[str, str] = {}
    for name in morphology_catalog(dna):
        p = morphology_params(dna, name)
        if name == "diagonal_hero_entry":
            if abs(form.angle_deg) >= float(p["min_abs_angle"]) and _print_ok(dna, lead_image, width):
                out[name] = f"nastrój „{form.mood}” uzasadnia kąt {form.angle_deg:.1f}°"
        elif name == "dual_scale_collage":
            if stories[1].images:
                out[name] = "drugi materiał ma własne zdjęcie do kolażu"
        elif name == "photo_dominant_strip":
            if _print_ok(dna, lead_image, width):
                out[name] = "zdjęcie główne ma rozdzielczość na pełną szerokość"
        elif name == "directional_tension":
            if column_side(lead_image):
                out[name] = (f"fotoedytor wskazał kierunek: {facing(lead_image)}" if facing(lead_image)
                             else f"fotoedytor wskazał wolną strefę: {column_side(lead_image)}")
        elif name == "type_behind_subject":
            if has_real_cutout(dna, lead_image):
                out[name] = "zdjęcie ma prawdziwą maskę alfa"
        elif name == "stacked_rail_cover":
            if len(stories) >= 5:
                out[name] = "pięć tematów: pasek, szyna zajawek i tytuł-stos"
        elif name == "dense_mosaic":
            if len(stories) >= 5 and sum(1 for st in stories[:5] if st.images) >= 3:
                out[name] = "co najmniej trzy tematy ze zdjęciami do gęstej mozaiki"
        elif name == "versus_split":
            if len(stories) >= 4 and stories[0].images and stories[1].images:
                out[name] = "dwa tematy ze zdjęciami do układu zderzenia (versus)"
    return out


def topology_signature(scene: SceneGraph) -> str:
    """Coarse page topology: photos and headlines by story rank on a 3x4 grid.

    Two candidates with the same signature differ only cosmetically (type
    size, colour); different signatures mean a different reading structure.
    """
    w, h = float(scene.page.trim[0]), float(scene.page.trim[1])
    weight: dict[str, float] = {}
    for element in scene.elements:
        if element.story_ref and element.role in {"photo", "headline"}:
            weight[element.story_ref] = max(weight.get(element.story_ref, 0.0), float(element.importance))
    ranks = {ref: index for index, ref in enumerate(sorted(weight, key=lambda ref: (-weight[ref], ref)))}
    tokens = []
    for element in scene.elements:
        if element.role not in {"photo", "headline"} or not element.story_ref:
            continue
        f = element.frame
        col = min(2, int((f.x + f.w / 2) / w * 3))
        row = min(3, int((f.y + f.h / 2) / h * 4))
        span = "W" if f.w > w * .7 else "M" if f.w > w * .4 else "N"
        tilt = "/" if abs(f.rotation_deg or 0) >= 2 else ""
        tokens.append(f"{element.role[0]}{ranks[element.story_ref]}@{row}{col}{span}{tilt}")
    return "|".join(sorted(set(tokens)))


# ---------------------------------------------------------------- composer
class _Cover:
    def __init__(self, dna, material, genes: dict, stories: list, name: str):
        from .plan_composer import _Ctx
        self.dna, self.material, self.genes, self.stories, self.name = dna, material, genes, stories, name
        self.ctx = _Ctx(dna, material, genes)
        fmt = dna.format
        self.left, self.top = fmt.margin_left_mm, fmt.margin_top_mm
        self.right, self.bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
        self.width = self.right - self.left
        self.g = dna.cover_grammar or {}
        self.p = morphology_params(dna, name)
        self.mood = resolve_page_mood(material).name
        self.form = mood_form(dna, self.mood)
        self.pal = mood_palette(dna, self.mood)
        # Colour plan: paper modules with keylines are the default; strong and
        # deep planes are spent deliberately, the light accent at most once.
        self.pal["paper"] = dna.palette.background
        self.pal["ink_on_paper"] = dna.palette.text
        self.gap = max(2.0, min(3.0, dna.grid.gutter_mm * .55))
        self.decisions: list[dict[str, Any]] = []
        self.used: list[str] = []
        # Emotion scales how much of the title's tension budget this page
        # may spend; the hard gate still checks the full DNA budget.
        self.energy_budget = float(dna.page_energy_budget) * max(.45, min(1.0, self.form.transgression_scale + .1))
        self.energy_used = 0.0

    def spend(self, transgression: str) -> bool:
        from .transgressions import get_transgression_catalog
        cost = get_transgression_catalog()[transgression].cost
        if self.energy_used + cost > self.energy_budget + 1e-6:
            self.decisions.append({"decision": "transgression_skipped", "id": transgression,
                                   "reason": f"budżet napięcia {self.energy_budget:.2f} dla nastroju {self.mood}"})
            return False
        self.energy_used += cost
        return True

    # -- copy
    def fit(self, story, field, x, y, w, h, size, *, color=None, bg=None, minimum=7.8, words=None, dominant=False):
        from .plan_composer import _cover_copy_fits
        ctx = self.ctx
        source = str(getattr(story, field, "") or "")
        if not source or h < 3:
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
        return ctx.text(role, story, field, x, y, w, h, size, value=candidate, color=color, bg_color=bg, dominant=dominant)

    def plane(self, story, key, x, y, w, h, color, z=0):
        element = Element(id=f"{key}-{story.id if story else 'page'}-{len(self.ctx.elements)}", role="band", importance=.08,
                          content_ref=f"{story.id if story else 'page'}.{key}", frame=Frame(x=x, y=y, w=w, h=max(1.0, h)),
                          style=ElementStyle(bg_color=color), z=z, constraints=["decorative_background"],
                          story_ref=story.id if story else None)
        self.ctx.elements.append(element)
        return element

    # -- chrome
    def masthead(self, ear_story=None) -> float:
        from .plan_composer import PT
        ctx, dna, material = self.ctx, self.dna, self.material
        masthead_h = min(48.0, max(34.0, float(self.g.get("masthead_band_mm", 42))))
        logo_plan = compose_display_headline(
            material.masthead_title, width_mm=self.width - 4, height_mm=masthead_h - 2,
            preferred_size_pt=min(132.0, masthead_h / PT * .88), minimum_size_pt=18.0,
            font_families=[ctx.family("logo")], max_lines=1)
        logo = ctx.text("logo", None, "masthead", self.left, self.top, self.width, masthead_h,
                        logo_plan.font_size_pt if logo_plan else min(91.0, masthead_h / PT * .65),
                        value=material.masthead_title, color="#ffffff", bg_color=dna.palette.secondary)
        has_image_logo = bool(logo and getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref)
        if has_image_logo:
            logo.image_url, logo.content_ref, logo.style.bg_color = dna.logo_profile.asset_ref, "masthead.logo", None
        # Tabloid "ear": a real teaser beside the title instead of an empty
        # stretch of the masthead band.  Only with a measured text logo.
        if ear_story is not None and logo_plan and not has_image_logo:
            logo_w = max(logo_plan.line_widths_pt) * PT + 6
            ear_w = self.width - logo_w - 4
            if ear_w >= 58 and ear_story.headline:
                ear_x = self.right - ear_w - 2
                self.used.append(ear_story.id)
                self.plane(ear_story, "ear_field", ear_x, self.top + 2, ear_w, masthead_h - 4, self.pal["light"], z=3)
                ey = self.top + 3
                if ear_story.kicker:
                    kicker = self.fit(ear_story, "kicker", ear_x + 1.5, ey, min(ear_w - 3, 60.0), 6.0, 8.6,
                                      color="#ffffff", bg=self.pal["strong"], minimum=7.5)
                    if kicker is not None:
                        kicker.text_content, kicker.z = kicker.text_content.upper(), 4
                    ey += 7
                body_h = 8.0 if ear_story.body else 0.0
                head = self.fit(ear_story, "headline", ear_x + 1.5, ey, ear_w - 3, self.top + masthead_h - 3 - ey - body_h,
                                26.0, color=self.pal["ink_on_light"], minimum=14.0)
                if head is not None:
                    head.style.font_weight, head.z = "bold", 4
                    from .fonts import resolve_font
                    chosen = next((f for f in (self.g.get("poster_teaser_font_candidates") or [])
                                   if resolve_font(f, bold=True, text=head.text_content)), None)
                    if chosen:
                        head.style.font_family = chosen
                if ear_story.body:
                    body = self.fit(ear_story, "body", ear_x + 1.5, self.top + masthead_h - 2.5 - body_h, ear_w - 3, body_h,
                                    8.6, color=self.pal["ink_on_light"], words=9, minimum=7.6)
                    if body is not None:
                        body.z = 4
                self.decisions.append({"decision": "masthead_ear", "story_ref": ear_story.id,
                                       "reason": "ucho winiety zamiast pustego pola obok tytułu"})
        folio_y = self.top + masthead_h + 1
        ctx.text("folio", None, "issue", self.left, folio_y, self.width, 6.0, 8.5,
                 value=f"{material.issue_date}  ·  {material.issue_number}  ·  {material.section_name}")
        return folio_y + 8

    # -- display headline
    def display(self, story, x, y, w, h, *, color, bg=None, angle=0.0, max_lines=3, min_lines=1,
                preferred=None, minimum=26.0, align=None, flow=None, over_photo=False, dominant=True):
        ctx, form = self.ctx, self.form
        candidates = list(self.g.get("display_font_candidates") or [])
        families = (candidates + [ctx.family("headline")] if form.display_width == "condensed"
                    else [ctx.family("headline"), *candidates])
        options = tuple(self.g.get("display_case_options") or ["normal"])
        case_options = (("upper", "normal") if form.display_case == "upper" else ("normal",))
        case_options = tuple(c for c in case_options if c in options or c == "normal") or ("normal",)
        preferred = preferred or min(118.0, self.dna.typography.scales.headline_xl * 1.6)
        plan = compose_display_headline(story.headline, width_mm=w - 2, height_mm=h - 1,
                                        preferred_size_pt=preferred, minimum_size_pt=minimum,
                                        font_families=list(dict.fromkeys(families)), case_options=case_options,
                                        min_lines=min_lines, max_lines=max_lines)
        if plan:
            used_h = len(plan.lines) * plan.font_size_pt * 1.06 * 0.352778 + 2.0
            element = ctx.text("headline", story, "headline", x, y, w, h if bg else min(h, used_h), plan.font_size_pt,
                               value=plan.text, color=color, bg_color=bg, dominant=dominant, align=align)
            element.style.font_family, element.style.case = plan.font_family, plan.case
            ctx.fit.append({"action": "display_headline_composition", "story_ref": story.id, "lines": list(plan.lines),
                            "font": plan.font_family, "font_size_pt": plan.font_size_pt, "case": plan.case,
                            "morphology": self.name})
        else:
            element = self.fit(story, "headline", x, y, w, h, preferred, color=color, bg=bg, minimum=minimum, dominant=dominant)
            if element is None:
                return None
            if align:
                element.style.align = align
        element.style.font_weight = "bold"
        if form.outline:
            element.style.outline_color = self.g.get("display_outline_color") or self.pal["deep"]
            element.style.outline_width_pt = float(self.g.get("display_outline_width_pt", .5))
        if form.shadow:
            element.style.shadow_color = self.g.get("display_shadow_color") or "#111111"
            element.style.shadow_offset_x_pt = float(self.g.get("display_shadow_offset_x_pt", .8))
            element.style.shadow_offset_y_pt = float(self.g.get("display_shadow_offset_y_pt", .8))
        element.z = 6
        element.flow_group = flow or f"display-headline-{story.id}"
        if bg:
            element.constraints.append("allow_stack")
        if over_photo and self.spend("overlap-scrim"):
            element.transgressions.append("overlap-scrim")
        if (element.style.font_size_pt or 0) >= self.dna.typography.scales.headline_xl * 1.15 and self.spend("extreme-scale"):
            element.transgressions.append("extreme-scale")
        if abs(angle) >= .5 and self.spend("diagonal-break"):
            element.frame.rotation_deg = round(angle, 2)
            element.transgressions.append("diagonal-break")
        return element

    def sticker(self, story, x, y, w, angle, *, on_photo=True):
        if not story.kicker:
            return None
        sticker = self.fit(story, "kicker", x, y, w, 9.5, 15.0, color=self.pal["ink_on_strong"],
                           bg=self.pal["strong"], minimum=10.0)
        if sticker is None:
            return None
        sticker.text_content = sticker.text_content.upper()
        sticker.style.font_weight = "bold"
        if abs(angle) > .5 and self.spend("diagonal-break"):
            sticker.frame.rotation_deg = angle
        if on_photo:
            sticker.constraints.append("intentional_photo_badge")
        sticker.z = 7
        return sticker

    # -- photographs
    def photo(self, story, image, x, y, w, h, *, treatment=None, crop=None):
        element = self.ctx.photo(story, image, x, y, w, h, treatment or str(self.genes.get("photo_treatment", "crop")))
        crop = crop or self.form.crop
        zoom = {"tight": .84, "medium": .93, "wide": 1.0}.get(crop, 1.0)
        if element.treatment == "crop" and zoom < 1 and element.crop_box and image.width_px:
            l, t, r, b = element.crop_box
            fx, fy = (image.focal_point or [.5, .5])[:2]
            cw, ch = (r - l) * zoom, (b - t) * zoom
            nl = min(max(0.0, fx - cw / 2), 1.0 - cw)
            nt = min(max(0.0, fy - ch / 2), 1.0 - ch)
            nl, nt = max(l, min(nl, r - cw)), max(t, min(nt, b - ch))
            dpi = image.width_px * cw / (w / 25.4)
            if dpi >= self.dna.photo_rules.min_dpi:
                element.crop_box = [round(nl, 4), round(nt, 4), round(nl + cw, 4), round(nt + ch, 4)]
                self.ctx.fit.append({"action": "mood_crop", "story_ref": story.id, "crop": crop, "zoom": zoom})
        return element

    def focal_mm(self, element) -> tuple[float, float]:
        fx, fy = (element.focal_point or [.5, .5])[:2]
        crop = element.crop_box or [0, 0, 1, 1]
        u = (float(fx) - crop[0]) / max(1e-6, crop[2] - crop[0])
        v = (float(fy) - crop[1]) / max(1e-6, crop[3] - crop[1])
        return element.frame.x + element.frame.w * min(1, max(0, u)), element.frame.y + element.frame.h * min(1, max(0, v))

    # -- secondary module
    def cell(self, story, x, y, w, h, *, plane, idx, photo=True, photo_share=.44, photo_left=False,
             text_z=None, plane_rise=0.0):
        self.used.append(story.id)
        picture = (story.images or [None])[0] if photo else None
        picture_w = 0.0
        if picture:
            picture_w = w * photo_share
            if picture.width_px:
                picture_w = min(picture_w, picture.width_px * 25.4 / self.dna.photo_rules.min_dpi)
            picture_w = max(0.0, picture_w)
        copy_w = w - picture_w - (2 if picture_w else 0)
        copy_x = x + (picture_w + 2 if picture_w and photo_left else 0)
        ink = self.pal["ink_on_" + plane] if ("ink_on_" + plane) in self.pal else "#111111"
        if plane == "paper":
            # Paper module: a strong keyline on top instead of a colour plane.
            self.ctx.elements.append(Element(id=f"keyline-{story.id}-{len(self.ctx.elements)}", role="band", importance=.05,
                                             content_ref=f"{story.id}.keyline", frame=Frame(x=x, y=y - 1.2, w=w, h=1.0),
                                             style=ElementStyle(bg_color=self.pal["strong"]), z=1,
                                             constraints=["decorative_background"], story_ref=story.id))
            ink = self.pal["deep"]
        else:
            self.plane(story, "cell_field", copy_x, y - plane_rise, copy_w, h + plane_rise, self.pal[plane],
                       z=5 if plane_rise else 0)
        if picture_w >= 18:
            placed = picture
            if (picture.width_px and picture.height_px and picture.height_px / picture.width_px > 1.2
                    and picture_w / h > 1.2 and list(picture.focal_point or []) == [.5, .5]):
                # A centred crop of a portrait in a wide slot cuts the head off;
                # without a photo-editor focal point, anchor to the upper third.
                placed = picture.model_copy(update={"focal_point": [.5, float(self.g.get("poster_portrait_focal_y", .34))]})
                self.ctx.fit.append({"action": "portrait_focal_default", "story_ref": story.id})
            self.photo(story, placed, x if photo_left else x + w - picture_w, y, picture_w, h, crop="medium")
        cy = y + 1.5
        if story.kicker:
            kicker_bg = self.pal["strong"] if plane != "strong" else self.pal["deep"]
            kicker = self.fit(story, "kicker", copy_x, (y - plane_rise + 1) if plane_rise else cy, min(copy_w, 70.0), 6.5,
                              9.0, color="#ffffff", bg=kicker_bg, minimum=7.5)
            if kicker is not None:
                kicker.text_content = kicker.text_content.upper()
                kicker.shape = "slant"
                if plane_rise:
                    kicker.constraints.append("intentional_photo_badge")
                    kicker.z = 7
                else:
                    cy += 7.5
        available = h - (cy - y) - 2
        body_h = min(max(7.0, h * .30), available * .42) if story.body else 0.0
        head_h = available - body_h
        headline = self.fit(story, "headline", copy_x + 1.5, cy, copy_w - 3, head_h,
                            min(34.0, self.dna.typography.scales.headline_s * 1.2), color=ink, minimum=13.0)
        if headline is not None:
            from .fonts import resolve_font
            teaser_families = self.g.get("poster_teaser_font_candidates") or []
            chosen = next((f for f in teaser_families if resolve_font(f, bold=True, text=headline.text_content)), None)
            if chosen:
                headline.style.font_family = chosen
            headline.style.font_weight = "bold"
        if story.body:
            self.fit(story, "body", copy_x + 1.5, y + h - body_h - 1, copy_w - 3, body_h, 9.6,
                     color=self.pal["ink_on_paper"] if plane == "paper" else ink,
                     words=self.form.teaser_words, minimum=8.0)
        if text_z is not None:
            for element in self.ctx.elements:
                if element.story_ref == story.id and element.role in {"headline", "body", "kicker"}:
                    element.z = max(element.z, text_z)

    def lead_body(self, lead, x, y, w, h):
        return self.fit(lead, "body", x, y, w, h, 10.0, color=self.pal["ink_on_light"], bg=self.pal["light"],
                        minimum=9.0, words=24)

    # -- tabloid toolkit ---------------------------------------------------
    def masthead_block(self, x, y, w, h) -> Element:
        """Masthead as a compact block (not a full-width band)."""
        from .plan_composer import PT
        plan = compose_display_headline(self.material.masthead_title, width_mm=w - 4, height_mm=h - 3,
                                        preferred_size_pt=min(150.0, h / PT * .9), minimum_size_pt=20.0,
                                        font_families=[self.ctx.family("logo")], max_lines=2)
        logo = self.ctx.text("logo", None, "masthead", x, y, w, h, plan.font_size_pt if plan else 48.0,
                             value=plan.text if plan else self.material.masthead_title,
                             color="#ffffff", bg_color=self.dna.palette.secondary, align="center")
        logo.style.valign = "center"
        from .frame_fill import fit_display_fill
        logo.style.inset_mm = [2.0, 2.5, 2.0, 2.5]
        fit_display_fill(logo, min_pt=18.0, max_pt=220.0, max_lines=2, allow_single_words=True)
        if getattr(self.dna, "logo_profile", None) and self.dna.logo_profile.asset_ref:
            logo.image_url, logo.content_ref, logo.style.bg_color = self.dna.logo_profile.asset_ref, "masthead.logo", None
        return logo

    def two_tier_skyline(self, story, x, y, w, h):
        """Skyline promo: kicker tier + headline tier in contrasting planes."""
        self.used.append(story.id)
        top_h = h * .36
        if story.kicker:
            tier = self.fit(story, "kicker", x, y, w, top_h, 14.0, color=self.pal["ink_on_strong"],
                            bg=self.pal["strong"], minimum=8.0)
            if tier is not None:
                tier.text_content = tier.text_content.upper()
                tier.style.align = "center"
                tier.constraints.extend(["label", "fixed_width"])
        else:
            top_h = 0.0
        body_w = w * .30 if story.body else 0.0
        head = self.fit(story, "headline", x, y + top_h, w - body_w, h - top_h, 40.0, color=self.pal["deep"],
                        bg=self.pal["light"], minimum=14.0)
        if story.body:
            line = self.fit(story, "body", x + w - body_w, y + top_h, body_w, h - top_h, 9.0,
                            color=self.pal["ink_on_deep"], bg=self.pal["deep"], words=16, minimum=7.6)
        if head is not None:
            head.style.align = "center"
            head.constraints.append("allow_stack")
            from .fonts import resolve_font
            chosen = next((f for f in (self.g.get("display_font_candidates") or [])
                           if resolve_font(f, bold=True, text=head.text_content)), None)
            if chosen:
                head.style.font_family = chosen
            head.style.font_weight = "bold"
        return head

    def rail(self, stories, x, y, w, h):
        """Stacked mini-teasers: photo + condensed headline + one line, rules between."""
        stories = [s for s in stories if s is not None]
        if not stories:
            return
        slot = (h - 2.0 * (len(stories) - 1)) / len(stories)
        colours = [self.pal["strong"], self.pal["deep"]]
        for index, story in enumerate(stories):
            yy = y + index * (slot + 2.0)
            self.used.append(story.id)
            picture = (story.images or [None])[0]
            photo_h = slot * .46 if picture else 0.0
            if picture:
                placed = picture
                if (picture.width_px and picture.height_px and picture.height_px / picture.width_px > 1.2
                        and list(picture.focal_point or []) == [.5, .5]):
                    placed = picture.model_copy(update={"focal_point": [.5, float(self.g.get("poster_portrait_focal_y", .34))]})
                self.photo(story, placed, x, yy, w, photo_h, crop="medium")
            cy = yy + photo_h + (1.2 if picture else 0)
            if story.kicker:
                kick = self.fit(story, "kicker", x, cy - (3.2 if picture else 0), w * .8, 6.4, 8.8, color="#ffffff",
                                bg=colours[(index + 1) % 2], minimum=7.2)
                if kick is not None:
                    kick.text_content = kick.text_content.upper()
                    kick.shape = "slant"
                    if picture:
                        kick.constraints.append("intentional_photo_badge")
                        kick.z = 7
                cy += 7.0 - (3.2 if picture else 0)
            body_h = max(8.0, (yy + slot - cy) * .30) if story.body else 0.0
            reversed_item = index == 1
            head = self.fit(story, "headline", x, cy, w, yy + slot - cy - body_h - 1, 30.0,
                            color="#ffffff" if reversed_item else colours[index % 2],
                            bg=self.pal["deep"] if reversed_item else None, minimum=13.0)
            if head is not None:
                from .fonts import resolve_font
                chosen = next((f for f in (self.g.get("display_font_candidates") or [])
                               if resolve_font(f, bold=True, text=head.text_content)), None)
                if chosen:
                    head.style.font_family = chosen
                head.style.font_weight = "bold"
            if story.body:
                self.fit(story, "body", x, yy + slot - body_h, w, body_h, 8.8, color=self.dna.palette.text, words=14, minimum=7.6)
            if index < len(stories) - 1:
                self.ctx.rule(x, yy + slot + .7, w, f"rail-{story.id}")

    def stamp(self, story, x, y, d, *, shape="starburst", angle=-8.0):
        """Round or starburst stamp carrying a story's own kicker."""
        if not story.kicker:
            return None
        if len(story.kicker) > 14:
            # Long label: a rotated rectangular sticker with a keyline.
            sticker = self.sticker(story, x - d * 1.1, y + d * .25, d * 2.1, angle)
            if sticker is not None:
                sticker.style.bg_color = "#ffffff"
                sticker.style.color = self.pal["strong"]
                sticker.style.border_color = self.pal["strong"]
                sticker.style.border_width_mm = 1.0
                sticker.frame.h = d * .42
                sticker.constraints.extend(["label", "fixed_width"])
            return sticker
        stamp = self.fit(story, "kicker", x, y, d, d, 16.0, color=self.pal["deep"], bg=self.pal["light"], minimum=7.0)
        if stamp is None:
            return None
        stamp.shape = shape
        stamp.text_content = stamp.text_content.upper()
        stamp.style.align = "center"
        stamp.constraints.extend(["intentional_photo_badge", "label", "fixed_width"])
        stamp.z = 8
        if abs(angle) > .5 and self.spend("diagonal-break"):
            stamp.frame.rotation_deg = angle
        return stamp

    def headline_stack(self, story, x, y, w, h, colors, *, outline=None):
        """Per-line display stack over a photo: every line fills the measure."""
        from .frame_fill import stack_display_lines
        holder = self.ctx.text("headline", story, "headline", x, y, w, h, 60.0, value=story.headline,
                               color=colors[0], dominant=True)
        candidates = list(self.g.get("display_font_candidates") or [])
        if candidates:
            holder.style.font_family = candidates[0]
        holder.style.font_weight = "bold"
        holder.style.case = "upper" if self.form.display_case == "upper" else "normal"
        holder.flow_group = f"display-headline-{story.id}"
        holder.transgressions.append("overlap-scrim")
        self.spend("overlap-scrim")
        scene_like = type("S", (), {"elements": self.ctx.elements})()
        lines = stack_display_lines(scene_like, holder, colors=colors, gap_mm=.4)
        if lines:
            # The holder was the plate; over a photo there is no plate at all.
            self.ctx.elements.remove(holder)
            for line in lines:
                line.style.outline_color = outline or "#111111"
                line.style.outline_width_pt = 1.1
                line.style.shadow_color = "#000000"
                line.style.shadow_offset_x_pt = 1.0
                line.style.shadow_offset_y_pt = 1.0
                line.style.align = "right"
                line.z = 7
            lines[0].transgressions = ["overlap-scrim"]
            if self.spend("extreme-scale"):
                lines[0].transgressions.append("extreme-scale")
        return lines

    # -- assembly
    def finish(self, extra: dict[str, Any]) -> SceneGraph:
        from .plan_composer import PT
        ctx, dna, fmt, stories = self.ctx, self.dna, self.dna.format, self.stories
        used = [s for s in stories if s.id in set(self.used)]
        for story in stories:
            if story.id not in self.used:
                ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id,
                                "reason": "Temat pozostaje w wydaniu; poza miejscami tej morfologii pierwszej strony"})
        for story in used:
            for field in ("kicker", "deck", "lead"):
                if getattr(story, field, None) and not any(el.content_ref == f"{story.id}.{field}" for el in ctx.elements):
                    ctx.fit.append({"action": "cover_editorial_reduction", "story_ref": story.id, "field": field,
                                    "reason": "Pełny tekst pozostaje w materiale źródłowym"})
            members = [el.id for el in ctx.elements if el.story_ref == story.id]
            if members:
                ctx.relations.append(Relation(type="belongs_to_story", members=members, story=story.id))
        missing = [f"{s.id}.{field}" for s in used for field in ("headline", "body")
                   if getattr(s, field, None) and not any(el.content_ref == f"{s.id}.{field}" for el in ctx.elements)]
        scene = SceneGraph(
            page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm,
                          safe_margin_mm=min(self.left, self.top),
                          grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                                "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                          title_dna_ref=dna.id, page_zone="front_page"),
            elements=ctx.elements, relations=ctx.relations, reading_order=ctx.order,
            metadata={"generator": "plan_composer", "architecture": "popular_poster", "layout_mode": "photo-top",
                      "cover_morphology": self.name, "page_zone": "front_page", "page_count": 1,
                      "single_page_width_mm": fmt.trim_w_mm,
                      "mood_form": self.form.as_dict(), "mood_palette": self.pal,
                      "morphology_params": self.p, "photo_driven_decisions": self.decisions,
                      "style_readiness": {"status": "ready", "warnings": [],
                                          "photo_story_count": len({s.id for s in stories if s.images}),
                                          "story_count": len(stories)},
                      "missing_content_refs": missing, "fit_adjustments": ctx.fit,
                      "style_blend": self.material.style_blend.model_dump(), "text_threads": {}, **extra})
        from .frame_fill import finalize_text_frames
        # Line colours of a stacked display headline: data from the mood
        # palette (accent line + readable ink), never a random sequence.
        scene.metadata.setdefault("display_line_colors", [self.pal["light"], self.pal["ink_on_strong"]]
                                  if self.form.mood not in {"solemn", "analytical", "practical"}
                                  else [self.pal["ink_on_strong"]])
        finalize_text_frames(scene, self.dna, self.material)
        scene.metadata["topology"] = topology_signature(scene)
        return scene

    def strip(self, stories, y, h, shares, planes, *, photo_flags=None, rises=None, text_z=None):
        gap = self.gap
        stories = [s for s in stories if s is not None]
        if not stories:
            return
        shares = list(shares[:len(stories)])
        total = sum(shares) or 1.0
        avail = self.width - gap * (len(stories) - 1)
        x = self.left
        for index, story in enumerate(stories):
            w = avail * shares[index] / total if index < len(stories) - 1 else self.right - x
            self.cell(story, x, y, w, h, plane=planes[index % len(planes)], idx=index + 2,
                      photo=(photo_flags[index] if photo_flags else True), photo_left=index % 2 == 1,
                      plane_rise=(rises[index] if rises else 0.0), text_z=text_z)
            x += w + gap


def _zone_for_headline(cover: _Cover, hero, preferred: str, band_top: float, band_bottom: float,
                       other_top: float, other_bottom: float) -> str:
    """Keep the face/subject out of the headline: flip the zone when needed."""
    _, fy = cover.focal_mm(hero)
    if preferred == "bottom" and band_top - 4 <= fy <= band_bottom + 4:
        cover.decisions.append({"decision": "headline_zone_flipped", "from": "bottom", "reason": "punkt ogniskowy w strefie tytułu"})
        return "top"
    if preferred == "top" and other_top - 4 <= fy <= other_bottom + 4:
        cover.decisions.append({"decision": "headline_zone_flipped", "from": "top", "reason": "punkt ogniskowy w strefie tytułu"})
        return "bottom"
    return preferred


# ------------------------------------------------------------- morphologies
def _diagonal_hero_entry(cover: _Cover) -> SceneGraph:
    s, p, form, pal = cover.stories, cover.p, cover.form, cover.pal
    lead, image = s[0], s[0].images[0]
    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    sky_h = float(p["skyline_mm"])
    cover.cell(s[1], cover.left, y, cover.width, sky_h, plane="light", idx=0, photo_share=.34)
    hero_y = y + sky_h + cover.gap
    strip_h = float(p["strip_mm"])
    body_h = 9.0 if lead.body else 0.0
    hero_h = cover.bottom - hero_y - strip_h - cover.gap - (body_h + cover.gap if body_h else 0)
    hero = cover.photo(lead, image, cover.left, hero_y, cover.width, hero_h)
    hero.importance = .96
    cover.used.append(lead.id)
    angle = form.angle_deg if abs(form.angle_deg) >= float(p["min_abs_angle"]) else -float(p["min_abs_angle"])
    rad = math.radians(abs(angle))
    band_h = min(float(p["headline_max_mm"]), hero_h * .34)
    band_w = (cover.width - 6 - band_h * math.sin(rad)) / math.cos(rad)
    aabb_h = band_w * math.sin(rad) + band_h * math.cos(rad)
    preferred = safe_zone(image) or "bottom"
    zone = _zone_for_headline(cover, hero, preferred, hero_y + hero_h - aabb_h - 3, hero_y + hero_h - 3,
                              hero_y + 3, hero_y + aabb_h + 3)
    cy = (hero_y + hero_h - aabb_h / 2 - 3) if zone == "bottom" else (hero_y + aabb_h / 2 + 3)
    cover.display(lead, cover.left + (cover.width - band_w) / 2, cy - band_h / 2, band_w, band_h,
                  color=pal["light"] if pal["strong"] != pal["light"] else "#ffffff", bg=pal["strong"], angle=angle,
                  max_lines=3, minimum=28.0, over_photo=True)
    cover.decisions.append({"decision": "headline_zone", "zone": zone,
                            "source": "fotoedytor" if safe_zone(image) else "domyślnie", "angle_deg": angle})
    if form.sticker and lead.kicker:
        sticker_y = (cy - aabb_h / 2 - 13) if zone == "bottom" else (cy + aabb_h / 2 + 4)
        sticker_y = max(hero_y + 3, min(hero_y + hero_h - 12, sticker_y))
        cover.sticker(lead, cover.left + 6, sticker_y, min(72.0, cover.width * .3), float(p["sticker_angle"]))
    after = hero_y + hero_h + cover.gap
    if body_h:
        cover.lead_body(lead, cover.left, after, cover.width, body_h)
        after += body_h + cover.gap
    rest = [story for story in s[2:5] if story.id not in cover.used]
    shares = p["strip_shares"] if len(rest) >= 3 else [.62, .38]
    cover.strip(rest, after, cover.bottom - after, shares, ["paper", "deep", "paper"],
                photo_flags=[True, False, True] if len(rest) >= 3 else [True, True])
    return cover.finish({"entry_angle_deg": angle})


def _dual_scale_collage(cover: _Cover) -> SceneGraph:
    s, p, pal = cover.stories, cover.p, cover.pal
    lead, image = s[0], s[0].images[0]
    second, minor_image = s[1], s[1].images[0]
    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    body_area = cover.bottom - y
    hero_h = body_area * float(p["hero_share"])
    major_w = cover.width * float(p["major_share"])
    fx = float((image.focal_point or [.5, .5])[0])
    looks = facing(image)
    if fx > .58:
        minor_side = "left"
    elif fx < .42:
        minor_side = "right"
    else:
        minor_side = looks or "right"  # subject looks toward the second story
    cover.decisions.append({"decision": "inset_side", "side": minor_side,
                            "reason": "chroni punkt ogniskowy" if abs(fx - .5) > .08 else
                            ("kierunek spojrzenia/ruchu" if looks else "domyślnie")})
    hero_x = cover.left if minor_side == "right" else cover.right - major_w
    hero = cover.photo(lead, image, hero_x, y, major_w, hero_h)
    hero.importance = .96
    cover.used.append(lead.id)
    col_w = cover.width - major_w - cover.gap
    col_x = cover.right - col_w if minor_side == "right" else cover.left
    overlap = float(p["overlap_mm"])
    border = float(p["inset_border_mm"])
    inset_w = col_w + overlap - border
    inset_h = hero_h * float(p["minor_height_share"])
    inset_x = col_x - overlap + border if minor_side == "right" else col_x
    # A white mount separates the two scales; it is a scene object (editable
    # in IDML), not a stroke baked into the picture.
    mount_x = inset_x - border
    mount_w = min(inset_w + 2 * border, cover.right - mount_x) if minor_side == "right" else inset_w + border
    if minor_side == "left":
        mount_x = inset_x
    cover.plane(second, "inset_mount", mount_x, y, mount_w, inset_h + border, "#ffffff", z=5)
    inset = cover.photo(second, minor_image, inset_x, y, inset_w, inset_h, crop="tight")
    inset.z = 6
    inset.constraints.append("intentional_photo_inset")
    cover.used.append(second.id)
    plate_y = y + inset_h + border + cover.gap
    plate_h = y + hero_h - plate_y
    cover.plane(second, "minor_plate", col_x, plate_y, col_w, plate_h, pal["deep"])
    if second.kicker:
        kicker = cover.fit(second, "kicker", col_x, plate_y + 1, col_w, 6.5, 9.0, color="#ffffff", bg=pal["strong"], minimum=7.5)
        if kicker is not None:
            kicker.text_content = kicker.text_content.upper()
    head_top = plate_y + (8.5 if second.kicker else 2)
    body_h = max(8.0, plate_h * .28) if second.body else 0
    headline = cover.fit(second, "headline", col_x + 1.5, head_top, col_w - 3, plate_h - (head_top - plate_y) - body_h - 1,
                         min(34.0, cover.dna.typography.scales.headline_s * 1.25), color=pal["ink_on_deep"], minimum=13.0)
    if headline is not None:
        from .fonts import resolve_font
        chosen = next((f for f in (cover.g.get("poster_teaser_font_candidates") or [])
                       if resolve_font(f, bold=True, text=headline.text_content)), None)
        if chosen:
            headline.style.font_family = chosen
        headline.style.font_weight = "bold"
    if second.body:
        cover.fit(second, "body", col_x + 1.5, plate_y + plate_h - body_h - 1, col_w - 3, body_h, 9.6,
                  color=pal["ink_on_deep"], words=cover.form.teaser_words, minimum=8.0)
    band_y = y + hero_h + cover.gap
    band_h = float(p["band_mm"])
    cover.display(lead, cover.left, band_y, cover.width, band_h, color=pal["ink_on_strong"] if cover.form.mood in {"solemn", "analytical", "practical"} else pal["light"],
                  bg=pal["strong"], angle=0.0, max_lines=2,
                  min_lines=2 if len(lead.headline.split()) >= 4 else 1, minimum=28.0)
    if cover.form.sticker and lead.kicker:
        sticker_x = hero_x + (6 if minor_side == "right" else major_w - 6 - min(70.0, major_w * .4))
        cover.sticker(lead, sticker_x, y + 6, min(70.0, major_w * .4), -3.0)
    after = band_y + band_h + cover.gap
    if lead.body:
        cover.lead_body(lead, cover.left, after, cover.width, 9.0)
        after += 9.0 + cover.gap
    cover.strip(s[2:4], after, cover.bottom - after, p["strip_shares"], ["paper", "deep"])
    return cover.finish({"inset_side": minor_side})


def _photo_dominant_strip(cover: _Cover) -> SceneGraph:
    from .fonts import resolve_font
    from .shaper import width_pt
    from .plan_composer import PT
    s, p, pal, form = cover.stories, cover.p, cover.pal, cover.form
    lead, image = s[0], s[0].images[0]
    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    sky_h = float(p["skyline_mm"])
    # Skyline: the lead's strap (source body, shortened) beside a text-only
    # second story.  The photograph below stays free of extra copy.
    strap_w = cover.width * .38 if lead.body else 0.0
    if lead.body:
        cover.plane(lead, "strap_field", cover.left, y, strap_w, sky_h, pal["strong"])
        strap = cover.fit(lead, "body", cover.left + 2, y + 2, strap_w - 4, sky_h - 4, 15.0,
                          color=pal["ink_on_strong"], words=12, minimum=10.0)
        if strap is not None:
            strap.style.font_weight = "bold"  # reads as the lead's strap, not as body copy
            strap.style.align = "left"
    cover.cell(s[1], cover.left + strap_w + (cover.gap if strap_w else 0), y,
               cover.width - strap_w - (cover.gap if strap_w else 0), sky_h, plane="deep", idx=0, photo=False)
    hero_y = y + sky_h + cover.gap
    strip_h = float(p["strip_mm"])
    hero_h = cover.bottom - hero_y - strip_h - cover.gap
    hero = cover.photo(lead, image, cover.left, hero_y, cover.width, hero_h)
    hero.importance = .96
    cover.used.append(lead.id)
    steps = [float(v) for v in p["step_mm"]]
    _, fy = cover.focal_mm(hero)
    if fy > hero_y + hero_h - max(steps) - 6:
        steps = [0.0 for _ in steps]
        cover.decisions.append({"decision": "strip_steps_disabled", "reason": "motyw przy dolnej krawędzi zdjęcia"})
    head_h = hero_h * float(p["headline_max_share"])
    bottom_limit = hero_y + hero_h - max(steps) - 4
    preferred = safe_zone(image) or "bottom"
    zone = _zone_for_headline(cover, hero, preferred, bottom_limit - head_h, bottom_limit, hero_y + 4, hero_y + 4 + head_h)
    head_y = (bottom_limit - head_h) if zone == "bottom" else hero_y + 4
    cover.decisions.append({"decision": "headline_zone", "zone": zone, "source": "fotoedytor" if safe_zone(image) else "domyślnie"})
    candidates = list(cover.g.get("display_font_candidates") or [])
    families = candidates + [cover.ctx.family("headline")] if form.display_width == "condensed" else [cover.ctx.family("headline"), *candidates]
    plan = compose_display_headline(lead.headline, width_mm=cover.width - 12, height_mm=head_h - 1,
                                    preferred_size_pt=min(120.0, cover.dna.typography.scales.headline_xl * 1.6),
                                    minimum_size_pt=28.0, font_families=list(dict.fromkeys(families)),
                                    case_options=("upper", "normal") if form.display_case == "upper" else ("normal",),
                                    max_lines=3)
    overlay_ink = "#ffffff" if form.mood in {"solemn", "human", "analytical", "practical"} else pal["light"]
    if plan:
        font_path = resolve_font(plan.font_family, bold=True, text=plan.text)
        line_h = (head_h - 1) / len(plan.lines)
        for index, line in enumerate(plan.lines):
            measure = width_pt(line, plan.font_size_pt, font_path) if font_path else plan.line_widths_pt[index]
            size = min(plan.font_size_pt * 1.25, line_h / PT / 1.06,
                       plan.font_size_pt * (cover.width - 14) / PT / max(1.0, measure) * .82)
            element = cover.ctx.text("headline", lead, "headline", cover.left + 5, head_y + index * line_h,
                                     cover.width - 10, line_h, max(28.0, round(size, 1)), value=line,
                                     color=overlay_ink, dominant=True)
            element.style.font_family, element.style.case = plan.font_family, plan.case
            element.style.font_weight = "bold"
            element.style.outline_color = pal["deep"]
            element.style.outline_width_pt = 1.0
            element.style.shadow_color = "#111111"
            element.style.shadow_offset_x_pt = 1.2
            element.style.shadow_offset_y_pt = 1.2
            element.z = 6
            element.flow_group = f"display-headline-{lead.id}"
            if index == 0:
                element.transgressions.append("overlap-scrim")
                cover.spend("overlap-scrim")
                if cover.spend("extreme-scale"):
                    element.transgressions.append("extreme-scale")
        cover.ctx.fit.append({"action": "display_headline_composition", "story_ref": lead.id, "lines": list(plan.lines),
                              "font": plan.font_family, "case": plan.case, "treatment": "photo_overlay",
                              "morphology": cover.name})
    else:
        cover.display(lead, cover.left + 4, head_y, cover.width - 8, head_h, color=overlay_ink, max_lines=3, over_photo=True)

    if form.sticker and lead.kicker:
        sy = hero_y + 5 if zone == "bottom" else bottom_limit - 14
        cover.sticker(lead, cover.right - min(74.0, cover.width * .3) - 5, sy, min(74.0, cover.width * .3), -4.0)
    strip_y = hero_y + hero_h + cover.gap
    rest = [story for story in s[2:5] if story.id not in cover.used]
    three = len(rest) >= 3
    cover.strip(rest, strip_y, cover.bottom - strip_y, p["strip_shares"] if three else [.58, .42],
                ["deep", "strong", "deep"], photo_flags=[True, False, True] if three else [True, True],
                rises=[v + cover.gap for v in (steps if three else [steps[0], steps[-1]])] if any(steps) else None,
                text_z=7)
    return cover.finish({"headline_zone": zone, "strip_steps_mm": steps})


def _directional_tension(cover: _Cover) -> SceneGraph:
    s, p, pal, form = cover.stories, cover.p, cover.pal, cover.form
    lead, image = s[0], s[0].images[0]
    direction = column_side(image) or "right"
    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    strip_h = float(p["strip_mm"])
    hero_h = cover.bottom - y - strip_h - cover.gap
    photo_w = cover.width * float(p["photo_share"])
    col_w = cover.width - photo_w - cover.gap
    # The subject looks/moves INTO the headline column.
    photo_x = cover.right - photo_w if direction == "left" else cover.left
    col_x = cover.left if direction == "left" else cover.right - col_w
    align = "right" if direction == "left" else "left"
    cover.decisions.append({"decision": "photo_side", "photo": "right" if direction == "left" else "left",
                            "reason": (f"główna postać patrzy/porusza się w stronę: {direction}" if facing(image)
                                       else f"wolna strefa zdjęcia po stronie: {direction}")})
    hero = cover.photo(lead, image, photo_x, y, photo_w, hero_h)
    hero.importance = .96
    cover.used.append(lead.id)
    cover.plane(lead, "column_field", col_x, y, col_w, hero_h, pal["light"])
    cy = y + 3
    if lead.kicker:
        kicker = cover.fit(lead, "kicker", col_x + 2, cy, col_w - 4, 8, 12.0, color=pal["ink_on_strong"], bg=pal["strong"], minimum=9.0)
        if kicker is not None:
            kicker.text_content = kicker.text_content.upper()
            kicker.style.align = align
        cy += 10
    teaser_h = float(p["rail_teaser_mm"])
    head_h = (hero_h - teaser_h - (cy - y)) * .66
    head = cover.display(lead, col_x + 2, cy, col_w - 4, head_h, color=pal["strong"] if form.mood not in {"solemn"} else pal["deep"],
                         max_lines=5, min_lines=2, minimum=26.0, align=align)
    cy += (head.frame.h if head is not None else head_h) + 3
    copy_h = y + hero_h - teaser_h - cover.gap - cy
    if lead.body and copy_h > 10:
        body = cover.fit(lead, "body", col_x + 2, cy, col_w - 4, copy_h, 11.5, color=pal["ink_on_light"],
                         minimum=9.5)
        if body is not None:
            body.style.align = align
    cover.cell(s[1], col_x, y + hero_h - teaser_h, col_w, teaser_h, plane="deep", idx=1, photo_share=.42,
               photo_left=direction == "right")
    after = y + hero_h + cover.gap
    cover.strip(s[2:4], after, cover.bottom - after, [.5, .5], ["paper", "deep"])
    return cover.finish({"direction": direction})


def _type_behind_subject(cover: _Cover) -> SceneGraph:
    s, p, pal, form = cover.stories, cover.p, cover.pal, cover.form
    lead, image = s[0], s[0].images[0]
    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    strip_h = float(p["strip_mm"])
    hero_h = cover.bottom - y - strip_h - cover.gap - (9.0 + cover.gap if lead.body else 0)
    cover.plane(lead, "type_field", cover.left, y, cover.width, hero_h, pal["light"])
    type_h = hero_h * float(p["type_share"])
    headline = cover.display(lead, cover.left + 2, y + 2, cover.width - 4, type_h,
                             color=pal["strong"] if form.mood != "solemn" else pal["deep"], max_lines=2,
                             preferred=min(150.0, cover.dna.typography.scales.headline_xl * 2.0), minimum=40.0)
    if headline is not None:
        headline.z = 3
    photo_w = cover.width * float(p["photo_share"])
    fx = float((image.focal_point or [.5, .5])[0])
    photo_x = cover.left + (cover.width - photo_w) * (0.0 if fx < .45 else 1.0 if fx > .55 else .5)
    photo_y = y + 2 + type_h * (1 - float(p["cover_share"]))
    hero = cover.photo(lead, image, photo_x, photo_y, photo_w, y + hero_h - photo_y, treatment="cutout", crop="wide")
    hero.importance = .96
    hero.z = 5
    cover.used.append(lead.id)
    rail_w = cover.width - photo_w - cover.gap
    if rail_w >= 50:
        rail_x = cover.left if photo_x > cover.left + 1 else cover.right - rail_w
        cover.cell(s[1], rail_x, y + type_h + 6, rail_w, hero_h - type_h - 8, plane="deep", idx=1, photo=False)
        rest = s[2:4]
    else:
        rest = s[1:4]
    after = y + hero_h + cover.gap
    if lead.body:
        cover.lead_body(lead, cover.left, after, cover.width, 9.0)
        after += 9.0 + cover.gap
    cover.strip(rest, after, cover.bottom - after, [.36, .32, .32][:len(rest)], ["strong", "deep", "light"])
    return cover.finish({"type_cover_share": float(p["cover_share"])})


def _stacked_rail_cover(cover: _Cover) -> SceneGraph:
    s, p, pal, form = cover.stories, cover.p, cover.pal, cover.form
    lead, image = s[0], s[0].images[0]
    gap = cover.gap
    sky_h = float(p["skyline_mm"])
    cover.two_tier_skyline(s[3], cover.left, cover.top, cover.width, sky_h)
    y = cover.top + sky_h + gap
    rail_w = cover.width * float(p["rail_share"])
    mast_h = float(p["masthead_mm"])
    cover.masthead_block(cover.left, y, rail_w, mast_h)
    hero_x = cover.left + rail_w + gap
    hero_w = cover.right - hero_x
    hero_h = cover.bottom - y
    cutout = has_real_cutout(cover.dna, image)
    hero = cover.photo(lead, image, hero_x, y, hero_w, hero_h, treatment="cutout" if cutout else "crop")
    hero.importance = .96
    cover.used.append(lead.id)
    if hero.treatment == "cutout":
        cover.plane(lead, "hero_field", hero_x, y, hero_w, hero_h, pal["light"])
    cover.ctx.text("folio", None, "issue", cover.left, y + mast_h + 1, rail_w, 5.0, 7.5,
                   value=f"{cover.material.issue_date}  ·  {cover.material.issue_number}")
    rail_y = y + mast_h + 7.5
    cover.rail([s[1], s[2], s[4] if len(s) > 4 else None], cover.left, rail_y, rail_w, cover.bottom - rail_y)
    # The stack may cover clothing or background, never the face: the face
    # band is the focal point ± 13 % of the photo height.  The stack takes
    # the larger free part (photo editor's quiet zone first).
    _, fy = cover.focal_mm(hero)
    face_top, face_bottom = fy - hero_h * .13, fy + hero_h * .13
    free_top = max(0.0, face_top - y - 6)
    free_bottom = max(0.0, cover.bottom - face_bottom - 6)
    preferred = safe_zone(image) or "bottom"
    if preferred == "top" and free_top >= hero_h * .30:
        zone = "top"
    elif free_bottom >= hero_h * .30:
        zone = "bottom"
    else:
        zone = "top" if free_top > free_bottom else "bottom"
    stack_h = min(hero_h * float(p["stack_share"]), free_top if zone == "top" else free_bottom)
    stack_y = y + 4 if zone == "top" else cover.bottom - stack_h - 3
    cover.decisions.append({"decision": "headline_zone", "zone": zone,
                            "reason": "strefa bez twarzy wyznaczona z punktu ogniskowego fotoedytora"})
    colors = ([pal["ink_on_strong"], pal["strong"], "#ffffff"] if form.mood not in {"solemn", "analytical", "practical"}
              else ["#ffffff"])
    cover.headline_stack(lead, hero_x + 4, stack_y, hero_w - 8, stack_h, colors)
    cover.decisions.append({"decision": "headline_stack", "zone": zone, "lines_colors": colors})
    if lead.kicker:
        d = float(p["stamp_mm"])
        sy = stack_y - d * .75 if zone == "bottom" else stack_y + stack_h - d * .2
        cover.stamp(lead, hero_x + hero_w - d - 4, max(y + 2, sy), d, shape="starburst" if form.sticker else "circle")
    if lead.body:
        # The lead's strap on a plate in the photo's upper quiet area; it
        # carries the story and closes the empty sky above the subject.
        strap_h = min(30.0, max(18.0, (face_top - y) * .55)) if zone == "bottom" else 20.0
        strap_y = y + 4 if zone == "bottom" else cover.bottom - strap_h - 4
        strap = cover.fit(lead, "body", hero_x + hero_w * .30, strap_y, hero_w * .70 - 4, strap_h, 14.0,
                          color=pal["light"] if form.mood not in {"solemn"} else "#ffffff", bg=pal["deep"], words=22, minimum=9.0)
        if strap is not None:
            strap.style.font_weight = "bold"
            strap.role = "deck"
            strap.constraints.append("intentional_photo_badge")
            strap.z = 7
    return cover.finish({"headline_zone": zone})


def _dense_mosaic(cover: _Cover) -> SceneGraph:
    """Dense popular front: many modules, reversed plates, keylines, a round
    inset and a starburst — every device carries real story content."""
    s, p, pal, form = cover.stories, cover.p, cover.pal, cover.form
    lead, image = s[0], s[0].images[0]
    g, L, W = cover.gap, cover.left, cover.width
    top_h = float(p["top_row_mm"])
    mast_w = W * .30
    cover.masthead_block(L, cover.top, mast_w, top_h)
    sky_w = W * .40 - g
    cover.two_tier_skyline(s[3], L + mast_w + g, cover.top, sky_w, top_h)
    promo_x = L + mast_w + g + sky_w + g
    cover.cell(s[4], promo_x, cover.top, cover.right - promo_x, top_h, plane="strong", idx=4, photo_share=.30)
    y = cover.top + top_h + 1
    cover.ctx.text("folio", None, "issue", L, y, W, 5.0, 7.5,
                   value=f"{cover.material.issue_date}  ·  {cover.material.issue_number}  ·  {cover.material.section_name}")
    y += 6.5
    plate_h = float(p["plate_mm"])
    plate = cover.display(lead, L, y, W, plate_h, color=pal["ink_on_strong"], bg=pal["strong"], max_lines=2, minimum=28.0)
    if plate is not None:
        plate.constraints.append("force_stack")
    cover.used.append(lead.id)
    y += plate_h + g
    bottom_h = float(p["bottom_mm"])
    hero_h = cover.bottom - y - bottom_h - g
    hero_w = W * float(p["hero_share"])
    hero = cover.photo(lead, image, L, y, hero_w, hero_h)
    hero.importance = .96
    # Right column: reversed box with a round photo inset.
    col_x, col_w = L + hero_w + g, W - hero_w - g
    second = s[1]
    cover.used.append(second.id)
    cover.plane(second, "box_field", col_x, y, col_w, hero_h, pal["deep"])
    circle_d = min(col_w - 12, hero_h * .42)
    if second.images:
        circle = cover.photo(second, second.images[0], col_x + (col_w - circle_d) / 2, y + 5, circle_d, circle_d, crop="tight")
        circle.shape = "circle"
        circle.z = 5
    cy = y + (circle_d + 9 if second.images else 4)
    if second.kicker:
        kick = cover.fit(second, "kicker", col_x + 4, cy, col_w - 8, 6.5, 9.0, color=pal["ink_on_strong"], bg=pal["strong"], minimum=7.5)
        if kick is not None:
            kick.text_content = kick.text_content.upper()
            kick.style.align = "center"
        cy += 8
    body_h = max(14.0, (y + hero_h - cy) * .42) if second.body else 0
    head = cover.fit(second, "headline", col_x + 4, cy, col_w - 8, y + hero_h - cy - body_h - 2, 30.0,
                     color=pal["light"], minimum=13.0)
    if head is not None:
        head.style.align = "center"
        head.style.font_weight = "bold"
        from .fonts import resolve_font
        chosen = next((f for f in (cover.g.get("poster_teaser_font_candidates") or [])
                       if resolve_font(f, bold=True, text=head.text_content)), None)
        if chosen:
            head.style.font_family = chosen
    if second.body:
        cover.fit(second, "body", col_x + 4, y + hero_h - body_h - 3, col_w - 8, body_h, 9.4, color="#ffffff", words=30, minimum=8.0)
    # Starburst stamp biting into the hero corner.
    if lead.kicker:
        d = float(p["stamp_mm"])
        cover.stamp(lead, L + hero_w - d - 4, y + 4, d, shape="starburst" if len(lead.kicker) <= 14 else "rect", angle=-10)
    # Bottom row: keyline box (photo + copy) and the lead's copy column.
    by = cover.bottom - bottom_h
    third = s[2]
    box_w = W * .58
    cover.used.append(third.id)
    frame = cover.plane(third, "keyline_box", L, by, box_w, bottom_h, "#ffffff")
    frame.style.border_color, frame.style.border_width_mm = pal["strong"], .9
    cover.cell(third, L + 2.5, by + 2.5, box_w - 5, bottom_h - 5, plane="light", idx=2, photo_share=.40, photo_left=True)
    if lead.body:
        lx = L + box_w + g
        cover.ctx.rule(lx, by, W - box_w - g, "lead-copy")
        cover.fit(lead, "body", lx, by + 2.5, W - box_w - g, bottom_h - 2.5, 9.6, color=cover.dna.palette.text, minimum=8.0)
    return cover.finish({})


def _versus_split(cover: _Cover) -> SceneGraph:
    """Clash / confrontation topology: two facing subjects split by a central tension axis."""
    s, p, pal = cover.stories, cover.p, cover.pal
    lead, second = s[0], s[1]
    lead_img = lead.images[0] if lead.images else None
    second_img = second.images[0] if second.images else None

    y = cover.masthead(ear_story=s[4] if len(s) > 4 else None)
    strip_h = float(p.get("strip_mm", 55.0))
    hero_h = cover.bottom - y - strip_h - cover.gap
    half_w = (cover.width - cover.gap) / 2.0

    left_x = cover.left
    right_x = cover.left + half_w + cover.gap

    cover.used.append(lead.id)
    cover.used.append(second.id)

    photo_h = hero_h * float(p.get("photo_share", 0.50))
    text_h = hero_h - photo_h - cover.gap

    if lead_img:
        hero_photo = cover.photo(lead, lead_img, left_x, y, half_w, photo_h)
        hero_photo.importance = 0.96
    if second_img:
        sec_photo = cover.photo(second, second_img, right_x, y, half_w, photo_h)
        sec_photo.importance = 0.75

    # Center clash badge
    vs_w = min(28.0, half_w * 0.40)
    vs_h = 13.0
    vs_x = cover.left + (cover.width - vs_w) / 2.0
    vs_y = y + photo_h - vs_h / 2.0
    vs_frame = Frame(x=vs_x, y=vs_y, w=vs_w, h=vs_h)
    from .infographics import create_editorial_badge_box
    badge = create_editorial_badge_box(text="KONTRA", category="VS", frame=vs_frame,
                                       bg_color=pal["strong"], text_color=pal["ink_on_strong"])
    badge.z = 7
    badge.constraints.extend(["allow_stack", "intentional_photo_badge", "label", "fixed_width"])
    cover.ctx.elements.append(badge)

    # Lead text (dominant)
    ty = y + photo_h + cover.gap
    cover.plane(lead, "versus_left", left_x, ty, half_w, text_h, pal["light"])
    head_lead = cover.display(lead, left_x + 2, ty + 2, half_w - 4, text_h * 0.55,
                              color=pal["deep"], max_lines=3, min_lines=1, minimum=18.0, dominant=True)
    used_head_h = head_lead.frame.h if head_lead else text_h * 0.55
    if lead.lead or lead.body:
        cover.fit(lead, "lead" if lead.lead else "body", left_x + 2, ty + used_head_h + 2,
                  half_w - 4, text_h - used_head_h - 4, 10.0, color=pal.get("ink_on_light", pal["ink_on_paper"]), minimum=8.5)

    # Second text (subordinate)
    cover.plane(second, "versus_right", right_x, ty, half_w, text_h, pal["paper"])
    head_sec = cover.display(second, right_x + 2, ty + 2, half_w - 4, text_h * 0.55,
                             color=pal["strong"], max_lines=3, min_lines=1, minimum=16.0, dominant=False)
    used_sec_h = head_sec.frame.h if head_sec else text_h * 0.55
    if second.lead or second.body:
        cover.fit(second, "lead" if second.lead else "body", right_x + 2, ty + used_sec_h + 2,
                  half_w - 4, text_h - used_sec_h - 4, 10.0, color=pal["ink_on_paper"], minimum=8.5)

    # Bottom strip for remaining stories
    after = y + hero_h + cover.gap
    rem = s[2:]
    if rem:
        count = min(3, len(rem))
        shares = [.5, .5] if count == 2 else ([.33, .33, .34] if count == 3 else [1.0])
        planes = ["light", "paper", "deep"][:count]
        cover.strip(rem[:count], after, strip_h, shares, planes)

    return cover.finish({"versus_split": True})


BUILDERS = {
    "diagonal_hero_entry": _diagonal_hero_entry,
    "dual_scale_collage": _dual_scale_collage,
    "photo_dominant_strip": _photo_dominant_strip,
    "directional_tension": _directional_tension,
    "type_behind_subject": _type_behind_subject,
    "stacked_rail_cover": _stacked_rail_cover,
    "dense_mosaic": _dense_mosaic,
    "versus_split": _versus_split,
}


def compose_morphology(dna, material, genes: dict, stories: list, name: str) -> SceneGraph:
    if name not in BUILDERS:
        raise ValueError(f"unknown morphology {name}")
    cover = _Cover(dna, material, genes, [s.model_copy(deep=True) for s in stories], name)
    scene = BUILDERS[name](cover)
    scene.metadata["morphology_feasibility"] = feasible_morphologies(dna, material, stories).get(name, "")
    return scene
