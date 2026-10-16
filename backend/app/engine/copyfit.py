"""Deterministic copyfitting primitives used by the critic and renderers.

The engine deliberately reports an estimate rather than silently editing the
editor's copy.  That keeps content and geometry separate while giving the
critic enough information to reject an impossible text frame before export.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class CopyfitReport:
    characters: int
    words: int
    estimated_lines: int
    capacity_lines: int
    capacity_characters: int
    overflow_ratio: float
    tracking_em: float = 0.0
    leading_pt: float = 0.0
    passes: bool = True
    # The fields below make the estimate useful to editorial planning.  They
    # are deliberately estimates (the production renderer remains the final
    # authority), but expose the same constraints that a TextPlan carries.
    chars_per_line: int = 0
    lines_per_column: int = 0
    free_lines: int = 0
    widows: int = 0
    orphans: int = 0
    paragraph_lines: Tuple[int, ...] = ()
    overlong_tokens: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()


def estimate_text_capacity(
    text: str,
    width_mm: float,
    height_mm: float,
    columns: int = 1,
    font_size_pt: float = 9.5,
    leading_pt: float | None = None,
    *,
    tracking_em: float = 0.0,
    widow_lines: int = 0,
    orphan_lines: int = 0,
    no_break_tokens: Iterable[str] | None = None,
    font_family: str | None = None,
    bold: bool = False,
    gutter_mm: float = 4.0,
    face_args: dict | None = None,
) -> CopyfitReport:
    """Whether ``text`` fits a multi-column frame.

    With ``font_family`` resolvable in the font library the result is measured
    by the production typesetter (HarfBuzz + Knuth–Plass) — the same breaks
    the PDF draws.  Otherwise a conservative estimate is used.

    The model uses a conservative average glyph width and reserves a little
    capacity for paragraph endings.  It is intentionally stable across
    machines so the SVG/HTML critic and the production exporter agree.
    """

    columns = max(1, int(columns))
    font_size_pt = max(1.0, float(font_size_pt))
    leading_pt = float(leading_pt or font_size_pt * 1.2)
    tracking_em = float(tracking_em)
    if font_family:
        measured = _measured_capacity(text, width_mm, height_mm, columns, font_size_pt, leading_pt, font_family, bold, gutter_mm,
                                       face_args, tracking_em)
        if measured is not None:
            return measured
    measure_mm = max(1.0, (float(width_mm) - (columns - 1) * gutter_mm) / columns)
    glyph_mm = max(0.8, font_size_pt * 0.17)
    # Tracking is expressed in em, e.g. -0.01em is the usual emergency
    # tightening used in a newspaper frame.  A negative value therefore
    # increases the usable measure while positive tracking reduces it.
    chars_per_line = max(1, int(measure_mm / glyph_mm / max(0.25, 1.0 + tracking_em)))
    leading_mm = max(0.5, leading_pt * 0.352778)
    lines_per_column = max(1, int(float(height_mm) / leading_mm))
    capacity_lines = lines_per_column * columns
    normalised = _normalise_measure_text(text or "")
    characters = len(re.sub(r"\s+", " ", normalised).strip())
    words = len((text or "").split())
    wrapped = [
        _wrap_paragraph(paragraph, chars_per_line, no_break_tokens=no_break_tokens)
        for paragraph in _paragraphs(normalised)
        if paragraph.strip()
    ]
    paragraph_lines = tuple(item[0] for item in wrapped)
    overlong_tokens = tuple(token for item in wrapped for token in item[1])
    estimated_lines = sum(paragraph_lines)
    # Keep the historical 5% reserve for paragraph endings, but never round a
    # non-empty paragraph down to zero lines.
    if estimated_lines:
        # Explicit display-title breaks are separate one-line paragraphs. They
        # already contain the art director's complete line plan and need no
        # paragraph-ending reserve. Add the reserve only when at least one
        # paragraph actually wraps inside its own line box.
        estimated_lines = (math.ceil(estimated_lines * 1.05)
                           if any(lines > 1 for lines in paragraph_lines)
                           else estimated_lines)
    capacity_characters = max(1, int(capacity_lines * chars_per_line * 0.94))
    overflow_ratio = characters / capacity_characters if capacity_characters else float("inf")
    free_lines = capacity_lines - estimated_lines
    widows, orphans = _widow_orphan_counts(
        paragraph_lines,
        lines_per_column,
        widow_lines=max(0, int(widow_lines)),
        orphan_lines=max(0, int(orphan_lines)),
    )
    warnings: List[str] = []
    if overflow_ratio > 1.0:
        warnings.append(f"estimated overflow ratio {overflow_ratio:.2f}")
    if estimated_lines > capacity_lines:
        warnings.append(f"copy needs {estimated_lines} lines; frame holds {capacity_lines}")
    if widows:
        warnings.append(f"{widows} widow line(s) below the configured threshold")
    if orphans:
        warnings.append(f"{orphans} orphan line(s) below the configured threshold")
    if overlong_tokens:
        warnings.append("no-break token exceeds the available line measure")
    return CopyfitReport(
        characters=characters,
        words=words,
        estimated_lines=estimated_lines,
        capacity_lines=capacity_lines,
        capacity_characters=capacity_characters,
        overflow_ratio=round(overflow_ratio, 3),
        tracking_em=round(tracking_em, 4),
        leading_pt=round(leading_pt, 2),
        # Copyfit is a hard gate for production.  The old 1.12 tolerance made
        # a visible overset look like a pass and was especially misleading for
        # narrow multi-column frames.
        passes=overflow_ratio <= 1.0 and estimated_lines <= capacity_lines and not widows and not orphans and not overlong_tokens,
        chars_per_line=chars_per_line,
        lines_per_column=lines_per_column,
        free_lines=free_lines,
        widows=widows,
        orphans=orphans,
        paragraph_lines=paragraph_lines,
        overlong_tokens=overlong_tokens,
        warnings=tuple(warnings),
    )


def _measured_capacity(text, width_mm, height_mm, columns, size, leading, family, bold, gutter_mm, face_args=None,
                       tracking_em=0.0):
    try:
        # Avoid entering the expensive measured path when the optional shaping
        # stack is not installed.  The caller then uses the deterministic
        # estimate below and the PDF renderer reports the same limitation.
        import fontTools  # noqa: F401
        import uharfbuzz  # noqa: F401
        from .fonts import resolve_font
        from .shaper import fill_columns
        path = (resolve_font(family, text=text, weight=face_args["weight"], italic=face_args["italic"],
                             width=face_args["width"]) if face_args else resolve_font(family, bold=bold, text=text))
        if not path:
            return None
        fit = fill_columns(text or "", width_mm=float(width_mm), height_mm=float(height_mm), columns=columns, gutter_mm=gutter_mm,
                           font_size_pt=size, leading_pt=leading, font_path=path, tracking_em=tracking_em or 0.0)
    except Exception:
        return None
    shaped = fit["shaped"]
    words = len((text or "").split())
    characters = len(re.sub(r"\s+", " ", text or "").strip())
    cap, need = fit["capacity"], fit["lines"]
    avg = characters / max(1, need)
    warnings = [] if need <= cap else [f"copy needs {need} lines; frame holds {cap}"]
    if shaped.overfull:
        warnings.append("a single word is wider than the column")
    return CopyfitReport(characters=characters, words=words, estimated_lines=need, capacity_lines=cap,
                         capacity_characters=max(1, int(cap * avg)), overflow_ratio=round(need / max(1, cap), 3), leading_pt=round(leading, 2),
                         passes=need <= cap and not shaped.overfull, chars_per_line=int(avg), lines_per_column=fit["lines_per_column"],
                         free_lines=cap - need, widows=shaped.widows, orphans=0, paragraph_lines=(need,),
                         warnings=tuple(warnings + ["measured: " + str(path).split("/")[-1]]))


def copyfit_text(text: str, width_mm: float, height_mm: float, columns: int = 1, font_size_pt: float = 9.5, leading_pt: float | None = None, **kwargs) -> CopyfitReport:
    """Public alias used by integrations and the CLI."""

    return estimate_text_capacity(text, width_mm, height_mm, columns, font_size_pt, leading_pt, **kwargs)


def _normalise_measure_text(text: str) -> str:
    """Normalise whitespace for measuring without changing editorial copy."""

    # Keep NBSP in the wrapping input: it occupies one character of measure
    # but must remain an unbreakable opportunity, just as in HTML/PDF.
    return str(text or "").strip()


def _paragraphs(text: str) -> List[str]:
    # CMS exports use either one or two newlines for a paragraph break.  Treat
    # both forms as a new paragraph so widow/orphan checks see the same blocks
    # that the HTML/IDML renderer receives.
    return [part.strip() for part in re.split(r"\n\s*", text or "") if part.strip()]


def _tokenise_paragraph(paragraph: str, no_break_tokens: Iterable[str] | None = None) -> List[str]:
    """Return words while keeping configured phrases as one unbreakable token."""

    # Keep Polish non-breaking spaces as word-joiners. Phrase matching below
    # treats them as spaces so a locked passage still matches polished copy.
    paragraph = paragraph.replace("\u00a0", "\u2060").replace("\u202f", "\u2060")
    tokens = [token for token in re.findall(r"\S+", paragraph) if token]
    protected = sorted((str(token).strip() for token in (no_break_tokens or []) if str(token).strip()), key=len, reverse=True)
    if not protected:
        return tokens
    # Mark spaces inside phrases before tokenisation.  The marker is removed
    # only for display; its length still includes the spaces in the measure.
    for phrase in protected:
        phrase_tokens = phrase.split()
        if len(phrase_tokens) < 2:
            continue
        needle = re.escape(" ".join(phrase_tokens)).replace(r"\ ", r"(?:\s|\u2060)+")
        paragraph = re.sub(needle, phrase.replace(" ", "\u2060"), paragraph)
    # Keep the marker in the returned token so wrapping can detect an
    # unbreakable phrase that is wider than the available measure.
    return [token for token in re.findall(r"\S+", paragraph) if token]


def _wrap_paragraph(paragraph: str, chars_per_line: int, *, no_break_tokens: Iterable[str] | None = None) -> Tuple[int, Tuple[str, ...]]:
    """Estimate wrapped lines with word boundaries and explicit no-break phrases."""

    protected = {str(token).strip() for token in (no_break_tokens or []) if str(token).strip()}
    tokens = _tokenise_paragraph(paragraph, protected)
    if not tokens:
        return 0, ()
    lines = 1
    current = 0
    overlong: List[str] = []
    for token in tokens:
        display_token = token.replace("\u2060", " ")
        unbreakable = "\u2060" in token or display_token in protected
        token_width = len(display_token)
        if unbreakable and token_width > chars_per_line:
            overlong.append(display_token)
            if current:
                lines += 1
            # The renderer will overflow this one line rather than split a
            # protected name/quote across lines.  The report fails via the
            # explicit overlong-token gate below.
            current = chars_per_line
            continue
        if current == 0:
            # A token longer than the measure is split by the browser/engine;
            # count the extra lines instead of silently under-reporting it.
            lines += max(0, math.ceil(token_width / chars_per_line) - 1)
            current = token_width % chars_per_line or chars_per_line
        elif current + 1 + token_width <= chars_per_line:
            current += 1 + token_width
        else:
            lines += 1
            lines += max(0, math.ceil(token_width / chars_per_line) - 1)
            current = token_width % chars_per_line or chars_per_line
    return lines, tuple(overlong)


def _widow_orphan_counts(
    paragraph_lines: Sequence[int],
    lines_per_column: int,
    *,
    widow_lines: int,
    orphan_lines: int,
) -> Tuple[int, int]:
    """Count paragraph fragments stranded at column boundaries.

    A count is returned instead of a boolean so the critic can explain why a
    candidate failed and the editor can choose between a copy variant and a
    reflow.  Thresholds of zero disable the corresponding check.
    """

    if not paragraph_lines or lines_per_column <= 0:
        return 0, 0
    widows = 0
    orphans = 0
    cursor = 0
    for count in paragraph_lines:
        if count <= 0:
            continue
        start_in_column = cursor % lines_per_column
        first_fragment = min(count, lines_per_column - start_in_column)
        remaining = count - first_fragment
        if remaining > 0:
            if orphan_lines and first_fragment < orphan_lines:
                orphans += first_fragment
            last_fragment = remaining % lines_per_column or lines_per_column
            if widow_lines and last_fragment < widow_lines:
                widows += last_fragment
        cursor += count
    return widows, orphans

