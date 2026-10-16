"""Framed tabloid cover: content placed into the module skeleton.

``cover_modules.wukadka_skeleton`` fixes the modules (measured on NR20–22);
this composer only fills them.  Every element is tagged with the module it
belongs to (``module:<name>``); the hard gate checks that it stays inside
it, except for the breakouts the title's grammar allows (``breakout``).
Lead type is sheared 8.8° (``Frame.skew_y_deg``), never rotated.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..models.schemas import Element, Frame, PageMeta, SceneGraph
from .cover_modules import LEAN, SHEAR_DEG, lead_slots, wukadka_skeleton
from .layered_cover import (PT, TOP_EM, Kit, LayeredCover, _bottom_corner, _bottom_strip, _dark_caps_box,
                            _ensure_legible, _interview_box, _norm)


def _tag(els: list[Element], module: str, *extra: str):
    for e in els:
        e.constraints = [*(e.constraints or []), f"module:{module}", *extra]


def compose_framed_cover(material, *, kit_name: str = "wukadka", genes: Optional[dict[str, Any]] = None, dna: Optional[Any] = None) -> SceneGraph:
    kit = Kit(kit_name)
    genes = {"bottom": "corner", "skybox_order": "interview_first", **(genes or {})}
    material = _apply_text_moves(material, genes)
    c = LayeredCover(kit, material, genes)
    stories = list(material.stories)
    lead = next(s for s in stories if s.rank == "lead")
    hero = next((s for s in stories if s.rank == "second" and s.images and s.images[0].alpha_mask_url), None)
    _int = next((s_ for s_ in stories if s_.group == "interview"), None)
    _promo = next((s_ for s_ in stories if s_.group == "promo"), None)
    _teasers = [s_ for s_ in stories if s_.rank == "teaser" and s_ not in (_int, _promo)]
    _sky = next((s_ for s_ in _teasers if s_.pin_zone == "top"), _teasers[0] if _teasers else None)
    if not next((s_ for s_ in _teasers if s_ is not _sky), None):
        genes["_no_bottom"] = True        # U15: an empty module disappears; the star's column takes its place
    hero_mode = genes.get("hero_mode", "breakout")
    if hero and "hero_place" not in genes:
        genes["hero_place"] = (_place_hero_breakout(kit, hero.images[0], genes) if hero_mode == "breakout"
                               else _place_hero_frame(kit, hero.images[0], genes))
    sk = wukadka_skeleton(kit, material, genes)
    interview = next((s for s in stories if s.group == "interview"), None)
    promo = next((s for s in stories if s.group == "promo"), None)
    teasers = [s for s in stories if s.rank == "teaser" and s not in (interview, promo)]
    sky_other = next((s for s in teasers if s.pin_zone == "top"), teasers[0] if teasers else None)
    bottom = next((s for s in teasers if s is not sky_other), None)
    n0 = lambda: len(c.out.elements)

    # 1. the title's frame ------------------------------------------------------
    k = n0()
    band = sk["frame_band"].poly
    c.plate(-c.bleed, band[0][1], band[1][0] + c.bleed, band[2][1] - band[0][1], "panel", z=1)
    left = sk["frame_left"].poly
    c.plate(-c.bleed, left[0][1], left[1][0] + c.bleed, left[2][1] - left[0][1], "panel", z=1)
    bar = sk["frame_bar"].poly
    (bx0, by0), (bx1, _), (fx1, fy), (fx0, _) = bar
    top_c = ((bx0 + bx1) / 2, by0 + 1.2)
    foot_c = ((fx0 + fx1) / 2, fy)
    length = math.hypot(foot_c[0] - top_c[0], foot_c[1] - top_c[1])
    mid = ((top_c[0] + foot_c[0]) / 2, (top_c[1] + foot_c[1]) / 2)
    bar_el = c.plate(mid[0] - 9.7 / 2, mid[1] - length / 2, 9.7, length, "panel", z=12)
    bar_el.frame.rotation_deg = round(math.degrees(math.atan2(top_c[0] - foot_c[0], foot_c[1] - top_c[1])), 3)
    win = sk["lead_window"].poly
    # the white window sits above the hero (her arm stays behind the bar)
    (wx0, wy0), (wx1, _), (wx2, wy2), _ = win
    c.plate(wx0, wy0, wx2 - wx0 + .3, wy2 - wy0, "white", z=10)
    c.plate(wx2, wy0, wx1 - wx2, wy2 - wy0, "white", shape="triangle_tl", z=10)
    c.plate(90.0, wy0, bx1 - 90.0, 9.8, "panel", z=12)  # top rail of the window (NR21/22)
    fb = sk["frame_bottom"].poly
    c.plate(-c.bleed, fb[0][1], fb[1][0] + c.bleed, fb[2][1] - fb[0][1], "panel", z=1)
    lg = kit.frame["logo"]
    from pathlib import Path
    logo_url = None
    if dna and getattr(dna, "logo_profile", None) and getattr(dna.logo_profile, "asset_ref", None):
        logo_url = dna.logo_profile.asset_ref
    elif dna and getattr(dna, "masthead", None) and getattr(dna.masthead, "logo_url", None):
        logo_url = dna.masthead.logo_url
    if not logo_url:
        logo_url = str(Path(kit.data["_root"]) / lg["asset"])

    c.add(Element(id="logo", role="logo", frame=Frame(x=lg["x"], y=lg["y"], w=lg["w"], h=lg["h"]), z=4,
                  image_url=logo_url, importance=.9, constraints=["brand"]))
    d = kit.frame["dateline"]
    c.plate(d["x"], d["y"], d["w"], d["h"], "white", z=14)  # brand line stays above the hero
    values = {"issue_number": material.issue_number or "", "issue_date": material.issue_date or ""}
    cap_y = d["y"] + (d["h"] - kit.face("info").cap * d["size_pt"] * PT) / 2
    c.line(d["left"].format(**values), "info", d["size_pt"], d["x"] + 3, cap_y, "ink", role="folio", z=15, on="white")
    cw = kit.width(d["center"], "info", d["size_pt"])
    c.line(d["center"], "info", d["size_pt"], d["x"] + d["w"] * .52 - cw / 2, cap_y, "ink", role="folio", z=15, on="white")
    rw = kit.width(d["right"], "info", d["size_pt"])
    c.line(d["right"], "info", d["size_pt"], d["x"] + d["w"] - 3 - rw, cap_y, "red", role="folio", z=15, on="white")
    _tag(c.out.elements[k:], "frame")

    # 2. skybox -----------------------------------------------------------------
    order = [interview, sky_other] if genes["skybox_order"] == "interview_first" else [sky_other, interview]
    single = sum(1 for s_ in order if s_ is not None) == 1
    if single:
        # U15: one skybox story takes the whole skybox band (no empty slot)
        a_, b_ = sk["skybox_a"].poly, sk["skybox_b"].poly
        from .cover_modules import rect as _rect
        sk["skybox_a"].poly = _rect(a_[0][0], a_[0][1], b_[1][0], a_[2][1])
        del sk["skybox_b"]
        order = [next(s_ for s_ in order if s_ is not None), None]
    for name, story in zip(("skybox_a", "skybox_b"), order):
        if story is None:
            continue
        p = sk[name].poly
        x0, y0, x1, y1 = p[0][0], p[0][1], p[1][0], p[2][1]
        k = n0()
        if story is interview:
            _interview_box(c, story, x0, y0, min(x1, c.R) - x0, y1 - y0)
        else:
            _dark_caps_box(c, story, x0, y0, x1 - x0, y1 - y0)
        _tag(c.out.elements[k:], name)

    # 3. bottom teaser ------------------------------------------------------------
    if not bottom and "bottom_teaser" in sk:
        del sk["bottom_teaser"]
    if bottom:
        p = sk["bottom_teaser"].poly
        k = n0()
        if genes["bottom"] == "corner":
            _bottom_corner(c, bottom, box=(p[0][0], p[0][1]), framed=genes.get("corner_photos", "framed"))
        else:
            _bottom_strip(c, bottom, rise=0.0, photos=genes.get("corner_photos", "framed"))  # NR22
        _tag(c.out.elements[k:], "bottom_teaser")

    # 4. hero -------------------------------------------------------------------------
    if hero and "hero" in sk:
        p = sk["hero"].poly
        k = n0()
        img = hero.images[0]
        x0, top, w, h = genes["hero_place"]
        if hero_mode == "breakout":
            # NR21 / rulebook U16–U17: the photo with its own background fills
            # the right column (behind the band, window and bar, which cut its
            # edges), and only the head that leaves the column — over the
            # masthead band — is cut out, at the same geometry
            R = _hero_column(kit, genes)
            full = (x0, top, w, h)
            # two seamless crops of one image: above the bar's top the column
            # starts at the bar's top x; below it the photo reaches under the
            # leaning bar down to its foot (no white wedge, U16)
            from .cover_modules import LEAN as _LEAN
            low_x0 = float(genes.get("bar_top_x", 184.6)) - (R[3] - 147.3) * _LEAN
            fill = ground = None
            reach = low_x0 + 9.7 - 1.0          # bar's right edge at the floor, 1 mm under it
            if x0 > reach:
                # the photo cannot reach under the leaning bar: the frame
                # ground (the bar's own colour) closes the gap — never paper
                y_s = 147.3 + max(0.0, (float(genes.get("bar_top_x", 184.6)) + 9.7 - x0) / _LEAN)
                ground = c.plate(reach - 1.0, y_s, x0 - reach + 1.5, R[3] - y_s, "panel", z=1)
                # visible patch right of the bar: a triangle (D30 when large)
                c.out.decisions.append({"decision": "hero_ground_patch",
                                        "area_mm2": round(.5 * (R[3] - y_s) * (x0 - (low_x0 + 9.7)), 1),
                                        "x": round(low_x0 + 9.7, 1), "y": round(y_s, 1)})
            for rx0, ry0, ry1 in ((R[0], R[1], 147.3), (low_x0, 147.3, R[3])):
                rx0 = max(rx0, x0)
                crop = [(rx0 - x0) / w, (ry0 - top) / h, (R[2] - x0) / w, (ry1 - top) / h]
                el = c.photo(img, rx0, ry0, R[2] - rx0, ry1 - ry0, story=hero, z=0, crop=crop, importance=.8)
                el.constraints = [*(el.constraints or []), "fills_module"]
                fill = fill or el
            # a head cut by its source frame never rises above the column (U7)
            from .cutout_quality import cut_segments
            b_top = max(top, R[1]) if "top" in cut_segments(img.alpha_mask_url) else top
            c.breakout(img, full, (x0, b_top, R[2], 147.3), backing=fill, story=hero, z=13, importance=.8)
        else:
            vis = min(x0 + w, c.trim_w + c.bleed) - x0
            # above the white window (z 10), behind the bar and rail (z 12)
            c.photo(img, x0, top, vis, h, story=hero, cutout=True, z=int(genes.get("hero_z", 11)), importance=.8,
                    crop=[0, 0, vis / w, 1])
        _tag([e for e in c.out.elements[k:] if e is not (ground if hero_mode == "breakout" else None)], "hero")
        if hero_mode == "breakout" and ground is not None:
            _tag([ground], "frame")
        t = sk["hero_text"].poly
        tx0, ty0, tx1, ty1 = t[0][0], t[0][1], t[1][0], t[2][1]
        k = n0()
        y = ty0
        if hero.kicker:
            chip = 10.5
            name = hero.kicker.upper()
            nw = kit.width(name, "info", chip)
            g = kit.g["hero_name_chip"]
            c.plate(tx0, y, nw + 5, kit.face("info").cap * chip * PT + 3.2, g["bg"], z=24, story=hero, role="band")
            c.line(name, "info", chip, tx0 + 2.5, y + 1.6, g["color"], story=hero, role="kicker", z=25, on=g["bg"])
            y += kit.face("info").cap * chip * PT + 6.0
        colours = kit.g["hero_headline_colors"]
        c.stack(hero, hero.headline.split(), {_norm(w) for w in hero.headline_emphasis}, "display_italic", tx0, y,
                lambda a, b: tx1 - tx0, ty1, base=colours[0], accent=colours[1], max_lines=4,
                max_pt=float(kit.g.get("hero_headline_max_pt", 95.0)), min_pt=20, gap_em=.05, outline=("ink", .7),
                case="normal", importance=.85, z=26)
        for e in c.out.elements[k:]:
            if e.role == "headline" and e.style.color != kit.color(colours[1]):
                e.style.outline_color, e.style.outline_width_pt = None, None
        _tag(c.out.elements[k:], "hero_text")
        cp = sk["hero_copy"].poly
        k = n0()
        text = hero.lead or hero.body
        if text and text.strip() != "—":
            g = kit.g["hero_body_box"]
            c.copy(text, "body", g["size_pt"], cp[0][0], cp[0][1], cp[1][0] - cp[0][0], cp[2][1] - cp[0][1], g["color"],
                   story=hero, role="lead", bg=g["bg"], inset=[2, 2.2, 2, 2.2], page_ref=hero.page_ref, z=24,
                   min_size=g["size_pt"] - .5, max_size=g["size_pt"] + .5)  # fixed size, shorten copy
        _tag(c.out.elements[k:], "hero_copy")

    # a figure whose head is cut by its source frame comes out from UNDER the
    # skybox: the skybox modules are lifted above it (z + 10)
    if hero and "hero" in sk and genes["hero_place"][1] < 71.2:
        for e in c.out.elements:
            if any(t in (e.constraints or []) for t in ("module:skybox_a", "module:skybox_b")):
                e.z += 10

    # 5. lead: sheared plates, lines and paragraph from the slots ----------------------
    slots = lead_slots(kit, sk, lead, force_lines=genes.get("lead_lines"))
    hero_el = next((e for e in c.out.elements if e.role == "photo" and hero is not None and e.story_ref == hero.id
                    and e.treatment == "cutout"), None)
    from .layered_cover import Silhouette
    hero_sil = Silhouette(hero_el.mask_ref, hero_el.frame, hero_el.crop_box) if hero_el is not None else None
    tan = math.tan(math.radians(SHEAR_DEG))
    k = n0()
    emph = {_norm(w) for w in lead.headline_emphasis}
    for s in slots:
        if s.kind == "plate":
            (x0, yl), (x1, _), _, (_, ylb) = s.poly
            h = ylb - yl
            pl = c.plate(x0, yl, x1 - x0, h, "red", z=21, story=lead, role="band")
            pl.frame.skew_y_deg = SHEAR_DEG
            size = s.data["size"]
            ln = c.line(s.data["text"], "display", size, x0 + 2.0, yl + 2.2 - 2.0 * tan, "white", story=lead,
                        role="kicker", z=23, on="red")
            ln.frame.skew_y_deg = SHEAR_DEG
        elif s.kind == "line":
            (x0, yl) = s.poly[0]
            size = s.data["size"]
            words = s.data["text"].split()
            runs: list[tuple[str, str]] = []
            for w in words:
                col = "red" if _norm(w) in emph else "ink"
                if runs and runs[-1][1] == col:
                    runs[-1] = (runs[-1][0] + " " + w, col)
                else:
                    runs.append((w, col))
            x = x0
            space = kit.width(" ", "display", size)
            for txt, col in runs:
                el = c.line(txt, "display", size, x, yl - (x - x0) * tan, col, story=lead, importance=.97,
                            flow=f"stack-{lead.id}", z=22)
                el.frame.skew_y_deg = SHEAR_DEG
                x += kit.width(txt, "display", size) + space
        elif s.name == "lead_paragraph":
            x0, y0 = s.poly[0]
            x1, y1 = s.poly[1][0], s.poly[2][1]
            text = lead.lead or lead.body
            if hero_sil is not None:
                # U8: running text stops 2.5 mm before the star's silhouette
                # (the paragraph is sheared: its right end rises by w·tan)
                ext = hero_sil.x_extent(y0 - (x1 - x0) * tan, y1)
                if ext and ext[0] - 2.5 < x1:
                    x1 = ext[0] - 2.5
            if text and text.strip() != "—" and x1 - x0 <= 25:
                c.out.missing.append({"story_ref": lead.id, "field": "lead",
                                      "reason": "brak miejsca obok najkrótszego wiersza (postać zajmuje okno)"})
            if text and text.strip() != "—" and x1 - x0 > 25:
                el = c.copy(text, "body", kit.g["body_size_pt"], x0, y0, x1 - x0, y1 - y0, "ink", story=lead,
                            role="lead", page_ref=lead.page_ref,
                            # the title's body size is fixed (NR20–22: 9.5 pt, corpus);
                            # copy is shortened at sentence ends rather than shrunk
                            min_size=kit.g["body_size_pt"] - .5, max_size=kit.g["body_size_pt"] + .5)
                el.frame.skew_y_deg = SHEAR_DEG
    stack_first = next((e for e in c.out.elements[k:] if e.flow_group == f"stack-{lead.id}"), None)
    if stack_first:
        stack_first.constraints = [*(stack_first.constraints or []), "must_dominate"]
    _tag(c.out.elements[k:], "lead_window", "breakout")  # plates break over the dateline, last line over the rail

    # 6. promo roundel pinned on the bar -------------------------------------------------
    if promo:
        r = sk["roundel"].data
        (cx, cy), dmm = r["center"], 30.0 + 4.6
        ring = 49.3
        k = n0()
        c.plate(cx - ring / 2, cy - ring / 2, ring, ring, "white", shape="circle", z=30, story=promo)
        c.plate(cx - dmm / 2, cy - dmm / 2, dmm, dmm, kit.g["promo_roundel"]["bg"], shape="circle", z=31, story=promo)
        lines = [(promo.kicker or "").upper(), *promo.headline.upper().split(" ", 1), promo.page_ref or ""]
        lines = [l for l in lines if l]
        inner = dmm * .78
        big = min(26.0, min(inner / max(1e-6, kit.width(l, "teaser", 1.0)) for l in lines[1:-1] or lines))
        sizes = [big * .7] + [big] * (len(lines) - 2) + [big * .42]
        heights = [kit.face("teaser").cap * s_ * PT for s_ in sizes]
        total = sum(heights) + 1.4 * (len(lines) - 1)
        ty = cy - total / 2
        cols = [kit.g["promo_roundel"]["accent"]] + [kit.g["promo_roundel"]["color"]] * (len(lines) - 1)
        for line, s_, col, hgt in zip(lines, sizes, cols, heights):
            lw = kit.width(line, "teaser", s_)
            el = c.line(line, "teaser", s_, cx - lw / 2, ty + (lw / 2) * tan, col, story=promo, role="kicker", z=32,
                        constraints=("promo",), on=kit.g["promo_roundel"]["bg"])
            el.frame.skew_y_deg = SHEAR_DEG
            ty += hgt + 1.4
        _tag(c.out.elements[k:], "roundel")

    used = {e.image_url for e in c.out.elements if e.role == "photo"}
    for s in stories:
        for im in s.images:
            if im.url not in used:
                c.out.decisions.append({"decision": "image_not_used", "story_ref": s.id, "image": im.id})
    c.snap_near_edges()
    _ensure_legible(c)
    for sb in kit.substitutions:
        c.out.decisions.append({"decision": "font_substituted", **sb})
    els = c.out.elements
    # a window hole with the WHOLE source copy set is a copy request (the
    # editor writes more), not a layout fault; with copy cut it stays a fault
    from .layered_rules import window_holes
    probe = {"modules": {n: [list(p) for p in m.poly] for n, m in sk.items()},
             "module_kinds": {n: m.kind for n, m in sk.items()}, "cutout_masks": c.out.masks}
    for name, area in window_holes(els, probe):
        story = lead if lead is not None else None
        cut = any(dc.get("decision") == "copy_shortened" and dc.get("story_ref") == getattr(story, "id", None)
                  for dc in c.out.decisions)
        # a breaking forced by the art director that leaves the hole is the
        # layout's fault (another breaking fills the window), not the copy's
        if story is not None and not cut and not genes.get("lead_lines"):
            c.out.missing.append({"story_ref": story.id, "field": "lead", "window": name,
                                  "reason": f"za krótki tekst: okno ma dziurę {area:.0f} cm²",
                                  "target_extra_words": int(area * 100 / 45)})
    return SceneGraph(page=PageMeta(trim=[c.trim_w, c.trim_h], bleed_mm=c.bleed, safe_margin_mm=c.L,
                                    page_zone="front_page", page_role="cover"),
                      elements=els, reading_order=[e.id for e in sorted(els, key=lambda e: (e.frame.y, e.frame.x))],
                      metadata={"composition": "layered", "architecture": "framed_cover", "title_kit": kit_name,
                                "genes": genes, "face_boxes": c.out.faces, "face_boxes_full": c.out.faces_full, "cutout_masks": c.out.masks,
                                "modules": {n: [list(p) for p in m.poly] for n, m in sk.items()},
                                "module_kinds": {n: m.kind for n, m in sk.items()},
                                "live_area": [kit.data["format"]["live"]["left"], kit.data["format"]["live"]["top"],
                                              kit.data["format"]["live"]["right"], kit.data["format"]["live"]["bottom"]],
                                "photo_driven_decisions": c.out.decisions, "missing_content_refs": c.out.missing,
                                "logo_rule": {"element": "logo", "max_covered_share": kit.frame["logo"]["max_covered_share"]},
                                "copy_mode": getattr(material, "copy_mode", "source")})


def _place_hero_frame(kit, img, genes) -> tuple[float, float, float, float]:
    """Hero cut-out placement, solved against the title's measured limits and
    the rulebook (U6, U7, U11):

    * major straight cuts of the source frame (≥ 8 % of a side: torso, head)
      decide the anchoring — a head cut comes out from under the skybox, a
      torso cut stands on the page edge;
    * every cut (also a hand or a thumb touching the border) must end up
      hidden: under the bar, the hero copy box, the bottom teaser or the
      skybox, or beyond the trim — the visible millimetres are a cost;
    * face clear of the dateline bar; logo covered ≤ the kit's limit.
    Larger than the page is allowed (cropped at the bleed, never distorted)."""
    from types import SimpleNamespace
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    from .cover_modules import wukadka_skeleton
    from .cutout_quality import cut_segments
    from .layered_cover import Silhouette
    from ..models.schemas import Frame
    fmt = kit.data["format"]
    trim_w, trim_h = fmt["trim_mm"]
    edge = trim_w + fmt["bleed_mm"]
    cuts = cut_segments(img.alpha_mask_url)
    major = {k for k, (a0, a1) in cuts.items() if a1 - a0 >= .08}
    top = 71.2 - 1.5 if "top" in major else 71.2 + 3.8
    if "bottom" in major:
        bottom = trim_h + fmt["bleed_mm"]
    else:
        bottom = 324.7 + 10.0 if genes.get("bottom", "corner") == "corner" else 351.0
    sk = wukadka_skeleton(kit, SimpleNamespace(stories=[]), {k: v for k, v in genes.items() if k != "hero_place"})
    covers = [Polygon(sk["frame_bar"].poly), Polygon(sk["bottom_teaser"].poly), Polygon(sk["skybox_a"].poly),
              Polygon(sk["skybox_b"].poly)]
    tx1 = 258.7
    copy_bottom = (324.7 if genes.get("bottom", "corner") == "corner" else 351.0) - 7.2
    covers.append(box(tx1 - 50.2, copy_bottom - 39.5, tx1, copy_bottom))  # hero copy box
    cover = unary_union(covers).buffer(.3)
    page = box(0, 0, trim_w, trim_h)

    def visible_cut_mm(x0, t, w, h):
        tot = 0.0
        for side, (a0, a1) in cuts.items():
            if side in ("left", "right"):
                x = x0 if side == "left" else x0 + w
                seg = LineString([(x, t + a0 * h), (x, t + a1 * h)])
            else:
                y = t if side == "top" else t + h
                seg = LineString([(x0 + a0 * w, y), (x0 + a1 * w, y)])
            tot += seg.intersection(page).difference(cover).length
        return tot

    an = img.photo_analysis or {}
    faces = an.get("faces") or []
    lg = kit.frame["logo"]
    d = kit.frame["dateline"]
    aspect = (img.width_px or 1) / (img.height_px or 1)
    best = None
    dy0, sh0 = int(genes.get("hero_dy", 0)), int(genes.get("hero_shift", 0))
    for dy in range(dy0, 60 + dy0, 3):
        for shift in range(sh0, 40 + sh0, 2):
            if "top" in major and "bottom" in major:
                if dy != dy0:
                    break
                t, h = top, bottom - top
            elif "top" in major:
                t, h = top, bottom - top - dy
            else:
                t = top + dy
                h = bottom - t
            w = h * aspect
            x0 = edge - w + shift
            f = faces[0] if faces else None
            if f:
                fx0, fy0, fy1 = x0 + f[0] * w, t + f[1] * h, t + f[3] * h
                if fx0 < d["x"] + d["w"] - 15.0 and fy0 < d["y"] + d["h"] and fy1 > d["y"]:
                    continue
            sil = Silhouette(img.alpha_mask_url, Frame(x=x0, y=t, w=w, h=h))
            ext = sil.x_extent(lg["y"], lg["y"] + lg["h"])
            covered = 0.0 if not ext or ext[0] >= lg["x"] + lg["w"] else (lg["x"] + lg["w"] - ext[0]) / lg["w"]
            if covered > lg["max_covered_share"]:
                continue
            vis = visible_cut_mm(x0, t, w, h)
            cost = (dy - dy0) * 1.0 + (shift - sh0) * .6 + 25.0 * vis
            if best is None or cost < best[0]:
                best = (cost, (x0, t, w, h), vis)
    if best is None:
        return edge - (bottom - top) * aspect, top, (bottom - top) * aspect, bottom - top
    return best[1]


def _apply_text_moves(material, genes: dict):
    """Art-direction moves that touch the copy's presentation, never its words:
    which words carry the accent colour (U4).  Unknown words are ignored."""
    import re
    norm = lambda w: re.sub(r"[^\wąćęłńóśźż]", "", w.lower())
    stories = []
    for s in material.stories:
        key = {"lead": "lead_emphasis", "second": "hero_emphasis"}.get(s.rank)
        words = genes.get(key) if key else None
        if words is not None:
            have = {norm(w) for w in s.headline.split()}
            pick = [w for w in words if norm(w) in have][:3]
            s = s.model_copy(update={"headline_emphasis": pick})
        stories.append(s)
    return material.model_copy(update={"stories": stories})


def _hero_column(kit, genes) -> tuple[float, float, float, float]:
    """The star's column: from the bar's top x to the bleed, from the top of
    the masthead band to the bottom teaser.  Band (z 1), window (z 10), bar
    and rail (z 12), dateline (z 14) and the teaser box (z 28) lie above the
    photo and give it its edges."""
    fmt = kit.data["format"]
    edge = fmt["trim_mm"][0] + fmt["bleed_mm"]
    floor = 324.7 if genes.get("bottom", "corner") == "corner" else 351.0
    if genes.get("_no_bottom"):
        floor = 375.1                     # down to the frame's bottom rail (U15)
    return (float(genes.get("bar_top_x", 184.6)), 78.6, edge, floor)


_HERO_CACHE: dict = {}


def _place_hero_breakout(kit, img, genes) -> tuple[float, float, float, float]:
    """Memoised: the solve depends only on the image, the column and the zoom."""
    key = (kit.name if hasattr(kit, "name") else id(kit), img.url, img.width_px, img.height_px,
           tuple(_hero_column(kit, genes)), float(genes.get("bar_top_x", 184.6)), float(genes.get("hero_scale", 1.0)))
    if key not in _HERO_CACHE:
        _HERO_CACHE[key] = _solve_hero_breakout(kit, img, genes)
    return _HERO_CACHE[key]


def _solve_hero_breakout(kit, img, genes) -> tuple[float, float, float, float]:
    """Full image frame for the breakout hero: it covers the column (U16),
    the face sits in the visible part of the column, clear of the dateline,
    the cut-out head covers the logo no more than the title's limit
    (NR21 ~9 %, kit <= 12 %) and the print stays >= 180 dpi.  Within those
    hard limits the photo reaches as far as it can under the leaning bar
    (below the band the bar hides the photo's edge; what it cannot reach is
    closed by the frame ground in the drawing, never left as paper — U18).
    ``hero_scale`` zooms in."""
    from .layered_cover import Silhouette
    from ..models.schemas import Frame
    from .cover_modules import LEAN
    R = _hero_column(kit, genes)
    W, H = R[2] - R[0], R[3] - R[1]
    bar_x = float(genes.get("bar_top_x", 184.6))
    # 1.5 mm under the bar's right edge at the column floor
    foot_x = bar_x - (R[3] - 147.3) * LEAN + 9.7 - 1.5
    aspect = (img.width_px or 1) / (img.height_px or 1)
    faces = (img.photo_analysis or {}).get("faces") or []
    f = faces[0] if faces else [.35, .1, .65, .35]
    fcx, fcy = (f[0] + f[2]) / 2, (f[1] + f[3]) / 2
    lg, d = kit.frame["logo"], kit.frame["dateline"]
    target_y = R[1] + .2 * H

    def face_hidden(fx0, fy0, fx1, fy1):
        """mm of the face hidden by the dateline bar (z 14) or, below the
        band, by the leaning bar and its rail (z 12); 0 = fully visible."""
        cost = 0.0
        if fy0 < d["y"] + d["h"] and fy1 > d["y"] and fx0 < d["x"] + d["w"]:
            cost += (min(fx1, d["x"] + d["w"]) - fx0)
        if fy1 > 147.3:
            bar_r = bar_x - (fy1 - 147.3) * LEAN + 9.7 + 1.0
            cost += max(0.0, bar_r - fx0) * 2
        return cost

    best = None
    for scale in (1.0, 1.04, 1.08, 1.12, 1.16, 1.2, 1.25, 1.3):
        h = max(H, W / aspect) * scale * float(genes.get("hero_scale", 1.0))
        w = h * aspect
        dpi = (img.width_px or 3000) / (w / 25.4)
        for tx in [bar_x + (R[2] - bar_x) * (.3 + .04 * i) for i in range(12)]:
            x0 = min(R[0], max(R[2] - w, tx - fcx * w))
            for ty in (target_y - 10, target_y, target_y + 10):
                y0 = min(R[1], max(R[3] - h, ty - fcy * h))
                fx0, fy0, fx1, fy1 = x0 + f[0] * w, y0 + f[1] * h, x0 + f[2] * w, y0 + f[3] * h
                sil = Silhouette(img.alpha_mask_url, Frame(x=x0, y=y0, w=w, h=h))
                ext = sil.x_extent(lg["y"], min(lg["y"] + lg["h"], 147.3))
                covered = 0.0 if not ext or ext[0] >= lg["x"] + lg["w"] else (lg["x"] + lg["w"] - ext[0]) / lg["w"]
                hard = (face_hidden(fx0, fy0, fx1, fy1) * 50 + max(0.0, covered - lg["max_covered_share"]) * 4000
                        + max(0.0, 180.0 - dpi) * 20)
                soft = (abs((fy1 - fy0) - 55) * .3 + abs(covered - .09) * 30 + (scale - 1) * 5
                        + max(0.0, x0 - foot_x) * 1.5)          # paper/ground under the bar
                cost = hard * 100 + soft
                if best is None or cost < best[0]:
                    best = (cost, (x0, y0, w, h))
    return best[1]
