from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from ..models.schemas import Story


class PhotoBrief(BaseModel):
    who: list[str] = Field(default_factory=list)
    where: str = ""
    what_event: str = ""
    when: str = ""
    shot_type: str = "illustration"
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)
    search_queries_pl: list[str] = Field(default_factory=list)
    search_queries_en: list[str] = Field(default_factory=list)
    is_real_event: bool = False
    real_people: list[str] = Field(default_factory=list)
    illustration_idea: str = ""
    provenance: dict = Field(default_factory=dict)


def build_photo_brief(story: Story, project_id: Optional[str] = None) -> PhotoBrief:
    """AI brief; offline fallback is conservative (treats the story as real)."""
    from .runtime import run_task
    from .gemini_client import AIUnavailable
    from .schemas import PhotoBriefAI
    try:
        res = run_task("photo_brief", "photo_brief", {"headline": story.headline, "lead": story.lead or "", "body": (story.body or "")[:3000]},
                       PhotoBriefAI, project_id=project_id)
        return PhotoBrief(**res.data, provenance=res.provenance)
    except AIUnavailable as exc:
        return PhotoBrief(what_event=story.headline, shot_type="archival", search_queries_pl=[story.headline],
                          search_queries_en=[], is_real_event=True, provenance={"provider": "deterministic-local", "ai_unavailable": str(exc),
                          "note": "bez AI tekst traktowany zachowawczo jako realne zdarzenie"})
