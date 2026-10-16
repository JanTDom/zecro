"""Fill every text frame exactly: the layout decides, the copy adapts.

Frames are fixed by the generator.  This pass makes each one look composed:

* labels/chips/stamps — inset, vertical centring, one line, sized to the frame;
* headlines — the largest size whose measured lines fit the inner box, never
  a stranded last word; display headlines also fill the width;
* running copy (body/deck/lead) — the text is made to fill 90–100 % of the
  frame:
    - ``copy_mode="placeholder"`` (tests, proofs): Polish placeholder copy
      ("tekst markowany") sized to the frame's measured capacity;
    - ``copy_mode="source"`` (use): longer source is shortened by the
      source-bound editor; shorter source is first extended with further
      source sentences of the same story, and only then recorded as an AI
      expansion request (``copy_requests``) that the copy editor fulfils
      after generation.  Nothing is invented locally.

Measurements use the same font files and shaper as the PDF typesetter.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

from .copyfit import estimate_text_capacity
from .display_headline import has_stranded_headline_word
from .shapes import inscribed_inset, is_rect, text_box

PT = 0.352778
FILL_MIN = .90
PLACEHOLDER_SENTENCES = (
    "Tu znajdzie się tekst artykułu przygotowany przez redakcję.",
    "Akapit pokazuje rytm łamu, długość wierszy i miejsce na przenoszenie wyrazów.",
    "Zdania mają naturalną polską długość, aby skład był oceniany na realnym materiale.",
    "Redaktor zastąpi ten fragment właściwą treścią przed wysłaniem strony do druku.",
    "Kolejne zdanie wypełnia ramkę, żeby sprawdzić światło, wdowy i bękarty.",
    "Tekst markowany nie jest informacją i nie może trafić do wydania.",
    "W tym miejscu autor rozwinie wątek, doda cytat albo kontekst wydarzenia.",
    "Szerokość łamu i stopień pisma zostały dobrane przez generator układu.",
)


def placeholder_text(words: int, seed: int = 0) -> str:
    out: list[str] = []
    index = seed
    while len(" ".join(out).split()) < words:
        out.append(PLACEHOLDER_SENTENCES[index % len(PLACEHOLDER_SENTENCES)])
        index += 1
    tokens = " ".join(out).split()[:max(1, words)]
    text = " ".join(tokens)
    return text if text.endswith((".", "!", "?")) else text.rstrip(",;:") + "."


def _leading(element) -> float:
    st = element.style
    size = float(st.font_size_pt or 9.5)
    return float(st.line_height_pt or size * 1.18)


def _bold(element) -> bool:
    return str(element.style.font_weight or "") in ("bold", "600", "700", "800", "900")


def measure(element, text: Optional[str] = None, *, gutter_mm: float = 4.0):
    st = element.style
    _, _, w, h = text_box(element)
    return estimate_text_capacity(text if text is not None else (element.text_content or ""), w, h,
                                  max(1, int(st.columns or 1)), float(st.font_size_pt or 9.5), _leading(element),
                                  font_family=st.font_family, bold=_bold(element), gutter_mm=gutter_mm)


def fill_ratio(element, *, gutter_mm: float = 4.0) -> float:
    report = measure(element, gutter_mm=gutter_mm)
    return report.estimated_lines / max(1, report.capacity_lines)


def _shape_lines(element, text: str, size: float):
    from .fonts import resolve_font
    from .shaper import shape_text
    _, _, w, _ = text_box(element)
    path = resolve_font(element.style.font_family, bold=_bold(element), text=text)
    shaped = shape_text(text.upper() if element.style.case == "upper" else text, width_pt=w / PT,
                        font_size_pt=size, leading_pt=size * 1.06, font_path=path, hyphenate=False)
    return shaped


def fit_headline(element, *, min_pt: float, max_pt: float, max_lines: int = 4) -> dict[str, Any]:
    """Largest size whose measured lines fit the inner box (no stranded word)."""
    text = element.text_content or ""
    _, _, w, h = text_box(element)
    best = None
    lo, hi = min_pt, max_pt
    for _ in range(18):
        size = (lo + hi) / 2
        shaped = _shape_lines(element, text, size)
        lines = [line.text for line in shaped.lines]
        height = (len(lines) * size * 1.06) * PT
        natural = max((line.width_pt for line in shaped.lines), default=0.0) * PT
        fits = (shaped.status != "unavailable" and not shaped.overfull and len(lines) <= max_lines
                and natural <= w * .97
                and height <= h - .4 and (len(lines) == 1 or not has_stranded_headline_word(lines)))
        if fits:
            # The hard gate's copyfit estimator must agree with the shaper.
            st = element.style
            fits = estimate_text_capacity(text, w, h, 1, size, size * 1.06, font_family=st.font_family,
                                          bold=_bold(element)).passes
        if fits:
            best = (size, shaped)
            lo = size
        else:
            hi = size
    if not best:
        return {"status": "unchanged"}
    size, shaped = best
    size = math.floor(size * 100) / 100
    element.style.font_size_pt = size
    element.style.line_height_pt = math.floor(size * 106) / 100
    widest = max((line.width_pt for line in shaped.lines), default=0.0) * PT
    used_h = len(shaped.lines) * size * 1.06 * PT
    return {"status": "fitted", "size_pt": round(size, 2), "lines": len(shaped.lines),
            "width_fill": round(widest / max(1e-6, w), 3), "height_fill": round(used_h / max(1e-6, h), 3)}


def _balanced_breaks(words: list[str], widths: list[float], space: float, n: int,
                     allow_single_words: bool = False) -> Optional[list[list[str]]]:
    """Split words into n lines minimising the widest line (DP); no stranded word."""
    if n > len(words):
        return None
    m = len(words)
    prefix = [0.0]
    for w in widths:
        prefix.append(prefix[-1] + w)

    def span(i, j):  # words[i:j]
        return prefix[j] - prefix[i] + space * (j - i - 1)

    import functools

    @functools.lru_cache(maxsize=None)
    def best(i, k):
        if k == 1:
            return span(i, m), (m,)
        result = None
        for j in range(i + 1, m - k + 2):
            rest = best(j, k - 1)
            if rest is None:
                continue
            value = max(span(i, j), rest[0])
            if result is None or value < result[0]:
                result = (value, (j,) + rest[1])
        return result

    found = best(0, n)
    if not found:
        return None
    lines, start = [], 0
    for end in found[1]:
        lines.append(words[start:end])
        start = end
    if n > 1 and not allow_single_words and has_stranded_headline_word([" ".join(line) for line in lines]):
        return None
    return lines


def fit_display_fill(element, *, min_pt: float, max_pt: float, max_lines: int = 4,
                     families: Optional[list[str]] = None, allow_single_words: bool = False) -> dict[str, Any]:
    """Choose line count + size that fill the plate in *both* directions.

    The layout fixes the plate; the headline is re-broken (balanced lines,
    never a stranded word) and sized so it fills the width and the height as
    much as possible at the same time.
    """
    from .fonts import resolve_font
    from .shaper import width_pt
    text = " ".join((element.text_content or "").split())
    if element.style.case == "upper":
        measured_text = text.upper()
    else:
        measured_text = text
    words = measured_text.split()
    if not words:
        return {"status": "unchanged"}
    _, _, w, h = text_box(element)
    best = None
    # The typeface is part of the fit: a condensed cut fills a tall plate, a
    # wide cut fills a long bar.  Candidates come from Title DNA.
    from .fonts import resolve_face

    def genuine(family: Optional[str]) -> bool:
        # Only typefaces that really exist in the library compete; a name
        # that silently falls back to another face would fake the choice.
        face = resolve_face(family, weight=700 if _bold(element) else 400, text=measured_text) if family else None
        names = [part.strip().lower() for part in str(family or "").split(",")]
        return bool(face and str(face.get("family", "")).lower() in names)

    candidates = [element.style.font_family] + [f for f in (families or []) if genuine(f)]
    for family in list(dict.fromkeys(candidates)):
        path = resolve_font(family, bold=_bold(element), text=measured_text)
        if not path:
            continue
        unit = [(width_pt(word, 100.0, path) / 100.0) for word in words]
        space = (width_pt(" ", 100.0, path) / 100.0)
        for n in range(1, min(max_lines, len(words)) + 1):
            lines = _balanced_breaks(words, unit, space, n, allow_single_words)
            if not lines:
                continue
            widest_unit = max((width_pt(" ".join(line), 100.0, path) / 100.0) for line in lines)
            size = min(max_pt, (w * .94) / PT / max(1e-6, widest_unit), (h - .5) / PT / (n * 1.06))
            if size < min_pt:
                continue
            width_fill = widest_unit * size * PT / w
            height_fill = n * size * 1.06 * PT / h
            score = width_fill * height_fill + .02 * size / max_pt
            if best is None or score > best[0]:
                best = (score, n, size, lines, width_fill, height_fill, family)
    if not best:
        return fit_headline(element, min_pt=min_pt, max_pt=max_pt, max_lines=max_lines)
    _, n, size, lines, width_fill, height_fill, family = best
    element.style.font_family = family
    original_words = text.split()
    rebuilt, index = [], 0
    for line in lines:
        rebuilt.append(" ".join(original_words[index:index + len(line)]))
        index += len(line)
    size = math.floor(size * 100) / 100
    st = element.style
    from .copyfit import estimate_text_capacity as _est
    while size > min_pt and not _est("\n".join(rebuilt), w, h, 1, size, size * 1.06, font_family=st.font_family,
                                       bold=_bold(element)).passes:
        size = math.floor(size * 97) / 100
    element.text_content = "\n".join(rebuilt)
    st.font_size_pt = size
    st.line_height_pt = math.floor(size * 106) / 100
    return {"status": "fitted", "size_pt": size, "lines": n, "width_fill": round(width_fill, 3),
            "height_fill": round(height_fill, 3)}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text or "") if s.strip()]


def fill_copy(element, source: str, extra_sources: list[str], *, mode: str, seed: int, gutter_mm: float,
              locked: Optional[list[str]] = None) -> dict[str, Any]:
    """Make running copy fill its frame (see module docstring)."""
    from .content_engine import rewrite_source_bound_copy

    def ratio(text: str) -> float:
        report = measure(element, text, gutter_mm=gutter_mm)
        return report.estimated_lines / max(1, report.capacity_lines)

    # Capacity in words, measured with the real metrics on representative copy.
    probe = placeholder_text(400, seed)
    lo, hi = 1, 400
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ratio(" ".join(probe.split()[:mid])) <= 1.0:
            lo = mid
        else:
            hi = mid - 1
    capacity = lo
    if mode == "placeholder":
        words = capacity
        text = placeholder_text(words, seed)
        while words > 1 and ratio(text) > 1.0:
            words -= 1
            text = placeholder_text(words, seed)
        element.text_content = text
        element.content_revision_ref = "placeholder"
        return {"status": "placeholder", "capacity_words": capacity, "fill": round(ratio(text), 3)}

    text = source.strip()
    if ratio(text) > 1.0:
        # Largest source-bound reduction that still fits (binary search).
        lo_w, hi_w, best = 3, len(text.split()), None
        while lo_w <= hi_w:
            mid = (lo_w + hi_w) // 2
            candidate, _ = rewrite_source_bound_copy(source, role="body", target_words=mid, locked_passages=locked or [])
            if ratio(candidate) <= 1.0:
                best, lo_w = candidate, mid + 1
            else:
                hi_w = mid - 1
        text = best or rewrite_source_bound_copy(source, role="body", target_words=3, locked_passages=locked or [])[0]
        element.text_content = text
        fill = ratio(text)
        if fill >= FILL_MIN:
            return {"status": "shortened", "capacity_words": capacity, "fill": round(fill, 3)}
        # Sentence boundaries left a gap: the copy editor rewrites to length.
        return {"status": "needs_expansion", "capacity_words": capacity, "target_words": int(capacity * .9),
                "fill": round(fill, 3)}
    # Too short: extend with further *source* sentences of the same story.
    used = set(_sentences(text))
    for extra in extra_sources:
        for sentence in _sentences(extra):
            if sentence in used:
                continue
            candidate = f"{text} {sentence}".strip()
            if ratio(candidate) > 1.0:
                break
            text, _ = candidate, used.add(sentence)
        if ratio(text) >= FILL_MIN:
            break
    element.text_content = text
    fill = ratio(text)
    if fill >= FILL_MIN:
        return {"status": "extended_from_source", "capacity_words": capacity, "fill": round(fill, 3)}
    target = int(capacity * .9)
    return {"status": "needs_expansion", "capacity_words": capacity, "target_words": target,
            "fill": round(fill, 3)}


def stack_display_lines(scene, element, *, colors: Optional[list[str]] = None, gap_mm: float = .6,
                        max_lines: int = 4) -> list:
    """Split a plate headline into per-line elements, each sized to the full
    measure (tabloid "stack"): every line fills the width, the stack fills the
    height.  The original frame stays as the plate (decorative band)."""
    from .fonts import resolve_font
    from .shaper import width_pt
    from ..models.schemas import Element, ElementStyle, Frame
    text = " ".join((element.text_content or "").split())
    st = element.style
    upper = st.case == "upper"
    words = (text.upper() if upper else text).split()
    if len(words) < 2:
        return []
    path = resolve_font(st.font_family, bold=_bold(element), text=" ".join(words))
    bx, by, bw, bh = text_box(element)
    unit = [(width_pt(word, 100.0, path) / 100.0) for word in words]
    space = (width_pt(" ", 100.0, path) / 100.0)
    best = None
    for n in range(2, min(max_lines, len(words)) + 1):
        lines = _balanced_breaks(words, unit, space, n)
        if not lines:
            continue
        sizes = [(bw * .95) / PT / max(1e-6, (width_pt(" ".join(line), 100.0, path) / 100.0)) for line in lines]
        height = sum(size * 1.02 * PT for size in sizes) + gap_mm * (n - 1)
        scale = min(1.0, (bh - .5) / height)
        sizes = [size * scale for size in sizes]
        ratio = max(sizes) / max(1e-6, min(sizes))
        if ratio > 2.6:
            continue  # wildly different line sizes read as a mistake, not a stack
        fill = scale * (height * scale) / bh if scale < 1 else height / bh
        score = min(1.0, fill) - .05 * (ratio - 1)
        if best is None or score > best[0]:
            best = (score, lines, sizes)
    if not best:
        return []
    _, lines, sizes = best
    original = text.split()
    created, index = [], 0
    total_h = sum(size * 1.02 * PT for size in sizes) + gap_mm * (len(lines) - 1)
    y = by + max(0.0, (bh - total_h) / 2)
    palette = colors or [st.color]
    for line_no, (line, size) in enumerate(zip(lines, sizes)):
        value = " ".join(original[index:index + len(line)])
        index += len(line)
        size = math.floor(size * 100) / 100
        line_h = size * 1.02 * PT
        style = st.model_copy(update={"font_size_pt": size, "line_height_pt": round(size * 1.02, 2), "bg_color": None,
                                      "inset_mm": [0, 0, 0, 0], "valign": "center", "align": "center",
                                      "color": palette[line_no % len(palette)]})
        line_el = Element(id=f"{element.id}-l{line_no}", role="headline", importance=element.importance,
                          content_ref=element.content_ref, text_content=value,
                          frame=Frame(x=bx, y=y, w=bw, h=line_h + .2, rotation_deg=element.frame.rotation_deg),
                          style=style, z=element.z + 1, constraints=[*(element.constraints or []), "no_fill"],
                          story_ref=element.story_ref, flow_group=element.flow_group or f"display-headline-{element.story_ref}",
                          transgressions=list(element.transgressions or []) if line_no == 0 else [],
                          source_refs=list(element.source_refs or []))
        if abs(element.frame.rotation_deg or 0) > .05:
            # Keep the stack rotated about the plate centre, like one object.
            import math as _m
            r = _m.radians(element.frame.rotation_deg)
            pcx, pcy = element.frame.x + element.frame.w / 2, element.frame.y + element.frame.h / 2
            lcx, lcy = bx + bw / 2, y + (line_h + .2) / 2
            dx, dy = lcx - pcx, lcy - pcy
            ncx, ncy = pcx + dx * _m.cos(r) - dy * _m.sin(r), pcy + dx * _m.sin(r) + dy * _m.cos(r)
            line_el.frame.x, line_el.frame.y = ncx - bw / 2, ncy - (line_h + .2) / 2
        created.append(line_el)
        y += line_h + gap_mm
    # The original frame becomes the plate; its words now live in the lines.
    element.role = "band"
    element.text_content = None
    element.content_ref = f"{element.story_ref}.headline_plate"
    element.constraints = [*(element.constraints or []), "decorative_background"]
    element.transgressions = []
    position = scene.elements.index(element)
    scene.elements[position + 1:position + 1] = created
    return created


def restack_module(scene, story_ref: str) -> None:
    """Inside one module: kicker → headline → copy follow each other with a
    fixed rhythm; the copy frame takes the rest of the module (and is then
    filled).  The module's outer frame (the layout decision) is unchanged."""
    members = [e for e in scene.elements if e.story_ref == story_ref and e.role in {"kicker", "headline", "body", "deck", "lead"}
               and "no_fill" not in (e.constraints or [])]
    heads = [e for e in members if e.role == "headline" and not e.style.bg_color and e.importance < .95]
    copies = [e for e in members if e.role in COPY_ROLES]
    for head in heads:
        below = [c for c in copies if c.frame.y >= head.frame.y and abs(c.frame.x - head.frame.x) < 4
                 and abs(c.frame.w - head.frame.w) < 6]
        if not below:
            continue
        copy = min(below, key=lambda c: c.frame.y)
        shaped = _shape_lines(head, head.text_content or "", float(head.style.font_size_pt or 14))
        head_h = len(shaped.lines) * float(head.style.font_size_pt or 14) * 1.06 * PT + .8
        if head_h >= head.frame.h:
            continue
        bottom = copy.frame.y + copy.frame.h
        head.frame.h = head_h
        copy.frame.y = head.frame.y + head_h + 1.6
        copy.frame.h = max(4.0, bottom - copy.frame.y)


LABEL_ROLES = {"kicker"}
COPY_ROLES = {"body", "deck", "lead"}


def finalize_text_frames(scene, dna, material, *, mode: Optional[str] = None) -> dict[str, Any]:
    """Apply insets, vertical alignment, headline sizing and copy fill."""
    mode = mode or getattr(material, "copy_mode", "source") or "source"
    gutter = dna.grid.gutter_mm
    stories = {story.id: story for story in material.stories}
    requests, report = [], {}
    # Pass 1: headlines and labels get their final size (they define where
    # the copy can start); pass 2 restacks modules; pass 3 fills copy.
    ordered = sorted(enumerate(list(scene.elements)), key=lambda item: item[1].role in COPY_ROLES)
    restacked = False
    for index, element in ordered:
        if not restacked and element.role in COPY_ROLES:
            for ref in {e.story_ref for e in scene.elements if e.story_ref}:
                restack_module(scene, ref)
            restacked = True
        st = element.style
        if element.role in {"logo", "folio", "rule", "band", "photo"} or not st or not element.text_content:
            continue
        if "no_fill" in (element.constraints or []):
            continue
        shape_inset = inscribed_inset(element.shape, element.frame.w, element.frame.h) if not is_rect(element.shape) else None
        has_plane = bool(st.bg_color) or not is_rect(element.shape)
        if element.role in LABEL_ROLES or "label" in (element.constraints or []):
            if "label" not in (element.constraints or []):
                element.constraints.append("label")
            pad_v, pad_h = .7, 1.6
            base = shape_inset or [0, 0, 0, 0]
            st.inset_mm = [base[0] + pad_v, base[1] + pad_h, base[2] + pad_v, base[3] + pad_h]
            st.valign = "center"
            size = float(st.font_size_pt or 9)
            _, _, iw, ih = text_box(element)
            report[element.id] = fit_headline(element, min_pt=max(6.5, size * .7), max_pt=max(size, ih / PT / 1.12), max_lines=3 if shape_inset else 1)
            if not shape_inset and "fixed_width" not in (element.constraints or []) and is_rect(element.shape):
                shaped = _shape_lines(element, element.text_content, float(st.font_size_pt))
                widest = max((line.width_pt for line in shaped.lines), default=0) * PT
                new_w = min(element.frame.w, widest + 2 * pad_h + 3.0)
                if st.align == "right":
                    element.frame.x += element.frame.w - new_w
                elif st.align == "center":
                    element.frame.x += (element.frame.w - new_w) / 2
                element.frame.w = new_w
            continue
        if element.role == "headline":
            if has_plane:
                base = shape_inset or [0, 0, 0, 0]
                pad = 2.2 if element.importance >= .95 else 1.6
                st.inset_mm = [base[0] + pad * .7, base[1] + pad, base[2] + pad * .7, base[3] + pad]
                st.valign = "center"
            elif not st.valign or st.valign == "top":
                st.valign = "bottom" if "headline_bottom" in (element.constraints or []) else "top"
            size = float(st.font_size_pt or 20)
            dominant = element.importance >= .95
            max_pt = size * (1.9 if dominant else 1.6)
            if element.flow_group and element.flow_group.startswith("display-headline") and "\n" not in element.text_content:
                max_pt = size * 1.35  # one line of a composed stack keeps its stack proportions
            single = "\n" not in element.text_content and bool(element.flow_group)
            if has_plane and (not single or "allow_stack" in (element.constraints or [])):
                families = [*((dna.cover_grammar or {}).get("display_font_candidates") or []),
                            *((dna.cover_grammar or {}).get("display_wide_font_candidates") or []),
                            dna.typography.fonts.get("headline"), dna.typography.fonts.get("sans")]
                result = fit_display_fill(element, min_pt=max(12.0, size * .6), max_pt=max_pt, max_lines=4,
                                          families=[f for f in families if f])
                if (result.get("status") == "fitted" and "allow_stack" in (element.constraints or [])
                        and (result["width_fill"] * result["height_fill"] < .72 or result["width_fill"] < .86
                             or "force_stack" in (element.constraints or []))):
                    colors = (list(scene.metadata.get("display_line_colors") or [])
                              or list(((dna.cover_grammar or {}).get("display_line_colors") or [])) or None)
                    lines = stack_display_lines(scene, element, colors=colors)
                    if lines:
                        report[element.id] = {"status": "stacked", "lines": len(lines), "width_fill": .965,
                                              "height_fill": round(sum(l.frame.h for l in lines) / max(1e-6, text_box(element)[3]), 3)}
                        continue
                report[element.id] = result
            else:
                report[element.id] = fit_headline(element, min_pt=max(14.0, size * .6), max_pt=max_pt,
                                                  max_lines=1 if single else 4)
            continue
        if element.role in COPY_ROLES:
            if has_plane:
                base = shape_inset or [0, 0, 0, 0]
                st.inset_mm = [base[0] + 1.6, base[1] + 2.0, base[2] + 1.6, base[3] + 2.0]
            st.valign = st.valign or "top"
            ref = (element.content_ref or "").split(".")
            story = stories.get(element.story_ref or "")
            field = ref[1] if len(ref) > 1 else element.role
            source = str(getattr(story, field, "") or element.text_content) if story else element.text_content
            extras = [str(getattr(story, f, "") or "") for f in ("lead", "deck", "body") if story and f != field]
            result = fill_copy(element, source, extras, mode=mode, seed=index, gutter_mm=gutter,
                               locked=list(getattr(story, "locked_passages", []) or []) if story else None)
            report[element.id] = result
            if result["status"] == "needs_expansion":
                requests.append({"element_id": element.id, "story_ref": element.story_ref, "field": field,
                                 "target_words": result["target_words"], "fill": result["fill"]})
    scene.metadata["copy_mode"] = mode
    scene.metadata["copy_requests"] = requests
    scene.metadata["frame_fill"] = report
    return report
