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
    Advertisement, EditorialModel, EditorialPage, build_edition, compute_editorial_area,
    import_ads_csv, late_ad_change, run_copyfit_ladder, suggest_capacity,
    tentative_variants, validate_editorial_model, validate_source_bound_text,
)

router = APIRouter(prefix="/editorial-model", tags=["editorial-model"])


class EditionRequest(BaseModel):
    pages: int = Field(default=4, ge=1)
    issue_date: str | None = None
    imposition: int = Field(default=4, ge=4)


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
