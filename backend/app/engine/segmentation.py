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
from .image_ops import extract_alpha_contour

@dataclass
class SegmentationResult:
    status: str
    reason: str | None = None
    mask_path: str | None = None
    contour: list[list[float]] | None = None
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


def segment_image(source_path: str | Path, output_path: str | Path, *, model: str = "birefnet-general", target_w_mm: float = 100.0, target_h_mm: float = 100.0) -> SegmentationResult:
    source_path, output_path = Path(source_path), Path(output_path)
    try:
        from rembg import remove, new_session
    except Exception as exc:
        return SegmentationResult(status="unavailable", reason=f"rembg is not installed: {exc}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as source:
            session = new_session(model)
            result = remove(source.read(), session=session, alpha_matting=True)
        output_path.write_bytes(result)
        quality = mask_quality(str(output_path))
        contour = extract_alpha_contour(str(output_path), target_w_mm, target_h_mm)
        if not contour:
            return SegmentationResult(status="unavailable", reason="segmentation produced no usable alpha contour", mask_path=str(output_path), quality=quality)
        return SegmentationResult(status="ready", mask_path=str(output_path), contour=contour, quality=quality)
    except Exception as exc:
        return SegmentationResult(status="failed", reason=str(exc))
