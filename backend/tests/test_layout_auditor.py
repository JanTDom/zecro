"""Unit tests for LayoutAuditor (diagnosing defects and measuring scores)."""
from __future__ import annotations

import pytest
from backend.app.engine.layout_auditor import LayoutAuditor
from backend.app.models.schemas import Element, ElementStyle, Frame, PageMeta, SceneGraph, TitleDNA


def test_auditor_flags_photo_competition():
    # Two large photos with identical size -> competing dominants
    scene = SceneGraph(
        page=PageMeta(trim=[280.0, 400.0], page_zone="front_page"),
        elements=[
            Element(
                id="photo_a",
                role="photo",
                frame=Frame(x=15.0, y=30.0, w=120.0, h=130.0),  # ~14% page area
                importance=0.8,
            ),
            Element(
                id="photo_b",
                role="photo",
                frame=Frame(x=145.0, y=30.0, w=120.0, h=130.0),  # ~14% page area, ratio 1.0
                importance=0.8,
            ),
            Element(
                id="head_1",
                role="headline",
                text_content="TYTUŁ ARTYKUŁU",
                frame=Frame(x=15.0, y=170.0, w=250.0, h=25.0),
                style=ElementStyle(font_size_pt=36.0),
            ),
        ],
    )
    auditor = LayoutAuditor()
    report = auditor.audit_layout(scene)

    rule_codes = {d.rule_code for d in report.defects}
    assert "PHOTO_COMPETITION" in rule_codes
    assert any("rywalizują o uwagę" in d.message for d in report.defects)


def test_auditor_flags_hanging_prepositions():
    # Polish text with dangling "w ", "z ", "o "
    scene = SceneGraph(
        page=PageMeta(trim=[280.0, 400.0]),
        elements=[
            Element(
                id="head_sierotki",
                role="headline",
                text_content="Nowy minister o planach rządu w sprawie podatków z roku 2026",
                frame=Frame(x=15.0, y=20.0, w=250.0, h=25.0),
                style=ElementStyle(font_size_pt=32.0),
            ),
            Element(
                id="lead_sierotki",
                role="lead",
                text_content="Spotkanie odbyło się w Warszawie a decyzje zapadną w piątek.",
                frame=Frame(x=15.0, y=50.0, w=250.0, h=20.0),
                style=ElementStyle(font_size_pt=14.0),
            ),
        ],
    )
    auditor = LayoutAuditor()
    report = auditor.audit_layout(scene)

    rule_codes = {d.rule_code for d in report.defects}
    assert "HANGING_PREPOSITIONS" in rule_codes


def test_auditor_flags_flat_typography():
    # Headline is only 16pt while body is 12pt (scale ratio 1.33 < 2.2)
    scene = SceneGraph(
        page=PageMeta(trim=[280.0, 400.0]),
        elements=[
            Element(
                id="head_flat",
                role="headline",
                text_content="TYTUŁ MAŁY I PŁASKI",
                frame=Frame(x=15.0, y=20.0, w=250.0, h=15.0),
                style=ElementStyle(font_size_pt=16.0),
            ),
            Element(
                id="body_1",
                role="body",
                text_content="Tekst artykułu pisany dużym stopniem pisma bez hierarchii wizualnej.",
                frame=Frame(x=15.0, y=40.0, w=250.0, h=60.0),
                style=ElementStyle(font_size_pt=12.0),
            ),
        ],
    )
    auditor = LayoutAuditor()
    report = auditor.audit_layout(scene)

    rule_codes = {d.rule_code for d in report.defects}
    assert "FLAT_TYPOGRAPHY" in rule_codes


def test_auditor_reports_high_score_for_balanced_layout():
    # Clear single dominant hero, fitting headline, no hanging prepositions
    from backend.app.engine.polish_typography import polish_microtypography
    text_clean = polish_microtypography("Wielki plan inwestycyjny")
    body_clean = polish_microtypography(
        "Prace modernizacyjne rozpoczną się natychmiast po podpisaniu kontraktu ze zwycięzcą przetargu publicznego. "
        "Projekt zakłada całkowitą przebudowę układu torowego oraz zakup nowoczesnego taboru niskoemisyjnego. "
        "Pasażerowie skorzystają z nowych połączeń już w nadchodzącym sezonie jesiennym. "
        "Całość inwestycji finansowana jest ze środków własnych oraz funduszy europejskich."
    )

    scene = SceneGraph(
        page=PageMeta(trim=[280.0, 400.0], page_zone="front_page"),
        elements=[
            Element(
                id="hero_photo",
                role="photo",
                frame=Frame(x=15.0, y=15.0, w=250.0, h=170.0),  # dominant hero > 35% of page
                z=1,
                importance=0.96,
                treatment="crop",
            ),
            Element(
                id="main_headline",
                role="headline",
                text_content=text_clean,
                frame=Frame(x=15.0, y=195.0, w=250.0, h=35.0),
                z=2,
                style=ElementStyle(font_size_pt=36.0, font_weight="bold"),
            ),
            Element(
                id="body_story",
                role="body",
                text_content=body_clean,
                frame=Frame(x=15.0, y=240.0, w=160.0, h=115.0),
                z=2,
                style=ElementStyle(font_size_pt=9.5),
            ),
            Element(
                id="footer_band",
                role="band",
                frame=Frame(x=15.0, y=365.0, w=250.0, h=15.0),
                z=2,
                style=ElementStyle(bg_color="#111827"),
            ),
        ],
    )
    auditor = LayoutAuditor()
    report = auditor.audit_layout(scene)

    assert report.hard_gate_passed is True
    assert report.overall_score >= 70
    assert report.aesthetic_score >= 60.0
