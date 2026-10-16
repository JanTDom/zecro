"""Layered tabloid cover ("kolaż warstwowy").

A popular cover is not a set of non-overlapping boxes.  It is a stack of
layers: brand frame (panel, logo, dateline) -> paper card -> cut-out people
-> display type set word by word -> stickers and roundels.  Overlap is the
norm; what is forbidden is measured instead:

* text of one story may not sit on the text of another story,
* no text and no sticker may cover a detected face,
* a cut-out may hide only a bounded share of the logo,
* text printed on a photo needs measured contrast.

The constant part of a title (logo, colours, faces, the brand frame) comes
from a *title kit* (``title_kits/<name>/kit.json``) measured from the
title's own production files.  The variable part is composed here from the
material and a small set of genes; no page of the corpus is copied.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from ..models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph

PT = 25.4 / 72.0  # mm per point
KITS = Path(__file__).with_name("title_kits")
DESC_EM = .23     # room under the baseline (Polish ogonek, comma)
TOP_EM = .80      # renderer: first baseline sits .8 em under the frame top


# ---------------------------------------------------------------- the kit
@lru_cache(maxsize=8)
def load_kit(name: str) -> dict[str, Any]:
    root = KITS / name
    kit = json.loads((root / "kit.json").read_text(encoding="utf-8"))
    kit["_root"] = str(root)
    return kit


@dataclass
class Face:
    family: str
    weight: str
    style: Optional[str]
    stretch: Optional[str]
    path: Optional[str]
    cap: float


class Kit:
    def __init__(self, name: str):
        self.data = load_kit(name)
        self.name = name
        self.pal = self.data["palette"]
        self.frame = self.data["brand_frame"]
        self.g = self.data["grammar"]
        self._faces: dict[str, Face] = {}
        self.substitutions: list[dict] = []

    def color(self, key: str) -> str:
        return self.pal.get(key, key)

    def face(self, key: str) -> Face:
        if key not in self._faces:
            from .fonts import STRETCH_CLASS, resolve_face, local_file
            spec = dict(self.data["fonts"][key])
            face = None
            # Only a face of the named family counts; the library's silent
            # fallback (another family) is replaced by the kit's own chain.
            for fam in [spec["family"], *spec.get("fallbacks", [])]:
                cand = resolve_face(fam, weight=int(spec.get("weight", 400)),
                                    italic=spec.get("style") == "italic", text="ĄĆĘŁŃÓŚŹŻąćęłńóśźż",
                                    width=STRETCH_CLASS.get(spec.get("stretch")) if spec.get("stretch") else None)
                if cand and str(cand.get("family", "")).lower() == fam.lower():
                    face = cand
                    if fam != spec["family"]:
                        self.substitutions.append({"role": key, "wanted": spec["family"], "used": fam})
                    spec["family"] = fam
                    break
            if face is None:
                self.substitutions.append({"role": key, "wanted": spec["family"], "used": None})
            path = str(local_file(face)) if face and local_file(face) else None
            cap = .70
            if path:
                try:
                    from fontTools.ttLib import TTFont
                    t = TTFont(path, lazy=True)
                    cap = (getattr(t["OS/2"], "sCapHeight", 0) or .70 * t["head"].unitsPerEm) / t["head"].unitsPerEm
                except Exception:
                    pass
            self._faces[key] = Face(spec["family"], str(spec.get("weight", "400")), spec.get("style"),
                                    spec.get("stretch"), path, cap)
        return self._faces[key]

    def tracking(self, key: str) -> float:
        return float(self.data["fonts"][key].get("tracking_em", 0.0))

    def width(self, text: str, key: str, size_pt: float) -> float:
        """Advance width with the kit's tracking, minus the trailing track
        after the last glyph (which prints as nothing)."""
        from .shaper import width_pt
        trk = self.tracking(key)
        w = width_pt(text, size_pt, self.face(key).path, trk)
        return (w - (trk * size_pt if text else 0.0)) * PT

    def style(self, key: str, size: float, color: str, **extra) -> ElementStyle:
        f = self.face(key)
        return ElementStyle(font_family=f.family, font_weight=f.weight, font_style=f.style, font_stretch=f.stretch,
                            font_size_pt=round(size, 2), line_height_pt=round(size * 1.0, 2), color=self.color(color),
                            tracking_em=self.tracking(key) or None, **extra)


# ------------------------------------------------------------- geometry
def rotate_about(cx: float, cy: float, px: float, py: float, deg: float) -> tuple[float, float]:
    """Clockwise-positive rotation in page (y-down) coordinates."""
    a = math.radians(deg)
    dx, dy = cx - px, cy - py
    return px + dx * math.cos(a) - dy * math.sin(a), py + dx * math.sin(a) + dy * math.cos(a)


class Silhouette:
    """Opaque extent of a placed cut-out, measured from its alpha mask."""

    def __init__(self, mask_path: str, frame: Frame, crop: Optional[list[float]] = None):
        import numpy as np
        from PIL import Image
        with Image.open(mask_path) as im:
            alpha = im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")
            if crop:
                W, H = alpha.size
                alpha = alpha.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
            small = alpha.resize((max(8, int(frame.w * 2)), max(8, int(frame.h * 2))))
        self.a = np.asarray(small) > 110
        self.f = frame

    def x_extent(self, y0: float, y1: float) -> Optional[tuple[float, float]]:
        f, a = self.f, self.a
        r0 = int(max(0, (y0 - f.y) / f.h * a.shape[0]))
        r1 = int(min(a.shape[0], math.ceil((y1 - f.y) / f.h * a.shape[0])))
        if r1 <= r0:
            return None
        cols = a[r0:r1].any(axis=0)
        if not cols.any():
            return None
        idx = cols.nonzero()[0]
        return f.x + idx[0] / a.shape[1] * f.w, f.x + (idx[-1] + 1) / a.shape[1] * f.w

    def covers(self, x0: float, y0: float, x1: float, y1: float) -> float:
        """Share of the rectangle covered by the opaque silhouette."""
        f, a = self.f, self.a
        c0 = int(max(0, (x0 - f.x) / f.w * a.shape[1])); c1 = int(min(a.shape[1], math.ceil((x1 - f.x) / f.w * a.shape[1])))
        r0 = int(max(0, (y0 - f.y) / f.h * a.shape[0])); r1 = int(min(a.shape[0], math.ceil((y1 - f.y) / f.h * a.shape[0])))
        area = max(1e-6, (x1 - x0) * (y1 - y0))
        if c1 <= c0 or r1 <= r0:
            return 0.0
        cell = (f.w / a.shape[1]) * (f.h / a.shape[0])
        return float(a[r0:r1, c0:c1].sum() * cell / area)


# ---------------------------------------------------------- the composer
@dataclass
class Placed:
    elements: list[Element] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    faces: dict[str, list[list[float]]] = field(default_factory=dict)  # photo id -> face boxes (mm)
    masks: dict[str, str] = field(default_factory=dict)
    # photo id -> the same face boxes before clipping to the element (mm):
    # a face split between seamless crops of one image is judged whole
    faces_full: dict[str, list[list[float]]] = field(default_factory=dict)


class LayeredCover:
    def __init__(self, kit: Kit, material, genes: dict[str, Any]):
        self.kit, self.m, self.genes = kit, material, genes
        fmt = kit.data["format"]
        self.trim_w, self.trim_h = fmt["trim_mm"]
        self.bleed = fmt["bleed_mm"]
        live = fmt["live"]
        self.L, self.R, self.T, self.B = live["left"], live["right"], live["top"], live["bottom"]
        self.out = Placed()
        self.n = 0
        self.aside = None

    # -- element factories
    def _id(self, stem: str) -> str:
        self.n += 1
        return f"{stem}-{self.n}"

    def add(self, el: Element) -> Element:
        self.out.elements.append(el)
        return el

    def plate(self, x, y, w, h, color, *, shape="rect", z=1, story=None, border=None, role="band", importance=.3):
        st = ElementStyle(bg_color=self.kit.color(color))
        if border:
            st.border_color, st.border_width_mm = self.kit.color(border[0]), border[1]
        return self.add(Element(id=self._id("plate"), role=role, frame=Frame(x=x, y=y, w=w, h=h), z=z, style=st,
                                shape=shape, story_ref=getattr(story, "id", None), importance=importance,
                                constraints=["decor"]))

    def legible_colour(self, wanted: str, on: Optional[str], style: ElementStyle) -> str:
        """The kit's colour, or its declared legible alternative on ``on``."""
        if not on:
            return wanted
        from .layered_rules import legible
        bg = self.kit.color(on)
        for key in [wanted, *self.kit.g.get("legible_alternatives", {}).get(wanted, []), "ink", "white"]:
            if legible(self.kit.color(key), bg, style):
                if key != wanted:
                    self.out.decisions.append({"decision": "colour_for_contrast", "wanted": wanted, "used": key,
                                               "background": on})
                return key
        return wanted

    def line(self, text, key, size, x, y_cap, color, *, story=None, role="headline", z=20, importance=.5,
             outline=None, align="left", case="normal", flow=None, constraints=(), on=None):
        """One line of display type whose cap height starts at ``y_cap``."""
        face = self.kit.face(key)
        shown = text.upper() if case == "upper" else text
        w = self.kit.width(shown, key, size) * 1.012 + .8
        st = self.kit.style(key, size, color, align=align, case=case)
        color = self.legible_colour(color, on, st)
        st.color = self.kit.color(color)
        if outline:
            st.outline_color, st.outline_width_pt = self.kit.color(outline[0]), outline[1]
        desc = DESC_EM
        if face.path:
            from .layered_rules import _glyph_bounds
            gb = _glyph_bounds(face.path)
            lows = [b[1] for b in (gb(ch) for ch in shown if not ch.isspace()) if b]
            desc = max(.04, -min(lows) + .03) if lows else DESC_EM  # frame ends under the real ink
        el = Element(id=self._id(role), role=role, text_content=text, importance=importance, z=z, style=st,
                     frame=Frame(x=x, y=y_cap - (TOP_EM - face.cap) * size * PT, w=w, h=(TOP_EM + desc) * size * PT),
                     story_ref=getattr(story, "id", None), flow_group=flow,
                     constraints=["label", "display_line", *constraints], content_revision_ref="source")
        return self.add(el)

    def copy(self, text, key, size, x, y, w, h, color, *, story=None, role="body", z=20, bg=None, inset=None,
             page_ref=None, align="justify", min_size=None, max_size=None, on=None):
        """Running copy fitted to a frame the layout fixed.

        The frame never grows: the text is shortened at sentence boundaries
        (source mode) and, if still too long, set down to ``min_size``.
        The page reference is appended and never cut.
        """
        from .copyfit import estimate_text_capacity
        from .fonts import style_face_args
        st = self.kit.style(key, size, color, align=align)
        st.color = self.kit.color(self.legible_colour(color, bg or on, st))
        st.line_height_pt = round(size * 1.12, 2)
        if bg:
            st.bg_color = self.kit.color(bg)
        if inset:
            st.inset_mm = inset
        tail = f" {page_ref}" if page_ref else ""
        sentences = [s for s in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if s]
        iw = w - ((inset or [0, 0, 0, 0])[1] + (inset or [0, 0, 0, 0])[3])
        ih = h - ((inset or [0, 0, 0, 0])[0] + (inset or [0, 0, 0, 0])[2])

        def fits(t, s):
            return estimate_text_capacity(t, iw, ih, 1, s, s * 1.12, font_family=st.font_family, tracking_em=st.tracking_em or 0.0,
                                          face_args=style_face_args(st)).passes

        def ratio(t, s):
            r = estimate_text_capacity(t, iw, ih, 1, s, s * 1.12, font_family=st.font_family, tracking_em=st.tracking_em or 0.0,
                                       face_args=style_face_args(st))
            return r.estimated_lines / max(1, r.capacity_lines)

        chosen, size_used = None, size
        for s in [size, *( [round(size - .3 * k, 2) for k in range(1, 6)] if min_size else [])]:
            if min_size and s < min_size:
                break
            for n in range(len(sentences), 0, -1):
                candidate = " ".join(sentences[:n]) + tail
                if fits(candidate, s):
                    chosen, size_used = candidate, s
                    break
            if chosen and ratio(chosen, s) >= .80:
                break
        if chosen is None:
            chosen = (sentences[0] if sentences else "") + tail
            self.out.decisions.append({"decision": "copy_overset", "story_ref": getattr(story, "id", None)})
        # Short copy: the type grows (within the kit's range) until the
        # frame is full, instead of leaving a hole at the bottom.
        if max_size and chosen and ratio(chosen, size_used) < .9:
            s = size_used
            while s + .1 <= max_size and fits(chosen, s + .1):
                s = round(s + .1, 2)
            size_used = s
        st.font_size_pt, st.line_height_pt = size_used, round(size_used * 1.12, 2)
        kept = len(chosen) - len(tail)
        if kept < len((text or "").strip()) - 2:
            self.out.decisions.append({"decision": "copy_shortened", "story_ref": getattr(story, "id", None),
                                       "kept_chars": kept, "source_chars": len((text or "").strip())})
        if not bg and not inset and chosen:
            # plain copy: the frame is as tall as the set text, so the empty
            # foot of a module is measured as what it is (a hole, D28/U15)
            r = estimate_text_capacity(chosen, iw, ih, 1, size_used, size_used * 1.12, font_family=st.font_family,
                                       tracking_em=st.tracking_em or 0.0, face_args=style_face_args(st))
            used = r.estimated_lines * size_used * 1.12 * 0.3528 + 1.0
            if r.passes and used < h - 3.0:
                h = used
        el = Element(id=self._id(role), role=role, text_content=chosen, z=z, style=st, importance=.4,
                     frame=Frame(x=x, y=y, w=w, h=h), story_ref=getattr(story, "id", None),
                     content_revision_ref="source")
        return self.add(el)

    def photo(self, image, x, y, w, h, *, story=None, cutout=False, z=10, crop=None, importance=.6, module=None):
        """Place a photo.  A cut-out is finished like a retoucher's (smooth
        path inside the hair line, decontaminated rim, 0.1–0.2 mm feather;
        ``cutout_quality.refine_cutout``).  With ``module`` (x0, y0, x1, y1)
        the straight cut edges of the source frame must lie on the module's
        edge or beyond the trim (U7/D09): the photo is snapped there when one
        move does it, otherwise it becomes a framed photo clipped to the
        module, and the decision is recorded."""
        if cutout and image.alpha_mask_url and module is not None:
            from .cutout_quality import cut_segments
            segs = cut_segments(image.alpha_mask_url, crop)
            x, y, ok = self._snap_cut_edges(segs, x, y, w, h, module)
            sides = {k: round(v[1] - v[0], 3) for k, v in segs.items()}
            if not ok:
                self.out.decisions.append({"decision": "cutout_rejected", "story_ref": getattr(story, "id", None),
                                           "image": image.id, "reason": "cut_edge_in_field", "sides": sides})
                mx0, my0, mx1, my1 = module
                fx0, fy0, fx1, fy1 = max(x, mx0), max(y, my0), min(x + w, mx1), min(y + h, my1)
                c0 = crop or [0, 0, 1, 1]
                cw, ch = c0[2] - c0[0], c0[3] - c0[1]
                crop = [c0[0] + (fx0 - x) / w * cw, c0[1] + (fy0 - y) / h * ch,
                        c0[0] + (fx1 - x) / w * cw, c0[1] + (fy1 - y) / h * ch]
                x, y, w, h, cutout = fx0, fy0, fx1 - fx0, fy1 - fy0, False
        el = Element(id=self._id("photo"), role="photo", frame=Frame(x=x, y=y, w=w, h=h), z=z,
                     image_url=image.url, treatment="cutout" if cutout else "crop",
                     mask_ref=image.alpha_mask_url if cutout else None, crop_box=crop or [0, 0, 1, 1],
                     story_ref=getattr(story, "id", None), importance=importance,
                     source_width_px=image.width_px, source_height_px=image.height_px,
                     focal_point=image.focal_point)
        self.add(el)
        crop = crop or [0, 0, 1, 1]
        cw, ch = crop[2] - crop[0], crop[3] - crop[1]
        faces, full = [], []
        for fb in ((image.photo_analysis or {}).get("faces") or []):
            u0, v0 = (fb[0] - crop[0]) / cw, (fb[1] - crop[1]) / ch
            u1, v1 = (fb[2] - crop[0]) / cw, (fb[3] - crop[1]) / ch
            if u1 <= 0 or v1 <= 0 or u0 >= 1 or v0 >= 1:
                continue
            faces.append([x + max(0, u0) * w, y + max(0, v0) * h, x + min(1, u1) * w, y + min(1, v1) * h])
            full.append([x + u0 * w, y + v0 * h, x + u1 * w, y + v1 * h])
        self.out.faces[el.id] = faces
        self.out.faces_full[el.id] = full
        if cutout and image.alpha_mask_url:
            from .cutout_quality import refine_cutout
            from .image_ops import extract_alpha_rings
            try:
                mask_path = refine_cutout(image.alpha_mask_url, source_path=image.url)
            except Exception as exc:  # never silently: the raw mask is still a valid cut
                mask_path = image.alpha_mask_url
                self.out.decisions.append({"decision": "cutout_refine_failed", "image": image.id, "error": str(exc)[:160]})
            el.mask_ref = mask_path
            self.out.masks[el.id] = mask_path
            if crop != [0, 0, 1, 1]:
                # the clip contour must be traced on the same crop the renderer draws
                import hashlib
                from PIL import Image
                key = hashlib.sha1(f"{mask_path}{crop}".encode()).hexdigest()[:10]
                cropped = Path(mask_path).with_name(f"{Path(mask_path).stem}.crop-{key}.png")
                if not cropped.exists():
                    with Image.open(mask_path) as im:
                        W, H = im.size
                        im.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H))).save(cropped)
                mask_path = str(cropped)
            # Generous threshold: the clip follows hair, the alpha does the rest.
            rings = extract_alpha_rings(mask_path, w, h, threshold=40, tolerance_mm=.35)
            if rings:
                el.contour_points = rings[0]["outer"]
                el.contour_holes = rings[0].get("holes") or None
        return el

    # ------------------------------------------------ general photo primitives
    def photo_fill(self, image, rect, *, story=None, z=10, face_target=(.5, .35), scale=1.0, importance=.6,
                   min_face_mm: float = 14.0):
        """Rulebook U16: a photo fills its module edge to edge with its own
        background (cover-crop, never letterboxed, never a figure on white).
        The face is placed at ``face_target`` (fractions of the module);
        ``scale`` > 1 zooms in.  Returns (element, full image frame)."""
        x0, y0, x1, y1 = rect
        W, H = x1 - x0, y1 - y0
        aspect = (image.width_px or 1) / (image.height_px or 1)
        h = max(H, W / aspect) * max(1.0, scale)
        w = h * aspect
        faces = (image.photo_analysis or {}).get("faces") or []
        if faces:
            f = faces[0]
            fcx, fcy = (f[0] + f[2]) / 2, (f[1] + f[3]) / 2
            # U6: a face in print is at least ~12 mm — zoom the crop in
            face_h = (f[3] - f[1]) * h
            if 0 < face_h < min_face_mm:
                h *= min_face_mm / face_h
                w = h * aspect
        else:
            fcx, fcy = (image.focal_point or [.5, .4])
        fx = min(x0, max(x1 - w, x0 + face_target[0] * W - fcx * w))
        fy = min(y0, max(y1 - h, y0 + face_target[1] * H - fcy * h))
        crop = [(x0 - fx) / w, (y0 - fy) / h, (x1 - fx) / w, (y1 - fy) / h]
        el = self.photo(image, x0, y0, W, H, story=story, z=z, crop=crop, importance=importance)
        el.constraints = [*(el.constraints or []), "fills_module"]
        return el, (fx, fy, w, h)

    def breakout(self, image, full, region, *, backing=None, story=None, z=20, importance=.7):
        """Rulebook U17: partial cut-out.  The same image at the same geometry,
        cut out only inside ``region`` — the part of the figure that leaves
        its module (a head over the masthead).  Inside the module the
        rectangular photo (``backing``) shows the identical pixels, so the
        breakout's straight crop edges are invisible."""
        fx, fy, w, h = full
        rx0, ry0 = max(region[0], fx), max(region[1], fy)
        rx1, ry1 = min(region[2], fx + w), min(region[3], fy + h)
        if rx1 - rx0 < 1 or ry1 - ry0 < 1:
            return None
        crop = [(rx0 - fx) / w, (ry0 - fy) / h, (rx1 - fx) / w, (ry1 - fy) / h]
        el = self.photo(image, rx0, ry0, rx1 - rx0, ry1 - ry0, story=story, cutout=True, z=z, crop=crop,
                        importance=importance)
        if backing is not None:
            el.constraints = [*(el.constraints or []), f"backed_by:{backing.id}"]
        return el

    def fade(self, el, **sides_mm):
        """Rulebook U18: a smooth transition — the photo dissolves into what
        lies beneath (an apla) over N mm on the given sides (left/right/top/
        bottom), instead of a hard edge or a white gap."""
        spec = ",".join(f"{k}={float(v):.1f}" for k, v in sides_mm.items() if v)
        if spec:
            el.constraints = [*(el.constraints or []), f"fade:{spec}"]
        return el

    def fill_block(self, text: str, key: str, width: float, height: float, *, max_lines: int = 5,
                   max_pt: float = 400.0, min_gap: float = 1.2, case_upper: bool = False):
        """Rulebook U16/U5: the breaking that lets a headline fill its box with
        the largest type (width- and height-limited), avoiding a preposition
        or conjunction at a line end.  Returns (lines, size)."""
        words = (text.upper() if case_upper else text).split()
        dangling = {"i", "w", "z", "na", "do", "o", "a", "u", "za", "po", "od", "bo", "że", "dla", "się", "nie"}
        best = None
        for n in range(1, min(max_lines, len(words)) + 1):
            for cuts in itertools.combinations(range(1, len(words)), n - 1):
                b = [0, *cuts, len(words)]
                lines = [" ".join(words[b[i]:b[i + 1]]) for i in range(n)]
                size = min(max_pt, min(width / max(1e-6, self.kit.width(l, key, 1.0)) for l in lines))
                size = self.fit_block(lines, key, size, height, min_gap)
                pen = sum(1 for l in lines[:-1] if l.split()[-1].lower() in dangling) * .12
                score = size * (1 - pen)
                if best is None or score > best[0]:
                    best = (score, lines, size)
        return best[1], best[2]

    def snap_near_edges(self, lo: float = .3, hi: float = 2.5):
        """Rulebook U9/D29: plates whose parallel edges almost meet are snapped
        onto the larger plate's edge — no paper sliver, no step."""
        plates = [e for e in self.out.elements if e.role == "band" and not e.frame.rotation_deg
                  and not getattr(e.frame, "skew_y_deg", 0) and e.shape in (None, "rect")]
        for a in plates:
            for b in plates:
                if a is b or a.frame.w * a.frame.h > b.frame.w * b.frame.h:
                    continue                          # move the smaller plate (a)
                fa, fb = a.frame, b.frame
                if min(fa.y + fa.h, fb.y + fb.h) - max(fa.y, fb.y) >= 3:
                    for ea in ("l", "r"):
                        xa = fa.x if ea == "l" else fa.x + fa.w
                        for xb in (fb.x, fb.x + fb.w):
                            if lo < abs(xa - xb) < hi:
                                if ea == "l":
                                    fa.w += fa.x - xb; fa.x = xb
                                else:
                                    fa.w = xb - fa.x
                                break
                if min(fa.x + fa.w, fb.x + fb.w) - max(fa.x, fb.x) >= 3:
                    for ea in ("t", "b"):
                        ya = fa.y if ea == "t" else fa.y + fa.h
                        for yb in (fb.y, fb.y + fb.h):
                            if lo < abs(ya - yb) < hi:
                                if ea == "t":
                                    fa.h += fa.y - yb; fa.y = yb
                                else:
                                    fa.h = yb - fa.y
                                break

    def _snap_cut_edges(self, segs, x, y, w, h, module, tol=1.0):
        mx0, my0, mx1, my1 = module
        L, T, R, B = -self.bleed + .01, -self.bleed + .01, self.trim_w + self.bleed - .01, self.trim_h + self.bleed - .01

        def visible_len(side, x, y):
            a0, a1 = segs[side]
            if side in ("left", "right"):
                pos = x if side == "left" else x + w
                if pos <= 0 or pos >= self.trim_w:
                    return 0.0
                lo, hi = y + a0 * h, y + a1 * h
                return max(0.0, min(hi, self.trim_h) - max(lo, 0.0))
            pos = y if side == "top" else y + h
            if pos <= 0 or pos >= self.trim_h:
                return 0.0
            lo, hi = x + a0 * w, x + a1 * w
            return max(0.0, min(hi, self.trim_w) - max(lo, 0.0))

        def on_edge(side, x, y):
            if visible_len(side, x, y) <= 1.0:
                return True
            if side == "left":
                return abs(x - mx0) <= tol or x <= L
            if side == "right":
                return abs(x + w - mx1) <= tol or x + w >= R
            if side == "top":
                return abs(y - my0) <= tol or y <= T
            return abs(y + h - my1) <= tol or y + h >= B
        # the nearest placement where every visible straight cut lies on the
        # module edge or the bleed (corners that fall off the page do not count)
        cands = sorted(((nx, ny) for nx in (x, mx0, mx1 - w) for ny in (y, my0, my1 - h)),
                       key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        for nx, ny in cands:
            if all(on_edge(sd, nx, ny) for sd in segs):
                return nx, ny, True
        return x, y, False

    def ink_ext(self, text: str, key: str, size: float) -> tuple[float, float]:
        """(mm of accents above the cap line, mm of descenders below the baseline)."""
        face = self.kit.face(key)
        if not face.path:
            return .18 * size * PT, .2 * size * PT
        from .layered_rules import _glyph_bounds
        gb = _glyph_bounds(face.path)
        bs = [b for b in (gb(ch) for ch in text if not ch.isspace()) if b]
        if not bs:
            return 0.0, 0.0
        return (max(0.0, max(b[3] for b in bs) - face.cap) * size * PT, max(0.0, -min(b[1] for b in bs)) * size * PT)

    def block(self, lines: list[str], key: str, size: float, min_gap: float = .8) -> tuple[list[float], float]:
        """Cap-line offsets of stacked lines (glyphs never touch) and the
        block's full ink height, accents and descenders included."""
        cap = self.kit.face(key).cap * size * PT
        offs, y = [], self.ink_ext(lines[0], key, size)[0]
        for i, line in enumerate(lines):
            if i:
                y += cap + self.ink_ext(lines[i - 1], key, size)[1] + self.ink_ext(line, key, size)[0] + min_gap
            offs.append(y)
        return offs, y + cap + self.ink_ext(lines[-1], key, size)[1]

    def fit_block(self, lines: list[str], key: str, size: float, height: float, min_gap: float = .8) -> float:
        for _ in range(4):
            _, h = self.block(lines, key, size, min_gap)
            if h <= height + .01:
                break
            size *= height / h
        return size

    def rotate_group(self, elements: list[Element], deg: float, pivot: tuple[float, float]):
        for el in elements:
            f = el.frame
            cx, cy = rotate_about(f.x + f.w / 2, f.y + f.h / 2, *pivot, deg)
            f.x, f.y, f.rotation_deg = cx - f.w / 2, cy - f.h / 2, round(deg, 2)

    # -- display headline set as a stack, word by word
    def stack(self, story, words: list[str], emphasis: set[str], key, x0, y0, width_at, y_max, *,
              base="ink", accent="red", max_lines=5, max_pt=260.0, min_pt=24.0, gap_em=.07, outline=None,
              case="upper", importance=.97, flow=None, z=22, aside: Optional[tuple[float, float]] = None,
              aside_y_max: Optional[float] = None, aside_poly=None):
        """Break the headline into lines, each scaled to fill the width
        available at its height (``width_at(y0, y1)``), packing the lines to
        fill the height.  Emphasised words take the accent colour.

        ``aside`` = (min width mm, area mm²) of a paragraph that must sit in
        the free space the stack leaves (beside short lines or below the
        stack).  The breaking is chosen so that stack + paragraph fill the
        column; the chosen paragraph region is stored in ``self.aside``.
        """
        face = self.kit.face(key)
        shown = [w.upper() if case == "upper" else w for w in words]
        band = lambda a, b: width_at(a, b) if isinstance(width_at(a, b), tuple) else (x0, x0 + width_at(a, b))
        col_l, col_r = band(y0, y0 + 1)
        col_w = col_r - col_l
        slices = 24
        dy = (y_max - y0) / slices
        col_area = sum(max(0.0, band(y0 + i * dy, y0 + (i + 1) * dy)[1] - band(y0 + i * dy, y0 + (i + 1) * dy)[0])
                       for i in range(slices)) * dy or col_w * (y_max - y0)
        best = None
        n = len(words)
        from .layered_rules import _glyph_bounds
        gb = _glyph_bounds(face.path) if face.path else None

        def ink_ext(text: str, size: float) -> tuple[float, float]:
            """(mm above the cap line, mm below the baseline) for accents/ogonki."""
            if not gb:
                return .18 * size * PT, .2 * size * PT
            bs = [gb(ch) for ch in text if not ch.isspace()]
            bs = [b for b in bs if b]
            if not bs:
                return 0.0, 0.0
            return (max(0.0, max(b[3] for b in bs) - face.cap) * size * PT,
                    max(0.0, -min(b[1] for b in bs)) * size * PT)

        def tops(lines, sizes):
            """Cap-line y of every line: glyphs of neighbours never touch."""
            ys, y = [], y0 + ink_ext(" ".join(lines[0]), sizes[0])[0]  # y0 = top of the ink
            for i, (line, size) in enumerate(zip(lines, sizes)):
                if i:
                    prev, psize = " ".join(lines[i - 1]), sizes[i - 1]
                    y += face.cap * psize * PT + ink_ext(prev, psize)[1] + ink_ext(" ".join(line), size)[0] \
                        + max(.8, gap_em * psize * PT)
                ys.append(y)
            last = " ".join(lines[-1])
            return ys, y + face.cap * sizes[-1] * PT + ink_ext(last, sizes[-1])[1]

        step = lambda size: face.cap * size * PT + gap_em * size * PT * 2.2
        a_ymax = min(y_max, aside_y_max or y_max)
        combos = []
        for k in range(1, min(max_lines, n) + 1):
            for cuts in itertools.combinations(range(1, n), k - 1):
                for aside_at in ([None, *range(k)] if aside else [None]):
                    combos.append((k, cuts, aside_at))
        for k, cuts, aside_at in combos:
                bounds = [0, *cuts, n]
                lines = [shown[bounds[i]:bounds[i + 1]] for i in range(k)]
                if any(len(l) > 3 for l in lines):
                    continue
                y, sizes, widths, ok = y0, [], [], True
                for li, line in enumerate(lines):
                    unit = self.kit.width(" ".join(line), key, 100.0) / 100.0  # mm per pt
                    size = max_pt
                    for _ in range(4):
                        # the frame adds 1.2 % + 0.8 mm of slack to the measured width
                        bl, br = band(y, y + face.cap * size * PT)
                        if li == aside_at:
                            br -= aside[0] + 7.0  # this line makes room for the paragraph
                        avail = (br - bl) / 1.012 - 1.0
                        size = min(max_pt, avail / max(1e-6, unit))
                    if size < min_pt:
                        ok = False
                        break
                    sizes.append(size)
                    y += step(size)
                if not ok:
                    continue
                for _ in range(3):
                    ys, bottom_y = tops(lines, sizes)
                    if bottom_y <= y_max + .01:
                        break
                    scale = (y_max - y0) / (bottom_y - y0)
                    sizes = [s * scale for s in sizes]
                # Final positions differ from the ones the widths were measured
                # at (uniform shrink, accent room): settle every line where it
                # actually lands, before the candidate is scored.
                sizes = list(sizes)
                for _ in range(4):
                    changed = False
                    for i2, (ln, yy2) in enumerate(zip(lines, tops(lines, sizes)[0])):
                        tx = " ".join(ln)
                        up2, down2 = ink_ext(tx, sizes[i2])
                        bl2, br2 = band(yy2 - up2, yy2 + face.cap * sizes[i2] * PT + down2)
                        if li_aside := (i2 == aside_at and aside):
                            br2 -= aside[0] + 7.0
                        fit = ((br2 - bl2) / 1.012 - 1.0) / max(1e-6, self.kit.width(tx, key, 1.0))
                        if fit < sizes[i2] - .05:
                            sizes[i2] = fit
                            changed = True
                    if not changed:
                        break
                if min(sizes) < min_pt or tops(lines, sizes)[1] > y_max + .5:
                    continue
                ys, bottom_y = tops(lines, sizes)
                # geometry of the result: (cap top incl. accents, baseline, width)
                rows = []  # (ink top, ink bottom, ink left, ink right, band right)
                for line, size, yy in zip(lines, sizes, ys):
                    text = " ".join(line)
                    w = self.kit.width(text, key, size)
                    bl, br = band(yy, yy + face.cap * size * PT)
                    up, down = ink_ext(text, size)
                    rows.append((yy - up, yy + face.cap * size * PT + down, bl, bl + w, br))
                ink = sum((r[1] - r[0]) * (r[3] - r[2]) for r in rows)
                region, region_area = None, 0.0
                if aside:
                    need_w, need_a = aside
                    cands = []
                    # free space beside consecutive lines ...
                    for i in range(len(rows)):
                        for j in range(i, len(rows)):
                            x_a = max(r[3] for r in rows[i:j + 1]) + 7.0
                            x_b = min(r[4] for r in rows[i:j + 1])
                            top_y = rows[i][0]
                            bot_y = min(a_ymax, rows[j + 1][0] - 2 if j + 1 < len(rows) else y_max)
                            if x_b - x_a >= need_w and bot_y - top_y > 8:
                                cands.append((x_a, top_y, x_b - x_a, bot_y - top_y))
                    # ... or below the stack
                    bl, br = band(rows[-1][1] + 6, a_ymax)
                    if a_ymax - (rows[-1][1] + 6) > 18 and br - bl >= need_w:
                        cands.append((bl, rows[-1][1] + 6, br - bl, a_ymax - (rows[-1][1] + 6)))
                    for cand in cands:
                        cand = _fit_rect(cand, aside_poly, need_w) if aside_poly is not None else cand
                        if cand and cand[2] * cand[3] > region_area:
                            region, region_area = cand, cand[2] * cand[3]
                    used_a = min(region_area, need_a)
                    fill = (ink + used_a) / col_area
                    short = max(0.0, need_a - region_area) / need_a
                    low = ((region[1] + region[3] / 2) - y0) / (y_max - y0) if region else 0.0
                    score = fill * 3.0 - 1.5 * short + .5 * low
                else:
                    fill = ink / col_area
                    score = fill * 3.0
                spread = max(sizes) / min(sizes)
                lonely = sum(1 for l in lines if len(l) == 1 and len(l[0]) <= 2)
                if emphasis:
                    # the biggest line carries a stressed word (NR20–22: NAS, DASZ, NIE)
                    big = max(range(len(lines)), key=lambda i: sizes[i])
                    if not any(_norm(wd) in emphasis for wd in lines[big]):
                        score -= .8
                score += -.5 * max(0, spread - 2.0) - .3 * lonely + .15 * (sum(sizes) / len(sizes)) / max_pt
                if self.genes.get("debug_stack"):
                    print("STACK", round(score, 3), [" ".join(l) for l in lines], [round(z) for z in sizes],
                          "region", [round(v) for v in region] if region else None, "fill", round(fill, 3))
                if best is None or score > best[0]:
                    best = (score, lines, sizes, region)
        if not best:
            self.out.missing.append(f"{story.id}.headline")
            return []
        _, lines, sizes, self.aside = best
        out = []
        for line, size, y in zip(lines, sizes, tops(lines, sizes)[0]):
            x = band(y, y + face.cap * size * PT)[0]
            runs: list[tuple[str, str]] = []
            for word in line:
                colour = accent if _norm(word) in emphasis else base
                if runs and runs[-1][1] == colour:
                    runs[-1] = (runs[-1][0] + " " + word, colour)
                else:
                    runs.append((word, colour))
            space = self.kit.width(" ", key, size)
            for text, colour in runs:
                el = self.line(text, key, size, x, y, colour, story=story, importance=importance, outline=outline,
                               case="normal", flow=flow or f"stack-{story.id}", z=z)
                out.append(el)
                x += self.kit.width(text, key, size) + space
        if importance >= .95:
            out[0].constraints.append("must_dominate")
        return out


def _fit_rect(rect, poly, min_w: float):
    """Shrink (x, y, w, h) from the bottom, then from the right, until it lies
    inside ``poly``; None if it cannot keep ``min_w`` x 12 mm."""
    from shapely.geometry import box as sbox
    x, y, w, h = rect
    while h >= 12:
        ww = w
        while ww >= min_w:
            if poly.contains(sbox(x, y, x + ww, y + h)):
                return (x, y, ww, h)
            ww -= 2.0
        h -= 2.0
    return None


def _norm(word: str) -> str:
    return re.sub(r"[^\wąćęłńóśźż]", "", word.lower())


# ---------------------------------------------------------------- building
def compose_layered_cover(material, *, kit_name: str = "wukadka", genes: Optional[dict[str, Any]] = None) -> SceneGraph:
    kit = Kit(kit_name)
    genes = {"lead_rotation_deg": None, "skybox_order": "interview_first", "bottom": "strip", **(genes or {})}
    c = LayeredCover(kit, material, genes)
    pal, frame = kit.pal, kit.frame
    stories = list(material.stories)
    lead = next(s for s in stories if s.rank == "lead")
    hero = next((s for s in stories if s.rank == "second" and s.images and s.images[0].alpha_mask_url), None)
    interview = next((s for s in stories if s.group == "interview"), None)
    promo = next((s for s in stories if s.group == "promo"), None)
    teasers = [s for s in stories if s.rank == "teaser" and s not in (interview, promo)]
    sky_other = next((s for s in teasers if s.pin_zone == "top"), teasers[0] if teasers else None)
    bottom = next((s for s in teasers if s is not sky_other), None)

    # 1. brand frame -----------------------------------------------------
    p = frame["panel"]
    panel_el = c.plate(p["x"], p["y"], p["w"], p["bottom"] - p["y"], p["color"], z=1)
    lg = frame["logo"]
    logo = c.add(Element(id="logo", role="logo", frame=Frame(x=lg["x"], y=lg["y"], w=lg["w"], h=lg["h"]), z=4,
                         image_url=str(Path(kit.data["_root"]) / lg["asset"]), importance=.9, constraints=["brand"]))
    d = frame["dateline"]
    c.plate(d["x"], d["y"], d["w"], d["h"], "white", z=12)
    values = {"issue_number": material.issue_number or "", "issue_date": material.issue_date or ""}
    cap_y = d["y"] + (d["h"] - kit.face("info").cap * d["size_pt"] * PT) / 2
    left = d["left"].format(**values)
    c.line(left, "info", d["size_pt"], d["x"] + 3, cap_y, "ink", role="folio", z=13, on="white")
    centre_w = kit.width(d["center"], "info", d["size_pt"])
    c.line(d["center"], "info", d["size_pt"], d["x"] + d["w"] * .52 - centre_w / 2, cap_y, "ink", role="folio", z=13)
    right_w = kit.width(d["right"], "info", d["size_pt"])
    c.line(d["right"], "info", d["size_pt"], d["x"] + d["w"] - 3 - right_w, cap_y, "red", role="folio", z=13, on="white")
    card = frame["card"]
    card_el = c.plate(card["inset_left"], card["top"], p["x"] + p["w"] - card["inset_left"], card["bottom"] - card["top"],
                      card["color"], z=2)
    c.line(d["sub"], "info", 5.0, d["x"] + 2, card["top"] + 1.4, "ink", role="folio", z=5)

    # 2. skybox ------------------------------------------------------------
    sb = frame["skybox"]
    slot_w = (c.trim_w - c.L - sb["gap"]) / 2
    slots = [(c.L, slot_w), (c.L + slot_w + sb["gap"], c.trim_w + c.bleed - (c.L + slot_w + sb["gap"]))]
    order = [interview, sky_other] if genes["skybox_order"] == "interview_first" else [sky_other, interview]
    for (sx, sw), story in zip(slots, order):
        if story is None:
            continue
        if story is interview:
            _interview_box(c, story, sx, sb["y"], min(sw, c.R - sx), sb["h"])
        else:
            _dark_caps_box(c, story, sx, sb["y"], sw, sb["h"])

    # 3. bottom teaser first: its cut-out head is an obstacle for the hero copy and the lead
    bottom_head = None
    hero_floor = None
    if bottom and genes.get("bottom") == "corner":
        hero_floor = _bottom_corner(c, bottom)
    elif bottom:
        _bottom_strip(c, bottom)
        heads = [e for e in c.out.elements if e.role == "photo" and e.story_ref == bottom.id]
        if heads and hero_floor is None:
            hf = heads[0].frame
            sil = Silhouette(c.out.masks[heads[0].id], hf, heads[0].crop_box) if heads[0].id in c.out.masks else None
            bottom_head = (hf, sil)

    # 4. hero cut-out (second story) --------------------------------------
    hero_x = c.R
    hero_info = None
    if hero:
        hero_info = _place_hero(c, hero, logo, obstacle=bottom_head, floor=hero_floor)
        hero_x = hero_info["x"]

    # 5. lead stack on the paper card ------------------------------------
    # The lead is composed in its own rotated frame (the kit measured 8.8–9°
    # on NR20–NR22).  Free space = card minus the hero, its type and the
    # bottom teaser, rotated into that frame, so the slanted block fills
    # the diagonal room instead of being rotated after the fact.
    from shapely import affinity
    from shapely.geometry import LineString, Polygon as SPoly, box as sbox
    from shapely.ops import unary_union
    from .critic import _frame_polygon
    lo_r, hi_r = kit.g["lead_rotation_deg"]
    rot = float(genes.get("lead_rotation_deg") if genes.get("lead_rotation_deg") is not None else (lo_r + hi_r) / 2)
    lead_left = card["inset_left"] + 4.0
    lead_top = card["top"] + 3.0
    lead_bottom = c.B - 4.0 if hero_floor is not None else card["bottom"] - 3.0
    right_cap = c.R if hero else p["x"] + p["w"] - 3.0
    blockers = []
    for e in c.out.elements:
        if e.story_ref and e.story_ref in {getattr(hero, "id", None), getattr(bottom, "id", None)}:
            if e.role == "photo" and e.contour_points:
                sil_poly = SPoly([(e.frame.x + x, e.frame.y + y) for x, y in e.contour_points]).buffer(0)
                faces_here = c.out.faces.get(e.id) or []
                if genes.get("lead_over_hero", True) and faces_here and e.story_ref == getattr(hero, "id", None):
                    # Tabloid layering: the lead may run in front of the
                    # hero's body, never over the head or face.
                    head_bottom = max(f[3] for f in faces_here) + 6.0
                    blockers.append(sil_poly.intersection(sbox(-50, -50, 400, head_bottom)).buffer(3.0))
                    for f in faces_here:
                        blockers.append(sbox(*f).buffer(6.0))
                else:
                    blockers.append(sil_poly.buffer(4.0))
            else:
                blockers.append(SPoly(_frame_polygon(e.frame, e.shape)).buffer(4.0))
    region = sbox(lead_left, lead_top, right_cap, lead_bottom)
    if blockers:
        region = region.difference(unary_union(blockers))
    card_region = sbox(card["inset_left"] + 3, card["top"] + 3, p["x"] + p["w"] - 3,
                       (c.B - 2.0 if hero_floor is not None else card["bottom"] - 3)).intersection(region)
    pivot = (lead_left, lead_top)
    local = affinity.rotate(region, -rot, origin=pivot)
    local_card = affinity.rotate(card_region, -rot, origin=pivot)
    lx0, ly0, lx1, ly1 = local.bounds

    def raw_band(y0, y1):
        lo, hi = -1e9, 1e9
        for yy in (y0, (y0 + y1) / 2, y1):
            seg = LineString([(lx0 - 10, yy), (lx1 + 10, yy)]).intersection(local)
            pieces = [g for g in getattr(seg, "geoms", [seg]) if not g.is_empty and g.length > 0]
            if not pieces:
                return (pivot[0], pivot[0])
            best = max(pieces, key=lambda g: g.length)
            lo, hi = max(lo, best.bounds[0]), min(hi, best.bounds[2])
        return (lo, hi) if hi > lo else (lo, lo)

    # Lines share one left edge in the rotated frame (a straight slanted
    # margin, as on the printed covers), not a staircase.
    # the margin follows the card's left edge (not the gaps around other stories)
    ends = [rotate_about(lead_left, yy, *pivot, -rot) for yy in (lead_top, lead_bottom)]
    common_left = max(x for x, _ in ends)

    def lead_band(y0, y1):
        """Lines start at the common margin and run right until the first
        obstacle anywhere in the band's height (never jump past one)."""
        hi = 1e9
        n = max(6, int((y1 - y0) / 1.5))
        for k in range(n + 1):
            yy = y0 + (y1 - y0) * k / n
            seg = LineString([(lx0 - 10, yy), (lx1 + 10, yy)]).intersection(local)
            pieces = [g for g in getattr(seg, "geoms", [seg]) if not g.is_empty and g.length > 0]
            here = [g for g in pieces if g.bounds[0] <= common_left + .5 <= g.bounds[2]]
            if not here:
                return (common_left, common_left)
            hi = min(hi, here[0].bounds[2])
        return (common_left, hi)

    # first local line that is wide enough (the top-right of the card is cut by the slant)
    top = ly0 + 2.0
    lead_els: list[Element] = []
    if lead.kicker:
        kick_lines = _balanced(lead.kicker.upper().split(), 2) if len(lead.kicker) > 22 else [lead.kicker.upper()]
        ky = top + 1.6
        widest = max(lead_band(yy, yy + 2)[1] - common_left for yy in [ly0 + 4 + 4 * k for k in range(20)])
        ksize = min(44.0, min(widest * .7 / max(1e-6, kit.width(l, "display", 1.0)) for l in kick_lines))
        for line in kick_lines:
            size = ksize
            h = kit.face("display").cap * size * PT
            need_w = kit.width(line, "display", size) + 5.0
            while lead_band(ky - 1.6, ky + h + 1.8)[1] - lead_band(ky - 1.6, ky + h + 1.8)[0] < need_w and ky < ly1 - 60:
                ky += 1.0  # the slant cuts the top corner: go down until the chip fits
            bl, br = lead_band(ky - 1.6, ky + h + 1.8)
            chip = c.plate(bl, ky - 1.6, kit.width(line, "display", size) + 4.5, h + 3.4, "red", z=21,
                           story=lead, role="band")
            lead_els.append(chip)
            lead_els.append(c.line(line, "display", size, bl + 2.2, ky, "white", story=lead, role="kicker", z=23,
                                   on="red"))
            ky += h + 4.2
        top = ky
    lead_text = lead.lead or lead.body
    lead_text = lead_text if lead_text and lead_text.strip() not in {"", "—"} else None
    emphasis = {_norm(w) for w in lead.headline_emphasis}
    body_pt = kit.g["body_size_pt"]
    need = None
    if lead_text:
        chars_w = kit.width(lead_text + " " + (lead.page_ref or ""), "body", body_pt)
        need = (46.0, chars_w * body_pt * 1.12 * PT * 1.08)
    # deepest local y the margin can reach (the slanted page bottom)
    from shapely.geometry import Point
    margin_bottom = top
    yy = top
    while yy < ly1:
        if local.buffer(.01).contains(Point(common_left + .6, yy)):
            margin_bottom = yy
        yy += 1.0
    stack = c.stack(lead, lead.headline.split(), emphasis, "display", lx0, top, lead_band,
                    margin_bottom - 1.0, flow=f"stack-{lead.id}", aside=need, aside_poly=local_card)
    lead_els += stack
    if lead_text and c.aside:
        rx, ry, rw, rh = c.aside
        lead_els.append(c.copy(lead_text, "body", body_pt, rx, ry, min(rw, 72.0), rh, "ink", story=lead, role="lead",
                               page_ref=lead.page_ref, min_size=7.4, max_size=10.5))
        c.out.decisions.append({"decision": "lead_paragraph_in_stack_gap", "region_mm": [round(v, 1) for v in c.aside]})
    if lead_els and abs(rot) > .1:
        c.rotate_group(lead_els, rot, pivot)
        c.out.decisions.append({"decision": "lead_rotation", "deg": rot})
    # The paper card is a plane the lead stands on: when the stack runs
    # deeper than the card, the card (and its blue rim) run to the trim
    # instead of an edge cutting through a line of type.
    from .layered_rules import _ink
    lowest = max((_ink(e).bounds[3] for e in lead_els if e.text_content), default=0.0)
    if lowest > card_el.frame.y + card_el.frame.h - 3.0:
        bottom_edge = c.trim_h + c.bleed
        card_el.frame.h = bottom_edge - card_el.frame.y
        panel_el.frame.h = bottom_edge - panel_el.frame.y
        c.out.decisions.append({"decision": "card_to_trim", "reason": "tytuł schodzi niżej niż karta"})

    # 6. promo roundel --------------------------------------------------------
    if promo:
        _place_roundel(c, promo, hero_info)


    # 7. every supplied image must be used or reported
    used = {e.image_url for e in c.out.elements if e.role == "photo"}
    for s in stories:
        for im in s.images:
            if im.url not in used:
                c.out.decisions.append({"decision": "image_not_used", "story_ref": s.id, "image": im.id})

    _ensure_legible(c)
    for sb in kit.substitutions:
        c.out.decisions.append({"decision": "font_substituted", **sb})
    for key, spec in kit.data["fonts"].items():
        if isinstance(spec, dict) and spec.get("substitute_for"):
            c.out.decisions.append({"decision": "font_substitute_in_kit", "role": key, "wanted": spec["substitute_for"],
                                    "used": kit.face(key).family})
    els = c.out.elements
    scene = SceneGraph(page=PageMeta(trim=[c.trim_w, c.trim_h], bleed_mm=c.bleed, safe_margin_mm=c.L,
                                     page_zone="front_page", page_role="cover"),
                       elements=els, reading_order=[e.id for e in sorted(els, key=lambda e: (e.frame.y, e.frame.x))],
                       metadata={"composition": "layered", "title_kit": kit_name, "genes": genes,
                                 "layout_mode": "layered_cover", "face_boxes": c.out.faces, "face_boxes_full": c.out.faces_full,
                                 "cutout_masks": c.out.masks, "photo_driven_decisions": c.out.decisions,
                                 "missing_content_refs": c.out.missing,
                                 "logo_rule": {"element": "logo", "max_covered_share": frame["logo"]["max_covered_share"]},
                                 "copy_mode": getattr(material, "copy_mode", "source")})
    return scene


def _balanced(words: list[str], n: int) -> list[str]:
    best = None
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        b = [0, *cuts, len(words)]
        lines = [" ".join(words[b[i]:b[i + 1]]) for i in range(n)]
        spread = max(map(len, lines)) - min(map(len, lines))
        if best is None or spread < best[0]:
            best = (spread, lines)
    return best[1] if best else [" ".join(words)]


def _fit_lines(c: LayeredCover, lines: list[str], key: str, width: float, max_pt: float) -> float:
    return min(max_pt, min(width / max(1e-6, c.kit.width(l, key, 1.0)) for l in lines))


def _interview_box(c: LayeredCover, story, x, y, w, h):
    """Interview skybox (NR21): the portrait is a rectangle filling the box
    height at its right edge, with its own background (U16) — not a cut-out
    standing in a corner; label, headline and lead fill the rest."""
    kit = c.kit
    c.plate(x, y, w, h, "yellow", z=3, story=story)
    img = story.images[0] if story.images else None
    text_l, text_r = x + 3, x + w - 3
    if img:
        aspect = (img.width_px or 1) / (img.height_px or 1)
        pw = min(w * .32, h * max(.62, aspect))
        c.photo_fill(img, (x + w - pw, y, x + w, y + h), story=story, z=6, face_target=(.5, .42))
        text_r = x + w - pw - 2.5
    label = kit.g["interview_label"]
    lsize = 15.0
    c.line(label[0], "label_italic", lsize, text_l, y + 3.2, "red", story=story, role="kicker", z=7, on="yellow")
    lw = kit.width(label[0], "label_italic", lsize)
    c.line(label[1], "display_italic", lsize * 1.35, text_l + lw + 1, y + 2.0, "panel", story=story, role="kicker", z=7,
           on="yellow")
    top = y + 3.2 + kit.face("display_italic").cap * lsize * 1.35 * PT + 2.5
    lead_h = 9.5 if story.lead else 0.0
    avail_h = y + h - lead_h - 1.5 - top
    lines, size = c.fill_block(story.headline, "deck_italic", text_r - text_l, avail_h, max_lines=3, max_pt=60.0,
                               min_gap=1.0)
    offs, _ = c.block(lines, "deck_italic", size, 1.0)
    for line, off in zip(lines, offs):
        c.line(line, "deck_italic", size, text_l, top + off, "teal", story=story, importance=.6, z=7, on="yellow")
    if story.lead:
        ly = y + h - lead_h - 1
        c.copy(story.lead, "body", 6.4, text_l, ly, text_r - text_l, lead_h, "ink", story=story,
               role="lead", page_ref=story.page_ref, z=7, min_size=5.8, max_size=7.6, align="left")


def _dark_caps_box(c: LayeredCover, story, x, y, w, h):
    kit = c.kit
    c.plate(x, y, w, h, "dark", z=3, story=story)
    img = story.images[0] if story.images else None
    text_r = x + w - 2
    if img:
        pw = w * .34
        c.photo_fill(img, (x + w - pw, y, x + w, y + h), story=story, z=4, face_target=(.5, .4))
        text_r = x + w - pw - 2
    lead_h = 10.0 if story.lead else 0
    lines, size = c.fill_block(story.headline, "display", text_r - x - 4, h - lead_h - 5, max_lines=4,
                               max_pt=90.0, case_upper=True)
    offs, _ = c.block(lines, "display", size, 1.2)
    for line, off in zip(lines, offs):
        c.line(line, "display", size, x + 3, y + 2.5 + off, "white", story=story, importance=.6, z=6, on="dark")
    if story.lead:
        c.copy(story.lead, "body", 6.4, x + 3, y + h - lead_h - 1, text_r - x - 4, lead_h, "white", story=story,
               role="lead", page_ref=story.page_ref, z=6, min_size=5.8, max_size=7.6, align="left")


def _place_hero(c: LayeredCover, story, logo: Element, obstacle=None, floor=None) -> dict[str, Any]:
    """Cut-out person at the right edge, as large and as high as the logo
    rule allows; headline, name chip and copy go on the body, below the face."""
    kit = c.kit
    img = story.images[0]
    an = img.photo_analysis or {}
    aspect = (img.width_px or 1) / (img.height_px or 1)
    bottom = kit.frame["panel"]["bottom"] if kit.frame.get("bottom") is None else kit.frame["bottom"]["y"] - 3
    if floor is not None:
        bottom = floor
    flush_right = (an.get("alpha_bbox") or [0, 0, 0, 0])[2] >= .985
    right = c.trim_w + c.bleed if flush_right else c.R
    sky_bottom = kit.frame["skybox"]["y"] + kit.frame["skybox"]["h"]
    lg = kit.frame["logo"]
    chosen = None
    for top in [sky_bottom + 3 + 2 * k for k in range(0, 40)]:
        h = bottom - top
        w = h * aspect
        if w > c.trim_w * .56:
            continue
        frame = Frame(x=right - w, y=top, w=w, h=h)
        sil = Silhouette(img.alpha_mask_url, frame)
        ext = sil.x_extent(lg["y"], lg["y"] + lg["h"])
        covered = 0.0 if not ext or ext[0] >= lg["x"] + lg["w"] else (lg["x"] + lg["w"] - ext[0]) / lg["w"]
        faces = an.get("faces") or []
        face_top = top + (faces[0][1] * h if faces else 0)
        clear_of_brand = True
        d = kit.frame["dateline"]
        for fb in faces:
            fx0, fy0, fx1, fy1 = frame.x + fb[0] * w, top + fb[1] * h, frame.x + fb[2] * w, top + fb[3] * h
            if fx0 < d["x"] + d["w"] and fy0 < d["y"] + d["h"] + 1 and fy1 > d["y"] - 1:
                clear_of_brand = False  # the dateline bar is drawn above the hero
        if covered <= lg["max_covered_share"] and face_top >= sky_bottom + 2 and clear_of_brand:
            chosen = (frame, sil, covered)
            break
    if chosen is None:
        c.out.missing.append(f"{story.id}.image")
        return {"x": c.R, "text_left": c.R}
    frame, sil, covered = chosen
    el = c.photo(img, frame.x, frame.y, frame.w, frame.h, story=story, cutout=True, z=8, importance=.8)
    c.out.decisions.append({"decision": "hero_cutout", "story_ref": story.id, "logo_covered": round(covered, 3),
                            "reason": "postać możliwie wysoko; zakrywa najwyżej dopuszczalną część winiety"})
    faces = c.out.faces.get(el.id) or []
    face_bottom = max((f[3] for f in faces), default=frame.y + frame.h * .35)
    # Text column on the body: from the silhouette's left edge (minus an
    # overhang onto the paper) to the live right edge.
    body_box_h = 40.0
    box_bottom = bottom
    if obstacle:
        hf, _ = obstacle
        if hf.x < c.R and hf.x + hf.w > c.R - 62:
            box_bottom = min(bottom, hf.y - 2.0)
    box_y = box_bottom - body_box_h
    ext = sil.x_extent(face_bottom + 8, box_y)
    # the hero's own type sits on her body (the lead may claim the rest)
    text_left = max(c.L + 70, (ext[0] if ext else frame.x) + float(c.genes.get("hero_text_inset", 2.0)))
    # name chip
    y = face_bottom + 9
    chip_size = 10.5
    if story.kicker:
        name = story.kicker.upper()
        nw = kit.width(name, "info", chip_size)
        c.plate(text_left, y, nw + 5, kit.face("info").cap * chip_size * PT + 3.2, kit.g["hero_name_chip"]["bg"],
                z=24, story=story, role="band")
        c.line(name, "info", chip_size, text_left + 2.5, y + 1.6, kit.g["hero_name_chip"]["color"], story=story,
               role="kicker", z=25, on=kit.g["hero_name_chip"]["bg"])
        y += kit.face("info").cap * chip_size * PT + 6.5
    # headline: lines fill the column; emphasised words in the accent colour
    emphasis = {_norm(w) for w in story.headline_emphasis}
    colours = kit.g["hero_headline_colors"]
    width = c.R - text_left
    stack = c.stack(story, story.headline.split(), emphasis, "display_italic", text_left, y,
                    lambda a, b: width, box_y - 4, base=colours[0], accent=colours[1], max_lines=4,
                    max_pt=float(kit.g.get("hero_headline_max_pt", 95.0)),
                    min_pt=20, gap_em=.05, outline=("ink", .7), case="normal", importance=.85, z=26)
    for e in stack:
        if e.style.color != kit.color(colours[1]):
            e.style.outline_color = None
            e.style.outline_width_pt = None
    # copy box
    text = story.lead or story.body
    if text:
        bw = 62.0
        c.copy(text, "body", kit.g["hero_body_box"]["size_pt"], c.R - bw, box_y, bw, body_box_h,
               kit.g["hero_body_box"]["color"], story=story, role="lead", bg=kit.g["hero_body_box"]["bg"],
               inset=[2, 2.2, 2, 2.2], page_ref=story.page_ref, z=24, min_size=7.2, max_size=10.0)
    return {"x": frame.x, "text_left": text_left, "face_bottom": face_bottom, "element": el}


def _place_roundel(c: LayeredCover, story, hero_info):
    """The promo roundel goes into the biggest hole of the page.  Occupancy
    is a 1 mm raster of real ink (glyph boxes, cut-out silhouettes, photos,
    top plates); the roundel never touches type or a face."""
    import numpy as np
    from shapely.geometry import Point
    from .layered_rules import _ink
    kit = c.kit
    g = kit.g["promo_roundel"]
    dmm = g["d_mm"]
    W, H = int(c.trim_w) + 1, int(c.trim_h) + 1
    occ = np.zeros((H, W), dtype=bool)
    text_ink = []
    for e in c.out.elements:
        if e.role == "photo":
            if e.id in c.out.masks:
                sil = Silhouette(c.out.masks[e.id], e.frame, e.crop_box)
                x0, y0 = int(max(0, e.frame.x)), int(max(0, e.frame.y))
                x1, y1 = int(min(W, e.frame.x + e.frame.w)), int(min(H, e.frame.y + e.frame.h))
                for yy in range(y0, y1):
                    for xx in range(x0, x1):
                        if sil.covers(xx, yy, xx + 1, yy + 1) > .5:
                            occ[yy, xx] = True
            else:
                occ[int(max(0, e.frame.y)):int(e.frame.y + e.frame.h), int(max(0, e.frame.x)):int(e.frame.x + e.frame.w)] = True
        elif e.text_content:
            ink = _ink(e)
            text_ink.append(ink)
            x0, y0, x1, y1 = (int(v) for v in ink.bounds)
            for yy in range(max(0, y0), min(H, y1 + 1)):
                for xx in range(max(0, x0), min(W, x1 + 1)):
                    if ink.contains(Point(xx + .5, yy + .5)):
                        occ[yy, xx] = True
        elif e.style and e.style.bg_color and e.z >= 20:
            occ[int(max(0, e.frame.y)):int(e.frame.y + e.frame.h), int(max(0, e.frame.x)):int(e.frame.x + e.frame.w)] = True
    faces = [f for boxes in c.out.faces.values() for f in boxes]
    for dmm in [g["d_mm"], *g.get("d_mm_smaller", [36.0, 32.0])]:
        if _try_roundel(c, story, g, dmm, occ, text_ink, faces):
            return
    c.out.missing.append(f"{story.id}.promo")


def _try_roundel(c, story, g, dmm, occ, text_ink, faces) -> bool:
    import numpy as np
    from shapely.geometry import Point
    kit = c.kit
    yy_, xx_ = np.mgrid[0:int(dmm), 0:int(dmm)]
    disk = (xx_ - dmm / 2 + .5) ** 2 + (yy_ - dmm / 2 + .5) ** 2 <= (dmm / 2) ** 2
    card_top = kit.frame["card"]["top"]

    def clear(x, y):
        circle = Point(x + dmm / 2, y + dmm / 2).buffer(dmm / 2 + 1.0)
        if any(circle.intersects(ink) for ink in text_ink):
            return False
        for f in faces:
            if not (x + dmm < f[0] or x > f[2] or y + dmm < f[1] or y > f[3]):
                return False
        return c.L - 2 <= x and x + dmm <= c.R + 2

    scored = []
    for yy in range(int(card_top + 4), int(c.B - dmm - 1), 3):
        for xx in range(int(c.L), int(c.R - dmm), 3):
            win = occ[yy:yy + int(dmm), xx:xx + int(dmm)]
            if win.shape != disk.shape:
                continue
            scored.append((-(~win & disk).sum() / disk.sum(), xx, yy))
    scored.sort()
    for _, xx, yy in scored:
        if clear(xx, yy):
            c.plate(xx, yy, dmm, dmm, g["bg"], shape="circle", z=30, story=story, border=("white", 1.4))
            lines = [(story.kicker or "").upper(), *story.headline.upper().split(" ", 1), story.page_ref or ""]
            lines = [l for l in lines if l]
            inner = dmm * .74
            mid = lines[1:-1] or lines
            big = min(22.0, min(inner / max(1e-6, kit.width(l, "teaser", 1.0)) for l in mid))
            sizes = [big * .55] + [big] * (len(lines) - 2) + [big * .42]
            colours = [g["accent"]] + [g["color"]] * (len(lines) - 2) + [g["color"]]
            heights = [kit.face("teaser").cap * s * PT for s in sizes]
            total = sum(heights) + 1.6 * (len(lines) - 1)
            ty = yy + (dmm - total) / 2
            for line, s, col, hgt in zip(lines, sizes, colours, heights):
                lw = kit.width(line, "teaser", s)
                c.line(line, "teaser", s, xx + (dmm - lw) / 2, ty, col, story=story, role="kicker", z=31,
                       constraints=("promo",), on=g["bg"])
                ty += hgt + 1.6
            c.rotate_group([e for e in c.out.elements if e.story_ref == story.id], float(g.get("rotation_deg", -8.8)),
                           (xx + dmm / 2, yy + dmm / 2))
            return True
    return False


def _bottom_strip(c: LayeredCover, story, rise: float = 34.0, photos: str = "framed"):
    """Full-width teaser strip under the frame (NR22).  Rulebook U16/U17:
    portraits are rectangles filling the strip height at its right end
    (``photos="framed"``), or cut-out heads standing on a coloured strip —
    never on bare paper; the headline fills the rest with the largest type."""
    kit = c.kit
    b = kit.frame["bottom"]
    y, h = b["y"], b["h"]
    x_l, x_r = c.L, c.trim_w + c.bleed
    ground = "white" if photos == "framed" else kit.g.get("cutout_ground", "yellow")
    c.plate(-c.bleed, y, x_r + c.bleed, h, ground, z=26, story=story)
    imgs = story.images[:2]
    if photos != "framed":
        # a portrait cut by its source frame on the right stands at the right bleed
        from .cutout_quality import cut_sides
        imgs = sorted(imgs, key=lambda im: "right" not in cut_sides(im.alpha_mask_url) if im.alpha_mask_url else True)
    right_limit = c.R
    px = x_r
    for k, img in enumerate(imgs):
        aspect = (img.width_px or 1) / (img.height_px or 1)
        if photos == "framed" or not img.alpha_mask_url:
            pw = min(h * max(.75, min(aspect, 1.1)), (x_r - x_l) * .22)
            c.photo_fill(img, (px - pw, y, px, y + h), story=story, z=27, face_target=(.5, .42), importance=.5)
            px -= pw + (0.0 if k == 0 else 0.0)
        else:
            ab = (img.photo_analysis or {}).get("alpha_bbox") or [0, 0, 1, 1]
            crop = [ab[0], ab[1], ab[2], 1.0]
            ca = ((ab[2] - ab[0]) * (img.width_px or 1)) / ((1.0 - ab[1]) * (img.height_px or 1))
            ph = h - 1.0
            pw = ph * ca
            c.photo(img, px - pw, y + h - ph, pw, ph, story=story, cutout=True, z=27 - k, crop=crop, importance=.5,
                    module=(-c.bleed, y, x_r, y + h))
            px -= pw + 1.0                         # side by side: no face behind a silhouette
        right_limit = min(right_limit, px - 3.0)
    ref = story.page_ref or ""
    ref_w = kit.width(ref, "info", 8.0) + 3 if ref else 0.0
    lines, size = c.fill_block(story.headline, "teaser", right_limit - x_l - ref_w, h - 3.0, max_lines=2,
                               max_pt=120.0, case_upper=True)
    offs, hh = c.block(lines, "teaser", size, 1.2)
    top = y + (h - hh) / 2
    for line, off in zip(lines, offs):
        c.line(line, "teaser", size, x_l, top + off, "ink", story=story, importance=.6, z=30, on=ground)
    if ref:
        c.line(ref, "info", 8.0, right_limit - ref_w + 1, y + h - kit.face("info").cap * 8.0 * PT - 2.0, "ink",
               story=story, role="jump_line", z=30, on=ground)


def _bottom_corner(c: LayeredCover, story, box: Optional[tuple[float, float]] = None, framed: bool = False) -> float:
    """Teaser box in the bottom-right corner under the hero: cut-out head(s)
    plus a condensed caps headline.  Returns the top edge (the hero's floor).
    ``box`` = (left x, top y) from the page skeleton."""
    kit = c.kit
    if box:
        x, y = box
        w, h = c.trim_w + c.bleed - x, c.B - y
    else:
        w, h = 118.0, 44.0
        x, y = c.trim_w + c.bleed - w, c.B - h
    # U17: cut-out heads need a ground — a coloured box; framed photos sit on white
    c.plate(x, y, w, h + (c.trim_h + c.bleed - c.B), kit.g.get("cutout_ground", "yellow") if framed == "cutout" else "white",
            z=28, story=story)
    heads = [im for im in story.images if im.alpha_mask_url][:2]
    text_x0, text_x1 = x + 4, c.R
    if framed == "cutout":
        # heads standing on the trim, as tall as the box: they belong to the
        # box (anchored at its bottom corners), the headline sits between
        full_h = c.trim_h + c.bleed - y + 6.0
        for k, img in enumerate([im for im in story.images if im.alpha_mask_url][:2]):
            ab = (img.photo_analysis or {}).get("alpha_bbox") or [0, 0, 1, 1]
            crop = [ab[0], ab[1], ab[2], 1.0]
            aspect = ((ab[2] - ab[0]) * (img.width_px or 1)) / ((1.0 - ab[1]) * (img.height_px or 1))
            pw = min(full_h * aspect, w * .36)
            ph = pw / aspect
            px = x - 2.0 if k == 0 else c.trim_w + c.bleed - pw
            el = c.photo(img, px, c.trim_h + c.bleed - ph, pw, ph, story=story, cutout=True, z=29, crop=crop,
                         importance=.5)
            fb = c.out.faces.get(el.id) or []
            if k == 0:
                text_x0 = (max(f[2] for f in fb) if fb else px + pw * .8) + 1.5
            else:
                text_x1 = (min(f[0] for f in fb) if fb else px + pw * .2) - 1.5
        heads = []
    elif framed:
        # NR21: both portraits are rectangular crops filling the box height,
        # one at each end; the headline sits between them.  The box ends on
        # the live-area bottom like the frame's rail (not in the bleed).
        full_h = c.B - y
        for e in c.out.elements[::-1]:
            if e.role == "band" and e.story_ref == story.id and abs(e.frame.y - y) < .01:
                e.frame.h = full_h
                break
        for k, img in enumerate(story.images[:2]):
            pw = w * .3
            iw, ih = (img.width_px or 1), (img.height_px or 1)
            fx = ((img.photo_analysis or {}).get("faces") or [[.3, .2, .7, .6]])[0]
            cw = min(1.0, (pw / full_h) * ih / iw)          # crop width (normalised)
            cu = min(1 - cw, max(0.0, (fx[0] + fx[2]) / 2 - cw / 2))
            px = x if k == 0 else c.trim_w + c.bleed - pw
            el = c.photo(img, px, y, pw, full_h, story=story, z=29, crop=[cu, 0, cu + cw, 1], importance=.5)
            if k == 0:
                text_x0 = px + pw + 2.0
            else:
                text_x1 = px - 2.0
        heads = []
    for k, img in enumerate(heads):
        ab = (img.photo_analysis or {}).get("alpha_bbox") or [0, 0, 1, 1]
        crop = [ab[0], ab[1], ab[2], 1.0]
        aspect = ((ab[2] - ab[0]) * (img.width_px or 1)) / ((1.0 - ab[1]) * (img.height_px or 1))
        ph = h - 2
        pw = min(ph * aspect, w * .34)
        ph = pw / aspect
        if k == 0:
            el = c.photo(img, x + 1, c.B - ph + 2, pw, ph, story=story, cutout=True, z=29, crop=crop, importance=.5)
            fr = [f[2] for f in c.out.faces.get(el.id) or []]
            text_x0 = (max(fr) if fr else x + 1 + pw * .8) + 2.0
        else:
            # second face at the outer edge, bleeding off the trim
            px = c.trim_w + c.bleed - pw
            el = c.photo(img, px, c.B - ph + 2, pw, ph, story=story, cutout=True, z=29, crop=crop, importance=.5)
            fl = [f[0] for f in c.out.faces.get(el.id) or []]
            text_x1 = min(c.R, (min(fl) if fl else px + pw * .2) - 2.0)
    ref_h = 4.0 if story.page_ref else 0.0
    # U16: the headline fills the box between the portraits (largest type)
    lines, size = c.fill_block(story.headline, "teaser", (text_x1 - text_x0) / 1.012 - 1.0, h - 5 - ref_h,
                               max_lines=4, max_pt=120.0, case_upper=True)
    offs, hh = c.block(lines, "teaser", size, 1.2)
    top = y + 2.5 + (h - 5 - ref_h - hh) / 2
    for line, off in zip(lines, offs):
        lw = kit.width(line, "teaser", size)
        c.line(line, "teaser", size, text_x0 + ((text_x1 - text_x0) - lw * 1.012 - 1.0) / 2, top + off, "ink",
               story=story, importance=.6, z=30, on=kit.g.get("cutout_ground", "yellow") if framed == "cutout" else "white")
    if story.page_ref:
        rw = kit.width(story.page_ref, "info", 7.5)
        c.line(story.page_ref, "info", 7.5, text_x1 - rw - 1, c.B - 3.4, "ink", story=story, role="jump_line",
               z=30, on="white")
    return y - 2.0


def _ensure_legible(c: LayeredCover) -> None:
    """Type that lands on a busy part of a photo gets an ink outline (the
    tabloid answer); if that is not enough, the kit's legible alternative."""
    from .layered_rules import contrast_failures
    meta = {"cutout_masks": c.out.masks}
    for _ in range(3):
        fails = contrast_failures(c.out.elements, meta)
        if not fails:
            return
        for t, name, ratio, need in fails:
            if not name.startswith("photo:"):
                continue
            if not t.style.outline_color:
                # the whole display group gets the same edge, not one word
                group = [e for e in c.out.elements if t.flow_group and e.flow_group == t.flow_group
                         and e.style.color == t.style.color] or [t]
                for e in group:
                    if not e.style.outline_color:
                        e.style.outline_color, e.style.outline_width_pt = c.kit.color("ink"), .7
                c.out.decisions.append({"decision": "outline_for_contrast", "element": t.id, "background": name})
            else:
                t.style.color = c.kit.color("white") if t.style.outline_color == c.kit.color("ink") else c.kit.color("ink")
                c.out.decisions.append({"decision": "colour_for_contrast", "element": t.id, "background": name})
