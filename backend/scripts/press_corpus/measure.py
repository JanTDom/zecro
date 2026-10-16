"""Measure the construction of a newspaper/magazine page from a PDF page.

Works on born-digital PDFs (vector text, real fonts, image boxes) and on
scans with an OCR text layer (archive.org *_text.pdf).  Everything is in mm
and pt.  No content is kept — only measurements.

Per page:
  format         trim w/h (mm), aspect, format class
  text           body size (char-weighted mode), leading, body line length
                 (chars), columns (count, width, gutter), text area share
  hierarchy      largest headline pt, ratio to body, 2nd/1st, 3rd/1st,
                 number of headlines (≥1.6×body), display lines
  stories        estimated number of stories (headline blocks)
  images         photo/graphic area share (pixels not covered by text and not
                 paper), largest single region share, born-digital image boxes
  colour         saturated pixel share, dark share, paper share (white space)
  rules          vector lines/boxes count (born-digital)
  fonts          distinct font families (born-digital), serif/sans of body
  dominant       share of the largest element (photo or headline block)
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import numpy as np
import pymupdf

PT_MM = 25.4 / 72.0


def format_class(w: float, h: float) -> str:
    s, l = sorted((w, h))
    if l >= 520:
        return "broadsheet"
    if l >= 440:
        return "berliner"
    if l >= 360:
        return "tabloid"        # compact/tabloid (e.g. 280×390, 289×380)
    if l >= 290:
        return "magazine"       # A4-ish, US letter
    return "small"              # A5, TV pocket guides, digests


def _family(name: str) -> str:
    name = re.sub(r"^[A-Z]{6}\+", "", name or "")
    return re.split(r"[-,]", name)[0]


def _is_serif(name: str) -> bool | None:
    n = (name or "").lower()
    if any(k in n for k in ("sans", "helvet", "arial", "gotham", "franklin", "futura", "univers", "frutiger",
                            "avenir", "myriad", "din", "verdana", "roboto", "open", "lato", "grotesk", "gill")):
        return False
    if any(k in n for k in ("serif", "times", "georgia", "utopia", "cheltenham", "imperial", "minion", "garamond",
                            "caslon", "bodoni", "century", "miller", "poynter", "nimbusrom", "palatino", "book")):
        return True
    return None


def _cluster(values: list[float], tol: float) -> list[tuple[float, int]]:
    """1-D clustering: (centre, count), sorted by count."""
    out: list[list[float]] = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return sorted(((float(np.median(c)), len(c)) for c in out), key=lambda t: -t[1])


def measure_page(page: pymupdf.Page, *, dpi: int = 30) -> dict:
    W, H = page.rect.width * PT_MM, page.rect.height * PT_MM
    res: dict = {"w_mm": round(W, 1), "h_mm": round(H, 1), "format": format_class(W, H)}
    d = page.get_text("dict")
    spans = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if not t:
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                size = float(sp["size"])
                # OCR layers often report a nominal size; the box height is the truth
                hbox = (y1 - y0)
                spans.append({"t": t, "size": size, "h": hbox, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                              "font": sp.get("font", ""), "color": sp.get("color", 0), "n": len(t)})
    res["chars"] = sum(s["n"] for s in spans)
    born_digital = bool(spans) and len({_family(s["font"]) for s in spans}) > 1 and \
        not all(_family(s["font"]).lower().startswith(("glyphless", "invisible", "times-roman")) for s in spans)
    res["source_kind"] = "born_digital" if born_digital else ("ocr" if spans else "image_only")
    # effective size: born-digital → font size; OCR → box height / 1.15 (line box ≈ 1.15 em)
    for s in spans:
        s["pt"] = s["size"] if born_digital else s["h"] / 1.15
    # ---------------------------------------------------------- text
    if spans:
        sizes = Counter()
        for s in spans:
            sizes[round(s["pt"] * 2) / 2] += s["n"]
        body = sizes.most_common(1)[0][0]
        res["body_pt"] = body
        body_sp = [s for s in spans if abs(s["pt"] - body) <= max(.6, body * .08)]
        # body lines: spans on one baseline joined while the gap is a word space
        # (PDFs often store one span per word; grouping by span would count
        # words as lines)
        segs = []
        for sp_ in sorted(body_sp, key=lambda x: (round(x["y1"] / max(1.0, body * .3)), x["x0"])):
            if segs and abs(sp_["y1"] - segs[-1]["y1"]) < body * .3 and -body * .2 <= sp_["x0"] - segs[-1]["x1"] < body * 1.2:
                segs[-1]["x1"] = max(segs[-1]["x1"], sp_["x1"]); segs[-1]["n"] += sp_["n"] + 1
            else:
                segs.append({"x0": sp_["x0"], "x1": sp_["x1"], "y1": sp_["y1"], "n": sp_["n"]})
        full = [g for g in segs if g["n"] >= 12]          # running-text lines, not stray words
        res["body_line_chars_median"] = float(np.median([g["n"] for g in full])) if full else None
        lefts = [g["x0"] for g in full]
        # paragraph indents (~1 em) belong to the same column
        cols = [c for c in _cluster(lefts, max(6.0, body * 1.6)) if c[1] >= max(6, len(lefts) * .04)]
        res["columns"] = len(cols)
        if len(cols) >= 2:
            xs = sorted(c[0] for c in cols)
            pitch = float(np.median(np.diff(xs))) * PT_MM
            widths = [g["x1"] - g["x0"] for g in full]
            colw = float(np.median(widths)) * PT_MM if widths else None
            res["column_pitch_mm"] = round(pitch, 1)
            res["column_width_mm"] = round(colw, 1) if colw else None
            res["gutter_mm"] = round(pitch - colw, 1) if colw and pitch > colw else None
        res["measure_version"] = 2
        # leading: baseline gaps inside body
        base = sorted({round(s["y1"], 1) for s in body_sp})
        gaps = [b - a for a, b in zip(base, base[1:]) if body * .9 < b - a < body * 2.0]
        res["body_leading_pt"] = round(float(np.median(gaps)), 2) if gaps else None
        # ------------------------------------------------------ hierarchy
        heads = [s for s in spans if s["pt"] >= body * 1.6 and s["n"] >= 2]
        hsizes = sorted({round(s["pt"]) for s in heads}, reverse=True)
        res["headline_max_pt"] = hsizes[0] if hsizes else None
        res["headline_ratio"] = round(hsizes[0] / body, 2) if hsizes and body else None
        res["headline_steps"] = [round(h / hsizes[0], 2) for h in hsizes[:6]] if hsizes else []
        # headline blocks: lines of similar size close together → one story head
        blocks: list[dict] = []
        for s in sorted(heads, key=lambda s: (s["y0"], s["x0"])):
            for bl in blocks:
                if abs(bl["pt"] - s["pt"]) <= s["pt"] * .25 and s["y0"] - bl["y1"] < s["pt"] * 1.2 and \
                        s["x0"] < bl["x1"] + s["pt"] and s["x1"] > bl["x0"] - s["pt"]:
                    bl.update(x0=min(bl["x0"], s["x0"]), x1=max(bl["x1"], s["x1"]), y1=max(bl["y1"], s["y1"]),
                              chars=bl["chars"] + s["n"])
                    break
            else:
                blocks.append({"pt": s["pt"], "x0": s["x0"], "x1": s["x1"], "y0": s["y0"], "y1": s["y1"], "chars": s["n"]})
        blocks = [b for b in blocks if b["chars"] >= 6]
        res["headline_blocks"] = len(blocks)
        pa = page.rect.width * page.rect.height
        if blocks:
            big = max(blocks, key=lambda b: (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]))
            res["largest_headline_area_share"] = round((big["x1"] - big["x0"]) * (big["y1"] - big["y0"]) / pa, 3)
            res["largest_headline_width_share"] = round((big["x1"] - big["x0"]) / page.rect.width, 3)
            res["largest_headline_y_share"] = round(big["y0"] / page.rect.height, 3)
        res["text_area_share"] = round(sum((s["x1"] - s["x0"]) * (s["y1"] - s["y0"]) for s in spans) / pa, 3)
        fams = Counter()
        for s in spans:
            fams[_family(s["font"])] += s["n"]
        if born_digital:
            res["font_families"] = len([f for f, n in fams.items() if n >= 20])
            bf = Counter(_family(s["font"]) for s in body_sp).most_common(1)
            res["body_font"] = bf[0][0] if bf else None
            res["body_serif"] = _is_serif(res["body_font"] or "")
            hf = Counter(_family(s["font"]) for s in heads).most_common(1)
            res["head_font"] = hf[0][0] if hf else None
            res["head_serif"] = _is_serif(res["head_font"] or "")
            res["coloured_text_share"] = round(sum(s["n"] for s in spans if s["color"] not in (0,) and
                                                   _sat(s["color"]) > .35) / max(1, res["chars"]), 3)
    # ---------------------------------------------------------- pixels
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(np.float32)
    sx, sy = pix.w / page.rect.width, pix.h / page.rect.height
    text_mask = np.zeros((pix.h, pix.w), bool)
    for s in spans:
        text_mask[max(0, int(s["y0"] * sy)):int(math.ceil(s["y1"] * sy)), max(0, int(s["x0"] * sx)):int(math.ceil(s["x1"] * sx))] = True
    mx, mn = img.max(2), img.min(2)
    sat = (mx - mn) / np.maximum(mx, 1)
    lum = img.mean(2)
    paper_ref = np.percentile(lum, 95)
    paper = (lum > paper_ref - 18) & (sat < .12)
    res["paper_share"] = round(float(paper.mean()), 3)                 # white space incl. margins
    res["saturated_share"] = round(float((sat > .35).mean()), 3)
    res["dark_share"] = round(float((lum < 60).mean()), 3)
    # graphic/photo: non-paper, not text, with local texture or solid fill
    g = (~paper) & (~text_mask)
    res["graphic_share"] = round(float(g.mean()), 3)
    # largest connected graphic region (coarse, 4-neighbour flood on a 1/2 grid)
    res["largest_graphic_share"] = round(_largest_region(g[::2, ::2]) * 4 / g.size, 3) if g.any() else 0.0
    if born_digital:
        ims = [i for i in page.get_image_info() if i.get("bbox")]
        areas = [abs((b[2] - b[0]) * (b[3] - b[1])) for b in (i["bbox"] for i in ims)]
        pa = page.rect.width * page.rect.height
        res["image_boxes"] = len([a for a in areas if a > pa * .005])
        um = np.zeros((pix.h, pix.w), bool)      # union, not sum: images overlap on full-bleed pages
        for i in ims:
            b = i["bbox"]
            um[max(0, int(b[1] * sy)):int(math.ceil(b[3] * sy)), max(0, int(b[0] * sx)):int(math.ceil(b[2] * sx))] = True
        res["image_area_share"] = round(float(um.mean()), 3)
        res["largest_image_share"] = round(max(areas) / pa, 3) if areas else 0.0
        try:
            dr = page.get_drawings()
            res["vector_rules"] = sum(1 for p in dr for it in p["items"] if it[0] == "l")
            res["vector_fills"] = sum(1 for p in dr if p.get("fill") is not None and
                                      (p["rect"].width * p["rect"].height) > pa * .002)
        except Exception:
            pass
    dom = max(res.get("largest_graphic_share") or 0, res.get("largest_headline_area_share") or 0)
    res["dominant_share"] = round(dom, 3)
    res["dominant_kind"] = "photo/graphic" if (res.get("largest_graphic_share") or 0) >= (res.get("largest_headline_area_share") or 0) else "headline"
    return res


def _sat(c: int) -> float:
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    mx, mn = max(r, g, b), min(r, g, b)
    return (mx - mn) / mx if mx else 0.0


def _largest_region(m: np.ndarray) -> int:
    """Size of the largest 4-connected True region (iterative, numpy-light)."""
    h, w = m.shape
    seen = np.zeros_like(m, bool)
    best = 0
    ys, xs = np.nonzero(m)
    for y, x in zip(ys, xs):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        n = 0
        while stack:
            cy, cx = stack.pop()
            n += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        best = max(best, n)
    return best


def measure_pdf(path: str, *, max_pages: int = 80) -> list[dict]:
    out = []
    with pymupdf.open(path) as doc:
        n = doc.page_count
        for i in range(min(n, max_pages)):
            try:
                m = measure_page(doc[i])
            except Exception as exc:  # a broken page must not stop the corpus
                m = {"error": str(exc)[:200]}
            m["page_index"] = i
            m["page_count"] = n
            m["page_role"] = "front" if i == 0 else ("back" if i == n - 1 else "inside")
            out.append(m)
    return out
