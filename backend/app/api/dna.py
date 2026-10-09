from fastapi import APIRouter, HTTPException
from ..models.schemas import TitleDNA
from ..models.database import db

router = APIRouter(prefix="/projects", tags=["dna"])

@router.get("/{project_id}/dna", response_model=TitleDNA)
def get_project_dna(project_id: str):
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=404, detail="Title DNA not found for this project")
    return dna

@router.put("/{project_id}/dna", response_model=TitleDNA)
def update_project_dna(project_id: str, dna: TitleDNA):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    saved = db.save_title_dna(project_id, dna)
    return saved
