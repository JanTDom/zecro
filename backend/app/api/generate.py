import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from ..models.schemas import ArtDirectionPlan, GenerationRequest, GenerationRun, Candidate, SceneGraph
from ..models.database import db
from ..engine.evolution import EvolutionaryLayoutGenerator
from ..engine.renderers.svg_renderer import SVGRenderer
from ..engine.polish_typography import sanitize_editorial_material
from ..engine.critic import LayoutCritic
from ..engine.corpus_indexer import build_generation_guidance
from ..engine.corpus_knowledge import load_corpus_knowledge
from ..engine.ai_director import AIDirector
from ..engine.art_direction import build_art_direction_plan
from ..engine.page_planner import plan_page
from ..engine.editorial_model import EditorialModel, apply_ads_to_scene

router = APIRouter(tags=["generate"])


@router.get("/projects/{project_id}/ai-director")
def get_ai_director_contract(project_id: str):
    """Expose the active AI operating contract and its evidence boundaries."""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=404, detail="Title DNA not found")
    knowledge = load_corpus_knowledge(db, project_id)
    return AIDirector(dna=dna, knowledge=knowledge, preference_model=db.get_taste_model(project_id)).contract()

@router.post("/projects/{project_id}/generate", response_model=GenerationRun, status_code=status.HTTP_201_CREATED)
def execute_generation_run(project_id: str, request: GenerationRequest):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=404, detail="Title DNA not found")

    if request.energy_budget_override is not None:
        dna.page_energy_budget = request.energy_budget_override

    # Production is remote-only: the Supabase corpus is the source of truth.
    # The knowledge layer enriches legacy rows with measured, coarse spatial
    # evidence and preserves explicit unknowns.  A local FEATURE_INDEX is only
    # a development fallback, never a hidden production dependency.
    corpus_knowledge = load_corpus_knowledge(db, project_id)
    corpus_features = list(corpus_knowledge.get("pages") or [])

    taste_model = db.get_taste_model(project_id)
    pref_weights = taste_model.feature_weights if taste_model else None

    # Automatic Polish editorial microtypography cleanup
    cleaned_material = sanitize_editorial_material(request.material)
    if request.style_blend is not None:
        cleaned_material.style_blend = request.style_blend
    if request.page_zone is not None:
        cleaned_material.page_zone = request.page_zone

    # Editorial hierarchy is planned before geometry.  The evolutionary
    # generator receives this immutable plan as a constraint and only explores
    # frames/treatments inside the allocated slots.
    page_plan = request.page_plan or cleaned_material.page_plan
    if page_plan is None:
        page_plan = plan_page(dna, cleaned_material.stories, page_zone=cleaned_material.page_zone)
    cleaned_material.page_plan = page_plan

    corpus_guidance = build_generation_guidance(
        corpus_features,
        archetype=dna.archetype,
        zone=cleaned_material.page_zone,
    )
    corpus_guidance["knowledge_source"] = corpus_knowledge.get("source", "unavailable")
    corpus_guidance["knowledge_evidence"] = corpus_knowledge.get("evidence", {})

    # Run Evolutionary Layout Engine
    generator = EvolutionaryLayoutGenerator(
        dna=dna,
        corpus_features=corpus_features,
        preference_weights=pref_weights,
        corpus_guidance=corpus_guidance,
    )

    pairs = generator.generate(
        material=cleaned_material,
        num_candidates=request.num_candidates,
        population_size=request.population_size,
        generations=request.generations,
        seed=request.seed,
        allow_transgressions=request.allow_transgressions,
    )

    visual_status = {"status": "skipped"}
    if getattr(request, "visual_review", True):
        from ..ai.visual_critic import rerank
        pairs, visual_status = rerank(pairs, dna, limit=min(4, len(pairs)), project_id=project_id)

    svg_renderer = SVGRenderer(dna)
    ai_director = AIDirector(dna=dna, knowledge=corpus_knowledge, preference_model=taste_model)
    run_id = str(uuid.uuid4())
    candidates = []

    for rank, (sg, critic_res) in enumerate(pairs):
        # PageMeta carries the owning project reference for render/export
        # lookup.  TitleDNA remains a versioned object, while this ref is an
        # explicit project foreign key.
        sg.page.title_dna_ref = project_id
        if request.editorial_edition:
            editorial_model = EditorialModel.model_validate(request.editorial_edition)
            page_no = int(sg.page.page_number or 1)
            editorial_page = next((page for page in editorial_model.edition.page_plan if page.no == page_no), None)
            if editorial_page:
                apply_ads_to_scene(sg, editorial_page, dna)
                # Ads are locked inputs to the critic. Re-evaluate after the
                # adapter materializes them so candidates cannot be exported
                # without the same advertising constraints.
                critic_res = LayoutCritic(dna, corpus_features=corpus_features,
                                          corpus_guidance=corpus_guidance).evaluate(sg)
        # Bind editorial intent and exact writing budgets to the concrete
        # candidate.  This is the bridge between art direction and fast page
        # copy: every frame becomes an actionable writing brief.
        art_direction = build_art_direction_plan(dna, cleaned_material, sg, corpus_guidance)
        sg.metadata["art_direction"] = art_direction.model_dump(mode="json")
        sg.metadata["ai_director"] = ai_director.candidate_trace(sg, critic_res)
        sg.metadata["corpus_guidance"] = corpus_guidance
        sg.metadata["page_plan"] = page_plan.model_dump(mode="json")
        if request.editorial_edition:
            sg.metadata["editorial_edition"] = request.editorial_edition
        cand_id = str(uuid.uuid4())
        svg_thumb = svg_renderer.render(sg)

        cand = Candidate(
            id=cand_id,
            run_id=run_id,
            scene_graph=sg,
            critic=critic_res,
            svg_thumbnail=svg_thumb,
            html_preview_url=f"/candidates/{cand_id}/preview",
            rank=rank + 1,
            selected=False,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        candidates.append(cand)

    run = GenerationRun(
        id=run_id,
        project_id=project_id,
        material=cleaned_material,
        candidates=candidates,
        status="completed",
        stats={
            "candidates_count": len(candidates),
            "visual_review": visual_status,
            "energy_budget_used": dna.page_energy_budget,
            "population_size": request.population_size,
            "generations": request.generations,
            "corpus_guidance": corpus_guidance,
            "corpus_knowledge": corpus_knowledge.get("evidence", {}),
            "ai_director_contract": ai_director.contract(),
            "art_direction_plans": len(candidates),
            "copy_slots": sum(
                len(candidate.scene_graph.metadata.get("art_direction", {}).get("copy_slots", []))
                for candidate in candidates
            ),
        },
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    return db.save_generation_run(run)

@router.get("/projects/{project_id}/runs", response_model=list[GenerationRun])
def list_generation_runs(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.list_generation_runs(project_id)

@router.get("/projects/{project_id}/runs/{run_id}", response_model=GenerationRun)
def get_generation_run(project_id: str, run_id: str):
    run = db.get_generation_run(run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Generation run not found")
    return run

@router.get("/candidates/{candidate_id}", response_model=Candidate)
def get_candidate(candidate_id: str):
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return cand


@router.get("/candidates/{candidate_id}/art-direction", response_model=ArtDirectionPlan)
def get_candidate_art_direction(candidate_id: str):
    """Return the candidate's decision trace and frame-bound writing map."""
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    payload = (cand.scene_graph.metadata or {}).get("art_direction")
    if not payload:
        raise HTTPException(
            status_code=409,
            detail="Candidate predates frame-bound art-direction planning; regenerate the page",
        )
    return ArtDirectionPlan.model_validate(payload)


@router.put("/candidates/{candidate_id}", response_model=Candidate)
def update_candidate_scene(candidate_id: str, scene_graph: SceneGraph):
    """Persist a human geometry edit and re-run the critic before export."""
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    project_id = db.get_candidate_project_id(candidate_id) or scene_graph.page.title_dna_ref or ""
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=409, detail="Title DNA for candidate project is unavailable")
    scene_graph.page.title_dna_ref = project_id
    corpus_knowledge = load_corpus_knowledge(db, project_id)
    corpus_features = list(corpus_knowledge.get("pages") or [])
    corpus_guidance = build_generation_guidance(
        corpus_features,
        archetype=dna.archetype,
        zone=scene_graph.page.page_zone,
    )
    corpus_guidance["knowledge_source"] = corpus_knowledge.get("source", "unavailable")
    corpus_guidance["knowledge_evidence"] = corpus_knowledge.get("evidence", {})
    critic = LayoutCritic(
        dna,
        corpus_features=corpus_features,
        corpus_guidance=corpus_guidance,
    )
    result = critic.evaluate(scene_graph)
    # Geometry edits change the amount and order of copy on the page. Rebuild
    # the frame-bound editorial plan from the original run material so the
    # Content Studio never shows stale targets after a drag or resize.
    run = db.get_generation_run(candidate.run_id)
    if run:
        updated_plan = build_art_direction_plan(dna, run.material, scene_graph, corpus_guidance)
        scene_graph.metadata["art_direction"] = updated_plan.model_dump(mode="json")
    svg = SVGRenderer(dna).render(scene_graph)
    scene_graph.metadata["ai_director"] = AIDirector(
        dna=dna,
        knowledge=corpus_knowledge,
        preference_model=db.get_taste_model(project_id),
    ).candidate_trace(scene_graph, result)
    updated = db.update_candidate_scene(candidate_id, scene_graph.model_dump_json(), result.model_dump_json(), svg)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return updated
