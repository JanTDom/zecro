"""Regression tests for generation policy and the export production boundary."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from backend.app.engine.evolution import EvolutionaryLayoutGenerator
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.main import app
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput


client = TestClient(app)


def test_allow_transgressions_false_removes_explicit_and_implicit_effects():
    material = PageInputMaterial(
        stories=[
            StoryInput(
                id="story-policy",
                headline="Policy controlled composition",
                body="A body passage that is long enough for the deterministic generator. " * 8,
                importance=1.0,
                images=[
                    StoryImageInput(
                        id="image-policy",
                        url="https://example.invalid/photo.jpg",
                        treatment="cutout",
                        is_cutout_candidate=True,
                    )
                ],
            )
        ]
    )
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    candidates = generator.generate(
        material,
        num_candidates=3,
        population_size=10,
        generations=1,
        seed=17,
        allow_transgressions=False,
    )

    for scene, critic in candidates:
        assert critic.hard_gate.passed
        for element in scene.elements:
            assert element.transgressions == []
            assert element.frame.rotation_deg == 0.0
            if element.role == "headline" and element.style and element.style.font_size_pt:
                assert element.style.font_size_pt <= dna.typography.scales.headline_l * 1.15
            if element.role == "photo":
                assert element.treatment not in {"cutout", "full-bleed"}
                assert element.contour_points is None
                assert not element.text_wrap or element.text_wrap.mode != "contour"


def test_export_rejects_candidate_after_failed_preflight():
    project = client.post("/projects", json={"name": "Preflight boundary test"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    try:
        generated = client.post(
            f"/projects/{project_id}/generate",
            json={
                "material": {
                    "stories": [
                        {
                            "id": "story-export-gate",
                            "headline": "A valid candidate before editing",
                            "body": "Body copy for export gate verification. " * 6,
                            "importance": 1.0,
                        }
                    ]
                },
                "num_candidates": 1,
                "population_size": 10,
                "generations": 1,
                "seed": 9,
                "allow_transgressions": False,
            },
        )
        assert generated.status_code == 201
        candidate = generated.json()["candidates"][0]
        assert all(not element["transgressions"] for element in candidate["scene_graph"]["elements"])
        scene = deepcopy(candidate["scene_graph"])
        headline = next(element for element in scene["elements"] if element["role"] == "headline")
        headline["frame"]["x"] = 10000.0

        updated = client.put(f"/candidates/{candidate['id']}", json=scene)
        assert updated.status_code == 200
        assert updated.json()["critic"]["hard_gate"]["passed"] is False

        exported = client.post(f"/candidates/{candidate['id']}/export?format=svg")
        assert exported.status_code == 409
        detail = exported.json()["detail"]
        assert "preflight" in detail
        assert "export was not created" in detail["message"]
    finally:
        client.delete(f"/projects/{project_id}")
