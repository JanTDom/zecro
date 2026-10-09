import pytest
from backend.app.models.schemas import PageInputMaterial, StoryInput, StoryImageInput, PreferenceSignal
from backend.app.engine.grammar import create_default_tabloid_dna
from backend.app.engine.evolution import EvolutionaryLayoutGenerator
from backend.app.engine.taste_loop import TasteLoopTrainer
from backend.app.engine.critic import LayoutCritic

def test_evolutionary_generation():
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)

    material = PageInputMaterial(
        masthead_title="TABLOID EXPRESS",
        stories=[
            StoryInput(
                id="s1",
                headline="AI LAYOUT ENGINE DELIVERS NOVEL DESIGNS",
                lead="Evolutionary algorithm explores parameter space.",
                body="Body text formatted into columns with tension budget enforcement.",
                importance=1.0,
                images=[StoryImageInput(id="img-1", url="https://example.com/cutout.png", is_cutout_candidate=True)]
            )
        ]
    )

    candidates = generator.generate(material, num_candidates=4, population_size=10, generations=3)
    assert len(candidates) >= 2
    for sg, crit in candidates:
        assert sg.page.trim == [280.0, 390.0]
        assert crit.total_fitness > 0.0

def test_taste_loop_pairwise_training():
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    critic = LayoutCritic(dna)

    material = PageInputMaterial(
        masthead_title="TABLOID EXPRESS",
        stories=[StoryInput(id="s1", headline="SAMPLE HEADLINE", body="Sample body text", importance=1.0)]
    )

    candidates = generator.generate(material, num_candidates=2, population_size=10, generations=2)
    sg1, _ = candidates[0]
    sg2, _ = candidates[1]

    signals = [
        PreferenceSignal(
            project_id="proj-test",
            signal_type="pairwise_comparison",
            winner_candidate_id="cand-1",
            loser_candidate_id="cand-2"
        )
    ]

    cand_map = {"cand-1": sg1, "cand-2": sg2}
    trainer = TasteLoopTrainer("proj-test")
    model = trainer.train_reward_model(signals, cand_map, critic)

    assert model.project_id == "proj-test"
    assert model.sample_count == 1
    assert model.human_preference_win_rate == 1.0
    assert len(model.feature_weights) == 10
