"""Gemini as the issue editor: three ranked page-plan proposals, validated by the packer."""
from __future__ import annotations
from typing import Any, Optional

from ..engine.page_planner import plan_page, validate_page_plan
from .runtime import run_task
from . import schemas as S


def propose_plans(dna, stories: list, *, page_zone: str = "front_page", title_style: Optional[str] = None,
                  project_id: Optional[str] = None) -> dict[str, Any]:
    pinned = [s.id for s in stories if getattr(s, "pin_zone", None) not in (None, "anywhere")]
    payload = {"page_zone": page_zone, "grid": {"columns": dna.grid.columns, "trim_mm": [dna.format.trim_w_mm, dna.format.trim_h_mm]},
               "title_style": title_style or getattr(dna, "archetype", "dziennik"),
               "stories": [{"id": s.id, "headline": s.headline, "lead": (s.lead or "")[:300], "words": len((s.body or "").split()),
                            "has_image": bool(s.images), "current_rank": getattr(s, "rank", None)} for s in stories],
               "pinned": [{"id": s.id, "rank": getattr(s, "rank", None), "pin_zone": getattr(s, "pin_zone", None)} for s in stories if s.id in pinned]}
    res = run_task("page_planning", "page_planning", payload, S.PlanProposals, project_id=project_id)
    ids = {s.id for s in stories}
    out = []
    for proposal in res.data["proposals"][:3]:
        by_id = {p["story_id"]: p for p in proposal["stories"]}
        problems = [f"brak tekstu {i} w planie" for i in ids - set(by_id)] + [f"nieznany tekst {i}" for i in set(by_id) - ids]
        if sum(1 for p in proposal["stories"] if p["rank"] == "lead") != 1:
            problems.append("plan musi mieć dokładnie jedną dominantę")
        ranked = []
        for s in stories:
            p = by_id.get(s.id)
            c = s.model_copy(deep=True)
            if p and s.id not in pinned:
                c.rank, c.span_cols, c.pin_zone, c.group, c.teaser_only = p["rank"], p["span_cols"], p["pin_zone"], p["group"] or None, p["teaser_only"]
            ranked.append(c)
        plan = plan_page(dna, ranked, page_zone=page_zone)
        errors = validate_page_plan(plan, ranked) + problems
        if errors:
            plan.status = "invalid"
            plan.warnings.extend(errors)
        out.append({"name": proposal["name"], "rationale": proposal["rationale"], "assignments": proposal["stories"],
                    "plan": plan.model_dump(mode="json"), "valid": not errors, "errors": errors})
    return {"proposals": out, "provenance": res.provenance, "status": "draft"}
