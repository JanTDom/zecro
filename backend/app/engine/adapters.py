"""Replaceable local/cloud adapter interfaces with deterministic defaults."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Protocol

from .content_engine import generate_copy_variants


@dataclass(frozen=True)
class AdapterInfo:
    provider: str
    model: str
    version: str


class ContentWriter(Protocol):
    info: AdapterInfo
    def generate(self, story: Any) -> List[Any]: ...


class FactChecker(Protocol):
    info: AdapterInfo
    def check(self, claims: Iterable[Any], sources: Iterable[Any]) -> List[Any]: ...


class VisionCritic(Protocol):
    info: AdapterInfo
    def score(self, scene_graph: Any) -> Dict[str, Any]: ...


class ImageSegmenter(Protocol):
    info: AdapterInfo
    def contour(self, asset_path: str, width_mm: float, height_mm: float) -> List[List[float]]: ...


class DeterministicContentWriter:
    info = AdapterInfo("zecro-local", "deterministic-content-v1", "1")
    def generate(self, story: Any) -> List[Any]:
        return generate_copy_variants(story)


class NoOpFactChecker:
    """Safe fallback: it never upgrades a claim without evidence."""
    info = AdapterInfo("zecro-local", "evidence-required-factcheck-v1", "1")
    def check(self, claims: Iterable[Any], sources: Iterable[Any]) -> List[Any]:
        source_text = " ".join(str(getattr(source, "excerpt", "") or "") for source in sources)
        output = []
        for claim in claims:
            if source_text and str(getattr(claim, "text", "")).rstrip(".") in source_text:
                claim.status, claim.confidence = "verified", 0.95
            else:
                claim.status, claim.confidence = "needs_editor", 0.0
            output.append(claim)
        return output


class DisabledVisionCritic:
    info = AdapterInfo("disabled", "no-vlm-configured", "1")
    def score(self, scene_graph: Any) -> Dict[str, Any]:
        return {"status": "unavailable", "score": None, "reason": "Configure VLM_ENDPOINT to enable visual scoring."}


__all__ = ["AdapterInfo", "ContentWriter", "FactChecker", "VisionCritic", "ImageSegmenter", "DeterministicContentWriter", "NoOpFactChecker", "DisabledVisionCritic"]
