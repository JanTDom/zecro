"""Corpus index and global TitleDNA archetype endpoints.

The project corpus is read-only reference material.  Indexing is explicit for
the expensive filesystem operation, while the five archetype presets are
available immediately to the editor and API clients.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..config import settings
from ..engine.corpus_indexer import (
    ARCHETYPE_IDS,
    ARCHETYPE_ALIASES,
    CorpusIndexer,
    aggregate_archetype_features,
    create_archetype_dnas,
    get_archetype_profiles,
)
from ..models.database import db
from ..models.schemas import TitleDNA


router = APIRouter(tags=["corpus", "archetypes"])


class CorpusIndexRequest(BaseModel):
    root: Optional[str] = None
    persist_path: Optional[str] = None


def _default_corpus_root() -> Path:
    # config.PROJECT_ROOT is the repository root in the local app.
    app_dir = Path(getattr(settings, "base_dir", Path.cwd()))
    for candidate in (app_dir / "corpus", app_dir.parent / "corpus", app_dir.parent.parent / "corpus"):
        if candidate.is_dir():
            return candidate
    return app_dir.parent / "corpus"


def _resolve_root(value: Optional[str]) -> Path:
    root = Path(value).expanduser() if value else _default_corpus_root()
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Corpus directory '{root}' does not exist or is not a directory.")
    return root


def _saved_global_index(*, include_pages: bool = False) -> Optional[Dict[str, Any]]:
    """Read SQLite first; lazily seed it from the immutable local snapshot."""
    saved = db.get_global_corpus_index(include_pages=include_pages)
    if saved:
        return saved
    cached = _default_corpus_root() / "FEATURE_INDEX.json"
    if not cached.exists():
        return None
    try:
        index = json.loads(cached.read_text(encoding="utf-8"))
        db.save_global_corpus_index(index)
        return db.get_global_corpus_index(include_pages=include_pages)
    except (OSError, ValueError, TypeError):
        return None


@router.get("/archetypes")
def list_archetypes() -> List[Dict[str, Any]]:
    """Return the five editable base TitleDNA profiles and their aliases."""
    saved_index = _saved_global_index(include_pages=False)
    saved = saved_index.get("archetypes", {}) if saved_index else {}
    if saved:
        output = []
        for key in ARCHETYPE_IDS:
            profile = saved.get(key)
            if not profile:
                continue
            dna = profile.get("title_dna", profile.get("dna", {}))
            output.append({"id": key, "name": profile.get("name", dna.get("name", key)), "dna": dna, "stats": profile.get("stats", {}), "mean_vector": profile.get("mean_vector", []), "aliases": [alias for alias, target in ARCHETYPE_ALIASES.items() if target == key]})
        if output:
            return output
    return get_archetype_profiles()


@router.get("/archetypes/{archetype_id}")
def get_archetype(archetype_id: str) -> Dict[str, Any]:
    profiles = list_archetypes()
    normalized = archetype_id.strip().lower().replace(" ", "_")
    for profile in profiles:
        if normalized == profile["id"] or normalized in profile.get("aliases", []):
            return profile
    raise HTTPException(status_code=404, detail=f"Unknown TitleDNA archetype '{archetype_id}'.")


@router.post("/projects/{project_id}/dna/archetype/{archetype_id}", response_model=TitleDNA)
def apply_archetype(project_id: str, archetype_id: str) -> TitleDNA:
    """Apply an archetype as the project's editable TitleDNA base profile."""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    normalized = archetype_id.strip().lower().replace(" ", "_")
    canonical = ARCHETYPE_ALIASES.get(normalized, normalized)
    if canonical not in ARCHETYPE_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown TitleDNA archetype '{archetype_id}'.")
    saved_index = _saved_global_index(include_pages=False)
    saved = saved_index.get("archetypes", {}) if saved_index else {}
    profile = saved.get(canonical, {}) if saved else {}
    dna_data = profile.get("title_dna", profile.get("dna")) if isinstance(profile, dict) else None
    dna = TitleDNA(**dna_data) if isinstance(dna_data, dict) else create_archetype_dnas()[canonical]
    dna.archetype = canonical
    if isinstance(profile, dict) and profile.get("stats"):
        dna.corpus_stats = dict(profile["stats"])
    dna.name = f"{project.name} — {dna.name}"
    return db.save_title_dna(project_id, dna)


@router.post("/corpus/index", status_code=status.HTTP_201_CREATED)
def rebuild_corpus_index(body: CorpusIndexRequest = CorpusIndexRequest()) -> Dict[str, Any]:
    """Scan the canonical corpus and return page features plus five aggregates."""
    root = _resolve_root(body.root)
    persist = Path(body.persist_path).expanduser().resolve() if body.persist_path else root / "FEATURE_INDEX.json"
    # A checked-in FEATURE_INDEX is already a measured, immutable snapshot of
    # the 1041-page corpus.  Reuse it for the default root so API startup stays
    # fast; callers can point at another root or persist path to force a scan.
    cached = root / "FEATURE_INDEX.json"
    if not body.persist_path and cached.exists():
        try:
            index = json.loads(cached.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            index = CorpusIndexer(root).build(persist_path=persist)
    else:
        index = CorpusIndexer(root).build(persist_path=persist)
    db.save_global_corpus_index(index)
    return {key: value for key, value in index.items() if key != "pages"} | {"pages_indexed": len(index.get("pages", [])), "indexed": True}


@router.get("/corpus/index")
def corpus_index_summary(
    root: Optional[str] = Query(default=None),
    rebuild: bool = Query(default=False),
) -> Dict[str, Any]:
    """Return a lightweight summary; pass ``rebuild=true`` to extract pages."""
    saved = db.get_global_corpus_index(_resolve_root(root) if root else None, include_pages=False)
    if saved and not rebuild:
        return saved
    if not rebuild:
        # The compact FEATURE_INDEX snapshot is bundled with the API deployment.
        # Seed SQLite from it so the production generator can use all measured
        # corpus vectors without shipping the multi-gigabyte raw media archive.
        if not root:
            cached_index = _saved_global_index(include_pages=False)
            if cached_index:
                return cached_index
        root_path = _resolve_root(root)
        catalog_path = root_path / "INDEX.json"
        catalog: Dict[str, Any] = {}
        if catalog_path.exists():
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                catalog = {}
        category_counts: Dict[str, int] = {}
        front = inside = back = title_count = 0
        for category, data in (catalog.get("categories", {}) or {}).items():
            titles = data.get("titles", []) if isinstance(data, dict) else []
            category_counts[category] = sum(int((title.get("counts", {}) or {}).get("total", 0)) for title in titles)
            title_count += len(titles)
            front += sum(int((title.get("counts", {}) or {}).get("front", 0)) for title in titles)
            inside += sum(int((title.get("counts", {}) or {}).get("spreads", 0)) for title in titles)
            back += sum(int((title.get("counts", {}) or {}).get("back", 0)) for title in titles)
        return {
            "version": "2.0.0",
            "page_count": front + inside + back,
            "title_count": title_count,
            "categories": category_counts,
            "zones": {"front": front, "inside": inside, "back": back},
            "indexed": False,
            "message": "Catalog summary loaded. Pass rebuild=true or POST to extract image features.",
            "archetypes": {profile["id"]: {"name": profile["name"], "dna": profile["dna"]} for profile in get_archetype_profiles()},
        }
    root_path = _resolve_root(root)
    index = CorpusIndexer(root_path).build(persist_path=root_path / "FEATURE_INDEX.json")
    db.save_global_corpus_index(index)
    return {key: value for key, value in index.items() if key != "pages"} | {"pages_indexed": len(index.get("pages", [])), "indexed": True}


@router.get("/projects/{project_id}/corpus/archetypes")
def project_archetypes(project_id: str) -> Dict[str, Any]:
    """Aggregate extracted upload features for one project without rescanning files."""
    if not db.get_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    pages = [page.extracted_features for page in db.list_corpus_pages(project_id) if page.extracted_features]
    profiles = aggregate_archetype_features(pages)
    # A project with no uploads still receives the five editable profiles.
    if not pages:
        profiles = {profile["id"]: profile for profile in get_archetype_profiles()}
    return {"project_id": project_id, "page_count": len(pages), "archetypes": profiles}


__all__ = ["router"]
