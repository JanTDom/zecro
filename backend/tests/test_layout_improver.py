"""Unit and integration tests for LayoutImprover and layout API endpoints."""
from __future__ import annotations

import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.engine.layout_auditor import LayoutAuditor
from backend.app.engine.layout_improver import LayoutImprover
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph


def _make_flawed_scene() -> SceneGraph:
    """Creates a layout with competing photos, hanging prepositions, and flat typography."""
    return SceneGraph(
        page=PageMeta(trim=[280.0, 400.0], page_zone="front_page"),
        elements=[
            # Competing photos (equal size)
            Element(
                id="photo_1",
                role="photo",
                frame=Frame(x=15.0, y=20.0, w=120.0, h=120.0),
                importance=0.8,
            ),
            Element(
                id="photo_2",
                role="photo",
                frame=Frame(x=145.0, y=20.0, w=120.0, h=120.0),
                importance=0.8,
            ),
            # Flat headline with hanging preposition "w " and "z "
            Element(
                id="headline_raw",
                role="headline",
                text_content="Nowe porozumienie w sprawie kolei z Warszawy",
                frame=Frame(x=15.0, y=150.0, w=250.0, h=18.0),
                style=ElementStyle(font_size_pt=18.0, font_weight="bold"),
            ),
            # Body text with underset slack
            Element(
                id="body_raw",
                role="body",
                text_content="Krótki tekst artykułu o zmianach w rozkładzie jazdy.",
                frame=Frame(x=15.0, y=175.0, w=160.0, h=120.0),
                style=ElementStyle(font_size_pt=10.0),
            ),
        ],
    )


def test_layout_improver_produces_three_improved_candidates():
    dna = create_default_tabloid_dna()
    scene = _make_flawed_scene()
    improver = LayoutImprover()

    result = improver.improve_layout(scene, dna)

    assert result.original_audit is not None
    assert len(result.candidates) == 3

    phenotypes = {c.phenotype for c in result.candidates}
    assert phenotypes == {"conservative_clean", "dynamic_dominant", "versus_split_or_asymmetric"}

    # Dynamic dominant candidate should resolve photo competition
    dom_cand = next(c for c in result.candidates if c.phenotype == "dynamic_dominant")
    assert dom_cand.score_after >= dom_cand.score_before
    photos_in_dom = [e for e in dom_cand.scene_graph.elements if e.role == "photo"]
    assert len(photos_in_dom) >= 1
    # Hero photo is scaled to dominant width (> 180 mm)
    hero_p = max(photos_in_dom, key=lambda p: p.frame.w * p.frame.h)
    assert hero_p.frame.w >= 180.0

    # Versus split candidate should introduce confrontation badge
    vs_cand = next(c for c in result.candidates if c.phenotype == "versus_split_or_asymmetric")
    badge_elem = next((e for e in vs_cand.scene_graph.elements if "KONTRA" in (e.text_content or "")), None)
    assert badge_elem is not None
    assert "intentional_photo_badge" in (badge_elem.constraints or [])


def test_layout_improver_fixes_polish_microtypography():
    dna = create_default_tabloid_dna()
    scene = _make_flawed_scene()
    improver = LayoutImprover()

    result = improver.improve_layout(scene, dna)

    for cand in result.candidates:
        hl = next(e for e in cand.scene_graph.elements if e.role == "headline")
        assert hl.text_content is not None
        # Must not contain dangling ' w ' or ' z ' with regular space
        assert " w " not in hl.text_content
        assert " z " not in hl.text_content


def test_api_layout_audit_and_improve_endpoints():
    client = TestClient(app)
    scene = _make_flawed_scene()
    dna = create_default_tabloid_dna()

    # 1. Test /layout/audit
    audit_resp = client.post(
        "/layout/audit",
        json={"scene_graph": scene.model_dump(), "title_dna": dna.model_dump()},
    )
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert "overall_score" in audit_data
    assert "defects" in audit_data
    assert len(audit_data["defects"]) >= 1

    # 2. Test /layout/improve
    imp_resp = client.post(
        "/layout/improve",
        json={"scene_graph": scene.model_dump(), "title_dna": dna.model_dump()},
    )
    assert imp_resp.status_code == 200
    imp_data = imp_resp.json()
    assert "candidates" in imp_data
    assert len(imp_data["candidates"]) == 3
    for cand in imp_data["candidates"]:
        assert cand["score_after"] >= cand["score_before"]
        assert "applied_actions" in cand
        assert len(cand["applied_actions"]) >= 1


def test_api_layout_export_idml_endpoint():
    client = TestClient(app)
    scene = _make_flawed_scene()
    dna = create_default_tabloid_dna()

    resp = client.post(
        "/layout/export-idml",
        json={"scene_graph": scene.model_dump(), "title_dna": dna.model_dump()},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.adobe.indesign-idml-package"
    assert len(resp.content) > 1000
