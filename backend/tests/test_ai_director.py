from types import SimpleNamespace

from backend.app.engine.ai_director import AIDirector, CONTRACT_VERSION


def test_contract_reports_evidence_and_unconfigured_specialists_without_fake_confidence():
    knowledge = {
        "source": "database",
        "evidence": {
            "knowledge_pages": 1041,
            "structural_pages": 120,
            "semantic_pages": 0,
            "levels": {"legacy-aggregate": 921, "measured-coarse": 120},
            "warnings": [],
        },
    }
    contract = AIDirector(dna=SimpleNamespace(), knowledge=knowledge).contract()
    assert contract["version"] == CONTRACT_VERSION
    assert contract["knowledge"]["sample_count"] == 1041
    assert contract["knowledge"]["semantic_pages"] == 0
    assert contract["specialists"]["taste_critic"]["status"] == "heuristic"
    assert contract["specialists"]["visual_critic"]["status"] == "unconfigured"
    assert "no_layout_is_approved_from_metadata_only" in contract["gates"]


def test_candidate_trace_makes_hard_gate_and_unknowns_explicit():
    knowledge = {"source": "unavailable", "evidence": {"knowledge_pages": 0, "levels": {}}}
    result = SimpleNamespace(hard_gate=SimpleNamespace(passed=False, violations=["body overset"]))
    scene = SimpleNamespace(metadata={"corpus_guidance": {"sample_count": 0}})
    trace = AIDirector(dna=SimpleNamespace(), knowledge=knowledge).candidate_trace(scene, result)
    assert trace["approval"] == "blocked_by_hard_gate"
    assert trace["selection"]["hard_gate"] == "FAIL"
    assert "body overset" in trace["selection"]["violations"]
    assert "visual model review is not configured" in trace["unknowns"]
