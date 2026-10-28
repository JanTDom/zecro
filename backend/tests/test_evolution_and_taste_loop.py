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


def test_map_elites_niche_computation_and_diversity():
    from backend.app.engine.evolution import compute_map_elites_niche
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)

    material = PageInputMaterial(
        masthead_title="TABLOID EXPRESS",
        stories=[
            StoryInput(id="s1", headline="WIELKI TEST ZDERZENIA I DYNAMIKI", body="Artykuł testowy.", importance=1.0,
                       images=[StoryImageInput(id="img-1", url="https://example.com/test1.png")]),
            StoryInput(id="s2", headline="DRUGI TEMAT DO ZDERZENIA", body="Drugi artykuł.", importance=0.8,
                       images=[StoryImageInput(id="img-2", url="https://example.com/test2.png")]),
            StoryInput(id="s3", headline="TRZECI TEMAT", body="Trzeci artykuł.", importance=0.5),
            StoryInput(id="s4", headline="CZWARTY TEMAT", body="Czwarty artykuł.", importance=0.4),
        ]
    )

    candidates = generator.generate(material, num_candidates=6, population_size=12, generations=3)
    assert len(candidates) >= 3
    niches = {compute_map_elites_niche(sg) for sg, _ in candidates}
    assert len(niches) >= 2


def test_taste_loop_reports_measured_duration_and_held_out_accuracy():
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    critic = LayoutCritic(dna)
    material = PageInputMaterial(stories=[StoryInput(id="s1", headline="Headline", body="Body text " * 20, importance=1.0)])
    candidates = generator.generate(material, num_candidates=2, population_size=12, generations=2, seed=7)
    signals = [
        PreferenceSignal(project_id="p", signal_type="pairwise_comparison", winner_candidate_id="a", loser_candidate_id="b", review_duration_sec=float(i + 1))
        for i in range(4)
    ]
    model = TasteLoopTrainer("p").train_reward_model(
        signals, {"a": candidates[0][0], "b": candidates[1][0]}, critic
    )
    assert model.sample_count == 4
    assert model.feedback_count == 4
    assert model.evaluated_sample_count == 1
    assert model.time_to_approve_avg_iterations == 2.5


def test_strategy_fingerprint_separates_architecture_from_geometry_fingerprint():
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    material = PageInputMaterial(stories=[StoryInput(id="s1", headline="Headline", body="Body text " * 20, importance=1.0)])
    candidates = generator.generate(material, num_candidates=5, population_size=18, generations=3, seed=12)
    strategy_vectors = {tuple(generator.critic.extract_strategy_feature_vector(scene)) for scene, _ in candidates}
    assert len(strategy_vectors) >= 2
    assert generator.last_run_stats["evaluated_unique_genomes"] > 0


def test_photo_and_headline_share_one_dominant_story_cluster_and_survive_selection():
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    material = PageInputMaterial(
        stories=[
            StoryInput(
                id="photo-story",
                headline="Lead story keeps its photo as a real layout choice",
                body="A sufficiently long body keeps copyfit meaningful. " * 18,
                importance=1.0,
                images=[StoryImageInput(id="lead-photo", url="https://example.com/lead.jpg", importance=1.0)],
            )
        ]
    )

    candidates = generator.generate(material, num_candidates=6, population_size=30, generations=3, seed=19)
    assert len(candidates) == 6
    assert all(critic.hard_gate.passed for _, critic in candidates)
    assert all(any(element.role == "photo" for element in scene.elements) for scene, _ in candidates)
    signatures = {
        tuple(generator.critic.extract_layout_feature_vector(scene))
        for scene, _ in candidates
    }
    assert len(signatures) >= 2
    for scene, _ in candidates:
        headline = next(element for element in scene.elements if element.role == "headline")
        assert "cutout-wrap" not in (headline.transgressions or [])


def test_nominal_72dpi_metadata_uses_effective_print_resolution():
    """A large raster with default 72-DPI metadata must not empty a run.

    Camera and generated JPEGs frequently carry 72 DPI metadata.  The press
    gate must calculate resolution from pixels divided by the placed frame,
    otherwise every photo-bearing genome is rejected before selection.
    """
    dna = create_default_tabloid_dna()
    generator = EvolutionaryLayoutGenerator(dna)
    material = PageInputMaterial(
        stories=[StoryInput(
            id="dpi-story",
            headline="Large raster remains usable at print size",
            body="A body with enough copy for the generated text frame. " * 14,
            importance=1.0,
            images=[StoryImageInput(
                id="raster",
                url="https://example.com/raster.jpg",
                width_px=1792,
                height_px=1008,
                dpi=72,
                aspect_ratio=1792 / 1008,
            )],
        )]
    )

    candidates = generator.generate(material, num_candidates=4, population_size=24, generations=3, seed=23)
    assert len(candidates) == 4
    assert all(critic.hard_gate.passed for _, critic in candidates)
    assert all(any(element.role == "photo" for element in scene.elements) for scene, _ in candidates)
