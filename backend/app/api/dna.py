from fastapi import APIRouter, File, HTTPException, UploadFile
from ..models.schemas import TitleDNA
from ..models.database import db

router = APIRouter(prefix="/projects", tags=["dna"])

@router.get("/{project_id}/dna", response_model=TitleDNA)
def get_project_dna(project_id: str):
    dna = db.get_title_dna(project_id)
    if not dna:
        proj = db.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        from ..engine.grammar import create_default_broadsheet_dna, create_default_tabloid_dna
        if "tabloid" in proj.name.lower() or "expressive" in (proj.description or "").lower():
            dna = create_default_tabloid_dna()
        else:
            dna = create_default_broadsheet_dna()
        dna.name = f"{proj.name} DNA"
        dna = db.save_title_dna(project_id, dna)
    return dna

@router.put("/{project_id}/dna", response_model=TitleDNA)
def update_project_dna(project_id: str, dna: TitleDNA):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    saved = db.save_title_dna(project_id, dna)
    return saved


@router.post("/{project_id}/dna/import-idml", response_model=TitleDNA)
async def import_idml_to_dna(project_id: str, file: UploadFile = File(...)):
    """Extracts TitleDNA grid, margins, swatches, and typography from an IDML archive."""
    import tempfile
    from pathlib import Path
    from scripts.dissect_indesign import parse_idml

    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    dna = db.get_title_dna(project_id)
    if not dna:
        from ..engine.grammar import create_default_tabloid_dna
        dna = create_default_tabloid_dna()

    suffix = Path(file.filename or "file.idml").suffix.lower() or ".idml"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        dissected = parse_idml(tmp_path)
        dna.grid.columns = dissected.grid.columns
        dna.grid.gutterWidthMm = dissected.grid.gutter_mm
        dna.grid.baselineGridPt = dissected.grid.baseline_grid_pt
        dna.grid.margins.topMm = dissected.grid.margin_top_mm
        dna.grid.margins.bottomMm = dissected.grid.margin_bottom_mm
        dna.grid.margins.insideMm = dissected.grid.margin_inside_mm
        dna.grid.margins.outsideMm = dissected.grid.margin_outside_mm
        dna.format.widthMm = dissected.grid.page_width_mm
        dna.format.heightMm = dissected.grid.page_height_mm

        if dissected.swatches:
            for s in dissected.swatches:
                if len(s.values) >= 4:
                    val_str = f"cmyk({s.values[0]:.0f}%, {s.values[1]:.0f}%, {s.values[2]:.0f}%, {s.values[3]:.0f}%)"
                    if "navy" in s.name.lower() or "primary" in s.name.lower():
                        dna.palette.primary = val_str
                    elif "red" in s.name.lower() or "accent" in s.name.lower():
                        dna.palette.accent = val_str

        saved = db.save_title_dna(project_id, dna)
        return saved
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

