from backend.app.engine.editorial_model import (
    Advertisement, EditorialModel, EditorialPage, StoryPackage, build_edition,
    compute_editorial_area, import_ads_csv, run_copyfit_ladder,
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
