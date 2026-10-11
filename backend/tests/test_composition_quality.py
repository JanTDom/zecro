"""Regression tests for editorially meaningful composition variants."""
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.copyfit import estimate_text_capacity
from backend.app.engine.zone_solver import compose_page
from backend.app.models.schemas import PageInputMaterial, StoryImageInput, StoryInput, TitleDNA


def _material(with_photo=True):
    image = StoryImageInput(url="photo.jpg", width_px=1792, height_px=1008) if with_photo else None
    return PageInputMaterial(stories=[
        StoryInput(
            id="lead", kicker="POLITYKA", headline="Nowy plan dla energetyki",
            deck="Rząd przedstawia plan zmian.", byline="Anna Nowak",
            lead="Eksperci przyjęli założenia reformy.",
            body="Ważne szczegóły planu i jego konsekwencje dla odbiorców. " * 4,
            images=[image] if image else [], importance=1.0,
        ),
        StoryInput(
            id="secondary", headline="Drewniane wieżowce zmieniają miasta",
            deck="Architektura i klimat.", byline="Jan Kowalski",
            lead="Projektanci pokazują nowe rozwiązania.",
            body="Nowe technologie zmieniają sposób projektowania.", importance=.6,
        ),
    ])


def test_compact_modules_keep_all_supplied_copy():
    dna = TitleDNA()
    sg = compose_page(dna, _material(), {"layout_mode": "dominant-left", "photo_placement": "inline_side"})
    assert sg.metadata["missing_content_refs"] == []
    refs = {e.content_ref for e in sg.elements}
    for field in ("headline", "deck", "byline", "lead", "body"):
        assert f"secondary.{field}" in refs


def test_architecture_modes_change_scene_geometry_and_pass_gate():
    dna = TitleDNA()
    critic = LayoutCritic(dna)
    signatures = {}
    for mode in ("dominant-left", "dominant-right", "stacked", "photo-top", "modular-grid"):
        sg = compose_page(dna, _material(), {"layout_mode": mode, "photo_placement": "inline_side"})
        result = critic.evaluate(sg)
        assert result.hard_gate.passed, result.hard_gate.violations
        signatures[mode] = tuple(
            (e.role, round(e.frame.x, 1), round(e.frame.y, 1), round(e.frame.w, 1), round(e.frame.h, 1))
            for e in sg.elements if e.role in {"headline", "photo", "body"}
        )
    assert len(set(signatures.values())) == len(signatures)


def test_one_line_copy_is_not_falsely_rounded_to_two_lines():
    report = estimate_text_capacity("Krótki tytuł", 80, 8, 1, 18, 21)
    assert report.estimated_lines == 1
    assert report.passes
