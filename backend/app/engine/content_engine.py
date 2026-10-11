"""Deterministic, provenance-first editorial content primitives.

This module is intentionally provider-neutral.  It can be replaced by a local
or hosted LLM adapter later, but the default implementation never invents a
fact: variants are derived only from the supplied story and source excerpts.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Mapping, Optional, Sequence, Tuple

from ..models.schemas import Claim, CopyVariant, Issue, IssuePlan, Story, TextFitResult, TextPlan
from .copyfit import CopyfitReport, estimate_text_capacity
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


def _locked_word_ranges(text: str, locked_passages: Sequence[str]) -> List[Tuple[int, int]]:
    """Return word ranges occupied by locked passages.

    Ranges are used only by the deterministic truncator.  They do not mutate
    the source text and allow a short/micro variant to include an approved
    name, quote or legal phrase even when it sits beyond the nominal cut.
    """

    words = (text or "").split()
    # Match editorial passages across sentence punctuation ("Nowak." should
    # still satisfy a lock for "Anna Nowak").
    normalised_words = [re.sub(r"^[\W_]+|[\W_]+$", "", word, flags=re.UNICODE).casefold() for word in words]
    ranges: List[Tuple[int, int]] = []
    for passage in locked_passages or []:
        passage_words = str(passage or "").split()
        normalised_passage = [re.sub(r"^[\W_]+|[\W_]+$", "", word, flags=re.UNICODE).casefold() for word in passage_words]
        if not passage_words:
            continue
        width = len(passage_words)
        for start in range(0, max(0, len(words) - width + 1)):
            if normalised_words[start:start + width] == normalised_passage:
                ranges.append((start, start + width))
                break
    return ranges


def _polish_copy_preserving_locked(text: str, locked_passages: Sequence[str]) -> str:
    """Polish copy while preserving approved passages byte-for-byte."""

    if not text or not locked_passages:
        return polish_microtypography(text or "")
    protected = {}
    result = text
    for index, passage in enumerate(sorted((item for item in locked_passages if item), key=len, reverse=True)):
        marker = f"\ue100{index}\ue101"
        if passage in result:
            protected[marker] = passage
            result = result.replace(passage, marker)
    result = polish_microtypography(result)
    for marker, passage in protected.items():
        result = result.replace(marker, passage)
    return result


def _shorten(text: str, target_words: int, locked_passages: Sequence[str] | None = None) -> str:
    words = (text or "").split()
    if target_words <= 0 or len(words) <= target_words:
        return text or ""
    keep = max(1, int(target_words))
    # If a locked passage crosses the cut, extend the cut to include it.  If a
    # locked passage appears later in the story, include it rather than
    # silently deleting an editorially approved phrase.
    for start, end in _locked_word_ranges(text, locked_passages or []):
        # A locked phrase is a hard editorial constraint, even if honoring it
        # means exceeding the requested word budget.  Silent deletion is worse
        # than an explicit fit warning returned by the caller.
        keep = max(keep, end)
    keep = min(len(words), keep)
    candidate = " ".join(words[:keep]).rstrip(" ,;:")
    if keep >= len(words):
        return candidate
    # Prefer a complete sentence when it does not throw away most of the
    # requested variant.  Otherwise preserve the exact prefix and mark it for
    # editorial review with an ellipsis.
    sentence_end = [match.end() for match in re.finditer(r"[.!?](?:[\"”’)]*)?(?:\s|$)", candidate)]
    if sentence_end:
        sentence_candidate = candidate[:sentence_end[-1]].rstrip()
        if len(sentence_candidate.split()) >= max(1, int(keep * 0.72)):
            candidate = sentence_candidate
    return candidate if candidate.endswith((".", "!", "?", "…")) else candidate + "…"


def _source_bound_variant(
    text: str,
    target_words: int,
    *,
    locked_passages: Sequence[str] | None = None,
    role: str = "body",
) -> tuple[str, dict[str, object]]:
    """Return a usable variant without pretending to be a reporting model.

    The offline writer is deliberately conservative: it may select and trim
    supplied sentences, but it cannot add a fact that is absent from the
    source.  A request longer than the source therefore returns the complete
    source and a machine-readable ``needs_more_source`` flag.  The editor can
    then add an approved paragraph or ask a configured provider to draft one.
    """

    source = _polish_copy_preserving_locked(text or "", locked_passages or [])
    source_words = len(source.split())
    target = max(0, int(target_words or 0))
    if not source or target <= 0:
        return source, {"needs_more_source": False, "source_words": source_words}
    if target >= source_words:
        return source, {
            "needs_more_source": target > source_words,
            "source_words": source_words,
            "requested_words": target,
        }
    # Headlines and kickers are best kept as a compact prefix: rearranging
    # supplied clauses can change the factual emphasis.  For running copy,
    # prefer complete source sentences and then fill the remaining budget with
    # the next sentence's prefix.
    if role in {"headline", "kicker", "byline", "caption"}:
        return _shorten(source, target, locked_passages), {
            "needs_more_source": False,
            "source_words": source_words,
            "requested_words": target,
        }
    sentences = _sentences(source)
    selected: list[str] = []
    count = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if count + sentence_words <= target:
            selected.append(sentence)
            count += sentence_words
        elif not selected:
            selected.append(_shorten(sentence, target, locked_passages))
            count = len(selected[-1].split())
            break
        else:
            break
    candidate = " ".join(selected).strip()
    # A locked passage is an editorial contract.  If sentence selection would
    # discard it, fall back to the safe truncator which extends the cut.
    if any(passage and passage not in candidate for passage in (locked_passages or [])):
        candidate = _shorten(source, target, locked_passages)
    return candidate, {
        "needs_more_source": False,
        "source_words": source_words,
        "requested_words": target,
        "selected_sentences": len(selected),
    }


def generate_copy_variants(story: Story, roles: Optional[Iterable[str]] = None) -> List[CopyVariant]:
    """Create micro/short/medium/long/exact-fit variants from existing copy."""
    roles = list(roles or ["headline", "deck", "lead", "body", "caption"])
    output: List[CopyVariant] = []
    claims = story.claims or extract_claims(story.body, story.source_refs)
    claim_refs = [claim.id for claim in claims]
    for role in roles:
        original = _polish_copy_preserving_locked(_field_for_role(story, role), story.locked_passages)
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
            requested = targets[kind]
            # No invented filler: long/exact-fit are complete source variants
            # unless a caller supplies a concrete target to the fitting API.
            text, variant_meta = _source_bound_variant(
                original,
                requested,
                locked_passages=story.locked_passages,
                role=role,
            )
            output.append(CopyVariant(
                story_ref=story.id, role=role, variant_kind=kind, text=text,
                target_words=requested, target_chars=len(text),
                claim_refs=claim_refs, source_refs=list(story.source_refs),
                locked_passages=list(story.locked_passages),
                provenance={"provider": "deterministic-local", "model": "zecro-content-v2-source-bound", "source_revision": story.version, **variant_meta},
            ))
    return output


def rewrite_source_bound_copy(
    text: str,
    *,
    role: str = "body",
    target_words: int | None = None,
    locked_passages: Sequence[str] | None = None,
) -> tuple[str, dict[str, object]]:
    """Public source-bound rewrite primitive used by API and Content Studio.

    ``target_words`` is a fitting request, not permission to fabricate copy.
    The returned metadata is shown to editors so an undersized source cannot
    be mistaken for a successful expansion.
    """

    source = _polish_copy_preserving_locked(text or "", locked_passages or [])
    requested = int(target_words or len(source.split()))
    result, metadata = _source_bound_variant(
        source,
        requested,
        locked_passages=locked_passages,
        role=role,
    )
    metadata.update({"provider": "deterministic-local", "model": "zecro-content-v2-source-bound", "role": role})
    return result, metadata


def _fit_warnings(plan: TextPlan, report: CopyfitReport, text: str) -> List[str]:
    warnings = list(report.warnings)
    word_count = len((text or "").split())
    if plan.min_words and word_count < plan.min_words:
        warnings.append(f"copy has {word_count} words; minimum is {plan.min_words}")
    if plan.max_words and word_count > plan.max_words:
        warnings.append(f"copy has {word_count} words; maximum is {plan.max_words}")
    if plan.target_words:
        delta = word_count - plan.target_words
        if delta:
            warnings.append(f"target word deviation {delta:+d}")
    if plan.target_chars:
        delta_chars = len((text or "").strip()) - plan.target_chars
        if delta_chars:
            warnings.append(f"target character deviation {delta_chars:+d}")
    if plan.target_lines:
        delta_lines = report.estimated_lines - plan.target_lines
        if delta_lines:
            warnings.append(f"target line deviation {delta_lines:+d}")
    if report.free_lines > max(3, report.capacity_lines // 4):
        warnings.append(f"frame leaves {report.free_lines} free line(s); consider a tighter variant or a pull quote")
    return warnings


def fit_text_plan(plan: TextPlan, text: str, *, variant_ref: Optional[str] = None, font_family: Optional[str] = None,
                  bold: bool = False, font_size_pt: Optional[float] = None, leading_pt: Optional[float] = None,
                  gutter_mm: float = 4.0) -> TextFitResult:
    # Use the plan's declared minimum as the hard lower bound.  Tracking and
    # leading are measured explicitly so the same result can be reproduced by
    # the SVG critic and the production preflight.
    base_font_size = max(1.0, float(font_size_pt or plan.min_font_size_pt))
    base_leading = float(leading_pt or base_font_size + 2.0)
    report = estimate_text_capacity(
        polish_microtypography(text or ""),
        plan.width_mm,
        plan.height_mm,
        plan.columns,
        base_font_size,
        base_leading,
        widow_lines=plan.widow_lines,
        orphan_lines=plan.orphan_lines,
        no_break_tokens=plan.no_break_tokens,
        font_family=font_family,
        bold=bold,
        gutter_mm=gutter_mm,
    )
    measure = (plan.width_mm - (plan.columns - 1) * gutter_mm) / max(1, plan.columns)
    too_narrow = measure < 30.0
    overflow_lines = max(0, report.estimated_lines - report.capacity_lines)
    leading_mm = base_leading * 0.352778
    overflow_mm = round(overflow_lines * leading_mm / max(1, plan.columns), 2)
    free_mm = round(max(0, report.free_lines) * leading_mm / max(1, plan.columns), 2)
    warnings = _fit_warnings(plan, report, text)
    if too_narrow:
        warnings.append(f"column measure {measure:.1f}mm is below 30mm")
    # min/max word counts and target lines are planning constraints.  A target
    # is advisory; min/max are hard because they represent editorial mandate.
    word_count = len((text or "").split())
    hard_word_bounds = (plan.min_words and word_count < plan.min_words) or (plan.max_words and word_count > plan.max_words)
    status = "PASS" if report.passes and not too_narrow and not hard_word_bounds else "FAIL"
    target_word_delta = word_count - plan.target_words if plan.target_words else 0
    target_line_delta = report.estimated_lines - plan.target_lines if plan.target_lines else 0
    return TextFitResult(
        text_plan_ref=plan.id, copy_variant_ref=variant_ref, status=status,
        words=report.words, lines=report.estimated_lines, capacity_lines=report.capacity_lines,
        overflow_mm=overflow_mm, free_space_mm=free_mm, too_narrow=too_narrow,
        widows=report.widows, orphans=report.orphans,
        target_words=plan.target_words, target_lines=plan.target_lines,
        target_deviation_words=target_word_delta, target_deviation_lines=target_line_delta,
        font_size_pt=base_font_size, leading_pt=base_leading, tracking_em=report.tracking_em,
        recommendations=_recommend_copyfit_actions(plan, report, too_narrow),
        warnings=warnings, content_hash=content_hash(text),
    )


def _recommend_copyfit_actions(plan: TextPlan, report: CopyfitReport, too_narrow: bool) -> List[str]:
    actions: List[str] = []
    if report.overflow_ratio > 1.0:
        if plan.overflow_policy in {"shorten", "alternate"}:
            actions.append("select a shorter approved copy variant")
        if plan.overflow_policy in {"continue", "reflow"} and plan.continuation_policy == "jump_if_needed":
            actions.append("split into a continuation and add a jump line")
        if plan.max_tracking > 0:
            actions.append(f"tighten tracking up to {min(10.0, plan.max_tracking):g}/1000em after copy selection")
        if plan.max_leading_adjustment_pt > 0:
            actions.append(f"reduce leading by at most {plan.max_leading_adjustment_pt:g}pt")
    if report.widows or report.orphans:
        actions.append("reflow the final paragraph to satisfy widow/orphan thresholds")
    if too_narrow:
        actions.append("increase the column measure or reduce the number of columns")
    if plan.target_words:
        if report.words > plan.target_words:
            actions.append("choose a shorter approved variant to approach the target word budget")
        elif report.words < plan.target_words:
            actions.append("choose a longer approved variant or add an approved deck/pull quote")
    if plan.target_lines and report.estimated_lines != plan.target_lines and report.passes:
        actions.append("reflow or adjust the assigned frame to approach the target line count")
    if report.free_lines > max(3, report.capacity_lines // 4):
        actions.append("consider a longer variant, deck, pull quote or fact box")
    return actions


def rank_copy_variants_for_plan(plan: TextPlan, variants: Iterable[CopyVariant]) -> List[Tuple[CopyVariant, TextFitResult]]:
    """Fit and rank approved variants without mutating editorial content.

    The ranking deliberately prefers a hard PASS, then the closest target
    length, then the least free space.  It can be called by a future hosted
    writer or Supabase edge function and keeps provider-specific generation
    outside the geometry contract.
    """

    scored: List[Tuple[CopyVariant, TextFitResult]] = []
    for variant in variants:
        result = fit_text_plan(plan, variant.text, variant_ref=variant.id)
        scored.append((variant, result))
    scored.sort(key=lambda item: (
        item[1].status != "PASS",
        abs(item[1].target_deviation_lines) if plan.target_lines else abs(item[1].target_deviation_words) if plan.target_words else 0,
        abs(item[1].free_space_mm),
        item[1].overflow_mm,
    ))
    return scored


def build_flat_plan(issue, stories: Iterable[Story], *, variant: str = "standard"):
    """Build a rank-aware issue plan before geometry.

    The old modulo assignment sent the second most important story to page 2
    regardless of its editorial role.  This planner keeps lead/second stories
    on the front, honours explicit pins and sends only continuations to their
    target page.  A story is assigned once; teaser-only stories are represented
    as a teaser slot and never duplicated as a full module.
    """
    from ..models.schemas import IssuePlan, IssuePlanPage
    story_list = list(stories)
    page_count = max(1, int(issue.page_count))
    by_page: dict[int, list[str]] = {page: [] for page in range(1, page_count + 1)}
    front_candidates = sorted(story_list, key=lambda item: ({"lead": 0, "second": 1, "third": 2, "short": 3, "brief": 4, "teaser": 5, "box": 4, "column": 3}.get(getattr(item, "rank", "second"), 6), -item.importance))
    assigned: set[str] = set()
    for story in front_candidates:
        explicit = getattr(story, "pin_page", None)
        target = int(explicit) if explicit and 1 <= int(explicit) <= page_count else None
        rank = getattr(story, "rank", "second")
        if target is None:
            if getattr(story, "continue_to_page", None):
                target = max(1, min(page_count, int(story.continue_to_page)))
            elif page_count == 1 or not by_page[1] or (rank == "lead" or (rank == "second" and story.importance >= .7) or rank in {"third", "brief", "teaser"}):
                target = 1
            else:
                target = 2 + ((len([ref for refs in by_page.values() for ref in refs]) - len(by_page[1])) % max(1, page_count - 1))
                target = min(page_count, target)
        if story.id not in assigned:
            by_page[target].append(story.id)
            assigned.add(story.id)
    pages = []
    for number in range(1, page_count + 1):
        role = "front" if number == 1 else ("back" if number == page_count else "inside")
        refs = by_page[number]
        pages.append(IssuePlanPage(page_number=number, page_role=role, story_refs=refs, masthead=number == 1, folio=True, surface_budget={"text": 0.62, "photo": 0.22, "white_space": 0.16}))
    return IssuePlan(issue_ref=issue.id, pages=pages, variant=variant, conflicts=[])

def build_text_plans_for_flatplan(issue: Issue, stories: Iterable[Story], flat_plan: IssuePlan) -> List[TextPlan]:
    """Create copy budgets before geometry is generated.

    A flatplan knows page ownership but not final scene-graph frames.  These
    plans therefore use conservative role presets as a planning measure and
    carry a stable ``frame_ref`` that the geometry pass can replace.  The
    target is derived from the supplied story, so this step never invents
    editorial copy; it only decides which approved variant should be tested
    against a page budget.
    """
    story_map = {story.id: story for story in stories}
    page_by_story: dict[str, int] = {}
    for page in flat_plan.pages:
        for story_ref in page.story_refs:
            page_by_story.setdefault(story_ref, page.page_number)

    role_presets = {
        "headline": {"width_mm": 120.0, "height_mm": 24.0, "columns": 1, "font": 26.0, "overflow": "manual"},
        "deck": {"width_mm": 115.0, "height_mm": 24.0, "columns": 2, "font": 12.0, "overflow": "shorten"},
        "lead": {"width_mm": 120.0, "height_mm": 62.0, "columns": 3, "font": 10.5, "overflow": "alternate"},
        "body": {"width_mm": 120.0, "height_mm": 145.0, "columns": 3, "font": 9.0, "overflow": "alternate"},
        "caption": {"width_mm": 52.0, "height_mm": 22.0, "columns": 1, "font": 7.0, "overflow": "shorten"},
        "byline": {"width_mm": 52.0, "height_mm": 10.0, "columns": 1, "font": 8.0, "overflow": "shorten"},
    }
    # A main/front-page story receives a larger editorial budget.  The values
    # are caps, not requested copy length; a shorter source remains shorter.
    page_caps = {"front": 560, "inside": 360, "back": 420}
    output: List[TextPlan] = []
    for story in sorted(story_map.values(), key=lambda item: item.importance, reverse=True):
        page_number = page_by_story.get(story.id)
        if page_number is None:
            continue
        page = next((item for item in flat_plan.pages if item.page_number == page_number), None)
        page_role = page.page_role if page else "inside"
        story_count = max(1, len(page.story_refs) if page else 1)
        story_cap = round(page_caps.get(page_role, 360) / story_count * (0.72 + 0.56 * story.importance))
        roles = [role for role in ("headline", "deck", "lead", "body", "caption", "byline") if getattr(story, role, None)]
        for role in roles:
            text = str(getattr(story, role) or "")
            words = len(text.split())
            if not words:
                continue
            preset = role_presets[role]
            target = min(words, story_cap) if role == "body" else words
            if role == "body":
                minimum = max(1, round(target * 0.70))
                maximum = max(target, minimum)
            elif role == "headline":
                minimum, maximum = 1, max(12, target)
            else:
                minimum, maximum = max(1, round(target * 0.65)), max(target, 1)
            target_lines = max(1, round(target * (0.42 if role == "body" else 0.70)))
            output.append(TextPlan(
                story_ref=story.id,
                issue_ref=issue.id,
                page_ref=f"{issue.id}:page-{page_number}",
                frame_ref=f"flatplan:{page_number}:{story.id}:{role}",
                role=role,
                flow_group=f"page-{page_number}:{story.id}",
                target_words=target,
                min_words=minimum,
                max_words=maximum,
                target_lines=target_lines,
                columns=int(preset["columns"]),
                width_mm=float(preset["width_mm"]),
                height_mm=float(preset["height_mm"]),
                priority=float(story.importance),
                required=role in {"headline", "body"},
                keep_with_next=role in {"headline", "deck", "lead"},
                no_break_tokens=list(story.locked_passages),
                overflow_policy=preset["overflow"],
                min_font_size_pt=float(preset["font"]),
                status="draft",
            ))
    return output
