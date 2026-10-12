from backend.app.engine.editorial_model import (
    Advertisement, EditorialModel, EditorialPage, StoryPackage, build_edition,
    apply_ads_to_scene, compute_editorial_area, import_ads_csv, run_copyfit_ladder,
    tentative_variants, validate_editorial_model, validate_source_bound_text,
)
from backend.app.engine.editorial_migration import migrate_editorial_model
from fastapi.testclient import TestClient
from backend.app.main import app


def test_build_16_page_edition_and_centerfold():
    edition = build_edition(16, imposition=8)
    assert len(edition.page_plan) == 16
    assert edition.centerfold == [8, 9]
    assert edition.page_plan[0].type == "front"
    assert edition.page_plan[-1].type == "back"


def test_advertorial_without_label_is_hard_failure_and_area_is_recomputed():
    page = EditorialPage(no=2, ads=[Advertisement(id="a1", format="1/2-horizontal", is_advertorial=True)])
    model = EditorialModel(edition=build_edition(4, page_plan=[page.model_dump(mode="json")] + [p.model_dump(mode="json") for p in build_edition(4).page_plan[1:]]))
    errors = validate_editorial_model(model)
    assert any("advertorial" in error for error in errors)
    area = compute_editorial_area(page)
    assert 0 < area["ratio"] < 1


def test_tentative_ad_produces_two_switchable_variants():
    page = EditorialPage(no=2, ads=[Advertisement(id="a1", format="1/2-horizontal", status="tentative")])
    pages = [p.model_dump(mode="json") for p in build_edition(4).page_plan]
    pages[1] = page.model_dump(mode="json")
    model = EditorialModel(edition=build_edition(4, page_plan=pages))
    variants = tentative_variants(model, 2)
    assert len(variants) == 2
    assert len(variants[0].edition.page_plan[1].ads) == 1
    assert not variants[1].edition.page_plan[1].ads


def test_source_guard_rejects_new_number_and_copyfit_never_invents():
    guard = validate_source_bound_text("W 2027 r. podała Anna Nowak.", "W 2026 r. podała Anna Nowak.")
    assert guard["status"] == "fail"
    fitted = run_copyfit_ladder("To jest tekst źródłowy bez dopisywania faktów.", 15)
    assert "dopisywania" not in fitted["text"]


def test_migration_keeps_single_page_projects_open():
    migrated = migrate_editorial_model({"page_zone": "front_page", "stories": [{"id": "s1", "rank": "lead"}]})
    assert migrated["schema_version"] == 2
    assert migrated["edition"]["pages"] == 4
    assert migrated["stories"][0]["rank"] == "A"


def test_csv_import_has_locked_ad_and_fields():
    ads = import_ads_csv("id,format,advertiser_category\na1,full-page,telecom\n")
    assert ads[0].locked is True
    assert ads[0].advertiser_category == "telecom"


def test_project_edition_persists_ads_and_short_buffer():
    client = TestClient(app)
    project = client.post("/projects", json={"name": "Edition persistence acceptance"}).json()
    project_id = project["id"]
    assert client.get(f"/editorial-model/projects/{project_id}/edition").status_code == 200
    changed = client.post(f"/editorial-model/projects/{project_id}/edition/ads", json={
        "page_no": 2, "ads": [{"id": "tentative-1", "format": "1/2-horizontal", "status": "tentative"}]
    })
    assert changed.status_code == 200
    short = client.post(f"/editorial-model/projects/{project_id}/edition/shorts", json={
        "page_no": 2, "item": {"id": "short-1", "headline": "Krótki tytuł", "body": "Źródłowy tekst shorta"}
    })
    assert short.status_code == 200
    reloaded = client.get(f"/editorial-model/projects/{project_id}/edition").json()
    assert reloaded["page_plan"][1]["ads"][0]["status"] == "tentative"
    assert reloaded["shorts_blocks"][0]["items"][0]["id"] == "short-1"


def test_locked_ads_materialize_into_shared_scene_graph():
    from backend.app.engine.grammar import create_default_broadsheet_dna
    from backend.app.engine.solver import GridSolver
    from backend.app.models.schemas import PageInputMaterial, StoryInput
    dna = create_default_broadsheet_dna()
    scene = GridSolver(dna).solve(PageInputMaterial(stories=[StoryInput(id="s-ad", headline="Materiał", body="Tekst", importance=1)]))
    page = EditorialPage(no=1, ads=[Advertisement(id="adv", format="front-ear-right", is_advertorial=True, advertorial_label="materiał reklamowy")])
    apply_ads_to_scene(scene, page, dna)
    ad = next(element for element in scene.elements if element.id == "ad-adv")
    assert ad.locked is True and ad.approval_status == "protected"
    assert scene.metadata["advertorial_labels"]["ad-adv"] == "materiał reklamowy"


def test_removed_ad_moves_waiting_copy_into_short_buffer():
    client = TestClient(app)
    project_id = client.post("/projects", json={"name": "Ad removal acceptance"}).json()["id"]
    added = client.post(f"/editorial-model/projects/{project_id}/edition/ads", json={
        "page_no": 2, "ads": [{"id": "half", "format": "1/2-horizontal", "position": "bottom"}]
    })
    assert added.status_code == 200
    waiting = client.post(f"/editorial-model/projects/{project_id}/edition/shorts", json={
        "page_no": 2, "waiting": True,
        "item": {"id": "ready-1", "headline": "Tekst z poczekalni", "body": "Gotowy tekst źródłowy", "source": "editor"}
    })
    assert waiting.status_code == 200
    removed = client.post(f"/editorial-model/projects/{project_id}/edition/ads", json={
        "page_no": 2, "removed": ["half"]
    })
    assert removed.status_code == 200
    result = removed.json()
    assert result["change"]["freed_units"] == 96
    assert result["change"]["shorts_moved"] == ["ready-1"]
    assert result["edition"]["shorts_blocks"][0]["items"][0]["id"] == "ready-1"
    assert result["edition"]["waiting_room"] == []
