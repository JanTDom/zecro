import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.schemas import Project, PageInputMaterial, StoryInput, GenerationRequest, PreferenceSignal

client = TestClient(app)

def test_health_and_root():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

def test_project_lifecycle_and_generation():
    # 1. Create Project
    proj_data = {
        "name": "Integration Test Tabloid",
        "description": "Tabloid newspaper for automated test suite",
        "status": "ready"
    }
    res = client.post("/projects", json=proj_data)
    assert res.status_code == 201
    created_proj = res.json()
    proj_id = created_proj["id"]

    # 2. Get Title DNA
    res_dna = client.get(f"/projects/{proj_id}/dna")
    assert res_dna.status_code == 200
    dna = res_dna.json()
    assert dna["grid"]["columns"] == 5

    # 3. Update Title DNA
    dna["page_energy_budget"] = 1.35
    res_update_dna = client.put(f"/projects/{proj_id}/dna", json=dna)
    assert res_update_dna.status_code == 200
    assert res_update_dna.json()["page_energy_budget"] == 1.35

    # 4. Ingest Corpus Page
    dummy_pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("test_page.pdf", dummy_pdf_content, "application/pdf")}
    data = {"title": "Test Page Issue 1"}
    res_corpus = client.post(f"/projects/{proj_id}/corpus", files=files, data=data)
    assert res_corpus.status_code == 201
    assert res_corpus.json()["file_type"] == "pdf"

    # 5. Learn DNA from Corpus
    res_learn = client.post(f"/projects/{proj_id}/dna:learn")
    assert res_learn.status_code == 200

    # 6. Execute Generation Run
    gen_payload = {
        "material": {
            "masthead_title": "TEST GAZETTE",
            "issue_date": "Sept 1, 2026",
            "section_name": "MAIN NEWS",
            "stories": [
                {
                    "id": "s1",
                    "kicker": "BREAKING",
                    "headline": "TEST LAYOUT GENERATED END TO END VIA FASTAPI",
                    "lead": "Testing complete integration flow.",
                    "body": "Body paragraphs fitting into the modular grid system.",
                    "importance": 1.0
                }
            ]
        },
        "num_candidates": 3,
        "population_size": 10,
        "generations": 3
    }
    res_gen = client.post(f"/projects/{proj_id}/generate", json=gen_payload)
    assert res_gen.status_code == 201
    run_data = res_gen.json()
    assert len(run_data["candidates"]) >= 2
    cand_1 = run_data["candidates"][0]
    cand_2 = run_data["candidates"][1]

    # 7. Record Preference Signal
    pref_payload = {
        "project_id": proj_id,
        "signal_type": "pairwise_comparison",
        "winner_candidate_id": cand_1["id"],
        "loser_candidate_id": cand_2["id"],
        "notes": "Preferred cleaner balance in candidate 1"
    }
    res_pref = client.post(f"/projects/{proj_id}/preferences", json=pref_payload)
    assert res_pref.status_code == 201

    # 8. Check Taste Model
    res_tm = client.get(f"/projects/{proj_id}/taste-model")
    assert res_tm.status_code == 200
    tm = res_tm.json()
    assert tm["sample_count"] >= 1

    # 9. Preview Candidate HTML
    res_prev = client.get(f"/candidates/{cand_1['id']}/preview")
    assert res_prev.status_code == 200
    assert "<!DOCTYPE html>" in res_prev.text

    # 10. Export Candidate to IDML & SVG & PDF
    res_export_svg = client.post(f"/candidates/{cand_1['id']}/export?format=svg")
    assert res_export_svg.status_code == 201
    svg_artifact = res_export_svg.json()
    assert svg_artifact["format"] == "svg"

    res_export_idml = client.post(f"/candidates/{cand_1['id']}/export?format=idml")
    assert res_export_idml.status_code == 201
    idml_artifact = res_export_idml.json()
    assert idml_artifact["format"] == "idml"

    # 11. Download Export
    res_down = client.get(f"/exports/{idml_artifact['id']}/download")
    assert res_down.status_code == 200
    assert len(res_down.content) > 100

    # 12. Delete Project
    res_del = client.delete(f"/projects/{proj_id}")
    assert res_del.status_code == 204
