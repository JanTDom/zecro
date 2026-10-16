"""TV-guide listing page: stations as navigation, hour bands, programme of the day.

The schedule (``PageInputMaterial.tv_schedule``) is laid out so a reader finds
station → hour → programme without reading the page:

* a navigation band with one colour tab per station (colours are DNA data in
  ``cover_grammar["navigation_colors"]``; colour marks the station, it is not
  decoration);
* a "programme of the day" box for the highlighted slot;
* a grid: one column per station, one row per hour band
  (``cover_grammar["hour_bands"]``) with the band label in the left gutter.

Each cell is measured with the real font.  Dense cells shrink to the readable
minimum; programmes that still do not fit are *not* silently dropped — they
are reported as missing content so the hard gate stops the page.
"""
from __future__ import annotations

from typing import Any

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, Relation, SceneGraph

DEFAULT_BANDS = [[6, 12, "Rano"], [12, 18, "Popołudnie"], [18, 24, "Wieczór"], [24, 30, "Noc"]]
DEFAULT_COLORS = ["#d62828", "#1d4e89", "#2a9d8f", "#e9a800", "#7b2cbf", "#ef6f00"]
MIN_LISTING_PT = 6.5


def _band_index(minutes: int, bands) -> int:
    hour = minutes / 60.0
    if hour < bands[0][0]:
        hour += 24  # after midnight belongs to the night band
    for index, (start, end, _) in enumerate(bands):
        if start <= hour < end:
            return index
    return len(bands) - 1


def compose_tv_listing(dna, material, genes: dict | None = None) -> SceneGraph:
    from .plan_composer import PT, _Ctx
    from .page_mood import readable_ink
    genes = genes or {}
    ctx = _Ctx(dna, material, genes)
    fmt, grammar = dna.format, (dna.cover_grammar or {})
    left, top = fmt.margin_left_mm, fmt.margin_top_mm
    right, bottom = fmt.trim_w_mm - fmt.margin_right_mm, fmt.trim_h_mm - fmt.margin_bottom_mm
    width = right - left
    schedule = sorted(material.tv_schedule, key=lambda slot: (slot.station, _band_index(slot.minutes, DEFAULT_BANDS), slot.minutes))
    stations = list(dict.fromkeys(slot.station for slot in material.tv_schedule))[: int(grammar.get("max_stations", 5))]
    colors = list(grammar.get("navigation_colors") or DEFAULT_COLORS)
    station_color = {station: colors[index % len(colors)] for index, station in enumerate(stations)}
    bands = [list(b) for b in (grammar.get("hour_bands") or DEFAULT_BANDS)]
    used_bands = sorted({_band_index(s.minutes, bands) for s in schedule if s.station in stations})
    missing: list[str] = []
    fit_log: list[dict[str, Any]] = []

    # Masthead + date strip (brand colour stays DNA-owned).
    mast_h = 16.0
    logo = ctx.text("logo", None, "masthead", left, top, width, mast_h, 30, value=material.masthead_title,
                    color="#ffffff", bg_color=dna.palette.primary)
    if getattr(dna, "logo_profile", None) and dna.logo_profile.asset_ref:
        logo.image_url, logo.content_ref = dna.logo_profile.asset_ref, "masthead.logo"
    y = top + mast_h + 1
    ctx.text("folio", None, "issue", left, y, width, 5, 7.5,
             value=f"{material.issue_date}  ·  {material.section_name or 'Program TV'}")
    y += 6

    # Navigation band: one tab per station, same order as the grid columns.
    gap = 1.6
    label_h = 5.5
    col_w = (width - gap * (len(stations) - 1)) / max(1, len(stations))
    nav_h = 8.0
    for index, station in enumerate(stations):
        x = left + index * (col_w + gap)
        tab = ctx.text("kicker", None, f"nav-{station}", x, y, col_w, nav_h, 10.5, value=station.upper(),
                       color=readable_ink(station_color[station]), bg_color=station_color[station])
        tab.content_ref = f"tv.nav.{station}"
        tab.constraints.append("navigation")
        tab.style.align = "center"
    y += nav_h + 2.5

    # Programme of the day: above the grid or closing the page (a genuine
    # alternative reading order, chosen by the architecture gene).
    highlight = next((slot for slot in material.tv_schedule if slot.highlight and slot.station in stations), None)
    at_bottom = str(genes.get("layout_mode", "")) in {"stacked", "modular-grid", "dominant-right"}
    grid_bottom = bottom
    box_h = (46.0 if highlight.image_url else 30.0) if highlight else 0.0
    resume_y = None
    if highlight and at_bottom:
        resume_y, y = y, bottom - box_h
        grid_bottom = bottom - box_h - 3
    if highlight:
        color = station_color[highlight.station]
        ctx.elements.append(Element(id="tv-highlight-field", role="band", importance=.1, content_ref="tv.highlight.field",
                                    frame=Frame(x=left, y=y, w=width, h=box_h), style=ElementStyle(bg_color=dna.palette.tint_bg),
                                    z=0, constraints=["decorative_background"]))
        text_x = left + 3
        if highlight.image_url:
            from ..models.schemas import StoryImageInput, StoryInput
            pseudo = StoryInput(id="tv-highlight", headline=highlight.title, body=highlight.description or "", importance=1)
            image = StoryImageInput(id="tv-highlight-image", url=highlight.image_url, width_px=highlight.image_width_px,
                                    height_px=highlight.image_height_px)
            photo_w = box_h * 1.5
            photo = ctx.photo(pseudo, image, left, y, photo_w, box_h, "crop")
            photo.content_ref = "tv.highlight.image"
            text_x = left + photo_w + 3
        tw = right - text_x - 3
        kick = ctx.text("kicker", None, "highlight-label", text_x, y + 2, tw, 6, 8.5,
                        value=f"PROGRAM DNIA · {highlight.station.upper()} · {highlight.time}",
                        color=readable_ink(color), bg_color=color)
        kick.content_ref = "tv.highlight.label"
        title = ctx.text("headline", None, "highlight-title", text_x, y + 9, tw, 14, min(26.0, dna.typography.scales.headline_m),
                         value=highlight.title, color=dna.palette.primary, dominant=True)
        title.content_ref, title.story_ref = "tv.highlight.title", "tv-highlight"
        if highlight.description:
            desc = ctx.text("body", None, "highlight-desc", text_x, y + 24, tw, box_h - 26, 8.6,
                            value=highlight.description, color=dna.palette.text)
            desc.content_ref = "tv.highlight.description"
        y += box_h + 3
    if resume_y is not None:
        y = resume_y

    # Grid: bands × stations.  Rows share the remaining height in proportion
    # to their measured demand, so a dense evening row gets more space.
    def cell_text(station: str, band: int) -> str:
        rows = [s for s in schedule if s.station == station and _band_index(s.minutes, bands) == band]
        return "\n".join(f"{s.time}  {s.title}" + (f" ({s.genre})" if s.genre else "") for s in rows)

    size = 8.2
    demand = {}
    for band in used_bands:
        demand[band] = max((ctx.need(cell_text(st, band), col_w - 2, "body", size) for st in stations), default=6.0) + 2
    avail = grid_bottom - y - (2 + label_h + .8) * len(used_bands)
    while sum(demand.values()) > avail and size > MIN_LISTING_PT:
        size = round(max(MIN_LISTING_PT, size * .94), 2)
        for band in used_bands:
            demand[band] = max((ctx.need(cell_text(st, band), col_w - 2, "body", size) for st in stations), default=6.0) + 2
    scale = avail / max(1.0, sum(demand.values()))
    fit_log.append({"action": "tv_listing_copyfit", "font_size_pt": size, "fits": scale >= 1.0})
    for band in used_bands:
        row_h = demand[band] * min(1.0, scale) if scale < 1 else demand[band] * min(scale, 1.6)
        label = ctx.text("kicker", None, f"band-{band}", left, y, width, label_h, 8.0,
                         value=f"{bands[band][2].upper()}  {bands[band][0] % 24}:00–{(bands[band][1] % 24) or 24}:00",
                         color=dna.palette.primary, bg_color=dna.palette.tint_bg)
        label.content_ref = f"tv.band.{band}"
        label.constraints.append("navigation")
        y += label_h + .8
        for index, station in enumerate(stations):
            text = cell_text(station, band)
            if not text:
                continue
            x = left + index * (col_w + gap)
            ctx.elements.append(Element(id=f"tv-rule-{station}-{band}", role="band", importance=.05,
                                        content_ref=f"tv.rule.{station}.{band}",
                                        frame=Frame(x=x, y=y, w=col_w, h=.8),
                                        style=ElementStyle(bg_color=station_color[station]), z=1,
                                        constraints=["decorative_background"]))
            need = ctx.need(text, col_w - 2, "body", size)
            if need > row_h - 1:
                missing.append(f"tv.{station}.{bands[band][2]}")
            cell = ctx.text("body", None, f"cell-{station}-{band}", x + 1, y + 1.4, col_w - 2, row_h - 1.4, size,
                            value=text, color=dna.palette.text, align="left")
            cell.content_ref, cell.story_ref = f"tv.{station}.{band}", f"tv-{station}"
        y += row_h + 2
    relations = [Relation(type="belongs_to_story", story=f"tv-{station}",
                          members=[e.id for e in ctx.elements if e.story_ref == f"tv-{station}"]) for station in stations]
    from .tabloid_morphologies import topology_signature
    scene = SceneGraph(
        page=PageMeta(trim=[fmt.trim_w_mm, fmt.trim_h_mm], bleed_mm=fmt.bleed_mm, safe_margin_mm=min(left, top),
                      grid={"cols": dna.grid.columns, "gutter_mm": dna.grid.gutter_mm,
                            "baseline_mm": dna.grid.baseline_grid_pt * PT, "rows": dna.grid.rows},
                      title_dna_ref=dna.id, page_zone=material.page_zone),
        elements=ctx.elements, relations=[r for r in relations if r.members], reading_order=ctx.order,
        metadata={"generator": "tv_listing", "architecture": "tv_listing", "layout_mode": "listing",
                  "cover_morphology": "listing_pick_bottom" if (highlight and at_bottom) else "listing_pick_top",
                  "page_zone": material.page_zone, "page_count": 1, "single_page_width_mm": fmt.trim_w_mm,
                  "stations": stations, "station_colors": station_color,
                  "hour_bands": [bands[b] for b in used_bands], "missing_content_refs": missing,
                  "fit_adjustments": [*ctx.fit, *fit_log], "style_blend": material.style_blend.model_dump(),
                  "omitted_stations": [s for s in dict.fromkeys(x.station for x in material.tv_schedule) if s not in stations],
                  "text_threads": {}})
    if scene.metadata["omitted_stations"]:
        scene.metadata["missing_content_refs"].extend(f"tv.{s}" for s in scene.metadata["omitted_stations"])
    scene.metadata["topology"] = topology_signature(scene)
    return scene
