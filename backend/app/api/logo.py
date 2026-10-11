from __future__ import annotations
import shutil, uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from ..config import settings
from ..engine.logo import analyze_logo, ai_logo_analysis
from ..models.database import db
from ..models.schemas import TitleDNA

router = APIRouter(prefix="/projects", tags=["logo"])


@router.post("/{project_id}/dna/logo")
async def upload_logo(project_id: str, file: UploadFile = File(...), variant: str = "primary", ai: bool = True):
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    ext = Path(file.filename or "logo.bin").suffix.lower()
    if ext not in {".svg", ".pdf", ".png", ".webp", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=415, detail="Obsługiwane: SVG, PDF, PNG, WebP, JPG (EPS/AI zapisz jako PDF)")
    path = settings.UPLOADS_DIR / f"logo_{uuid.uuid4().hex}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    profile = analyze_logo(path, asset_ref=str(path), variant=variant)
    if ai:
        try:
            profile.ai_analysis = ai_logo_analysis(path, profile, project_id=project_id)
        except Exception as exc:
            profile.ai_analysis = {"status": "unavailable", "reason": str(exc)[:300]}
    dna = db.get_title_dna(project_id) or TitleDNA()
    dna.logo_profile = profile
    db.save_title_dna(project_id, dna)
    return {"status": "draft", "asset_ref": str(path), "logo_profile": profile.model_dump(mode="json")}


class LogoApproval(BaseModel):
    use_vector: bool = False
    apply_palette: bool = True
    font_pairing_index: int | None = 0


@router.post("/{project_id}/dna/logo/approve")
def approve_logo(project_id: str, req: LogoApproval):
    dna = db.get_title_dna(project_id)
    if not dna or not dna.logo_profile:
        raise HTTPException(status_code=404, detail="Brak logo w DNA")
    prof = dna.logo_profile
    if req.use_vector and prof.vector_ref:
        prof.asset_ref, prof.vector = prof.vector_ref, True
    ai = prof.ai_analysis or {}
    roles = ai.get("palette_roles") or {}
    if req.apply_palette and roles.get("kicker"):
        dna.palette.secondary = roles["kicker"]
    pairs = ai.get("font_pairings") or []
    if req.font_pairing_index is not None and 0 <= req.font_pairing_index < len(pairs):
        fp = pairs[req.font_pairing_index]
        dna.typography.fonts["headline"] = f"{fp['headline_family']}, serif"
        dna.typography.fonts["body"] = f"{fp['body_family']}, serif"
    prof.approved = True
    db.save_title_dna(project_id, dna)
    return {"status": "approved", "dna": dna.model_dump(mode="json")}
