import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.database import db


def test_editorial_plan_variants_and_copyfit_roundtrip():
    client = TestClient(app)
    project_id = str(uuid.uuid4())
    issue_id = str(uuid.uuid4())
    story_id = str(uuid.uuid4())
    try:
        assert client.post("/projects", json={"id": project_id, "name": "Zecro editorial test"}).status_code == 201
        assert client.post(f"/projects/{project_id}/issues", json={
            "id": issue_id, "project_id": project_id, "issue_number": "01/2026", "publication_date": "2026-10-09", "page_count": 4,
        }).status_code == 201
        assert client.post(f"/issues/{issue_id}/sources", json={
            "issue_ref": issue_id, "source_type": "statement", "title": "Źródło", "excerpt": "Anna Nowak powiedziała 12 mln zł.",
        }).status_code == 201
        assert client.post(f"/issues/{issue_id}/stories", json={
            "id": story_id, "issue_ref": issue_id, "slug": "test", "headline": "Nowy projekt", "body": "Anna Nowak powiedziała 12 mln zł. To ważna decyzja.",
        }).status_code == 201
        plan = client.post(f"/issues/{issue_id}/plan/auto", json={"variant": "standard"})
        assert plan.status_code == 201
        assert len(plan.json()["pages"]) == 4
        assert plan.json()["pages"][0]["text_plan_refs"]
        auto_text_plans = client.get(f"/issues/{issue_id}/manifest").json()["text_plans"]
        assert any(item["story_ref"] == story_id and item["role"] == "body" for item in auto_text_plans)
        variants = client.post(f"/stories/{story_id}/generate-variants", json={})
        assert variants.status_code == 200
        assert len(variants.json()) >= 5
        text_plan = client.post("/text-plans", json={
            "story_ref": story_id, "issue_ref": issue_id, "width_mm": 90, "height_mm": 120, "columns": 2,
        })
        assert text_plan.status_code == 201
        fit = client.post(f"/text-plans/{text_plan.json()['id']}/fit", json={"text": "Krótki tekst do pomiaru."})
        assert fit.status_code == 201
        assert fit.json()["status"] in {"PASS", "FAIL"}
        history = client.get(f"/editorial/story/{story_id}/history")
        assert history.status_code == 200
        assert history.json()["revisions"]
    finally:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM editorial_objects WHERE id IN (?, ?) OR issue_ref = ?", (issue_id, story_id, issue_id))
            conn.commit()
        db.delete_project(project_id)
