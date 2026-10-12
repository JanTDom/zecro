"""Edition flatplan API.

The routes are deliberately stateless: callers may persist the returned
version through the existing issue/editorial object store.  This keeps old
single-page projects working while exposing a stable edition contract.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..engine.editorial_migration import migrate_editorial_model
from ..engine.editorial_model import (
    Advertisement, EditorialModel, EditorialPage, ShortItem, ShortsBlock, WaitingRoomItem,
    build_edition, compute_editorial_area,
    import_ads_csv, late_ad_change, run_copyfit_ladder, suggest_capacity,
    tentative_variants, validate_editorial_model, validate_source_bound_text,
)
from ..models.database import db

router = APIRouter(prefix="/editorial-model", tags=["editorial-model"])


class EditionRequest(BaseModel):
    pages: int = Field(default=4, ge=1)
    issue_date: str | None = None
    imposition: int = Field(default=4, ge=4)


class PersistedEditionRequest(BaseModel):
    edition: dict[str, Any] | None = None
    pages: int = Field(default=16, ge=1)
    imposition: int = Field(default=8, ge=4)
    issue_date: str | None = None


def _project_or_404(project_id: str) -> None:
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")


def _stored_edition(project_id: str) -> dict[str, Any] | None:
    rows = db.list_editorial_objects("editorial_edition", project_id=project_id)
    if not rows:
        return None
    row = rows[0]
    return row.get("model", row)


def _stored_version(project_id: str) -> int:
    rows = db.list_editorial_objects("editorial_edition", project_id=project_id)
    return int((rows[0] if rows else {}).get("version", 0) or 0)


def _flat_edition(model: EditorialModel) -> dict[str, Any]:
    result = model.edition.model_dump(mode="json")
    result["shorts_blocks"] = [block.model_dump(mode="json") for block in model.shorts_blocks]
    result["waiting_room"] = [item.model_dump(mode="json") for item in model.waiting_room]
    return result


@router.get("/ad-modules")
def ad_modules():
    from ..engine.editorial_model import AD_MODULE_CATALOG
    return {"modules": AD_MODULE_CATALOG}


@router.post("/editions")
def create_edition(payload: EditionRequest):
    try:
        return build_edition(payload.pages, issue_date=payload.issue_date, imposition=payload.imposition).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/projects/{project_id}/edition")
def get_project_edition(project_id: str):
    _project_or_404(project_id)
    edition = _stored_edition(project_id)
    if edition is None:
        edition = build_edition(16, imposition=8).model_dump(mode="json")
    if "edition" in edition:
        result = dict(edition["edition"])
        result["shorts_blocks"] = edition.get("shorts_blocks", [])
        result["waiting_room"] = edition.get("waiting_room", [])
        return result
    return edition


@router.post("/projects/{project_id}/edition")
def save_project_edition(project_id: str, payload: PersistedEditionRequest):
    _project_or_404(project_id)
    try:
        edition = (build_edition(payload.pages, issue_date=payload.issue_date, imposition=payload.imposition)
                   if payload.edition is None else build_edition(
                       int(payload.edition.get("pages", payload.pages)),
                       issue_date=payload.edition.get("date") or payload.issue_date,
                       imposition=int(payload.edition.get("imposition", payload.imposition)),
                       page_plan=payload.edition.get("page_plan")))
        model = {"schema_version": 2, "edition": edition.model_dump(mode="json"), "stories": [],
                 "shorts_blocks": (payload.edition or {}).get("shorts_blocks", []),
                 "waiting_room": (payload.edition or {}).get("waiting_room", [])}
        errors = validate_editorial_model(model)
        if errors:
            raise HTTPException(status_code=422, detail={"status": "FAIL", "errors": errors})
        saved = {"id": f"edition:{project_id}", "version": _stored_version(project_id) + 1, "project_id": project_id, "model": model}
        db.save_editorial_object("editorial_edition", saved, project_id=project_id, reason="edition_saved")
        return _flat_edition(EditorialModel.model_validate(model))
    except HTTPException:
        raise
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class EditionAdsRequest(BaseModel):
    page_no: int = Field(ge=1)
    ads: list[dict[str, Any]] = Field(default_factory=list)
    csv: str | None = None
    removed: list[str] = Field(default_factory=list)


@router.post("/projects/{project_id}/edition/ads")
def update_project_ads(project_id: str, payload: EditionAdsRequest):
    _project_or_404(project_id)
    stored = _stored_edition(project_id)
    model = EditorialModel.model_validate(stored or {"edition": build_edition(16, imposition=8).model_dump(mode="json")})
    page = next((item for item in model.edition.page_plan if item.no == payload.page_no), None)
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    try:
        incoming = import_ads_csv(payload.csv) if payload.csv else [Advertisement.model_validate(item) for item in payload.ads]
        before_change = page.model_copy(deep=True)
        page.ads = [ad for ad in page.ads if ad.id not in set(payload.removed)]
        page.ads.extend(incoming)
        change = late_ad_change(before_change, removed=payload.removed, added=incoming)
        page.editorial_area = compute_editorial_area(page)
        errors = validate_editorial_model(model)
        if errors:
            raise HTTPException(status_code=422, detail={"status": "FAIL", "errors": errors})
        if change["freed_units"]:
            block = next((item for item in model.shorts_blocks if item.page == page.no), None)
            if block is None:
                block = ShortsBlock(page=page.no)
                model.shorts_blocks.append(block)
            # One short consumes roughly one twelfth of the page grid. Move
            # existing source-backed waiting-room copy before requesting more.
            slots = min(int(change["freed_units"] // 12), block.max_items - len(block.items))
            moved = []
            for item in list(model.waiting_room):
                if len(moved) >= slots:
                    break
                block.items.append(ShortItem(id=item.id, rank={"A": 1, "B": 2, "C": 3}[item.rank],
                                             headline=item.headline, body=item.body, source=item.source))
                model.waiting_room.remove(item)
                moved.append(item.id)
            change["shorts_moved"] = moved
            change["unfilled_short_slots"] = max(0, slots - len(moved))
        saved = {"id": f"edition:{project_id}", "version": _stored_version(project_id) + 1, "project_id": project_id, "model": model.model_dump(mode="json")}
        db.save_editorial_object("editorial_edition", saved, project_id=project_id, reason="ads_updated")
        return {"edition": _flat_edition(model), "model": model.model_dump(mode="json"),
                "change": change}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ShortsRequest(BaseModel):
    page_no: int = Field(ge=1)
    item: dict[str, Any] | None = None
    waiting: bool = False


@router.post("/projects/{project_id}/edition/shorts")
def add_short_or_waiting(project_id: str, payload: ShortsRequest):
    _project_or_404(project_id)
    stored = _stored_edition(project_id)
    model = EditorialModel.model_validate(stored or {"edition": build_edition(16, imposition=8).model_dump(mode="json")})
    if not payload.item:
        raise HTTPException(status_code=422, detail="item jest wymagany")
    try:
        if payload.waiting:
            model.waiting_room.append(WaitingRoomItem.model_validate(payload.item))
        else:
            block = next((item for item in model.shorts_blocks if item.page == payload.page_no), None)
            if block is None:
                block = ShortsBlock(page=payload.page_no)
                model.shorts_blocks.append(block)
            block.items.append(ShortItem.model_validate(payload.item))
        saved = {"id": f"edition:{project_id}", "version": _stored_version(project_id) + 1, "project_id": project_id, "model": model.model_dump(mode="json")}
        db.save_editorial_object("editorial_edition", saved, project_id=project_id, reason="short_added")
        return {"edition": _flat_edition(model), "model": model.model_dump(mode="json")}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/projects/{project_id}/edition/tentative-variants/{page_no}")
def project_tentative_variants(project_id: str, page_no: int):
    _project_or_404(project_id)
    stored = _stored_edition(project_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="edition not found")
    from ..engine.editorial_model import tentative_variants
    try:
        variants = tentative_variants(stored, page_no)
        return {"variants": [variant.model_dump(mode="json") for variant in variants]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/editions/migrate")
def migrate_edition(payload: dict[str, Any]):
    try:
        return migrate_editorial_model(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/editions/validate")
def validate_edition(payload: dict[str, Any]):
    try:
        model = EditorialModel.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    errors = validate_editorial_model(model)
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "edition": model.model_dump(mode="json")}


class AreaRequest(BaseModel):
    page: dict[str, Any]


@router.post("/editorial-area")
def editorial_area(payload: AreaRequest):
    return compute_editorial_area(EditorialPage.model_validate(payload.page))


class CapacityRequest(BaseModel):
    editorial_area: dict[str, Any] | float = 1.0
    page_type: str = "inner-right"


@router.post("/capacity")
def capacity(payload: CapacityRequest):
    return suggest_capacity(payload.editorial_area, payload.page_type)


class AdsCSVRequest(BaseModel):
    csv: str


@router.post("/ads/import-csv")
def ads_import(payload: AdsCSVRequest):
    try:
        ads = import_ads_csv(payload.csv)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"items": [ad.model_dump(mode="json") for ad in ads], "count": len(ads)}


class SourceGuardRequest(BaseModel):
    output: str
    source: str = ""


@router.post("/copyfit/source-guard")
def source_guard(payload: SourceGuardRequest):
    return validate_source_bound_text(payload.output, payload.source)


class CopyfitRequest(BaseModel):
    text: str
    budget: int = Field(ge=0)
    lock: bool = False


@router.post("/copyfit")
def copyfit(payload: CopyfitRequest):
    return run_copyfit_ladder(payload.text, payload.budget, lock=payload.lock)


class LateAdRequest(BaseModel):
    page: dict[str, Any]
    removed: list[str] = Field(default_factory=list)
    added: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/ads/late-change")
def late_change(payload: LateAdRequest):
    try:
        added = [Advertisement.model_validate(item) for item in payload.added]
        return late_ad_change(EditorialPage.model_validate(payload.page), removed=payload.removed, added=added)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/ads/tentative-variants/{page_no}")
def tentative_ad_variants(page_no: int, payload: dict[str, Any]):
    try:
        variants = tentative_variants(payload, page_no)
        return {"variants": [variant.model_dump(mode="json") for variant in variants]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


__all__ = ["router"]
