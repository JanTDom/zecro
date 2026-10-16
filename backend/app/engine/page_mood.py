"""Source-bound editorial intent for page composition.

This is an auditable fallback when no editor has selected a mood.  It does not
claim to understand the truth of an article.  Weak or conflicting lexical
evidence leaves the page neutral/analytical; explicit editor choices win.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models.schemas import PageInputMaterial, StyleBlend


@dataclass(frozen=True)
class MoodProfile:
    name: str
    evidence: str
    headline_delta: float
    geometry_delta: float
    photo_delta: float
    allow_sensational_effects: bool


PROFILES = {
    "urgent": MoodProfile("urgent", "", .08, .04, .10, True),
    "human": MoodProfile("human", "", -.03, -.02, .12, False),
    "solemn": MoodProfile("solemn", "", -.18, -.16, .02, False),
    "celebratory": MoodProfile("celebratory", "", .06, .10, .10, True),
    "analytical": MoodProfile("analytical", "", -.12, -.06, -.12, False),
    "practical": MoodProfile("practical", "", -.10, -.12, -.08, False),
    "scandal": MoodProfile("scandal", "", .07, .06, .06, True),
    "entertainment": MoodProfile("entertainment", "", .04, .08, .12, True),
}

_CUES = {
    "solemn": (r"\b(?:zmarł\w*|nie żyje|śmier[ćc]\w*|traged\w*|żałob\w*|pogrzeb\w*|ofiara\w*|zgin[ąę]\w*)\b",),
    "urgent": (r"\b(?:alarm\w*|ewakuac\w*|piln\w*|pożar\w*|powodz\w*|zagrożen\w*|wypadek\w*)\b",),
    "celebratory": (r"\b(?:zwycię\w*|wygran\w*|świętuj\w*|sukces\w*|narodzin\w*)\b",),
    "human": (r"\b(?:rodzin\w*|bohater\w*|ocali\w*|pomoc\w*|marzen\w*|nowy początek)\b",),
    "scandal": (r"\b(?:skandal\w*|afer\w*|zdradz\w*|zdrad\w*|kłamstw\w*|ujawni\w*|oszu\w*|wstyd\w*|kompromitac\w*)\b",),
    "entertainment": (r"\b(?:gwiazd\w*|celebryt\w*|serial\w*|koncert\w*|festiwal\w*|ślub\w*|show|randk\w*|premier[ay]\w*)\b",),
}


def resolve_page_mood(material: PageInputMaterial) -> MoodProfile:
    explicit = material.editorial_mood
    if explicit != "auto":
        base = PROFILES[explicit]
        return MoodProfile(base.name, "wybór redakcji", base.headline_delta,
                           base.geometry_delta, base.photo_delta, base.allow_sensational_effects)
    lead = max(material.stories, key=lambda s: s.importance, default=None)
    if lead:
        text = " ".join((lead.headline, lead.kicker or "", lead.lead or ""))[:1000].lower()
        for mood in ("solemn", "urgent", "scandal", "celebratory", "entertainment", "human"):
            if any(re.search(pattern, text) for pattern in _CUES[mood]):
                base = PROFILES[mood]
                return MoodProfile(base.name, "sygnał w tytule lub leadzie", base.headline_delta,
                                   base.geometry_delta, base.photo_delta, base.allow_sensational_effects)
    fallback = "practical" if material.page_topic == "practical" else "analytical" if material.page_topic in {"science", "economy", "politics"} else "human"
    base = PROFILES[fallback]
    return MoodProfile(base.name, "temat strony; słaby sygnał emocjonalny", base.headline_delta,
                       base.geometry_delta, base.photo_delta, base.allow_sensational_effects)


def apply_page_mood(blend: StyleBlend, profile: MoodProfile) -> StyleBlend:
    values = (blend.opinion_to_tabloid, blend.classical_to_avantgarde, blend.dense_to_photo)
    deltas = (profile.headline_delta, profile.geometry_delta, profile.photo_delta)
    updated = [min(1.0, max(0.0, float(value) + delta)) for value, delta in zip(values, deltas)]
    return StyleBlend(opinion_to_tabloid=updated[0], classical_to_avantgarde=updated[1], dense_to_photo=updated[2])


def story_color_roles(dna, mood: str) -> tuple[str, str, str]:
    """Return story accent roles; masthead and the title's brand remain DNA-owned."""
    secondary, primary, accent = dna.palette.secondary, dna.palette.primary, dna.palette.accent
    if mood in {"solemn", "analytical", "practical"}:
        return primary, primary, dna.palette.tint_bg
    if mood == "human":
        return secondary, primary, accent
    return secondary, primary, accent


# ---------------------------------------------------------------------------
# Mood -> form.  The profile above shifts the continuous style blend; the
# form below is what the cover generators consume directly: angle, palette
# saturation, display case/width, effects, transgression cost, photo share,
# crop tightness and teaser length.  Title DNA may override every value via
# ``cover_grammar["mood_forms"][mood]`` and ``cover_grammar["mood_palettes"]``.
# ---------------------------------------------------------------------------
import colorsys
from dataclasses import asdict, replace


@dataclass(frozen=True)
class MoodForm:
    mood: str
    angle_deg: float          # diagonal entry of the display headline (negative = rising)
    saturation: float         # multiplier applied to story colour planes
    display_case: str         # "upper" | "normal"
    display_width: str        # "condensed" | "regular"
    outline: bool
    shadow: bool
    transgression_scale: float
    photo_share: float        # share of the editorial body given to the lead photo
    crop: str                 # "tight" | "medium" | "wide"
    teaser_words: int
    sticker: bool             # a rotated label/sticker is appropriate

    def as_dict(self) -> dict:
        return asdict(self)


MOOD_FORMS = {
    "urgent": MoodForm("urgent", -6.0, 1.15, "upper", "condensed", True, True, 1.0, .56, "tight", 10, True),
    "scandal": MoodForm("scandal", -5.0, 1.10, "upper", "condensed", True, True, .9, .52, "tight", 12, True),
    "celebratory": MoodForm("celebratory", -4.0, 1.05, "upper", "condensed", True, False, .8, .58, "medium", 12, True),
    "entertainment": MoodForm("entertainment", -3.5, 1.10, "normal", "condensed", True, False, .8, .55, "tight", 12, True),
    "human": MoodForm("human", -1.5, .85, "normal", "regular", False, False, .5, .60, "medium", 16, False),
    "solemn": MoodForm("solemn", 0.0, .30, "normal", "regular", False, False, .2, .62, "wide", 18, False),
    "analytical": MoodForm("analytical", 0.0, .60, "normal", "regular", False, False, .3, .45, "medium", 18, False),
    "practical": MoodForm("practical", 0.0, .60, "normal", "regular", False, False, .3, .42, "medium", 16, False),
}


def mood_form(dna, mood: str) -> MoodForm:
    base = MOOD_FORMS.get(mood, MOOD_FORMS["human"])
    overrides = ((getattr(dna, "cover_grammar", None) or {}).get("mood_forms") or {}).get(mood) or {}
    allowed = {key: value for key, value in overrides.items() if key in base.__dataclass_fields__ and key != "mood"}
    return replace(base, **allowed) if allowed else base


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = (value or "#000000").lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (0.0, 0.0, 0.0)


def _rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def adjust_color(value: str, *, saturation: float = 1.0, lightness: float = 1.0) -> str:
    h, l, s = colorsys.rgb_to_hls(*_hex_to_rgb(value))
    return _rgb_to_hex(colorsys.hls_to_rgb(h, max(0.0, min(1.0, l * lightness)), max(0.0, min(1.0, s * saturation))))


def relative_luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _hex_to_rgb(value))
    return .2126 * r + .7152 * g + .0722 * b


def readable_ink(background: str, dark: str = "#111111") -> str:
    """White or dark ink with the higher WCAG contrast on ``background``."""
    lum = relative_luminance(background)
    dark_lum = relative_luminance(dark)
    return "#ffffff" if (1.05 / (lum + .05)) >= ((lum + .05) / (dark_lum + .05)) else dark


def mood_palette(dna, mood: str) -> dict[str, str]:
    """Story colour planes for a mood: strong / deep / light (+ readable inks).

    Masthead and brand colours stay DNA-owned; only story planes respond to
    the material.  A tragic story never gets the "tabloid red + yellow" set.
    """
    explicit = ((getattr(dna, "cover_grammar", None) or {}).get("mood_palettes") or {}).get(mood)
    palette = dna.palette
    form = mood_form(dna, mood)
    if explicit:
        strong, deep, light = explicit.get("strong"), explicit.get("deep"), explicit.get("light")
    elif mood == "solemn":
        strong = adjust_color(palette.primary, saturation=form.saturation, lightness=.55)
        deep = adjust_color(palette.primary, saturation=.2, lightness=.35)
        light = palette.tint_bg
    elif mood in {"analytical", "practical"}:
        strong, deep, light = palette.primary, palette.primary, palette.tint_bg
    elif mood == "scandal":
        strong = adjust_color(palette.secondary, saturation=form.saturation)
        deep = adjust_color(palette.primary, saturation=.4, lightness=.38)
        light = palette.accent
    elif mood == "human":
        strong = adjust_color(palette.secondary, saturation=form.saturation, lightness=1.05)
        deep = palette.primary
        light = palette.tint_bg
    else:
        strong = adjust_color(palette.secondary, saturation=form.saturation)
        deep = palette.primary
        light = adjust_color(palette.accent, saturation=form.saturation)
    strong = strong or palette.secondary
    deep = deep or palette.primary
    light = light or palette.accent
    return {"strong": strong, "deep": deep, "light": light,
            "ink_on_strong": readable_ink(strong), "ink_on_deep": readable_ink(deep),
            "ink_on_light": readable_ink(light, dark=deep if relative_luminance(deep) < .2 else "#111111")}
