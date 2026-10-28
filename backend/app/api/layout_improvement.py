"""API router for layout dissection, diagnosis audit, and directed improvement.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ..engine.layout_auditor import LayoutAuditor
from ..engine.layout_dissector import LayoutDissector
from ..engine.layout_improver import LayoutImprover
from ..engine.renderers.idml_renderer import IDMLRenderer
from ..models.schemas import SceneGraph, TitleDNA

router = APIRouter(prefix="/layout", tags=["layout-improvement"])


class AuditRequest(BaseModel):
    scene_graph: SceneGraph
    title_dna: Optional[TitleDNA] = None


class ImproveRequest(BaseModel):
    scene_graph: SceneGraph
    title_dna: Optional[TitleDNA] = None


class ExportIDMLRequest(BaseModel):
    scene_graph: SceneGraph
    title_dna: Optional[TitleDNA] = None


@router.post("/dissect")
async def dissect_layout_file(file: UploadFile = File(...)):
    """Decompiles an uploaded IDML or PDF newspaper file into SceneGraph and TitleDNA."""
    filename = file.filename or "upload.idml"
    suffix = Path(filename).suffix.lower()

    if suffix not in (".idml", ".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Nieobsługiwany format '{suffix}'. Obsługiwane formaty: .idml, .pdf"
        )

    content = await file.read()
    dissector = LayoutDissector()

    try:
        if suffix == ".idml":
            scene, dna, meta = dissector.dissect_idml(content, title_name=Path(filename).stem)
        else:
            scene, dna, meta = dissector.dissect_pdf(content, title_name=Path(filename).stem)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Błąd dekompilacji pliku {filename}: {str(exc)}")

    # Run audit on dissected layout
    auditor = LayoutAuditor(dna)
    audit_report = auditor.audit_layout(scene, dna)

    return {
        "filename": filename,
        "format": suffix.replace(".", ""),
        "scene_graph": scene.model_dump(),
        "title_dna": dna.model_dump(),
        "audit": audit_report.to_dict(),
        "metadata": meta,
    }


@router.post("/audit")
def audit_layout_endpoint(req: AuditRequest):
    """Performs deep diagnosis of editorial layout against newspaper and aesthetic rules."""
    auditor = LayoutAuditor(req.title_dna)
    report = auditor.audit_layout(req.scene_graph, req.title_dna)
    return report.to_dict()


@router.post("/improve")
def improve_layout_endpoint(req: ImproveRequest):
    """Generates 3 directed improvement candidates addressing diagnosed layout defects."""
    improver = LayoutImprover()
    target_dna = req.title_dna
    if not target_dna:
        from ..engine.grammar import create_default_tabloid_dna
        target_dna = create_default_tabloid_dna()

    result = improver.improve_layout(req.scene_graph, target_dna)
    return result.to_dict()


@router.post("/export-idml")
def export_scene_to_idml(req: ExportIDMLRequest):
    """Renders the improved SceneGraph directly into a production-ready Adobe InDesign IDML package."""
    target_dna = req.title_dna
    renderer = IDMLRenderer(target_dna)

    with tempfile.NamedTemporaryFile(suffix=".idml", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        renderer.render_to_zip(req.scene_graph, str(tmp_path))
        data = tmp_path.read_bytes()
        return Response(
            content=data,
            media_type="application/vnd.adobe.indesign-idml-package",
            headers={"Content-Disposition": 'attachment; filename="improved_layout.idml"'},
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
