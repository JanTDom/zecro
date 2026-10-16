"""Magazine morphologies and TV listing: behaviour, not snapshots."""
import random

import pytest
from PIL import Image, ImageDraw

from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.magazine_morphologies import CATALOG, feasible
from backend.app.engine.plan_composer import compose_planned_page
from backend.app.engine.tabloid_morphologies import topology_signature
from backend.app.engine.zone_solver import compose_page
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput, TVSlot


@pytest.fixture(scope="module")
def portrait(tmp_path_factory):
    path = tmp_path_factory.mktemp("img") / "portrait.jpg"
    img = Image.new("RGB", (3000, 4000), (205, 208, 212))
    draw = ImageDraw.Draw(img)
    draw.ellipse((1900, 700, 2500, 1400), fill=(120, 90, 80))
    draw.rectangle((1750, 1400, 2700, 4000), fill=(40, 40, 60))
    img.save(path)
    return path


def _magazine(portrait, analysis=None, stories=4):
    image = StoryImageInput(id="p", url=str(portrait), width_px=3000, height_px=4000, focal_point=[.73, .27],
                            photo_analysis=analysis)
    items = [StoryInput(id="a", importance=1, kicker="ROZMOWA", headline="Zaczynam wszystko od nowa",
                        deck="Aktorka o powrocie na scenę.", body="Tekst rozmowy. " * 40, images=[image])]
    for i, head in enumerate(["Miasto nad rzeką", "Nowa czytelnia", "Kuchnia jesieni"][: stories - 1]):
        items.append(StoryInput(id=f"s{i}", importance=.6 - i * .1, headline=head, body="Zapowiedź tekstu. " * 3,
                                images=[StoryImageInput(id=f"i{i}", url=str(portrait), width_px=3000, height_px=4000)]))
    return PageInputMaterial(masthead_title="PRÓBA", page_zone="front_page", stories=items)


PERSON = {"face_count": 1, "subject_box": [.15, .55, 1.0, .92], "gaze_direction": "left"}


def test_magazine_offers_several_topologies_that_pass_the_gate(portrait):
    dna = create_archetype_dnas()["editorial_magazine"]
    material = _magazine(portrait, PERSON)
    material.style_blend = dna.style_blend
    names = feasible(dna, material)
    assert set(CATALOG) <= set(names)
    signatures = set()
    for name in CATALOG:
        scene = compose_planned_page(dna, material, {"layout_mode": "photo-top", "cover_morphology": name})
        assert scene.metadata["cover_morphology"] == name
        gate = LayoutCritic(dna).evaluate_hard_gate(scene)
        assert gate.passed, (name, gate.violations[:3])
        signatures.add(topology_signature(scene))
    assert len(signatures) == len(CATALOG)


def test_portrait_cover_lines_use_measured_negative_space(portrait):
    dna = create_archetype_dnas()["editorial_magazine"]
    material = _magazine(portrait, PERSON)
    material.style_blend = dna.style_blend
    scene = compose_planned_page(dna, material, {"layout_mode": "photo-top", "cover_morphology": "portrait_cover"})
    lines = [e for e in scene.elements if "photo_negative_space" in (e.constraints or [])]
    assert lines and all(scene.metadata["negative_space_contrast"][e.id] >= 3 for e in lines)
    box = scene.metadata["photo_subject_boxes"]["photo-a"]
    assert all(e.frame.x + e.frame.w <= box[0] + 1 for e in lines), "lines stay left of the figure"
    # Moving a line onto the figure is caught by the hard gate.
    lines[0].frame.x = box[0] + 5
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert any("covers the subject" in v for v in gate.violations)


def test_portrait_cover_requires_a_person_and_free_side(portrait):
    dna = create_archetype_dnas()["editorial_magazine"]
    assert "portrait_cover" not in feasible(dna, _magazine(portrait, None))
    crowded = {"face_count": 2, "subject_box": [.1, .2, 1.0, .9]}
    assert "portrait_cover" not in feasible(dna, _magazine(portrait, crowded))


def test_magazine_is_not_a_tabloid_with_fewer_elements(portrait):
    profiles = create_archetype_dnas()
    material = _magazine(portrait, PERSON)
    mag = compose_planned_page(profiles["editorial_magazine"], material, {"layout_mode": "photo-top", "cover_morphology": "detail_still_life"})
    tab = compose_planned_page(profiles["tabloid"], material, {"layout_mode": "photo-top"})
    def planes(scene):
        page = scene.page.trim[0] * scene.page.trim[1]
        return sum(e.frame.w * e.frame.h for e in scene.elements
                   if e.role != "logo" and e.style and e.style.bg_color) / page
    assert planes(tab) > .05 and planes(mag) < planes(tab) * .3  # no colour-plane mosaic
    assert not any(abs(e.frame.rotation_deg or 0) > .5 for e in mag.elements)


def test_magazine_opening_spread_bleeds_photo_and_flows_body(portrait):
    dna = create_archetype_dnas()["editorial_magazine"]
    material = _magazine(portrait, PERSON)
    material.page_zone = "spread"
    scene = compose_page(dna, material, {"cover_morphology": "opening_spread"})
    assert scene.page.trim[0] == pytest.approx(dna.format.trim_w_mm * 2)
    photo = next(e for e in scene.elements if e.role == "photo")
    body = next(e for e in scene.elements if e.role == "body")
    assert photo.treatment == "full-bleed" and photo.frame.x < 0
    assert body.frame.x > dna.format.trim_w_mm and body.style.columns == 2
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed


def _schedule(n_stations=5, highlight=True):
    titles = ["Wiadomości", "Pogoda", "Serial obyczajowy", "Film dokumentalny", "Teleturniej", "Sport", "Koncert"]
    rng, slots = random.Random(4), []
    for station in ["TVP1", "TVP2", "POLSAT", "TVN", "TV4", "TV6"][:n_stations]:
        minute = 6 * 60
        while minute < 25 * 60:
            slots.append(TVSlot(station=station, time=f"{(minute // 60) % 24:02d}:{minute % 60:02d}", title=rng.choice(titles)))
            minute += rng.choice([30, 45, 60, 90])
    if highlight:
        slots[7].highlight = True
        slots[7].description = "Opis programu dnia."
    return slots


def test_tv_listing_is_navigable_by_station_and_hour():
    dna = create_archetype_dnas()["tv_guide"]
    slots = _schedule()
    material = PageInputMaterial(masthead_title="TELE", page_zone="back_page", tv_schedule=slots)
    scene = compose_page(dna, material, {})
    assert scene.metadata["architecture"] == "tv_listing"
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert gate.passed, gate.violations[:3]
    tabs = [e for e in scene.elements if (e.content_ref or "").startswith("tv.nav.")]
    assert [t.text_content for t in tabs] == ["TVP1", "TVP2", "POLSAT", "TVN", "TV4"]
    colors = scene.metadata["station_colors"]
    assert len(set(colors.values())) == 5  # colour identifies the station
    for tab in tabs:
        station = tab.content_ref.split(".")[-1]
        cells = [e for e in scene.elements if (e.content_ref or "").startswith(f"tv.{station}.") and e.role == "body"]
        assert cells and all(abs((c.frame.x - 1) - tab.frame.x) < .5 for c in cells), "column under its tab"
    # every programme is on the page, at the time it airs
    text = "\n".join(e.text_content or "" for e in scene.elements)
    for slot in slots:
        assert f"{slot.time}  {slot.title}" in text
    assert any((e.content_ref or "") == "tv.highlight.title" for e in scene.elements)


def test_tv_listing_never_drops_programmes_silently():
    dna = create_archetype_dnas()["tv_guide"]
    dense = []
    for station in ["TVP1", "TVP2", "POLSAT", "TVN", "TV4"]:
        for minute in range(6 * 60, 24 * 60, 10):
            dense.append(TVSlot(station=station, time=f"{minute // 60:02d}:{minute % 60:02d}", title="Bardzo długi tytuł programu"))
    scene = compose_page(dna, PageInputMaterial(masthead_title="TELE", page_zone="back_page", tv_schedule=dense), {})
    assert scene.metadata["missing_content_refs"]
    assert not LayoutCritic(dna).evaluate_hard_gate(scene).passed
    sixth = _schedule(n_stations=6, highlight=False)
    scene = compose_page(dna, PageInputMaterial(masthead_title="TELE", page_zone="back_page", tv_schedule=sixth), {})
    assert "tv.TV6" in scene.metadata["missing_content_refs"]
