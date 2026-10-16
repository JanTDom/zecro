"""Content-aware crop anchor; failures leave editorial control intact."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image

from . import schemas as S
from .runtime import run_task


def analyse_photo_focal(path: str | Path) -> dict[str, Any]:
    try:
        with Image.open(path) as source:
            preview = source.convert("RGB")
            preview.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            preview.save(buffer, format="JPEG", quality=85)
        response = run_task("photo_focal", "photo_focal", {}, S.PhotoFocalAI,
                            images=[{"data": buffer.getvalue(), "mime_type": "image/jpeg"}],
                            timeout_s=22, max_retries=0)
        row = S.PhotoFocalAI.model_validate(response.data)
        if row.confidence < .6 or row.subject_kind == "uncertain":
            return {"status": "uncertain", "focal_point": [.5, .5],
                    "subject_kind": row.subject_kind, "confidence": row.confidence}
        return {"status": "ready", "focal_point": [round(row.point_x / 1000, 3), round(row.point_y / 1000, 3)],
                "subject_kind": row.subject_kind, "confidence": row.confidence,
                "provider": response.provenance.get("provider"), "model": response.provenance.get("model")}
    except Exception as exc:
        return {"status": "unavailable", "focal_point": [.5, .5],
                "subject_kind": "uncertain", "reason": exc.__class__.__name__}
