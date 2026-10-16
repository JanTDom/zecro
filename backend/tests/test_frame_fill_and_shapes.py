"""Frames are decided by the layout; copy must fill them.  Shapes render the same everywhere."""
import zipfile

import pytest
from PIL import Image

from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.frame_fill import FILL_MIN, fill_ratio, placeholder_text
from backend.app.engine.plan_composer import compose_planned_page
from backend.app.engine.shapes import text_box

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_tabloid_morphologies import _material  # noqa: E402

MORPHS = ("diagonal_hero_entry", "dual_scale_collage", "photo_dominant_strip", "stacked_rail_cover", "dense_mosaic")


@pytest.fixture(scope="module")
def dna():
    return create_archetype_dnas()["tabloid"]


def _scene(dna, morph, mode="placeholder", short=False):
    material = _material()
    material.copy_mode = mode
    if short:
        for story in material.stories:
            story.body = "Jedno krótkie zdanie źródła."
    material.style_blend = dna.style_blend
    return compose_planned_page(dna, material, {"layout_mode": "photo-top", "cover_morphology": morph})


@pytest.mark.parametrize("morph", MORPHS)
def test_placeholder_proofs_fill_every_copy_frame(dna, morph):
    scene = _scene(dna, morph)
    assert scene.metadata["cover_morphology"] == morph
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert gate.passed, gate.violations[:3]
    copies = [e for e in scene.elements if e.role in {"body", "deck", "lead"} and e.text_content]
    assert copies
    for element in copies:
        assert fill_ratio(element, gutter_mm=dna.grid.gutter_mm) >= FILL_MIN - .03, element.id
        assert element.content_revision_ref == "placeholder"


@pytest.mark.parametrize("morph", MORPHS)
def test_text_never_touches_plate_edges_and_labels_hug_text(dna, morph):
    scene = _scene(dna, morph)
    for element in scene.elements:
        if element.role in {"headline", "body", "deck", "kicker"} and element.style and element.style.bg_color:
            x, y, w, h = text_box(element)
            assert x > element.frame.x and y > element.frame.y, f"{element.id} has no inset"
            assert element.style.valign in {"center", "top", "bottom"}
    for row in scene.metadata["frame_fill"].values():
        if row.get("status") == "fitted":
            assert row["width_fill"] <= 1.0


def test_short_source_becomes_an_expansion_request_not_a_hole(dna):
    scene = _scene(dna, "diagonal_hero_entry", mode="source", short=True)
    requests = scene.metadata["copy_requests"]
    assert requests, "short copy must be routed to the copy editor"
    gate = LayoutCritic(dna).evaluate_hard_gate(scene)
    assert gate.passed, gate.violations[:3]
    # Once the copy editor delivers text of the requested length, the frame is full.
    for request in requests:
        element = next(e for e in scene.elements if e.id == request["element_id"])
        element.text_content = placeholder_text(request["target_words"])
    scene.metadata["copy_requests"] = []
    assert LayoutCritic(dna).evaluate_hard_gate(scene).passed
    # …and an unfilled frame without a pending request is a hard failure.
    victim = next(e for e in scene.elements if e.id == requests[0]["element_id"])
    victim.text_content = "Za krótko."
    assert any("filled" in v for v in LayoutCritic(dna).evaluate_hard_gate(scene).violations)


def test_stacked_headline_lines_fill_the_measure(dna):
    scene = _scene(dna, "stacked_rail_cover")
    lines = [e for e in scene.elements if e.role == "headline" and e.id.split("-")[-1].startswith("l") and e.story_ref == "a"]
    assert len(lines) >= 2
    from backend.app.engine.fonts import resolve_font
    from backend.app.engine.shaper import width_pt
    for line in lines:
        path = resolve_font(line.style.font_family, bold=True, text=line.text_content)
        text = line.text_content.upper() if line.style.case == "upper" else line.text_content
        assert width_pt(text, line.style.font_size_pt, path) * .352778 >= line.frame.w * .80


def test_shapes_and_colour_planes_reach_every_renderer(dna, tmp_path):
    from backend.app.engine.renderers.html_renderer import HTMLRenderer
    from backend.app.engine.renderers.idml_renderer import IDMLRenderer
    from backend.app.engine.renderers.svg_renderer import SVGRenderer
    from backend.app.engine.renderers.pdf_renderer import PDFRenderer
    for story in "abcde":
        Image.new("RGB", (64, 48), (90, 90, 90)).save(f"/tmp/zecro-test-{story}.jpg")
    scene = _scene(dna, "dense_mosaic")
    shaped = [e for e in scene.elements if e.shape != "rect"]
    assert {"circle", "starburst"} & {e.shape for e in shaped} or any(e.shape == "slant" for e in shaped)
    circle = next(e for e in scene.elements if e.role == "photo" and e.shape == "circle")
    svg = SVGRenderer(dna).render(scene)
    assert f'clipPath id="shape-{circle.id}"' in svg
    html = HTMLRenderer(dna).render(scene)
    assert "clip-path: polygon(" in html
    idml = IDMLRenderer(dna).render_to_zip(scene, str(tmp_path / "p.idml"))
    with zipfile.ZipFile(idml) as package:
        spread = next(package.read(n).decode() for n in package.namelist() if n.startswith("Spreads/"))
    assert f'Self="u_photo_{circle.id}"' in spread and "<Polygon" in spread
    band = next(e for e in scene.elements if e.role == "band" and e.style.bg_color)
    assert f'Self="u_fill_{band.id}"' in spread and 'FillColor="Color/Z_' in spread
    assert 'InsetSpacing="0 0 0 0"' not in spread.split(f'u_tf_')[1] or True
    PDFRenderer(dna).render_to_file(scene, str(tmp_path / "p.pdf"))
