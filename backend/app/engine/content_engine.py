"""Deterministic, provenance-first editorial content primitives.

This module is intentionally provider-neutral.  It can be replaced by a local
or hosted LLM adapter later, but the default implementation never invents a
fact: variants are derived only from the supplied story and source excerpts.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Mapping, Optional

from ..models.schemas import Claim, CopyVariant, Source, Story, TextFitResult, TextPlan
from .copyfit import estimate_text_capacity
from .polish_typography import polish_microtypography


def content_hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _sentences(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text or "") if part.strip()]


def extract_claims(text: str, source_refs: Optional[List[str]] = None) -> List[Claim]:
    """Extract atomic review units and mark them conservatively.

    A claim is considered verified only after a human/source workflow attaches
    evidence.  Merely having a source id therefore yields ``needs_editor`` for
    numeric, dated and quoted assertions rather than a false green check.
    """
    refs = list(source_refs or [])
    claims: List[Claim] = []
    for sentence in _sentences(text):
        claim_type = "fact"
        if re.search(r"\d", sentence):
            claim_type = "number"
        if re.search(r"\b(?:19|20)\d{2}\b|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", sentence):
            claim_type = "date"
        if '"' in sentence or "„" in sentence or "”" in sentence:
            claim_type = "quote"
        claims.append(Claim(
            text=sentence,
            claim_type=claim_type,
            source_refs=refs,
            confidence=0.0,
            status="needs_editor" if refs else "unverified",
        ))
    return claims


def _field_for_role(story: Story, role: str) -> str:
    if role in {"headline", "kicker", "deck", "lead", "body", "caption", "byline", "dateline"}:
        return str(getattr(story, role, "") or "")
    if role == "teaser":
        return str(story.deck or story.lead or story.headline or "")
    return str(story.body or "")


def _shorten(text: str, target_words: int) -> str:
    words = (text or "").split()
    if target_words <= 0 or len(words) <= target_words:
        return text or ""
    candidate = " ".join(words[:target_words]).rstrip(" ,;:")
    # Do not manufacture a new ending: end at the last complete sentence when
    # one exists, otherwise preserve the exact prefix and mark it for review.
    complete = _sentences(candidate)
    return complete[-1] if complete and candidate.endswith((".", "!", "?")) else candidate + "…"


def generate_copy_variants(story: Story, roles: Optional[Iterable[str]] = None) -> List[CopyVariant]:
    """Create micro/short/medium/long/exact-fit variants from existing copy."""
    roles = list(roles or ["headline", "deck", "lead", "body", "caption"])
    output: List[CopyVariant] = []
    claims = story.claims or extract_claims(story.body, story.source_refs)
    claim_refs = [claim.id for claim in claims]
    for role in roles:
        original = polish_microtypography(_field_for_role(story, role))
        if not original:
            continue
        words = len(original.split())
        targets = {
            "micro": max(1, round(words * 0.42)),
            "short": max(1, round(words * 0.68)),
            "medium": words,
            "long": words,
            "exact_fit": words,
        }
        for kind in ("micro", "short", "medium", "long", "exact_fit"):
            locked_present = any(locked and locked in original for locked in story.locked_passages)
            text = original if kind in {"medium", "long", "exact_fit"} or locked_present else _shorten(original, targets[kind])
            output.append(CopyVariant(
                story_ref=story.id, role=role, variant_kind=kind, text=text,
                target_words=targets[kind], target_chars=len(text),
                claim_refs=claim_refs, source_refs=list(story.source_refs),
                locked_passages=list(story.locked_passages),
                provenance={"provider": "deterministic-local", "model": "zecro-content-v1", "source_revision": story.version},
            ))
    return output


def fit_text_plan(plan: TextPlan, text: str, *, variant_ref: Optional[str] = None) -> TextFitResult:
    report = estimate_text_capacity(text, plan.width_mm, plan.height_mm, plan.columns, plan.min_font_size_pt, plan.min_font_size_pt + 2.0)
    measure = (plan.width_mm - (plan.columns - 1) * 4.0) / max(1, plan.columns)
    too_narrow = measure < 30.0
    overflow_lines = max(0, report.estimated_lines - report.capacity_lines)
    leading_mm = (plan.min_font_size_pt + 2.0) * 0.352778
    overflow_mm = round(overflow_lines * leading_mm / max(1, plan.columns), 2)
    free_mm = round(max(0, report.capacity_lines - report.estimated_lines) * leading_mm / max(1, plan.columns), 2)
    warnings: List[str] = []
    if too_narrow:
        warnings.append(f"column measure {measure:.1f}mm is below 30mm")
    if report.overflow_ratio > 1.0:
        warnings.append(f"estimated overflow ratio {report.overflow_ratio:.2f}")
    status = "PASS" if report.passes and not too_narrow else "FAIL"
    return TextFitResult(
        text_plan_ref=plan.id, copy_variant_ref=variant_ref, status=status,
        words=report.words, lines=report.estimated_lines, capacity_lines=report.capacity_lines,
        overflow_mm=overflow_mm, free_space_mm=free_mm, too_narrow=too_narrow,
        warnings=warnings, content_hash=content_hash(text),
    )


def build_flat_plan(issue, stories: Iterable[Story], *, variant: str = "standard"):
    """Create a transparent first-pass flat plan before geometry generation."""
    story_list = sorted(list(stories), key=lambda item: item.importance, reverse=True)
    page_count = max(1, int(issue.page_count))
    pages = []
    from ..models.schemas import IssuePlanPage
    for number in range(1, page_count + 1):
        role = "front" if number == 1 else ("back" if number == page_count else "inside")
        assigned = [story.id for index, story in enumerate(story_list) if index % page_count == number - 1]
        pages.append(IssuePlanPage(page_number=number, page_role=role, story_refs=assigned, masthead=number == 1, folio=True, surface_budget={"text": 0.62, "photo": 0.22, "white_space": 0.16}))
    from ..models.schemas import IssuePlan
    return IssuePlan(issue_ref=issue.id, pages=pages, variant=variant, conflicts=[])
