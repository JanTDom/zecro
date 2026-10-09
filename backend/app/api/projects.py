from fastapi import APIRouter, HTTPException, status
from typing import List
from ..models.schemas import Project, TitleDNA
from ..models.database import db
from ..engine.grammar import create_default_broadsheet_dna, create_default_tabloid_dna

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("", response_model=List[Project])
def list_projects():
    return db.list_projects()

@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(project: Project):
    created = db.create_project(project)
    # Automatically initialize default TitleDNA for the project
    if "tabloid" in project.name.lower() or "expressive" in (project.description or "").lower():
        dna = create_default_tabloid_dna()
    else:
        dna = create_default_broadsheet_dna()
    dna.name = f"{project.name} DNA"
    db.save_title_dna(project.id, dna)
    return created

@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str):
    success = db.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return None
