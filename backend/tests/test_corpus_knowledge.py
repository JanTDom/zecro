from pathlib import Path

from backend.app.engine.corpus_indexer import extract_page_features
from backend.app.engine.corpus_knowledge import enrich_feature_record, extract_spatial_structure


def test_page_index_keeps_spatial_evidence_separate_from_aggregate_strategy():
    page = next(Path("corpus").rglob("*.jpg"))
    record = extract_page_features(page)

    signature = record["structural_signature"]
    assert signature["evidence_level"] == "measured-coarse"
    assert len(signature["spatial_vector"]) == 96
    assert record["strategy"]["evidence_level"] == "measured-coarse"
    assert "region_count" in record["strategy"]["features"]


def test_legacy_row_is_explicit_about_unverified_semantics_and_never_claims_segmentation():
    enriched = enrich_feature_record(
        {
            "file_type": "pdf",
            "zone": "front_page",
            "columns": 5,
            "photo_coverage_pct": 42,
            "text_coverage_pct": 45,
            "headline_scale_ratio": 5,
            "strategy": {"id": "visual-opener", "confidence": 0.99},
        }
    )
    assert enriched["knowledge_evidence"]["level"] == "prior-or-unknown"
    assert enriched["knowledge_evidence"]["semantic_roles_verified"] is False
    assert enriched["strategy"]["confidence"] <= 0.72
    assert enriched["strategy"]["evidence_level"] == "prior-or-unknown"


def test_blank_preview_has_measured_zero_ink_signature():
    try:
        import numpy as np
    except ImportError:
        return
    signature = extract_spatial_structure(np.ones((64, 64), dtype="float32"))
    assert signature["evidence_level"] == "measured-coarse"
    assert signature["ink_coverage_pct"] == 0
    assert signature["whitespace_ratio"] == 1
    assert signature["spatial_vector"] == [0.0] * 96


def test_remote_only_loader_does_not_fall_back_to_workstation_snapshot():
    class Page:
        extracted_features = {
            "file_type": "pdf", "zone": "front", "columns": 5,
            "photo_coverage_pct": 30, "text_coverage_pct": 60,
            "headline_scale_ratio": 4.5,
        }
        id = "project-page"

    class Database:
        def list_global_corpus_features(self):
            return []

        def list_corpus_pages(self, project_id):
            assert project_id == "p1"
            return [Page()]

    from backend.app.engine.corpus_knowledge import load_corpus_knowledge

    result = load_corpus_knowledge(Database(), "p1", remote_only=True)
    assert result["source"] == "unavailable"
    assert result["remote_only"] is True
    assert result["evidence"]["global_pages"] == 0
    assert result["evidence"]["project_pages"] == 1
    assert result["evidence"]["warnings"] == ["global_corpus_unavailable"]
