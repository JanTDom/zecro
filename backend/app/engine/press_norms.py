"""Measured press norms (knowledge/press_norms.json) applied to our pages.

The corpus was measured with one instrument (scripts/press_corpus/measure.py)
on thousands of real pages: front pages of ~520 dailies from 40 countries on
several dates, full issues of tabloids, free commuter dailies, regional
dailies, TV guides, news and consumer magazines, and the title's own issues.

``scene_metrics`` measures OUR page the same way (from the scene graph and
its render) and ``norm_report`` says where it sits in the distribution of its
genre: inside p25–p75 = typical, p10–p90 = unusual, outside = atypical.  The
report is a fact for the art director and the editor, not a hard rule: a
title's own grammar (kit) wins over the genre's statistics.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Optional

NORMS = Path(__file__).resolve().parents[1] / "knowledge" / "press_norms.json"

GENRE_KINDS = {
    "G-TABLOID-FRAME": ["pl_free_tabloid", "free_commuter", "uk_tabloid", "tabloid"],
    "G-TABLOID-COLLAGE": ["uk_tabloid", "tabloid", "pl_newspaper"],
    "G-BROADSHEET": ["daily_newspaper|front|format=broadsheet", "modern_daily_full"],
    "G-COMPACT": ["daily_newspaper|front|format=tabloid", "daily_newspaper|front|format=berliner",
                  "free_commuter", "modern_daily_full", "us_local_newspaper"],
    "G-MAGAZINE": ["news_magazine", "consumer_magazine", "pl_magazine"],
    "G-TV": ["pl_tv_guide", "tv_guide"],
    "G-INSIDE": ["modern_daily_full", "uk_tabloid", "free_commuter", "pl_newspaper"],
}
# text_area_share is left out: the corpus sums span boxes (overlaps on
# display type), our scene sums frames — not the same quantity
KEY_METRICS = ["headline_ratio", "headline_max_pt", "body_pt", "headline_blocks", "graphic_share",
               "largest_graphic_share", "paper_share", "saturated_share", "dominant_share"]


def load() -> dict:
    if not NORMS.exists():
        return {}
    return json.loads(NORMS.read_text(encoding="utf-8"))


def norms_for(genre: str, role: str = "front") -> dict[str, Any]:
    data = (load().get("norms") or {})
    out = {}
    for k in GENRE_KINDS.get(genre, []):
        key = k if k.count("|") >= 2 else f"{k}|{role}"
        if key in data:
            out[key] = {m: data[key][m] for m in KEY_METRICS + ["columns", "body_line_chars_median"] if m in data[key]}
            out[key]["pages"] = data[key].get("pages")
            out[key]["titles"] = data[key].get("titles")
    return out


def scene_metrics(scene, png_path: Optional[str] = None) -> dict[str, float]:
    """The corpus instrument's measures, computed on our scene (+ render)."""
    import numpy as np
    W, H = scene.page.trim
    area = W * H
    texts = [e for e in scene.elements if e.text_content and e.style and e.style.font_size_pt]
    chars = Counter()
    for e in texts:
        chars[round(float(e.style.font_size_pt) * 2) / 2] += len(e.text_content)
    body = chars.most_common(1)[0][0] if chars else None
    heads = [e for e in texts if body and float(e.style.font_size_pt) >= body * 1.6 and len(e.text_content) >= 2]
    hmax = max((float(e.style.font_size_pt) for e in heads), default=None)
    stories_with_heads = {e.story_ref for e in heads if e.story_ref}
    m = {"body_pt": body, "headline_max_pt": hmax,
         "headline_ratio": round(hmax / body, 2) if hmax and body else None,
         "headline_blocks": len(stories_with_heads),
         "text_area_share": round(min(1.0, sum(e.frame.w * e.frame.h for e in texts) / area), 3)}
    if png_path:
        from PIL import Image
        im = Image.open(png_path).convert("RGB")
        a = np.asarray(im, dtype=np.float32)
        mx, mn = a.max(2), a.min(2)
        sat = (mx - mn) / np.maximum(mx, 1)
        lum = a.mean(2)
        paper = (lum > np.percentile(lum, 95) - 18) & (sat < .12)
        m["paper_share"] = round(float(paper.mean()), 3)
        m["saturated_share"] = round(float((sat > .35).mean()), 3)
        # graphic share exactly as in the corpus: not paper, not text
        hpx, wpx = lum.shape
        tm = np.zeros_like(paper)
        for e in texts:
            f = e.frame
            tm[max(0, int(f.y / H * hpx)):int((f.y + f.h) / H * hpx) + 1, max(0, int(f.x / W * wpx)):int((f.x + f.w) / W * wpx) + 1] = True
        m["graphic_share_px"] = round(float((~paper & ~tm).mean()), 3)
    photos = [e for e in scene.elements if e.role == "photo"]
    if photos:
        import numpy as np
        g = np.zeros((int(H), int(W)), bool)
        for e in photos:
            f = e.frame
            g[max(0, int(f.y)):int(min(H, f.y + f.h)), max(0, int(f.x)):int(min(W, f.x + f.w))] = True
        m["graphic_share_frames"] = round(float(g.mean()), 3)
        m["largest_graphic_share"] = round(max(min(1.0, e.frame.w * e.frame.h / area) for e in photos), 3)
    if "graphic_share_px" in m:
        m["graphic_share"] = m.pop("graphic_share_px")
    return m


def norm_report(metrics: dict, genre: str, role: str = "front") -> list[dict]:
    rows = []
    for key, d in norms_for(genre, role).items():
        for k, v in metrics.items():
            if k not in KEY_METRICS:
                continue
            dist = d.get(k)
            if v is None or not isinstance(dist, dict):
                continue
            if dist["n"] < 8:
                # a handful of the title's own pages is a range, not a distribution
                lo, hi = dist["p10"], dist["p90"]
                pad = max(abs(hi - lo) * .5, abs(dist["median"]) * .15)
                where = "w zakresie wydań" if lo - pad <= v <= hi + pad else "poza zakresem wydań"
            elif dist["p25"] <= v <= dist["p75"]:
                where = "typowe"
            elif dist["p10"] <= v <= dist["p90"]:
                where = "nietypowe (poza p25–p75)"
            else:
                where = "skrajne (poza p10–p90)"
            rows.append({"grupa": key, "miara": k, "nasza": v, "mediana": dist["median"],
                         "p25_p75": [dist["p25"], dist["p75"]], "ocena": where, "n": dist["n"]})
    return rows


def norm_distance(rows: list[dict]) -> float:
    """How far a page sits from its genre: 0 typical … 2 extreme, summed."""
    w = {"typowe": 0.0, "w zakresie wydań": 0.0, "nietypowe (poza p25–p75)": 1.0,
         "poza zakresem wydań": 2.0, "skrajne (poza p10–p90)": 2.0}
    return float(sum(w.get(r.get("ocena"), 0.0) for r in rows if "error" not in r))
