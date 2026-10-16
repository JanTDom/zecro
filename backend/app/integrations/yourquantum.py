"""Small, server-side adapter for the YourQuantum optimization API.

YourQuantum is used here only for a discrete subproblem: choosing a small set
of editorial transgressions under the Title DNA energy budget.  It does not
receive copy, images, scene geometry, or secrets from the browser.  The local
generator and critic remain authoritative for geometry and production gates.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..config import settings
from ..models.schemas import PageInputMaterial, TitleDNA, TransgressionDef


SUPPORTED_TRANSGRESSIONS = {"diagonal-break", "extreme-scale", "cutout-wrap"}


@dataclass
class YourQuantumSelection:
    status: str
    selected_ids: list[str] = field(default_factory=list)
    solver_used: Optional[str] = None
    optimality_proven: Optional[bool] = None
    optimality_gap_percent: Optional[float] = None
    sha256_passport: Optional[str] = None
    request_sha256: Optional[str] = None
    error: Optional[str] = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_ids": list(self.selected_ids),
            "solver_used": self.solver_used,
            "optimality_proven": self.optimality_proven,
            "optimality_gap_percent": self.optimality_gap_percent,
            "sha256_passport": self.sha256_passport,
            "request_sha256": self.request_sha256,
            "error": self.error,
        }


def configured() -> bool:
    """Return whether a server-side API call is explicitly enabled."""
    return bool(settings.yourquantum_api_url.strip() and settings.yourquantum_api_key.strip())


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/universal/compute"):
        return base
    if base.endswith("/api/v1"):
        return f"{base}/universal/compute"
    return f"{base}/api/v1/universal/compute"


def _lead_story(material: PageInputMaterial) -> Any | None:
    stories = list(material.stories or [])
    return max(stories, key=lambda story: float(getattr(story, "importance", 0.0) or 0.0), default=None)


def _eligible_catalog(dna: TitleDNA, material: PageInputMaterial) -> list[TransgressionDef]:
    """Keep only effects the current genome can actually realize."""
    # Empty DNA catalogs use the engine's standard catalog at runtime; mirror
    # that behavior here so the integration is useful for default archetypes.
    source_catalog = dna.transgressions
    if not source_catalog:
        from ..engine.transgressions import STANDARD_TRANSGRESSIONS
        source_catalog = STANDARD_TRANSGRESSIONS
    catalog = [item for item in source_catalog if item.id in SUPPORTED_TRANSGRESSIONS]
    lead = _lead_story(material)
    lead_importance = float(getattr(lead, "importance", 0.0) or 0.0)
    has_cutout_asset = any(
        bool(getattr(image, "is_cutout_candidate", False)
             or getattr(image, "contour_polygon", None)
             or getattr(image, "treatment", None) == "cutout")
        for story in (material.stories or [])
        for image in (getattr(story, "images", None) or [])
    )
    eligible: list[TransgressionDef] = []
    for item in catalog:
        if item.id == "diagonal-break" and (lead_importance < 0.7 or dna.page_energy_budget < 0.5):
            continue
        if item.id == "extreme-scale" and lead_importance < 0.85:
            continue
        if item.id == "cutout-wrap" and not has_cutout_asset:
            continue
        eligible.append(item)
    return eligible


def _utility(transgression_id: str, material: PageInputMaterial) -> float:
    blend = getattr(material, "style_blend", None)
    avantgarde = float(getattr(blend, "classical_to_avantgarde", 0.35) or 0.35)
    tabloid = float(getattr(blend, "opinion_to_tabloid", 0.35) or 0.35)
    photo = float(getattr(blend, "dense_to_photo", 0.50) or 0.50)
    values = {
        "diagonal-break": 0.28 + 0.58 * avantgarde,
        "extreme-scale": 0.25 + 0.62 * tabloid,
        "cutout-wrap": 0.25 + 0.62 * photo,
    }
    return round(max(0.01, min(1.0, values.get(transgression_id, 0.25))), 4)


def _request_payload(dna: TitleDNA, material: PageInputMaterial, catalog: Iterable[TransgressionDef]) -> dict[str, Any]:
    items = list(catalog)
    return {
        "domain": "editorial_layout",
        "title": f"Wybór transgresji: {dna.name}",
        "variables": [
            {
                "id": item.id,
                "name": item.name,
                "attributes": {
                    "utility": _utility(item.id, material),
                    "energy_cost": float(item.cost),
                },
            }
            for item in items
        ],
        "objective_direction": "maximize",
        "objective_attribute": "utility",
        "constraints": [
            {
                "id": "page-energy-budget",
                "name": "Budżet napięcia strony",
                "type": "budget",
                "attribute": "energy_cost",
                "limit": float(dna.page_energy_budget),
            }
        ],
        "solver": "auto",
        "include_stress_test": False,
        "approved_by_caller": True,
    }


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        _endpoint(settings.yourquantum_api_url),
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.yourquantum_api_key.strip()}",
            "X-API-Key": settings.yourquantum_api_key.strip(),
            "User-Agent": "Zecro-Layout-Engine/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=max(1.0, float(settings.yourquantum_timeout_s))) as response:
        raw = response.read()
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("YourQuantum returned a non-object JSON response")
    return result


def select_transgressions(dna: TitleDNA, material: PageInputMaterial, *, enabled: bool = True) -> YourQuantumSelection:
    """Ask YourQuantum for a feasible discrete transgression policy.

    The call is deliberately one-per-generation-run, never one-per-genome.
    Any transport, authentication, schema, or server error becomes an
    explicit ``unavailable`` result and leaves local stochastic exploration in
    charge.
    """
    if not enabled or not configured():
        return YourQuantumSelection(status="disabled")
    catalog = _eligible_catalog(dna, material)
    if not catalog:
        return YourQuantumSelection(status="skipped", error="no eligible transgressions")
    payload = _request_payload(dna, material, catalog)
    request_sha = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    try:
        result = _post(payload)
        if result.get("status") not in {"SUCCESS", "INFEASIBLE"}:
            raise ValueError(f"unexpected status: {result.get('status')}")
        allowed = {item.id for item in catalog}
        selected: list[str] = []
        for item in result.get("optimal_selection") or []:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id in allowed and item_id not in selected:
                selected.append(item_id)
        return YourQuantumSelection(
            status="ready" if result.get("status") == "SUCCESS" else "infeasible",
            selected_ids=selected,
            solver_used=result.get("solver_used"),
            optimality_proven=result.get("optimality_proven"),
            optimality_gap_percent=result.get("optimality_gap_percent"),
            sha256_passport=result.get("sha256_passport"),
            request_sha256=request_sha,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
        return YourQuantumSelection(status="unavailable", request_sha256=request_sha, error=str(exc)[:300])

