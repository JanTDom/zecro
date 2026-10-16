"""Behavioural tests: photo editing before geometry, morphologies, mood, export.

These tests check what the system does with the same material (topology,
photo-driven placement, hard-gate outcomes, renderer agreement), not
component snapshots.
"""
import zipfile
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.app.ai import photo_editor
from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.page_mood import mood_form, mood_palette
from backend.app.engine.plan_composer import compose_planned_page
from backend.app.engine.tabloid_morphologies import feasible_morphologies, topology_signature
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput

MORPHS = ("asymmetric_hero_rail", "diagonal_hero_entry", "dual_scale_collage", "photo_dominant_strip")


def _material(mood="urgent", analysis=None, lead_focal=(.5, .4)):
    def image(story_id, w=4200, h=2800):
        return StoryImageInput(id=f"im-{story_id}", url=f"/tmp/zecro-test-{story_id}.jpg", width_px=w, height_px=h,
                               dpi=300, focal_point=list(lead_focal) if story_id == "a" else [.5, .5],
                               photo_analysis=analysis if story_id == "a" else None)
    stories = [
        StoryInput(id="a", rank="lead", importance=1.0, kicker="PILNE", headline="Nie mamy jak wrócić do domu!",
                   body="Mieszkańcy pytają, kiedy skończy się remont i którędy dojdą do mieszkań. " * 4,
                   images=[image("a")]),
        StoryInput(id="b", rank="second", importance=.7, kicker="ROZMOWA", headline="Zaczyna wszystko od nowa",
                   body="Rozmówczyni opowiada o planach po przeprowadzce. " * 3, images=[image("b", 2400, 3200)]),
        StoryInput(id="c", rank="second", importance=.55, kicker="CENTRUM", headline="Rozkopali pół miasta",
                   body="Utrudnienia przy budowie nowego przejścia. " * 3, images=[image("c")]),
        StoryInput(id="d", rank="third", importance=.45, kicker="PO GODZINACH", headline="Tu też nie przejdziemy?",
                   body="Piesi pytają o objazd przy pobliskiej ulicy. " * 3, images=[image("d")]),
        StoryInput(id="e", rank="third", importance=.4, kicker="KOLEJ", headline="Pociąg ominie stację?",
                   body="Pasażerowie pytają o zmiany w rozkładzie. " * 3, images=[image("e")]),
    ]
    return PageInputMaterial(masthead_title="MIASTO DZIŚ", issue_date="15.10.2026", issue_number="1",
                             section_name="Wiadomości", page_zone="front_page", editorial_mood=mood, stories=stories)


@pytest.fixture()
def dna():
    profile = create_archetype_dnas()["tabloid"]
    return profile


def _compose(dna, material, morphology):
    material.style_blend = dna.style_blend
    return compose_planned_page(dna, material, {"layout_mode": "photo-top", "photo_treatment": "crop",
                                                "cover_morphology": morphology})


# ------------------------------------------------------------ diversity
def test_three_morphologies_differ_in_topology_and_pass_hard_gate(dna):
    material = _material()
    scenes = {name: _compose(dna, material, name) for name in MORPHS}
    signatures = set()
    for name, scene in scenes.items():
        assert scene.metadata["cover_morphology"] == name
        gate = LayoutCritic(dna).evaluate_hard_gate(scene)
        assert gate.passed, (name, gate.violations)
        dominant = {e.story_ref for e in scene.elements if e.importance >= .95 and e.role in {"headline", "photo"}}
        assert dominant == {"a"}, name  # exactly one dominant story
        signatures.add(topology_signature(scene))
    assert len(signatures) == len(MORPHS), "variants must differ in topology, not cosmetics"


def test_morphologies_differ_by_more_than_type_size(dna):
    material = _material()
    a, b = _compose(dna, material, "diagonal_hero_entry"), _compose(dna, material, "dual_scale_collage")
    hero = lambda s: next(e for e in s.elements if e.role == "photo" and e.story_ref == "a")
    head = lambda s: next(e for e in s.elements if e.role == "headline" and e.story_ref == "a")
    assert abs(hero(a).frame.w - hero(b).frame.w) > 40
    assert abs(head(a).frame.rotation_deg) >= 2.5 and abs(head(b).frame.rotation_deg) < .5
    assert any("intentional_photo_inset" in (e.constraints or []) for e in b.elements)


# ------------------------------------------------------- photo -> geometry
def test_gaze_direction_mirrors_directional_composition(dna):
    sides = {}
    for gaze in ("left", "right"):
        material = _material(analysis={"gaze_direction": gaze, "headline_safe_zone": "none"})
        assert "directional_tension" in feasible_morphologies(dna, material)
        scene = _compose(dna, material, "directional_tension")
        assert LayoutCritic(dna).evaluate_hard_gate(scene).passed
        hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
        head = next(e for e in scene.elements if e.role == "headline" and e.story_ref == "a")
        sides[gaze] = (hero.frame.x, head.frame.x)
        # the subject looks INTO the headline column
        assert (head.frame.x < hero.frame.x) == (gaze == "left")
    assert sides["left"][0] != sides["right"][0]


def test_directional_morphology_requires_photo_editor_direction(dna):
    assert "directional_tension" not in feasible_morphologies(dna, _material())


def test_headline_zone_follows_photo_editor_and_protects_subject(dna):
    top = _compose(dna, _material(analysis={"headline_safe_zone": "top"}, lead_focal=(.5, .8)), "photo_dominant_strip")
    bottom = _compose(dna, _material(analysis={"headline_safe_zone": "bottom"}, lead_focal=(.5, .25)), "photo_dominant_strip")
    y = lambda s: min(e.frame.y for e in s.elements if e.role == "headline" and e.story_ref == "a")
    assert y(top) < y(bottom)
    # Subject sits where the editor wanted the headline: the composer flips it.
    flipped = _compose(dna, _material(analysis={"headline_safe_zone": "bottom"}, lead_focal=(.5, .62)), "photo_dominant_strip")
    assert any(d.get("decision") == "headline_zone_flipped" for d in flipped.metadata["photo_driven_decisions"])


def test_collage_inset_never_covers_lead_subject(dna):
    for focal_x, expected in ((.8, "left"), (.2, "right")):
        scene = _compose(dna, _material(lead_focal=(focal_x, .4)), "dual_scale_collage")
        assert scene.metadata["inset_side"] == expected
        assert LayoutCritic(dna).evaluate_hard_gate(scene).passed
    scene = _compose(dna, _material(lead_focal=(.2, .4)), "dual_scale_collage")
    inset = next(e for e in scene.elements if "intentional_photo_inset" in (e.constraints or []))
    hero = next(e for e in scene.elements if e.role == "photo" and e.story_ref == "a")
    hero.focal_point = [.97, .2]  # pretend the subject sits under the inset
    hero.crop_box = [0, 0, 1, 1]
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert any("covers the subject" in v for v in gate.violations)


# ------------------------------------------------------------- mood -> form
def test_urgent_and_solemn_material_get_different_form(dna):
    urgent, solemn = mood_form(dna, "urgent"), mood_form(dna, "solemn")
    assert urgent.angle_deg < -4 and solemn.angle_deg == 0
    assert urgent.display_case == "upper" and solemn.display_case == "normal"
    assert urgent.transgression_scale > solemn.transgression_scale
    assert mood_palette(dna, "urgent")["strong"] != mood_palette(dna, "solemn")["strong"]
    assert mood_palette(dna, "solemn")["light"] != dna.palette.accent  # no tabloid yellow for grief
    assert "diagonal_hero_entry" in feasible_morphologies(dna, _material("urgent"))
    assert "diagonal_hero_entry" not in feasible_morphologies(dna, _material("solemn"))
    scene = _compose(dna, _material("entertainment"), "dual_scale_collage")
    assert scene.metadata["mood_palette"]["strong"] == dna.cover_grammar["mood_palettes"]["entertainment"]["strong"]


# ------------------------------------------------------------------ critic
def test_rotated_headline_outside_margins_is_rejected(dna):
    scene = _compose(dna, _material(), "dual_scale_collage")
    head = next(e for e in scene.elements if e.role == "headline" and e.story_ref == "a")
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed
    fmt = dna.format
    head.frame.x, head.frame.w = fmt.margin_left_mm, fmt.trim_w_mm - fmt.margin_left_mm - fmt.margin_right_mm
    head.frame.h = 40.0
    head.frame.rotation_deg = -12.0  # the unrotated box still fits; the rotated one does not
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert any("breaches" in v or "collision" in v for v in gate.violations if head.id in v)


# ------------------------------------------------------------------ export
def test_rotation_is_identical_in_svg_html_and_idml(dna, tmp_path):
    from backend.app.engine.renderers.html_renderer import HTMLRenderer
    from backend.app.engine.renderers.idml_renderer import IDMLRenderer
    from backend.app.engine.renderers.svg_renderer import SVGRenderer
    for story in "abcde":
        Image.new("RGB", (64, 48), (90, 90, 90)).save(f"/tmp/zecro-test-{story}.jpg")
    scene = _compose(dna, _material(), "diagonal_hero_entry")
    head = next(e for e in scene.elements if e.role == "headline" and e.story_ref == "a")
    assert abs(head.frame.rotation_deg) >= 2.5
    svg = SVGRenderer(dna).render(scene)
    html = HTMLRenderer(dna).render(scene)
    assert f'id="elem-g-{head.id}" transform="rotate({head.frame.rotation_deg:.1f}' in svg
    assert f"rotate({head.frame.rotation_deg}deg)" in html
    path = IDMLRenderer(dna).render_to_zip(scene, str(tmp_path / "page.idml"))
    with zipfile.ZipFile(path) as package:
        spread = next(package.read(n).decode() for n in package.namelist() if n.startswith("Spreads/"))
    import math
    a = math.cos(math.radians(head.frame.rotation_deg))
    tag = spread.split(f'Self="u_tf_{head.id}"')[1].split(">")[0]
    assert f'ItemTransform="{a:.6f}' in tag
    for element in scene.elements:
        if element.role not in {"rule"}:
            assert element.id in svg


# ------------------------------------------------------------ photo editor
def _photo_material(tmp_path, count=2):
    paths = []
    for index in range(count):
        path = tmp_path / f"c{index}.jpg"
        Image.new("RGB", (900, 600), (30 + index * 50, 60, 90)).save(path)
        paths.append(path)
    return PageInputMaterial(stories=[
        StoryInput(id="lead", importance=1, headline="Tłum ucieka ze stacji", body="Nagłe wydarzenie.",
                   images=[StoryImageInput(id=f"p{i}", url=str(p), width_px=900, height_px=600)
                           for i, p in enumerate(paths)]),
        StoryInput(id="other", importance=.4, headline="Inny temat", body="Treść."),
    ])


def _row(index, **values):
    base = {"index": index, "relevance": .8, "headline_match": .7, "newsworthiness": .6, "reportage": .5,
            "motion": .4, "technical_quality": .8, "print_quality_at_crop": .8, "depicts_claimed_subject": "yes",
            "posed": False, "emotion": "tension", "gaze_direction": "left", "headline_safe_zone": "top",
            "subject_box": [100, 300, 900, 700], "face_count": 2, "risks": [], "reason": "r"}
    base.update(values)
    return base


def test_photo_editor_prefers_dynamic_reporting_frame_and_records_features(monkeypatch, tmp_path):
    material = _photo_material(tmp_path)

    def fake(*_a, **kwargs):
        assert all(item["mime_type"] == "image/jpeg" for item in kwargs["images"])  # downscaled previews
        return SimpleNamespace(data={"scores": [
            _row(0, motion=.05, reportage=.1, posed=True, emotion="calm", reason="spokojny portret"),
            _row(1, motion=.9, reportage=.9, emotion="fear", reason="ucieczka w kadrze"),
        ]}, provenance={"provider": "gemini", "model": "test"})

    monkeypatch.setattr(photo_editor, "run_task", fake)
    selected, trace = photo_editor.select_story_photos(material)
    chosen = selected.stories[0].images[0]
    assert chosen.id == "p1"
    assert chosen.photo_analysis["emotion"] == "fear"
    assert chosen.photo_analysis["gaze_direction"] == "left"
    assert chosen.photo_analysis["dynamic"] > .8
    assert chosen.focal_point == [.5, round(.1 + .8 * .38, 4)]
    entry = trace[0]
    assert entry["verdict"] == "ok" and entry["reason"] == "ucieczka w kadrze"
    assert entry["alternatives"][0]["image_ref"] == "p0"
    assert photo_editor.lead_photo_stop(trace) is None


def test_single_weak_lead_photo_stops_before_geometry(monkeypatch, tmp_path):
    material = _photo_material(tmp_path, count=1)
    monkeypatch.setattr(photo_editor, "run_task", lambda *a, **k: SimpleNamespace(
        data={"scores": [_row(0, relevance=.2, headline_match=.1, reportage=.0, motion=.0, posed=True)]},
        provenance={}))
    _, trace = photo_editor.select_story_photos(material)
    stop = photo_editor.lead_photo_stop(trace)
    assert stop and stop["story_ref"] == "lead"
    assert stop["message"].startswith("Potrzebne inne zdjęcie")


def test_generation_api_returns_photo_needed_and_respects_override(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    project = client.post("/projects", json={"name": "Test zdjęć", "status": "ready"}).json()
    path = tmp_path / "weak.jpg"
    Image.new("RGB", (900, 600), (90, 90, 90)).save(path)
    monkeypatch.setattr(photo_editor, "run_task", lambda *a, **k: SimpleNamespace(
        data={"scores": [_row(0, relevance=.1, headline_match=.05, reportage=0, motion=0, posed=True)]},
        provenance={}))
    from backend.app.ai import visual_critic
    monkeypatch.setattr(visual_critic, "rerank", lambda pairs, dna, **k: (pairs, {"status": "skipped_in_test"}))
    payload = {"material": {"masthead_title": "TEST", "stories": [
        {"id": "s1", "headline": "Tłum ucieka ze stacji", "body": "Treść materiału. " * 10, "importance": 1,
         "images": [{"id": "w", "url": str(path), "width_px": 900, "height_px": 600}]},
        {"id": "s2", "headline": "Drugi temat dnia", "body": "Treść. " * 10, "importance": .5}]},
        "num_candidates": 2, "population_size": 10, "generations": 1, "visual_review": True}
    res = client.post(f"/projects/{project['id']}/generate", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "photo_needed"
    assert "Potrzebne inne zdjęcie" in res.json()["detail"]["message"]
    res = client.post(f"/projects/{project['id']}/generate", json={**payload, "accept_weak_photos": True})
    assert res.status_code == 201
    assert res.json()["stats"]["photo_selection"][0]["verdict"] == "needs_other_photo"


# --------------------------------------------------------------- evolution
def test_generator_returns_several_topologies_for_one_material(dna):
    from backend.app.engine.evolution import EvolutionaryLayoutGenerator
    material = _material()
    material.style_blend = dna.style_blend
    pairs = EvolutionaryLayoutGenerator(dna).generate(material=material, num_candidates=8, population_size=12,
                                                      generations=2, seed=7)
    assert all(crit.hard_gate.passed for _, crit in pairs)
    morphs = {sg.metadata.get("cover_morphology") for sg, crit in pairs}
    assert len(morphs & {"diagonal_hero_entry", "dual_scale_collage", "photo_dominant_strip"}) >= 3
    assert len({sg.metadata.get("topology") for sg, _ in pairs}) >= 3


def test_genres_get_different_architectures_and_guide_survives_five_stories():
    profiles = create_archetype_dnas()
    architectures = {}
    for genre in ("tabloid", "editorial_magazine", "tv_guide"):
        dna = profiles[genre]
        material = _material()
        material.style_blend = dna.style_blend
        scene = compose_planned_page(dna, material, {"layout_mode": "photo-top", "cover_morphology": "diagonal_hero_entry"})
        gate = LayoutCritic(dna).evaluate_hard_gate(scene)
        assert gate.passed, (genre, gate.violations[:3])
        architectures[genre] = scene.metadata["architecture"]
    assert len(set(architectures.values())) == 3


def test_photo_check_endpoint_reports_before_geometry(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    project = client.post("/projects", json={"name": "Kontrola zdjęć", "status": "ready"}).json()
    path = tmp_path / "x.jpg"
    Image.new("RGB", (900, 600), (90, 90, 90)).save(path)
    monkeypatch.setattr(photo_editor, "run_task", lambda *a, **k: SimpleNamespace(
        data={"scores": [_row(0, relevance=.1, headline_match=.05, reportage=0, motion=0, posed=True)]}, provenance={}))
    material = {"masthead_title": "T", "stories": [
        {"id": "s1", "headline": "Tłum ucieka", "body": "Treść.", "importance": 1,
         "images": [{"id": "w", "url": str(path), "width_px": 900, "height_px": 600}]}]}
    res = client.post(f"/projects/{project['id']}/photo-check", json={"material": material})
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False and body["message"].startswith("Potrzebne inne zdjęcie")
    assert not client.get(f"/projects/{project['id']}/runs").json(), "no layout was generated"
