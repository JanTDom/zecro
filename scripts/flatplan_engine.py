#!/usr/bin/env python3
"""
Zecro Flatplan & Pagination Engine.

Manages newspaper issue flatplans, pagination, spread balancing (verso/recto),
ad-to-editorial ratio auditing, and signature (składka drukarska) compliance.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AdSlot:
    slot_id: str
    name: str
    width_cols: int
    height_mm: float
    page: int
    is_advertorial: bool = False
    rate_pln: float = 0.0


@dataclass
class StorySlot:
    story_id: str
    headline: str
    section: str
    page: int
    width_cols: int
    height_mm: float
    word_count_target: int = 0
    is_lead: bool = False


@dataclass
class PagePlan:
    page_number: int
    page_type: str  # cover, inside, back_cover
    side: str  # recto (right/odd), verso (left/even)
    section: str
    columns_total: int
    page_height_mm: float
    page_width_mm: float
    stories: List[StorySlot] = field(default_factory=list)
    ads: List[AdSlot] = field(default_factory=list)

    @property
    def total_ad_area_sqmm(self) -> float:
        col_width_mm = (self.page_width_mm - 30) / max(1, self.columns_total)
        return sum(ad.width_cols * col_width_mm * ad.height_mm for ad in self.ads)

    @property
    def page_printable_area_sqmm(self) -> float:
        return (self.page_width_mm - 30) * (self.page_height_mm - 40)

    @property
    def ad_density(self) -> float:
        printable = self.page_printable_area_sqmm
        return (self.total_ad_area_sqmm / printable) if printable > 0 else 0.0


@dataclass
class IssuePlan:
    title: str
    issue_number: int
    page_count: int
    page_width_mm: float = 289.0  # Wukadka Berliner-like / Tabloid standard
    page_height_mm: float = 380.0
    columns: int = 5
    pages: List[PagePlan] = field(default_factory=list)

    def validate_signatures(self) -> List[str]:
        issues = []
        if self.page_count % 4 != 0:
            issues.append(
                f"Page count ({self.page_count}) is not divisible by 4 (required for printing signature/składka)."
            )
        if self.page_count < 4:
            issues.append("An issue must have at least 4 pages.")
        return issues

    def audit_ad_ratios(self, max_ratio: float = 0.40) -> List[str]:
        issues = []
        for p in self.pages:
            if p.ad_density > max_ratio:
                issues.append(
                    f"Page {p.page_number} ({p.section}) ad density is {p.ad_density*100:.1f}%, exceeding maximum {max_ratio*100:.0f}%."
                )
        return issues

    def get_spreads(self) -> List[Dict[str, Any]]:
        spreads = []
        if not self.pages:
            return spreads

        # Page 1 is standalone cover (recto)
        spreads.append({"spread_id": "cover", "left": None, "right": self.pages[0]})

        # Subsequent pairs
        idx = 1
        while idx < len(self.pages) - 1:
            left_page = self.pages[idx]
            right_page = self.pages[idx + 1] if idx + 1 < len(self.pages) else None
            spreads.append({
                "spread_id": f"pages_{left_page.page_number}-{right_page.page_number if right_page else ''}",
                "left": left_page,
                "right": right_page,
            })
            idx += 2

        # Last page if standalone back cover
        if idx < len(self.pages):
            spreads.append({"spread_id": "back_cover", "left": self.pages[idx], "right": None})

        return spreads


def create_default_issue(title: str = "Wukadka", issue_nr: int = 21, pages: int = 8) -> IssuePlan:
    sections = [
        "Okładka",
        "Wiadomości Lokalne",
        "Inwestycje i Transport",
        "Społeczność i Historia",
        "Kultura i Reportaż",
        "Publicystyka",
        "Edukacja i Ogłoszenia",
        "Ostatnia Strona / Felieton",
    ]

    issue = IssuePlan(title=title, issue_number=issue_nr, page_count=pages, columns=5)

    for i in range(1, pages + 1):
        ptype = "cover" if i == 1 else ("back_cover" if i == pages else "inside")
        side = "recto" if i % 2 == 1 else "verso"
        sec = sections[i - 1] if i - 1 < len(sections) else "Ogólne"
        p = PagePlan(
            page_number=i,
            page_type=ptype,
            side=side,
            section=sec,
            columns_total=5,
            page_height_mm=issue.page_height_mm,
            page_width_mm=issue.page_width_mm,
        )
        issue.pages.append(p)
    return issue


def format_flatplan_markdown(issue: IssuePlan) -> str:
    md = [
        f"# Makieta Wydania: {issue.title} (Nr {issue.issue_number})",
        f"- **Liczba stron:** {issue.page_count} (Składka: {'Zgodna z arkuszem % 4' if issue.page_count % 4 == 0 else 'BŁĄD: niepodzielna przez 4'})",
        f"- **Format:** {issue.page_width_mm:.0f} × {issue.page_height_mm:.0f} mm, {issue.columns} szpalt",
        "",
        "## Rozkład stron (Flatplan Spreads)",
        "| Strona | Typ | Pozycja | Sekcja | Teksty | Reklamy | Gęstość reklam |",
        "|---|---|---|---|---|---|---|",
    ]

    for p in issue.pages:
        ad_pct = f"{p.ad_density*100:.1f}%"
        stories_cnt = len(p.stories)
        ads_cnt = len(p.ads)
        md.append(
            f"| {p.page_number} | {p.page_type} | {p.side} | {p.section} | {stories_cnt} | {ads_cnt} | {ad_pct} |"
        )

    sig_errs = issue.validate_signatures()
    ad_errs = issue.audit_ad_ratios()
    if sig_errs or ad_errs:
        md.append("\n## Ostrzeżenia i błędy preflightu makiety")
        for e in sig_errs + ad_errs:
            md.append(f"- ⚠️ {e}")
    else:
        md.append("\n## Status walidacji: **PASS** (Makieta poprawna technicznie)")

    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Zecro Flatplan & Pagination Engine CLI")
    parser.add_argument("--title", default="Wukadka", help="Title of publication")
    parser.add_argument("--issue", type=int, default=21, help="Issue number")
    parser.add_argument("--pages", type=int, default=8, help="Total page count (multiple of 4)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", type=str, help="Save output to file")
    args = parser.parse_args()

    issue = create_default_issue(title=args.title, issue_nr=args.issue, pages=args.pages)

    if args.json:
        out_text = json.dumps(asdict(issue), indent=2, ensure_ascii=False)
    else:
        out_text = format_flatplan_markdown(issue)

    if args.output:
        Path(args.output).write_text(out_text, encoding="utf-8")
        print(f"Flatplan written to {args.output}")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
