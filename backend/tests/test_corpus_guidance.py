from backend.app.engine.corpus_indexer import build_generation_guidance


def test_generation_guidance_uses_zone_and_archetype_priors_with_fallback_metadata():
    pages = [
        {
            "archetype": "compact",
            "zone": "front",
            "columns": 6,
            "gutter_mm": 4.5,
            "baseline_grid_pt": 10,
            "body_size_pt": 8.5,
            "headline_scale_ratio": 5,
            "photo_coverage_pct": 38,
            "text_coverage_pct": 50,
            "avg_transgressions_per_page": 1.5,
        },
        {
            "archetype": "classical",
            "zone": "inside",
            "columns": 4,
            "gutter_mm": 5,
            "baseline_grid_pt": 11,
            "body_size_pt": 9,
            "headline_scale_ratio": 4,
            "photo_coverage_pct": 20,
            "text_coverage_pct": 65,
            "avg_transgressions_per_page": 1,
        },
    ]

    front = build_generation_guidance(pages, archetype="compact", zone="front_page")
    assert front["sample_count"] == 1
    assert front["used_fallback"] is False
    assert front["columns_mean"] == 6
    assert front["photo_coverage_pct_mean"] == 38

    fallback = build_generation_guidance(pages, archetype="compact", zone="back_page")
    assert fallback["sample_count"] == 2
    assert fallback["used_fallback"] is True
