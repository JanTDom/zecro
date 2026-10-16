"""press_norms.json + press_archetypes.json → press_norms.md (Polish, readable)."""
import json

from analyze import KIND_PL

N = json.load(open("press_norms.json"))
A = json.load(open("press_archetypes.json"))
S = N["summary"]

ROLE = {"front": "pierwsza", "inside": "środek", "back": "ostatnia"}
COLS = [("w_mm", "format szer. mm", 0), ("h_mm", "wys. mm", 0), ("columns", "łamy", 0), ("body_pt", "tekst pt", 1),
        ("body_line_chars_median", "znaki/wiersz", 0), ("headline_max_pt", "tytuł max pt", 0),
        ("headline_ratio", "tytuł ÷ tekst", 1), ("step2", "2. tytuł ÷ 1.", 2), ("headline_blocks", "tematy", 0),
        ("graphic_share", "grafika %", 0), ("largest_graphic_share", "największe zdjęcie %", 0),
        ("paper_share", "białe %", 0), ("saturated_share", "kolor %", 0)]
PCT = {"graphic_share", "largest_graphic_share", "paper_share", "saturated_share"}


def cell(d, key, dec):
    x = d.get(key)
    if not isinstance(x, dict):
        return "—"
    f = (lambda v: f"{v * 100:.0f}") if key in PCT else (lambda v: f"{v:.{dec}f}")
    return f"{f(x['median'])} ({f(x['p25'])}–{f(x['p75'])})"


lines = ["# Normy prasy zmierzone na korpusie (Zecro)", "",
         f"Zmierzono **{S['pages']:,} stron** z **{S['items']:,} wydań**, **{S['titles']} tytułów**, "
         f"**{S['countries']} krajów** jednym przyrządem (`scripts/press_corpus/measure.py`). "
         "Wartości: mediana (p25–p75). Udziały w % powierzchni strony; „białe” to papier bez tekstu i grafiki, "
         "łącznie z marginesami.", "",
         "Typy pism w korpusie: " + ", ".join(f"{KIND_PL.get(k, k)} — {v} str." for k, v in
                                              sorted(S["by_kind"].items(), key=lambda t: -t[1])) + ".", ""]
lines += ["## Normy według typu pisma i roli strony", "",
          "| typ | strona | n | " + " | ".join(c[1] for c in COLS) + " |",
          "|---|---|---|" + "---|" * len(COLS)]
order = ["daily_newspaper", "modern_daily_full", "us_local_newspaper", "world_newspaper", "free_commuter",
         "pl_free_tabloid", "uk_tabloid", "tabloid", "pl_newspaper", "pl_tv_guide", "tv_guide", "news_magazine",
         "pl_magazine", "consumer_magazine"]
for k in order:
    for role in ("front", "inside", "back"):
        d = N["norms"].get(f"{k}|{role}")
        if not d:
            continue
        lines.append(f"| {KIND_PL.get(k, k)} | {ROLE[role]} | {d['pages']} | " +
                     " | ".join(cell(d, c, dec) for c, _, dec in COLS) + " |")
lines += ["", "## Pierwsze strony dzienników według formatu", "",
          "| format | n | " + " | ".join(c[1] for c in COLS) + " |", "|---|---|" + "---|" * len(COLS)]
for key, d in N["norms"].items():
    if key.startswith("daily_newspaper|front|format="):
        lines.append(f"| {key.split('=')[1]} | {d['pages']} | " + " | ".join(cell(d, c, dec) for c, _, dec in COLS) + " |")
lines += ["", "## Pierwsze strony dzienników według regionu", "",
          "| region | n | " + " | ".join(c[1] for c in COLS) + " |", "|---|---|" + "---|" * len(COLS)]
for key, d in N["norms"].items():
    if key.startswith("daily_newspaper|front|region="):
        lines.append(f"| {key.split('=')[1]} | {d['pages']} | " + " | ".join(cell(d, c, dec) for c, _, dec in COLS) + " |")
lines += ["", "## Pierwsza strona a środek (mediany, pełne wydania)", "",
          "| typ | tytuł÷tekst 1./środek | tematy 1./środek | największe zdjęcie % 1./środek | białe % 1./środek |",
          "|---|---|---|---|---|"]
for k, d in N.get("front_vs_inside", {}).items():
    g = lambda m, pct=False: (f"{d[m]['front'] * (100 if pct else 1):.{0 if pct else 1}f} / "
                              f"{d[m]['inside'] * (100 if pct else 1):.{0 if pct else 1}f}") if m in d else "—"
    lines.append(f"| {KIND_PL.get(k, k)} | {g('headline_ratio')} | {g('headline_blocks')} | "
                 f"{g('largest_graphic_share', True)} | {g('paper_share', True)} |")
lines += ["", "## Archetypy pierwszych stron (klasteryzacja, bez założeń z góry)", ""]
for a in A:
    m = a["median"]
    lines.append(f"- **{a['pages']} stron** — tytuł {m['headline_max_pt']:.0f} pt (×{m['headline_ratio']:.1f} tekstu), "
                 f"tematów {m['headline_blocks']:.0f}, największe zdjęcie {m['largest_graphic_share'] * 100:.0f} %, "
                 f"grafika {m['graphic_share'] * 100:.0f} %, białe {m['paper_share'] * 100:.0f} %, kolor "
                 f"{m['saturated_share'] * 100:.0f} %, szer. tytułu {m['largest_headline_width_share'] * 100:.0f} % strony. "
                 f"Typy: {', '.join(f'{KIND_PL.get(k, k)} {n}' for k, n in a['kinds'][:3])}. "
                 f"Przykłady: {'; '.join(a['exemplars'][:5])}.")
open("press_norms.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines[:12]))
