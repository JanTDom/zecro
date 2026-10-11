from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from ..config import settings
from ..engine.image_ops import extract_alpha_contour
from ..engine.segmentation import segment_image
from ..models.database import db
from ..models.schemas import Asset
from ..storage.asset_store import persist_asset
from ..storage.supabase_storage import get_storage_public_url, parse_storage_reference

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("/image")
@router.post("", include_in_schema=False)
async def upload_image_asset(file: UploadFile = File(...), auto_cutout: bool = Form(False)):
    """Store an editorial image and optionally derive an alpha contour.

    Background removal itself is deliberately provider-neutral.  The endpoint
    accepts pre-masked PNGs from a local editor or an external segmenter and
    records a deterministic contour for the scene graph.
    """
    ext = Path(file.filename or "asset.bin").suffix.lower() or ".bin"
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        raise HTTPException(status_code=415, detail="Unsupported image format")
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())
    path = settings.UPLOADS_DIR / f"asset_{asset_id}{ext}"
    with path.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    contour = None
    width_px = height_px = None
    dpi = None
    try:
        from PIL import Image
        with Image.open(path) as image:
            width_px, height_px = image.size
            if image.info.get("dpi"):
                dpi = float(image.info["dpi"][0])
    except Exception:
        pass
    cutout_status = "not_requested"
    if auto_cutout:
        if ext == ".png":
            contour = extract_alpha_contour(str(path), 100.0, 100.0)
            cutout_status = "ready" if contour else "unavailable"
        else:
            result = segment_image(path, settings.UPLOADS_DIR / f"mask_{asset_id}.png", target_w_mm=100.0, target_h_mm=100.0)
            contour, cutout_status = result.contour, result.status
    stored_reference = persist_asset(path, prefix="uploads", key=path.name)
    if not stored_reference:
        raise HTTPException(status_code=503, detail="Asset storage is unavailable; remote storage is required")
    remote = parse_storage_reference(stored_reference)
    public_url = get_storage_public_url(stored_reference) if remote else f"/static/uploads/{path.name}"
    asset = Asset(id=asset_id, uri=stored_reference, asset_type="photo", width_px=width_px, height_px=height_px, dpi=dpi, focal_point=[0.5,0.5], status="available")
    db.save_editorial_object("asset", asset, project_id=None, reason="asset_uploaded")
    return {
        "id": asset_id,
        "file_name": path.name,
        "url": public_url,
        "storage_ref": stored_reference,
        "alpha_mask_url": public_url if contour else None,
        "contour_polygon": contour,
        "is_cutout_candidate": bool(contour),
        "cutout_status": cutout_status,
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
    }


@router.post("/{asset_id}/cutout")
def cutout_asset(asset_id: str):
    payload = db.get_editorial_object("asset", asset_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Asset not found")
    ref = payload.get("uri") or ""
    source = Path(ref)
    if not source.exists():
        source = settings.UPLOADS_DIR / Path(ref).name
    if not source.exists():
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":"local asset is unavailable"})
    mask = settings.UPLOADS_DIR / f"mask_{asset_id}.png"
    result = segment_image(source, mask, target_w_mm=100.0, target_h_mm=100.0)
    if result.status != "ready":
        raise HTTPException(status_code=503, detail={"status":result.status, "reason":result.reason})
    payload.setdefault("metadata", {})["alpha_mask_url"] = str(mask)
    payload["version"] = int(payload.get("version",1)) + 1
    db.save_editorial_object("asset", Asset(**payload), reason="asset_cutout")
    return {"status":"ready", "asset_id":asset_id, "alpha_mask_url":str(mask), "contour_polygon":result.contour, "quality":result.quality}
