"""Edition-level editorial model.

This module is the compatibility layer between the existing single-page
scene graph and a complete issue flatplan.  It intentionally contains no
renderer code: the Art Director produces geometry and budgets, the copyfit
layer proposes text changes, and the critic validates the result.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


PageType = Literal["front", "back", "inner-left", "inner-right", "spread-left", "spread-right"]
SpreadKind = Literal["centerfold", "regular"]
AdStatus = Literal["booked", "tentative"]
StoryRank = Literal["A", "B", "C"]


AD_MODULE_CATALOG: dict[str, dict[str, Any]] = {
    "full-page": {"label": "Cała strona", "w": 12, "h": 16, "positions": ["anywhere"]},
    "spread-full": {"label": "Cała rozkładówka", "w": 24, "h": 16, "positions": ["spread"]},
    "1/2-horizontal": {"label": "1/2 poziomo", "w": 12, "h": 8, "positions": ["top", "bottom"]},
    "1/2-vertical": {"label": "1/2 pionowo", "w": 6, "h": 16, "positions": ["left", "right"]},
    "1/3-horizontal": {"label": "1/3 poziomo", "w": 12, "h": 5, "positions": ["top", "middle", "bottom"]},
    "1/3-vertical": {"label": "1/3 pionowo", "w": 4, "h": 16, "positions": ["left", "right"]},
    "1/4": {"label": "1/4", "w": 6, "h": 8, "positions": ["corner", "top", "bottom"]},
    "1/8": {"label": "1/8", "w": 6, "h": 4, "positions": ["corner", "bottom"]},
    "footer-strip": {"label": "Belka dolna", "w": 12, "h": 2, "positions": ["bottom"]},
    "corner": {"label": "Narożnik", "w": 4, "h": 4, "positions": ["corner"]},
    "L-shape": {"label": "L-shape", "w": 12, "h": 16, "positions": ["left", "right"]},
    "island": {"label": "Wyspa", "w": 4, "h": 4, "positions": ["anywhere"]},
    "front-ear-left": {"label": "Ucho lewe", "w": 3, "h": 2, "positions": ["front"]},
    "front-ear-right": {"label": "Ucho prawe", "w": 3, "h": 2, "positions": ["front"]},
    "front-banner-top": {"label": "Banner nad winietą", "w": 12, "h": 2, "positions": ["front"]},
    "front-banner-bottom": {"label": "Banner pod winietą", "w": 12, "h": 2, "positions": ["front"]},
}


class FixedElement(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    role: str = "fixed"
    locked: bool = True
    frame: dict[str, float] | None = None


class Advertisement(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    format: str
    position: str | None = None
    status: AdStatus = "booked"
    advertiser: str | None = None
    advertiser_category: str | None = None
    asset: str | dict[str, Any] | None = None
    asset_ref: str | None = None
    is_advertorial: bool = False
    advertorial_label: str | None = None
    locked: bool = True
    page: int | None = Field(default=None, ge=1)

    @property
    def area_units(self) -> float:
        spec = AD_MODULE_CATALOG.get(self.format, {})
        return float(spec.get("w", 0) * spec.get("h", 0))


class EditorialPage(BaseModel):
    model_config = ConfigDict(extra="allow")
    no: int = Field(ge=1)
    type: PageType = "inner-right"
    section: str | None = None
    spread_id: str | None = None
    spread_kind: SpreadKind | None = None
    facing_full_page_ad: bool = False
    fixed: list[FixedElement | str] = Field(default_factory=list)
    ads: list[Advertisement] = Field(default_factory=list)
    story_refs: list[str] = Field(default_factory=list)
    shorts_block_ref: str | None = None
    editorial_area: dict[str, Any] | None = None
    status: Literal["empty", "in_progress", "approved"] = "empty"


class Spread(BaseModel):
    id: str
    left_page: int = Field(ge=1)
    right_page: int = Field(ge=1)
    kind: SpreadKind = "regular"
    spine_zone_mm: float = Field(default=6.0, ge=0.0)
    continuous_text_allowed: bool = False


class Edition(BaseModel):
    """Versioned issue flatplan.  ``page_plan`` is kept as the public name."""
    model_config = ConfigDict(extra="allow")
    schema_version: int = 2
    date: str = Field(default_factory=lambda: date.today().isoformat())
    pages: int = Field(default=4, ge=1)
    imposition: Literal[4, 8, 16] = 4
    centerfold: list[int] | None = None
    page_plan: list[EditorialPage] = Field(default_factory=list)
    spreads: list[Spread] = Field(default_factory=list)
    wrapper: dict[str, Any] | None = None
    insert: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize_pages(self):
        if self.pages % self.imposition:
            raise ValueError(f"objętość wydania musi być wielokrotnością imposition={self.imposition}")
        if not self.page_plan:
            self.page_plan = make_page_plan(self.pages)
        if len(self.page_plan) != self.pages:
            raise ValueError("page_plan musi zawierać dokładnie tyle stron, ile ma wydanie")
        if self.centerfold is None:
            self.centerfold = [self.pages // 2, self.pages // 2 + 1]
        if not self.spreads:
            left, right = self.centerfold
            self.spreads = [Spread(id="centerfold", left_page=left, right_page=right, kind="centerfold")]
        return self


class ShortItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    rank: int = Field(default=1, ge=1)
    headline: str = ""
    body: str = ""
    photo: str | None = None
    source: str | None = None


class ShortsBlock(BaseModel):
    page: int = Field(ge=1)
    min_items: int = Field(default=0, ge=0)
    max_items: int = Field(default=12, ge=1)
    item_format: list[int] = Field(default_factory=lambda: [250, 400, 600])
    header: str = "W skrócie"
    style: str = "default"
    items: list[ShortItem] = Field(default_factory=list)


class WaitingRoomItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    rank: StoryRank = "C"
    headline: str = ""
    body: str = ""
    source: str | None = None
    reason: str | None = None


class StoryElement(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    role: Literal["kicker", "headline", "deck", "lead", "body", "photo", "caption", "pullquote", "infobox", "factbox", "teaser", "byline"]
    source: Literal["ai", "paste", "import", "editor", "extract"] = "editor"
    text: str = ""
    lock: bool = False
    length: dict[str, int] = Field(default_factory=dict)
    optional: bool = False
    status: Literal["draft", "fitted", "approved", "protected"] = "draft"
    verbatim: bool = False
    source_refs: list[str] = Field(default_factory=list)


class StoryPackage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    page: int | None = Field(default=None, ge=1)
    rank: StoryRank = "B"
    topic_tags: list[str] = Field(default_factory=list)
    cut_policy: list[str] = Field(default_factory=lambda: ["satellites", "tail", "digressions"])
    source_material: str | None = None
    elements: list[StoryElement] = Field(default_factory=list)
    protected: bool = False


class EditorialModel(BaseModel):
    schema_version: int = 2
    edition: Edition
    stories: list[StoryPackage] = Field(default_factory=list)
    shorts_blocks: list[ShortsBlock] = Field(default_factory=list)
    waiting_room: list[WaitingRoomItem] = Field(default_factory=list)


def _as_page(value: Any) -> EditorialPage:
    return value if isinstance(value, EditorialPage) else EditorialPage.model_validate(value)


def make_page_plan(pages: int) -> list[EditorialPage]:
    result: list[EditorialPage] = []
    center = [pages // 2, pages // 2 + 1]
    for no in range(1, pages + 1):
        if no == 1:
            kind: PageType = "front"
        elif no == pages:
            kind = "back"
        elif no in center:
            kind = "spread-left" if no == center[0] else "spread-right"
        else:
            kind = "inner-left" if no % 2 == 0 else "inner-right"
        fixed = [FixedElement(id="masthead", role="masthead")] if no == 1 else []
        result.append(EditorialPage(no=no, type=kind, fixed=fixed,
                                    spread_id="centerfold" if no in center else None,
                                    spread_kind="centerfold" if no in center else None))
    return result


def build_edition(pages: int, *, issue_date: str | None = None, imposition: int = 4,
                  page_plan: list[Mapping[str, Any]] | None = None) -> Edition:
    if imposition not in (4, 8, 16):
        raise ValueError("imposition musi wynosić 4, 8 albo 16")
    payload = {"pages": pages, "imposition": imposition, "date": issue_date or date.today().isoformat()}
    if page_plan is not None:
        payload["page_plan"] = page_plan
    return Edition.model_validate(payload)


def dna_value(dna: Any, name: str, default: Any) -> Any:
    if dna is None:
        return default
    value = getattr(dna, name, default)
    return value if value is not None else default


def ad_catalog(dna: Any = None) -> dict[str, dict[str, Any]]:
    custom = dna_value(dna, "ad_modules", {})
    result = {**AD_MODULE_CATALOG}
    if isinstance(custom, list):
        custom = {x.get("id"): x for x in custom if isinstance(x, dict) and x.get("id")}
    for key, spec in (custom or {}).items():
        result[str(key)] = {**result.get(str(key), {}), **dict(spec)}
    return result


def page_area_ratio(page: EditorialPage, dna: Any = None) -> float:
    catalog = ad_catalog(dna)
    total = 12 * 16
    reserved = sum(catalog.get(ad.format, {}).get("w", 0) * catalog.get(ad.format, {}).get("h", 0) for ad in page.ads)
    reserved += sum(1 for _ in page.fixed) * 12  # fixed items reserve a safe band
    return max(0.0, min(1.0, 1 - reserved / total))


def compute_editorial_area(page: EditorialPage | Mapping[str, Any], dna: Any = None) -> dict[str, Any]:
    page = _as_page(page)
    ratio = page_area_ratio(page, dna)
    simplified_threshold = float(dna_value(dna, "ad_area_simplified_threshold", 0.5))
    return {"kind": "polygon" if any(ad.format == "L-shape" for ad in page.ads) else "rect",
            "ratio": round(ratio, 4), "reserved_ratio": round(1 - ratio, 4),
            "simplified": (1 - ratio) >= simplified_threshold,
            "ads": [ad.id for ad in page.ads], "fixed": [getattr(item, "id", item) for item in page.fixed]}


def suggest_capacity(editorial_area: Mapping[str, Any] | float, page_type: str = "inner-right", dna: Any = None) -> dict[str, int]:
    ratio = float(editorial_area.get("ratio", 1.0) if isinstance(editorial_area, Mapping) else editorial_area)
    base = {"A": 1, "B": 3, "C": 6}
    if page_type == "front":
        base = {"A": 1, "B": 2, "C": 3}
    if page_type.startswith("spread"):
        base = {"A": 1, "B": 3, "C": 6}
    if ratio < 0.5:
        base = {key: (value if key == "A" else max(0, value - (1 if ratio < 0.35 else 0))) for key, value in base.items()}
    if ratio < 0.25:
        base["C"] = 0
    return base


def _rect(ad: Advertisement, page_no: int, dna: Any = None) -> tuple[float, float, float, float]:
    spec = ad_catalog(dna).get(ad.format, {})
    w, h = float(spec.get("w", 0)), float(spec.get("h", 0))
    if ad.format == "front-ear-right":
        return 12.0 - w, 0.0, w, h
    if ad.format == "front-ear-left":
        return 0.0, 0.0, w, h
    if ad.format == "front-banner-bottom":
        return 0.0, 2.0, w, h
    pos = ad.position or "anywhere"
    x = 0.0 if pos in {"left", "top", "bottom", "anywhere", "front"} else 12.0 - w
    y = 0.0 if pos in {"top", "left", "anywhere", "front"} else 16.0 - h
    if pos == "middle": y = 5.5
    return x, y, w, h


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0]) and min(a[1] + a[3], b[1] + b[3]) > max(a[1], b[1])


def validate_editorial_model(model: EditorialModel | Mapping[str, Any], dna: Any = None) -> list[str]:
    model = model if isinstance(model, EditorialModel) else EditorialModel.model_validate(model)
    errors: list[str] = []
    catalog = ad_catalog(dna)
    competitor_categories = dna_value(dna, "competitive_ad_categories", {}) or {}
    collision_matrix = dna_value(dna, "context_collision_matrix", {}) or {}
    for page in model.edition.page_plan:
        seen: list[Advertisement] = []
        for ad in page.ads:
            if ad.format not in catalog:
                errors.append(f"{page.no}:{ad.id}: nieznany format reklamy {ad.format}")
            if ad.is_advertorial and not ad.advertorial_label:
                errors.append(f"{page.no}:{ad.id}: advertorial wymaga etykiety")
            if ad.is_advertorial and dna_value(dna, "advertorial_style", "") == "editorial":
                errors.append(f"{page.no}:{ad.id}: advertorial nie może używać stylu redakcyjnego")
            box = _rect(ad, page.no, dna)
            for other in seen:
                if _overlap(box, _rect(other, page.no, dna)):
                    errors.append(f"{page.no}: kolizja reklam {ad.id}/{other.id}")
            seen.append(ad)
        categories = [ad.advertiser_category for ad in page.ads if ad.advertiser_category]
        for category in categories:
            rivals = competitor_categories.get(category, []) if isinstance(competitor_categories, dict) else []
            if any(rival in categories for rival in rivals):
                errors.append(f"{page.no}: konkurencyjne kategorie reklam")
        tags = {tag for story in model.stories if story.page == page.no for tag in story.topic_tags}
        for ad in page.ads:
            blocked = collision_matrix.get(ad.advertiser_category or "", []) if isinstance(collision_matrix, dict) else []
            hit = sorted(set(blocked) & tags)
            if hit:
                errors.append(f"{page.no}: kolizja kontekstowa {ad.id}: {', '.join(hit)}")
    errors.extend(validate_spine_constraints(model))
    for page in model.edition.page_plan:
        if page.type == "front" and not any(getattr(item, "role", item) == "masthead" for item in page.fixed):
            # A missing masthead is a warning in legacy plans, a hard issue only
            # when the caller explicitly supplied fixed elements.
            if page.fixed:
                errors.append("1: winieta front musi być elementem fixed")
    return errors


def validate_spine_constraints(model: EditorialModel | Mapping[str, Any]) -> list[str]:
    """Check the no-continuous-text-through-spine rule for regular spreads.

    Imported clients may provide ``spine_crossing`` on an element when the
    geometry is stored outside this editorial contract; the flag is enough to
    run the same gate before the full scene graph exists.
    """
    model = model if isinstance(model, EditorialModel) else EditorialModel.model_validate(model)
    errors: list[str] = []
    spread_pages = {page.spread_id: page for page in model.edition.page_plan if page.spread_id}
    for spread_id in spread_pages:
        pages = [page for page in model.edition.page_plan if page.spread_id == spread_id]
        kind = next((page.spread_kind for page in pages if page.spread_kind), "regular")
        if kind != "regular":
            continue
        refs = {ref for page in pages for ref in page.story_refs}
        for story in model.stories:
            if story.id not in refs and story.page not in {page.no for page in pages}:
                continue
            for element in story.elements:
                crossing = bool(getattr(element, "spine_crossing", False))
                frame = getattr(element, "frame", None) or {}
                crossing = crossing or bool(getattr(element, "crosses_spine", False))
                if isinstance(frame, dict) and frame.get("x") is not None and frame.get("w") is not None:
                    crossing = crossing or float(frame["x"]) < 0 < float(frame["x"]) + float(frame["w"])
                if crossing and element.role in {"body", "lead", "deck", "caption", "byline", "pullquote"}:
                    errors.append(f"{spread_id}: tekst {element.id} przechodzi przez grzbiet zwykłej rozkładówki")
    return errors


_NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:[\.,]\d+)?%?(?![\w])")
_PROPER = re.compile(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]{2,}(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]{2,})*")


def validate_source_bound_text(output: str, source: str) -> dict[str, Any]:
    """Reject new numbers/dates/names before a copyfit proposal is approved."""
    source = source or ""
    numbers = sorted(set(_NUMBER.findall(output)) - set(_NUMBER.findall(source)))
    names = sorted(set(_PROPER.findall(output)) - set(_PROPER.findall(source)))
    unsupported = numbers + names
    return {"status": "pass" if not unsupported else "fail", "unsupported": unsupported,
            "flags": [{"kind": "entity", "value": value} for value in unsupported]}


def copyfit_delta(text: str, budget: int) -> int:
    return len(text or "") - max(0, int(budget))


def run_copyfit_ladder(text: str, budget: int, *, lock: bool = False,
                       cut_policy: Iterable[str] = ("satellites", "tail", "digressions"),
                       satellites: list[StoryElement] | None = None,
                       source_material: str | None = None) -> dict[str, Any]:
    original = text or ""
    delta = copyfit_delta(original, budget)
    result = {"text": original, "delta": delta, "status": "fit" if delta == 0 else ("underfill" if delta < 0 else "overflow"),
              "steps": [], "requires_editor": False, "needs_source": False}
    if delta < 0:
        if source_material:
            result["steps"].append("expand_from_source_only")
        else:
            result["needs_source"] = True
            result["requires_editor"] = True
            result["message"] = f"brakuje {-delta} zn., potrzebny materiał źródłowy"
        return result
    if delta <= 0 or lock:
        if lock and delta > 0:
            result["requires_editor"] = True
        return result
    # Source bound reduction: preserve a complete word and never invent copy.
    shortened = original[:budget].rsplit(" ", 1)[0].rstrip(" ,;:") if budget else ""
    if shortened and len(shortened) < len(original):
        result["text"] = shortened
        result["delta"] = copyfit_delta(shortened, budget)
        result["status"] = "fit" if result["delta"] <= 0 else "overflow"
        result["steps"].append("source_bound_shortcut")
    if result["delta"] > 0 and satellites:
        result["steps"].append("remove_optional_satellites")
    if result["delta"] > 0:
        result["requires_editor"] = True
    return result


def tentative_variants(model: EditorialModel | Mapping[str, Any], page_no: int) -> list[EditorialModel]:
    """Return the two reviewable plans for a page containing tentative ads."""
    model = model if isinstance(model, EditorialModel) else EditorialModel.model_validate(model)
    page = next((item for item in model.edition.page_plan if item.no == page_no), None)
    if page is None:
        raise ValueError(f"nie znaleziono strony {page_no}")
    tentative = [ad for ad in page.ads if ad.status == "tentative"]
    if not tentative:
        return [model]
    variants: list[EditorialModel] = []
    for include in (True, False):
        clone = model.model_copy(deep=True)
        target = next(item for item in clone.edition.page_plan if item.no == page_no)
        if not include:
            target.ads = [ad for ad in target.ads if ad.status != "tentative"]
        target.editorial_area = compute_editorial_area(target)
        variants.append(clone)
    return variants


def protect_approved(story: StoryPackage | Mapping[str, Any]) -> StoryPackage:
    story = story if isinstance(story, StoryPackage) else StoryPackage.model_validate(story)
    clone = story.model_copy(deep=True)
    clone.protected = True
    clone.elements = [element.model_copy(update={"status": "protected" if element.status == "approved" else element.status}) for element in clone.elements]
    return clone


def import_ads_csv(payload: str, *, default_status: AdStatus = "booked") -> list[Advertisement]:
    reader = csv.DictReader(io.StringIO(payload))
    required = {"id", "format"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("CSV reklam musi zawierać kolumny id i format")
    result = []
    for row in reader:
        result.append(Advertisement(id=row["id"], format=row["format"], position=row.get("position") or None,
                                    status=row.get("status") or default_status, advertiser=row.get("advertiser") or None,
                                    advertiser_category=row.get("advertiser_category") or None,
                                    asset=row.get("asset") or None, is_advertorial=str(row.get("is_advertorial", "")).lower() in {"1", "true", "yes"}))
    return result


def late_ad_change(page: EditorialPage | Mapping[str, Any], *, removed: Iterable[str] = (), added: Iterable[Advertisement] = ()) -> dict[str, Any]:
    page = _as_page(page)
    removed = set(removed)
    remaining = [ad for ad in page.ads if ad.id not in removed]
    freed = sum(ad.area_units for ad in page.ads if ad.id in removed)
    added_list = list(added)
    occupied = sum(ad.area_units for ad in remaining + added_list)
    return {"removed": sorted(removed), "freed_units": freed, "added": [ad.id for ad in added_list],
            "occupied_units": occupied, "strategy": "shorts_first" if freed else "local_reflow",
            "protected_untouched": True, "full_rebuild": bool(freed and freed > 12 * 16 * 0.25)}


def apply_ads_to_scene(scene_graph: Any, page: EditorialPage | Mapping[str, Any], dna: Any = None) -> Any:
    """Materialize locked ad modules into the shared Scene Graph.

    The generator still owns editorial geometry.  This adapter adds reserved
    advertising frames after generation and marks them protected so all
    renderers and the critic see the same locked objects.
    """
    from ..models.schemas import Element, ElementStyle, Frame
    page = _as_page(page)
    existing = {element.id for element in scene_graph.elements}
    page_w, page_h = float(scene_graph.page.trim[0]), float(scene_graph.page.trim[1])
    labels = dict(scene_graph.metadata.get("advertorial_labels") or {})
    advertorial_ids = list(scene_graph.metadata.get("advertorial_ids") or [])
    for ad in page.ads:
        element_id = f"ad-{ad.id}"
        if element_id in existing:
            continue
        x, y, w, h = _rect(ad, page.no, dna)
        frame = Frame(x=x / 12 * page_w, y=y / 16 * page_h, w=w / 12 * page_w, h=h / 16 * page_h)
        text = ad.advertorial_label or ("REKLAMA" if not ad.asset else "")
        asset_ref = ad.asset_ref or (ad.asset if isinstance(ad.asset, str) else None)
        scene_graph.elements.append(Element(id=element_id, role="band", text_content=text, frame=frame, z=100,
                                             style=ElementStyle(font_size_pt=7, font_weight="bold", color="#111", bg_color="#f2ede4"),
                                             locked=True, approval_status="protected", constraints=["advertisement_locked", "no_overlap"],
                                             content_ref=asset_ref))
        if ad.is_advertorial:
            advertorial_ids.append(element_id)
            if ad.advertorial_label:
                labels[element_id] = ad.advertorial_label
    scene_graph.metadata["advertorial_ids"] = advertorial_ids
    scene_graph.metadata["advertorial_labels"] = labels
    scene_graph.metadata["locked_ad_ids"] = [f"ad-{ad.id}" for ad in page.ads]
    return scene_graph


__all__ = ["AD_MODULE_CATALOG", "Advertisement", "Edition", "EditorialModel", "EditorialPage", "FixedElement", "ShortItem", "ShortsBlock", "Spread", "StoryElement", "StoryPackage", "WaitingRoomItem", "ad_catalog", "apply_ads_to_scene", "build_edition", "compute_editorial_area", "copyfit_delta", "import_ads_csv", "late_ad_change", "make_page_plan", "page_area_ratio", "protect_approved", "run_copyfit_ladder", "suggest_capacity", "tentative_variants", "validate_editorial_model", "validate_source_bound_text", "validate_spine_constraints"]
