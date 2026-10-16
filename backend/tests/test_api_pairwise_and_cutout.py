"""Testy endpointów pojedynków A/B (Bradley-Terry) oraz automatycznego szparowania (cutout)."""
import io
import json
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.database import db
from backend.app.models.schemas import Project, TitleDNA

client = TestClient(app)


def _setup_project(project_id="test-proj-pairs"):
    proj = Project(
        id=project_id,
        name="Test Gazeta",
        newspaper_title="Test News",
        archetype="tabloid"
    )
    db.create_project(proj)
    from backend.app.engine.corpus_indexer import create_archetype_dnas
    dna = create_archetype_dnas()["tabloid"]
    db.save_title_dna(project_id, dna)
    return project_id


def test_pairwise_get_and_vote():
    pid = _setup_project("proj-pairs-1")

    # 1. Pobranie pary do pojedynku
    res = client.get(f"/projects/{pid}/pairs?composer=framed_cover:wukadka")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "pair_id" in data
    assert data["candidate_a"]["id"]
    assert data["candidate_b"]["id"]
    assert "features_a" in data and "features_b" in data
    assert data["features_a"]["balance"] is not None

    # 2. Głosowanie na kandydata A
    vote_payload = {
        "pair_id": data["pair_id"],
        "candidate_a_id": data["candidate_a"]["id"],
        "candidate_b_id": data["candidate_b"]["id"],
        "winner": "A",
        "features_a": data["features_a"],
        "features_b": data["features_b"],
        "archetype": data["archetype"],
        "notes": "Lepsze wyważenie optyczne i wyrazista gwiazda."
    }
    vote_res = client.post(f"/projects/{pid}/pairs/vote", json=vote_payload)
    assert vote_res.status_code == 200, vote_res.text
    vdata = vote_res.json()
    assert vdata["status"] == "recorded"
    assert vdata["winner"] == "A"
    assert vdata["total_human_pairs"] >= 1

    # 3. Status kalibracji
    st_res = client.get(f"/projects/{pid}/pairs/status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["human_pairs_count"] >= 1
    assert st_data["archetype"] == "tabloid"


def test_photo_cutout_endpoint(tmp_path, monkeypatch):
    pid = _setup_project("proj-cutout-1")

    # Przygotowanie prostego obrazu PNG z przezroczystością
    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # narysujmy czerwone koło w środku
    for x in range(30, 70):
        for y in range(30, 70):
            im.putpixel((x, y), (255, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)

    res = client.post(
        f"/projects/{pid}/cutout",
        files={"file": ("test_portrait.png", buf, "image/png")}
    )
    assert res.status_code == 200, res.text
    cdata = res.json()
    assert cdata["status"] in ("ready", "partial")
    assert "contour_polygon" in cdata
    assert "focal_point" in cdata
    assert "quality" in cdata
