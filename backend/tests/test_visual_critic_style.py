from types import SimpleNamespace

from backend.app.ai import visual_critic
from backend.app.api.generate import _visual_feedback


def test_visual_critic_receives_editorial_character(monkeypatch):
    seen = []
    monkeypatch.setattr(visual_critic, "render_png", lambda *_: b"page-preview")

    def fake_run(_task, _prompt, payload, _schema, **_kwargs):
        seen.append(payload["title_style"])
        return SimpleNamespace(data={"score": 0.8}, provenance={"provider": "gemini"})

    monkeypatch.setattr(visual_critic, "run_task", fake_run)
    dna = SimpleNamespace(style_blend=SimpleNamespace(opinion_to_tabloid=.2),
                          grid=SimpleNamespace(columns=5), format=SimpleNamespace(trim_w_mm=315, trim_h_mm=470))
    scene = SimpleNamespace(elements=[], metadata={"style_blend": {"opinion_to_tabloid": .9}})
    visual_critic.critique(scene, dna)
    scene.metadata["style_blend"]["opinion_to_tabloid"] = .1
    visual_critic.critique(scene, dna)
    assert seen == ["gazeta bulwarowa", "gazeta poważna i opiniotwórcza"]


def test_category_review_never_equates_a_style_score_with_editorial_approval():
    weak = visual_critic.category_review({"score": .9, "style_fidelity": .5, "category_mismatch": []})
    high_but_wrong = visual_critic.category_review({"score": .92, "style_fidelity": .96,
                                                     "category_mismatch": ["zbyt spokojny układ"]})
    strong = visual_critic.category_review({"score": .91, "style_fidelity": .94, "category_mismatch": []})
    assert weak["status"] == "needs_revision"
    assert high_but_wrong["status"] == "needs_revision"
    wrong_photo = visual_critic.category_review({"score": .95, "style_fidelity": .95,
                                                 "photo_headline_match": .2, "photo_use": .8,
                                                 "category_mismatch": []})
    assert wrong_photo["status"] == "needs_revision"
    assert strong["status"] == "candidate_for_editor"
    assert strong["editorial_approval_required"] is True


def test_text_only_page_is_not_penalized_for_missing_photo():
    critique = {"score": .91, "style_fidelity": .94, "category_mismatch": [],
                "photo_headline_match": 0, "photo_use": 0}
    assert visual_critic.category_review(critique, has_photos=False)["status"] == "candidate_for_editor"
    assert visual_critic.category_review(critique, has_photos=True)["status"] == "needs_revision"


def test_visual_failure_biases_second_pass_without_directly_editing_scene():
    scene = SimpleNamespace(metadata={"layout_mode": "type-led", "visual_critique": {
        "style_fidelity": .5, "photo_headline_match": .8, "dead_zones": ["puste pole"],
        "category_review": {"status": "needs_revision"},
    }})
    feedback = _visual_feedback([(scene, None)])
    assert feedback["rejected_modes"] == ["type-led"]
    assert feedback["dead_zones"] is True
    assert feedback["photo_selection_needed"] is False


def test_unreviewed_candidate_cannot_outrank_reviewed_scene(monkeypatch):
    monkeypatch.setattr(visual_critic, "critique", lambda *_args, **_kwargs: {
        "score": .4, "style_fidelity": .4,
        "category_review": {"status": "needs_revision"},
    })
    reviewed = SimpleNamespace(metadata={})
    unreviewed = SimpleNamespace(metadata={})
    gate = SimpleNamespace(passed=True)
    pairs = [(reviewed, SimpleNamespace(total_fitness=.3, hard_gate=gate)),
             (unreviewed, SimpleNamespace(total_fitness=.9, hard_gate=gate))]
    ordered, status = visual_critic.rerank(pairs, SimpleNamespace(), limit=1)
    assert ordered[0][0] is reviewed
    assert unreviewed.metadata["visual_critique"]["status"] == "not_reviewed"
    assert status["reviewed"] == 1
    assert status["unreviewed"] == 1


def test_visual_reviews_are_memory_safe_by_default(monkeypatch):
    active = 0
    peak = 0

    def fake_critique(*_args, **_kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        # A serial executor completes this call before starting the next one.
        active -= 1
        return {"score": .9, "style_fidelity": .9,
                "category_review": {"status": "candidate_for_editor"}}

    monkeypatch.delenv("ZECRO_VISUAL_CRITIC_WORKERS", raising=False)
    monkeypatch.setattr(visual_critic, "critique", fake_critique)
    gate = SimpleNamespace(passed=True)
    pairs = [(SimpleNamespace(metadata={}), SimpleNamespace(total_fitness=.8, hard_gate=gate))
             for _ in range(3)]
    _ordered, status = visual_critic.rerank(pairs, SimpleNamespace(), limit=3)
    assert status["review_workers"] == 1
    assert status["reviewed"] == 3
    assert peak == 1
