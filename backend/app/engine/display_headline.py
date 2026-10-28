"""Measured line composition for prominent newspaper headlines.

The editorial words stay intact.  The compositor may choose a font, case,
size and explicit line breaks, then the renderer draws that exact plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .fonts import resolve_font
from .shaper import PT_PER_MM, width_pt


@dataclass(frozen=True)
class DisplayHeadline:
    text: str
    font_family: str
    font_size_pt: float
    case: str
    lines: tuple[str, ...]
    line_widths_pt: tuple[float, ...]


@dataclass(frozen=True)
class StagedDisplayHeadline:
    lead_word: str
    lead_size_pt: float
    sub_lines: tuple[str, ...]
    sub_size_pt: float
    font_family: str
    case: str
    text: str
    lead_line_width_pt: float
    sub_line_widths_pt: tuple[float, ...]


def compose_display_headline(
    text: str,
    *,
    width_mm: float,
    height_mm: float,
    preferred_size_pt: float,
    minimum_size_pt: float,
    font_families: list[str],
    case_options: tuple[str, ...] = ("normal",),
    min_lines: int = 1,
    max_lines: int = 3,
    allow_internal_single_word: bool = False,
    leading_ratio: float = 1.06,
) -> DisplayHeadline | None:
    """Find a readable, balanced arrangement using the actual glyph widths.

    A one-word final line is never accepted for a multi-line display title.
    A little horizontal slack covers renderer differences and the outline.
    """
    words = str(text or "").split()
    if not words or width_mm <= 0 or height_mm <= 0:
        return None
    measure_pt = width_mm * PT_PER_MM * .965
    best: tuple[float, DisplayHeadline] | None = None
    families = list(dict.fromkeys(str(f).strip() for f in font_families if str(f).strip()))
    for family_index, family in enumerate(families):
        path = resolve_font(family, bold=True, text=" ".join(words))
        if not path:
            continue
        for case in case_options:
            if case not in {"normal", "upper"}:
                continue
            display_words = [word.upper() if case == "upper" else word for word in words]
            for line_count in range(max(1, min_lines), min(max_lines, len(words)) + 1):
                if line_count > 1 and len(words) < (line_count + 1 if allow_internal_single_word else line_count * 2):
                    continue
                for breaks in combinations(range(1, len(words)), line_count - 1):
                    points = (0, *breaks, len(words))
                    groups = [display_words[points[i]:points[i + 1]] for i in range(line_count)]
                    if line_count > 1 and (len(groups[-1]) < 2 or
                                           (not allow_internal_single_word and any(len(group) < 2 for group in groups))):
                        continue
                    lines = tuple(" ".join(group) for group in groups)
                    for half_points in range(round(preferred_size_pt * 2), round(minimum_size_pt * 2) - 1, -1):
                        size = half_points / 2
                        if line_count * size * leading_ratio > height_mm * PT_PER_MM * .98:
                            continue
                        widths = tuple(width_pt(line, size, path) for line in lines)
                        if max(widths) > measure_pt:
                            continue
                        balance = min(widths) / max(widths)
                        # Large display type matters, but a severely uneven
                        # two-line title cannot win by being a point larger.
                        coverage = max(widths) / measure_pt
                        score = (
                            .58 * size / preferred_size_pt
                            + .27 * balance
                            + .15 * coverage
                            - .018 * (line_count - 1)
                            - .025 * family_index
                            - (.012 if case == "upper" else 0)
                        )
                        proposal = DisplayHeadline("\n".join(lines), family, size, case, lines, widths)
                        if best is None or score > best[0]:
                            best = (score, proposal)
                        break  # largest fitting size for this line plan
    if best:
        return best[1]

    # A missing local font must not silently remove the editorial line plan.
    # Production normally reaches the measured branch above, but a new server
    # or an offline preview can be rendered before the font library has been
    # materialised. Keep the title balanced and let the renderer use the
    # declared fallback family until the real face becomes available.
    fallback_family = (next((family for family in families
                             if "," in family or "sans-serif" in family.lower() or "serif" == family.lower()),
                            families[-1] if families else "sans-serif"))
    fallback_case = next((value for value in case_options if value in {"normal", "upper"}), "normal")
    display_words = [word.upper() if fallback_case == "upper" else word for word in words]
    fallback_best: tuple[float, DisplayHeadline] | None = None
    for line_count in range(max(1, min_lines), min(max_lines, len(words)) + 1):
        if line_count > 1 and len(words) < (line_count + 1 if allow_internal_single_word else line_count * 2):
            continue
        for breaks in combinations(range(1, len(words)), line_count - 1):
            points = (0, *breaks, len(words))
            groups = [display_words[points[i]:points[i + 1]] for i in range(line_count)]
            if line_count > 1 and (len(groups[-1]) < 2 or
                                   (not allow_internal_single_word and any(len(group) < 2 for group in groups))):
                continue
            lines = tuple(" ".join(group) for group in groups)
            # Condensed display faces average about 0.47 em per glyph. Using
            # 0.52 here leaves conservative room for punctuation and capitals.
            units = tuple(max(1.0, len(line) * .52) for line in lines)
            width_size = measure_pt / max(units)
            height_size = height_mm * PT_PER_MM * .98 / (line_count * leading_ratio)
            size = min(preferred_size_pt, width_size, height_size)
            if size < minimum_size_pt:
                continue
            widths = tuple(unit * size for unit in units)
            balance = min(widths) / max(widths)
            coverage = max(widths) / measure_pt
            score = .60 * size / preferred_size_pt + .30 * balance + .10 * coverage - .018 * (line_count - 1)
            proposal = DisplayHeadline("\n".join(lines), fallback_family, round(size, 1),
                                       fallback_case, lines, widths)
            if fallback_best is None or score > fallback_best[0]:
                fallback_best = (score, proposal)
    return fallback_best[1] if fallback_best else None


def has_stranded_headline_word(lines: list[str] | tuple[str, ...]) -> bool:
    return len(lines) > 1 and len(lines[-1].split()) == 1


def compose_staged_display_headline(
    text: str,
    *,
    width_mm: float,
    height_mm: float,
    preferred_size_pt: float,
    minimum_size_pt: float = 18.0,
    font_families: list[str],
    case_options: tuple[str, ...] = ("normal",),
    leading_ratio: float = 1.06,
) -> StagedDisplayHeadline | None:
    """Compose a dynamic poster-style headline: large lead screamer word + sub-headline."""
    words = str(text or "").split()
    if len(words) < 3 or width_mm <= 0 or height_mm <= 0:
        return None

    lead_word = words[0]
    sub_text = " ".join(words[1:])
    measure_pt = width_mm * PT_PER_MM * 0.965
    families = list(dict.fromkeys(str(f).strip() for f in font_families if str(f).strip()))
    if not families:
        families = ["Inter, sans-serif"]

    best: StagedDisplayHeadline | None = None
    best_score = -1.0

    for family in families:
        path = resolve_font(family, bold=True, text=" ".join(words))
        for case in case_options:
            dw_lead = lead_word.upper() if case == "upper" else lead_word
            dw_sub = sub_text.upper() if case == "upper" else sub_text

            lead_h_mm = height_mm * 0.48
            sub_h_mm = height_mm - lead_h_mm

            lead_max_size = lead_h_mm * PT_PER_MM / leading_ratio
            if path:
                lead_w_pt = width_pt(dw_lead, lead_max_size, path)
                if lead_w_pt > measure_pt:
                    lead_size = lead_max_size * (measure_pt / max(1.0, lead_w_pt))
                else:
                    lead_size = min(lead_max_size, preferred_size_pt * 1.5)
                actual_lead_w = width_pt(dw_lead, lead_size, path)
            else:
                lead_units = max(1.0, len(dw_lead) * 0.52)
                lead_size = min(lead_max_size, measure_pt / lead_units, preferred_size_pt * 1.5)
                actual_lead_w = lead_units * lead_size

            if lead_size < minimum_size_pt:
                continue

            sub_plan = compose_display_headline(
                dw_sub,
                width_mm=width_mm,
                height_mm=sub_h_mm,
                preferred_size_pt=min(preferred_size_pt, lead_size * 0.72),
                minimum_size_pt=minimum_size_pt * 0.75,
                font_families=[family],
                case_options=(case,),
                min_lines=1,
                max_lines=2,
                allow_internal_single_word=True,
            )
            if not sub_plan:
                continue

            score = (
                0.5 * (lead_size / preferred_size_pt)
                + 0.3 * (sub_plan.font_size_pt / preferred_size_pt)
                + 0.2 * (actual_lead_w / measure_pt)
            )
            if score > best_score:
                best_score = score
                combined = f"{dw_lead}\n{sub_plan.text}"
                best = StagedDisplayHeadline(
                    lead_word=dw_lead,
                    lead_size_pt=round(lead_size, 1),
                    sub_lines=sub_plan.lines,
                    sub_size_pt=sub_plan.font_size_pt,
                    font_family=family,
                    case=case,
                    text=combined,
                    lead_line_width_pt=actual_lead_w,
                    sub_line_widths_pt=sub_plan.line_widths_pt,
                )

    return best

