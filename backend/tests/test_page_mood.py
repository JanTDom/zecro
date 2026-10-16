from backend.app.models.schemas import PageInputMaterial, StoryInput, StyleBlend
from backend.app.engine.page_mood import apply_page_mood, resolve_page_mood, story_color_roles


def _material(headline: str, topic="general", mood="auto"):
    return PageInputMaterial(page_topic=topic, editorial_mood=mood,
                             stories=[StoryInput(headline=headline, body="Tekst materiału", importance=1)])


def test_tragedy_takes_precedence_over_alarm_and_reduces_page_energy():
    profile = resolve_page_mood(_material("Alarm po tragedii. Nie żyje jedna osoba"))
    assert profile.name == "solemn"
    assert profile.allow_sensational_effects is False
    result = apply_page_mood(StyleBlend(opinion_to_tabloid=.9,
                                        classical_to_avantgarde=.7, dense_to_photo=.8), profile)
    assert result.opinion_to_tabloid < .9
    assert result.classical_to_avantgarde < .7


def test_explicit_editorial_intent_wins_and_topic_is_fallback():
    assert resolve_page_mood(_material("Wyniki badania", topic="science")).name == "analytical"
    assert resolve_page_mood(_material("Wyniki badania", topic="science", mood="celebratory")).name == "celebratory"


def test_sombre_story_accents_are_muted_without_changing_brand():
    from backend.app.models.schemas import TitleDNA
    dna = TitleDNA(name="Próba")
    accent, primary, highlight = story_color_roles(dna, "solemn")
    assert accent == primary == dna.palette.primary
    assert highlight == dna.palette.tint_bg
    assert dna.palette.secondary != accent
