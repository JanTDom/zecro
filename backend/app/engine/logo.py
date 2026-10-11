"""Logo analysis, palette extraction, vectorisation and masthead geometry.

Deterministic measurements (content box, Lab k-means colours, CMYK, optical
weight) are always computed; Gemini adds a stylistic reading plus palette-role
and font-pairing *proposals* that change nothing until an editor approves.
"""
from __future__ import annotations
import io, re
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from ..models.schemas import LogoProfile, TitleDNA


def rasterize(path: Path, width: int = 1600) -> Optional[Image.Image]:
    ext = path.suffix.lower()
    try:
        if ext == ".svg":
            import resvg_py
            png = bytes(resvg_py.svg_to_bytes(svg_path=str(path), width=width))
            return Image.open(io.BytesIO(png)).convert("RGBA")
        if ext == ".pdf":
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(path)); page = doc[0]
            img = page.render(scale=width / page.get_width()).to_pil().convert("RGBA")
            doc.close()
            arr = np.array(img); white = (arr[..., :3] > 248).all(-1); arr[white, 3] = 0
            return Image.fromarray(arr)
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _rgb_to_cmyk(rgb: tuple[int, int, int]) -> list[float]:
    r, g, b = [c / 255 for c in rgb]
    k = 1 - max(r, g, b)
    if k >= 1:
        return [0.0, 0.0, 0.0, 100.0]
    c, m, y = [(1 - v - k) / (1 - k) for v in (r, g, b)]
    return [round(100 * v, 1) for v in (c, m, y, k)]


def _kmeans_colors(img: Image.Image, k: int = 5) -> list[tuple[str, float]]:
    arr = np.asarray(img.convert("RGBA").resize((200, max(1, int(200 * img.height / max(1, img.width))))))
    px = arr.reshape(-1, 4)
    px = px[px[:, 3] > 128][:, :3].astype(float)
    if not len(px):
        return []
    px = px[~((px > 245).all(1))]  # drop paper white
    if not len(px):
        return [("#ffffff", 1.0)]
    rng = np.random.default_rng(0)
    centers = px[rng.choice(len(px), size=min(k, len(px)), replace=False)]
    for _ in range(15):
        d = ((px[:, None, :] - centers[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        centers = np.array([px[lab == i].mean(0) if (lab == i).any() else centers[i] for i in range(len(centers))])
    counts = np.bincount(lab, minlength=len(centers)) / len(px)
    out = sorted(((("#%02x%02x%02x" % tuple(int(v) for v in c)), float(w)) for c, w in zip(centers, counts)), key=lambda t: -t[1])
    merged: list[tuple[str, float]] = []
    for hexc, w in out:
        if w >= 0.03 and hexc not in [m[0] for m in merged]:
            merged.append((hexc, round(w, 3)))
    return merged


def vectorize(img: Image.Image, out_path: Path) -> Optional[str]:
    try:
        import vtracer
        tmp = out_path.with_suffix(".png")
        img.save(tmp)
        vtracer.convert_image_to_svg_py(str(tmp), str(out_path), colormode="color", hierarchical="stacked", mode="spline",
                                        filter_speckle=4, color_precision=6, corner_threshold=60, path_precision=3)
        return str(out_path)
    except Exception:
        return None


def analyze_logo(path: str | Path, *, asset_ref: str | None = None, variant: str = "primary", vectorize_raster: bool = True) -> LogoProfile:
    p = Path(path)
    vector = p.suffix.lower() in {".svg", ".pdf", ".eps", ".ai"}
    img = rasterize(p)
    ratio = bbox = None
    colors: list[tuple[str, float]] = []
    weight = None
    raster_px = None
    vector_ref = None
    preflight: list[dict] = []
    if img is not None:
        alpha = np.asarray(img.getchannel("A"))
        if not vector and (alpha > 250).all():  # opaque raster: remove paper background
            arr = np.asarray(img).copy()
            bg = np.median(np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]]), axis=0)[:3]
            dist = np.abs(arr[..., :3].astype(int) - bg.astype(int)).sum(-1)
            arr[dist < 40, 3] = 0
            img = Image.fromarray(arr); alpha = arr[..., 3]
        ys, xs = np.nonzero(alpha > 128)
        if len(xs):
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            bbox = [round(x0 / img.width, 4), round(y0 / img.height, 4), round(x1 / img.width, 4), round(y1 / img.height, 4)]
            ratio = (x1 - x0) / max(1, (y1 - y0))
            weight = round(float((alpha[y0:y1, x0:x1] > 128).mean()), 3)
        colors = _kmeans_colors(img)
        if not vector:
            raster_px = [img.width, img.height]
            if vectorize_raster and asset_ref:
                vector_ref = vectorize(img.crop((x0, y0, x1, y1)) if len(xs) else img, p.with_name(p.stem + "_vector.svg"))
    elif p.suffix.lower() == ".svg":
        raw = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'viewBox="([^"]+)"', raw)
        if m and len(m.group(1).split()) == 4:
            vals = [float(v) for v in m.group(1).split()]
            ratio = vals[2] / vals[3] if vals[3] else None
        colors = [(c, 0.0) for c in dict.fromkeys(re.findall(r"#[0-9a-fA-F]{6}", raw))][:6]
    cmyk = [_rgb_to_cmyk(tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))) for h, _ in colors]
    for hexc, c in zip([h for h, _ in colors], cmyk):
        tac = sum(c)
        if tac > 300:
            preflight.append({"level": "WARN", "code": "logo_tac", "message": f"kolor {hexc} → CMYK {c} (TAC {tac:.0f}% > 300%)"})
    if not vector:
        preflight.append({"level": "WARN", "code": "logo_raster", "message": "logo rastrowe — w druku użyj wektora (proponowana wektoryzacja wymaga akceptacji)"})
    layout = "horizontal" if (ratio or 1.0) >= 2.2 else "side" if (ratio or 1.0) < 0.8 else "ears"
    return LogoProfile(asset_ref=asset_ref, variant=variant, aspect_ratio=round(ratio, 4) if ratio else None, content_bbox=bbox,
                       dominant_colors=[h for h, _ in colors], cmyk_colors=cmyk, optical_weight=weight, layout_mode=layout, vector=vector,
                       clear_space_mm=3.0, approved=False, raster_px=raster_px, vector_ref=vector_ref, preflight=preflight)


def ai_logo_analysis(path: str | Path, profile: LogoProfile, *, project_id: Optional[str] = None) -> dict[str, Any]:
    from ..ai.runtime import run_task
    from ..ai.schemas import LogoAI
    from .fonts import families
    img = rasterize(Path(path), 1200)
    if img is None:
        raise ValueError("logo cannot be rasterised for analysis")
    flat = Image.new("RGB", img.size, (255, 255, 255)); flat.paste(img, mask=img.getchannel("A"))
    buf = io.BytesIO(); flat.save(buf, "PNG")
    fams = [f["family"] for f in families(require_polish=True)]
    res = run_task("logo_analysis", "logo_analysis", {"measured": {"aspect_ratio": profile.aspect_ratio, "colors": profile.dominant_colors,
                   "cmyk": profile.cmyk_colors, "optical_weight": profile.optical_weight, "layout_mode": profile.layout_mode},
                   "available_fonts": fams}, LogoAI, images=[{"data": buf.getvalue(), "mime_type": "image/png"}], project_id=project_id)
    data = res.data
    data["font_pairings"] = [fp for fp in data["font_pairings"] if fp["headline_family"] in fams and fp["body_family"] in fams]
    roles = data.get("palette_roles") or {}
    for k, v in list(roles.items()):
        if v and v.lower() not in [c.lower() for c in profile.dominant_colors]:
            roles[k] = None  # only measured colours are allowed
    return {**data, "provenance": res.provenance, "status": "draft"}


def masthead_geometry(dna: TitleDNA, profile: LogoProfile | None, page_width_mm: float, *, zone: str = "front_page") -> dict[str, float | str]:
    grid = dna.grid
    base = max(.1, float(grid.baseline_grid_pt) * .352778)
    usable = page_width_mm - dna.format.margin_left_mm - dna.format.margin_right_mm
    if not profile or not profile.aspect_ratio:
        return {"mode": "horizontal", "x": dna.format.margin_left_mm, "y": dna.format.margin_top_mm, "w": usable, "h": round(max(12, base * 8) / base) * base}
    mode = profile.layout_mode if zone == "front_page" else ("side" if profile.layout_mode == "side" else "horizontal")
    if mode == "horizontal":
        w = usable * 0.86
    elif mode == "ears":
        w = usable * 0.5
    else:
        w = min(usable * 0.22, max(20, profile.min_width_mm or 24))
    h = w / profile.aspect_ratio
    h = max(base * 6, min(h, base * 24))
    h = round(h / base) * base  # snap to baseline grid
    if mode != "side":
        w = min(w, h * profile.aspect_ratio)
    return {"mode": mode, "x": dna.format.margin_left_mm, "y": dna.format.margin_top_mm, "w": round(w, 2), "h": round(h, 2)}
