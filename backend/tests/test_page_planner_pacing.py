from backend.app.engine.page_planner import calculate_issue_pacing


def test_issue_pacing_profile():
    # Page 1: Cover must be poster / maximum energy
    p1 = calculate_issue_pacing(1, total_pages=8)
    assert p1.side == "recto"
    assert p1.energy == 1.0
    assert p1.rhythm == "poster"
    assert p1.recommended_mode == "photo-top"

    # Page 2: Inside left (Verso) must be quiet / breathing context
    p2 = calculate_issue_pacing(2, total_pages=8)
    assert p2.side == "verso"
    assert p2.energy < 0.70
    assert p2.rhythm == "quiet_context"
    assert p2.negative_space_bias >= 0.15

    # Center spread (pages 4 and 5 in 8-page issue)
    p4 = calculate_issue_pacing(4, total_pages=8)
    p5 = calculate_issue_pacing(5, total_pages=8)
    assert p4.rhythm == "analytical_spread"
    assert p5.rhythm == "analytical_spread"
    assert p4.side == "verso"
    assert p5.side == "recto"

    # Back cover (page 8)
    p8 = calculate_issue_pacing(8, total_pages=8)
    assert p8.energy >= 0.85
