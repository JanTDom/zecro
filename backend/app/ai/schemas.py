"""Structured-output contracts for every AI task (validated server-side)."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FitDraft(BaseModel):
    text: str
    words: int = 0
    need_more_source: bool = False
    notes: str = ""


class HeadlineOption(BaseModel):
    text: str
    angle: str = ""
    facts_used: list[str] = Field(default_factory=list)


class HeadlineSet(BaseModel):
    headlines: list[HeadlineOption]


class SourcedSentence(BaseModel):
    text: str
    source_id: str
    source_excerpt: str


class BriefArticle(BaseModel):
    headline: str
    kicker: str = ""
    lead: str
    body: str
    sentences: list[SourcedSentence] = Field(default_factory=list)
    need_more_source: bool = False


class SentenceCheck(BaseModel):
    sentence: str
    status: Literal["supported", "partially", "unsupported"]
    source_excerpt: str = ""
    problem: str = ""


class FactCheck(BaseModel):
    sentences: list[SentenceCheck]


class Translation(BaseModel):
    translation: str
    terms: list[str] = Field(default_factory=list)


class Teaser(BaseModel):
    title: str
    sentence: str
    reference: str


class Caption(BaseModel):
    caption: str
    identity_basis: Literal["metadata", "story", "none"] = "none"


class Quote(BaseModel):
    text: str
    speaker: str = ""


class PullQuotes(BaseModel):
    quotes: list[Quote]


class InfoPoint(BaseModel):
    point: str
    source_sentence: str


class InfoBox(BaseModel):
    title: str = ""
    points: list[InfoPoint] = Field(default_factory=list)


class PlanStory(BaseModel):
    story_id: str
    rank: Literal["lead", "second", "third", "short", "brief", "teaser", "box", "column"]
    span_cols: int = 1
    pin_zone: Literal["top", "under_masthead", "left_rail", "right_rail", "center", "bottom", "anywhere"] = "anywhere"
    group: str = ""
    teaser_only: bool = False


class PlanProposal(BaseModel):
    name: str
    rationale: str
    stories: list[PlanStory]


class PlanProposals(BaseModel):
    proposals: list[PlanProposal]


class PhotoBriefAI(BaseModel):
    who: list[str] = Field(default_factory=list)
    where: str = ""
    what_event: str = ""
    when: str = ""
    shot_type: Literal["portrait", "wide", "detail", "archival", "illustration"] = "illustration"
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)
    search_queries_pl: list[str] = Field(default_factory=list)
    search_queries_en: list[str] = Field(default_factory=list)
    is_real_event: bool = False
    real_people: list[str] = Field(default_factory=list)
    illustration_idea: str = ""


class PhotoScore(BaseModel):
    index: int
    relevance: float
    depicts_claimed_subject: Literal["yes", "no", "unknown"] = "unknown"
    newsworthiness: float = 0.0
    technical_quality: float = 0.0
    crop_suggestion: list[int] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reason: str = ""


class PhotoRanking(BaseModel):
    scores: list[PhotoScore]


class PageCritique(BaseModel):
    hierarchy_clear: float
    single_dominant: bool
    eye_path: str = ""
    photo_headline_match: float = 0.0
    masthead_balance: float = 0.0
    dead_zones: list[str] = Field(default_factory=list)
    crowding: list[str] = Field(default_factory=list)
    typographic_issues: list[str] = Field(default_factory=list)
    score: float
    top_3_fixes: list[str] = Field(default_factory=list)


class MaskQA(BaseModel):
    quality: Literal["clean", "minor_issues", "unusable"]
    issues: list[str] = Field(default_factory=list)
    description: str = ""


class CorpusVerdict(BaseModel):
    is_newspaper_or_magazine_page: bool
    page_zone_guess: Literal["front", "inside", "back", "unknown"] = "unknown"
    title_matches_folder: Literal["yes", "no", "unknown"] = "unknown"
    era: str = "unknown"
    language: str = "unknown"
    reason: str = ""


class FontPairing(BaseModel):
    headline_family: str
    body_family: str
    reason: str


class PaletteRoles(BaseModel):
    kicker: Optional[str] = None
    rules: Optional[str] = None
    box_background: Optional[str] = None


class LogoAI(BaseModel):
    letter_style: Literal["serif", "sans", "slab", "script", "display", "blackletter", "mixed"]
    all_caps: bool = False
    contrast: Literal["low", "medium", "high"] = "medium"
    character: list[str] = Field(default_factory=list)
    palette_roles: PaletteRoles = Field(default_factory=PaletteRoles)
    font_pairings: list[FontPairing] = Field(default_factory=list)
    masthead_advice: str = ""


class ImagePrompt(BaseModel):
    prompt: str
    negative: list[str] = Field(default_factory=list)
