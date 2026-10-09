from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from ..config import settings
from ..engine.image_ops import extract_alpha_contour

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
    if auto_cutout and ext == ".png":
        contour = extract_alpha_contour(str(path), 100.0, 100.0)
    return {
        "id": asset_id,
        "file_name": path.name,
        "url": f"/static/uploads/{path.name}",
        "alpha_mask_url": f"/static/uploads/{path.name}" if contour else None,
        "contour_polygon": contour,
        "is_cutout_candidate": bool(contour),
        "width_px": width_px,
        "height_px": height_px,
        "dpi": dpi,
    }
