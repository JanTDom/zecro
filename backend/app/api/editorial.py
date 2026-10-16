"""Editorial planning, provenance and copyfit API.

The content layer persists structured objects separately from geometry.  Its
default writer is deterministic and source-bound; deployments can replace it
with an LLM adapter without changing the contracts or approval gates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..engine.content_engine import (
    build_flat_plan,
    build_text_plans_for_flatplan,
    content_hash,
    extract_claims,
    fit_text_plan,
    generate_copy_variants,
    rewrite_source_bound_copy,
)
from ..engine.polish_typography import polish_microtypography
from ..ai.editorial_writer import fit_to_frame as ai_fit_to_frame, headline_variants as ai_headline_variants
from ..ai.source_guard import guard_generated_text
from ..ai.integration_registry import registry
from ..models.database import db
from ..models.schemas import (
    Asset, CopyVariant, EditorialBrief, GenerationRequest, GenerationRun,
    Issue, IssuePlan, PageInputMaterial, PreflightReport, Source, Story,
    StoryImageInput, StoryInput, StyleBlend, TextFitResult, TextPlan,
)

router = APIRouter(tags=["editorial", "content"])


class GuardRequest(BaseModel):
    output: str
    source: str


@router.post("/editorial/source-guard")
def source_guard_endpoint(request: GuardRequest):
    result = guard_generated_text(request.output, request.source)
    return {"status": result.status, "unsupported": result.unsupported,
            "flags": [flag.__dict__ for flag in result.flags], "provenance": result.provenance}


class HeadlineRequest(BaseModel):
    width_mm: float = Field(gt=0)
    font: str = ""
    size_pt: float = Field(default=24, gt=0)
    max_lines: int = Field(default=2, ge=1)
    n: int = Field(default=5, ge=1, le=20)


@router.post("/stories/{story_id}/headline-variants")
def story_headline_variants(story_id: str, request: HeadlineRequest):
    story = _get("story", story_id, Story)
    variants = ai_headline_variants(story, request.width_mm, request.font, request.size_pt, request.max_lines, request.n)
    return {"status": "draft", "provider": "deterministic-local", "variants": [item.model_dump(mode="json") for item in variants]}


class VariantRequest(BaseModel):
    roles: Optional[List[str]] = None


class RewriteRequest(BaseModel):
    role: str = "body"
    text: Optional[str] = None
    target_words: Optional[int] = None
    variant_kind: str = "medium"


class FrameCopyRequest(BaseModel):
    """Copy Studio request bound to an actual scene frame."""

    element_ref: str
    text: Optional[str] = None
    role: Optional[str] = None
    target_words: Optional[int] = Field(default=None, ge=1, le=5000)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    columns: int = Field(default=1, ge=1, le=12)
    font_size_pt: float = Field(default=9.0, gt=0, le=120)
    line_height_pt: Optional[float] = Field(default=None, gt=0, le=180)
    locked_passages: List[str] = Field(default_factory=list)


class FrameCopyResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    version: int = 1
    status: str = "draft"
    element_ref: str
    role: str
    text: str
    source_words: int
    output_words: int
    target_words: int
    provider: str
    needs_more_source: bool = False
    fit: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class CandidateFrameCopyRequest(BaseModel):
    element_ref: str
    text: Optional[str] = None
    target_words: Optional[int] = Field(default=None, ge=1, le=5000)
    locked_passages: List[str] = Field(default_factory=list)


class FitRequest(BaseModel):
    text: str
    variant_ref: Optional[str] = None


class TranslateRequest(BaseModel):
    """Request a provider-neutral translation record.

    A local deployment without a configured translation adapter returns the
    source text as a clearly marked draft.  It never presents an unchanged
    string as an approved translation or invents a translated fact.
    """

    target_language: str = Field(min_length=2, max_length=16)
    role: str = "body"
    text: Optional[str] = None


class LockPassageRequest(BaseModel):
    passage: str = Field(min_length=1)
    locked: bool = True


class IssueLayoutRequest(BaseModel):
    page_number: int = Field(default=1, ge=1)
    page_zone: Optional[str] = None
    story_refs: Optional[List[str]] = None
    num_candidates: int = Field(default=8, ge=1, le=24)
    population_size: int = Field(default=30, ge=10, le=100)
    generations: int = Field(default=15, ge=1, le=50)
    allow_transgressions: bool = True
    style_blend: Optional[StyleBlend] = None
    seed: Optional[int] = None


def _not_found(kind: str, identifier: str):
    raise HTTPException(status_code=404, detail=f"{kind} '{identifier}' not found")


def _get(kind: str, identifier: str, model):
    payload = db.get_editorial_object(kind, identifier)
    if not payload:
        _not_found(kind, identifier)
    return model(**payload)


@router.post("/projects/{project_id}/issues", response_model=Issue, status_code=status.HTTP_201_CREATED)
def create_issue(project_id: str, issue: Issue):
    if not db.get_project(project_id):
        _not_found("project", project_id)
    issue.project_id = project_id
    issue.content_hash = content_hash(issue.model_dump_json())
    db.save_editorial_object("issue", issue, project_id=project_id, reason="issue_created")
    return issue


@router.get("/projects/{project_id}/issues", response_model=List[Issue])
def list_issues(project_id: str):
    if not db.get_project(project_id):
        _not_found("project", project_id)
    return [Issue(**row) for row in db.list_editorial_objects("issue", project_id=project_id)]


@router.get("/issues/{issue_id}", response_model=Issue)
def get_issue(issue_id: str):
    return _get("issue", issue_id, Issue)


@router.post("/issues/{issue_id}/sources", response_model=Source, status_code=status.HTTP_201_CREATED)
def create_source(issue_id: str, source: Source):
    _get("issue", issue_id, Issue)
    source.issue_ref = issue_id
    source.content_hash = content_hash(source.model_dump_json())
    db.save_editorial_object("source", source, issue_ref=issue_id, reason="source_ingested")
    return source


@router.get("/issues/{issue_id}/sources", response_model=List[Source])
def list_sources(issue_id: str):
    _get("issue", issue_id, Issue)
    return [Source(**row) for row in db.list_editorial_objects("source", issue_ref=issue_id)]


@router.post("/issues/{issue_id}/briefs", response_model=EditorialBrief, status_code=status.HTTP_201_CREATED)
def create_brief(issue_id: str, brief: EditorialBrief):
    _get("issue", issue_id, Issue)
    brief.issue_ref = issue_id
    brief.content_hash = content_hash(brief.model_dump_json())
    db.save_editorial_object("brief", brief, issue_ref=issue_id, reason="brief_created")
    return brief


@router.get("/issues/{issue_id}/briefs", response_model=List[EditorialBrief])
def list_briefs(issue_id: str):
    _get("issue", issue_id, Issue)
    return [EditorialBrief(**row) for row in db.list_editorial_objects("brief", issue_ref=issue_id)]


@router.post("/issues/{issue_id}/plan", response_model=IssuePlan, status_code=status.HTTP_201_CREATED)
def save_issue_plan(issue_id: str, plan: IssuePlan):
    _get("issue", issue_id, Issue)
    plan.issue_ref = issue_id
    plan.content_hash = content_hash(plan.model_dump_json())
    db.save_editorial_object("issue_plan", plan, issue_ref=issue_id, reason="flatplan_saved")
    return plan


class AutoPlanRequest(BaseModel):
    variant: Literal["dense", "standard", "breathing", "poster"] = "standard"


@router.post("/issues/{issue_id}/plan/auto", response_model=IssuePlan, status_code=status.HTTP_201_CREATED)
def auto_issue_plan(issue_id: str, request: AutoPlanRequest = AutoPlanRequest()):
    issue = _get("issue", issue_id, Issue)
    stories = [Story(**row) for row in db.list_editorial_objects("story", issue_ref=issue_id)]
    plan = build_flat_plan(issue, stories, variant=request.variant)
    # Copy budgets are persisted alongside the flatplan, before layout
    # geometry.  The next generation pass can bind these stable frame refs to
    # concrete scene-graph elements and immediately run copyfit.
    text_plans = build_text_plans_for_flatplan(issue, stories, plan)
    plans_by_page: Dict[int, List[str]] = {}
    for text_plan in text_plans:
        text_plan.content_hash = content_hash(text_plan.model_dump_json())
        db.save_editorial_object("text_plan", text_plan, issue_ref=issue_id, reason="text_plan_auto_planned")
        page_number = int((text_plan.page_ref or "page-1").rsplit("page-", 1)[-1])
        plans_by_page.setdefault(page_number, []).append(text_plan.id)
    for page in plan.pages:
        page.text_plan_refs = plans_by_page.get(page.page_number, [])
    plan.content_hash = content_hash(plan.model_dump_json())
    db.save_editorial_object("issue_plan", plan, issue_ref=issue_id, reason="flatplan_auto_planned")
    return plan


@router.get("/issues/{issue_id}/plan", response_model=IssuePlan)
def get_issue_plan(issue_id: str):
    _get("issue", issue_id, Issue)
    rows = db.list_editorial_objects("issue_plan", issue_ref=issue_id)
    if not rows:
        _not_found("issue plan", issue_id)
    return IssuePlan(**rows[0])


@router.post("/issues/{issue_id}/stories", response_model=Story, status_code=status.HTTP_201_CREATED)
def create_story(issue_id: str, story: Story):
    _get("issue", issue_id, Issue)
    story.issue_ref = issue_id
    story.content_hash = content_hash(story.model_dump_json())
    db.save_editorial_object("story", story, issue_ref=issue_id, reason="story_created")
    return story


@router.get("/issues/{issue_id}/stories", response_model=List[Story])
def list_stories(issue_id: str):
    _get("issue", issue_id, Issue)
    return [Story(**row) for row in db.list_editorial_objects("story", issue_ref=issue_id)]


def _story_input_from_editorial(story: Story, text_plan_refs: Optional[Dict[str, str]] = None) -> StoryInput:
    """Map the content contract to the geometry generator's input contract."""
    images: List[StoryImageInput] = []
    for asset_id in story.asset_refs:
        asset_payload = db.get_editorial_object("asset", asset_id)
        if not asset_payload or asset_payload.get("asset_type") != "photo":
            continue
        images.append(StoryImageInput(
            id=asset_id,
            image_id=asset_id,
            url=str(asset_payload.get("uri") or ""),
            caption=asset_payload.get("caption"),
            credit=asset_payload.get("credit_line"),
            focal_point=asset_payload.get("focal_point") or [0.5, 0.5],
            width_px=asset_payload.get("width_px"),
            height_px=asset_payload.get("height_px"),
            dpi=asset_payload.get("dpi"),
            treatment="cutout" if asset_payload.get("metadata", {}).get("treatment") == "cutout" else None,
        ))
    return StoryInput(
        id=story.id,
        headline=story.headline,
        deck=story.deck,
        lead=story.lead,
        body=story.body,
        byline=story.byline,
        importance=story.importance,
        images=images,
        source_refs=list(story.source_refs),
        claim_refs=[claim.id for claim in story.claims],
        content_revision_ref=f"{story.id}:v{story.version}",
        text_plan_refs=text_plan_refs or {},
        locked_passages=list(story.locked_passages),
        approval_status=story.editorial_status,
    )


@router.post("/issues/{issue_id}/generate-layouts", response_model=GenerationRun, status_code=status.HTTP_201_CREATED)
def generate_issue_layouts(issue_id: str, request: IssueLayoutRequest = IssueLayoutRequest()):
    """Generate geometry from the issue's approved content contracts.

    The issue endpoint is a thin orchestration layer: content remains stored
    as Story/Claim revisions, while the existing project generator still owns
    exploration, critic scoring and candidate persistence.
    """
    issue = _get("issue", issue_id, Issue)
    if request.page_number > issue.page_count:
        raise HTTPException(status_code=422, detail="page_number exceeds issue.page_count")
    stories = [Story(**row) for row in db.list_editorial_objects("story", issue_ref=issue_id)]
    flat_plans = db.list_editorial_objects("issue_plan", issue_ref=issue_id)
    flat_plan = IssuePlan(**flat_plans[0]) if flat_plans else None
    planned_page = next((page for page in flat_plan.pages if page.page_number == request.page_number), None) if flat_plan else None
    selected_refs = request.story_refs if request.story_refs is not None else planned_page.story_refs if planned_page else None
    if selected_refs is not None:
        allowed = set(selected_refs)
        stories = [story for story in stories if story.id in allowed]
    if not stories:
        raise HTTPException(status_code=409, detail="Issue has no stories selected for layout generation")
    zone = request.page_zone or ("front_page" if request.page_number == 1 else "back_page" if request.page_number == issue.page_count else "spread")
    if zone not in {"front_page", "spread", "back_page"}:
        raise HTTPException(status_code=422, detail="page_zone must be front_page, spread or back_page")
    text_plans = [TextPlan(**row) for row in db.list_editorial_objects("text_plan", issue_ref=issue_id)]
    if request.story_refs is not None:
        selected_story_set = set(request.story_refs)
        allowed_text_plans = {item.id for item in text_plans if item.story_ref in selected_story_set}
    else:
        allowed_text_plans = set(planned_page.text_plan_refs) if planned_page else None
    refs_by_story: Dict[str, Dict[str, str]] = {}
    for text_plan in text_plans:
        if allowed_text_plans is not None and text_plan.id not in allowed_text_plans:
            continue
        # list_editorial_objects returns newest first; retain the latest role
        # budget when multiple revisions/plans exist for the same story.
        refs_by_story.setdefault(text_plan.story_ref, {}).setdefault(text_plan.role, text_plan.id)
    material = PageInputMaterial(
        issue_date=issue.publication_date,
        issue_number=issue.issue_number,
        section_name=issue.sections[0] if issue.sections else "EDITORIAL",
        masthead_title="ZECRO",
        page_zone=zone,
        style_blend=request.style_blend or StyleBlend(),
        stories=[_story_input_from_editorial(story, refs_by_story.get(story.id)) for story in stories],
    )
    generation = GenerationRequest(
        material=material,
        num_candidates=request.num_candidates,
        population_size=request.population_size,
        generations=request.generations,
        allow_transgressions=request.allow_transgressions,
        style_blend=request.style_blend,
        page_zone=zone,
        seed=request.seed,
    )
    # Import locally to keep router import order and FastAPI app startup free
    # from a circular dependency.
    from .generate import execute_generation_run
    run = execute_generation_run(issue.project_id, generation)
    for candidate in run.candidates:
        candidate.scene_graph.page.issue_ref = issue.id
        candidate.scene_graph.page.page_number = request.page_number
        candidate.scene_graph.page.page_role = "front" if request.page_number == 1 else "back" if request.page_number == issue.page_count else "spread"
        candidate.scene_graph.metadata.update({"issue_ref": issue.id, "page_number": request.page_number})
        if flat_plan:
            candidate.scene_graph.metadata["issue_plan_ref"] = flat_plan.id
    db.save_generation_run(run)
    return run


@router.get("/stories/{story_id}", response_model=Story)
def get_story(story_id: str):
    return _get("story", story_id, Story)


@router.post("/stories/{story_id}/generate-variants", response_model=List[CopyVariant])
def generate_variants(story_id: str, request: VariantRequest = VariantRequest()):
    story = _get("story", story_id, Story)
    if not story.claims:
        story.claims = extract_claims(story.body, story.source_refs)
        story.content_hash = content_hash(story.model_dump_json())
        story.version += 1
        db.save_editorial_object("story", story, issue_ref=story.issue_ref, reason="claims_extracted")
    variants = generate_copy_variants(story, request.roles)
    for variant in variants:
        db.save_editorial_object("copy_variant", variant, issue_ref=story.issue_ref, reason="variant_generated")
    return variants


@router.post("/stories/{story_id}/rewrite", response_model=CopyVariant, status_code=status.HTTP_201_CREATED)
def rewrite_story(story_id: str, request: RewriteRequest):
    story = _get("story", story_id, Story)
    text = request.text if request.text is not None else str(getattr(story, request.role, "") or "")
    rewritten, metadata = rewrite_source_bound_copy(
        text,
        role=request.role,
        target_words=request.target_words,
        locked_passages=story.locked_passages,
    )
    variant = CopyVariant(story_ref=story.id, role=request.role, variant_kind=request.variant_kind, text=rewritten, target_words=request.target_words or len(rewritten.split()), target_chars=len(rewritten), claim_refs=[claim.id for claim in story.claims], source_refs=list(story.source_refs), locked_passages=list(story.locked_passages), provenance={**metadata, "operation": "rewrite", "source_revision": story.version})
    variant.content_hash = content_hash(variant.text)
    db.save_editorial_object("copy_variant", variant, issue_ref=story.issue_ref, reason="editorial_rewrite")
    return variant


@router.post("/stories/{story_id}/shorten", response_model=CopyVariant, status_code=status.HTTP_201_CREATED)
def shorten_story(story_id: str, request: RewriteRequest):
    request.variant_kind = "exact_fit"
    request.target_words = request.target_words or 60
    return rewrite_story(story_id, request)


@router.post("/stories/{story_id}/copy/fit", response_model=FrameCopyResponse)
def fit_story_copy_to_frame(story_id: str, request: FrameCopyRequest):
    """Propose source-bound copy for one concrete frame.

    This endpoint is intentionally a *proposal*: it measures the actual
    geometry and returns provenance/warnings.  Applying it to a candidate is a
    separate scene edit so an editor can compare, undo, or lock the passage.
    """

    story = _get("story", story_id, Story)
    role = request.role or "body"
    if role not in {"kicker", "headline", "deck", "lead", "body", "caption", "byline", "dateline", "pullquote", "factbox", "teaser"}:
        raise HTTPException(status_code=422, detail=f"Unsupported copy role: {role}")
    source = request.text if request.text is not None else str(getattr(story, role, "") or "")
    if not source.strip():
        raise HTTPException(status_code=422, detail=f"Story has no source text for role '{role}'")
    source_words = len(source.split())
    target = request.target_words or source_words
    output, metadata = rewrite_source_bound_copy(
        source,
        role=role,
        target_words=target,
        locked_passages=request.locked_passages or story.locked_passages,
    )
    # Reuse the canonical copyfit estimator through a transient TextPlan.  It
    # carries the same columns, leading and hard gates as production export.
    plan = TextPlan(
        story_ref=story.id,
        issue_ref=story.issue_ref,
        frame_ref=request.element_ref,
        role=role,
        target_words=target,
        min_words=1,
        max_words=max(target, source_words),
        columns=request.columns,
        width_mm=request.width_mm,
        height_mm=request.height_mm,
        min_font_size_pt=request.font_size_pt,
        widow_lines=0 if role in {"headline", "kicker", "byline"} else 2,
        orphan_lines=0 if role in {"headline", "kicker", "byline"} else 2,
        no_break_tokens=request.locked_passages or story.locked_passages,
    )
    fit = fit_text_plan(plan, output)
    warnings = list(fit.warnings)
    if metadata.get("needs_more_source"):
        warnings.append("Źródło jest krótsze od żądanego limitu; system nie dopisał niepotwierdzonych faktów.")
    response = FrameCopyResponse(
        element_ref=request.element_ref,
        role=role,
        text=output,
        source_words=source_words,
        output_words=len(output.split()),
        target_words=target,
        provider=str(metadata.get("provider") or "deterministic-local"),
        needs_more_source=bool(metadata.get("needs_more_source")),
        fit=fit.model_dump(mode="json"),
        warnings=warnings,
    )
    db.save_editorial_object("copy_fit_proposal", response, issue_ref=story.issue_ref, reason="frame_copyfit_proposal")
    return response


@router.post("/candidates/{candidate_id}/copy/fit", response_model=FrameCopyResponse)
def fit_candidate_copy_to_frame(candidate_id: str, request: CandidateFrameCopyRequest):
    """Fit text directly against a selected candidate's scene-graph frame."""

    candidate = db.get_candidate(candidate_id)
    if not candidate:
        _not_found("candidate", candidate_id)
    element = next((item for item in candidate.scene_graph.elements if item.id == request.element_ref), None)
    if not element or not element.text_content:
        raise HTTPException(status_code=404, detail="Text element not found in candidate")
    role = element.role
    source = request.text if request.text is not None else element.text_content
    source_words = len(source.split())
    target = request.target_words or source_words
    output, metadata = rewrite_source_bound_copy(
        source,
        role=role,
        target_words=target,
        locked_passages=request.locked_passages,
    )
    style = element.style
    font_size = float((style.font_size_pt if style else None) or 9.0)
    plan = TextPlan(
        story_ref=element.story_ref or element.id,
        issue_ref=candidate.scene_graph.page.issue_ref or "candidate",
        frame_ref=element.id,
        role=role,
        target_words=target,
        min_words=1,
        max_words=max(target, source_words),
        columns=max(1, int((style.columns if style else None) or 1)),
        width_mm=element.frame.w,
        height_mm=element.frame.h,
        min_font_size_pt=font_size,
        widow_lines=0 if role in {"headline", "kicker", "byline"} else 2,
        orphan_lines=0 if role in {"headline", "kicker", "byline"} else 2,
        no_break_tokens=request.locked_passages,
    )
    fit = fit_text_plan(plan, output)
    warnings = list(fit.warnings)
    if metadata.get("needs_more_source"):
        warnings.append("Źródło jest krótsze od żądanego limitu; system nie dopisał niepotwierdzonych faktów.")
    response = FrameCopyResponse(
        element_ref=element.id,
        role=role,
        text=output,
        source_words=source_words,
        output_words=len(output.split()),
        target_words=target,
        provider=str(metadata.get("provider") or "deterministic-local"),
        needs_more_source=bool(metadata.get("needs_more_source")),
        fit=fit.model_dump(mode="json"),
        warnings=warnings,
    )
    db.save_editorial_object("copy_fit_proposal", response, issue_ref=candidate.scene_graph.page.issue_ref, reason="candidate_copyfit_proposal")
    return response


@router.post("/stories/{story_id}/translate", response_model=CopyVariant, status_code=status.HTTP_201_CREATED)
def translate_story(story_id: str, request: TranslateRequest):
    """Create a reviewable translation placeholder when no adapter is configured."""
    story = _get("story", story_id, Story)
    text = request.text if request.text is not None else str(getattr(story, request.role, "") or "")
    if not text:
        raise HTTPException(status_code=422, detail=f"Story has no text for role '{request.role}'")
    variant = CopyVariant(
        story_ref=story.id,
        role=request.role,
        variant_kind="medium",
        text=polish_microtypography(text),
        target_words=len(text.split()),
        target_chars=len(text),
        claim_refs=[claim.id for claim in story.claims],
        source_refs=list(story.source_refs),
        locked_passages=list(story.locked_passages),
        status="draft",
        provenance={
            "provider": "disabled-local",
            "model": "no-translation-adapter",
            "operation": "translate",
            "source_language": story.language,
            "target_language": request.target_language,
            "requires_editor": True,
        },
        approval={"editorial": "pending", "fact_check": "pending"},
    )
    variant.content_hash = content_hash(variant.text)
    db.save_editorial_object("copy_variant", variant, issue_ref=story.issue_ref, reason="translation_draft_created")
    return variant


@router.post("/stories/{story_id}/factcheck", response_model=Story)
def factcheck_story(story_id: str):
    story = _get("story", story_id, Story)
    sources = db.list_editorial_objects("source", issue_ref=story.issue_ref)
    source_text = " ".join(str(item.get("excerpt") or "") for item in sources)
    claims = story.claims or extract_claims(story.body, story.source_refs)
    for claim in claims:
        if claim.source_refs and source_text and claim.text.rstrip(".") in source_text:
            claim.status, claim.confidence, claim.evidence_excerpt = "verified", 0.95, claim.text
        elif claim.source_refs:
            claim.status, claim.confidence = "partially_verified", 0.45
        else:
            claim.status, claim.confidence = "unverified", 0.0
    story.claims = claims
    story.fact_checked = bool(story.claims) and all(c.status == "verified" for c in story.claims)
    story.editorial_status = "fact_check" if not story.fact_checked else "approved_for_layout"
    story.version += 1
    story.content_hash = content_hash(story.model_dump_json())
    db.save_editorial_object("story", story, issue_ref=story.issue_ref, reason="factcheck_completed")
    return story


@router.post("/stories/{story_id}/approve", response_model=Story)
def approve_story(story_id: str):
    """Close the editorial gate explicitly after a successful fact check."""
    story = _get("story", story_id, Story)
    if not story.fact_checked:
        raise HTTPException(status_code=409, detail="Story must pass fact-check before editorial approval")
    story.editor_approved = True
    story.editorial_status = "approved_for_layout"
    story.version += 1
    story.content_hash = content_hash(story.model_dump_json())
    db.save_editorial_object("story", story, issue_ref=story.issue_ref, reason="story_approved_for_layout")
    return story


@router.post("/stories/{story_id}/lock", response_model=Story)
def lock_story_passage(story_id: str, request: LockPassageRequest):
    """Add or remove a human-locked passage without rewriting story copy."""
    story = _get("story", story_id, Story)
    passages = list(story.locked_passages)
    if request.locked and request.passage not in passages:
        passages.append(request.passage)
    elif not request.locked:
        passages = [passage for passage in passages if passage != request.passage]
    story.locked_passages = passages
    story.version += 1
    story.content_hash = content_hash(story.model_dump_json())
    db.save_editorial_object("story", story, issue_ref=story.issue_ref, reason="story_passage_lock_changed")
    return story


@router.post("/assets/records", response_model=Asset, status_code=status.HTTP_201_CREATED)
def register_asset(asset: Asset):
    asset.content_hash = asset.content_hash or content_hash(asset.model_dump_json())
    db.save_editorial_object("asset", asset, project_id=asset.project_id, issue_ref=asset.issue_ref, reason="asset_registered")
    return asset


@router.post("/text-plans", response_model=TextPlan, status_code=status.HTTP_201_CREATED)
def create_text_plan(plan: TextPlan):
    plan.content_hash = content_hash(plan.model_dump_json())
    db.save_editorial_object("text_plan", plan, issue_ref=plan.issue_ref, reason="text_plan_created")
    return plan


@router.get("/text-plans/{plan_id}", response_model=TextPlan)
def get_text_plan(plan_id: str):
    return _get("text_plan", plan_id, TextPlan)


@router.post("/text-plans/{plan_id}/fit", response_model=TextFitResult, status_code=status.HTTP_201_CREATED)
def fit_text_plan_endpoint(plan_id: str, request: FitRequest):
    plan = _get("text_plan", plan_id, TextPlan)
    result = fit_text_plan(plan, request.text, variant_ref=request.variant_ref)
    db.save_editorial_object("text_fit", result, issue_ref=plan.issue_ref, reason="copyfit_measured")
    return result


@router.get("/issues/{issue_id}/manifest")
def issue_manifest(issue_id: str) -> Dict[str, Any]:
    issue = _get("issue", issue_id, Issue)
    project_profiles = db.list_editorial_objects("production_profile", project_id=issue.project_id)
    return {
        "issue": issue.model_dump(mode="json"),
        "plan": (db.list_editorial_objects("issue_plan", issue_ref=issue_id) or [None])[0],
        "sources": db.list_editorial_objects("source", issue_ref=issue_id),
        "briefs": db.list_editorial_objects("brief", issue_ref=issue_id),
        "stories": db.list_editorial_objects("story", issue_ref=issue_id),
        "assets": db.list_editorial_objects("asset", issue_ref=issue_id),
        "copy_variants": db.list_editorial_objects("copy_variant", issue_ref=issue_id),
        "text_plans": db.list_editorial_objects("text_plan", issue_ref=issue_id),
        "text_fits": db.list_editorial_objects("text_fit", issue_ref=issue_id),
        "preflight_reports": db.list_editorial_objects("preflight_report", issue_ref=issue_id),
        "production_profiles": project_profiles,
        "exports": [artifact.model_dump(mode="json") for artifact in db.list_export_artifacts(issue.project_id)],
        "generated_at": issue.updated_at,
    }


@router.get("/editorial/{object_type}/{object_id}/history")
def editorial_history(object_type: str, object_id: str):
    if not db.get_editorial_object(object_type, object_id):
        _not_found(object_type, object_id)
    return {"object_id": object_id, "object_type": object_type, "revisions": db.list_editorial_revisions(object_id)}


# -------------------------------------------------------------------------
# Smart Content Ingest & AI Editorial Redaction Endpoints
# -------------------------------------------------------------------------
class IngestUrlRequest(BaseModel):
    url: str
    auto_cutout: bool = True
    project_id: Optional[str] = None


class RedactTextRequest(BaseModel):
    text: str
    title: Optional[str] = None
    project_id: Optional[str] = None


@router.post("/editorial/ingest-url")
def ingest_url_endpoint(request: IngestUrlRequest):
    """Fetch article content from an internet link, extract its photo, process AI cutout and redact copy."""
    from ..engine.content_ingest import download_and_extract_url, process_editorial_photo, redact_editorial_article

    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="Adres URL jest wymagany.")

    try:
        extracted = download_and_extract_url(request.url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Nie udało się pobrać strony: {str(exc)}")

    raw_title = extracted.get("raw_title") or "AKTUALNOŚCI"
    raw_body = extracted.get("raw_body") or extracted.get("raw_description") or ""
    if not raw_body:
        raise HTTPException(status_code=422, detail="Na podanej stronie nie znaleziono treści artykułu.")

    # 1. Redact article copy with AI
    redacted = redact_editorial_article(
        raw_title=raw_title,
        raw_text=raw_body,
        domain=extracted.get("domain", ""),
        project_id=request.project_id,
    )

    # 2. Process photo if found
    photos = []
    image_url = extracted.get("image_url")
    if image_url:
        photo_meta = process_editorial_photo(
            image_source=image_url,
            auto_cutout=request.auto_cutout,
            caption=redacted.get("headline", ""),
            credit=f"Foto: {extracted.get('domain', 'Internet')}",
        )
        if photo_meta:
            photos.append(photo_meta)

    lead_story = {
        "id": "story-lead-01",
        "role": "lead-story",
        "importance": 5,
        "kicker": redacted.get("kicker", "RAPORT"),
        "headline": redacted.get("headline", raw_title.upper()),
        "deck": redacted.get("deck", ""),
        "lead": redacted.get("lead", ""),
        "body": redacted.get("body", raw_body[:800]),
        "byline": redacted.get("byline", f"opr. / {extracted.get('domain', '')}"),
        "pullQuote": redacted.get("pull_quote", ""),
        "wordCount": len((redacted.get("body") or "").split()),
    }

    return {
        "status": "ok",
        "leadStory": lead_story,
        "photos": photos,
        "source": {
            "url": extracted.get("source_url"),
            "domain": extracted.get("domain"),
            "raw_title": raw_title,
        },
        "provenance": redacted.get("provenance", {}),
    }


@router.post("/editorial/ingest-file")
async def ingest_file_endpoint(
    file: UploadFile = File(...),
    auto_cutout: bool = Form(True),
    project_id: Optional[str] = Form(None),
):
    """Extract content from an uploaded document (DOCX, PDF, TXT), process embedded photos and redact."""
    from ..engine.content_ingest import extract_document_file, process_editorial_photo, redact_editorial_article

    ext = Path(file.filename or "doc.txt").suffix.lower()
    if ext not in {".docx", ".doc", ".pdf", ".txt", ".rtf", ".md", ".odt"}:
        raise HTTPException(status_code=415, detail="Obsługiwane formaty dokumentów: DOCX, PDF, TXT, RTF, MD.")

    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = settings.UPLOADS_DIR / f"temp_doc_{uuid4()}{ext}"
    try:
        content = await file.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Plik przekracza dopuszczalny limit rozmiaru (20 MB).")
        temp_path.write_bytes(content)

        extracted = extract_document_file(temp_path, file.filename or "dokument")
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

    raw_title = extracted.get("raw_title") or Path(file.filename or "Dokument").stem
    raw_body = extracted.get("raw_body") or ""
    if not raw_body.strip():
        raise HTTPException(status_code=422, detail="Plik nie zawiera tekstu lub nie udało się go odczytać.")

    # 1. Redact article copy
    redacted = redact_editorial_article(
        raw_title=raw_title,
        raw_text=raw_body,
        domain="",
        project_id=project_id,
    )

    # 2. Process embedded image if found in docx/pdf
    photos = []
    if extracted.get("extracted_image_bytes"):
        photo_meta = process_editorial_photo(
            image_source=extracted["extracted_image_bytes"],
            auto_cutout=auto_cutout,
            caption=redacted.get("headline", ""),
            credit=f"Dokument: {file.filename}",
        )
        if photo_meta:
            photos.append(photo_meta)

    lead_story = {
        "id": "story-lead-01",
        "role": "lead-story",
        "importance": 5,
        "kicker": redacted.get("kicker", "DOKUMENT"),
        "headline": redacted.get("headline", raw_title.upper()),
        "deck": redacted.get("deck", ""),
        "lead": redacted.get("lead", ""),
        "body": redacted.get("body", raw_body[:800]),
        "byline": redacted.get("byline", "Opracowanie redakcyjne"),
        "pullQuote": redacted.get("pull_quote", ""),
        "wordCount": len((redacted.get("body") or "").split()),
    }

    return {
        "status": "ok",
        "leadStory": lead_story,
        "photos": photos,
        "source": {
            "filename": file.filename,
        },
        "provenance": redacted.get("provenance", {}),
    }


@router.post("/editorial/redact-text")
def redact_text_endpoint(request: RedactTextRequest):
    """Redact raw draft/notes into formatted Polish editorial newspaper copy."""
    from ..engine.content_ingest import redact_editorial_article

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Tekst do zredagowania jest wymagany.")

    redacted = redact_editorial_article(
        raw_title=request.title or "AKTUALNOŚCI",
        raw_text=request.text,
        domain="",
        project_id=request.project_id,
    )

    lead_story = {
        "id": "story-lead-01",
        "role": "lead-story",
        "importance": 5,
        "kicker": redacted.get("kicker", "WYDANIE GŁÓWNE"),
        "headline": redacted.get("headline", (request.title or "TYTUŁ").upper()),
        "deck": redacted.get("deck", ""),
        "lead": redacted.get("lead", ""),
        "body": redacted.get("body", request.text[:800]),
        "byline": redacted.get("byline", "Redakcja"),
        "pullQuote": redacted.get("pull_quote", ""),
        "wordCount": len((redacted.get("body") or "").split()),
    }

    return {
        "status": "ok",
        "leadStory": lead_story,
        "provenance": redacted.get("provenance", {}),
    }

