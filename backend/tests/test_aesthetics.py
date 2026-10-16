"""Tests for the Aesthetics and Visual Perception Engine (Xerox PARC + Sophi.io + Poynter)."""
from __future__ import annotations

import pytest
from backend.app.models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph, TitleDNA
from backend.app.engine.aesthetics import (
    element_optical_weight,
    calculate_visual_balance,
    calculate_visual_equilibrium,
    calculate_alignment_rhythm,
    detect_trapped_whitespace,
    evaluate_entry_point,
    evaluate_gaze_direction,
    evaluate_bottom_anchor,
    evaluate_page_aesthetics,
)
from backend.app.engine.critic import LayoutCritic
from backend.app.engine.art_director import measurements


def _simple_scene(elements, w=264.6, h=390.0, **meta) -> SceneGraph:
    return SceneGraph(
        page=PageMeta(trim=[w, h], bleed_mm=3.0),
        elements=elements,
        metadata={"composition": "modular", **meta}
    )


def test_visual_balance_lateral_symmetry():
    # Symmetric layout: equal blocks left and right
    e_left = Element(id="e1", role="photo", frame=Frame(x=10, y=100, w=100, h=100), importance=0.8)
    e_right = Element(id="e2", role="photo", frame=Frame(x=154.6, y=100, w=100, h=100), importance=0.8)
    sg_sym = _simple_scene([e_left, e_right])

    bal_sym, cx_sym, _ = calculate_visual_balance(sg_sym)
    assert bal_sym > 0.95
    assert abs(cx_sym - (264.6 / 2.0)) < 2.0

    # Highly unbalanced layout: single massive photo jammed into far left edge
    e_heavy = Element(id="e1", role="photo", frame=Frame(x=5, y=50, w=120, h=250), importance=1.0)
    sg_asym = _simple_scene([e_heavy])

    bal_asym, cx_asym, _ = calculate_visual_balance(sg_asym)
    assert bal_asym < 0.70
    assert cx_asym < 100.0


def test_visual_equilibrium_optical_center():
    # Mass near 45% height (approx 175 mm on 390 mm page)
    eq_optimal = calculate_visual_equilibrium(opt_y=175.0, page_h=390.0)
    assert eq_optimal > 0.95

    # Mass completely sinking near bottom edge (y=360)
    eq_sinking = calculate_visual_equilibrium(opt_y=360.0, page_h=390.0)
    assert eq_sinking < 0.30


def test_alignment_rhythm_clusters():
    # Clean grid: all elements share x=20, x=120, x=220
    e1 = Element(id="e1", role="headline", frame=Frame(x=20, y=30, w=200, h=40))
    e2 = Element(id="e2", role="photo", frame=Frame(x=20, y=80, w=100, h=100))
    e3 = Element(id="e3", role="body", frame=Frame(x=120, y=80, w=100, h=100))
    sg_clean = _simple_scene([e1, e2, e3])

    rhythm, nx, ny = calculate_alignment_rhythm(sg_clean)
    assert rhythm > 0.35
    assert nx <= 4


def test_trapped_whitespace_sophi_detection():
    # Create an enclosed O-box: four surrounding elements with a void in the middle
    # Middle void: x in [100, 160], y in [100, 180] (area = 60 * 80 = 4800 mm^2 = 48 cm^2)
    top = Element(id="top", role="band", frame=Frame(x=30, y=40, w=200, h=60))
    bottom = Element(id="bot", role="band", frame=Frame(x=30, y=180, w=200, h=60))
    left = Element(id="left", role="band", frame=Frame(x=30, y=100, w=70, h=80))
    right = Element(id="right", role="band", frame=Frame(x=160, y=100, w=70, h=80))

    sg_trapped = _simple_scene([top, bottom, left, right])
    trapped_cm2, pockets = detect_trapped_whitespace(sg_trapped)
    assert trapped_cm2 > 20.0
    assert len(pockets) >= 1
    pocket = pockets[0]
    assert 80 <= pocket["x"] <= 120
    assert 80 <= pocket["y"] <= 120

    # Compare with an open L-shape (open to exterior margin, not trapped)
    sg_open = _simple_scene([top, left])
    trapped_open_cm2, pockets_open = detect_trapped_whitespace(sg_open)
    assert trapped_open_cm2 < 5.0


def test_poynter_gaze_direction_evaluation():
    # Subject on left flank looking off-page (left) -> penalized
    ph_bad = Element(
        id="ph1", role="photo", frame=Frame(x=10, y=50, w=70, h=120),
        photo_analysis={"gaze_direction": "left"}
    )
    sg_bad = _simple_scene([ph_bad])
    score_bad, issues_bad = evaluate_gaze_direction(sg_bad)
    assert score_bad < 0.80
    assert any("left flank" in msg for msg in issues_bad)

    # Subject on left flank looking inwards (right) -> perfect score
    ph_good = Element(
        id="ph2", role="photo", frame=Frame(x=10, y=50, w=70, h=120),
        photo_analysis={"gaze_direction": "right"}
    )
    sg_good = _simple_scene([ph_good])
    score_good, issues_good = evaluate_gaze_direction(sg_good)
    assert score_good == 1.0
    assert len(issues_good) == 0


def test_entry_point_and_bottom_anchor():
    lead_headline = Element(id="h1", role="headline", frame=Frame(x=20, y=40, w=220, h=50),
                            importance=1.0, story_ref="s1", style=ElementStyle(font_size_pt=64))
    teaser = Element(id="h2", role="headline", frame=Frame(x=20, y=120, w=80, h=20),
                     importance=0.5, story_ref="s2", style=ElementStyle(font_size_pt=18))
    footer_bar = Element(id="foot", role="band", frame=Frame(x=0, y=340, w=264.6, h=50), importance=0.6)

    sg = _simple_scene([lead_headline, teaser, footer_bar])

    entry_score, dominant_id = evaluate_entry_point(sg)
    assert entry_score == 1.0
    assert dominant_id == "h1"

    anchor_score = evaluate_bottom_anchor(sg)
    assert anchor_score > 0.60


def test_evaluate_page_aesthetics_synthesis():
    e1 = Element(id="h1", role="headline", frame=Frame(x=20, y=40, w=220, h=40), importance=1.0,
                 style=ElementStyle(font_size_pt=48))
    e2 = Element(id="ph", role="photo", frame=Frame(x=20, y=90, w=100, h=140), importance=0.8)
    e3 = Element(id="bd", role="body", frame=Frame(x=130, y=90, w=110, h=140), importance=0.6,
                 style=ElementStyle(font_size_pt=9))
    e4 = Element(id="bt", role="band", frame=Frame(x=0, y=340, w=264.6, h=50), importance=0.5)

    sg = _simple_scene([e1, e2, e3, e4])
    report = evaluate_page_aesthetics(sg)

    assert 0.0 <= report.total_aesthetic_index <= 1.0
    assert report.total_aesthetic_index > 0.65
    assert report.balance_score > 0.70
    assert report.trapped_whitespace_cm2 < 10.0


def test_critic_integrates_aesthetic_index():
    from backend.app.engine.corpus_indexer import create_archetype_dnas
    dna = create_archetype_dnas()["tabloid"]
    critic = LayoutCritic(dna)

    e1 = Element(id="h1", role="headline", frame=Frame(x=20, y=40, w=220, h=40), importance=1.0,
                 style=ElementStyle(font_size_pt=48))
    e2 = Element(id="ph", role="photo", frame=Frame(x=20, y=90, w=100, h=140), importance=0.8)
    sg = _simple_scene([e1, e2])

    heur = critic.evaluate_heuristics(sg)
    assert hasattr(heur, "aesthetic_index")
    assert heur.aesthetic_index > 0.0
    assert heur.composite_soft_score > 0.0


def test_art_director_measurements_contains_aesthetics():
    e1 = Element(id="h1", role="headline", frame=Frame(x=20, y=40, w=220, h=40), importance=1.0,
                 style=ElementStyle(font_size_pt=48))
    sg = _simple_scene([e1])

    meas = measurements(sg)
    assert "estetyka_kompozycyjna" in meas
    est = meas["estetyka_kompozycyjna"]
    assert "indeks_estetyki" in est
    assert "rownowaga_optyczna" in est
    assert "uwieziona_biel_cm2" in est
