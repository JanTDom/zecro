"""Real background-removal adapter and mask quality metrics.

No provider is silently substituted: when rembg/model data is unavailable the
result is ``unavailable`` and callers can keep the original rectangular photo.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
from PIL import Image
from .image_ops import extract_alpha_contour, extract_alpha_rings

@dataclass
class SegmentationResult:
    status: str
    reason: str | None = None
    mask_path: str | None = None
    contour: list[list[float]] | None = None
    holes: list[list[list[float]]] | None = None
    quality: dict[str, Any] | None = None
    provider: str = "rembg"


def mask_quality(mask_path: str) -> dict[str, Any]:
    with Image.open(mask_path).convert("RGBA") as im:
        alpha = im.getchannel("A")
        values = list(alpha.getdata())
        semi = sum(0 < value < 255 for value in values)
        opaque = sum(value >= 128 for value in values)
        return {
            "semi_transparent_ratio": round(semi / max(1, len(values)), 4),
            "coverage_ratio": round(opaque / max(1, len(values)), 4),
            "status": "clean" if opaque and semi / max(1, len(values)) < .35 else "minor_issues" if opaque else "unusable",
        }


_SESSIONS: dict[str, Any] = {}


def default_model() -> str:
    import os
    return os.getenv("ZECRO_SEGMENTATION_MODEL", "birefnet-general-lite")


def _session(model: str):
    from rembg import new_session
    if model not in _SESSIONS:
        _SESSIONS[model] = new_session(model)
    return _SESSIONS[model]


def segment_image(source_path: str | Path, output_path: str | Path, *, model: str | None = None, target_w_mm: float = 100.0, target_h_mm: float = 100.0, alpha_matting: bool = False) -> SegmentationResult:
    source_path, output_path = Path(source_path), Path(output_path)
    try:
        from rembg import remove
    except Exception as exc:
        return SegmentationResult(status="unavailable", reason=f"rembg is not installed: {exc}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as source:
            model = model or default_model()
            # BiRefNet already produces matte-quality edges; classic alpha
            # matting is optional (slow, and can erode thin limbs).
            result = remove(source.read(), session=_session(model), alpha_matting=alpha_matting)
        output_path.write_bytes(result)
        quality = mask_quality(str(output_path))
        # Contours are stored in normalised image space (0..100) so the
        # layout can apply any crop later without re-segmenting.
        rings = extract_alpha_rings(str(output_path), 100.0, 100.0)
        if not rings:
            return SegmentationResult(status="unavailable", reason="segmentation produced no usable alpha contour", mask_path=str(output_path), quality=quality, provider=f"rembg:{model}")
        return SegmentationResult(status="ready", mask_path=str(output_path), contour=rings[0]["outer"], holes=rings[0]["holes"], quality=quality, provider=f"rembg:{model}")
    except Exception as exc:
        return SegmentationResult(status="failed", reason=str(exc))
