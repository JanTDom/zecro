"""Layered tabloid cover: title kit, measured rules, composition."""
from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from backend.app.engine.layered_cover import Kit, Silhouette, compose_layered_cover
from backend.app.engine.layered_rules import layered_violations, required_contrast
from backend.app.models.schemas import (Element, ElementStyle, Frame, PageInputMaterial, PageMeta, SceneGraph,
                                StoryImageInput, StoryInput)


def _person(path, w=600, h=1200, flush_right=True):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((w * .25, h * .05, w * .75, h * .32), fill=(220, 180, 160, 255))           # head
    d.rectangle((w * .1, h * .3, w if flush_right else w * .9, h), fill=(240, 240, 240, 255))  # body
    im.save(path)
    return {"faces": [[.25, .05, .75, .32]], "alpha_bbox": [.1, .05, 1.0 if flush_right else .9, 1.0]}


def _kit_or_skip():
    kit = Kit("wukadka")
    if not kit.face("display").path:
        pytest.skip("font library without the Wukadka faces")
    return kit


def test_kit_resolves_exact_faces():
    kit = _kit_or_skip()
    assert kit.face("display").path and "Gotham" in kit.face("display").path
    assert kit.width("TAK NIE", "display", 100) > kit.width("TAK", "display", 100)


def test_wcag_large_text_rule():
    assert required_contrast(ElementStyle(font_size_pt=14, font_weight="700")) == 3.0
    assert required_contrast(ElementStyle(font_size_pt=14, font_weight="400")) == 4.5
    assert required_contrast(ElementStyle(font_size_pt=20)) == 3.0


def _scene(elements, **meta):
    return SceneGraph(page=PageMeta(trim=[264.6, 390]), elements=elements,
                      metadata={"composition": "layered", **meta})


def test_text_on_face_and_text_on_text_are_violations(tmp_path):
    mask = tmp_path / "p.png"
    _person(mask)
    photo = Element(id="ph", role="photo", frame=Frame(x=100, y=100, w=60, h=120), z=5, treatment="cutout",
                    image_url=str(mask), mask_ref=str(mask))
    face = [[115, 106, 145, 138]]
    on_face = Element(id="t1", role="headline", text_content="Twarz", z=9, story_ref="a",
                      frame=Frame(x=110, y=110, w=40, h=12), style=ElementStyle(font_size_pt=30, color="#000000"))
    other = Element(id="t2", role="body", text_content="Inny materiał leży tutaj", z=9, story_ref="b",
                    frame=Frame(x=112, y=112, w=40, h=12), style=ElementStyle(font_size_pt=9, color="#000000"))
    v = layered_violations(_scene([photo, on_face, other], face_boxes={"ph": face}, cutout_masks={"ph": str(mask)}))
    assert any("zakrywa twarz" in x for x in v)
    assert any("leży na tekście" in x for x in v)


def test_logo_coverage_is_measured_from_the_mask(tmp_path):
    mask = tmp_path / "p.png"
    _person(mask)
    logo = Element(id="logo", role="logo", frame=Frame(x=0, y=80, w=200, h=40), z=4)
    over = Element(id="ph", role="photo", frame=Frame(x=60, y=60, w=100, h=200), z=8, treatment="cutout",
                   image_url=str(mask), mask_ref=str(mask))
    meta = {"logo_rule": {"element": "logo", "max_covered_share": .12}, "cutout_masks": {"ph": str(mask)}}
    assert any("winiety" in x for x in layered_violations(_scene([logo, over], **meta)))
    beside = over.model_copy(update={"frame": Frame(x=196, y=60, w=60, h=120)})
    assert not any("winiety" in x for x in layered_violations(_scene([logo, beside], **meta)))


def test_silhouette_extent(tmp_path):
    mask = tmp_path / "p.png"
    _person(mask)
    sil = Silhouette(str(mask), Frame(x=0, y=0, w=60, h=120))
    x0, x1 = sil.x_extent(80, 100)
    assert 4 < x0 < 8 and x1 > 58


@pytest.mark.xfail(strict=True, reason="free-collage composer (superseded by framed_cover) puts cut-outs on bare paper and leaves dead fields: rulebook U15–U17 / D26–D27")
def test_compose_layered_cover_passes_its_rules(tmp_path):
    _kit_or_skip()
    m = tmp_path / "hero.png"
    an = _person(m)
    head = tmp_path / "head.png"
    an2 = _person(head, 400, 500, flush_right=False)
    hero_img = StoryImageInput(id="hero", url=str(m), alpha_mask_url=str(m), width_px=600, height_px=1200,
                               photo_analysis=an)
    head_img = StoryImageInput(id="head", url=str(head), alpha_mask_url=str(head), width_px=400, height_px=500,
                               photo_analysis=an2)
    material = PageInputMaterial(issue_number="1", issue_date="1 stycznia 2027", stories=[
        StoryInput(id="lead", rank="lead", kicker="Uwaga, pasażerowie", headline="Pociągi pojadą szybciej",
                   headline_emphasis=["szybciej"], page_ref="STR. 3",
                   lead="Nowy rozkład wchodzi w życie w niedzielę. Sprawdziliśmy, które kursy znikną. "
                        "Pokazujemy też, gdzie warto się przesiąść.", body="—"),
        StoryInput(id="hero", rank="second", kicker="Anna Nowak", headline="Wróciła na scenę po latach!",
                   headline_emphasis=["latach"], page_ref="STR. 5", images=[hero_img],
                   lead="Aktorka opowiada o nowej roli i o tym, dlaczego zniknęła z ekranu.", body="—"),
        StoryInput(id="t1", rank="teaser", group="interview", headline="Lubimy jeździć koleją",
                   page_ref="STR. 2", lead="Rozmawiamy z maszynistą z trzydziestoletnim stażem.", body="—"),
        StoryInput(id="t2", rank="teaser", headline="Co dalej z remontem", page_ref="STR. 6",
                   images=[head_img], body="—"),
    ])
    scene = compose_layered_cover(material, genes={"bottom": "corner"})
    assert scene.metadata["composition"] == "layered"
    roles = {e.role for e in scene.elements}
    assert {"logo", "photo", "headline", "lead"} <= roles
    stack = [e for e in scene.elements if e.flow_group == "stack-lead"]
    assert len(stack) >= 2
    v = layered_violations(scene)
    assert not v, v


@pytest.mark.xfail(strict=True, reason="free-collage composer (superseded by framed_cover) puts cut-outs on bare paper and leaves dead fields: rulebook U15–U17 / D26–D27")
def test_full_hard_gate_on_layered_cover(tmp_path):
    _kit_or_skip()
    from backend.app.engine.corpus_indexer import create_archetype_dnas
    from backend.app.engine.critic import LayoutCritic
    from backend.app.engine.layered_cover import load_kit
    m = tmp_path / "hero.png"
    an = _person(m, 1500, 3000)
    material = PageInputMaterial(issue_number="2", issue_date="2 stycznia 2027", stories=[
        StoryInput(id="lead", rank="lead", kicker="Tylko u nas", headline="Kolej wraca na stare tory",
                   headline_emphasis=["wraca"], page_ref="STR. 4",
                   lead="Po dwudziestu latach przerwy pociągi znów pojadą przez miasteczko. "
                        "Mieszkańcy czekali na to od dawna.", body="—"),
        StoryInput(id="hero", rank="second", kicker="Jan Kowalski", headline="Śpiewa dla pasażerów!",
                   headline_emphasis=["pasażerów"], page_ref="STR. 7",
                   images=[StoryImageInput(id="hero", url=str(m), alpha_mask_url=str(m), width_px=1500,
                                           height_px=3000, photo_analysis=an)],
                   lead="Muzyk z Grodziska daje koncerty w wagonach. Pasażerowie są zachwyceni.", body="—"),
    ])
    scene = compose_layered_cover(material, genes={"bottom": "strip"})
    kit = load_kit("wukadka")
    dna = create_archetype_dnas()["tabloid"]
    fmt = kit["format"]
    dna.format.trim_w_mm, dna.format.trim_h_mm = fmt["trim_mm"]
    dna.format.margin_left_mm = fmt["live"]["left"]
    dna.format.margin_right_mm = fmt["trim_mm"][0] - fmt["live"]["right"]
    dna.format.margin_top_mm = fmt["live"]["top"]
    dna.format.margin_bottom_mm = fmt["trim_mm"][1] - fmt["live"]["bottom"]
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert gate.passed, gate.violations


def test_skewed_frame_polygon_keeps_verticals():
    from backend.app.engine.critic import _frame_polygon
    pts = _frame_polygon(Frame(x=10, y=100, w=100, h=20, skew_y_deg=8.8))
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    assert x0 == x3 and x1 == x2          # verticals stay vertical
    assert y1 < y0 and abs((y0 - y1) - 100 * 0.15481) < .05  # right end rises by w·tan 8.8°


def test_framed_cover_every_element_is_anchored(tmp_path):
    _kit_or_skip()
    from backend.app.engine.framed_cover import compose_framed_cover
    m = tmp_path / "hero.png"
    an = _person(m, 1500, 3000)
    head = tmp_path / "head.png"
    an2 = _person(head, 800, 1000, flush_right=False)
    material = PageInputMaterial(issue_number="3", issue_date="3 stycznia 2027", stories=[
        StoryInput(id="lead", rank="lead", kicker="Uwaga pasażerowie", headline="Pociągi pojadą szybciej",
                   headline_emphasis=["szybciej"], page_ref="STR. 3",
                   lead="Nowy rozkład wchodzi w życie w niedzielę. Sprawdziliśmy, które kursy znikną. "
                        "Pokazujemy też, gdzie warto się przesiąść.", body="—"),
        StoryInput(id="hero", rank="second", kicker="Anna Nowak", headline="Wróciła na scenę po latach!",
                   headline_emphasis=["latach"], page_ref="STR. 5",
                   images=[StoryImageInput(id="hero", url=str(m), alpha_mask_url=str(m), width_px=1500,
                                           height_px=3000, photo_analysis=an)],
                   lead="Aktorka opowiada o nowej roli i o tym, dlaczego zniknęła z ekranu.", body="—"),
        StoryInput(id="t2", rank="teaser", headline="Co dalej z remontem", page_ref="STR. 6",
                   images=[StoryImageInput(id="head", url=str(head), alpha_mask_url=str(head), width_px=800,
                                           height_px=1000, photo_analysis=an2)], body="—"),
    ])
    scene = compose_framed_cover(material, genes={"bottom": "corner"})
    assert scene.metadata["modules"]["lead_window"]
    for e in scene.elements:
        assert e.id == "logo" or any(t.startswith("module:") for t in e.constraints or []), e.id
    lines = [e for e in scene.elements if e.flow_group == "stack-lead"]
    assert lines and all(abs(e.frame.skew_y_deg - 8.8) < 1e-6 and not e.frame.rotation_deg for e in lines)
    v = layered_violations(scene)
    assert not v, v
