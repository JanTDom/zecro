"""Production profiles and deterministic candidate preflight."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from typing import List

from ..engine.production import preflight_scene_graph
from ..models.database import db
from ..models.schemas import PreflightReport, ProductionProfile

router = APIRouter(tags=["production", "preflight"])


@router.post("/projects/{project_id}/production-profiles", response_model=ProductionProfile, status_code=status.HTTP_201_CREATED)
def create_production_profile(project_id: str, profile: ProductionProfile):
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    profile.project_id = project_id
    db.save_editorial_object("production_profile", profile, project_id=project_id, reason="production_profile_saved")
    return profile


@router.get("/projects/{project_id}/production-profiles", response_model=List[ProductionProfile])
def list_production_profiles(project_id: str):
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return [ProductionProfile(**row) for row in db.list_editorial_objects("production_profile", project_id=project_id)]


@router.post("/candidates/{candidate_id}/preflight", response_model=PreflightReport)
def preflight_candidate(candidate_id: str):
    candidate = db.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    project_id = db.get_candidate_project_id(candidate_id) or candidate.scene_graph.page.title_dna_ref
    dna = db.get_title_dna(project_id or "")
    if not dna:
        raise HTTPException(status_code=409, detail="Title DNA for candidate is unavailable")
    report = preflight_scene_graph(candidate.scene_graph, dna, candidate_ref=candidate_id)
    db.save_editorial_object(
        "preflight_report",
        report,
        project_id=project_id,
        issue_ref=candidate.scene_graph.page.issue_ref,
        reason="candidate_preflight",
    )
    return report


@router.get("/candidates/{candidate_id}/preflight", response_model=PreflightReport)
def get_candidate_preflight(candidate_id: str):
    rows = db.list_editorial_objects("preflight_report")
    for row in rows:
        if row.get("candidate_ref") == candidate_id:
            return PreflightReport(**row)
    return preflight_candidate(candidate_id)
