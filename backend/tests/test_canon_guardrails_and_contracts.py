import json
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.schemas import (
    TitleDNA, SceneGraph, PageInputMaterial, StoryInput, StoryImageInput,
    Project, PreferenceSignal, Candidate, GenerationRequest
)
from backend.app.engine.grammar import create_default_tabloid_dna, create_default_broadsheet_dna, LayoutGrammar
from backend.app.engine.solver import GridSolver
from backend.app.engine.evolution import EvolutionaryLayoutGenerator
from backend.app.engine.critic import LayoutCritic

class SchemaValidator:
    def __init__(self, schema_path: str):
        with open(schema_path, "r") as f:
            self.schema = json.load(f)
        self.definitions = self.schema.get("definitions", {})

    def _resolve_ref(self, ref: str) -> Dict[str, Any]:
        if ref.startswith("#/definitions/"):
            def_name = ref.split("/")[-1]
            if def_name in self.definitions:
                return self.definitions[def_name]
        raise ValueError(f"Cannot resolve reference: {ref}")

    def validate(self, instance: Any, subschema: Dict[str, Any] = None, path: str = "$") -> None:
        if subschema is None:
            subschema = self.schema

        if "$ref" in subschema:
            resolved = self._resolve_ref(subschema["$ref"])
            self.validate(instance, resolved, path)
            return

        expected_type = subschema.get("type")
        if expected_type:
            if expected_type == "object":
                assert isinstance(instance, dict), f"At {path}: expected dict, got {type(instance).__name__}"
                for req in subschema.get("required", []):
                    assert req in instance, f"At {path}: missing required property '{req}'"
                properties = subschema.get("properties", {})
                for prop_name, prop_schema in properties.items():
                    if prop_name in instance and instance[prop_name] is not None:
                        self.validate(instance[prop_name], prop_schema, f"{path}.{prop_name}")

            elif expected_type == "array":
                assert isinstance(instance, (list, tuple)), f"At {path}: expected list, got {type(instance).__name__}"
                min_items = subschema.get("minItems")
                if min_items is not None:
                    assert len(instance) >= min_items, f"At {path}: len {len(instance)} < minItems {min_items}"
                max_items = subschema.get("maxItems")
                if max_items is not None:
                    assert len(instance) <= max_items, f"At {path}: len {len(instance)} > maxItems {max_items}"
                items_schema = subschema.get("items")
                if items_schema:
                    for idx, item in enumerate(instance):
                        self.validate(item, items_schema, f"{path}[{idx}]")

            elif expected_type == "string":
                assert isinstance(instance, str), f"At {path}: expected str, got {type(instance).__name__}"
                enum_vals = subschema.get("enum")
                if enum_vals is not None:
                    assert instance in enum_vals, f"At {path}: '{instance}' not in allowed enum {enum_vals}"

            elif expected_type in ("number", "integer"):
                if expected_type == "integer":
                    assert isinstance(instance, int) and not isinstance(instance, bool), f"At {path}: expected int, got {type(instance).__name__}"
                else:
                    assert isinstance(instance, (int, float)) and not isinstance(instance, bool), f"At {path}: expected num, got {type(instance).__name__}"
                minimum = subschema.get("minimum")
                if minimum is not None:
                    assert instance >= minimum, f"At {path}: {instance} < minimum {minimum}"
                maximum = subschema.get("maximum")
                if maximum is not None:
                    assert instance <= maximum, f"At {path}: {instance} > maximum {maximum}"

            elif expected_type == "boolean":
                assert isinstance(instance, bool), f"At {path}: expected bool, got {type(instance).__name__}"

def test_contract_title_dna_schema_validation():
    dna_val = SchemaValidator("contracts/title_dna.schema.json")
    tabloid_dna = create_default_tabloid_dna()
    broadsheet_dna = create_default_broadsheet_dna()

    dna_val.validate(tabloid_dna.model_dump(mode="json"))
    dna_val.validate(broadsheet_dna.model_dump(mode="json"))

def test_contract_scene_graph_schema_validation():
    sg_val = SchemaValidator("contracts/scene_graph.schema.json")
    tabloid_dna = create_default_tabloid_dna()
    solver = GridSolver(tabloid_dna)

    material = PageInputMaterial(
        masthead_title="THE CANON CHRONICLE",
        issue_date="September 1, 2026",
        section_name="AUDIT INVESTIGATION",
        stories=[
            StoryInput(
                id="lead_story",
                kicker="CANON AUDIT",
                headline="GENERATIVE PREPRESS PASSES FORMAL VERIFICATION",
                lead="All hard constraints, baseline grids, and IDML packages verified.",
                body="Modular grid solver packs text columns strictly avoiding cutout contour masks while maintaining vertical baseline rhythm.",
                importance=1.0,
                image=StoryImageInput(
                    image_id="img_lead",
                    url="lead.jpg",
                    aspect_ratio=1.33,
                    treatment="cutout",
                    has_alpha_mask=True,
                    contour_polygon=[[10.0, 10.0], [50.0, 10.0], [50.0, 60.0], [10.0, 60.0]]
                )
            )
        ]
    )

    sg = solver.solve(material)
    sg_val.validate(sg.model_dump(mode="json"))

    evo = EvolutionaryLayoutGenerator(tabloid_dna)
    candidates = evo.generate(material, num_candidates=8, population_size=16, generations=4)
    assert len(candidates) >= 8
    for cand_sg, crit_res in candidates:
        sg_val.validate(cand_sg.model_dump(mode="json"))

def test_full_e2e_lifecycle_and_idml_audit():
    client = TestClient(app)

    # 1. Create project
    res_p = client.post("/projects", json={"name": "Test Lifecycle Project", "description": "QA"})
    assert res_p.status_code == 201
    proj_id = res_p.json()["id"]

    # 2. Ingest corpus and learn DNA
    client.post(
        f"/projects/{proj_id}/corpus",
        files={"file": ("p1.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"title": "Page 1"}
    )
    res_l = client.post(f"/projects/{proj_id}/dna:learn")
    assert res_l.status_code == 200

    # 3. Evolutionary run N=8
    material_payload = {
        "masthead_title": "THE CANON HERALD",
        "issue_date": "September 1, 2026",
        "section_name": "INVESTIGATIVE DESK",
        "stories": [
            {
                "id": "story_main",
                "kicker": "SPECIAL REPORT",
                "headline": "AUTONOMOUS PREPRESS SOLVER MEETS GOLDEN GUARDRAILS",
                "lead": "Every golden guardrail from SKILL.md has been rigorously verified.",
                "body": "The dual-engine separation ensures unconditional exploration while the hard constraint gate filters any unprintable layouts.",
                "importance": 1.0,
                "image": {
                    "image_id": "img_main",
                    "url": "test.jpg",
                    "aspect_ratio": 1.25,
                    "treatment": "cutout",
                    "has_alpha_mask": True,
                    "contour_polygon": [[12.0, 12.0], [45.0, 12.0], [45.0, 55.0], [12.0, 55.0]]
                }
            }
        ]
    }
    res_g = client.post(f"/projects/{proj_id}/generate", json={
        "material": material_payload,
        "num_candidates": 8,
        "population_size": 20,
        "generations": 4
    })
    assert res_g.status_code == 201
    candidates = res_g.json()["candidates"]
    # A one-story page has a small space of genuinely different layouts; the
    # generator returns distinct candidates rather than padding with clones.
    assert 4 <= len(candidates) <= 8
    signatures = {tuple(sorted((e["role"], round(e["frame"]["x"]), round(e["frame"]["y"]), round(e["frame"]["w"]), round(e["frame"]["h"])) for e in c["scene_graph"]["elements"])) for c in candidates}
    assert len(signatures) == len(candidates)

    cand_1 = candidates[0]
    cand_2 = candidates[1]

    # 4. Pairwise preference and edit delta
    res_pref = client.post(f"/projects/{proj_id}/preferences", json={
        "project_id": proj_id,
        "signal_type": "pairwise_comparison",
        "winner_candidate_id": cand_1["id"],
        "loser_candidate_id": cand_2["id"],
        "notes": "Prefer cand 1"
    })
    assert res_pref.status_code == 201

    res_edit = client.post(f"/projects/{proj_id}/preferences", json={
        "project_id": proj_id,
        "signal_type": "manual_edit_delta",
        "winner_candidate_id": cand_1["id"],
        "delta_features": {"visual_balance": 0.08},
        "notes": "Shift"
    })
    assert res_edit.status_code == 201

    # 5. Export IDML, SVG, PDF
    res_idml = client.post(f"/candidates/{cand_1['id']}/export?format=idml")
    assert res_idml.status_code == 201
    idml_path = res_idml.json()["file_path"]

    # Verify IDML ZIP structure
    assert zipfile.is_zipfile(idml_path)
    with zipfile.ZipFile(idml_path, "r") as zf:
        namelist = zf.namelist()
        assert namelist[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert "META-INF/container.xml" in namelist
        assert "designmap.xml" in namelist
        assert "Resources/Styles.xml" in namelist
        assert "Resources/Fonts.xml" in namelist
        assert "Resources/Graphic.xml" in namelist
        assert "Resources/Preferences.xml" in namelist
        assert "Spreads/Spread_u_spread_0.xml" in namelist
        assert any(name.startswith("Stories/Story_") for name in namelist)

        # XML parsing validation
        ET.fromstring(zf.read("META-INF/container.xml"))
        ET.fromstring(zf.read("designmap.xml"))
        ET.fromstring(zf.read("Spreads/Spread_u_spread_0.xml"))

    # Cleanup
    client.delete(f"/projects/{proj_id}")
