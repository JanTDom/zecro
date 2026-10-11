"""Offline smoke test of the endpoints used by the new frontend panels."""
from fastapi.testclient import TestClient


def test_planner_settings_fonts_endpoints(library_fonts, monkeypatch):
    from backend.app.main import app
    from backend.app.config import settings
    monkeypatch.setattr(settings, "admin_token", "t0ken")
    c = TestClient(app)
    adm = {"X-Zecro-Admin-Token": "t0ken"}
    pid = c.post("/projects", json={"name": "Smoke", "description": "", "status": "ready"}).json()["id"]
    body = "Rada miasta przyjęła w czwartek uchwałę o nowym planie zagospodarowania Pragi. " * 30
    stories = [{"id": f"s{i}", "headline": f"Tytuł {i} na stronie", "body": body[: 2400 // (i + 1)], "rank": r}
               for i, r in enumerate(["lead", "second", "brief", "brief"])]
    plan = c.post(f"/projects/{pid}/page-plan", json={"stories": stories}).json()
    assert plan["status"] == "valid" and plan["geometry"] == "auto"
    plan["geometry"] = "fixed"
    run = c.post(f"/projects/{pid}/generate", json={
        "material": {"stories": stories, "masthead_title": "SMOKE", "page_zone": "front_page", "page_plan": plan},
        "page_plan": plan, "num_candidates": 2, "population_size": 10, "generations": 1, "visual_review": False})
    assert run.status_code in (200, 201), run.text[:500]
    cands = run.json()["candidates"]
    assert cands and all(cd["scene_graph"]["metadata"]["architecture"] == "fixed" for cd in cands)
    assert c.get("/settings/routing", headers=adm).status_code == 200
    assert c.get("/settings/limits", headers=adm).status_code == 200
    assert isinstance(c.get("/settings/audit", headers=adm).json(), list)
    assert isinstance(c.get("/photos/sources").json(), list)
    fams = c.get("/fonts?polish_only=true").json()
    assert any(f["polish"] in {"full", "partial"} for f in fams)
