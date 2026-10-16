from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from ..config import settings
from ..engine.image_ops import extract_alpha_contour
from ..engine.segmentation import segment_image
from ..ai.photo_focal import analyse_photo_focal
from ..models.database import db
from ..models.schemas import Asset
from ..storage.asset_store import materialize_asset, persist_asset
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
    mask_reference = None
    cutout_provider = None
    cutout_quality = None
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
    focal_review = analyse_photo_focal(path)
    cutout_status = "not_requested"
    if auto_cutout:
        if ext == ".png":
            contour = extract_alpha_contour(str(path), 100.0, 100.0)
            cutout_status = "ready" if contour else "unavailable"
        elif (focal_review.get("status") == "ready" and focal_review.get("confidence", 0) >= .7
              and focal_review.get("subject_kind") in {"object", "scene"}):
            cutout_status = "not_applicable"
        else:
            result = segment_image(path, settings.UPLOADS_DIR / f"mask_{asset_id}.png", target_w_mm=100.0, target_h_mm=100.0)
            contour, cutout_status = result.contour, result.status
            cutout_provider, cutout_quality = result.provider, result.quality
            if contour and result.mask_path:
                mask_path = Path(result.mask_path)
                mask_reference = persist_asset(mask_path, prefix="uploads", key=mask_path.name)
                if not mask_reference:
                    contour, cutout_status = None, "unavailable"
    stored_reference = persist_asset(path, prefix="uploads", key=path.name)
    if not stored_reference:
        raise HTTPException(status_code=503, detail="Asset storage is unavailable; remote storage is required")
    remote = parse_storage_reference(stored_reference)
    public_url = get_storage_public_url(stored_reference) if remote else f"/static/uploads/{path.name}"
    if contour and not mask_reference:
        mask_reference = stored_reference  # uploaded PNG already contains genuine alpha
    mask_url = (get_storage_public_url(mask_reference) if parse_storage_reference(mask_reference)
                else f"/static/uploads/{Path(mask_reference).name}") if mask_reference else None
    focal = list(focal_review.get("focal_point") or [.5, .5])
    if contour and focal_review.get("status") != "ready":
        # The mask gives a measurable subject location.  Bias toward the
        # upper part of a person instead of cropping at the body's centroid.
        xs = [float(point[0]) for point in contour]
        ys = [float(point[1]) for point in contour]
        focal = [round(min(.95, max(.05, (min(xs) + max(xs)) / 200)), 3),
                 round(min(.95, max(.05, (min(ys) + .30 * (max(ys) - min(ys))) / 100)), 3)]
    asset = Asset(id=asset_id, uri=stored_reference, asset_type="photo", width_px=width_px, height_px=height_px,
                  dpi=dpi, focal_point=focal, status="available",
                  metadata={"alpha_mask_ref": mask_reference, "contour_polygon": contour,
                            "cutout_status": cutout_status, "cutout_provider": cutout_provider,
                            "cutout_quality": cutout_quality, "focal_review": focal_review})
    db.save_editorial_object("asset", asset, project_id=None, reason="asset_uploaded")
    return {
        "id": asset_id,
        "file_name": path.name,
        "url": public_url,
        "storage_ref": stored_reference,
        "alpha_mask_url": mask_url,
        "contour_polygon": contour,
        "is_cutout_candidate": bool(contour),
        "cutout_status": cutout_status,
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
        "focal_point": focal,
        "focal_status": focal_review.get("status"),
        "subject_kind": focal_review.get("subject_kind"),
    }


@router.post("/{asset_id}/cutout")
def cutout_asset(asset_id: str):
    payload = db.get_editorial_object("asset", asset_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Asset not found")
    ref = payload.get("uri") or ""
    source = materialize_asset(ref, prefix="uploads", cache_dir=settings.UPLOADS_DIR / ".cache")
    if source is None:
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":"local asset is unavailable"})
    mask = settings.UPLOADS_DIR / f"mask_{asset_id}.png"
    result = segment_image(source, mask, target_w_mm=100.0, target_h_mm=100.0)
    if result.status != "ready":
        raise HTTPException(status_code=503, detail={"status":result.status, "reason":result.reason})
    mask_reference = persist_asset(mask, prefix="uploads", key=mask.name)
    if not mask_reference:
        raise HTTPException(status_code=503, detail={"status":"unavailable", "reason":"mask storage is unavailable"})
    payload.setdefault("metadata", {}).update({"alpha_mask_ref": mask_reference, "contour_polygon": result.contour,
                                                 "cutout_status": "ready", "cutout_provider": result.provider,
                                                 "cutout_quality": result.quality})
    payload["version"] = int(payload.get("version",1)) + 1
    db.save_editorial_object("asset", Asset(**payload), reason="asset_cutout")
    mask_url = (get_storage_public_url(mask_reference) if parse_storage_reference(mask_reference)
                else f"/static/uploads/{Path(mask_reference).name}")
    return {"status":"ready", "asset_id":asset_id, "alpha_mask_url":mask_url,
            "contour_polygon":result.contour, "quality":result.quality}
