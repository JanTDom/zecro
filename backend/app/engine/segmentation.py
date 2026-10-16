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
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel, Field
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
        histogram = alpha.histogram()
        semi = sum(histogram[1:255])
        opaque = sum(histogram[128:])
        pixel_count = alpha.width * alpha.height
        return {
            "semi_transparent_ratio": round(semi / max(1, pixel_count), 4),
            "coverage_ratio": round(opaque / max(1, pixel_count), 4),
            "status": "clean" if opaque and semi / max(1, pixel_count) < .35 else "minor_issues" if opaque else "unusable",
        }


_SESSIONS: dict[str, Any] = {}


class _SegmentedSubject(BaseModel):
    label: str
    box_2d: list[int] = Field(default_factory=list)
    mask: list[list[int]]


class _SubjectSegmentation(BaseModel):
    objects: list[_SegmentedSubject] = Field(default_factory=list)


def _polygon_area(points: list[list[float]]) -> float:
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] -
                   points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points))) / 2)


def _gemini_segment(source_path: Path, output_path: Path) -> SegmentationResult:
    """Use a model-returned polygon, then make the alpha locally from pixels.

    This is the production fallback when the heavyweight local ONNX adapter
    is unavailable.  A missing or box-like polygon never becomes a cutout.
    """
    from ..ai.runtime import run_task
    try:
        import io
        with Image.open(source_path) as original:
            original = original.convert("RGB")
            preview = original.copy()
            preview.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            preview.save(buffer, format="JPEG", quality=85)
            response = run_task(
                "subject_segmentation", "subject_segmentation",
                {"target": "najważniejsza osoba lub zwierzę na pierwszym planie"},
                _SubjectSegmentation,
                images=[{"data": buffer.getvalue(), "mime_type": "image/jpeg"}],
                timeout_s=60, max_retries=1,
            )
            valid = []
            for item in response.data.get("objects") or []:
                raw = item.get("mask") or []
                if len(raw) < 8 or len(raw) > 256 or any(len(point) != 2 for point in raw):
                    continue
                if any(not all(isinstance(v, (int, float)) and 0 <= v <= 1000 for v in point) for point in raw):
                    continue
                ring = [[float(x) / 10, float(y) / 10] for x, y in raw]
                area = _polygon_area(ring)
                if not 350 <= area <= 8500:
                    continue
                valid.append((area, ring))
            if not valid:
                return SegmentationResult(status="unavailable", reason="Gemini returned no usable foreground contour", provider="gemini")
            _, ring = max(valid, key=lambda pair: pair[0])
            # Reject an axis-aligned rectangle presented as segmentation.
            if len({round(p[0], 1) for p in ring}) <= 2 and len({round(p[1], 1) for p in ring}) <= 2:
                return SegmentationResult(status="unavailable", reason="Gemini returned a bounding box rather than a contour", provider="gemini")
            mask = Image.new("L", original.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.polygon([(round(x * original.width / 100), round(y * original.height / 100))
                          for x, y in ring], fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=max(.7, min(original.size) / 1300)))
            cutout = original.convert("RGBA")
            cutout.putalpha(mask)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cutout.save(output_path)
            quality = mask_quality(str(output_path))
            quality.update({"polygon_points": len(ring), "coverage_ratio": round(_polygon_area(ring) / 10000, 4)})
            return SegmentationResult(status="ready", mask_path=str(output_path), contour=ring,
                                      holes=[], quality=quality,
                                      provider="gemini:" + str(response.provenance.get("model") or "unknown"))
    except Exception as exc:
        return SegmentationResult(status="unavailable", reason=f"Gemini segmentation unavailable: {str(exc)[:240]}", provider="gemini")


def _remote_service_segment(
    source_path: Path,
    output_path: Path,
    service_url: str,
    api_key: str | None = None,
    timeout_s: float = 30.0,
) -> SegmentationResult:
    """Delegate background removal to an external microservice worker."""
    import urllib.request
    import urllib.error
    import mimetypes

    try:
        data = source_path.read_bytes()
        boundary = f"----WebKitFormBoundary{hashlib.md5(data[:64] or b'zecro').hexdigest()}"
        filename = source_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "ZecroLayoutEngine/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            service_url,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            resp_body = resp.read()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp_body)
            quality = mask_quality(str(output_path))
            rings = extract_alpha_rings(str(output_path), 100.0, 100.0)
            if not rings:
                return SegmentationResult(
                    status="unavailable",
                    reason="Remote segmentation produced no usable alpha contour",
                    mask_path=str(output_path),
                    quality=quality,
                    provider="remote_service",
                )
            return SegmentationResult(
                status="ready",
                mask_path=str(output_path),
                contour=rings[0]["outer"],
                holes=rings[0]["holes"],
                quality=quality,
                provider="remote_service",
            )
    except Exception as exc:
        return SegmentationResult(
            status="unavailable",
            reason=f"Remote segmentation service failed: {str(exc)[:200]}",
            provider="remote_service",
        )


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
    import os
    remote_url = os.getenv("ZECRO_SEGMENTATION_SERVICE_URL")
    if remote_url:
        remote_res = _remote_service_segment(source_path, output_path, remote_url, os.getenv("ZECRO_SEGMENTATION_API_KEY"))
        if remote_res.status == "ready":
            return remote_res

    try:
        from rembg import remove
    except Exception as exc:
        return _gemini_segment(source_path, output_path)
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

