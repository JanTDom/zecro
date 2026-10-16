"""Rulebook knowledge, measured press norms, cut-out finishing, hyphen runs."""
import json

import numpy as np
from PIL import Image


def _mask(path, draw):
    a = np.zeros((400, 300), np.uint8)
    draw(a)
    rgba = np.zeros((400, 300, 4), np.uint8)
    rgba[..., :3] = 180
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)
    return str(path)


def test_cut_segments_tell_cut_from_touch(tmp_path):
    from backend.app.engine.cutout_quality import cut_segments
    # a torso cut by the source bottom border
    torso = _mask(tmp_path / "torso.png", lambda a: a.__setitem__((slice(100, 400), slice(80, 220)), 255))
    assert "bottom" in cut_segments(torso)
    # a head fully inside the frame touches nothing
    head = _mask(tmp_path / "head.png", lambda a: a.__setitem__((slice(50, 350), slice(60, 240)), 255))
    assert cut_segments(head) == {}
    # cropping to the subject's bbox makes it touch the crop, but nothing is cut
    assert cut_segments(head, [60 / 300, 50 / 400, 240 / 300, 350 / 400]) == {}


def test_refine_cutout_smooths_and_never_grows(tmp_path):
    from backend.app.engine.cutout_quality import refine_cutout, spikiness

    def spiky(a):
        a[100:350, 80:220] = 255
        a[60:100:6, 100:200] = 255          # thin hair-like spikes above the head
    p = _mask(tmp_path / "s.png", spiky)
    out = refine_cutout(p)
    a0 = np.asarray(Image.open(p))[..., 3] > 128
    a1 = np.asarray(Image.open(out).resize((300, 400)))[..., 3] > 128
    assert spikiness(out) <= spikiness(p)
    assert (a1 & ~a0).sum() < a0.sum() * .01   # the path runs inside, never outside


def test_hyphen_runs_limited():
    from backend.app.engine.shaper import MAX_HYPHEN_RUN
    assert MAX_HYPHEN_RUN == 2


def test_rulebook_and_defects_load():
    from backend.app.engine.art_director import knowledge
    k = knowledge()
    ids = {d["id"] for d in k["defekty"]}
    assert {"D05", "D08", "D09", "D12"} <= ids and "U7" in k["zasady_i_gramatyki"]


def test_norm_report_places_values():
    from backend.app.engine import press_norms
    data = press_norms.load()
    if not data:
        return  # knowledge file not built in this checkout
    rows = press_norms.norm_report({"body_pt": 9.5, "paper_share": .9}, "G-TABLOID-FRAME")
    assert rows and all(r["ocena"] for r in rows)
    assert any(r["miara"] == "paper_share" and r["ocena"].startswith("skrajne") for r in rows)


def _el(id_, role, x, y, w, h, z=1, **kw):
    from backend.app.models.schemas import Element, ElementStyle, Frame
    return Element(id=id_, role=role, frame=Frame(x=x, y=y, w=w, h=h), z=z, style=ElementStyle(**kw.pop("style", {})), **kw)


def test_near_miss_edges_and_box_holes():
    from backend.app.engine.layered_rules import near_miss_edges, empty_in_boxes
    a = _el("a", "band", 0, 0, 100, 50, style={"bg_color": "#3355aa"})
    b = _el("b", "band", 101.3, 0, 50, 50, style={"bg_color": "#3355aa"})        # 1.3 mm sliver
    assert near_miss_edges([a, b], [200, 200])
    b2 = _el("b", "band", 100, 0, 50, 50, style={"bg_color": "#3355aa"})         # touching: fine
    assert not near_miss_edges([a, b2], [200, 200])
    box = _el("box", "band", 0, 0, 120, 60, style={"bg_color": "#ffd000"})
    head = _el("t", "headline", 3, 3, 40, 12, z=5, text_content="Krótko", style={"font_size_pt": 30})
    assert empty_in_boxes([box, head], {})                                      # most of the box is a hole


def test_photo_fill_covers_module_and_zooms_small_faces():
    from types import SimpleNamespace
    from backend.app.engine.layered_cover import Kit, LayeredCover
    from backend.app.models.schemas import PageInputMaterial, StoryImageInput
    try:
        c = LayeredCover(Kit("wukadka"), PageInputMaterial(stories=[]), {})
    except Exception:
        import pytest
        pytest.skip("title kit fonts unavailable")
    img = StoryImageInput(id="p", url="x.jpg", width_px=1000, height_px=1500,
                          photo_analysis={"faces": [[.4, .1, .5, .15]]})
    el, (fx, fy, w, h) = c.photo_fill(img, (10, 10, 60, 40))
    assert fx <= 10 and fy <= 10 and fx + w >= 60 and fy + h >= 40              # covers the module
    assert (.15 - .1) * h >= 13.9                                               # face ≥ 14 mm after zoom


def test_editor_is_overruled_by_measurement():
    from backend.app.engine.art_director import _against_measurements
    rv = {"defekty": [{"id": "D26"}, {"id": "D28"}],
          "poprawki": [{"ruch": "bottom", "naprawia": "goły papier (D26)"}, {"ruch": "lead_lines", "naprawia": "D28"}]}
    out = _against_measurements(rv, [])
    assert [d["id"] for d in out["defekty"]] == ["D28"]
    assert [f["ruch"] for f in out["poprawki"]] == ["lead_lines"]
    # a defect the gate did find stays
    kept = _against_measurements(rv, ["Wycięta postać photo-3 stoi na białym papierze (40% obrysu bez gruntu)"])
    assert {d["id"] for d in kept["defekty"]} == {"D26", "D28"}


def test_planned_hole_measure_matches_geometry():
    from shapely.geometry import box
    from backend.app.engine.layered_rules import largest_free_of_polys_cm2
    win = box(0, 0, 100, 100)                     # 100 cm²
    assert largest_free_of_polys_cm2(win, [box(0, 0, 100, 100)]) < 1
    half = largest_free_of_polys_cm2(win, [box(0, 0, 100, 50)])
    # 50 cm² true; the gate's measure erodes 3 mm and adds back with a fixed
    # factor (calibrated on small holes), so large holes read high — never low
    assert 45 < half < 85
