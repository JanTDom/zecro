"""Turn page measurements into press knowledge.

Inputs : corpus_ff.jsonl (front pages, 520 titles × dates), corpus_ia*.jsonl
         (full issues of many kinds), corpus_wukadka.jsonl (the title's own).
Outputs: press_norms.json  — distributions per kind × page role (+ formats)
         press_archetypes.json — front-page archetypes found by clustering
         press_norms.md    — readable summary (Polish) for the rulebook
"""
from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

METRICS = ["w_mm", "h_mm", "columns", "column_pitch_mm", "gutter_mm", "body_pt", "body_leading_pt",
           "body_line_chars_median", "headline_max_pt", "headline_ratio", "step2", "step3", "headline_blocks",
           "largest_headline_width_share", "largest_headline_y_share", "text_area_share", "graphic_share",
           "largest_graphic_share", "image_boxes", "paper_share", "saturated_share", "dark_share",
           "dominant_share", "font_families", "vector_rules", "chars"]

KIND_PL = {
    "daily_newspaper": "dzienniki (pierwsze strony, 40 krajów)",
    "pl_free_tabloid": "Wukadka (bezpłatny tabloid PL)",
    "pl_tv_guide": "programy TV (PL)", "tv_guide": "TV Guide (USA)",
    "pl_newspaper": "gazety PL", "pl_magazine": "tygodniki/magazyny PL",
    "tabloid": "tabloidy (różne)", "uk_tabloid": "tabloidy brytyjskie",
    "free_commuter": "bezpłatne dzienniki Metro", "us_local_newspaper": "lokalne gazety USA",
    "world_newspaper": "gazety (świat, różne)", "modern_daily_full": "dzienniki — pełne wydania",
    "news_magazine": "newsmagazyny", "consumer_magazine": "magazyny konsumenckie",
}


def load() -> pd.DataFrame:
    rows = []
    seen_items: set = set()
    for f in sorted(glob.glob("corpus_*.jsonl")):
        for line in open(f):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error") or not r.get("pages"):
                continue
            item = r.get("identifier") or f"{r.get('slug') or r.get('file')}:{r.get('date', '')}"
            if (item, f.endswith("_v2.jsonl")) in seen_items:
                continue                      # two crawlers met on the same issue
            seen_items.add((item, f.endswith("_v2.jsonl")))
            for p in r["pages"]:
                if p.get("error"):
                    continue
                steps = p.get("headline_steps") or []
                rows.append({**{k: p.get(k) for k in METRICS if k not in ("step2", "step3")},
                             "step2": steps[1] if len(steps) > 1 else None,
                             "step3": steps[2] if len(steps) > 2 else None,
                             "format": p.get("format"), "source_kind": p.get("source_kind"),
                             "dominant_kind": p.get("dominant_kind"), "body_serif": p.get("body_serif"),
                             "head_serif": p.get("head_serif"), "body_font": p.get("body_font"),
                             "head_font": p.get("head_font"),
                             "page_role": p.get("page_role"), "page_index": p.get("page_index"),
                             "page_count": p.get("page_count"), "kind": r.get("kind"), "source": r.get("source"),
                             "measure_version": p.get("measure_version"),
                             "title": r.get("title"), "country": r.get("country"), "region": r.get("region"),
                             "item": item})
    df = pd.DataFrame(rows)
    # line/column measures are reliable only from instrument v2 (word spans joined into lines)
    v2 = df["measure_version"] == 2
    for c in ("columns", "column_pitch_mm", "gutter_mm", "body_line_chars_median"):
        df.loc[~v2, c] = np.nan
    # Freedom Forum v2 re-measure replaces the v1 record of the same front page
    df = df.sort_values("measure_version", na_position="first").drop_duplicates(
        subset=["item", "page_index"], keep="last") if "measure_version" in df else df
    for c in METRICS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def drop_non_press(df: pd.DataFrame) -> pd.DataFrame:
    """Items that are not periodicals (books, catalogues swept in by search):
    single-column body on most pages and almost no headline blocks."""
    g = df.groupby("item").agg(col=("columns", "median"), hb=("headline_blocks", "median"),
                               pc=("page_count", "max"))
    bad = set(g[((g.col <= 1) & (g.hb <= 1)) | (g.pc > 400)].index)
    import re
    junk = re.compile(r"(manga|train|game|angora|neuronowe|lubeckiego|pisma t\.|gg art|catalog|jstor|ebook|"
                      r"pdfdrive|kompendium|secret service|top secret|cwaniacz|podcast)", re.I)
    bad |= set(df[df.title.fillna("").str.contains(junk)].item)
    bad = list(bad)
    return df[~df.item.isin(bad)].copy(), list(bad)


def dist(s: pd.Series, min_n: int = 5) -> dict | None:
    s = s.dropna()
    if len(s) < min_n:
        return None
    q = s.quantile([.1, .25, .5, .75, .9])
    return {"n": int(len(s)), "p10": round(float(q[.1]), 3), "p25": round(float(q[.25]), 3),
            "median": round(float(q[.5]), 3), "p75": round(float(q[.75]), 3), "p90": round(float(q[.9]), 3)}


def norms(df: pd.DataFrame) -> dict:
    out = {}
    for (kind, role), g in df.groupby(["kind", "page_role"]):
        own = kind == "pl_free_tabloid"          # the title's own issues: few pages, all of them count
        if len(g) < (3 if own else 8):
            continue
        d = {m: dist(g[m], 3 if own else 5) for m in METRICS}
        d = {k: v for k, v in d.items() if v}
        d["pages"] = int(len(g))
        d["items"] = int(g.item.nunique())
        d["titles"] = int(g.title.nunique())
        d["formats"] = dict(Counter(g.format.dropna()).most_common())
        d["source_kinds"] = dict(Counter(g.source_kind.dropna()).most_common())
        d["dominant_kind"] = dict(Counter(g.dominant_kind.dropna()).most_common())
        bs = g.body_serif.dropna()
        hs = g.head_serif.dropna()
        if len(bs) >= 5:
            d["body_serif_share"] = round(float(bs.astype(float).mean()), 3)
        if len(hs) >= 5:
            d["head_serif_share"] = round(float(hs.astype(float).mean()), 3)
        d["top_body_fonts"] = [f for f, _ in Counter(g.body_font.dropna()).most_common(8)]
        d["top_head_fonts"] = [f for f, _ in Counter(g.head_font.dropna()).most_common(8)]
        out[f"{kind}|{role}"] = d
    # daily fronts by format and by region
    ff = df[df.kind == "daily_newspaper"]
    for key, col in (("format", "format"), ("region", "region")):
        for v, g in ff.groupby(col):
            if len(g) >= 15:
                d = {m: dist(g[m]) for m in METRICS}
                out[f"daily_newspaper|front|{key}={v}"] = {**{k: x for k, x in d.items() if x}, "pages": int(len(g)),
                                                           "titles": int(g.title.nunique())}
    return out


ARCH_FEATURES = ["headline_ratio", "headline_blocks", "largest_graphic_share", "graphic_share", "text_area_share",
                 "paper_share", "saturated_share", "largest_headline_width_share"]


def archetypes(df: pd.DataFrame, k: int = 6) -> list[dict]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    fr = df[(df.page_role == "front")].dropna(subset=ARCH_FEATURES).copy()
    X = StandardScaler().fit_transform(np.log1p(fr[ARCH_FEATURES].clip(lower=0)))
    km = KMeans(n_clusters=k, n_init=20, random_state=7).fit(X)
    fr["cluster"] = km.labels_
    out = []
    for c, g in fr.groupby("cluster"):
        med = {f: round(float(g[f].median()), 3) for f in ARCH_FEATURES + ["columns", "body_pt", "headline_max_pt"]}
        kinds = Counter(g.kind).most_common(6)
        formats = Counter(g.format).most_common(4)
        # exemplars: closest to the centre
        dd = np.linalg.norm(X[fr.cluster.values == c] - km.cluster_centers_[c], axis=1)
        ex = g.iloc[np.argsort(dd)[:8]]
        out.append({"cluster": int(c), "pages": int(len(g)), "median": med, "kinds": kinds, "formats": formats,
                    "exemplars": [f"{t} ({k})" for t, k in zip(ex.title, ex.kind)]})
    return sorted(out, key=lambda a: -a["pages"])


def front_vs_inside(df: pd.DataFrame) -> dict:
    out = {}
    for kind, g in df[df.source != "freedomforum"].groupby("kind"):
        f, i = g[g.page_role == "front"], g[g.page_role == "inside"]
        if len(f) >= 5 and len(i) >= 20:
            out[kind] = {m: {"front": round(float(f[m].median()), 3), "inside": round(float(i[m].median()), 3)}
                         for m in ("headline_ratio", "headline_blocks", "largest_graphic_share", "graphic_share",
                                   "text_area_share", "paper_share", "columns", "dominant_share")
                         if f[m].notna().sum() >= 5 and i[m].notna().sum() >= 10}
    return out


if __name__ == "__main__":
    df = load()
    df, dropped = drop_non_press(df)
    print("pages", len(df), "items", df.item.nunique(), "titles", df.title.nunique(), "dropped items", len(dropped))
    print(df.groupby(["kind", "page_role"]).size().unstack(fill_value=0))
    n = norms(df)
    a = archetypes(df)
    fi = front_vs_inside(df)
    summary = {"pages": int(len(df)), "items": int(df.item.nunique()), "titles": int(df.title.nunique()),
               "countries": int(df.country.nunique()), "dropped_non_press_items": dropped,
               "by_kind": {k: int(v) for k, v in df.groupby("kind").size().items()}}
    json.dump({"summary": summary, "norms": n, "front_vs_inside": fi}, open("press_norms.json", "w"),
              ensure_ascii=False, indent=1)
    json.dump(a, open("press_archetypes.json", "w"), ensure_ascii=False, indent=1)
    for x in a:
        print(x["pages"], x["median"], x["kinds"][:3], x["exemplars"][:4])
