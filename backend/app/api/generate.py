import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from ..models.schemas import ArtDirectionPlan, GenerationRequest, GenerationRun, Candidate, PageInputMaterial, SceneGraph, Story
from ..models.database import db
from ..engine.evolution import EvolutionaryLayoutGenerator
from ..engine.renderers.svg_renderer import SVGRenderer
from ..engine.polish_typography import sanitize_editorial_material
from ..engine.critic import LayoutCritic
from ..engine.corpus_indexer import build_generation_guidance
from ..engine.corpus_knowledge import load_corpus_knowledge
from ..engine.ai_director import AIDirector
from ..ai.integration_registry import registry
from ..engine.art_direction import build_art_direction_plan
from ..engine.page_planner import plan_page
from ..engine.editorial_model import EditorialModel, apply_ads_to_scene
from ..engine.editorial_style import editorial_style_label
from ..engine.page_topic import apply_page_topic, PAGE_TOPIC_LABELS
from ..engine.page_mood import apply_page_mood, resolve_page_mood
from ..integrations.yourquantum import select_transgressions

router = APIRouter(tags=["generate"])


def _fulfil_copy_requests(pairs, material, project_id, critic, limit: int = 3) -> dict:
    """The layout fixed the frames; the copy editor writes source-bound copy of
    the requested length for frames the source could not fill."""
    from ..engine.frame_fill import FILL_MIN, measure
    pending_total = sum(len((sg.metadata or {}).get("copy_requests") or []) for sg, _ in pairs[:limit])
    if not pending_total:
        return {"status": "nothing_pending"}
    if registry.resolve("copy_fit", project_id).status != "ready":
        for sg, _ in pairs[:limit]:
            if (sg.metadata or {}).get("copy_requests"):
                sg.metadata["copy_status"] = "pending_ai_unavailable"
        return {"status": "unavailable", "pending": pending_total}
    from ..ai.editorial_writer import fit_to_frame
    sources = {story.id: story for story in material.stories}
    done = failed = 0
    for index, (sg, crit) in enumerate(pairs[:limit]):
        remaining = []
        for request in (sg.metadata or {}).get("copy_requests") or []:
            element = next((e for e in sg.elements if e.id == request.get("element_id")), None)
            source = sources.get(request.get("story_ref") or "")
            if element is None or source is None:
                failed += 1
                continue
            story = Story(id=source.id, issue_ref="generation", slug=source.id, headline=source.headline,
                          lead=source.lead or "", body=source.body, deck=source.deck or "", byline=source.byline or "",
                          locked_passages=list(source.locked_passages or []))
            try:
                draft = fit_to_frame(story, request.get("field") or "body",
                                     {"width_mm": element.frame.w, "height_mm": element.frame.h,
                                      "columns": element.style.columns or 1, "font_size_pt": element.style.font_size_pt or 9.5},
                                     target_words=int(request["target_words"]), project_id=project_id,
                                     timeout_s=30, max_retries=1)
            except Exception:
                remaining.append(request)
                failed += 1
                continue
            report = measure(element, draft.text, gutter_mm=critic.dna.grid.gutter_mm)
            ratio = report.estimated_lines / max(1, report.capacity_lines)
            if draft.approvable and FILL_MIN - .03 <= ratio <= 1.0:
                element.text_content = draft.text
                done += 1
            else:
                remaining.append(request)
                failed += 1
        sg.metadata["copy_requests"] = remaining
        sg.metadata["copy_status"] = "complete" if not remaining else "pending"
        pairs[index] = (sg, critic.evaluate(sg))
    return {"status": "ready", "written": done, "pending": failed}


def _diversity_first(pairs):
    seen, first, rest = set(), [], []
    for pair in pairs:
        meta = pair[0].metadata or {}
        coarse = meta.get("architecture")
        if coarse not in seen:
            seen.add(coarse)
            first.append(pair)
        else:
            rest.append(pair)
    return first + rest


def _visual_feedback(pairs) -> dict:
    """Convert measured visual failures into bounded exploration hints.

    The VLM remains a critic. It never writes geometry or invents content.
    Its structured observations only bias a second, independently gated
    generation pass.
    """
    critiques = [(sg, (sg.metadata or {}).get("visual_critique") or {}) for sg, _ in pairs]
    reviewed = [(sg, c) for sg, c in critiques if isinstance(c.get("style_fidelity"), (int, float))]
    if not reviewed:
        return {}
    return {
        "rejected_modes": list(dict.fromkeys(str((sg.metadata or {}).get("layout_mode", ""))
                                                for sg, c in reviewed
                                                if c.get("category_review", {}).get("status") == "needs_revision")),
        "dead_zones": any(bool(c.get("dead_zones")) for _, c in reviewed),
        "observed_fidelity": max(float(c.get("style_fidelity", 0)) for _, c in reviewed),
        "photo_selection_needed": all(float(c.get("photo_headline_match", 1)) < .45 for _, c in reviewed),
    }


def _refine_copy_with_ai(pairs, material, project_id, critic):
    """Fit the lead headline and shortened body to the chosen layout.

    Genre and page topic shape the wording, but every proposal must pass the
    source guard, measured typesetting and the deterministic page hard gate.
    """
    if not pairs:
        return pairs, {"status": "no_candidates"}
    sg, old_crit = pairs[0]
    shortened = {row.get("element_ref", "").removeprefix("body-") for row in (sg.metadata or {}).get("fit_adjustments", [])
                 if row.get("action") == "copyfit_shorten"}
    if registry.resolve("copy_fit", project_id).status != "ready":
        return pairs, {"status": "unavailable"}
    from ..ai.editorial_writer import fit_to_frame
    from ..engine.copyfit import estimate_text_capacity
    sources = {story.id: story for story in material.stories}
    accepted = []
    attempted = 0
    headline_done = False
    body_done = False
    title_style = f"{editorial_style_label(material.style_blend)}; dział: {PAGE_TOPIC_LABELS.get(material.page_topic, 'temat ogólny')}"
    for element in sg.elements:
        if not element.style or not element.story_ref or not element.text_content:
            continue
        is_headline = element.role == "headline" and "must_dominate" in (getattr(element, "constraints", []) or []) and not headline_done
        is_body = element.role == "body" and element.story_ref in shortened and not body_done
        if not (is_headline or is_body):
            continue
        source = sources.get(element.story_ref)
        if not source or (is_body and not source.body):
            continue
        role = "headline" if is_headline else "body"
        headline_done |= is_headline
        body_done |= is_body
        attempted += 1
        story = Story(id=source.id, issue_ref="generation", slug=source.id, headline=source.headline,
                      lead=source.lead or "", body=source.body, deck=source.deck or "", byline=source.byline or "",
                      locked_passages=list(source.locked_passages or []))
        frame = {"width_mm": element.frame.w, "height_mm": element.frame.h,
                 "columns": element.style.columns or 1, "font_size_pt": element.style.font_size_pt or 9.5}
        try:
            draft = fit_to_frame(story, role, frame, target_words=len(element.text_content.split()),
                                 target_lines=max(1, int(element.frame.h / max(1.0, (element.style.line_height_pt or 11) * .352778))),
                                 project_id=project_id,
                                 title_style=title_style,
                                 timeout_s=30, max_retries=1)
            if not draft.approvable or draft.provenance.get("provider") in (None, "deterministic-local"):
                continue
            if (draft.guard.get("provenance", {}).get("ai_pass") or {}).get("status") == "unavailable":
                continue
            if draft.text.strip() == element.text_content.strip():
                continue
            report = estimate_text_capacity(draft.text, element.frame.w, element.frame.h,
                                            element.style.columns or 1, element.style.font_size_pt or 9.5,
                                            element.style.line_height_pt, font_family=element.style.font_family,
                                            gutter_mm=critic.dna.grid.gutter_mm)
            if not report.passes:
                continue
            previous = element.text_content
            element.text_content = draft.text
            new_crit = critic.evaluate(sg)
            if not new_crit.hard_gate.passed:
                element.text_content = previous
                continue
            old_crit = new_crit
            accepted.append({"element_id": element.id, "role": role, "provider": draft.provenance.get("provider"),
                             "model": draft.provenance.get("model"), "source_words": len((source.headline if is_headline else source.body).split()),
                             "result_words": len(draft.text.split())})
            sg.metadata.setdefault("fit_adjustments", []).append({"action": "ai_copy_refinement", "element_ref": element.id,
                "story_ref": source.id, "field": role, "from_words": len(previous.split()), "to_words": len(draft.text.split()),
                "reason": "Dopasowanie treści do ramy i charakteru gazety z kontrolą źródeł", "provider": draft.provenance.get("provider")})
        except Exception as exc:
            sg.metadata.setdefault("copy_ai_errors", []).append(exc.__class__.__name__)
    sg.metadata["copy_ai"] = {"status": "applied" if accepted else "fallback", "attempted": attempted,
                              "accepted": accepted}
    pairs[0] = (sg, old_crit)
    return pairs, sg.metadata["copy_ai"]


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
    return AIDirector(
        dna=dna, knowledge=knowledge, preference_model=db.get_taste_model(project_id),
        task_statuses={task: registry.resolve(task, project_id).status for task in ("visual_critic", "copy_fit")},
    ).contract()

class PhotoCheckRequest(BaseModel):
    material: PageInputMaterial


@router.post("/projects/{project_id}/photo-check")
def check_material_photos(project_id: str, request: PhotoCheckRequest):
    """Guided step 3: photo editing verdicts *before* any geometry exists."""
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=404, detail="Title DNA not found")
    from ..ai.photo_editor import lead_photo_stop, select_story_photos
    material = sanitize_editorial_material(request.material)
    if not any(story.images for story in material.stories):
        return {"ready": True, "photo_selection": [], "stop": None,
                "message": "Brak zdjęć. Strona powstanie bez fotografii albo z ilustracjami, które dodasz później."}
    rules = dna.photo_rules
    printable_w = dna.format.trim_w_mm - dna.format.margin_left_mm - dna.format.margin_right_mm
    _, trace = select_story_photos(material, project_id=project_id,
                                   min_lead_score=float(rules.min_lead_photo_score),
                                   min_lead_match=float(rules.min_lead_photo_match),
                                   target_width_mm=printable_w * .72, min_dpi=int(rules.min_dpi))
    stop = lead_photo_stop(trace)
    unavailable = [row for row in trace if row.get("status") == "unavailable"]
    return {"ready": stop is None, "photo_selection": trace, "stop": stop,
            "message": (stop or {}).get("message") or (
                "Fotoedytor AI jest chwilowo niedostępny; zdjęcia nie zostały ocenione." if unavailable and len(unavailable) == len(trace)
                else "Zdjęcia sprawdzone.")}


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
    base_style_blend = cleaned_material.style_blend.model_dump()
    cleaned_material.style_blend = apply_page_topic(cleaned_material.style_blend, cleaned_material.page_topic)
    mood_profile = resolve_page_mood(cleaned_material)
    cleaned_material.editorial_mood = mood_profile.name
    cleaned_material.style_blend = apply_page_mood(cleaned_material.style_blend, mood_profile)

    # The first image consumed by the geometry engine must be an editorial
    # choice, not upload order.  Visual-review runs use Gemini as a photo
    # editor when a story supplies alternatives; unavailable remote-only
    # sources fall back transparently to the user's original order.
    photo_selection: list[dict] = []
    if request.visual_review and any(story.images for story in cleaned_material.stories):
        from ..ai.photo_editor import lead_photo_stop, select_story_photos
        rules = dna.photo_rules
        printable_w = dna.format.trim_w_mm - dna.format.margin_left_mm - dna.format.margin_right_mm
        cleaned_material, photo_selection = select_story_photos(
            cleaned_material, project_id=project_id,
            min_lead_score=float(getattr(rules, "min_lead_photo_score", .52)),
            min_lead_match=float(getattr(rules, "min_lead_photo_match", .45)),
            target_width_mm=printable_w * .72, min_dpi=int(rules.min_dpi))
        stop = lead_photo_stop(photo_selection)
        if stop and not request.accept_weak_photos:
            # Photo editing precedes geometry: a weak lead photograph is a
            # content problem, and no layout can repair it.
            raise HTTPException(status_code=422, detail={
                "code": "photo_needed",
                "message": stop.get("message") or "Potrzebne inne zdjęcie do głównego materiału.",
                "story_ref": stop.get("story_ref"),
                "photo_selection": photo_selection,
            })

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

    # Optional discrete optimization: YourQuantum chooses a feasible set of
    # supported transgressions under the Title DNA energy budget.  Geometry,
    # novelty, copyfit, and all hard production checks stay local.
    yourquantum = select_transgressions(
        dna,
        cleaned_material,
        enabled=bool(request.allow_transgressions),
    )
    corpus_guidance["yourquantum"] = yourquantum.as_metadata()

    # Run Evolutionary Layout Engine
    generator = EvolutionaryLayoutGenerator(
        dna=dna,
        corpus_features=corpus_features,
        preference_weights=pref_weights,
        corpus_guidance=corpus_guidance,
        novelty_priority=1.0 if request.prioritize_novelty else 0.35,
        preferred_transgressions=yourquantum.selected_ids,
    )

    pairs = generator.generate(
        material=cleaned_material,
        num_candidates=request.num_candidates,
        population_size=request.population_size,
        generations=request.generations,
        seed=request.seed,
        allow_transgressions=request.allow_transgressions,
    )
    for scene, _ in pairs:
        scene.metadata["page_topic"] = cleaned_material.page_topic
        scene.metadata["editorial_mood"] = mood_profile.name
        scene.metadata["editorial_mood_evidence"] = mood_profile.evidence
        scene.metadata["base_style_blend"] = base_style_blend
        scene.metadata["photo_selection"] = photo_selection

    copy_status = {"status": "skipped"}
    if request.copy_review:
        pairs, copy_status = _refine_copy_with_ai(pairs, cleaned_material, project_id, generator.critic)
    # Frames are fixed by the layout: copy the source could not fill is
    # written to length by the copy editor (never left as a hole).
    copy_status["frame_fill"] = _fulfil_copy_requests(pairs, cleaned_material, project_id, generator.critic,
                                                      limit=min(3, len(pairs)))

    visual_status = {"status": "skipped"}
    if request.visual_review:
        from ..ai.visual_critic import rerank
        # The VLM sees a few renders only.  Spend them across *different*
        # page architectures/morphologies (best of each first) instead of
        # three neighbours of the heuristic optimum, so the independent critic
        # can actually compare topologies.
        pairs = _diversity_first(pairs)
        pairs, visual_status = rerank(pairs, dna, limit=min(3, len(pairs)), project_id=project_id)
        feedback = _visual_feedback(pairs)
        if (feedback and visual_status.get("candidates_for_editor", 0) == 0
                and not feedback["photo_selection_needed"]):
            retry_guidance = {**corpus_guidance, "visual_feedback": feedback}
            retry_generator = EvolutionaryLayoutGenerator(
                dna=dna, corpus_features=corpus_features, preference_weights=pref_weights,
                corpus_guidance=retry_guidance, novelty_priority=1.0 if request.prioritize_novelty else .35,
                preferred_transgressions=yourquantum.selected_ids,
            )
            retry_pairs = retry_generator.generate(
                material=cleaned_material, num_candidates=min(3, request.num_candidates),
                population_size=min(14, request.population_size), generations=min(2, request.generations),
                seed=(request.seed + 1009 if request.seed is not None else None),
                allow_transgressions=request.allow_transgressions,
            )
            for scene, _ in retry_pairs:
                scene.metadata.update({"page_topic": cleaned_material.page_topic,
                                       "editorial_mood": mood_profile.name,
                                       "editorial_mood_evidence": mood_profile.evidence,
                                       "base_style_blend": base_style_blend,
                                       "visual_revision": {"pass": 2, "feedback": feedback}})
            retry_pairs, retry_status = rerank(retry_pairs, dna, limit=min(2, len(retry_pairs)), project_id=project_id)
            pairs = sorted([*pairs, *retry_pairs], key=lambda item: float(
                (item[0].metadata or {}).get("blended_score", item[1].total_fitness)), reverse=True)[:request.num_candidates]
            visual_status = {**visual_status, "revision_passes": 2,
                             "reviewed": visual_status.get("reviewed", 0) + retry_status.get("reviewed", 0),
                             "candidates_for_editor": visual_status.get("candidates_for_editor", 0)
                                                      + retry_status.get("candidates_for_editor", 0),
                             "feedback": feedback}
        elif feedback:
            visual_status["revision_passes"] = 1
            visual_status["feedback"] = feedback

    svg_renderer = SVGRenderer(dna)
    ai_director = AIDirector(
        dna=dna, knowledge=corpus_knowledge, preference_model=taste_model,
        task_statuses={task: registry.resolve(task, project_id).status for task in ("visual_critic", "copy_fit")},
    )
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
        sg.metadata["yourquantum"] = yourquantum.as_metadata()
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
            "photo_selection": photo_selection,
            "copy_review": copy_status,
            "energy_budget_used": dna.page_energy_budget,
            "population_size": request.population_size,
            "generations": request.generations,
            "evolution": generator.last_run_stats,
            "corpus_guidance": corpus_guidance,
            "corpus_knowledge": corpus_knowledge.get("evidence", {}),
            "yourquantum": yourquantum.as_metadata(),
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
