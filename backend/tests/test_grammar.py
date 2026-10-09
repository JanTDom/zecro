import pytest
from backend.app.models.schemas import PageInputMaterial, StoryInput, TitleDNA
from backend.app.engine.grammar import LayoutGrammar, create_default_broadsheet_dna, create_default_tabloid_dna
from backend.app.engine.polish_typography import sanitize_editorial_material

def test_default_broadsheet_dna():
    dna = create_default_broadsheet_dna()
    assert dna.grid.columns == 6
    assert dna.format.trim_w_mm == 350.0
    assert dna.format.trim_h_mm == 500.0
    assert dna.page_energy_budget == 0.8

def test_default_tabloid_dna():
    dna = create_default_tabloid_dna()
    assert dna.grid.columns == 5
    assert dna.page_energy_budget == 1.2
    assert dna.photo_rules.allow_cutout is True

def test_grammar_geometry_calculations():
    dna = create_default_broadsheet_dna()
    grammar = LayoutGrammar(dna)

    # Margin left=15, right=15, trim_w=350 -> printable=320
    # 6 cols, 5 gutters of 4.5 -> 320 - 22.5 = 297.5 / 6 = 49.583 mm
    assert grammar.col_w_mm > 40.0
    assert grammar.col_to_x_mm(0) == dna.format.margin_left_mm
    assert grammar.span_to_w_mm(1) == grammar.col_w_mm
    assert grammar.span_to_w_mm(2) > grammar.col_w_mm * 2

def test_baseline_snapping():
    dna = create_default_broadsheet_dna()
    grammar = LayoutGrammar(dna)
    snapped = grammar.snap_to_baseline(25.3)
    assert snapped >= dna.format.margin_top_mm


def test_locked_passage_survives_polish_cleanup_inside_surrounding_copy():
    locked = '"Jan Kowalski"'
    material = PageInputMaterial(stories=[StoryInput(
        headline='Relacja',
        body='W tekście pada cytat "Jan Kowalski" i zdanie z w oraz do redakcji.',
        locked_passages=[locked],
    )])
    cleaned = sanitize_editorial_material(material)
    body = cleaned.stories[0].body
    assert locked in body
    assert 'z\u00a0w' in body
    assert 'oraz\u00a0do' in body
