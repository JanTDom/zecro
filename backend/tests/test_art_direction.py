from backend.app.engine.art_direction import build_art_direction_plan
from backend.app.engine.evolution import EvolutionaryLayoutGenerator
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.models.schemas import PageInputMaterial, StoryInput


def test_art_direction_binds_copy_slots_to_real_scene_frames():
    dna = create_default_tabloid_dna()
    material = PageInputMaterial(
        masthead_title="THE EDITORIAL TEST",
        stories=[
            StoryInput(
                id="lead",
                headline="A concrete headline with a defined editorial promise",
                deck="The deck explains the consequence without repeating the headline.",
                lead="The lead gives the reader the first verified fact and its location.",
                body="The body carries context and evidence. " * 12,
                importance=1.0,
            ),
        ],
    )
    generator = EvolutionaryLayoutGenerator(dna)
    scene, _ = generator.generate(material, num_candidates=1, population_size=16, generations=2, seed=17)[0]
    plan = build_art_direction_plan(dna, material, scene, {"sample_count": 1041, "archetype": "tabloid", "zone": "front"})

    # Corpus volume is evidence, not a calibrated confidence in taste.  The
    # deterministic planner reports zero until an explicit preference/VLM
    # calibration is supplied.
    assert plan.confidence == 0.0
    assert plan.corpus_evidence["sample_count"] == 1041
    assert plan.copy_slots
    assert {slot.element_ref for slot in plan.copy_slots}.issubset({element.id for element in scene.elements})
    assert all(slot.width_mm > 0 and slot.height_mm > 0 for slot in plan.copy_slots)
    assert any(slot.role == "headline" and slot.editorial_job for slot in plan.copy_slots)
