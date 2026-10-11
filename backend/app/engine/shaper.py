"""Typesetting core: HarfBuzz shaping + Polish hyphenation + Knuth–Plass.

The same line breaks are used to *measure* (copyfit, critic, AI headline
fitting) and to *draw* (production PDF typesetter), so a measured fit is the
printed fit.  Without a font file the module returns ``status="estimate"``.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import math
import re
from typing import Optional

PT_PER_MM = 72.0 / 25.4
FEATURES = {"kern": True, "liga": False, "clig": False}
LETTER_STRETCH = 0.025   # max +2.5 % tracking at ratio 1 (newspaper justification)
LETTER_SHRINK = 0.015
WORD_STRETCH = 0.5
WORD_SHRINK = 0.2


@dataclass
class ShapedLine:
    text: str
    width_pt: float
    hyphenated: bool = False
    ratio: float = 0.0           # Knuth–Plass adjustment ratio (justification)
    words: list[tuple[str, float]] = field(default_factory=list)  # (word, natural width)
    last: bool = False


@dataclass
class ShapeResult:
    status: str
    lines: list[ShapedLine] = field(default_factory=list)
    line_count: int = 0
    font_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    overfull: bool = False
    widows: int = 0
    orphans: int = 0


# ---------------------------------------------------------------- shaping
@lru_cache(maxsize=64)
def _hb_font(path: str):
    import uharfbuzz as hb
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    font = hb.Font(face)
    return font, face.upem


@lru_cache(maxsize=200_000)
def advance(text: str, path: str) -> float:
    """Advance of ``text`` in font units / upem (multiply by size in pt)."""
    import uharfbuzz as hb
    font, upem = _hb_font(path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, FEATURES)
    return sum(p.x_advance for p in buf.glyph_positions) / float(upem)


def glyph_offsets(text: str, path: str) -> list[float]:
    """Pen x position (in em) for each character, from HarfBuzz clusters."""
    import uharfbuzz as hb
    font, upem = _hb_font(path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, FEATURES)
    xs, pen = {}, 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        xs.setdefault(info.cluster, pen / upem)
        pen += pos.x_advance
    out, last = [], 0.0
    for i in range(len(text)):
        last = xs.get(i, last)
        out.append(last)
    return out


def width_pt(text: str, size: float, path: Optional[str]) -> float:
    if path and Path(path).exists():
        return advance(text, path) * size
    return len(text) * size * 0.48


def chars_per_line(width_mm: float, size_pt: float, font_path: Optional[str]) -> int:
    sample = "Rada miasta przyjęła uchwałę o zieleni, a mieszkańcy ogłosili protest ŁÓDŹ"
    avg = width_pt(sample, size_pt, font_path) / len(sample)
    return max(4, int(width_mm * PT_PER_MM / max(0.1, avg)))


# ---------------------------------------------------------------- hyphenation
@lru_cache(maxsize=1)
def _pyphen():
    import pyphen
    return pyphen.Pyphen(lang="pl_PL", left=2, right=3)


@lru_cache(maxsize=50_000)
def hyphen_points(word: str) -> tuple[int, ...]:
    core = re.match(r"^([\W_]*)(.*?)([\W_]*)$", word)
    lead, body, _ = core.groups() if core else ("", word, "")
    if len(body) < 6 or not body.isalpha() or body.isupper():
        return ()
    try:
        return tuple(len(lead) + p for p in _pyphen().positions(body))
    except Exception:
        return ()


# ---------------------------------------------------------------- Knuth–Plass
@dataclass
class _Item:
    kind: str          # box | glue | penalty
    width: float
    stretch: float = 0.0
    shrink: float = 0.0
    penalty: float = 0.0
    flagged: bool = False
    text: str = ""


INF = 10_000


def _items(paragraph: str, size: float, path: Optional[str], hyphenate: bool) -> list[_Item]:
    space = width_pt(" ", size, path)
    hyph = width_pt("-", size, path)
    items: list[_Item] = []
    words = [w for w in re.split(r"[ \t]+", paragraph.strip()) if w]
    for i, word in enumerate(words):
        points = hyphen_points(word) if hyphenate else ()
        start = 0
        for p in points:
            bw = width_pt(word[start:p], size, path)
            items.append(_Item("box", bw, stretch=bw * LETTER_STRETCH, shrink=bw * LETTER_SHRINK, text=word[start:p]))
            items.append(_Item("penalty", hyph, penalty=50, flagged=True, text="-"))
            start = p
        bw = width_pt(word[start:], size, path)
        items.append(_Item("box", bw, stretch=bw * LETTER_STRETCH, shrink=bw * LETTER_SHRINK, text=word[start:]))
        if i < len(words) - 1:
            items.append(_Item("glue", space, stretch=space * 0.5, shrink=space * 0.2, text=" "))
    items.append(_Item("glue", 0, stretch=INF))
    items.append(_Item("penalty", 0, penalty=-INF))
    return items


def _break(items: list[_Item], line_w: float, tolerance: float = 2.5) -> Optional[list[int]]:
    sums_w = [0.0]; sums_y = [0.0]; sums_z = [0.0]
    for it in items:
        sums_w.append(sums_w[-1] + (it.width if it.kind != "penalty" else 0))
        sums_y.append(sums_y[-1] + (it.stretch if it.kind != "penalty" else 0))
        sums_z.append(sums_z[-1] + (it.shrink if it.kind != "penalty" else 0))
    active = [(0, 0, 0.0, None, False)]  # (pos, line, demerits, prev_node_index, flagged)
    nodes = [(0, 0, 0.0, None, False)]
    active_idx = [0]
    for b, it in enumerate(items):
        legal = (it.kind == "penalty" and it.penalty < INF) or (it.kind == "glue" and b > 0 and items[b - 1].kind == "box")
        if not legal:
            continue
        best: dict[int, tuple[float, int]] = {}
        still = []
        for ai in active_idx:
            pos, line, dem, _, fl = nodes[ai]
            start = pos + 1 if pos else 0
            while start < len(items) and items[start].kind in {"glue", "penalty"} and pos:
                start += 1
            w = sums_w[b] - sums_w[start] + (it.width if it.kind == "penalty" else 0)
            if w < line_w:
                y = sums_y[b] - sums_y[start]
                r = (line_w - w) / y if y > 0 else INF
            elif w > line_w:
                z = sums_z[b] - sums_z[start]
                r = (line_w - w) / z if z > 0 else -INF
            else:
                r = 0.0
            if r < -1 or (it.kind == "penalty" and it.penalty == -INF):
                pass
            else:
                still.append(ai)
            if -1 <= r <= tolerance:
                badness = 100 * abs(r) ** 3
                p = it.penalty if it.kind == "penalty" else 0
                d = (1 + badness + (p if p > 0 else 0)) ** 2 - (p ** 2 if -INF < p < 0 else 0)
                if fl and it.kind == "penalty" and it.flagged:
                    d += 3000
                total = dem + d
                if line not in best or total < best[line][0]:
                    best[line] = (total, ai)
            elif r < -1:
                pass
        active_idx = still
        for line, (total, ai) in best.items():
            nodes.append((b, line + 1, total, ai, bool(it.kind == "penalty" and it.flagged)))
            active_idx.append(len(nodes) - 1)
        if not active_idx:
            return None
    final = [i for i in active_idx if nodes[i][0] == len(items) - 1]
    if not final:
        return None
    cur = min(final, key=lambda i: nodes[i][2])
    breaks = []
    while cur is not None and nodes[cur][0] != 0:
        breaks.append(nodes[cur][0]); cur = nodes[cur][3]
    return list(reversed(breaks))


def _greedy(items: list[_Item], line_w: float) -> list[int]:
    breaks, w = [], 0.0
    last_glue = None
    for i, it in enumerate(items):
        if it.kind == "box":
            w += it.width
            if w > line_w and last_glue is not None:
                breaks.append(last_glue); w = sum(x.width for x in items[last_glue + 1:i + 1] if x.kind == "box")
                last_glue = None
        elif it.kind == "glue":
            if it.stretch >= INF:
                continue
            last_glue = i; w += it.width
    breaks.append(len(items) - 1)
    return breaks


def _lines_from(items: list[_Item], breaks: list[int], line_w: float) -> list[ShapedLine]:
    lines, start = [], 0
    for n, b in enumerate(breaks):
        seg = items[start:b + (1 if items[b].kind == "penalty" and items[b].flagged else 0)]
        text, words, cur, cur_w = "", [], "", 0.0
        for it in seg:
            if it.kind == "box":
                cur += it.text; cur_w += it.width
            elif it.kind == "glue" and it.stretch < INF:
                if cur:
                    words.append((cur, cur_w)); cur, cur_w = "", 0.0
            elif it.kind == "penalty" and it.flagged and it is items[b]:
                cur += "-"; cur_w += it.width
        if cur:
            words.append((cur, cur_w))
        natural = sum(w for _, w in words) + sum(i.width for i in seg if i.kind == "glue" and i.stretch < INF)
        stretch = sum(i.stretch for i in seg if i.kind != "penalty" and i.stretch < INF)
        shrink = sum(i.shrink for i in seg if i.kind != "penalty" and i.stretch < INF)
        ratio = (line_w - natural) / stretch if natural < line_w and stretch else ((line_w - natural) / shrink if natural > line_w and shrink else 0.0)
        is_last = n == len(breaks) - 1
        lines.append(ShapedLine(" ".join(w for w, _ in words), natural, items[b].kind == "penalty" and items[b].flagged,
                                0.0 if is_last else ratio, words, is_last))
        start = b + 1
        while start < len(items) and items[start].kind in {"glue", "penalty"} and items[start].stretch < INF:
            start += 1
    return lines


@lru_cache(maxsize=4096)
def _shape_paragraph(paragraph: str, width: float, size: float, path: Optional[str], hyphenate: bool) -> tuple:
    items = _items(paragraph, size, path, hyphenate)
    breaks = None
    for tol in (1.5, 3.0, 6.0, 20.0):
        breaks = _break(items, width, tol)
        if breaks:
            break
    lines = _lines_from(items, breaks or _greedy(items, width), width)
    return tuple(lines)


def shape_text(text: str, *, width_pt: float, font_size_pt: float = 9.5, leading_pt: Optional[float] = None,
               font_path: Optional[str] = None, language: str = "pl", max_lines: Optional[int] = None,
               widow_lines: int = 0, orphan_lines: int = 0, hyphenate: bool = True) -> ShapeResult:
    if width_pt <= 0:
        return ShapeResult(status="unavailable", warnings=["width must be positive"])
    measured = bool(font_path and Path(font_path).exists())
    path = font_path if measured else None
    lines: list[ShapedLine] = []
    widows = orphans = 0
    for paragraph in [p for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]:
        plines = list(_shape_paragraph(paragraph, float(width_pt), float(font_size_pt), path, hyphenate and language.startswith("pl")))
        if len(plines) > 1 and len(plines[-1].text.split()) == 1 and len(plines[-1].text) < 6:
            widows += 1
        lines.extend(plines)
    warnings = []
    overfull = any(l.width_pt > width_pt * 1.0001 and len(l.words) == 1 for l in lines)
    if max_lines is not None and len(lines) > max_lines:
        warnings.append(f"text needs {len(lines)} lines; frame holds {max_lines}")
    if not measured:
        warnings.append("font file unavailable; using deterministic estimate")
    return ShapeResult(status="measured" if measured else "estimate", lines=lines, line_count=len(lines), font_path=font_path,
                       warnings=warnings, overfull=overfull, widows=widows, orphans=orphans)


HYPHENATE_BELOW_PT = 14.0  # display type (headlines) is never hyphenated


def hyphenate_for(size_pt: float) -> bool:
    return float(size_pt) < HYPHENATE_BELOW_PT


def measure_text(text: str, width_mm: float, *, font_size_pt: float = 9.5, leading_pt: Optional[float] = None,
                 font_path: Optional[str] = None, language: str = "pl", height_mm: Optional[float] = None) -> ShapeResult:
    leading = leading_pt or font_size_pt * 1.2
    max_lines = int(float(height_mm) * PT_PER_MM / leading + 1e-6) if height_mm else None
    return shape_text(text, width_pt=float(width_mm) * PT_PER_MM, font_size_pt=font_size_pt, leading_pt=leading,
                      font_path=font_path, language=language, max_lines=max_lines, hyphenate=hyphenate_for(font_size_pt))


def fill_columns(text: str, *, width_mm: float, height_mm: float, columns: int, gutter_mm: float, font_size_pt: float,
                 leading_pt: float, font_path: Optional[str]) -> dict:
    col_w = (width_mm - (columns - 1) * gutter_mm) / max(1, columns)
    shaped = measure_text(text, col_w, font_size_pt=font_size_pt, leading_pt=leading_pt, font_path=font_path)
    per_col = max(1, int(height_mm * PT_PER_MM / leading_pt + 1e-6))
    capacity = per_col * columns
    return {"column_width_mm": col_w, "lines_per_column": per_col, "capacity": capacity, "lines": shaped.line_count,
            "overset_lines": max(0, shaped.line_count - capacity), "status": shaped.status, "shaped": shaped}
