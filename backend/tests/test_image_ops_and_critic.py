import pytest
import numpy as np
from PIL import Image
from backend.app.engine import image_ops
from backend.app.engine.image_ops import (
    simplify_douglas_peucker, extract_alpha_rings, extract_alpha_contour,
    offset_rings, offset_contour_polygon, contour_to_css_polygon, contour_to_svg_path
)
from backend.app.engine.grammar import create_default_broadsheet_dna
from backend.app.engine.solver import GridSolver
from backend.app.engine.critic import LayoutCritic, effective_print_dpi, cutout_geometry_issue
from backend.app.models.schemas import Element, Frame, PageInputMaterial, StoryInput


def _akimbo_mask(path):
    """Synthetic alpha mask: torso + an arm bent to the hip, enclosing a gap."""
    alpha = np.zeros((300, 200), dtype=np.uint8)
    alpha[40:300, 70:130] = 255          # torso
    alpha[60:70, 130:180] = 255          # upper arm
    alpha[60:200, 170:180] = 255         # forearm down
    alpha[190:200, 130:180] = 255        # hand back to hip
    rgba = np.dstack([np.full_like(alpha, 120)] * 3 + [alpha])
    Image.fromarray(rgba, "RGBA").save(path)


def test_real_mask_rings_keep_hole_and_concavity(tmp_path):
    pytest.importorskip("cv2", reason="OpenCV is required for real contour extraction")
    pytest.importorskip("shapely", reason="Shapely is required to verify offset geometry")
    mask = tmp_path / "akimbo.png"
    _akimbo_mask(mask)
    rings = extract_alpha_rings(str(mask), 100.0, 150.0)
    assert rings, "real mask must vectorise"
    assert len(rings[0]["holes"]) == 1, "gap between arm and torso must be a hole"
    outer = rings[0]["outer"]
    assert extract_alpha_contour(str(mask), 100.0, 150.0) == outer
    assert len(simplify_douglas_peucker([tuple(p) for p in outer], 2.0)) <= len(outer)
    off = offset_rings(outer, 2.0, rings[0]["holes"])
    assert off and off["holes"], "offset keeps the (shrunk) hole"
    from shapely.geometry import Polygon
    assert Polygon(off["outer"]).contains(Polygon(outer).buffer(-0.01))
    assert contour_to_css_polygon(outer, 100.0, 150.0).startswith("polygon(")
    d = contour_to_svg_path(outer, rings[0]["holes"])
    assert d.count("M ") == 2 and d.endswith("Z")


def test_no_synthetic_silhouette_anywhere(tmp_path):
    assert not hasattr(image_ops, "generate_default_silhouette_contour")
    assert extract_alpha_contour(str(tmp_path / "missing.png"), 50, 50) == []
    assert offset_contour_polygon([], 3.0) == []


def test_print_dpi_uses_weakest_axis_after_crop():
    photo = Element(role="photo", frame=Frame(x=10, y=10, w=200, h=250),
                    source_width_px=3000, source_height_px=1000,
                    crop_box=[.25, 0, .75, 1])
    assert effective_print_dpi(photo) == pytest.approx(101.6, rel=.01)
    photo.crop_box = [0, 0, 1, 1]
    assert effective_print_dpi(photo) == pytest.approx(101.6, rel=.01)
    photo.crop_box = [.4, 0, .6, 1]
    assert effective_print_dpi(photo) == pytest.approx(76.2, rel=.01)


def test_cutout_geometry_rejects_fragments_and_rectangular_masks():
    fragment = Element(id="fragment", role="photo", treatment="cutout",
                       frame=Frame(x=0, y=0, w=100, h=150),
                       contour_points=[[45, 55], [55, 55], [55, 95], [45, 95]])
    rectangle = Element(id="box", role="photo", treatment="cutout",
                        frame=Frame(x=0, y=0, w=100, h=150),
                        contour_points=[[0, 0], [100, 0], [100, 150], [0, 150]])
    subject = Element(id="person", role="photo", treatment="cutout",
                      frame=Frame(x=0, y=0, w=100, h=150),
                      contour_points=[[38, 5], [62, 5], [75, 55], [68, 145],
                                      [32, 145], [25, 55]])
    assert "fragment" in cutout_geometry_issue(fragment)
    assert "rectangular" in cutout_geometry_issue(rectangle)
    assert cutout_geometry_issue(subject) is None


def test_critic_evaluation_on_valid_page():
    dna = create_default_broadsheet_dna()
    solver = GridSolver(dna)
    critic = LayoutCritic(dna)

    material = PageInputMaterial(
        masthead_title="THE CHRONICLE",
        stories=[
            StoryInput(
                id="s1",
                kicker="WORLD NEWS",
                headline="CRITIC EVALUATES EDITORIAL BALANCE AND READING GRAVITY",
                lead="A strong lead paragraph introducing the story.",
                body="Extensive body text demonstrating full compliance with editorial standards.",
                importance=1.0
            )
        ]
    )

    sg = solver.solve(material)
    res = critic.evaluate(sg)

    assert res.hard_gate.passed is True
    assert res.heuristics.visual_balance_score > 0.0
    assert res.heuristics.composite_soft_score > 0.5
    assert res.total_fitness > 0.5
    assert "Passed:" in res.explanation
