"""Gemini review of a segmentation mask (original + cut-out on a checkerboard)."""
from __future__ import annotations
import io
from typing import Any, Optional
from PIL import Image
from .runtime import run_task
from . import schemas as S


def _checker(mask_path: str) -> bytes:
    cut = Image.open(mask_path).convert("RGBA")
    cut.thumbnail((900, 900))
    tile = 24
    bg = Image.new("RGB", cut.size, (255, 255, 255))
    for y in range(0, cut.height, tile):
        for x in range(0, cut.width, tile):
            if (x // tile + y // tile) % 2:
                bg.paste((205, 205, 205), (x, y, x + tile, y + tile))
    bg.paste(cut, mask=cut.getchannel("A"))
    buf = io.BytesIO(); bg.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def review_mask(original: str, mask: str, project_id: Optional[str] = None) -> dict[str, Any]:
    from ..storage.asset_store import materialize_asset
    from ..config import settings
    o = materialize_asset(original, prefix="uploads", cache_dir=settings.uploads_dir / "_cache") or original
    m = materialize_asset(mask, prefix="uploads", cache_dir=settings.uploads_dir / "_cache") or mask
    im = Image.open(o).convert("RGB"); im.thumbnail((900, 900))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
    res = run_task("mask_qa", "mask_qa", {"note": "obraz 1: oryginał, obraz 2: wycięcie na szachownicy"}, S.MaskQA,
                   images=[{"data": buf.getvalue(), "mime_type": "image/jpeg"}, {"data": _checker(str(m)), "mime_type": "image/jpeg"}], project_id=project_id)
    return {**res.data, "provenance": res.provenance}
