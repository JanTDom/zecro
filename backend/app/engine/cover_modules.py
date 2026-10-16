"""Module skeleton of a layered tabloid cover (Wukadka grammar).

The page is built from modules anchored to each other and to the title's
fixed frame, measured on the printed covers NR20–NR22 (PDF vector shapes):

* skybox band 22.0–71.2 mm, two slots split by an 11.2 mm gap;
* blue brand frame: masthead band 0–211.1 × 78.6–132.7, left strip 0–8.3,
  a 9.7 mm bar leaning 13° that closes the lead window on the right
  (top at y 147.3), bottom band 8.7 mm high;
* the lead window = the white parallelogram between strip and bar;
* lead type is sheared (verticals stay vertical, baselines rise 8.8°) and
  every line spans the window at its own height; kicker plates sheared 9°
  and centred on one axis;
* the hero stands right of the bar, 3.8 mm under the skybox, flush to the
  bleed; its type block is aligned to x = 258.7;
* the promo roundel (Ø 49.3) is pinned on the bar's centre line;
* the bottom teaser either starts at the foot of the bar (corner) or runs
  as a strip under the frame.

Every module records what it is anchored to; nothing is placed by
searching for free space.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

LEAN = math.tan(math.radians(13.0))   # frame bar
SHEAR_DEG = 8.8                       # lead type (vertical shear)
PT = 25.4 / 72.0


@dataclass
class Module:
    name: str
    kind: str
    poly: list[tuple[float, float]]
    anchors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def wukadka_skeleton(kit, material, genes: Optional[dict] = None) -> dict[str, Module]:
    genes = {"bottom": "corner", "bar_top_x": 184.6, "skybox_split": 132.0, **(genes or {})}
    fmt = kit.data["format"]
    trim_w, trim_h = fmt["trim_mm"]
    bleed = fmt["bleed_mm"]
    L, R = fmt["live"]["left"], fmt["live"]["right"]
    m: dict[str, Module] = {}

    def add(mod: Module):
        m[mod.name] = mod
        return mod

    # skybox ---------------------------------------------------------------
    s = float(genes["skybox_split"])
    add(Module("skybox_a", "slot", rect(10.1, 22.0, s, 71.2), ["lewa krawędź = margines 10,1", "pas 22,0–71,2"]))
    add(Module("skybox_b", "slot", rect(s + 11.2, 22.0, trim_w + bleed, 71.2),
               ["odstęp 11,2 od skyboxu A", "na spad"]))
    # frame ----------------------------------------------------------------
    add(Module("frame_band", "frame", rect(0, 78.6, 211.1, 132.7), ["stała rama tytułu"]))
    add(Module("logo", "brand", rect(4.1, 83.8, 204.6, 127.5), ["winieta w pasie ramy"]))
    add(Module("dateline", "brand", rect(7.0, 134.0, 198.0, 140.6), ["pod pasem ramy"]))
    corner = genes["bottom"] == "corner"
    yb = 366.4 if corner else 341.6
    bx = float(genes["bar_top_x"])
    y_top, y_bot = 147.3, yb + 8.7

    def bar_left(y):
        return bx - (y - y_top) * LEAN

    add(Module("frame_left", "frame", rect(0, 108.8, 8.3, y_bot), ["lewa listwa ramy"]))
    add(Module("frame_bar", "frame", [(bx, y_top), (bx + 9.7, y_top), (bar_left(y_bot) + 9.7, y_bot), (bar_left(y_bot), y_bot)],
               ["belka 13°, start pod paskiem daty"]))
    add(Module("frame_bottom", "frame", rect(0, yb, bar_left(yb) + 2, y_bot), ["dolna listwa ramy, do belki"]))
    window = [(8.3, 147.1), (bar_left(147.1), 147.1), (bar_left(yb), yb), (8.3, yb)]
    add(Module("lead_window", "window", window, ["między listwą a belką", "od paska daty do dolnej listwy"]))
    # bottom teaser --------------------------------------------------------
    if corner:
        bt = 324.7
        add(Module("bottom_teaser", "slot", rect(bar_left(375.0) + 8.0, bt, trim_w + bleed, trim_h + bleed),
                   ["lewa krawędź = stopa belki", "na spad"]))
        hero_bottom = bt + 10.0
    else:
        bt = 351.0
        add(Module("bottom_teaser", "slot", rect(0, bt, trim_w + bleed, 377.0), ["pas pod ramą, pełna szerokość"]))
        hero_bottom = bt
    # hero -------------------------------------------------------------------
    hero = next((st for st in material.stories if st.rank == "second" and st.images), None)
    if hero:
        img = hero.images[0]
        top = 71.2 + 3.8
        h = hero_bottom - top
        w = h * (img.width_px or 1) / (img.height_px or 1)
        x0 = trim_w + bleed - w
        if genes.get("hero_place"):
            # placement solved by the composer (face clear of the dateline,
            # logo coverage within the title's measured limit)
            x0, top, w, h = genes["hero_place"]
        faces = (img.photo_analysis or {}).get("faces") or []
        face = [x0 + faces[0][0] * w, top + faces[0][1] * h, x0 + faces[0][2] * w, top + faces[0][3] * h] if faces else None
        add(Module("hero", "cutout", rect(x0, top, min(x0 + w, trim_w + bleed), top + h),
                   ["3,8 mm pod skyboxem", "do spadu", "stopy na zapowiedzi dolnej"], {"face": face}))
        name_y = (face[3] if face else top + h * .35) + 36.0
        tx1 = 258.7
        tx0 = max(bx + 9.7 - (name_y - y_top) * LEAN + 2.0, tx1 - 76.0)
        copy_bottom = bt - 7.2
        add(Module("hero_text", "type", rect(tx0, name_y, tx1, copy_bottom - 42.0),
                   ["prawa krawędź x = 258,7", "od imienia pod twarzą"]))
        add(Module("hero_copy", "type", rect(tx1 - 50.2, copy_bottom - 39.5, tx1, copy_bottom),
                   ["prawa krawędź x = 258,7", "7,2 mm nad zapowiedzią dolną"]))
    # roundel ------------------------------------------------------------------
    yc = y_top + .68 * (yb - y_top)
    xc = bar_left(yc) + 4.85
    d = 49.3
    add(Module("roundel", "sticker", [(xc + d / 2 * math.cos(t / 24 * 2 * math.pi), yc + d / 2 * math.sin(t / 24 * 2 * math.pi)) for t in range(24)],
               ["środek na osi belki"], {"center": (xc, yc), "d": d}))
    return m


def lead_slots(kit, skel: dict[str, Module], story, gap_right: float = 5.0, margin_left: float = 9.5,
               force_lines: Optional[list[str]] = None) -> list[Module]:
    """Kicker plates and sheared headline lines inside the lead window.

    Geometry is anchored at the LEFT end of every line (shear keeps the
    verticals; the right end rises by width·tan 8.8°).  Each line spans the
    window from the left margin to the bar minus a gap, measured at the
    height of its own right end.  Lines without a stressed word are capped
    at 0.8 × the biggest stressed line (NR21: SIĘ 168 pt vs DASZ 212 pt),
    which leaves the room for the lead paragraph.  The breaking that fills
    the window height best wins; the last line may break the frame bottom
    by up to 10 mm (NR21: OKRAŚĆ)."""
    import itertools
    import re
    from .layered_rules import _glyph_bounds
    bar = skel["frame_bar"].poly
    bx, y_top = bar[0]

    def bar_left(y):
        return bx - (y - y_top) * LEAN

    yb = skel["lead_window"].poly[2][1]
    face = kit.face("display")
    gb = _glyph_bounds(face.path) if face.path else None
    sh = math.tan(math.radians(SHEAR_DEG))

    def ink(text, size):
        if not gb:
            return .18 * size * PT, .2 * size * PT
        bs = [b for b in (gb(ch) for ch in text if not ch.isspace()) if b]
        return (max(0.0, max(b[3] for b in bs) - face.cap) * size * PT, max(0.0, -min(b[1] for b in bs)) * size * PT)

    from .shaper import width_pt

    def glyph_cols(text, size):
        """(x0, x1, above-cap, below-baseline) per glyph, mm, from the line start."""
        cols = []
        for i, ch in enumerate(text):
            if ch.isspace() or not gb:
                continue
            b = gb(ch)
            if not b:
                continue
            x = kit.width(text[:i], "display", size) if i else 0.0
            cols.append((x + b[0] * size * PT, x + b[2] * size * PT,
                         max(0.0, b[3] - face.cap) * size * PT, max(0.0, -b[1]) * size * PT))
        return cols

    def interlock(prev, psize, nxt, nsize):
        """Extra room between two stacked lines: only where an ogonek of the
        upper line meets an accent of the lower one (lines interlock, NR21)."""
        need = 0.0
        a, b_ = glyph_cols(prev, psize), glyph_cols(nxt, nsize)
        for ax0, ax1, _, adown in a:
            for bx0, bx1, bup, _ in b_:
                if ax1 > bx0 and bx1 > ax0:
                    need = max(need, adown + bup)
                else:
                    need = max(need, max(adown, bup) * 0.0)
        return need

    norm = lambda w: re.sub(r"[^\wąćęłńóśźż]", "", w.lower())
    out: list[Module] = []
    # kicker plates: one axis, sheared like the type; the first plate starts
    # on the dateline (it breaks over the frame, NR21/NR22)
    y_axis = 137.3 + 12.0
    if story.kicker:
        words = story.kicker.upper().split()
        if len(story.kicker) <= 16:
            klines = [" ".join(words)]
        else:
            klines = min(([" ".join(words[:c]), " ".join(words[c:])] for c in range(1, len(words))),
                         key=lambda ab: abs(len(ab[0]) - len(ab[1])))
        size = 51.2  # plates on NR20–22: Gotham XNarrow Black 37–51 pt
        widths = [kit.width(l, "display", size) for l in klines]
        axis = margin_left + max(widths) / 2 + 2.0
        for l, w in zip(klines, widths):
            h = face.cap * size * PT + 4.4
            x0, x1 = axis - w / 2 - 2.0, axis + w / 2 + 2.0
            yl = y_axis + (axis - x0) * sh      # top edge at the left end
            poly = [(x0, yl), (x1, yl - (x1 - x0) * sh), (x1, yl - (x1 - x0) * sh + h), (x0, yl + h)]
            out.append(Module(f"kicker:{l}", "plate", poly, ["wspólna oś belek", "ścięcie 8,8°"], {"text": l, "size": size}))
            y_axis += h + 1.8
        y_left = max(m.poly[3][1] for m in out) + 1.5 - 0.0   # cap top of the first line at the margin
        y_left = y_axis + (axis - margin_left) * sh + 1.5
    else:
        y_left = 152.0 + 0.0
    words = story.headline.upper().split()
    emph = {norm(w) for w in story.headline_emphasis}
    bottom_target = yb - 3.0  # type stays inside the window (no line on the frame rail)
    rail_bottom = skel["lead_window"].poly[0][1] + 9.8
    ring_c = skel["roundel"].data["center"] if "roundel" in skel else (1e6, 1e6)
    ring_r = 49.3 / 2 if "roundel" in skel else 0.0
    best = None
    forced = None
    if force_lines:
        fl = [l.upper().split() for l in force_lines if l.strip()]
        if sum(fl, []) == words:  # the art director's breaking, if it is the same headline
            acc, cuts_ = 0, []
            for l in fl[:-1]:
                acc += len(l); cuts_.append(acc)
            forced = tuple(cuts_)
    for k in range(2, min(5, len(words)) + 1):
        for cuts in itertools.combinations(range(1, len(words)), k - 1):
            if forced is not None and cuts != forced:
                continue
            b = [0, *cuts, len(words)]
            lines = [" ".join(words[b[i]:b[i + 1]]) for i in range(k)]
            # sizes from the window width, then the stress cap
            yl, sizes = y_left, []
            for i, ln in enumerate(lines):
                if i:
                    yl += face.cap * sizes[-1] * PT + interlock(lines[i - 1], sizes[-1], ln, sizes[-1]) + 1.6
                size = 260.0
                for _ in range(4):
                    w = kit.width(ln, "display", size)
                    # the bar leans left going down: the binding point is the
                    # right end's baseline, not its middle
                    y_right_base = yl - w * sh + face.cap * size * PT
                    right = bar_left(y_right_base) - gap_right
                    # the promo roundel (with its white ring) sits on the bar:
                    # a line whose band crosses it stops before the ring
                    r_top, r_bot = yl - w * sh, yl + face.cap * size * PT
                    if r_bot > ring_c[1] - ring_r and r_top < ring_c[1] + ring_r:
                        right = min(right, ring_c[0] - ring_r - 2.0)
                    avail = right - margin_left
                    # the sheared right end rises: it stays under the window's
                    # top rail (NR21: the first line's right end clears the rail)
                    if margin_left + w > 90.0:
                        rise_room = yl - rail_bottom - 1.5 - ink(ln, size)[0]
                        avail = min(avail, max(10.0, rise_room / sh))
                    size = min(260.0, avail / max(1e-6, kit.width(ln, "display", 1.0)))
                sizes.append(size)
            stressed = [sizes[i] for i, ln in enumerate(lines) if any(norm(w) in emph for w in ln.split())]
            if stressed:
                cap = .8 * max(stressed)
                sizes = [s if any(norm(w) in emph for w in ln.split()) else min(s, cap) for s, ln in zip(sizes, lines)]
            def stack(sz):
                yl, tops = y_left, []
                for i, ln in enumerate(lines):
                    if i:
                        yl += face.cap * sz[i - 1] * PT + interlock(lines[i - 1], sz[i - 1], ln, sz[i]) + 1.6
                    tops.append(yl)
                return tops, tops[-1] + face.cap * sz[-1] * PT
            tops, bottom = stack(sizes)
            for _ in range(4):  # too tall: the whole stack shrinks together
                if bottom <= bottom_target + .5:
                    break
                f = (bottom_target - y_left) / (bottom - y_left)
                sizes = [s_ * f for s_ in sizes]
                tops, bottom = stack(sizes)
            pen = abs(bottom - bottom_target) / (bottom_target - y_left)
            pen += .4 * max(0, max(sizes) / min(sizes) - 2.2) + .3 * sum(1 for ln in lines if len(ln) <= 2)
            if bottom > bottom_target + 4:
                pen += 1.0
            if best is None or pen < best[0]:
                best = (pen, lines, sizes, tops)
    _, lines, sizes, tops = best
    for ln, size, yl in zip(lines, sizes, tops):
        hcap = face.cap * size * PT
        w = kit.width(ln, "display", size)
        x0 = margin_left
        out.append(Module(f"line:{ln}", "line", [(x0, yl), (x0 + w, yl - w * sh), (x0 + w, yl - w * sh + hcap), (x0, yl + hcap)],
                          ["lewy margines okna", "prawy koniec ≤ belka − 5 mm", "ścięcie 8,8°"],
                          {"text": ln, "size": round(size, 1)}))
    # lead paragraph: beside the line that leaves most room
    rc, rd = skel["roundel"].data["center"], skel["roundel"].data["d"]
    cands = []
    for mod in (m for m in out if m.kind == "line"):
        x1 = mod.poly[1][0]
        y0, y1 = mod.poly[1][1], mod.poly[3][1]
        right = bar_left((y0 + y1) / 2) - gap_right
        if y1 > rc[1] - rd / 2 and y0 < rc[1] + rd / 2:
            right = min(right, rc[0] - rd / 2 - 4.0)
        cands.append((right - (x1 + 2.8), mod, right))
    room, mod, right = max(cands, key=lambda t: t[0])
    if room > 30:
        x1 = mod.poly[1][0]
        lines_only = [m for m in out if m.kind == "line"]
        nxt = lines_only[lines_only.index(mod) + 1] if lines_only.index(mod) + 1 < len(lines_only) else None
        bottom = mod.poly[2][1] + 10.0
        if nxt is not None:
            # stop above the next line's accents, measured at the paragraph's left edge
            nx0, nyl = nxt.poly[0]
            top_there = nyl - (x1 + 2.8 - nx0) * sh - ink(nxt.data["text"], nxt.data["size"])[0]
            bottom = min(bottom, top_there - 2.0)
        out.append(Module("lead_paragraph", "type", rect(x1 + 2.8, mod.poly[1][1] + 1.0, right, bottom),
                          ["lewa = koniec najkrótszego wiersza + 2,8", "prawa = przed roundelem / belką"]))
    else:
        # no room beside a line (a short stack): the paragraph takes the
        # window's foot under the stack — the window never keeps a hole (U15)
        last = [m for m in out if m.kind == "line"][-1]
        top = max(p[1] for p in last.poly) + ink(last.data["text"], last.data["size"])[1] + 5.0
        bottom = yb - 4.0
        if bottom - top >= 20.0:
            right = bar_left(bottom) - gap_right
            if bottom > rc[1] - rd / 2 and top < rc[1] + rd / 2:
                right = min(right, rc[0] - 49.3 / 2 - 3.0)
            out.append(Module("lead_paragraph", "type", rect(margin_left, top, right, bottom),
                              ["pod stosem tytułu (brak miejsca obok wiersza)", "prawa = przed roundelem / belką"]))
    return out


def lead_breakings(kit, skel: dict[str, Module], story, limit: int = 8) -> list[dict]:
    """Every sensible breaking of the lead headline, measured by the engine:
    how much of the window height the stack fills and the size ratio.  The
    art director chooses among these instead of guessing geometry."""
    import itertools
    words = story.headline.upper().split()
    yb = skel["lead_window"].poly[2][1]
    out = []
    small_words = {"I", "W", "Z", "NA", "DO", "O", "A", "U", "ZA", "PO", "OD", "BO", "ŻE", "SIĘ", "NIE"}
    for k in range(2, min(5, len(words)) + 1):
        for cuts in itertools.combinations(range(1, len(words)), k - 1):
            b = [0, *cuts, len(words)]
            lines = [" ".join(words[b[i]:b[i + 1]]) for i in range(k)]
            slots = lead_slots(kit, skel, story, force_lines=lines)
            mods = [m for m in slots if m.kind == "line"]
            if not mods:
                continue
            # the window's largest hole once the stack and the lead are set
            # (lead height estimated from its length: ~45 mm² a word at 9.5 pt)
            from shapely.geometry import Polygon, box as _box
            from shapely.ops import unary_union
            win = Polygon(skel["lead_window"].poly)
            # as the gate sees it: the stack is one block (its bounding box)
            lb = unary_union([Polygon(m.poly) for m in mods]).bounds
            taken = [_box(*lb)] + [Polygon(m.poly) for m in slots if m.kind == "plate"]
            if "roundel" in skel:
                taken.append(Polygon([(0, 0), (1, 0), (1, 1)]).buffer(0).union(
                    __import__("shapely.geometry", fromlist=["Point"]).Point(*skel["roundel"].data["center"]).buffer(49.3 / 2)))
            para = next((m for m in slots if m.name == "lead_paragraph"), None)
            lead_txt = (story.lead or story.body or "").strip()
            if para is not None and lead_txt and lead_txt != "—":
                px0, py0 = para.poly[0]; px1, py1 = para.poly[2]
                need = len(lead_txt.split()) * 45.0 / max(1.0, px1 - px0)
                taken.append(_box(px0, py0, px1, min(py1, py0 + need)))
            from .layered_rules import largest_free_of_polys_cm2
            hole = largest_free_of_polys_cm2(win, taken)
            top = min(m.poly[0][1] for m in mods)
            bottom = max(m.poly[3][1] for m in mods)
            sizes = [m.data["size"] for m in mods]
            # where the window starts for the type (below the kicker plates)
            win_top = min(m.poly[0][1] for m in mods)
            fill = (bottom - win_top) / max(1e-6, (yb - 3.0) - win_top)
            dangling = [l for l in lines[:-1] if l.split()[-1] in {"I", "W", "Z", "NA", "DO", "O", "A", "U", "ZA", "PO", "OD", "BO", "ŻE"}]
            # width use: each line's length against the window width at its height
            bx_, y_top_ = skel["frame_bar"].poly[0]
            wfill = []
            for m in mods:
                ymid = (m.poly[0][1] + m.poly[3][1]) / 2
                avail = (bx_ - (ymid - y_top_) * LEAN) - 5.0 - m.poly[0][0]
                wfill.append(min(1.0, (m.poly[1][0] - m.poly[0][0]) / max(1e-6, avail)))
            width_fill = sum(wfill) / len(wfill)
            area = min(fill, 1.0) * width_fill
            out.append({"wiersze": " | ".join(lines), "wypelnienie_wysokosci": round(min(fill, 1.2), 2),
                        "wypelnienie_szerokosci": round(width_fill, 2), "wypelnienie_powierzchni": round(area, 2),
                        "dziura_okna_cm2": round(hole), "stopnie_pt": [round(x) for x in sizes],
                        "uwagi": ("wiszący przyimek/spójnik na końcu wiersza (U5)" if dangling else "")})
    # a hole over the gate's limit (30 cm²) disqualifies; then the fill
    out.sort(key=lambda d: ((d["dziura_okna_cm2"] > 30), -d["wypelnienie_powierzchni"] + (.5 if d["uwagi"] else 0)))
    return out[:limit]
