"""Cut-out quality: how a repro studio finishes a silhouette (U7, D08, D09).

A segmentation mask is not a print cut-out.  rembg-style masks are binary
and keep wisps of hair together with the background between them; drawn at
print size they read as teeth with a fringe of the old background.  A
retoucher instead draws a smooth path just INSIDE the hair line, gives up
single strands, removes the contaminated rim and softens the edge by a
fraction of a millimetre.  ``refine_cutout`` does exactly that, in numpy +
Pillow only (no scipy/OpenCV, so it also runs on the serverless backend).

``cut_sides`` reports where the subject runs into the border of the source
frame: those are straight cut edges and must lie on a module edge or the
bleed (D09), otherwise the photo has to be framed instead of cut out.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter

VERSION = "refine-7"


def _odd(n: float) -> int:
    n = max(1, int(round(n)))
    return n if n % 2 else n + 1


def _morph(mask: Image.Image, size: int, op: str) -> Image.Image:
    f = ImageFilter.MinFilter(_odd(size)) if op == "erode" else ImageFilter.MaxFilter(_odd(size))
    return mask.filter(f)


def cut_sides(mask_path: str, crop: Optional[list[float]] = None, share: float = .008) -> dict[str, float]:
    """Sides of the (cropped) frame that cut the subject, with the cut's share
    of the side (see ``cut_segments``)."""
    return {k: round(v[1] - v[0], 3) for k, v in cut_segments(mask_path, crop, share).items()}


def spikiness(mask_path: str) -> float:
    """Share of the subject area that only exists as thin spikes (wisps,
    teeth): what a smoothing cut would give up.  0 = clean contour."""
    with Image.open(mask_path) as im:
        m = (im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L"))
    ws = min(1.0, 640 / max(m.size))
    m = m.resize((max(1, round(m.width * ws)), max(1, round(m.height * ws))), Image.BILINEAR).point(lambda v: 255 if v > 128 else 0)
    r = max(2, int(min(m.size) * .012))
    opened = _morph(_morph(m, 2 * r + 1, "erode"), 2 * r + 1, "dilate")
    a, o = np.asarray(m) > 0, np.asarray(opened) > 0
    return round(float((a & ~o).sum() / max(1, a.sum())), 4)


def refine_cutout(mask_path: str, *, source_path: Optional[str] = None, min_long_px: int = 1600) -> str:
    """Return a print-ready RGBA cut-out next to ``mask_path`` (cached).

    1. upsample small sources so the edge is not drawn from big pixels;
    2. opening + closing at ~1.2 % of the subject size removes spikes and
       pin-holes (the path runs inside the hair line);
    3. Gaussian smoothing + re-threshold gives a smooth contour;
    4. the contour is pulled in by ~0.25 % (the contaminated rim goes);
    5. a 1–2 px feather makes the edge soft, as a retoucher's 0.2 mm feather.
    """
    src = Path(mask_path)
    if ".refined-" in src.name:
        return str(src)                      # already finished
    key = hashlib.sha1(f"{VERSION}{src.resolve()}{src.stat().st_mtime_ns}{min_long_px}{source_path}".encode()).hexdigest()[:10]
    out = src.with_name(f"{src.stem}.refined-{key}.png")
    if out.exists():
        return str(out)
    import os
    import tempfile
    if not os.access(src.parent, os.W_OK):
        # serverless: the app bundle is read-only; cache in the temp dir
        cache = Path(tempfile.gettempdir()) / "zecro-cutouts"
        cache.mkdir(parents=True, exist_ok=True)
        out = cache / out.name
        if out.exists():
            return str(out)
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
    W, H = rgba.size
    scale = max(1.0, min(4.0, min_long_px / max(W, H)))
    if scale > 1.0:
        rgba = rgba.resize((round(W * scale), round(H * scale)), Image.LANCZOS)
    alpha = rgba.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    bbox = alpha.getbbox()
    if not bbox:
        return str(src)
    if source_path and Path(source_path).exists():
        alpha = _drop_background_rim(alpha, source_path)
    # the contour is designed on a working copy (long side ≤ 640 px): it is
    # meant to be smooth, so nothing is lost, and the filters stay cheap
    ws = min(1.0, 640 / max(alpha.size))
    small = alpha.resize((max(1, round(alpha.width * ws)), max(1, round(alpha.height * ws))), Image.BILINEAR)
    small = small.point(lambda v: 255 if v > 128 else 0)
    sb = small.getbbox() or (0, 0, *small.size)
    subject = min(sb[2] - sb[0], sb[3] - sb[1])
    r = max(3, int(subject * .03))
    m = _morph(_morph(small, 2 * r + 1, "erode"), 2 * r + 1, "dilate")      # opening: spikes go
    m = _morph(_morph(m, 2 * r + 1, "dilate"), 2 * r + 1, "erode")          # closing: pin-holes go
    m = m.filter(ImageFilter.GaussianBlur(max(1.0, r * .6)))
    m = m.resize(alpha.size, Image.BICUBIC)
    # soft ramp around a threshold slightly above 50 %: the path runs just
    # inside the hair line and the edge gets a ~1 px feather at print size
    # a crisp edge from the smooth field, then a feather of ~1 px at the
    # working resolution (≈0.1–0.2 mm in print): soft, never a glow
    m = m.point(lambda v: 255 if v > 175 else 0)
    # choke: segmentation masks keep a rim of the old background; the cut
    # goes ~0.5 % of the subject's size inside it
    choke = max(2, int(max(m.size) * .005))
    m = _morph(m, 2 * choke + 1, "erode").filter(ImageFilter.GaussianBlur(.9))
    a = np.minimum(np.asarray(m), np.asarray(alpha.filter(ImageFilter.MaxFilter(3))))
    # straight cuts on the source border stay where the source cut them
    orig = np.asarray(alpha)
    b = max(2, int(2 * scale))
    for sl in (np.s_[:b, :], np.s_[-b:, :], np.s_[:, :b], np.s_[:, -b:]):
        a[sl] = np.maximum(a[sl], np.minimum(orig[sl], np.asarray(m)[sl]))
    a = np.ascontiguousarray(a).astype(np.uint8)
    # colour decontamination: the rim takes the colour of the subject just
    # inside it, so no trace of the old background survives the feather
    rim_w = 3  # only the feather zone and 1 px inside it
    inner = Image.fromarray(a).point(lambda v: 255 if v >= 250 else 0).filter(ImageFilter.MinFilter(_odd(rim_w)))
    if inner.getbbox():
        rgb = rgba.convert("RGB")
        sig = rim_w * 1.5
        wsum = np.asarray(inner.filter(ImageFilter.GaussianBlur(sig)), dtype=np.float32) / 255.0
        masked = Image.composite(rgb, Image.new("RGB", rgb.size), inner)
        csum = np.asarray(masked.filter(ImageFilter.GaussianBlur(sig)), dtype=np.float32)
        fill = csum / np.maximum(wsum, 1e-3)[..., None]
        rim = (a > 0) & (np.asarray(inner) == 0) & (wsum > .02)
        out_rgb = np.asarray(rgb, dtype=np.float32).copy()
        out_rgb[rim] = np.clip(fill[rim], 0, 255)
        rgba = Image.fromarray(out_rgb.astype(np.uint8), "RGB").convert("RGBA")
    rgba.putalpha(Image.fromarray(a))
    rgba.save(out)
    return str(out)


def _box_blur(a: np.ndarray, r: int) -> np.ndarray:
    """Three box passes ≈ Gaussian; numpy only."""
    r = max(1, int(r))
    for _ in range(3):
        for ax in (0, 1):
            pad = [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)]
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
            n = c.shape[ax]
            a = (np.take(c, range(2 * r + 1, n), axis=ax) - np.take(c, range(0, n - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a


def _drop_background_rim(alpha: Image.Image, source_path: str) -> Image.Image:
    """Remove mask pixels near the edge whose colour belongs to the local
    background rather than to the subject (bits of the old background the
    segmenter kept between hair strands).  Nearest-local-mean on a band
    along the edge, computed on a working copy."""
    with Image.open(source_path) as im:
        rgb = im.convert("RGB").resize(alpha.size, Image.BILINEAR)
    ws = min(1.0, 900 / max(alpha.size))
    size = (max(1, round(alpha.width * ws)), max(1, round(alpha.height * ws)))
    m = np.asarray(alpha.resize(size, Image.NEAREST)) > 128
    c = np.asarray(rgb.resize(size, Image.BILINEAR), dtype=np.float32)
    subj = max(8, int(min(size) * .03))
    band = max(3, int(min(size) * .025))
    mi = Image.fromarray(m.astype(np.uint8) * 255)
    core = np.asarray(_morph(mi, 2 * band + 1, "erode")) > 0
    outside = ~(np.asarray(_morph(mi, 5, "dilate")) > 0)
    rim = m & ~core
    if not rim.any() or not outside.any() or not core.any():
        return alpha

    def local_mean(region):
        w = _box_blur(region.astype(np.float32), subj)
        s_ = np.stack([_box_blur(c[..., k] * region, subj) for k in range(3)], -1)
        return s_ / np.maximum(w, 1e-4)[..., None], w

    fg, wf = local_mean(core)
    bg, wb = local_mean(outside)
    df = np.linalg.norm(c - fg, axis=-1)
    db = np.linalg.norm(c - bg, axis=-1)
    contrast = np.linalg.norm(fg - bg, axis=-1)
    drop = rim & (wf > .01) & (wb > .01) & (contrast > 25) & (db < .7 * df)
    if not drop.any():
        return alpha
    m2 = m & ~drop
    small = Image.fromarray(m2.astype(np.uint8) * 255).resize(alpha.size, Image.NEAREST)
    return Image.fromarray(np.minimum(np.asarray(small), np.asarray(alpha)))


def assess(mask_path: str, crop: Optional[list[float]] = None) -> dict:
    """Facts a director needs before deciding cut-out vs framed photo."""
    with Image.open(mask_path) as im:
        w, h = im.size
    return {"px": [w, h], "spikiness": spikiness(mask_path), "cut_sides": cut_sides(mask_path, crop)}


def straight_edges(mask_path: str, crop: Optional[list[float]] = None, min_share: float = .035) -> list[dict]:
    """Straight vertical/horizontal runs of the subject's contour INSIDE the
    frame: where segmentation cut a limb along an occluder or a hard source
    edge.  Diagnostic only — straight hair or a sleeve also produce runs, so
    the hard gate does not use it.  A retoucher would never leave them visible (D09).  Runs on the
    frame border are ``cut_sides``' business, not reported here.

    Returns [{"axis": "v"|"h", "at": u, "from": a, "to": b}] in 0..1 of the
    (cropped) frame: for "v" ``at`` is x, from/to are y; for "h" vice versa."""
    with Image.open(mask_path) as im:
        alpha = im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")
    W, H = alpha.size
    if crop and list(crop) != [0, 0, 1, 1]:
        alpha = alpha.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
    ws = min(1.0, 800 / max(alpha.size))
    a = np.asarray(alpha.resize((max(1, round(alpha.width * ws)), max(1, round(alpha.height * ws))), Image.NEAREST)) > 128
    h, w = a.shape
    out = []
    for axis, arr in (("v", a), ("h", a.T)):
        rows, cols = arr.shape            # walk along rows; a vertical edge = same column of transition
        edge = arr[:, 1:] != arr[:, :-1]  # transitions between column j and j+1
        min_len = max(6, int(rows * min_share))
        for j in range(2, cols - 3):      # skip the frame border
            col = edge[:, j]
            if col.sum() < min_len:
                continue
            # longest run of consecutive rows with a transition at exactly this column
            # (±1 px tolerance by OR-ing the neighbours)
            near = col | edge[:, j - 1] | edge[:, j + 1]
            run = best = start = bs = 0
            for i, v in enumerate(near):
                if v:
                    if run == 0:
                        start = i
                    run += 1
                    if run > best:
                        best, bs = run, start
                else:
                    run = 0
            exact = col[bs:bs + best].mean() if best else 0
            if best >= min_len and exact > .6:
                out.append({"axis": axis, "at": round((j + 1) / cols, 4), "from": round(bs / rows, 4),
                            "to": round((bs + best) / rows, 4)})
    # merge duplicates from neighbouring columns
    merged: list[dict] = []
    for e in sorted(out, key=lambda e: (e["axis"], e["at"])):
        if merged and merged[-1]["axis"] == e["axis"] and abs(merged[-1]["at"] - e["at"]) < .01:
            if e["to"] - e["from"] > merged[-1]["to"] - merged[-1]["from"]:
                merged[-1] = e
            continue
        merged.append(e)
    return merged


def cut_segments(mask_path: str, crop: Optional[list[float]] = None, share: float = .008) -> dict[str, tuple[float, float]]:
    """For every side of the (cropped) frame that CUTS the subject: the extent
    (0..1 along the side) of the visible straight cut.

    A side cuts the subject when the subject continues beyond it in the
    source, or when it is the source's own border and the subject reaches
    it (segmenters stop a few px short, so within 1 % counts).  A crop that
    merely touches the top of the hair is not a cut."""
    with Image.open(mask_path) as im:
        full = np.asarray(im.getchannel("A") if im.mode in ("RGBA", "LA") else im.convert("L")) > 128
    H, W = full.shape
    c = list(crop) if crop else [0, 0, 1, 1]
    x0, y0, x1, y1 = int(round(c[0] * W)), int(round(c[1] * H)), int(round(c[2] * W)), int(round(c[3] * H))
    a = full[y0:y1, x0:x1]
    if not a.size:
        return {}
    h, w = a.shape
    bx, by = max(2, int(W * .01)), max(2, int(H * .01))

    def beyond(side):
        """opaque on the far side of the crop line (or the line is the source border)"""
        if side == "left":
            return full[y0:y1, max(0, x0 - bx):x0].any(1) if x0 > bx else None
        if side == "right":
            return full[y0:y1, x1:min(W, x1 + bx)].any(1) if x1 < W - bx else None
        if side == "top":
            return full[max(0, y0 - by):y0, x0:x1].any(0) if y0 > by else None
        return full[y1:min(H, y1 + by), x0:x1].any(0) if y1 < H - by else None

    inside = {"left": a[:, :bx].any(1), "right": a[:, -bx:].any(1), "top": a[:by, :].any(0), "bottom": a[-by:, :].any(0)}
    out = {}
    for side, v in inside.items():
        far = beyond(side)
        cut = v if far is None else (v & far)
        if cut.mean() > share:
            idx = np.nonzero(cut)[0]
            out[side] = (float(idx[0] / len(cut)), float((idx[-1] + 1) / len(cut)))
    return out
