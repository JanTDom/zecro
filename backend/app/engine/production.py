"""Deterministic production gate shared by export and editorial preflight."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models.schemas import PreflightReport, SceneGraph, TitleDNA
from .content_engine import fit_text_plan
from .critic import LayoutCritic, effective_print_dpi
from .image_ops import resolve_asset_path
from ..models.schemas import TextPlan


def preflight_scene_graph(scene: SceneGraph, dna: TitleDNA, *, candidate_ref: Optional[str] = None) -> PreflightReport:
    checks = []
    errors = []
    warnings = []
    critic = LayoutCritic(dna).evaluate(scene)
    checks.append({"id": "hard_gate", "status": "PASS" if critic.hard_gate.passed else "FAIL", "value": critic.hard_gate.violations})
    if not critic.hard_gate.passed:
        errors.extend(critic.hard_gate.violations)
    for element in scene.elements:
        if element.role == "photo":
            if not element.image_url or not resolve_asset_path(element.image_url):
                warnings.append(f"missing or remote asset: {element.id}")
            photo_dpi = effective_print_dpi(element)
            if photo_dpi is not None and photo_dpi < dna.photo_rules.min_dpi:
                errors.append(f"{element.id}: {photo_dpi:.0f} effective dpi below {dna.photo_rules.min_dpi}dpi")
        if element.role in {"body", "lead", "deck", "caption"} and element.text_content:
            plan = None
            if element.text_plan_ref:
                from ..models.database import db

                saved_plan = db.get_editorial_object("text_plan", element.text_plan_ref)
                if saved_plan:
                    plan = TextPlan(**saved_plan)
                    # The flatplan's dimensions are planning priors.  The
                    # scene frame is authoritative once geometry exists.
                    plan.frame_ref = element.id
                    plan.columns = int(element.style.columns or plan.columns or 1)
                    plan.width_mm = element.frame.w
                    plan.height_mm = element.frame.h
            if plan is None:
                plan = TextPlan(story_ref=element.content_ref or element.id, issue_ref="preflight", page_ref="scene", frame_ref=element.id, role=element.role, columns=int(element.style.columns or 1), width_mm=element.frame.w, height_mm=element.frame.h, min_font_size_pt=float(element.style.font_size_pt or dna.typography.scales.body))
            fit = fit_text_plan(plan, element.text_content)
            checks.append({"id": f"copyfit:{element.id}", "status": fit.status, "value": fit.model_dump(mode="json")})
            if fit.status == "FAIL":
                errors.extend([f"{element.id}: {warning}" for warning in fit.warnings])
        if element.fit_status == "FAIL":
            errors.append(f"{element.id}: scene element carries an explicit FAIL fit status")

    # When a scene was generated from the editorial layer, provenance is a
    # production gate rather than a soft score.  Project-only exploratory
    # candidates have no story_ref and therefore keep the geometry-only path.
    story_refs = {element.story_ref for element in scene.elements if element.story_ref}
    if story_refs and scene.page.issue_ref:
        from ..models.database import db

        approved_states = {"approved_for_layout", "placed", "proof", "approved_for_print", "published", "archived"}
        provenance_errors = []
        for story_ref in sorted(story_refs):
            story = db.get_editorial_object("story", story_ref)
            if not story:
                provenance_errors.append(f"story {story_ref}: provenance record is missing")
                continue
            if not story.get("fact_checked"):
                provenance_errors.append(f"story {story_ref}: fact_check is not closed")
            claims = story.get("claims") or []
            unresolved = [claim.get("id") or claim.get("text", "") for claim in claims if claim.get("status") != "verified"]
            if unresolved:
                provenance_errors.append(f"story {story_ref}: unresolved claims {unresolved}")
            if not story.get("editor_approved") and story.get("editorial_status") not in approved_states:
                provenance_errors.append(f"story {story_ref}: editorial approval is not closed")
            for asset_ref in story.get("asset_refs") or []:
                asset = db.get_editorial_object("asset", asset_ref)
                if not asset:
                    provenance_errors.append(f"asset {asset_ref}: record is missing")
                elif asset.get("status") not in {"available", "approved"}:
                    provenance_errors.append(f"asset {asset_ref}: rights status is {asset.get('status')}")
                elif not asset.get("credit_line"):
                    provenance_errors.append(f"asset {asset_ref}: credit line is missing")
        checks.append({"id": "editorial_provenance", "status": "FAIL" if provenance_errors else "PASS", "value": provenance_errors})
        errors.extend(provenance_errors)
    checks.append({"id": "pdfx", "status": "WARN", "value": "PDF/X requires external ICC/preflight validator"})
    warnings.append("PDF/X, TAC and ICC output intent require an external press validator")
    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return PreflightReport(candidate_ref=candidate_ref, status=status, checks=checks, errors=errors, warnings=warnings)
