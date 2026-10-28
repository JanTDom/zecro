"""Authentic newspaper infographics and editorial widgets.

Creates production-ready scene elements for weather ear boxes, quote pullouts,
fact sidebars, and financial market tickers.
"""
from __future__ import annotations

import uuid
from typing import Any, List, Optional
from ..models.schemas import Element, ElementStyle, Frame
from .polish_typography import polish_microtypography


def create_weather_ear_box(
    city: str,
    temp_high: int,
    temp_low: int,
    condition: str = "slonce",
    frame: Optional[Frame] = None,
    date_str: Optional[str] = None,
) -> Element:
    """Create a weather ear box for masthead corners."""
    if frame is None:
        frame = Frame(x=10.0, y=8.0, w=45.0, h=22.0)

    weather_icons = {
        "slonce": "☀",
        "deszcz": "🌧",
        "chmury": "☁",
        "snieg": "❄",
        "burza": "⛈",
    }
    icon = weather_icons.get(condition.lower(), "☀")
    date_line = f"{date_str} | " if date_str else ""
    text_content = (
        f"POGODA {date_line}{city.upper()}\n"
        f"{icon} {temp_high}°C / {temp_low}°C\n"
        f"{condition.capitalize()}"
    )
    text_content = polish_microtypography(text_content)

    return Element(
        id=f"weather_{uuid.uuid4().hex[:6]}",
        role="infobox",
        importance=0.4,
        text_content=text_content,
        frame=frame,
        z=3,
        style=ElementStyle(
            font_family="Inter, sans-serif",
            font_size_pt=7.5,
            font_weight="bold",
            line_height=1.2,
            color="#111827",
            bg_color="#F9FAFB",
            border_width_mm=0.3,
            border_color="#D1D5DB",
            padding_mm=2.0,
            align="center",
            valign="center",
        ),
    )


def create_quote_callout_box(
    quote: str,
    author: str,
    frame: Optional[Frame] = None,
    title_affiliation: Optional[str] = None,
) -> Element:
    """Create an editorial pull quote box with authentic quotation styling."""
    if frame is None:
        frame = Frame(x=15.0, y=80.0, w=65.0, h=45.0)

    clean_quote = quote.strip("„”\"' ")
    author_line = f"— {author}"
    if title_affiliation:
        author_line += f", {title_affiliation}"

    formatted_text = f"„{clean_quote}”\n\n{author_line}"
    formatted_text = polish_microtypography(formatted_text)

    return Element(
        id=f"quote_{uuid.uuid4().hex[:6]}",
        role="pullquote",
        importance=0.7,
        text_content=formatted_text,
        frame=frame,
        z=4,
        style=ElementStyle(
            font_family="PT Serif, Georgia, serif",
            font_size_pt=13.0,
            font_weight="bold",
            line_height=1.25,
            color="#111827",
            bg_color="#FAF9F5",
            border_width_mm=0.4,
            border_color="#C2410C",  # Editorial crimson / ochre tint
            padding_mm=3.5,
            align="left",
            valign="top",
            font_style="italic",
        ),
    )


def create_fact_box(
    title: str,
    facts: List[str],
    frame: Optional[Frame] = None,
) -> Element:
    """Create a tinted sidebar box with bulleted facts ('W SKRÓCIE')."""
    if frame is None:
        frame = Frame(x=15.0, y=140.0, w=55.0, h=60.0)

    header = title.upper()
    bullet_items = [f"• {fact.strip()}" for fact in facts if fact.strip()]
    content = f"{header}\n\n" + "\n".join(bullet_items)
    content = polish_microtypography(content)

    return Element(
        id=f"factbox_{uuid.uuid4().hex[:6]}",
        role="infobox",
        importance=0.6,
        text_content=content,
        frame=frame,
        z=3,
        style=ElementStyle(
            font_family="Inter, sans-serif",
            font_size_pt=8.0,
            font_weight="normal",
            line_height=1.3,
            color="#1F2937",
            bg_color="#F3F4F6",
            border_width_mm=0.5,
            border_color="#1F2937",
            padding_mm=3.0,
            align="left",
            valign="top",
        ),
    )


def create_market_ticker_box(
    indices: List[dict[str, Any]],
    frame: Optional[Frame] = None,
) -> Element:
    """Create a financial ticker bar with market indices and directional change."""
    if frame is None:
        frame = Frame(x=10.0, y=285.0, w=190.0, h=8.0)

    # Format entries like: WIG20: 2,410 ▲ +0.8% | EUR/PLN: 4.28 ▼ -0.1%
    items = []
    for entry in indices:
        name = entry.get("name", "")
        val = entry.get("value", "")
        change = entry.get("change", 0.0)
        arrow = "▲" if change >= 0 else "▼"
        sign = "+" if change >= 0 else ""
        items.append(f"{name}: {val} {arrow} {sign}{change}%")

    content = "  |  ".join(items)

    return Element(
        id=f"ticker_{uuid.uuid4().hex[:6]}",
        role="band",
        importance=0.4,
        text_content=content,
        frame=frame,
        z=3,
        style=ElementStyle(
            font_family="Inter, monospace",
            font_size_pt=6.5,
            font_weight="bold",
            line_height=1.1,
            color="#FFFFFF",
            bg_color="#111827",
            padding_mm=1.0,
            align="center",
            valign="center",
        ),
    )


def create_editorial_badge_box(
    text: str,
    category: str = "PILNE",
    frame: Optional[Frame] = None,
    bg_color: str = "#C2410C",
    text_color: str = "#FFFFFF",
) -> Element:
    """Create an authentic editorial badge or stamp to anchor columns or headlines."""
    if frame is None:
        frame = Frame(x=10.0, y=10.0, w=40.0, h=16.0)

    clean_cat = (category or "").strip().upper()
    clean_text = polish_microtypography((text or "").strip().upper())
    if clean_cat and clean_cat != clean_text:
        full_content = f"[{clean_cat}]\n{clean_text}"
    else:
        full_content = clean_text

    return Element(
        id=f"badge_{uuid.uuid4().hex[:6]}",
        role="infobox",
        importance=0.55,
        text_content=full_content,
        frame=frame,
        z=3,
        style=ElementStyle(
            font_family="Inter, sans-serif",
            font_size_pt=8.5,
            font_weight="bold",
            line_height=1.15,
            color=text_color,
            bg_color=bg_color,
            border_width_mm=0.5,
            border_color="#FFFFFF",
            padding_mm=2.0,
            align="center",
            valign="center",
        ),
    )


def extract_story_facts(story: Any, max_facts: int = 3) -> List[str]:
    """Extract factual snippets with numbers/statistics or structured infobox without hallucinating."""
    import re
    facts: List[str] = []
    infobox = getattr(story, "infobox", None)
    if infobox and isinstance(infobox, dict):
        for k, v in infobox.items():
            facts.append(f"{k}: {v}")
            if len(facts) >= max_facts:
                return facts

    # Extract sentences with numbers, dates or currency from body/lead
    body = (getattr(story, "lead", None) or "") + " " + (getattr(story, "body", None) or "")
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", body) if s.strip()]
    for s in sentences:
        if re.search(r"\b\d+(?:[.,]\d+)?(?:\s?(?:zł|mln|mld|%|tys\.|proc\.|lat|km|godz\.))?\b", s):
            if 15 <= len(s) <= 120 and s not in facts:
                facts.append(s)
                if len(facts) >= max_facts:
                    break
    return facts

