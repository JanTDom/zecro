"""Gemini (or any routed model) as the copy editor, always behind the source guard.

Every operation returns drafts with provenance; when the AI is unavailable the
deterministic source-bound trimmer is used and labelled as such.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

from ..engine.content_engine import rewrite_source_bound_copy, fit_text_plan
from ..engine.polish_typography import polish_microtypography
from ..models.schemas import Story, TextPlan
from .gemini_client import AIUnavailable
from .runtime import run_task
from .source_guard import guard_generated_text
from . import schemas as S


class EditorialDraft(BaseModel):
    text: str
    role: str
    status: str = "draft"
    guard: dict[str, Any] = Field(default_factory=dict)
    fit: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    approvable: bool = True


class HeadlineVariant(BaseModel):
    text: str
    lines: int = 0
    fits: bool = False
    angle: str = ""
    status: str = "draft"
    guard: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


def _locked_ok(text: str, locked: list[str]) -> list[str]:
    return [p for p in locked or [] if p and p not in text]


def _finish(text: str, role: str, source: str, provenance: dict, plan: Optional[TextPlan], locked: list[str], ai_pass: bool,
            project_id: Optional[str]) -> EditorialDraft:
    text = polish_microtypography(text)
    guard = guard_generated_text(text, source, provider=provenance.get("provider", "?"), ai_pass=ai_pass, project_id=project_id)
    missing = _locked_ok(text, locked)
    gd = guard.as_dict()
    if missing:
        gd["unsupported"] = gd["unsupported"] + [f"brak zablokowanego fragmentu: {m}" for m in missing]
        gd["status"] = "unsupported"
    fit = fit_text_plan(plan, text).model_dump(mode="json") if plan else {}
    return EditorialDraft(text=text, role=role, guard=gd, fit=fit, provenance=provenance, approvable=gd["status"] == "supported")


def _style(story: Story) -> str:
    return getattr(story, "title_style", None) or "dziennik"


def fit_to_frame(story: Story, role: str, frame: dict[str, float], *, target_words: Optional[int] = None,
                 target_lines: Optional[int] = None, project_id: Optional[str] = None, ai: bool = True) -> EditorialDraft:
    source = str(getattr(story, role, "") or story.body or "")
    plan = TextPlan(story_ref=story.id, issue_ref=story.issue_ref, role=role, target_words=target_words or len(source.split()),
                    target_lines=target_lines or 0, width_mm=float(frame.get("width_mm", frame.get("w", 80))),
                    height_mm=float(frame.get("height_mm", frame.get("h", 60))), columns=int(frame.get("columns", 1)),
                    min_words=0, max_words=target_words or 0, min_font_size_pt=float(frame.get("font_size_pt", 9.5)))
    if ai:
        try:
            full_source = "\n\n".join(filter(None, [story.headline, story.lead, story.body])) if role != "body" else source
            res = run_task("copy_fit", "editorial_writer", {"role": role, "source": source, "context": full_source[:6000],
                           "target_words": target_words, "target_lines": target_lines, "frame": frame, "title_style": _style(story),
                           "locked_passages": story.locked_passages}, S.FitDraft, project_id=project_id)
            draft = _finish(res.data["text"], role, full_source, {**res.provenance, "need_more_source": res.data["need_more_source"],
                            "notes": res.data["notes"]}, plan, story.locked_passages, True, project_id)
            return draft
        except AIUnavailable as exc:
            reason = str(exc)
        else:
            reason = ""
    else:
        reason = "AI disabled for this call"
    output, metadata = rewrite_source_bound_copy(source, role=role, target_words=target_words, locked_passages=story.locked_passages)
    return _finish(output, role, source, {**metadata, "ai_unavailable": reason}, plan, story.locked_passages, False, project_id)


def headline_variants(story: Story, width_mm: float, font: str, size_pt: float, max_lines: int, n: int = 5, *,
                      font_path: Optional[str] = None, project_id: Optional[str] = None) -> list[HeadlineVariant]:
    from ..engine.shaper import measure_text, chars_per_line
    from ..engine.fonts import resolve_font
    font_path = font_path or resolve_font(font, bold=True)
    cpl = chars_per_line(width_mm, size_pt, font_path)
    source = "\n".join(filter(None, [story.headline, story.lead, (story.body or "")[:1500]]))
    try:
        res = run_task("headline_variants", "headline_variants", {"source": source, "max_chars_per_line": cpl, "max_lines": max_lines,
                       "title_style": _style(story), "n": n + 3}, S.HeadlineSet, project_id=project_id)
        options = [(h["text"], h["angle"]) for h in res.data["headlines"]]
        provenance = res.provenance
    except AIUnavailable as exc:
        words = story.headline.split()
        options = [(" ".join(words[:c]), "trim") for c in dict.fromkeys([len(words), max(1, int(len(words) * .75)), max(1, int(len(words) * .5))])]
        provenance = {"provider": "deterministic-local", "ai_unavailable": str(exc)}
    out: list[HeadlineVariant] = []
    for text, angle in options:
        text = polish_microtypography(text.strip().rstrip("."))
        shaped = measure_text(text, width_mm, font_size_pt=size_pt, font_path=font_path)
        fits = shaped.line_count <= max_lines and not shaped.overfull
        guard = guard_generated_text(text, source).as_dict()
        out.append(HeadlineVariant(text=text, lines=shaped.line_count, fits=fits, angle=angle, guard=guard,
                                   provenance={**provenance, "measure": shaped.status, "font_path": font_path}))
    return [v for v in out if v.fits][:n]


def write_from_brief(brief: dict, sources: list[dict], rank: str, target_words: int, *, title_style: str = "dziennik",
                     project_id: Optional[str] = None) -> dict[str, Any]:
    res = run_task("write_from_brief", "write_from_brief", {"brief": brief, "sources": sources, "rank": rank,
                   "target_words": target_words, "title_style": title_style}, S.BriefArticle, project_id=project_id)
    source_text = "\n\n".join(s.get("text", "") for s in sources)
    data = res.data
    data["body"] = polish_microtypography(data["body"])
    unsourced = [s["text"] for s in data["sentences"] if s["source_excerpt"].strip() and s["source_excerpt"].strip() not in source_text]
    guard = guard_generated_text("\n".join([data["headline"], data["lead"], data["body"]]), source_text, ai_pass=True, project_id=project_id).as_dict()
    if unsourced:
        guard["unsupported"] += [f"cytowany fragment źródła nie istnieje: {t}" for t in unsourced]
        guard["status"] = "unsupported"
    return {**data, "guard": guard, "approvable": guard["status"] == "supported", "provenance": res.provenance, "status": "draft"}


def simple_task(task: str, prompt_id: str, payload: dict, schema, source_for_guard: Optional[str] = None,
                project_id: Optional[str] = None) -> dict[str, Any]:
    res = run_task(task, prompt_id, payload, schema, project_id=project_id)
    data = res.data
    out = {**data, "provenance": res.provenance, "status": "draft"}
    if source_for_guard is not None:
        text = " ".join(str(v) for k, v in data.items() if isinstance(v, str))
        out["guard"] = guard_generated_text(text, source_for_guard).as_dict()
        out["approvable"] = out["guard"]["status"] == "supported"
    return out


def pullquotes(story: Story, project_id: Optional[str] = None) -> dict[str, Any]:
    res = run_task("pullquote", "pullquote", {"body": story.body}, S.PullQuotes, project_id=project_id)
    verbatim = [q for q in res.data["quotes"] if q["text"].strip() and q["text"].strip() in story.body]
    rejected = [q for q in res.data["quotes"] if q not in verbatim]
    return {"quotes": verbatim, "rejected_not_verbatim": rejected, "provenance": res.provenance, "status": "draft"}


def infobox(story: Story, project_id: Optional[str] = None) -> dict[str, Any]:
    res = run_task("infobox", "infobox", {"body": story.body, "title_hint": story.headline}, S.InfoBox, project_id=project_id)
    points = [p for p in res.data["points"] if p["source_sentence"].strip()[:60] in story.body]
    return {"title": res.data["title"], "points": points, "dropped_unsourced": len(res.data["points"]) - len(points),
            "provenance": res.provenance, "status": "draft"}
