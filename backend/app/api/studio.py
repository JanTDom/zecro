"""AI studio endpoints working on raw story payloads (Generate/Copy Studio)."""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from ..ai.gemini_client import AIUnavailable, AIBudgetExceeded
from ..models.schemas import StoryInput, Story
from ..models.database import db

router = APIRouter(tags=["studio"])


def _ai(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except AIBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail={"status": "budget_exceeded", "reason": str(exc)})
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail={"status": "unavailable", "reason": str(exc)})


def _story(s: StoryInput) -> Story:
    return Story(id=s.id, issue_ref="studio", slug=s.id, headline=s.headline, lead=s.lead, body=s.body, deck=s.deck,
                 byline=s.byline, locked_passages=list(s.locked_passages or []))


class FitReq(BaseModel):
    story: StoryInput
    role: str = "body"
    frame: dict[str, float] = Field(default_factory=lambda: {"width_mm": 80, "height_mm": 60, "columns": 1, "font_size_pt": 9.5})
    target_words: Optional[int] = None
    target_lines: Optional[int] = None
    project_id: Optional[str] = None


@router.post("/ai/copy/fit")
def ai_copy_fit(req: FitReq):
    from ..ai.editorial_writer import fit_to_frame
    return _ai(fit_to_frame, _story(req.story), req.role, req.frame, target_words=req.target_words, target_lines=req.target_lines, project_id=req.project_id)


class HeadReq(BaseModel):
    story: StoryInput
    width_mm: float
    font: str = "Playfair Display, serif"
    size_pt: float = 36
    max_lines: int = 2
    n: int = 5
    project_id: Optional[str] = None


@router.post("/ai/headlines")
def ai_headlines(req: HeadReq):
    from ..ai.editorial_writer import headline_variants
    return _ai(headline_variants, _story(req.story), req.width_mm, req.font, req.size_pt, req.max_lines, req.n, project_id=req.project_id)


class BriefReq(BaseModel):
    brief: dict[str, Any]
    sources: list[dict[str, str]]
    rank: str = "second"
    target_words: int = 350
    title_style: str = "dziennik"
    project_id: Optional[str] = None


@router.post("/ai/write-from-brief")
def ai_write(req: BriefReq):
    from ..ai.editorial_writer import write_from_brief
    return _ai(write_from_brief, req.brief, req.sources, req.rank, req.target_words, title_style=req.title_style, project_id=req.project_id)


class SimpleReq(BaseModel):
    story: StoryInput
    target_language: str = "en"
    page_number: int = 2
    max_words: int = 25
    project_id: Optional[str] = None


@router.post("/ai/translate")
def ai_translate(req: SimpleReq):
    from ..ai.editorial_writer import simple_task
    from ..ai import schemas as S
    src = "\n\n".join(filter(None, [req.story.headline, req.story.lead, req.story.body]))
    return _ai(simple_task, "translate", "translate", {"text": src, "target_language": req.target_language, "title_style": "dziennik"}, S.Translation, project_id=req.project_id)


@router.post("/ai/teaser")
def ai_teaser(req: SimpleReq):
    from ..ai.editorial_writer import simple_task
    from ..ai import schemas as S
    src = "\n".join(filter(None, [req.story.headline, req.story.lead, req.story.body[:1500]]))
    return _ai(simple_task, "teaser", "teaser", {"headline": req.story.headline, "lead": req.story.lead or req.story.body[:600],
               "page_number": req.page_number, "max_words": req.max_words}, S.Teaser, source_for_guard=src, project_id=req.project_id)


@router.post("/ai/pullquotes")
def ai_pullquotes(req: SimpleReq):
    from ..ai.editorial_writer import pullquotes
    return _ai(pullquotes, _story(req.story), project_id=req.project_id)


@router.post("/ai/infobox")
def ai_infobox(req: SimpleReq):
    from ..ai.editorial_writer import infobox
    return _ai(infobox, _story(req.story), project_id=req.project_id)


class GuardReq(BaseModel):
    output: str
    source: str
    ai_pass: bool = True


@router.post("/ai/fact-guard")
def ai_guard(req: GuardReq):
    from ..ai.source_guard import guard_generated_text
    return guard_generated_text(req.output, req.source, ai_pass=req.ai_pass).as_dict()


# ------------------------------------------------------------- photos
class PhotoReq(BaseModel):
    story: StoryInput
    providers: Optional[list[str]] = None
    limit: int = 6
    project_id: Optional[str] = None


@router.get("/photos/sources")
def photo_sources():
    from ..integrations.photo_sources import source_status
    return source_status()


@router.post("/photos/propose")
def photos_propose(req: PhotoReq):
    from ..ai.photo_pipeline import propose_photos
    return _ai(propose_photos, req.story, project_id=req.project_id, limit=req.limit, providers=req.providers)


class AcceptReq(BaseModel):
    candidate: dict[str, Any]
    story: Optional[StoryInput] = None
    project_id: Optional[str] = None


@router.post("/photos/accept")
def photos_accept(req: AcceptReq):
    from ..ai.photo_pipeline import accept_photo
    return _ai(accept_photo, req.candidate, req.story, project_id=req.project_id)


class IllustrateReq(BaseModel):
    story: StoryInput
    style: str = "editorial vector illustration"
    aspect_ratio: str = "4:3"
    palette: list[str] = Field(default_factory=list)
    n: int = 3
    project_id: Optional[str] = None


@router.post("/photos/illustrate")
def photos_illustrate(req: IllustrateReq):
    from ..ai.photo_pipeline import generate_illustration
    return _ai(generate_illustration, req.story, project_id=req.project_id, aspect_ratio=req.aspect_ratio, style=req.style, palette=req.palette, n=req.n)


# ------------------------------------------------------------- fonts
@router.get("/fonts")
def fonts_list(polish_only: bool = False):
    from ..engine.fonts import families
    return families(require_polish=polish_only)


@router.get("/fonts/google")
def fonts_google(q: str = "", polish_only: bool = True, limit: int = 60):
    from ..engine.fonts import google_catalog
    rows = google_catalog(polish_only)
    if q:
        rows = [r for r in rows if q.lower() in r["family"].lower()]
    return sorted(rows, key=lambda r: r.get("popularity") or 1e9)[:limit]


class GoogleInstall(BaseModel):
    family: str
    weights: list[int] = Field(default_factory=lambda: [400, 700])
    italics: bool = True


@router.post("/fonts/google/install")
def fonts_google_install(req: GoogleInstall):
    from ..engine.fonts import install_google_font, FontRejected
    try:
        return install_google_font(req.family, req.weights, req.italics)
    except FontRejected as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/fonts/upload")
async def fonts_upload(files: list[UploadFile] = File(...), source: str = Form("upload"), license_note: str = Form("")):
    from ..engine.fonts import ingest_bytes, FontRejected
    out = []
    for f in files:
        try:
            out += ingest_bytes(await f.read(), f.filename or "font.otf", source=source, license_note=license_note)
        except FontRejected as exc:
            out.append({"status": "unsupported", "file": f.filename, "reason": str(exc)})
        except Exception as exc:
            out.append({"status": "error", "file": f.filename, "reason": str(exc)[:200]})
    return out


@router.delete("/fonts/{font_id}")
def fonts_delete(font_id: str):
    if not db.delete_font(font_id):
        raise HTTPException(status_code=404, detail="font not found")
    return {"status": "deleted"}


class FontCheck(BaseModel):
    family: str
    text: str


@router.post("/fonts/check")
def fonts_check(req: FontCheck):
    from ..engine.fonts import _candidates
    faces = db.list_fonts(req.family.split(",")[0].strip())
    needed = set(req.text)
    return [{"subfamily": f["subfamily"], "weight": f["weight"], "italic": f["italic"], "missing_in_text": sorted(needed & set(f["missing_chars"]))} for f in faces]


# ------------------------------------------------------------- critique & mask QA
@router.post("/candidates/{candidate_id}/critique")
def candidate_critique(candidate_id: str):
    from ..ai.visual_critic import critique
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    dna = db.get_title_dna(cand.scene_graph.page.title_dna_ref) if cand.scene_graph.page.title_dna_ref else None
    if dna is None:
        from ..engine.grammar import create_default_broadsheet_dna
        dna = create_default_broadsheet_dna()
    return _ai(critique, cand.scene_graph, dna)


class MaskQAReq(BaseModel):
    original: str
    mask: str


@router.post("/assets/mask-qa")
def mask_qa(req: MaskQAReq):
    from ..ai.mask_qa import review_mask
    return _ai(review_mask, req.original, req.mask)
