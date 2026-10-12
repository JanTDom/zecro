"""Schema migrations for the edition model.

Migrations are pure functions so imports can be previewed and old projects
remain readable even when persistence is supplied by SQLite or Supabase.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .editorial_model import make_page_plan


CURRENT_SCHEMA_VERSION = 2


def migrate_editorial_model(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(dict(payload or {}))
    version = int(data.get("schema_version", 1) or 1)
    if "edition" not in data:
        # The old single-page material contract becomes a one-page issue.
        page_zone = data.get("page_zone") or "front_page"
        page = {"no": 1, "type": "front" if page_zone == "front_page" else "inner-right",
                "section": data.get("section_name"), "story_refs": [str(s.get("id")) for s in data.get("stories", []) if isinstance(s, dict)]}
        data = {"schema_version": 1, "edition": {"date": data.get("issue_date"), "pages": 4, "imposition": 4,
                 "page_plan": [page] + make_page_plan(4)[1:]}, "stories": data.get("stories", []),
                 "shorts_blocks": [], "waiting_room": []}
        version = 1
    edition = dict(data.get("edition") or {})
    pages = int(edition.get("pages") or len(edition.get("page_plan") or []) or 4)
    edition.setdefault("imposition", 4)
    if pages % int(edition["imposition"]):
        edition["imposition"] = 4
        pages = ((pages + 3) // 4) * 4
    edition["pages"] = pages
    plan = list(edition.get("page_plan") or [])
    defaults = make_page_plan(pages)
    by_no = {int(item.get("no")): item for item in plan if isinstance(item, dict) and item.get("no")}
    normalized = []
    for default in defaults:
        item = by_no.get(default.no, default.model_dump(mode="json"))
        item.setdefault("type", default.type)
        item.setdefault("ads", [])
        item.setdefault("fixed", [])
        if default.no == 1 and not item["fixed"]:
            item["fixed"] = [{"id": "masthead", "role": "masthead", "locked": True}]
        normalized.append(item)
    edition["page_plan"] = normalized
    edition["centerfold"] = edition.get("centerfold") or [pages // 2, pages // 2 + 1]
    data["edition"] = edition
    data.setdefault("shorts_blocks", [])
    data.setdefault("waiting_room", [])
    # Legacy story ranks are meaningful but use a different vocabulary.
    for story in data.get("stories", []):
        if not isinstance(story, dict):
            continue
        rank = story.get("rank")
        story["rank"] = {"lead": "A", "second": "B", "third": "B", "brief": "C", "short": "C", "box": "C", "column": "C", "teaser": "C"}.get(rank, rank or "B")
        story.setdefault("cut_policy", ["satellites", "tail", "digressions"])
        story.setdefault("elements", [])
        if story.get("source_material") is None:
            story.setdefault("source_material", None)
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    data["migration"] = {"from": version, "to": CURRENT_SCHEMA_VERSION}
    return data


def migrate_project(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Alias used by importers and API clients."""
    return migrate_editorial_model(payload)


__all__ = ["CURRENT_SCHEMA_VERSION", "migrate_editorial_model", "migrate_project"]
