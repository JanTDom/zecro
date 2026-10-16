"""Hard rules for layered covers (composition == "layered").

On a layered cover overlap is the norm, so the pairwise "no collision" rule
of box layouts is replaced by measured rules:

1. text of one story never sits on the text of another story, and the
   glyph masses (cap boxes) of display lines never overlap,
2. nothing drawn above a photo covers a detected face,
3. a cut-out hides at most the kit's share of the logo; nothing else may sit
   on the logo,
4. text printed over a photo has measured contrast (WCAG ratio on the actual
   pixels under the type; an outline counts as the text edge).
"""
from __future__ import annotations

from typing import Optional

from shapely.geometry import Polygon, box

from ..models.schemas import Element, SceneGraph

PT = 25.4 / 72.0
TEXT_ROLES = {"headline", "deck", "lead", "body", "kicker", "caption", "byline", "pullquote", "jump_line", "folio"}


def _poly(frame, shape="rect") -> Polygon:
    from .critic import _frame_polygon
    return Polygon(_frame_polygon(frame, shape))


def _ink_frame(el: Element):
    """Cap box of a display line (cap top .. baseline); full frame otherwise."""
    from copy import copy
    f = el.frame
    if "display_line" not in (el.constraints or []) or not el.style or not el.style.font_size_pt:
        return f
    size = el.style.font_size_pt * PT
    g = copy(f)
    cap = _cap(el)
    g.y = f.y + (.80 - cap) * size
    g.h = cap * size
    return g


def _cap(el: Element) -> float:
    try:
        from .fonts import resolve_font, style_face_args
        from fontTools.ttLib import TTFont
        a = style_face_args(el.style)
        path = resolve_font(el.style.font_family, text=el.text_content or "", weight=a["weight"], italic=a["italic"],
                            width=a["width"])
        t = TTFont(path, lazy=True)
        return (getattr(t["OS/2"], "sCapHeight", 0) or .7 * t["head"].unitsPerEm) / t["head"].unitsPerEm
    except Exception:
        return .70


_BOUNDS: dict = {}


def _glyph_bounds(path: str):
    if path not in _BOUNDS:
        from fontTools.ttLib import TTFont
        from fontTools.pens.boundsPen import BoundsPen
        t = TTFont(path, lazy=True)
        gs, cmap, upm = t.getGlyphSet(), t.getBestCmap(), t["head"].unitsPerEm
        cache = {}

        def get(ch):
            if ch not in cache:
                name = cmap.get(ord(ch))
                if not name:
                    cache[ch] = None
                else:
                    pen = BoundsPen(gs)
                    gs[name].draw(pen)
                    b = pen.bounds
                    cache[ch] = None if b is None else tuple(v / upm for v in b)
            return cache[ch]
        _BOUNDS[path] = get
    return _BOUNDS[path]


def glyph_polys(el: Element) -> list[Polygon]:
    """Real ink of a display line: one box per glyph, accents and ogonki
    included, placed with the shaper's advances and rotated like the frame."""
    import math
    from .fonts import resolve_font, style_face_args
    from .shaper import width_pt
    st = el.style
    text = (el.text_content or "")
    text = text.upper() if st.case == "upper" else text
    a = style_face_args(st)
    path = resolve_font(st.font_family, text=text, weight=a["weight"], italic=a["italic"], width=a["width"])
    if not path:
        return [_poly(el.frame)]
    get = _glyph_bounds(path)
    size = float(st.font_size_pt) * PT
    f = el.frame
    base_y = f.y + .80 * size
    cx, cy = f.x + f.w / 2, f.y + f.h / 2
    r = math.radians(float(f.rotation_deg or 0))
    out = []
    for i, ch in enumerate(text):
        b = get(ch)
        if not b or ch.isspace():
            continue
        trk = float(st.tracking_em or 0.0)
        x0 = f.x + (width_pt(text[:i], st.font_size_pt, path, trk) * PT if i else 0.0)
        pts = [(x0 + b[0] * size, base_y - b[3] * size), (x0 + b[2] * size, base_y - b[3] * size),
               (x0 + b[2] * size, base_y - b[1] * size), (x0 + b[0] * size, base_y - b[1] * size)]
        if f.skew_y_deg:
            t = math.tan(math.radians(f.skew_y_deg))
            pts = [(px, py - (px - f.x) * t) for px, py in pts]
        if r:
            pts = [(cx + (px - cx) * math.cos(r) - (py - cy) * math.sin(r),
                    cy + (px - cx) * math.sin(r) + (py - cy) * math.cos(r)) for px, py in pts]
        out.append(Polygon(pts))
    return out or [_poly(el.frame)]


def _ink(el: Element):
    from shapely.ops import unary_union
    if "display_line" in (el.constraints or []) and el.style and el.style.font_size_pt:
        return unary_union(glyph_polys(el))
    return _poly(el.frame)


def _luminance(rgb) -> float:
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def _hex(value: Optional[str]):
    value = (value or "#000000").lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _contrast(a, b) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


def _pixels_under(photo: Element, region: Polygon, masks: dict):
    """RGB pixels of ``photo`` (visible part only) under ``region``."""
    import numpy as np
    from PIL import Image
    from .renderers.production_utils import local_asset
    src = local_asset(photo.mask_ref if photo.treatment == "cutout" and photo.mask_ref else photo.image_url)
    if not src:
        return None
    with Image.open(src) as im:
        im = im.convert("RGBA")
        crop = photo.crop_box or [0, 0, 1, 1]
        W, H = im.size
        im = im.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
        f = photo.frame
        scale = 4  # px per mm is plenty for a median
        im = im.resize((max(4, int(f.w * scale)), max(4, int(f.h * scale))))
        arr = np.asarray(im)
    x0, y0, x1, y1 = region.bounds
    c0, c1 = int(max(0, (x0 - f.x) * scale)), int(min(arr.shape[1], (x1 - f.x) * scale))
    r0, r1 = int(max(0, (y0 - f.y) * scale)), int(min(arr.shape[0], (y1 - f.y) * scale))
    if c1 <= c0 or r1 <= r0:
        return None
    sub = arr[r0:r1, c0:c1].reshape(-1, 4)
    sub = sub[sub[:, 3] > 128]
    return sub[:, :3] if len(sub) else None


def required_contrast(style) -> float:
    """WCAG 2.x: large text (>= 18 pt, or >= 14 pt bold) needs 3:1, else 4.5:1."""
    size = float(style.font_size_pt or 0)
    w = str(style.font_weight or "")
    bold = w in ("bold",) or (w.isdigit() and int(w) >= 700)
    return 3.0 if size >= 18 or (bold and size >= 14) else 4.5


def legible(colour_hex: str, bg_hex: str, style) -> bool:
    return _contrast(_hex(colour_hex), _hex(bg_hex)) >= required_contrast(style)


GROUND_PATCH_MAX_MM2 = 400.0   # 4 cm² (NR21-like corner variant: ~2.6)


def layered_violations(sg: SceneGraph) -> list[str]:
    meta = sg.metadata or {}
    out: list[str] = []
    els = sg.elements
    # D30: a gap the photo could not reach, closed with the frame ground —
    # tolerated while small; large, it reads as a misshapen bar
    for dcs in (meta.get("photo_driven_decisions") or []):
        if isinstance(dcs, dict) and dcs.get("decision") == "hero_ground_patch" and dcs["area_mm2"] > GROUND_PATCH_MAX_MM2:
            out.append(f"Zdjęcie bohatera nie sięga pod belkę: klin {dcs['area_mm2'] / 100:.0f} cm² (okolice x={dcs['x']:.0f}, "
                       f"y={dcs['y']:.0f}) łatany gruntem ramy — za mało pikseli albo za niski moduł dolny; "
                       f"wybierz wyższy moduł dolny (narożnik) albo inne zdjęcie.")
    texts = [e for e in els if e.role in TEXT_ROLES and e.text_content]
    # 1. text on text (glyph ink for display lines, frames for copy)
    inks = {e.id: _ink(e) for e in texts}
    for i, a in enumerate(texts):
        pa = inks[a.id]
        for b in texts[i + 1:]:
            if a.story_ref == b.story_ref and a.flow_group and a.flow_group == b.flow_group:
                # lines of one stack: glyphs (with accents/ogonki) must not touch
                if pa.intersection(inks[b.id]).area > .5:
                    out.append(f"Linie tytułu {a.id} i {b.id} nachodzą na siebie.")
                continue
            if a.role == "folio" and b.role == "folio":
                continue
            pb = inks[b.id]
            area = pa.intersection(pb).area
            if area > 2.0:
                who = "różnych materiałów" if a.story_ref != b.story_ref else "tego samego materiału"
                out.append(f"Tekst {a.id} leży na tekście {b.id} ({who}, {area:.0f} mm²).")
    # 1b. a cut-out drawn above type never hides it
    masks_ = meta.get("cutout_masks") or {}
    for ph in (e for e in els if e.role == "photo"):
        sil = None
        for t in texts:
            if t.z >= ph.z or t.story_ref == ph.story_ref and t.role == "caption":
                continue
            ink_t = inks[t.id]
            if not ink_t.intersects(_poly(ph.frame)):
                continue
            if ph.treatment == "cutout" and ph.id in masks_:
                if sil is None:
                    from .layered_cover import Silhouette
                    sil = Silhouette(masks_[ph.id], ph.frame, ph.crop_box)
                x0, y0, x1, y1 = ink_t.bounds
                share = sil.covers(x0, y0, x1, y1)
            else:
                share = ink_t.intersection(_poly(ph.frame)).area / max(1e-6, ink_t.area)
            if share > .03:
                out.append(f"Zdjęcie {ph.id} zasłania tekst {t.id} ({share:.0%}).")
    # 2. faces
    faces = meta.get("face_boxes") or {}
    photos = {e.id: e for e in els if e.role == "photo"}
    for pid, boxes in faces.items():
        photo = photos.get(pid)
        if not photo:
            continue
        for fb in boxes:
            face = box(*fb)
            # the face is shown by the topmost photo of the same image that
            # covers it (a partial cut-out over its own rectangle, U17)
            same = [q for q in els if q.role == "photo" and q.image_url == photo.image_url
                    and _poly(q.frame).intersection(face).area > .5 * face.area]
            top_z = max([photo.z] + [q.z for q in same])
            for e in els:
                if e.z <= top_z or e.id == pid or "brand" in (e.constraints or []):
                    continue
                if e.role == "photo" and e.image_url == photo.image_url:
                    continue
                if e.role == "photo" and e.treatment == "cutout" and e.id in (meta.get("cutout_masks") or {}):
                    # a cut-out covers with its silhouette, not its frame
                    from .layered_cover import Silhouette
                    share = Silhouette(meta["cutout_masks"][e.id], e.frame, e.crop_box).covers(*fb)
                else:
                    poly = _poly(_ink_frame(e) if e.role in TEXT_ROLES else e.frame, e.shape if e.role not in TEXT_ROLES else "rect")
                    share = poly.intersection(face).area / max(1e-6, face.area)
                if share > .03:
                    out.append(f"Element {e.id} ({e.role}) zakrywa twarz na zdjęciu {pid} ({share:.0%}).")
    # 3. logo
    rule = meta.get("logo_rule") or {}
    logo = next((e for e in els if e.id == rule.get("element")), None)
    if logo:
        lp = _poly(logo.frame)
        masks = meta.get("cutout_masks") or {}
        for e in els:
            if e.z <= logo.z or e.id == logo.id:
                continue
            if e.role == "photo" and e.treatment == "cutout" and e.id in masks:
                from .layered_cover import Silhouette
                sil = Silhouette(masks[e.id], e.frame, e.crop_box)
                ext = sil.x_extent(logo.frame.y, logo.frame.y + logo.frame.h)
                lx1 = logo.frame.x + logo.frame.w
                share = 0.0 if not ext or ext[0] >= lx1 or ext[1] <= logo.frame.x else \
                    (min(lx1, ext[1]) - max(logo.frame.x, ext[0])) / logo.frame.w
                if share > float(rule.get("max_covered_share", .1)) + 1e-6:
                    out.append(f"Postać {e.id} zakrywa {share:.0%} winiety (dopuszczalne "
                               f"{float(rule.get('max_covered_share', .1)):.0%}).")
            elif lp.intersection(_poly(e.frame, e.shape)).area > 1.0:
                out.append(f"Element {e.id} ({e.role}) leży na winiecie.")
    # 3b. anchoring: an element tagged with a module stays inside it, except
    # the breakouts the title's grammar allows; untagged editorial elements
    # on a framed cover are "floating" and rejected.
    modules = meta.get("modules") or {}
    if modules:
        for e in els:
            tags = [t for t in (e.constraints or []) if t.startswith("module:")]
            if not tags:
                if e.role != "logo" and "brand" not in (e.constraints or []):
                    out.append(f"Element {e.id} ({e.role}) nie jest przypięty do żadnego modułu.")
                continue
            name = tags[0].split(":", 1)[1]
            if name not in modules or "breakout" in (e.constraints or []) or name == "frame":
                continue
            mod = Polygon(modules[name]).buffer(1.5)
            shape = _ink(e) if e.role in TEXT_ROLES and e.text_content else _poly(e.frame, e.shape)
            outside = shape.difference(mod).area / max(1e-6, shape.area)
            if e.role == "photo" and e.treatment == "cutout":
                continue  # a cut-out may leave its module (checked by the face/logo rules)
            if outside > .03:
                out.append(f"Element {e.id} ({e.role}) wychodzi poza moduł {name} ({outside:.0%}).")
    # 4. a line of type never sits on a visible edge of a colour plane
    for t, plate in straddled_edges(els, meta):
        out.append(f"Wiersz {t.id} leży na krawędzi plamy {plate.id}.")
    # 5. contrast
    for t, name, ratio, need in contrast_failures(els, meta):
        out.append(f"Tekst {t.id} na tle {name} ma kontrast {ratio:.1f}:1 (min {need}:1).")
    out.extend(photo_text_violations(els, meta, list(sg.page.trim or [])))
    for pid, share in figures_on_paper(els, meta, list(sg.page.trim or [])):
        out.append(f"Wycięta postać {pid} stoi na białym papierze ({share:.0%} obrysu bez gruntu) — "
                   f"potrzebny grunt: zdjęcie w prostokącie, apla albo wycięcie tylko poza modułem.")
    asked = {m.get("window") for m in (meta.get("missing_content_refs") or []) if isinstance(m, dict)}
    for name, area in window_holes(els, meta):
        if name in asked:
            continue              # a pending copy request fills it (more lead copy)
        out.append(f"Okno {name} ma dziurę {area:.0f} cm² — tytuł i lead mają wypełniać okno (inne łamanie, lead pod stosem).")
    for pid, area, share in empty_in_boxes(els, meta):
        out.append(f"Moduł {pid} ma pusty fragment {area:.0f} cm² ({share:.0%} pola) — treść ma wypełniać pudełko.")
    for a, b, gap in near_miss_edges(els, list(sg.page.trim or [])):
        out.append(f"Krawędzie {a} i {b} rozminęły się o {gap:.1f} mm — mają się pokrywać albo być wyraźnie odsunięte.")
    for (cx, cy), w0, w1 in tapered_gaps(els, meta, list(sg.page.trim or [])):
        out.append(f"Klin białego papieru między elementami (szerokość {w0:.0f}→{w1:.0f} mm, okolice x={cx:.0f}, "
                   f"y={cy:.0f}) — elementy mają się stykać albo trzymać stały rowek.")
    for area, (cx, cy) in unowned_white(els, meta, list(sg.page.trim or [])):
        out.append(f"Martwe pole: {area:.0f} cm² papieru nie należy do żadnego modułu (okolice x={cx:.0f}, y={cy:.0f} mm).")
    return out


UNOWNED_MAX_CM2 = 12.0   # D27: a white area larger than ~35×35 mm owned by nothing


def unowned_white(els: list[Element], meta: dict, trim: list) -> list[tuple[float, tuple[float, float]]]:
    """Rulebook U16/D27: every part of the live area belongs to a module —
    a photo (a cut-out owns only its silhouette), a plate (also a designed
    white one), a text block or the logo.  Gutters and margins are allowed:
    the free area is eroded by 3 mm before measuring.  Returns the regions
    above the limit as (cm², centre)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    if not trim or len(trim) < 2:
        return []
    W, H = float(trim[0]), float(trim[1])
    live = meta.get("live_area") or [0, 0, W, H]
    sc = 1.0  # px per mm
    owned = Image.new("L", (int(W * sc) + 1, int(H * sc) + 1), 0)
    d = ImageDraw.Draw(owned)
    masks_ = meta.get("cutout_masks") or {}
    for e in els:
        if e.role == "photo" and e.treatment == "cutout" and e.id in masks_:
            try:
                with Image.open(masks_[e.id]) as im:
                    a = im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")
                    cb = e.crop_box or [0, 0, 1, 1]
                    A0, A1 = a.size
                    a = a.crop((int(cb[0] * A0), int(cb[1] * A1), int(cb[2] * A0), int(cb[3] * A1)))
                    a = a.resize((max(1, int(e.frame.w * sc)), max(1, int(e.frame.h * sc))))
                    owned.paste(255, (int(e.frame.x * sc), int(e.frame.y * sc)), a.point(lambda v: 255 if v > 100 else 0))
            except Exception:
                pass
            continue
        poly = _poly(e.frame, e.shape if e.role not in TEXT_ROLES else "rect")
        if not poly.is_empty:
            d.polygon([(x * sc, y * sc) for x, y in poly.exterior.coords], fill=255)
    free = np.asarray(owned) == 0
    m = np.zeros_like(free)
    x0, y0, x1, y1 = [int(v * sc) for v in live]
    m[max(0, y0):y1, max(0, x0):x1] = True
    free &= m
    er = np.asarray(Image.fromarray(free.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(7))) > 0
    # connected free regions on a 2 mm grid
    g = er[::2, ::2]
    seen = np.zeros_like(g)
    out = []
    hh, ww = g.shape
    for yy, xx in zip(*np.nonzero(g)):
        if seen[yy, xx]:
            continue
        stack, cells = [(yy, xx)], []
        seen[yy, xx] = True
        while stack:
            cy, cx = stack.pop()
            cells.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < hh and 0 <= nx < ww and g[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        # eroded area under-counts by the 3 mm rim: add it back approximately
        area_cm2 = len(cells) * 4 / 100.0
        if area_cm2 > UNOWNED_MAX_CM2:
            ys, xs = zip(*cells)
            out.append((area_cm2, (float(np.mean(xs)) * 2 / sc, float(np.mean(ys)) * 2 / sc)))
    return sorted(out, reverse=True)



SMALL_TEXT_PT = 24.0      # U8: only display type (≥ 24 pt) may stand on a photo
MIN_FACE_MM = 12.0        # U6: a face smaller than this does not read in print


def photo_text_violations(els: list[Element], meta: dict, trim: Optional[list] = None) -> list[str]:
    """D05 small type on a photo, D07 faces too small, D09 straight cut edges
    in the field.  Rules from the rulebook (knowledge/rulebook.md U6–U8)."""
    out: list[str] = []
    masks_ = meta.get("cutout_masks") or {}
    modules = meta.get("modules") or {}
    photos = [e for e in els if e.role == "photo"]
    plates = [e for e in els if e.role in {"band", "rule"} or (e.role not in TEXT_ROLES and e.role not in {"photo", "logo"})]
    sils = {}

    def silhouette(ph):
        if ph.id not in sils:
            from .layered_cover import Silhouette
            sils[ph.id] = Silhouette(masks_[ph.id], ph.frame, ph.crop_box) if ph.treatment == "cutout" and ph.id in masks_ else None
        return sils[ph.id]

    # D05
    for t in (e for e in els if e.role in TEXT_ROLES and e.text_content):
        size = float((t.style.font_size_pt if t.style else None) or 0)
        if size >= SMALL_TEXT_PT or (t.style and t.style.bg_color):
            continue
        ink_t = _ink(t)
        x0, y0, x1, y1 = ink_t.bounds
        for ph in photos:
            if ph.z >= t.z or not ink_t.intersects(_poly(ph.frame)):
                continue
            sil = silhouette(ph)
            share = sil.covers(x0, y0, x1, y1) if sil is not None else \
                ink_t.intersection(_poly(ph.frame)).area / max(1e-6, ink_t.area)
            if share <= .02:
                continue
            # an opaque plate between the photo and the text is an apla: fine
            from shapely.ops import unary_union
            between = [_poly(p.frame, p.shape) for p in plates if ph.z < p.z < t.z]
            shielded = bool(between) and unary_union(between).buffer(.2).contains(ink_t)
            if not shielded:
                out.append(f"Drobny tekst {t.id} ({size:.1f} pt) leży na zdjęciu {ph.id} bez apli ({share:.0%}).")
    # D07
    full_of = meta.get("face_boxes_full") or {}
    url_of = {e.id: e.image_url for e in photos}
    for pid, boxes in (meta.get("face_boxes") or {}).items():
        for i, fb in enumerate(boxes):
            hmm = fb[3] - fb[1]
            full = (full_of.get(pid) or [None] * len(boxes))[i] if i < len(full_of.get(pid) or []) else None
            if full and hmm < full[3] - full[1] - .1:
                # clipped: a seamless sibling crop of the same image (same full
                # box) shows the rest, so the face is judged whole
                seen = sum(b[3] - b[1] for q, bs in (meta.get("face_boxes") or {}).items()
                           if url_of.get(q) == url_of.get(pid)
                           for j, b in enumerate(bs)
                           if j < len(full_of.get(q) or []) and
                           max(abs(u - v) for u, v in zip(full_of[q][j], full)) < .5)
                if seen >= (full[3] - full[1]) - .5:
                    hmm = full[3] - full[1]
            if hmm < MIN_FACE_MM:
                out.append(f"Twarz na zdjęciu {pid} ma {hmm:.1f} mm wysokości (min {MIN_FACE_MM:.0f} mm).")
    # D09
    for item in cut_edge_report(els, meta, trim):
        for side, st in item["sides"].items():
            if st["visible_mm"] > 1.0:
                out.append(f"Wycięcie {item['element']} kończy się prostą krawędzią ({side}, {st['visible_mm']:.0f} mm "
                           f"widoczne) w polu modułu {item['module']}.")
    return out


def contrast_failures(els: list[Element], meta: dict) -> list[tuple]:
    """The background of each text is whatever is drawn directly below it
    (a plate, a photo's measured pixels, or the paper)."""
    import numpy as np
    masks = meta.get("cutout_masks") or {}
    texts = [e for e in els if e.role in TEXT_ROLES and e.text_content]
    fails = []
    for t in texts:
        if t.style and t.style.bg_color:
            bgs = [("plate", _hex(t.style.bg_color))]
        else:
            region = _poly(_ink_frame(t))
            below = sorted((e for e in els if e.z < t.z and e.id != t.id
                            and (e.role == "photo" or (e.style and e.style.bg_color and not e.text_content))
                            and region.intersects(_poly(e.frame, e.shape))), key=lambda e: -e.z)
            bgs, remaining = [], 1.0
            for e in below:
                inter = region.intersection(_poly(e.frame, e.shape))
                cover = inter.area / max(1e-6, region.area)
                if e.role == "photo":
                    pix = _pixels_under(e, inter, masks)
                    if pix is None or len(pix) < 12:
                        continue
                    cover *= min(1.0, len(pix) / max(1.0, inter.area * 16))
                    if cover < .08:
                        continue
                    bgs.append(("photo:" + e.id, tuple(np.median(pix, axis=0))))
                else:
                    bgs.append(("plate:" + e.id, _hex(e.style.bg_color)))
                remaining -= cover
                if remaining <= .1:
                    break
            if remaining > .1:
                bgs.append(("paper", (255, 255, 255)))
        colours = [_hex(t.style.color)] + ([_hex(t.style.outline_color)] if t.style.outline_color else [])
        need = required_contrast(t.style)
        for name, bg in bgs:
            ratio = max(_contrast(c, bg) for c in colours)
            if ratio < need:
                fails.append((t, name, ratio, need))
    return fails


def straddled_edges(els: list[Element], meta: dict) -> list[tuple]:
    """(text, plate) pairs where a visible plate edge runs through the ink.

    An edge hidden by something drawn above the plate (a cut-out, a photo,
    another plate) does not count: only what the reader actually sees."""
    from shapely.geometry import Point
    masks = meta.get("cutout_masks") or {}
    texts = [e for e in els if e.role in TEXT_ROLES and e.text_content and not (e.style and e.style.bg_color)]
    planes = [e for e in els if e.role == "band" and not e.text_content and e.style and e.style.bg_color]
    # adjacent planes of one colour are one surface (a seam between them is invisible)
    from shapely.ops import unary_union
    merged = []
    for colour in {p.style.bg_color for p in planes}:
        group = [p for p in planes if p.style.bg_color == colour]
        for z in {p.z for p in group}:
            same = [p for p in group if p.z == z]
            union = unary_union([_poly(p.frame, p.shape).buffer(.2) for p in same]).buffer(-.2)
            for geom in getattr(union, "geoms", [union]):
                merged.append((same[0], geom))
    sils = {}
    out = []
    for t in texts:
        ink = _ink(t)
        for p, poly in merged:
            if p.z >= t.z:
                continue
            if not poly.intersects(ink):
                continue
            share = poly.intersection(ink).area / max(1e-6, ink.area)
            if share <= .02 or share >= .98:
                continue
            edge = poly.exterior.intersection(ink)
            if edge.is_empty or edge.length < 1.0:
                continue
            between = [e for e in els if p.z < e.z < t.z and e.id != t.id
                       and (e.role == "photo" or (e.style and e.style.bg_color and not e.text_content))]
            visible = False
            n = max(2, int(edge.length))
            for k in range(n + 1):
                pt = edge.interpolate(k / n, normalized=True)
                hidden = False
                for e in between:
                    if e.role == "photo" and e.id in masks:
                        if e.id not in sils:
                            from .layered_cover import Silhouette
                            sils[e.id] = Silhouette(masks[e.id], e.frame, e.crop_box)
                        if sils[e.id].covers(pt.x - .4, pt.y - .4, pt.x + .4, pt.y + .4) > .5:
                            hidden = True
                            break
                    elif _poly(e.frame, e.shape).contains(Point(pt.x, pt.y)):
                        hidden = True
                        break
                if not hidden:
                    visible = True
                    break
            if visible:
                out.append((t, p))
    return out


def cut_edge_report(els: list[Element], meta: dict, trim: Optional[list] = None) -> list[dict]:
    """Every straight cut of every cut-out, with where it lies and how much of
    it is visible (mm): on a drawn edge (plate/frame), under a higher opaque
    element, beyond the trim, on a structural module edge, or in the field.
    Used by the gate (D09) and given to the AI editor as fact."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from .cutout_quality import cut_segments
    masks_ = meta.get("cutout_masks") or {}
    modules = meta.get("modules") or {}
    kinds = meta.get("module_kinds") or {}
    trim = list(trim or []) + [None, None]
    report = []
    for ph in (e for e in els if e.role == "photo" and e.treatment == "cutout" and e.id in masks_):
        tag = next((t.split(":", 1)[1] for t in (ph.constraints or []) if t.startswith("module:")), None)
        if tag not in modules:
            continue
        xs = [p[0] for p in modules[tag]]; ys = [p[1] for p in modules[tag]]
        structural = kinds.get(tag) != "cutout"
        mx0, my0, mx1, my1 = min(xs), min(ys), max(xs), max(ys)
        f = ph.frame
        covers = [_poly(e.frame, e.shape) for e in els
                  if e.z > ph.z and e.role not in TEXT_ROLES and e.role != "logo"
                  and not (e.role == "photo" and e.treatment == "cutout")]
        # a rectangle of the same image under/over the cut-out shows identical
        # pixels: a straight crop edge over it is invisible (U17 partial cut-out)
        covers += [_poly(e.frame) for e in els if e.id != ph.id and e.role == "photo"
                   and e.image_url == ph.image_url and e.treatment != "cutout"]
        cover = unary_union(covers).buffer(.3) if covers else None
        drawn = [_poly(e.frame, e.shape).exterior.buffer(1.0) for e in els
                 if e.id != ph.id and e.role not in TEXT_ROLES and e.role != "logo"
                 and not (e.role == "photo" and e.treatment == "cutout")]
        on_drawn = unary_union(drawn) if drawn else None
        page = box(0, 0, trim[0], trim[1]) if trim[0] and trim[1] else None
        segs: dict[str, LineString] = {}
        for side, (a0, a1) in cut_segments(masks_[ph.id], ph.crop_box).items():
            pos = {"left": f.x, "right": f.x + f.w, "top": f.y, "bottom": f.y + f.h}[side]
            if structural and abs(pos - {"left": mx0, "right": mx1, "top": my0, "bottom": my1}[side]) <= 1.5:
                segs[side] = None
                continue
            segs[side] = (LineString([(pos, f.y + a0 * f.h), (pos, f.y + a1 * f.h)]) if side in ("left", "right")
                          else LineString([(f.x + a0 * f.w, pos), (f.x + a1 * f.w, pos)]))
        # NB: straight runs INSIDE the contour (cutout_quality.straight_edges)
        # are not gated: straight hair or a sleeve gives false alarms; the AI
        # editor judges them on high-resolution close-ups.
        sides = {}
        for side, seg in segs.items():
            if seg is None:
                sides[side] = {"where": "na krawędzi modułu", "visible_mm": 0.0}
                continue
            total = seg.length
            if page is not None:
                seg = seg.intersection(page)
            if seg.is_empty or seg.length < .5:
                sides[side] = {"where": "poza stroną (spad)", "visible_mm": 0.0}
                continue
            vis = seg.difference(cover) if cover is not None else seg
            if vis.length < .5:
                sides[side] = {"where": "schowana pod elementem wyżej", "visible_mm": 0.0}
                continue
            if on_drawn is not None and vis.difference(on_drawn).length < 1.0:
                sides[side] = {"where": "na rysowanej krawędzi (apla/rama)", "visible_mm": 0.0}
                continue
            left = vis.difference(on_drawn) if on_drawn is not None else vis
            sides[side] = {"where": "w polu", "visible_mm": round(left.length, 1), "total_mm": round(total, 1)}
        report.append({"element": ph.id, "story": ph.story_ref, "module": tag, "sides": sides})
    return report


ON_PAPER_MAX = .35   # D26: share of a cut-out's outline that may touch bare paper


def _is_whiteish(hex_):
    rgb = _hex(hex_)
    return rgb is not None and min(rgb) >= 235


def figures_on_paper(els: list[Element], meta: dict, trim: list) -> list[tuple[str, float]]:
    """Rulebook U17/D26: a fully cut-out figure needs a ground — a photo, a
    coloured apla or the frame — under its outline.  Measures the 2 mm ring
    around the silhouette: the share lying on bare paper (nothing drawn
    below, or a white plate)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    if not trim or len(trim) < 2:
        return []
    W, H = float(trim[0]), float(trim[1])
    masks_ = meta.get("cutout_masks") or {}
    out = []
    for ph in (e for e in els if e.role == "photo" and e.treatment == "cutout" and e.id in masks_):
        if any(c.startswith("backed_by:") for c in (ph.constraints or [])):
            continue                                  # a partial cut-out over its own photo
        sc = 2.0
        ground = Image.new("L", (int(W * sc) + 1, int(H * sc) + 1), 0)
        d = ImageDraw.Draw(ground)
        for e in els:
            if e.id == ph.id or e.z >= ph.z and e.role != "photo":
                pass
            if e.id == ph.id or e.role in TEXT_ROLES:
                continue
            if e.role == "photo" and e.treatment == "cutout":
                continue
            if e.role != "photo" and (not e.style or not e.style.bg_color or _is_whiteish(e.style.bg_color)) \
                    and e.role not in {"logo"}:
                continue
            poly = _poly(e.frame, e.shape)
            if not poly.is_empty:
                d.polygon([(x * sc, y * sc) for x, y in poly.exterior.coords], fill=255)
        try:
            with Image.open(masks_[ph.id]) as im:
                a = im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")
                cb = ph.crop_box or [0, 0, 1, 1]
                A0, A1 = a.size
                a = a.crop((int(cb[0] * A0), int(cb[1] * A1), int(cb[2] * A0), int(cb[3] * A1)))
                a = a.resize((max(1, int(ph.frame.w * sc)), max(1, int(ph.frame.h * sc))))
        except Exception:
            continue
        sil = Image.new("L", ground.size, 0)
        sil.paste(a.point(lambda v: 255 if v > 100 else 0), (int(ph.frame.x * sc), int(ph.frame.y * sc)))
        ring = np.asarray(sil.filter(ImageFilter.MaxFilter(9))) > 0
        ring &= ~(np.asarray(sil) > 0)
        page = np.zeros_like(ring)
        page[:int(H * sc), :int(W * sc)] = True
        ring &= page
        if ring.sum() < 50:
            continue
        on_paper = float((ring & ~(np.asarray(ground) > 0)).sum() / ring.sum())
        if on_paper > ON_PAPER_MAX:
            out.append((ph.id, on_paper))
    return out


BOX_EMPTY_MAX = (6.0, .20)   # D28: free area in a box: cm² and share of the box
WINDOW_EMPTY_MAX = 30.0      # D28: a hole in a type window (cm²) — NR20–22 windows are full


def _module_of(e):
    return next((t.split(":", 1)[1] for t in (e.constraints or []) if t.startswith("module:")), None)


def _largest_free_cm2(P, content: list[Element], masks_: dict) -> float:
    """Largest connected part of polygon P not covered by ``content`` (a text
    block owns its whole measure; cut-outs count by their mask), cm²."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    sc = 1.0
    x0, y0, x1, y1 = P.bounds
    W, H = int(x1 - x0) + 1, int(y1 - y0) + 1
    free = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(free)
    d.polygon([((x - x0) * sc, (y - y0) * sc) for x, y in P.exterior.coords], fill=255)
    # a text block owns its whole measure: a ragged right edge or line
    # spacing is not a hole — group the type of one story into one block
    blocks: dict = {}
    for e in content:
        if e.role in TEXT_ROLES and e.text_content:
            q = _ink(e)
            if not q.is_empty:
                blocks.setdefault((e.story_ref, e.role in {"lead", "body", "caption", "jump_line"}), []).append(q.bounds)
    for bb in blocks.values():
        bx0, by0 = min(b[0] for b in bb), min(b[1] for b in bb)
        bx1, by1 = max(b[2] for b in bb), max(b[3] for b in bb)
        d.rectangle([bx0 - x0, by0 - y0, bx1 - x0, by1 - y0], fill=0)
    for e in content:
        if e.role == "photo" and e.treatment == "cutout" and e.id in masks_:
            try:
                with Image.open(masks_[e.id]) as im:
                    a = im.getchannel("A")
                    cb = e.crop_box or [0, 0, 1, 1]
                    A0, A1 = a.size
                    a = a.crop((int(cb[0] * A0), int(cb[1] * A1), int(cb[2] * A0), int(cb[3] * A1)))
                    a = a.resize((max(1, int(e.frame.w)), max(1, int(e.frame.h))))
                    free.paste(0, (int(e.frame.x - x0), int(e.frame.y - y0)), a.point(lambda v: 255 if v > 100 else 0))
            except Exception:
                pass
            continue
        q = _ink(e) if e.role in TEXT_ROLES and e.text_content else _poly(e.frame, e.shape)
        for part in getattr(q, "geoms", [q]):
            if not part.is_empty and hasattr(part, "exterior"):
                d.polygon([((x - x0) * sc, (y - y0) * sc) for x, y in part.exterior.coords], fill=0)
    return _largest_component_cm2(free)


def largest_free_of_polys_cm2(P, polys) -> float:
    """Same measure for planned geometry (shapely polygons as content)."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = P.bounds
    free = Image.new("L", (int(x1 - x0) + 1, int(y1 - y0) + 1), 0)
    d = ImageDraw.Draw(free)
    d.polygon([(x - x0, y - y0) for x, y in P.exterior.coords], fill=255)
    for q in polys:
        for part in getattr(q, "geoms", [q]):
            if not part.is_empty and hasattr(part, "exterior"):
                d.polygon([(x - x0, y - y0) for x, y in part.exterior.coords], fill=0)
    return _largest_component_cm2(free)


def _largest_component_cm2(free) -> float:
    import numpy as np
    from PIL import ImageFilter
    # inner padding (~3 mm) and line gaps are not holes
    er = np.asarray(free.filter(ImageFilter.MinFilter(7))) > 0
    g = er[::2, ::2]
    seen = np.zeros_like(g)
    best = 0
    hh, ww = g.shape
    for yy, xx in zip(*np.nonzero(g)):
        if seen[yy, xx]:
            continue
        stack, n = [(yy, xx)], 0
        seen[yy, xx] = True
        while stack:
            cy, cx = stack.pop(); n += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < hh and 0 <= nx < ww and g[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        best = max(best, n)
    return best * 4 / 100.0 * 1.6      # erosion took ~3 mm off every side: rough add-back


def window_holes(els: list[Element], meta: dict) -> list[tuple[str, float]]:
    """D28 for windows (the lead window of a framed cover): its type fills it;
    a free part over WINDOW_EMPTY_MAX cm² is a hole the eye falls into."""
    from shapely.geometry import Polygon
    kinds = meta.get("module_kinds") or {}
    mods = meta.get("modules") or {}
    out = []
    for name, kind in kinds.items():
        if kind != "window" or name not in mods:
            continue
        P = Polygon(mods[name])
        content = [e for e in els if _module_of(e) != "frame"
                   and _poly(e.frame, e.shape).intersection(P).area > 1.0]
        area = _largest_free_cm2(P, content, meta.get("cutout_masks") or {})
        if area > WINDOW_EMPTY_MAX:
            out.append((name, area))
    return out


def empty_in_boxes(els: list[Element], meta: dict) -> list[tuple[str, float, float]]:
    """Rulebook U16/D28: a box (plate carrying content) is filled by its
    content; a free part larger than the limit is a hole.  Frame, window and
    brand plates are structure, not boxes."""
    kinds = meta.get("module_kinds") or {}
    masks_ = meta.get("cutout_masks") or {}
    out = []
    for p in (e for e in els if e.role == "band" and not e.text_content):
        mod = _module_of(p)
        if mod == "frame" or kinds.get(mod) in {"frame", "window", "brand"} or "brand" in (p.constraints or []):
            continue
        P = _poly(p.frame, p.shape)
        if P.area < 400:                              # < 4 cm²: chips, small plates
            continue
        content = [e for e in els if e.id != p.id and e.z > p.z and not (e.role == "band" and e.frame.w * e.frame.h < 50)
                   and _poly(e.frame).intersection(P).area > .5 * max(1e-6, _poly(e.frame).area * (1 if e.role != "photo" else .2))]
        if not content:
            continue
        area_cm2 = _largest_free_cm2(P, content, masks_)
        share = area_cm2 * 100 / P.area
        if area_cm2 > BOX_EMPTY_MAX[0] and share > BOX_EMPTY_MAX[1]:
            out.append((p.id, area_cm2, share))
    return out


def near_miss_edges(els: list[Element], trim: list, lo: float = .3, hi: float = 2.5) -> list[tuple[str, str, float]]:
    """Rulebook U9/D29: parallel edges of plates and photos that almost meet
    (0.3–2.5 mm apart over ≥ 3 mm) read as a mistake — a step, a sliver of
    paper.  They must coincide or be clearly apart."""
    if not trim:
        return []
    W, H = float(trim[0]), float(trim[1])
    edges = []
    for e in els:
        if e.role not in {"band", "photo"} or (e.role == "photo" and e.treatment == "cutout"):
            continue
        f = e.frame
        if f.rotation_deg or getattr(f, "skew_y_deg", 0) or not (e.shape in (None, "rect")):
            continue
        for x in (f.x, f.x + f.w):
            if 0 < x < W:
                edges.append(("v", x, max(0, f.y), min(H, f.y + f.h), e.id))
        for y in (f.y, f.y + f.h):
            if 0 < y < H:
                edges.append(("h", y, max(0, f.x), min(W, f.x + f.w), e.id))
    # only VISIBLE edges can form a step: drop edge parts hidden under higher
    # opaque elements (a photo edge under the window plate is not on paper)
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    by_id = {e.id: e for e in els}
    vis_edges = []
    for kind, c_, a0, a1, eid in edges:
        z = by_id[eid].z
        above = [_poly(o.frame, o.shape) for o in els if o.z > z and o.role not in TEXT_ROLES and o.id != eid
                 and not (o.role == "photo" and o.treatment == "cutout")]
        seg = LineString([(c_, a0), (c_, a1)]) if kind == "v" else LineString([(a0, c_), (a1, c_)])
        if above:
            seg = seg.difference(unary_union(above))
        if seg.is_empty or seg.length < 3.0:
            continue
        b = seg.bounds
        lo_, hi_ = (b[1], b[3]) if kind == "v" else (b[0], b[2])
        vis_edges.append((kind, c_, lo_, hi_, eid))
    edges = vis_edges
    out, seen = [], set()
    for i, a in enumerate(edges):
        for b in edges[i + 1:]:
            if a[0] != b[0] or a[4] == b[4]:
                continue
            gap = abs(a[1] - b[1])
            overlap = min(a[3], b[3]) - max(a[2], b[2])
            if lo < gap < hi and overlap >= 3.0:
                key = tuple(sorted((a[4], b[4])))
                if key not in seen:
                    seen.add(key)
                    out.append((key[0], key[1], gap))
    return out


def _owned_raster(els, meta, W, H, sc, white_is_paper: bool = False):
    import numpy as np
    from PIL import Image, ImageDraw
    owned = Image.new("L", (int(W * sc) + 1, int(H * sc) + 1), 0)
    d = ImageDraw.Draw(owned)
    masks_ = meta.get("cutout_masks") or {}
    for e in els:
        if e.role == "photo" and e.treatment == "cutout" and e.id in masks_:
            try:
                with Image.open(masks_[e.id]) as im:
                    a = im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")
                    cb = e.crop_box or [0, 0, 1, 1]
                    A0, A1 = a.size
                    a = a.crop((int(cb[0] * A0), int(cb[1] * A1), int(cb[2] * A0), int(cb[3] * A1)))
                    a = a.resize((max(1, int(e.frame.w * sc)), max(1, int(e.frame.h * sc))))
                    owned.paste(255, (int(e.frame.x * sc), int(e.frame.y * sc)), a.point(lambda v: 255 if v > 100 else 0))
            except Exception:
                pass
            continue
        if e.role in TEXT_ROLES:
            continue                       # type does not bound a gap: only plates, photos, logo
        if white_is_paper and e.role == "band" and e.style and _is_whiteish(e.style.bg_color):
            continue                       # a white plate reads as the same paper
        poly = _poly(e.frame, e.shape)
        for part in getattr(poly, "geoms", [poly]):
            if not part.is_empty and hasattr(part, "exterior"):
                d.polygon([(x * sc, y * sc) for x, y in part.exterior.coords], fill=255)
    return np.asarray(owned) > 0


def tapered_gaps(els: list[Element], meta: dict, trim: list, min_h: float = 25.0, taper: float = 3.0,
                 max_w: float = 18.0) -> list[tuple[tuple[float, float], float, float]]:
    """Rulebook U18/D30: a strip of bare paper squeezed between two elements
    whose width changes along its length (a wedge) — e.g. between a leaning
    bar and a photo edge.  Gutters keep a constant width and pass."""
    import numpy as np
    if not trim or len(trim) < 2:
        return []
    W, H = float(trim[0]), float(trim[1])
    sc = 2.0
    owned = _owned_raster(els, meta, W, H, sc, white_is_paper=True)
    hh, ww = owned.shape
    tracks: list[list] = []          # each: list of (y_mm, width_mm, x0_px, x1_px)
    active: list[list] = []
    for y in range(0, min(hh, int(H * sc))):
        row = owned[y, :int(W * sc)]
        edges = list(np.nonzero(np.diff(row.astype(np.int8)))[0] + 1)
        segs = []
        for a_, b_ in zip(edges, edges[1:]):
            if not row[a_] and row[a_ - 1] and b_ < len(row) and row[b_]:
                wmm = (b_ - a_) / sc
                if 1.0 <= wmm <= max_w * 1.6:
                    segs.append((a_, b_, wmm))
        new_active = []
        for a_, b_, wmm in segs:
            tr = next((t for t in active if t[-1][2] < b_ and a_ < t[-1][3]), None)
            if tr is None:
                tr = []
                tracks.append(tr)
            tr.append((y / sc, wmm, a_, b_))
            new_active.append(tr)
        active = new_active
    # a wedge widens smoothly; a jump in width is a step between two elements
    pieces = []
    for tr in tracks:
        cur = [tr[0]] if tr else []
        for q in tr[1:]:
            if abs(q[1] - cur[-1][1]) > 1.5 or q[0] - cur[-1][0] > 1.0:
                pieces.append(cur); cur = [q]
            else:
                cur.append(q)
        if cur:
            pieces.append(cur)
    out = []
    for tr in pieces:
        if len(tr) < 2 or tr[-1][0] - tr[0][0] < min_h:
            continue
        wv = [q[1] for q in tr if q[1] <= max_w]
        if len(wv) < 2:
            continue
        if max(wv) - min(wv) >= taper:
            ys = [q[0] for q in tr]
            xs_ = [(q[2] + q[3]) / 2 / sc for q in tr]
            out.append(((float(np.mean(xs_)), float(np.mean(ys))), min(wv), max(wv)))
    return out
