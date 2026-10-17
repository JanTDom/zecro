"""
Tests for Zecro Editorial Architecture Suite:
- Flatplan & Multipage Pagination Engine
- InDesign Archive Dissector
- RIP Soft-Proofing & TAC Simulator
- Editorial Asset Curation & Art Buyer
- Editorial Document Ingestion & Fact-Guard Taxonomy
- Taste Preference Active Learner
- Press Cartography & Vector Infographics
"""

import json
from pathlib import Path

from scripts.art_buyer import inspect_editorial_image
from scripts.dissect_indesign import dissect_editorial_directory
from scripts.editorial_cartography import generate_locator_map_svg
from scripts.flatplan_engine import create_default_issue
from scripts.ingest_editorial_doc import extract_facts, parse_raw_paragraphs
from scripts.rip_simulator import compute_tac_cmyk, simulate_newsprint_dot_gain
from scripts.tune_preference_model import (
    LayoutCandidate,
    PreferenceWeights,
    calculate_pairwise_uncertainty,
    select_active_learning_pair,
    update_weights_bradley_terry,
)


def test_flatplan_pagination_signature_and_spreads():
    issue = create_default_issue(title="Wukadka", issue_nr=21, pages=8)
    assert issue.page_count == 8
    assert len(issue.pages) == 8
    # Signatures must be divisible by 4
    assert len(issue.validate_signatures()) == 0

    # Spreads verification
    spreads = issue.get_spreads()
    assert len(spreads) >= 4  # Cover, 2-3, 4-5, 6-7, back cover
    assert spreads[0]["spread_id"] == "cover"
    assert spreads[0]["right"].page_number == 1
    assert spreads[0]["right"].side == "recto"

    # Odd page count failure
    bad_issue = create_default_issue(title="Wukadka", issue_nr=21, pages=7)
    assert len(bad_issue.validate_signatures()) > 0


def test_indesign_archive_dissection_wukadka():
    wukadka_path = Path("/Users/macbookpro/Desktop/LAYOUTY/WUKADKA/NR21")
    dna = dissect_editorial_directory(wukadka_path)
    assert dna.title_name == "NR21"
    assert dna.grid.columns == 5
    assert dna.grid.page_width_mm == 289.0
    assert dna.grid.page_height_mm == 380.0
    assert len(dna.swatches) >= 3
    assert any(s.name == "Wukadka_Navy" for s in dna.swatches)
    assert len(dna.paragraph_styles) >= 4


def test_rip_simulator_tac_and_dot_gain():
    # TAC passing (210% <= 240%)
    res_pass = compute_tac_cmyk(c=50, m=40, y=40, k=80, max_allowed=240.0)
    assert res_pass.is_tac_compliant is True
    assert res_pass.max_tac_measured == 210.0

    # TAC failing (280% > 240%)
    res_fail = compute_tac_cmyk(c=80, m=70, y=60, k=70, max_allowed=240.0)
    assert res_fail.is_tac_compliant is False
    assert res_fail.risk_level == "CRITICAL"

    # Dot gain simulation (newsprint shifts ~25-30% on midtones)
    dg = simulate_newsprint_dot_gain(nominal_50_pct=50.0, substrate="newsprint")
    assert dg.simulated_printed_pct > 65.0
    assert dg.dot_gain_curve_shift_pct > 15.0


def test_art_buyer_ppi_and_ethical_guard():
    # High resolution image (603 PPI) -> PASS
    high_res = inspect_editorial_image(
        image_name="DSC_0222.JPG",
        width_px=4288,
        height_px=2848,
        frame_width_mm=180.0,
        frame_height_mm=120.0,
    )
    assert high_res.is_ppi_pass is True
    assert high_res.effective_ppi > 500.0
    assert high_res.ethical_guards_pass is True

    # Low resolution image (72 PPI) -> FAIL
    low_res = inspect_editorial_image(
        image_name="thumb.jpg",
        width_px=200,
        height_px=150,
        frame_width_mm=100.0,
        frame_height_mm=75.0,
    )
    assert low_res.is_ppi_pass is False

    # Ethical guard violation on tragedy: circular badge on accident -> FAIL
    tragedy_viol = inspect_editorial_image(
        image_name="victim.jpg",
        width_px=1500,
        height_px=1500,
        frame_width_mm=80.0,
        frame_height_mm=80.0,
        is_sensitive_tragedy=True,
        is_circular_badge=True,
    )
    assert tragedy_viol.ethical_guards_pass is False
    assert any("BŁĄD ETYCZNY" in err for err in tragedy_viol.issues)


def test_editorial_doc_ingestion_and_facts():
    sample_text = (
        "Remont Linii WKD pod Warszawą\n\n"
        "W dniu 25 czerwca 2023 r. ruszyła kluczowa modernizacja torowiska za kwotę 14 mln zł.\n\n"
        "Pociągi będą kursować z ograniczeniem do 40 km/h do 3 września 2023 r."
    )
    paragraphs = sample_text.split("\n\n")
    pkg = parse_raw_paragraphs("artykul.txt", paragraphs)

    assert pkg.headline == "Remont Linii WKD pod Warszawą"
    assert "25 czerwca" in pkg.lead
    assert len(pkg.frozen_claims) >= 3

    # Check extracted categories
    categories = {c.category for c in pkg.frozen_claims}
    assert "date" in categories
    assert "currency" in categories


def test_taste_preference_active_learning():
    weights = PreferenceWeights(hierarchy_contrast=1.5, whitespace_balance=1.0)
    c1 = LayoutCandidate("cand_1", "hero", {"hierarchy_contrast": 0.8, "whitespace_balance": 0.5})
    c2 = LayoutCandidate("cand_2", "grid", {"hierarchy_contrast": 0.5, "whitespace_balance": 0.8})

    cand_a, cand_b, unc = select_active_learning_pair([c1, c2], weights)
    assert cand_a.candidate_id == "cand_1"
    assert cand_b.candidate_id == "cand_2"
    assert unc > 0.0

    # Winner cand_1 updates weights
    updated = update_weights_bradley_terry(weights, winner=c1, loser=c2, learning_rate=0.1)
    # Since c1 has higher hierarchy_contrast, its weight should increase or adjust
    assert updated.hierarchy_contrast >= weights.hierarchy_contrast


def test_editorial_cartography_svg_generation():
    svg = generate_locator_map_svg(
        title="Remont Torowiska",
        location_label="Stacja WKD",
        width_mm=104.0,
        height_mm=70.0,
    )
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "Remont Torowiska" in svg
    assert "Stacja WKD" in svg
    assert 'class="compass"' in svg
    assert "250 m" in svg


def test_api_ingest_doc_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    content = b"Wielki Sukces Nowego Wydania\n\nW dniu 17 pazdziernika 2026 r. zakonczono prace za 120 tys. zl.\n\nKolejne wydanie w krotce."
    response = client.post(
        "/editorial/ingest-doc",
        files={"file": ("manuskrypt.txt", content, "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["headline"] == "Wielki Sukces Nowego Wydania"
    assert len(data["frozen_claims"]) >= 1


def test_api_pairwise_uncertainty_sampling():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    proj_resp = client.get("/projects")
    if proj_resp.status_code == 200:
        projects = proj_resp.json()
        if projects:
            pid = projects[0]["id"]
            res = client.get(f"/projects/{pid}/pairs")
            if res.status_code == 200:
                data = res.json()
                assert data["selection_method"] == "uncertainty_sampling"
                assert "active_learning_entropy" in data

