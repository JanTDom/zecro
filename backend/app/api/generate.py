import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from ..models.schemas import GenerationRequest, GenerationRun, Candidate, SceneGraph
from ..models.database import db
from ..engine.evolution import EvolutionaryLayoutGenerator
from ..engine.renderers.svg_renderer import SVGRenderer
from ..engine.polish_typography import sanitize_editorial_material
from ..engine.critic import LayoutCritic
from ..engine.corpus_indexer import load_feature_index

router = APIRouter(tags=["generate"])

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

    corpus_pages = db.list_corpus_pages(project_id)
    project_features = [c.extracted_features for c in corpus_pages if c.extracted_features]
    # Novelty search always has the global measured corpus as a reference. A
    # project's private uploads are added as a second source, so a local title
    # can learn from its own archive without disabling anti-copying checks.
    global_features = db.list_global_corpus_features()
    if not global_features:
        global_features = load_feature_index()
    corpus_features = global_features + project_features

    taste_model = db.get_taste_model(project_id)
    pref_weights = taste_model.feature_weights if taste_model else None

    # Automatic Polish editorial microtypography cleanup
    cleaned_material = sanitize_editorial_material(request.material)
    if request.style_blend is not None:
        cleaned_material.style_blend = request.style_blend
    if request.page_zone is not None:
        cleaned_material.page_zone = request.page_zone

    # Run Evolutionary Layout Engine
    generator = EvolutionaryLayoutGenerator(
        dna=dna,
        corpus_features=corpus_features,
        preference_weights=pref_weights
    )

    pairs = generator.generate(
        material=cleaned_material,
        num_candidates=request.num_candidates,
        population_size=request.population_size,
        generations=request.generations,
        seed=request.seed,
        allow_transgressions=request.allow_transgressions,
    )

    svg_renderer = SVGRenderer(dna)
    run_id = str(uuid.uuid4())
    candidates = []

    for rank, (sg, critic_res) in enumerate(pairs):
        # PageMeta carries the owning project reference for render/export
        # lookup.  TitleDNA remains a versioned object, while this ref is an
        # explicit project foreign key.
        sg.page.title_dna_ref = project_id
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
            "energy_budget_used": dna.page_energy_budget,
            "population_size": request.population_size,
            "generations": request.generations
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
    critic = LayoutCritic(dna)
    result = critic.evaluate(scene_graph)
    svg = SVGRenderer(dna).render(scene_graph)
    updated = db.update_candidate_scene(candidate_id, scene_graph.model_dump_json(), result.model_dump_json(), svg)
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return updated
