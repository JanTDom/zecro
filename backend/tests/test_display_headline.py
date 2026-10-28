from backend.app.engine.display_headline import (
    compose_display_headline,
    compose_staged_display_headline,
    has_stranded_headline_word,
)


def test_compose_display_headline_multiline():
    plan = compose_display_headline(
        "Awantura w rządzie o miliardy z funduszu",
        width_mm=160.0,
        height_mm=40.0,
        preferred_size_pt=48.0,
        minimum_size_pt=20.0,
        font_families=["Inter, sans-serif"],
        min_lines=2,
        max_lines=3,
    )
    assert plan is not None
    assert len(plan.lines) in (2, 3)
    assert not has_stranded_headline_word(plan.lines)
    assert plan.font_size_pt >= 20.0


def test_compose_staged_display_headline():
    staged = compose_staged_display_headline(
        "SZOKUJĄCY wyrok w sprawie afery reprywatyzacyjnej",
        width_mm=180.0,
        height_mm=55.0,
        preferred_size_pt=50.0,
        minimum_size_pt=18.0,
        font_families=["Inter, sans-serif"],
        case_options=("normal", "upper"),
    )
    assert staged is not None
    assert staged.lead_word.upper().startswith("SZOKUJĄCY")
    assert staged.lead_size_pt > staged.sub_size_pt
    assert len(staged.sub_lines) >= 1
    assert "SZOKUJĄCY" in staged.text
