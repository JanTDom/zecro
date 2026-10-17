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


@router.post("/candidates/{candidate_id}/export-social", response_model=ExportArtifact, status_code=status.HTTP_201_CREATED)
def export_social_card(
    candidate_id: str,
    ratio: str = Query("9:16", enum=["9:16", "1:1"]),
):
    """Generates a high-impact social media digital twin card (9:16 Stories or 1:1 Post)."""
    cand = db.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    project_id = db.get_candidate_project_id(candidate_id) or cand.scene_graph.page.title_dna_ref or ""
    dna = db.get_title_dna(project_id)
    if not dna:
        raise HTTPException(status_code=409, detail="Title DNA for candidate project is unavailable")

    export_id = str(uuid.uuid4())
    filename = f"social_{candidate_id}_{ratio.replace(':', 'x')}_{export_id}.svg"
    file_path = settings.EXPORTS_DIR / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if ratio == "9:16":
        width_px, height_px = 1080, 1920
    else:
        width_px, height_px = 1080, 1080

    elements = cand.scene_graph.elements
    headline_el = next((el for el in elements if el.role in ("headline", "lead_headline")), None)
    photo_el = next((el for el in elements if el.role in ("photo", "lead_photo", "cutout_photo")), None)
    kicker_el = next((el for el in elements if el.role == "kicker"), None)

    paper_name = dna.name.upper() if dna and getattr(dna, "name", None) else "ZECRO PRESS"
    headline_text = (headline_el.text_content or "") if headline_el and getattr(headline_el, "text_content", None) else "GŁÓWNY TEMAT WYDANIA"
    kicker_text = (kicker_el.text_content or "") if kicker_el and getattr(kicker_el, "text_content", None) else "WYDANIE SPECJALNE"
    photo_url = (photo_el.image_url or "") if photo_el and getattr(photo_el, "image_url", None) else ""

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width_px} {height_px}" width="{width_px}" height="{height_px}">
  <defs>
    <style>
      .bg {{ fill: #0f1115; }}
      .card-frame {{ fill: #ffffff; stroke: #111111; stroke-width: 8; }}
      .masthead {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: {width_px * 0.055:.1f}px; font-weight: 900; fill: #111111; letter-spacing: 2px; text-transform: uppercase; }}
      .kicker {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: {width_px * 0.024:.1f}px; font-weight: 800; fill: #cc0000; letter-spacing: 1.5px; text-transform: uppercase; }}
      .date-badge {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: {width_px * 0.02:.1f}px; font-weight: 700; fill: #666666; }}
      .read-more {{ font-family: 'Barlow', 'Helvetica Neue', Arial, sans-serif; font-size: {width_px * 0.028:.1f}px; font-weight: 800; fill: #ffffff; text-transform: uppercase; }}
    </style>
  </defs>

  <rect class="bg" width="{width_px}" height="{height_px}" />
  <rect class="card-frame" x="40" y="40" width="{width_px - 80}" height="{height_px - 80}" rx="12" />

  <text class="masthead" x="80" y="130">{paper_name}</text>
  <text class="date-badge" x="{width_px - 80}" y="125" text-anchor="end">Wydanie Cyfrowe · Dziś w kioskach</text>
  <line x1="80" y1="160" x2="{width_px - 80}" y2="160" stroke="#111111" stroke-width="4" />

  <text class="kicker" x="80" y="220">{kicker_text}</text>

  <foreignObject x="80" y="240" width="{width_px - 160}" height="280">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: 'PT Serif', Georgia, serif; font-size: {width_px * 0.058:.1f}px; font-weight: 900; color: #111111; line-height: 1.15; text-transform: none;">
      {headline_text}
    </div>
  </foreignObject>

  <g transform="translate(80, 540)">
    <rect width="{width_px - 160}" height="{height_px - 720}" fill="#e8e4dc" stroke="#111111" stroke-width="3" rx="6" />
    {f'<image href="{photo_url}" width="{width_px - 160}" height="{height_px - 720}" preserveAspectRatio="xMidYMid slice" clip-path="inset(0 round 6px)" />' if photo_url else f'<text x="{(width_px - 160)/2}" y="{(height_px - 720)/2}" text-anchor="middle" font-family="sans-serif" font-size="28" fill="#888888">Zdjęcie czołówkowe wydania</text>'}
  </g>

  <rect x="80" y="{height_px - 140}" width="{width_px - 160}" height="70" fill="#cc0000" rx="6" />
  <text class="read-more" x="{width_px / 2}" y="{height_px - 96}" text-anchor="middle">Czytaj pełne wydanie w druku i PDF</text>
</svg>"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    file_size = os.path.getsize(file_path)
    stored_reference = persist_asset(file_path, prefix="exports", key=filename)
    if not stored_reference:
        raise HTTPException(status_code=503, detail="Export storage is unavailable")

    artifact = ExportArtifact(
        id=export_id,
        project_id=project_id,
        candidate_id=candidate_id,
        format="svg",
        file_path=stored_reference,
        file_size_bytes=file_size,
        created_at=datetime.now(timezone.utc).isoformat()
    )

    db.save_export_artifact(artifact)
    return artifact


