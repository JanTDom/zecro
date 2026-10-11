from backend.app.engine.content_engine import (
    fit_text_plan,
    generate_copy_variants,
    rank_copy_variants_for_plan,
)
from backend.app.engine.copyfit import estimate_text_capacity
from backend.app.models.schemas import CopyVariant, Story, TextPlan
from backend.app.engine.content_engine import build_flat_plan, build_text_plans_for_flatplan
from backend.app.models.schemas import Issue


def test_copyfit_respects_no_break_tokens_and_reports_overlong_phrase():
    report = estimate_text_capacity(
        "Jan Kowalski podpisał dokument.",
        width_mm=5,
        height_mm=30,
        columns=1,
        font_size_pt=9,
        leading_pt=11,
        no_break_tokens=["Jan Kowalski"],
    )

    assert report.overlong_tokens == ("Jan Kowalski",)
    assert report.passes is False
    assert any("no-break" in warning for warning in report.warnings)


def test_fit_plan_exposes_targets_widows_and_editorial_actions():
    plan = TextPlan(
        story_ref="story-1",
        issue_ref="issue-1",
        width_mm=32,
        height_mm=35,
        columns=2,
        min_words=5,
        max_words=20,
        target_words=12,
        target_lines=8,
        widow_lines=2,
        orphan_lines=2,
        overflow_policy="alternate",
    )
    result = fit_text_plan(
        plan,
        "To jest tekst, który ma więcej słów i powinien pokazać rekomendacje copyfit.",
    )

    assert result.target_words == 12
    assert result.target_lines == 8
    assert result.target_deviation_words == 0
    assert result.target_deviation_lines != 0
    assert result.recommendations
    assert result.warnings


def test_locked_passage_is_kept_in_short_variant_and_variants_can_be_ranked():
    story = Story(
        issue_ref="issue-1",
        slug="locked",
        headline="Nagłówek",
        body=(
            "Pierwsze zdanie. W materiale pozostaje zatwierdzony zwrot "
            "Jan Kowalski oraz dalszy kontekst, który można skrócić."
        ),
        locked_passages=["Jan Kowalski"],
    )
    variants = generate_copy_variants(story, roles=["body"])
    short = next(item for item in variants if item.variant_kind == "short")
    assert "Jan Kowalski" in short.text

    plan = TextPlan(story_ref=story.id, issue_ref=story.issue_ref, width_mm=90, height_mm=120, columns=2)
    ranked = rank_copy_variants_for_plan(plan, variants)
    assert len(ranked) == len(variants)
    assert all(item[1].text_plan_ref == plan.id for item in ranked)


def test_flatplan_creates_role_budgets_before_scene_geometry():
    issue = Issue(project_id="project-1", issue_number="01", publication_date="2026-10-10", page_count=1)
    story = Story(
        issue_ref=issue.id,
        slug="lead",
        importance=0.9,
        headline="Ważna decyzja redakcji",
        deck="Najważniejsze fakty w kilku słowach.",
        body="To jest dłuższy materiał redakcyjny. " * 160,
    )
    flat_plan = build_flat_plan(issue, [story])
    plans = build_text_plans_for_flatplan(issue, [story], flat_plan)
    roles = {plan.role for plan in plans}
    assert {"headline", "deck", "body"}.issubset(roles)
    body_plan = next(plan for plan in plans if plan.role == "body")
    assert body_plan.frame_ref.startswith("flatplan:1:")
    assert body_plan.target_words < len(story.body.split())
    assert body_plan.max_words >= body_plan.target_words
