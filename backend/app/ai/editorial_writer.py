from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
from ..engine.content_engine import rewrite_source_bound_copy, fit_text_plan
from ..models.schemas import Story, TextPlan
from .source_guard import guard_generated_text, GuardResult
from .gemini_client import generate_json, AIUnavailable
from ..config import settings

class EditorialDraft(BaseModel):
    text: str
    role: str
    status: str = "draft"
    guard: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

class HeadlineVariant(BaseModel):
    text: str
    lines: int = 0
    fits: bool = False
    status: str = "draft"
    provenance: dict[str, Any] = Field(default_factory=dict)


def fit_to_frame(story: Story, role: str, frame: dict[str, float], *, target_words: int | None = None, target_lines: int | None = None) -> EditorialDraft:
    source=str(getattr(story, role, "") or story.body or "")
    plan=TextPlan(story_ref=story.id, issue_ref=story.issue_ref, role=role, target_words=target_words or len(source.split()), target_lines=target_lines or 0, width_mm=float(frame.get("width_mm", frame.get("w", 80))), height_mm=float(frame.get("height_mm", frame.get("h", 60))), columns=int(frame.get("columns",1)), min_words=0, max_words=target_words or 0, min_font_size_pt=float(frame.get("font_size_pt",9.5)))
    output, metadata=rewrite_source_bound_copy(source, role=role, target_words=target_words, locked_passages=story.locked_passages)
    guard=guard_generated_text(output, source)
    fit=fit_text_plan(plan, output)
    return EditorialDraft(text=output, role=role, guard={**guard.__dict__,"flags":[flag.__dict__ for flag in guard.flags],"fit":fit.model_dump(mode="json")}, provenance={**metadata,"status":"draft","fit_status":fit.status})


def headline_variants(story: Story, width_mm: float, font: str, size_pt: float, max_lines: int, n: int = 5) -> list[HeadlineVariant]:
    source=story.headline
    # Offline mode derives candidate sentence-safe trims only; a configured
    # Gemini provider can supply editorial variants through the same contract.
    candidates=[]
    words=source.split()
    for count in dict.fromkeys([len(words), max(1,int(len(words)*.82)), max(1,int(len(words)*.62)), max(1,int(len(words)*.45))]):
        candidate=" ".join(words[:count]).rstrip(" ,;:")
        if count < len(words): candidate += "…"
        plan=TextPlan(story_ref=story.id, issue_ref=story.issue_ref, role="headline", target_lines=max_lines, width_mm=width_mm, height_mm=max_lines*size_pt*.4, columns=1, min_font_size_pt=size_pt)
        fit=fit_text_plan(plan,candidate)
        candidates.append(HeadlineVariant(text=candidate, lines=fit.lines, fits=fit.status=="PASS" and fit.lines<=max_lines, provenance={"provider":"deterministic-local","model":"zecro-headline-fit-v1","status":"draft"}))
    return [item for item in candidates if item.fits][:n]
