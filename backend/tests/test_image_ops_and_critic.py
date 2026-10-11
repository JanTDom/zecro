import pytest
from backend.app.engine.image_ops import (
    simplify_douglas_peucker, generate_default_silhouette_contour,
    offset_contour_polygon, contour_to_css_polygon, contour_to_svg_path
)
from backend.app.engine.grammar import create_default_broadsheet_dna
from backend.app.engine.solver import GridSolver
from backend.app.engine.critic import LayoutCritic
from backend.app.models.schemas import PageInputMaterial, StoryInput

def test_image_ops_contour_helpers():
    poly = generate_default_silhouette_contour(100.0, 150.0)
    assert len(poly) >= 5

    simplified = simplify_douglas_peucker([(p[0], p[1]) for p in poly], tolerance=2.0)
    assert len(simplified) <= len(poly)

    dilated = offset_contour_polygon(poly, offset_mm=3.5)
    assert len(dilated) == len(poly)

    css_poly = contour_to_css_polygon(poly, 100.0, 150.0)
    assert css_poly.startswith("polygon(")

    svg_path = contour_to_svg_path(poly)
    assert svg_path.startswith("M ")
    assert svg_path.endswith("Z")

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
