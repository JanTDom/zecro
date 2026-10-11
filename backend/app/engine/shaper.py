"""Font-aware text measurement with a deterministic offline estimate fallback."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable

@dataclass
class ShapedLine:
    text: str
    width_pt: float
    hyphenated: bool = False

@dataclass
class ShapeResult:
    status: str
    lines: list[ShapedLine] = field(default_factory=list)
    line_count: int = 0
    font_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def _font_width(text: str, font_path: str | None, size_pt: float) -> float:
    if not font_path or not Path(font_path).exists():
        return len(text) * float(size_pt) * .48
    try:
        from fontTools.ttLib import TTFont
        font=TTFont(font_path); cmap=font.getBestCmap() or {}; units=float(font["head"].unitsPerEm)
        hmtx=font["hmtx"].metrics
        return sum(float(hmtx.get(cmap.get(ord(ch), ".notdef"), hmtx.get(".notdef", (units*.5,0)))[0]) / units * size_pt for ch in text)
    except Exception:
        return len(text) * float(size_pt) * .48


def _hyphenate(word: str, language: str = "pl") -> list[str]:
    try:
        import pyphen
        dic=pyphen.Pyphen(lang="pl_PL" if language.startswith("pl") else language)
        positions=dic.positions(word)
        if not positions: return [word]
        parts=[]; start=0
        for pos in positions: parts.append(word[start:pos] + "-" ); start=pos
        parts.append(word[start:]); return parts
    except Exception:
        return [word]


def shape_text(text: str, *, width_pt: float, font_size_pt: float = 9.5, leading_pt: float | None = None, font_path: str | None = None, language: str = "pl", max_lines: int | None = None, widow_lines: int = 0, orphan_lines: int = 0) -> ShapeResult:
    if width_pt <= 0: return ShapeResult(status="unavailable", warnings=["width must be positive"])
    tokens=re.findall(r"\S+", text or "")
    lines=[]; current=""; hyphenated=False
    def flush():
        nonlocal current, hyphenated
        if current: lines.append(ShapedLine(current,_font_width(current,font_path,font_size_pt),hyphenated)); current=""; hyphenated=False
    for token in tokens:
        candidate=token if not current else current + " " + token
        if _font_width(candidate,font_path,font_size_pt) <= width_pt:
            current=candidate; continue
        if current: flush()
        if _font_width(token,font_path,font_size_pt) <= width_pt:
            current=token; continue
        parts=_hyphenate(token,language)
        if len(parts)==1:
            current=token; continue
        for part in parts[:-1]:
            if _font_width(part,font_path,font_size_pt) <= width_pt: lines.append(ShapedLine(part,_font_width(part,font_path,font_size_pt),True))
        current=parts[-1]; hyphenated=True
    flush()
    warnings=[]
    if max_lines is not None and len(lines)>max_lines: warnings.append(f"text needs {len(lines)} lines; frame holds {max_lines}")
    status="measured" if font_path and Path(font_path).exists() else "estimate"
    if status=="estimate": warnings.append("font file unavailable; using deterministic estimate")
    return ShapeResult(status=status,lines=lines,line_count=len(lines),font_path=font_path,warnings=warnings)


def measure_text(text: str, width_mm: float, *, font_size_pt: float = 9.5, leading_pt: float | None = None, font_path: str | None = None, language: str = "pl", height_mm: float | None = None) -> ShapeResult:
    result=shape_text(text,width_pt=float(width_mm)*2.83464567,font_size_pt=font_size_pt,leading_pt=leading_pt,font_path=font_path,language=language,max_lines=(int(float(height_mm)*2.83464567/(leading_pt or font_size_pt*1.2)) if height_mm else None))
    return result
