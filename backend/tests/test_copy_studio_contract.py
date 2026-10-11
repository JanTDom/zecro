from backend.app.engine.art_direction import _copy_slot
from backend.app.engine.content_engine import rewrite_source_bound_copy
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.models.schemas import Element, ElementStyle, Frame


def test_source_bound_rewrite_never_fabricates_and_honours_locks():
    source = "Pierwsze zdanie. Decyzję podpisała Anna Nowak. To zamyka sprawę."
    text, meta = rewrite_source_bound_copy(source, role="body", target_words=30, locked_passages=["Anna Nowak"])
    assert text.replace("\u00a0", " ") == source
    assert meta["needs_more_source"] is True
    trimmed, _ = rewrite_source_bound_copy(source, role="body", target_words=3, locked_passages=["Anna Nowak"])
    assert "Anna Nowak" in trimmed


def test_copy_slot_does_not_expand_short_secondary_into_empty_frame():
    dna = create_default_tabloid_dna()
    element = Element(
        id="body-secondary",
        role="body",
        text_content="Krótka, kompletna informacja.",
        frame=Frame(x=10, y=10, w=100, h=200),
        style=ElementStyle(font_size_pt=9, line_height_pt=11, columns=2),
    )
    slot = _copy_slot(element, dna)
    assert slot is not None
    assert slot.fit_status == "PASS"
    assert slot.target_words == slot.source_words
    assert any("oddech" in item for item in slot.recommendations)
