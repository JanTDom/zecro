from types import SimpleNamespace

from backend.app.api import generate
from backend.app.models.schemas import PageInputMaterial, StoryInput, StyleBlend


def _setup(monkeypatch, *, guard_status="supported", hard_pass=True):
    element = SimpleNamespace(
        id="body-lead", role="body", story_ref="lead", text_content="Krótki tekst.",
        frame=SimpleNamespace(w=80.0, h=50.0),
        style=SimpleNamespace(columns=1, font_size_pt=9.5, line_height_pt=11.5, font_family="Georgia"),
    )
    scene = SimpleNamespace(elements=[element], metadata={"fit_adjustments": [
        {"action": "copyfit_shorten", "element_ref": "body-lead"}]})
    critic = SimpleNamespace(dna=SimpleNamespace(grid=SimpleNamespace(gutter_mm=4.0)),
                             evaluate=lambda scene: SimpleNamespace(hard_gate=SimpleNamespace(passed=hard_pass)))
    material = PageInputMaterial(stories=[StoryInput(id="lead", headline="Tytuł", body="Dłuższy tekst źródłowy o sprawie.")],
                                 style_blend=StyleBlend(opinion_to_tabloid=.85))
    monkeypatch.setattr(generate.registry, "resolve", lambda *_: SimpleNamespace(status="ready"))
    monkeypatch.setattr("backend.app.ai.editorial_writer.fit_to_frame", lambda *args, **kwargs: SimpleNamespace(
        text="Tekst redakcyjny o sprawie.", approvable=guard_status == "supported",
        guard={"provenance": {"ai_pass": {"status": "supported"}}},
        provenance={"provider": "gemini", "model": "test-model"}))
    monkeypatch.setattr("backend.app.engine.copyfit.estimate_text_capacity", lambda *args, **kwargs: SimpleNamespace(passes=True))
    return [(scene, SimpleNamespace(hard_gate=SimpleNamespace(passed=True)))], material, critic


def test_ai_copy_is_applied_only_after_source_and_layout_checks(monkeypatch):
    pairs, material, critic = _setup(monkeypatch)
    result, status = generate._refine_copy_with_ai(pairs, material, "project", critic)
    assert status["status"] == "applied"
    assert result[0][0].elements[0].text_content == "Tekst redakcyjny o sprawie."
    assert result[0][0].metadata["copy_ai"]["accepted"][0]["provider"] == "gemini"


def test_ai_copy_keeps_original_when_hard_gate_fails(monkeypatch):
    pairs, material, critic = _setup(monkeypatch, hard_pass=False)
    result, status = generate._refine_copy_with_ai(pairs, material, "project", critic)
    assert status["status"] == "fallback"
    assert result[0][0].elements[0].text_content == "Krótki tekst."


def test_ai_adapts_source_bound_lead_headline_to_the_page(monkeypatch):
    pairs, material, critic = _setup(monkeypatch)
    scene = pairs[0][0]
    scene.metadata["fit_adjustments"] = []
    scene.elements = [SimpleNamespace(
        id="headline-lead", role="headline", story_ref="lead", text_content="Tytuł",
        constraints=["must_dominate"], frame=SimpleNamespace(w=120.0, h=34.0),
        style=SimpleNamespace(columns=1, font_size_pt=42.0, line_height_pt=45.0, font_family="Roboto Condensed"),
    )]
    result, status = generate._refine_copy_with_ai(pairs, material, "project", critic)
    assert status["status"] == "applied"
    assert status["attempted"] == 1
    assert result[0][0].elements[0].text_content == "Tekst redakcyjny o sprawie."
    assert scene.metadata["fit_adjustments"][-1]["field"] == "headline"
