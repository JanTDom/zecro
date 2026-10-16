"""AI photo editing decisions made before page geometry is generated.

The layout engine consumes the first image of each story.  This module makes
that order editorial rather than accidental: a vision model acting as a photo
editor compares the locally materialised source photographs with the headline
and lead, promotes the strongest candidate and records *structured
observations* (emotion, motion, faces, gaze, a headline-safe zone, cutout
feasibility, print quality at the target crop).  The geometry generator reads
those observations as data; the model never sets coordinates.

When the best photograph of the lead story is too weak for its headline the
run stops with an explicit "potrzebne inne zdjęcie" verdict instead of laying
out a weak cover.  The module never invents a photo, never identifies people
from faces and never mutates the caller's material.
"""
from __future__ import annotations

from typing import Any, Optional

from .runtime import run_task
from .schemas import PhotoRanking
from ..engine.image_ops import resolve_asset_path
from ..models.schemas import PageInputMaterial

# Editorial weights.  Relevance and headline match dominate; reportage and
# motion separate a reporting frame from a calm/posed stock frame of the same
# subject; technical and print quality break ties.
WEIGHTS = {
    "relevance": .30, "headline_match": .22, "newsworthiness": .10,
    "reportage": .14, "motion": .08, "technical_quality": .08, "print_quality_at_crop": .08,
}

ANALYSIS_KEYS = (
    "relevance", "headline_match", "newsworthiness", "reportage", "posed", "motion", "emotion",
    "face_count", "largest_face_share", "gaze_direction", "motion_direction", "subject_box",
    "headline_safe_zone", "cutout_feasible", "technical_quality", "print_quality_at_crop",
    "depicts_claimed_subject", "risks",
)


def _num(row: dict[str, Any], key: str) -> float:
    try:
        return max(0.0, min(1.0, float(row.get(key) or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def editorial_score(row: dict[str, Any]) -> float:
    """Deterministic, auditable combination of the photo editor's observations."""
    total = sum(weight * _num(row, key) for key, weight in WEIGHTS.items())
    if row.get("depicts_claimed_subject") == "no":
        total -= .55
    if row.get("posed") and _num(row, "reportage") < .5:
        total -= .05
    if row.get("risks"):
        total -= min(.25, .05 * len(row["risks"]))
    return round(total, 4)


def _box(value: Any) -> Optional[list[float]]:
    if not (isinstance(value, (list, tuple)) and len(value) == 4
            and all(isinstance(item, (int, float)) for item in value)):
        return None
    ymin, xmin, ymax, xmax = [max(0.0, min(1000.0, float(item))) for item in value]
    if xmax <= xmin or ymax <= ymin:
        return None
    return [ymin, xmin, ymax, xmax]


def photo_analysis(row: dict[str, Any], *, score: float) -> dict[str, Any]:
    """Normalised observation record stored on the image and in the scene."""
    analysis = {key: row.get(key) for key in ANALYSIS_KEYS if key in row}
    box = _box(row.get("subject_box"))
    analysis["subject_box"] = [round(v / 1000, 4) for v in box] if box else None  # [ymin,xmin,ymax,xmax] 0..1
    analysis["editorial_score"] = score
    analysis["dynamic"] = round(.55 * _num(row, "motion") + .45 * _num(row, "reportage"), 4)
    analysis["reason"] = row.get("reason", "")
    return analysis


def _focal_point(row: dict[str, Any]) -> Optional[list[float]]:
    crop = _box(row.get("crop_suggestion"))
    subject = _box(row.get("subject_box"))
    if subject:
        ymin, xmin, ymax, xmax = subject
        # Faces sit in the upper part of a person box; anchor slightly high.
        y = ymin + (ymax - ymin) * (.38 if int(row.get("face_count") or 0) else .5)
        return [round((xmin + xmax) / 2000, 4), round(y / 1000, 4)]
    if crop:
        ymin, xmin, ymax, xmax = crop
        return [round((xmin + xmax) / 2000, 4), round((ymin + ymax) / 2000, 4)]
    return None


def _preview(path, max_side: int = 1280) -> dict[str, Any]:
    """Downscaled JPEG for the vision model; the original stays untouched.

    Multi-megapixel press photos made the ranking call time out, which
    silently fell back to upload order.  Judging relevance, emotion and gaze
    does not need print resolution (print quality is computed from pixels).
    """
    import io
    from PIL import Image
    with Image.open(path) as source:
        preview = source.convert("RGB")
        preview.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        preview.save(buffer, format="JPEG", quality=84)
    return {"data": buffer.getvalue(), "mime_type": "image/jpeg"}


def _lead_story_id(material: PageInputMaterial) -> Optional[str]:
    lead = max(material.stories, key=lambda story: story.importance, default=None)
    return lead.id if lead else None


def select_story_photos(material: PageInputMaterial, *, project_id: str | None = None,
                        max_candidates: int = 6, analyse_single_lead: bool = True,
                        min_lead_score: float = .52, min_lead_match: float = .45,
                        target_width_mm: Optional[float] = None,
                        min_dpi: int = 200, timeout_s: float = 60.0) -> tuple[PageInputMaterial, list[dict[str, Any]]]:
    selected = material.model_copy(deep=True)
    trace: list[dict[str, Any]] = []
    lead_id = _lead_story_id(selected)
    for story in selected.stories:
        is_lead = story.id == lead_id
        if len(story.images) < (1 if (is_lead and analyse_single_lead) else 2):
            continue
        resolved: list[tuple[int, Any, Any]] = []
        for original_index, candidate in enumerate(story.images[:max_candidates]):
            path = resolve_asset_path(candidate.url)
            if path:
                resolved.append((original_index, candidate, path))
        if not resolved or (len(resolved) < 2 and not is_lead):
            trace.append({"story_ref": story.id, "lead": is_lead, "status": "insufficient_local_candidates"})
            continue
        payload = {
            "story": {"headline": story.headline, "lead": story.lead or story.deck or ""},
            "brief": ("Wybierz zdjęcie o największej zgodności treściowej, emocjonalnej i reporterskiej "
                      "z tytułem. Preferuj uchwycony moment zdarzenia nad pozowanym portretem."),
            "target": {"width_mm": round(target_width_mm, 1) if target_width_mm else None, "min_dpi": min_dpi},
            "candidates": [
                {"index": visible_index, "title": candidate.caption or "", "description": candidate.caption or "",
                 "credit_line": candidate.credit or "", "license": "unknown",
                 "width_px": candidate.width_px, "height_px": candidate.height_px}
                for visible_index, (_, candidate, _) in enumerate(resolved)
            ],
        }
        try:
            result = run_task("photo_ranking", "photo_ranking", payload, PhotoRanking,
                              images=[_preview(path) for _, _, path in resolved], project_id=project_id,
                              timeout_s=timeout_s, max_retries=1, use_cache=True)
            rows = result.data.get("scores") or []
            valid = [row for row in rows if isinstance(row.get("index"), int)
                     and 0 <= row["index"] < len(resolved)]
            if not valid:
                trace.append({"story_ref": story.id, "lead": is_lead, "status": "no_valid_scores"})
                continue
            ranked = sorted(valid, key=editorial_score, reverse=True)
            winner = ranked[0]
            visible_index = int(winner["index"])
            original_index, image, _ = resolved[visible_index]
            score = editorial_score(winner)
            image.photo_analysis = photo_analysis(winner, score=score)
            focal = _focal_point(winner)
            if focal:
                image.focal_point = focal
            for row in ranked[1:]:
                _, other, _ = resolved[int(row["index"])]
                other.photo_analysis = photo_analysis(row, score=editorial_score(row))
            story.images = [image, *[item for index, item in enumerate(story.images) if index != original_index]]
            entry = {
                "story_ref": story.id, "lead": is_lead, "status": "selected", "image_ref": image.id,
                "original_index": original_index, "score": score,
                "headline_match": _num(winner, "headline_match"), "relevance": _num(winner, "relevance"),
                "dynamic": image.photo_analysis["dynamic"], "emotion": winner.get("emotion"),
                "gaze_direction": winner.get("gaze_direction"), "headline_safe_zone": winner.get("headline_safe_zone"),
                "cutout_feasible": bool(winner.get("cutout_feasible")),
                "reason": winner.get("reason", ""), "risks": winner.get("risks") or [],
                "focal_point": image.focal_point,
                "alternatives": [{"image_ref": resolved[int(row["index"])][1].id, "score": editorial_score(row),
                                  "reason": row.get("reason", "")} for row in ranked[1:]],
                "provider": result.provenance.get("provider"), "model": result.provenance.get("model"),
            }
            if is_lead:
                weak = (score < min_lead_score or _num(winner, "headline_match") < min_lead_match
                        or winner.get("depicts_claimed_subject") == "no")
                entry["verdict"] = "needs_other_photo" if weak else "ok"
                if weak:
                    entry["message"] = (
                        f"Potrzebne inne zdjęcie do materiału „{story.headline}”. Najlepszy kadr ma ocenę "
                        f"{score:.2f} (zgodność z tytułem {_num(winner, 'headline_match'):.2f}; wymagane "
                        f"{min_lead_score:.2f} i {min_lead_match:.2f}). {winner.get('reason', '')}".strip())
            trace.append(entry)
        except Exception as exc:
            trace.append({"story_ref": story.id, "lead": is_lead, "status": "unavailable", "reason": str(exc)[:240]})
    return selected, trace


def lead_photo_stop(trace: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Return the lead-story verdict that must stop generation, if any."""
    return next((row for row in trace if row.get("lead") and row.get("verdict") == "needs_other_photo"), None)
