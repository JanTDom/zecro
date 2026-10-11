import pytest
from backend.app.models.schemas import PageInputMaterial, StoryInput, StoryImageInput
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.engine.solver import GridSolver
from backend.app.engine.transgressions import TransgressionManager, STANDARD_TRANSGRESSIONS

def test_grid_solver_solves_valid_page():
    dna = create_default_tabloid_dna()
    solver = GridSolver(dna)

    material = PageInputMaterial(
        masthead_title="THE CITY POST",
        stories=[
            StoryInput(
                id="story-1",
                kicker="EXCLUSIVE",
                headline="SOLVER DELIVERS PRECISE MODULAR GRIDS",
                lead="A demonstration of deterministic layout solving.",
                body="Full body copy spanning the allocated columns with strict baseline grid alignment.",
                importance=1.0,
                images=[
                    StoryImageInput(
                        id="img-1",
                        url="https://example.com/photo.jpg",
                        caption="A test caption",
                        importance=0.8
                    )
                ]
            )
        ]
    )

    sg = solver.solve(material)
    assert sg.page.trim == [280.0, 390.0]
    assert len(sg.elements) >= 4
    assert any(e.role == "headline" for e in sg.elements)
    assert any(e.role == "photo" for e in sg.elements)
    assert any(e.role == "body" for e in sg.elements)
    assert len(sg.reading_order) >= 2

def test_transgression_budget_accounting():
    mgr = TransgressionManager(STANDARD_TRANSGRESSIONS, budget=0.8)
    dna = create_default_tabloid_dna()
    solver = GridSolver(dna)

    material = PageInputMaterial(
        masthead_title="THE DAILY",
        stories=[StoryInput(id="s1", headline="SAMPLE HEADLINE", body="Sample body text", importance=1.0)]
    )
    sg = solver.solve(material)

    within_budget, energy, budget = mgr.is_within_budget(sg)
    assert within_budget is True
    assert energy >= 0.0
