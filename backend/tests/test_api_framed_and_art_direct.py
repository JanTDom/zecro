"""Testy endpointów okładki ramowej i pętli AI w API (framed-cover, art-direct, apply-fixes)."""
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app


def test_framed_cover_endpoint():
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Projekt Okładka", "status": "ready"}).json()
    project_id = proj["id"]

    res = client.post(f"/projects/{project_id}/framed-cover", json={"kit_name": "wukadka", "genes": {}})
    assert res.status_code == 200, res.text
    cand = res.json()
    assert cand["id"]
    assert cand["scene_graph"]["metadata"]["architecture"] == "framed_cover"
    assert cand["scene_graph"]["metadata"]["composition"] == "layered"
    assert cand["svg_thumbnail"]
    assert "<svg" in cand["svg_thumbnail"]
    assert cand["critic"]["hard_gate"]["passed"] is True


def test_apply_fixes_endpoint():
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Projekt Poprawki", "status": "ready"}).json()
    project_id = proj["id"]

    fixes = ["bottom: strip"]
    res = client.post(
        f"/projects/{project_id}/art-direct/apply-fixes",
        json={"composer": "framed_cover:wukadka", "genes": {}, "fixes": fixes}
    )
    assert res.status_code == 200, res.text
    cand = res.json()
    assert cand["id"]
    assert cand["scene_graph"]["metadata"]["applied_fixes"] == fixes
    assert cand["scene_graph"]["metadata"]["genes"]["bottom"] == "strip"


def test_art_direct_endpoint_with_mocked_loop(tmp_path):
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Projekt Art Direct", "status": "ready"}).json()
    project_id = proj["id"]

    scene_file = tmp_path / "okladka.scene.json"
    from backend.scripts.wukadka_demo import material
    from backend.app.engine.framed_cover import compose_framed_cover
    sg = compose_framed_cover(material(), kit_name="wukadka", genes={})
    scene_file.write_text(sg.model_dump_json(), encoding="utf-8")

    fake_trace = {
        "composer": "framed_cover:wukadka",
        "plan": {"mysl_przewodnia": "Mocna okładka sensacyjna"},
        "rounds": [
            {
                "round": 1,
                "genes": {},
                "gate": "PASS",
                "violations": [],
                "scene": str(scene_file),
                "review": {
                    "ocena": 8.5,
                    "do_druku": True,
                    "werdykt": "Strona gotowa do druku",
                    "defekty": [],
                    "poprawki": ["hero_shift: -3"]
                }
            }
        ],
        "best_round": 1,
        "done": "gotowe: ocena redaktora >= 8.5"
    }

    with patch("backend.app.api.generate.art_direct", return_value={"trace": fake_trace}):
        res = client.post(
            f"/projects/{project_id}/art-direct",
            json={"composer": "framed_cover:wukadka", "rounds": 1}
        )
        assert res.status_code == 200, res.text
        run = res.json()
        assert run["status"] == "completed"
        assert len(run["candidates"]) == 1
        cand = run["candidates"][0]
        assert cand["rank"] == 1
        assert cand["scene_graph"]["metadata"]["visual_critique"]["score"] == 8.5
        assert cand["scene_graph"]["metadata"]["visual_critique"]["status"] == "candidate_for_editor"
