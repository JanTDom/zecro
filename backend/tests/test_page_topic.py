from backend.app.engine.page_topic import apply_page_topic, PAGE_TOPIC_DELTAS
from backend.app.models.schemas import PageInputMaterial, StyleBlend


def test_page_topics_nudge_layout_without_replacing_title_dna():
    base = StyleBlend(opinion_to_tabloid=.45, classical_to_avantgarde=.4, dense_to_photo=.5)
    politics = apply_page_topic(base, "politics")
    celebrities = apply_page_topic(base, "celebrities")
    assert politics.dense_to_photo < base.dense_to_photo < celebrities.dense_to_photo
    assert politics.opinion_to_tabloid < celebrities.opinion_to_tabloid
    assert base.dense_to_photo == .5
    assert set(PAGE_TOPIC_DELTAS) == {"general", "events", "politics", "science", "celebrities", "economy", "sports", "culture", "practical"}


def test_page_topic_is_part_of_generation_material():
    material = PageInputMaterial(page_topic="science", page_zone="spread")
    assert material.page_topic == "science"
    assert material.page_zone == "spread"
