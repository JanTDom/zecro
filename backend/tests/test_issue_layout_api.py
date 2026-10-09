import uuid

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.database import db


def test_issue_layout_orchestration_preserves_issue_provenance_and_translation_draft():
    client = TestClient(app)
    project_id = str(uuid.uuid4())
    issue_id = str(uuid.uuid4())
    story_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    try:
        assert client.post("/projects", json={"id": project_id, "name": "Zecro issue generation"}).status_code == 201
        assert client.post(f"/projects/{project_id}/issues", json={
            "id": issue_id,
            "project_id": project_id,
            "issue_number": "09/2026",
            "publication_date": "2026-10-09",
            "page_count": 2,
            "sections": ["NEWS"],
        }).status_code == 201
        assert client.post(f"/issues/{issue_id}/sources", json={
            "id": source_id,
            "issue_ref": issue_id,
            "source_type": "statement",
            "title": "Źródło testowe",
            "excerpt": "Treść artykułu pozostaje powiązana ze źródłami i wydaniem.",
        }).status_code == 201
        assert client.post(f"/issues/{issue_id}/stories", json={
            "id": story_id,
            "issue_ref": issue_id,
            "slug": "issue-story",
            "headline": "Wydanie ma własny kontekst",
            "body": "Treść artykułu pozostaje powiązana ze źródłami i wydaniem. Druga teza wymaga potwierdzenia.",
            "language": "pl",
            "importance": 1.0,
            "source_refs": [source_id],
        }).status_code == 201

        translated = client.post(f"/stories/{story_id}/translate", json={"target_language": "en"})
        assert translated.status_code == 201
        assert translated.json()["provenance"]["requires_editor"] is True
        assert translated.json()["approval"]["editorial"] == "pending"

        generated = client.post(f"/issues/{issue_id}/generate-layouts", json={
            "page_number": 1,
            "num_candidates": 1,
            "population_size": 10,
            "generations": 1,
            "allow_transgressions": False,
            "seed": 23,
        })
        assert generated.status_code == 201
        candidate = generated.json()["candidates"][0]
        page = candidate["scene_graph"]["page"]
        assert page["issue_ref"] == issue_id
        assert page["page_number"] == 1
        assert page["page_role"] == "front"
        assert candidate["scene_graph"]["metadata"]["issue_ref"] == issue_id
        preflight = client.post(f"/candidates/{candidate['id']}/preflight")
        assert preflight.status_code == 200
        assert preflight.json()["status"] == "FAIL"
        assert any("fact_check" in error for error in preflight.json()["errors"])
        factchecked = client.post(f"/stories/{story_id}/factcheck")
        assert factchecked.status_code == 200
        assert factchecked.json()["fact_checked"] is False
        assert any(claim["status"] == "verified" for claim in factchecked.json()["claims"])
        assert client.post(f"/stories/{story_id}/approve").status_code == 409
        locked = client.post(f"/stories/{story_id}/lock", json={"passage": "Wydanie ma", "locked": True})
        assert locked.status_code == 200
        assert "Wydanie ma" in locked.json()["locked_passages"]
        manifest = client.get(f"/issues/{issue_id}/manifest")
        assert manifest.status_code == 200
        for key in ("copy_variants", "text_plans", "text_fits", "preflight_reports", "exports"):
            assert key in manifest.json()
        assert len(manifest.json()["preflight_reports"]) >= 1
    finally:
        db.delete_project(project_id)
