"""Deterministic copyfitting primitives used by the critic and renderers.

The engine deliberately reports an estimate rather than silently editing the
editor's copy.  That keeps content and geometry separate while giving the
critic enough information to reject an impossible text frame before export.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


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


def estimate_text_capacity(
    text: str,
    width_mm: float,
    height_mm: float,
    columns: int = 1,
    font_size_pt: float = 9.5,
    leading_pt: float | None = None,
) -> CopyfitReport:
    """Estimate whether ``text`` fits a multi-column frame.

    The model uses a conservative average glyph width and reserves a little
    capacity for paragraph endings.  It is intentionally stable across
    machines so the SVG/HTML critic and the production exporter agree.
    """

    columns = max(1, int(columns))
    font_size_pt = max(1.0, float(font_size_pt))
    leading_pt = float(leading_pt or font_size_pt * 1.2)
    gutter_mm = 4.0
    measure_mm = max(1.0, (float(width_mm) - (columns - 1) * gutter_mm) / columns)
    glyph_mm = max(0.8, font_size_pt * 0.17)
    chars_per_line = max(1, int(measure_mm / glyph_mm))
    leading_mm = max(0.5, leading_pt * 0.352778)
    lines_per_column = max(1, int(float(height_mm) / leading_mm))
    capacity_lines = lines_per_column * columns
    characters = len(re.sub(r"\s+", " ", text or "").strip())
    words = len((text or "").split())
    estimated_lines = max(1, math.ceil(characters / chars_per_line * 1.05)) if characters else 0
    capacity_characters = max(1, int(capacity_lines * chars_per_line * 0.94))
    overflow_ratio = characters / capacity_characters if capacity_characters else float("inf")
    return CopyfitReport(
        characters=characters,
        words=words,
        estimated_lines=estimated_lines,
        capacity_lines=capacity_lines,
        capacity_characters=capacity_characters,
        overflow_ratio=round(overflow_ratio, 3),
        leading_pt=round(leading_pt, 2),
        passes=overflow_ratio <= 1.12,
    )


def copyfit_text(text: str, width_mm: float, height_mm: float, columns: int = 1, font_size_pt: float = 9.5, leading_pt: float | None = None) -> CopyfitReport:
    """Public alias used by integrations and the CLI."""

    return estimate_text_capacity(text, width_mm, height_mm, columns, font_size_pt, leading_pt)

