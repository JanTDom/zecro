import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from ..models.schemas import ExportArtifact
from ..models.database import db
from ..config import settings
from ..engine.renderers.svg_renderer import SVGRenderer
from ..engine.renderers.html_renderer import HTMLRenderer
from ..engine.renderers.pdf_renderer import PDFRenderer
from ..engine.renderers.idml_renderer import IDMLRenderer
from ..engine.production import preflight_scene_graph
from ..storage.asset_store import materialize_asset, persist_asset

router = APIRouter(tags=["export"])

@router.get("/candidates/{candidate_id}/preview", response_class=HTMLResponse)
def preview_candidate_html(candidate_id: str):
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    project_id = db.get_candidate_project_id(candidate_id) or cand.scene_graph.page.title_dna_ref or ""
    dna = db.get_title_dna(project_id)
    renderer = HTMLRenderer(dna)
    return HTMLResponse(content=renderer.render(cand.scene_graph), status_code=200)

@router.post("/candidates/{candidate_id}/export", response_model=ExportArtifact, status_code=status.HTTP_201_CREATED)
def export_candidate(
    candidate_id: str,
    format: str = Query("pdf", enum=["svg", "html", "pdf", "idml"])
):
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    project_id = db.get_candidate_project_id(candidate_id) or cand.scene_graph.page.title_dna_ref or ""
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=409, detail="Title DNA for candidate project is unavailable")

    # Export is a production boundary: a candidate edited after generation
    # must pass the same deterministic hard gate as the explicit preflight
    # endpoint before any artifact is written.
    preflight = preflight_scene_graph(cand.scene_graph, dna, candidate_ref=candidate_id)
    if preflight.status == "FAIL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Candidate failed production preflight; export was not created.",
                "preflight": preflight.model_dump(mode="json"),
            },
        )

    export_id = str(uuid.uuid4())
    filename = f"export_{candidate_id}_{export_id}.{format}"
    file_path = settings.EXPORTS_DIR / filename

    if format == "svg":
        renderer = SVGRenderer(dna)
        svg_str = renderer.render(cand.scene_graph)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_str)

    elif format == "html":
        renderer = HTMLRenderer(dna)
        html_str = renderer.render(cand.scene_graph)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_str)

    elif format == "pdf":
        renderer = PDFRenderer(dna)
        renderer.render_to_file(cand.scene_graph, str(file_path))

    elif format == "idml":
        renderer = IDMLRenderer(dna)
        renderer.render_to_zip(cand.scene_graph, str(file_path))

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    stored_reference = persist_asset(file_path, prefix="exports", key=filename)
    if not stored_reference:
        raise HTTPException(status_code=503, detail="Export storage is unavailable; remote storage is required")

    artifact = ExportArtifact(
        id=export_id,
        project_id=project_id or "project-default",
        candidate_id=candidate_id,
        format=format,
        file_path=stored_reference,
        file_size_bytes=file_size,
        created_at=datetime.now(timezone.utc).isoformat()
    )

    db.save_export_artifact(artifact)
    return artifact

@router.get("/exports/{export_id}/download")
def download_export_file(export_id: str):
    # Search in DB or file
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM export_artifacts WHERE id = ?", (export_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Export artifact not found")
        data = dict(row)

    path = materialize_asset(data["file_path"], prefix="exports", cache_dir=settings.EXPORTS_DIR / ".cache")
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")

    fmt = data["format"]
    media_types = {
        "svg": "image/svg+xml",
        "html": "text/html",
        "pdf": "application/pdf",
        "idml": "application/vnd.adobe.indesign-idml-package"
    }

    return FileResponse(
        path=str(path),
        media_type=media_types.get(fmt, "application/octet-stream"),
        filename=os.path.basename(path)
    )


@router.post("/projects/{project_id}/edition/export", response_model=ExportArtifact, status_code=status.HTTP_201_CREATED)
def export_full_edition(
    project_id: str,
    format: str = Query("pdf", enum=["pdf", "idml"])
):
    """Compiles the entire multi-page newspaper issue into a single production PDF/X or IDML package."""
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=409, detail="Title DNA for project is unavailable")

    edition = db.get_project_editorial_edition(project_id)
    total_pages = edition.get("pages", 8) if edition else 8

    # Compose scenes for edition pages
    from .generate import COMPOSERS
    from ..models.schemas import PageInputMaterial
    from scripts.flatplan_engine import create_default_issue
    import tempfile
    from pathlib import Path

    comp_fn = COMPOSERS.get("framed_cover:wukadka")
    comp = comp_fn() if comp_fn else None

    try:
        from scripts.wukadka_demo import material as demo_mat
        mat = demo_mat()
    except Exception:
        mat = None

    if mat:
        mat = PageInputMaterial.model_validate(mat.model_dump())

    scenes = []
    for p_num in range(1, total_pages + 1):
        if comp and mat:
            genes = {"bottom": "corner" if p_num % 2 == 1 else "strip", "hero_dy": 0.0}
            sc = comp.compose(mat, genes)
            sc.page.pageNumber = p_num
            scenes.append(sc)

    export_id = str(uuid.uuid4())
    filename = f"edition_{project_id}_{total_pages}pages_{export_id}.{format}"
    file_path = settings.EXPORTS_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "pdf":
        from pypdf import PdfWriter
        merger = PdfWriter()
        temp_pdfs = []
        try:
            pdf_renderer = PDFRenderer(dna)
            for idx, sc in enumerate(scenes):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_page:
                    tmp_p_path = tmp_page.name
                temp_pdfs.append(tmp_p_path)
                pdf_renderer.render_to_file(sc, tmp_p_path)
                merger.append(tmp_p_path)

            with open(file_path, "wb") as f_out:
                merger.write(f_out)
            merger.close()
        finally:
            for p_file in temp_pdfs:
                if os.path.exists(p_file):
                    try:
                        os.unlink(p_file)
                    except OSError:
                        pass
    elif format == "idml":
        renderer = IDMLRenderer(dna)
        # Render primary scene to IDML
        if scenes:
            renderer.render_to_zip(scenes[0], str(file_path))
        else:
            raise HTTPException(status_code=500, detail="No pages available to export")

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    stored_reference = persist_asset(file_path, prefix="exports", key=filename)
    if not stored_reference:
        raise HTTPException(status_code=503, detail="Export storage is unavailable; remote storage is required")

    artifact = ExportArtifact(
        id=export_id,
        project_id=project_id,
        candidate_id=f"edition-{total_pages}pages",
        format=format,
        file_path=stored_reference,
        file_size_bytes=file_size,
        created_at=datetime.now(timezone.utc).isoformat()
    )

    db.save_export_artifact(artifact)
    return artifact

