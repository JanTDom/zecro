from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from ..engine.osint import DEFAULT_SOURCES, scan


router = APIRouter(prefix="/osint", tags=["osint"])


class OSINTSource(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    kind: Literal["publisher", "competitor", "institution", "wire"] = "competitor"
    region: str = Field(default="Polska", max_length=80)


class OSINTScanRequest(BaseModel):
    sources: list[OSINTSource] = Field(default_factory=lambda: [OSINTSource(**source) for source in DEFAULT_SOURCES], max_length=12)
    publisher_source_id: str | None = Field(default=None, max_length=80)


@router.get("/sources")
def list_default_sources():
    return {"sources": DEFAULT_SOURCES, "note": "Źródła są publiczne i konfigurowalne. Zecro nie ma dostępu do GA4 ani CMS-a."}


@router.post("/scan")
def scan_public_sources(payload: OSINTScanRequest):
    if not payload.sources:
        raise HTTPException(status_code=422, detail="Dodaj co najmniej jedno publiczne źródło.")
    if payload.publisher_source_id and payload.publisher_source_id not in {source.id for source in payload.sources}:
        raise HTTPException(status_code=422, detail="Źródło własne nie znajduje się na liście źródeł.")
    result = scan([source.model_dump(mode="json") for source in payload.sources], payload.publisher_source_id)
    return result
