from __future__ import annotations
import shutil, uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..config import settings
from ..engine.logo import analyze_logo
from ..models.database import db
from ..models.schemas import TitleDNA
router=APIRouter(prefix="/projects",tags=["logo"])
@router.post("/{project_id}/dna/logo")
async def upload_logo(project_id: str, file: UploadFile = File(...), variant: str = "primary"):
    if not db.get_project(project_id): raise HTTPException(status_code=404,detail="Project not found")
    ext=Path(file.filename or "logo.bin").suffix.lower()
    if ext not in {".svg",".pdf",".eps",".ai",".png",".webp",".jpg",".jpeg"}: raise HTTPException(status_code=415,detail="Unsupported logo format")
    path=settings.UPLOADS_DIR/f"logo_{uuid.uuid4().hex}{ext}"; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as out: shutil.copyfileobj(file.file,out)
    profile=analyze_logo(path,asset_ref=str(path),variant=variant)
    dna=db.get_title_dna(project_id) or TitleDNA(); dna.logo_profile=profile; db.save_title_dna(project_id,dna)
    return {"status":"draft","asset_ref":str(path),"logo_profile":profile.model_dump(mode="json")}
