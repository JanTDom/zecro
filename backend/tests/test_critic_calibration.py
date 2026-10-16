"""Critic calibration from A/B pairs: fitting, validity gate and effect."""
import random

from backend.app.engine import critic_calibration as cc
from backend.app.engine.corpus_indexer import create_archetype_dnas
from backend.app.engine.critic import LayoutCritic


def _features(rng, good):
    row = {f: rng.random() for f in cc.FEATURES}
    row["module_uniformity"] = rng.uniform(0, .4) if good else rng.uniform(.6, 1)
    row["hero_photo_share"] = rng.uniform(.4, .7) if good else rng.uniform(.1, .3)
    return row


def test_bradley_terry_recovers_preference_and_reports_loo():
    rng = random.Random(3)
    pairs = [{"winner": _features(rng, True), "loser": _features(rng, False)} for _ in range(30)]
    data = cc.fit_calibration(pairs, archetype="test", source="synthetic")
    assert data["valid"] and data["loo_accuracy"] >= .9
    assert data["weights"]["module_uniformity"] < 0 < data["weights"]["hero_photo_share"]
    assert cc.calibrated_score(data, _features(rng, True)) > cc.calibrated_score(data, _features(rng, False))


def test_small_or_noisy_calibration_is_never_used():
    rng = random.Random(5)
    few = [{"winner": _features(rng, True), "loser": _features(rng, False)} for _ in range(6)]
    assert not cc.fit_calibration(few, archetype="t", source="synthetic")["valid"]
    noise = [{"winner": {f: rng.random() for f in cc.FEATURES}, "loser": {f: rng.random() for f in cc.FEATURES}}
             for _ in range(30)]
    assert not cc.fit_calibration(noise, archetype="t", source="synthetic")["valid"]


def test_tabloid_calibration_prefers_photo_led_morphology_over_tiles():
    from backend.app.engine.plan_composer import compose_planned_page
    from test_tabloid_morphologies import _material
    calibration = cc.load_calibration("tabloid")
    assert calibration and calibration["valid"] and calibration["pairs"] >= cc.MIN_PAIRS
    assert calibration["loo_accuracy"] > calibration["heuristic_pair_accuracy"]
    dna = create_archetype_dnas()["tabloid"]
    material = _material()
    material.style_blend = dna.style_blend
    tiles = compose_planned_page(dna, material, {"layout_mode": "modular-grid"})
    poster = compose_planned_page(dna, material, {"layout_mode": "photo-top", "cover_morphology": "diagonal_hero_entry"})
    critic = LayoutCritic(dna)
    a, b = critic.evaluate(poster), critic.evaluate(tiles)
    assert a.calibrated_score is not None and b.calibrated_score is not None
    assert a.calibrated_score > b.calibrated_score
    critic.use_calibration = False
    assert critic.evaluate(poster).calibrated_score is None
