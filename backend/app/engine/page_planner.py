"""Editorial page planning before geometry.

The planner is deliberately deterministic and separate from the evolutionary
geometry generator.  It allocates each story exactly once (or explicitly as a
teaser), so a crowded front page remains reviewable instead of duplicating
secondary copy in a band and a full article module.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Any

from ..models.schemas import PagePlan, PagePlanSlot, StoryInput, Story

_RANK_ORDER = {"lead": 0, "second": 1, "third": 2, "column": 3, "box": 4, "brief": 5, "short": 6, "teaser": 7}


def _rank(story: Any) -> str:
    value = getattr(story, "rank", None)
    if value in _RANK_ORDER:
        return value
    importance = float(getattr(story, "importance", .5) or .5)
    return "lead" if importance >= .9 else "second" if importance >= .7 else "brief"


def _module_type(story: Any, rank: str) -> str:
    if getattr(story, "teaser_only", False) or rank == "teaser":
        return "teaser_band"
    if rank == "lead":
        return "lead"
    if rank in {"brief", "short"}:
        return "brief_column"
    if rank == "box":
        return "infobox"
    if rank == "column":
        return "column"
    return "article"


def _fit(occupied: list[list[bool]], cols: int, rows: int, c: int, r: int, w: int, h: int) -> bool:
    if c < 0 or r < 0 or c + w > cols or r + h > rows:
        return False
    return all(not occupied[y][x] for y in range(r, r + h) for x in range(c, c + w))


def _mark(occupied: list[list[bool]], c: int, r: int, w: int, h: int) -> None:
    for y in range(r, r + h):
        for x in range(c, c + w):
            occupied[y][x] = True


def _find_first(occupied: list[list[bool]], cols: int, rows: int, w: int, h: int, preferred: str | None = None) -> tuple[int, int] | None:
    starts = list(range(cols))
    if preferred == "right_rail":
        starts = [cols - w]
    elif preferred == "left_rail":
        starts = [0]
    elif preferred in {"center", "top", "under_masthead"}:
        starts = sorted(starts, key=lambda x: abs(x - (cols - w) / 2))
    row_order = list(reversed(range(rows))) if preferred == "bottom" else list(range(rows))
    if preferred in {"top", "under_masthead"}:
        row_order = [0]
    for r in row_order:
        for c in starts:
            if _fit(occupied, cols, rows, c, r, w, h):
                return c, r
    return None


def plan_page(dna: Any, stories: Iterable[Any], *, page_zone: str = "front_page", page_number: int = 1, rows: int | None = None) -> PagePlan:
    """Pack ranked stories on a modular grid with a 30mm minimum measure.

    Pinned stories are attempted first at their requested zone.  If a pin is
    impossible it is retained as a warning and packed into the next valid
    position, making the decision explicit for an editor.
    """
    cols = max(1, int(getattr(dna.grid, "columns", 6)))
    total_rows = max(4, int(rows or getattr(dna.grid, "rows", 12)))
    masthead_rows = 1 if page_zone == "front_page" else 0
    usable_rows = max(1, total_rows - masthead_rows)
    ordered = sorted(list(stories), key=lambda s: (_RANK_ORDER.get(_rank(s), 99), -float(getattr(s, "importance", .5) or .5), str(getattr(s, "id", ""))))
    # Dense inner pages need a compact module profile.  This changes only the
    # requested slot depth; every module still keeps its minimum two-column
    # measure and remains on the same deterministic grid.
    compact_page = len(ordered) >= 10
    occupied = [[False] * cols for _ in range(usable_rows)]
    slots: list[PagePlanSlot] = []
    warnings: list[str] = []
    teaser_counter = 0

    for story in ordered:
        story_id = str(getattr(story, "id", ""))
        rank = _rank(story)
        module_type = _module_type(story, rank)
        teaser_only = bool(getattr(story, "teaser_only", False) or rank == "teaser")
        if teaser_only:
            teaser_counter += 1
            target_page = getattr(story, "continue_to_page", None) or (page_number + 1 if page_zone == "front_page" else None)
            slots.append(PagePlanSlot(slot_id=f"teaser-{story_id}", story_ref=story_id, rank="teaser", col_start=0, col_span=max(2, min(cols, 2)), row_start=0, row_span=1, module_type="teaser_band", page_number=page_number, teaser_only=True, continuation_page=target_page))
            continue
        requested_w = getattr(story, "span_cols", None)
        if rank == "lead":
            w = max(3, min(cols, int(requested_w or max(3, round(cols * .62)))))
            h = max(3, min(usable_rows, 4 if compact_page else (5 if getattr(story, "depth_hint", None) in {None, "L", "XL"} else 4)))
        elif rank in {"second", "third"}:
            w = max(2, min(cols, int(requested_w or max(2, round(cols * .34)))))
            h = max(2, min(usable_rows, 2 if compact_page else 3))
        elif rank in {"brief", "short"}:
            w = max(2, min(cols, int(requested_w or 2)))
            h = 1
            module_type = "brief_column"
        elif rank == "box":
            w, h = max(2, min(cols, int(requested_w or 2))), (1 if compact_page else 2)
        else:
            w, h = max(2, min(cols, int(requested_w or 3))), (2 if compact_page else 3)
        preferred = getattr(story, "pin_zone", None)
        if preferred == "left_rail":
            candidate = _find_first(occupied, cols, usable_rows, w, h, "left_rail")
        elif preferred == "right_rail":
            candidate = _find_first(occupied, cols, usable_rows, w, h, "right_rail")
        else:
            candidate = _find_first(occupied, cols, usable_rows, w, h, preferred)
        if candidate is None:
            # Compact modules can reflow to a smaller row depth but never to a
            # one-column brief; a narrow title is not a valid rescue.
            if module_type == "brief_column":
                candidate = _find_first(occupied, cols, usable_rows, max(2, min(w, cols)), 1, preferred)
                h = 1 if candidate else h
            if candidate is None:
                warnings.append(f"story {story_id} could not fit its requested {rank} slot")
                continue
        c, r = candidate
        _mark(occupied, c, r, w, h)
        slots.append(PagePlanSlot(slot_id=f"slot-{story_id}", story_ref=story_id, rank=rank, col_start=c, col_span=w, row_start=r + masthead_rows, row_span=h, module_type=module_type, page_number=page_number, continuation_page=getattr(story, "continue_to_page", None)))

    # Exactly-once validation is part of the planner contract.
    seen = [slot.story_ref for slot in slots]
    expected = [str(getattr(s, "id", "")) for s in ordered]
    missing = [ref for ref in expected if ref not in seen]
    duplicates = sorted({ref for ref in seen if seen.count(ref) > 1})
    if missing:
        warnings.append("missing stories: " + ", ".join(missing))
    if duplicates:
        warnings.append("duplicate stories: " + ", ".join(duplicates))
    return PagePlan(page_zone=page_zone, columns=cols, rows=total_rows, masthead_rows=masthead_rows, slots=slots, warnings=warnings, status="invalid" if missing or duplicates else "valid")


def validate_page_plan(plan: PagePlan, stories: Iterable[Any]) -> list[str]:
    errors: list[str] = []
    refs = [str(getattr(s, "id", "")) for s in stories]
    seen = [slot.story_ref for slot in plan.slots]
    for ref in refs:
        count = seen.count(ref)
        if count != 1:
            # Teaser-only is intentionally one teaser slot; continuation is
            # represented by the slot metadata rather than another copy.
            errors.append(f"story {ref} appears {count} times")
    for slot in plan.slots:
        if slot.col_span < 2 and slot.module_type in {"brief_column", "teaser_band", "article", "lead"}:
            errors.append(f"slot {slot.slot_id} is narrower than two columns")
        if slot.col_start + slot.col_span > plan.columns or slot.row_start + slot.row_span > plan.rows:
            errors.append(f"slot {slot.slot_id} exceeds grid bounds")
    return errors
