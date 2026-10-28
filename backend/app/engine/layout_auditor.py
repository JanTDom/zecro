"""Layout Auditor: Diagnoses defects, visual competition, microtypography,
trapped whitespace, and prepress issues in editorial page layouts.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import Element, SceneGraph, TitleDNA
from .aesthetics import evaluate_page_aesthetics
from .critic import LayoutCritic

POLISH_CONJUNCTIONS_REGEX = re.compile(r'(?:^|\s)([aiouwzAIOUWZ])\s+(?!\s)')


@dataclass
class AuditDefect:
    id: str
    rule_code: str
    severity: str  # "critical" | "warning" | "suggestion"
    message: str
    element_ids: List[str] = field(default_factory=list)
    remedy: str = ""


@dataclass
class LayoutAuditReport:
    overall_score: int  # 0..100
    hard_gate_passed: bool
    aesthetic_score: float  # 0..100
    defects: List[AuditDefect] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "hard_gate_passed": self.hard_gate_passed,
            "aesthetic_score": self.aesthetic_score,
            "defects": [asdict(d) for d in self.defects],
            "recommendations": self.recommendations,
            "metrics": self.metrics,
        }


class LayoutAuditor:
    """Performs deep diagnosis of editorial layouts against newsprint and design invariants."""

    def __init__(self, default_dna: Optional[TitleDNA] = None):
        self.default_dna = default_dna

    def audit_layout(
        self,
        scene: SceneGraph,
        dna: Optional[TitleDNA] = None
    ) -> LayoutAuditReport:
        target_dna = dna or self.default_dna
        if not target_dna:
            from .grammar import create_default_tabloid_dna
            target_dna = create_default_tabloid_dna()

        pw, ph = float(scene.page.trim[0]), float(scene.page.trim[1])
        page_area = max(1.0, pw * ph)
        defects: List[AuditDefect] = []

        # 1. Aesthetic Analysis (Xerox PARC, Sophi.io, Poynter)
        aesthetic_rep = evaluate_page_aesthetics(scene)
        aesthetic_score = round(aesthetic_rep.total_aesthetic_index * 100.0, 1)

        # 2. Hard Gate Checks (Critic)
        critic = LayoutCritic(target_dna)
        hard_gate = critic.evaluate_hard_gate(scene)

        if not hard_gate.passed:
            for i, vio in enumerate(hard_gate.violations):
                defects.append(
                    AuditDefect(
                        id=f"HG-{i+1}",
                        rule_code="HARD_GATE_VIOLATION",
                        severity="critical",
                        message=vio,
                        remedy="Skoryguj nakładanie się elementów lub dodaj regułę allow_stack.",
                    )
                )

        # 3. Visual Dominant & Photo Competition (Rule U1 / Poynter)
        photos = [e for e in scene.elements if e.role == "photo" and e.frame.w > 0 and e.frame.h > 0]
        if len(photos) >= 2:
            sorted_photos = sorted(photos, key=lambda p: p.frame.w * p.frame.h, reverse=True)
            p1_area = sorted_photos[0].frame.w * sorted_photos[0].frame.h
            p2_area = sorted_photos[1].frame.w * sorted_photos[1].frame.h

            p1_share = p1_area / page_area
            p2_share = p2_area / page_area

            # If two photos are large and close in area (< 1.35x difference)
            if p1_share >= 0.12 and p2_share >= 0.10 and (p1_area / max(1.0, p2_area)) < 1.35:
                defects.append(
                    AuditDefect(
                        id=f"DOM-1",
                        rule_code="PHOTO_COMPETITION",
                        severity="warning",
                        message=f"Dwa zdjęcia ({sorted_photos[0].id}, {sorted_photos[1].id}) rywalizują o uwagę ({p1_share*100:.0f}% vs {p2_share*100:.0f}% strony). Brak wyraźnego lidera.",
                        element_ids=[sorted_photos[0].id, sorted_photos[1].id],
                        remedy="Powiększ jedno ze zdjęć do dominacji >= 32% strony lub zredukuj drugie do kadru dopełniającego.",
                    )
                )
        elif len(photos) == 1:
            p_share = (photos[0].frame.w * photos[0].frame.h) / page_area
            if p_share < 0.18 and scene.page.page_zone in ("front_page", "spread"):
                defects.append(
                    AuditDefect(
                        id="DOM-2",
                        rule_code="WEAK_HERO_PHOTO",
                        severity="suggestion",
                        message=f"Główne zdjęcie zajmuje zaledwie {p_share*100:.0f}% strony — punkt wejścia wzroku jest słaby.",
                        element_ids=[photos[0].id],
                        remedy="Zwiększ szerokość zdjęcia do 3-4 szpalt.",
                    )
                )

        # 4. Trapped Whitespace & Dead Fields (Sophi.io / Rule U17)
        if aesthetic_rep.trapped_whitespace_cm2 > 8.0:
            defects.append(
                AuditDefect(
                    id="VOID-1",
                    rule_code="TRAPPED_WHITESPACE",
                    severity="warning" if aesthetic_rep.trapped_whitespace_cm2 > 16.0 else "suggestion",
                    message=f"Wykryto {aesthetic_rep.trapped_whitespace_cm2:.1f} cm² uwięzionej pustki między blokami redakcyjnymi.",
                    remedy="Wypełnij martwe pole wyimkiem cytatu (Pullquote), boksem faktów lub stemplową odznaką.",
                )
            )

        # 5. Typographic Hierarchy & Scale Contrast
        headlines = [e for e in scene.elements if e.role == "headline"]
        body_elements = [e for e in scene.elements if e.role == "body"]

        max_headline_pt = max(
            [(h.style.font_size_pt if h.style else 14.0) or 14.0 for h in headlines],
            default=18.0
        )
        avg_body_pt = (
            sum([(b.style.font_size_pt if b.style else 9.5) or 9.5 for b in body_elements]) / max(1, len(body_elements))
            if body_elements else 9.5
        )

        scale_ratio = max_headline_pt / max(1.0, avg_body_pt)
        if scale_ratio < 2.2 and headlines:
            defects.append(
                AuditDefect(
                    id="TYPO-1",
                    rule_code="FLAT_TYPOGRAPHY",
                    severity="warning",
                    message=f"Tytuł ({max_headline_pt:.1f} pt) ma za mały kontrast skali względem tekstu głównego ({avg_body_pt:.1f} pt, stosunek {scale_ratio:.1f}:1).",
                    element_ids=[h.id for h in headlines[:2]],
                    remedy="Zastosuj wielostopniowy nagłówek (Staged Display Headline) z mocnym słowem-kluczem >= 36 pt.",
                )
            )

        # 6. Polish Microtypography: Hanging Prepositions & Conjunctions
        hanging_elements: List[str] = []
        for e in scene.elements:
            if e.role in ("headline", "lead", "deck", "body", "kicker") and e.text_content:
                if POLISH_CONJUNCTIONS_REGEX.search(e.text_content):
                    hanging_elements.append(e.id)

        if hanging_elements:
            defects.append(
                AuditDefect(
                    id="MICRO-1",
                    rule_code="HANGING_PREPOSITIONS",
                    severity="warning",
                    message=f"Wykryto wiszące spójniki (sierotki) w {len(hanging_elements)} elementach tekstowych.",
                    element_ids=hanging_elements[:5],
                    remedy="Połącz jednoliterowe spójniki (a, i, o, u, w, z) ze słowami twardą spacją (\\u00A0).",
                )
            )

        # 7. Underset Slack in Columns
        # If a body text frame is tall but its text is very short (< 15 words in a frame > 80mm height)
        for b in body_elements:
            words = len((b.text_content or "").split())
            if b.frame.h > 70.0 and words > 0 and words < 30:
                defects.append(
                    AuditDefect(
                        id=f"FIT-{b.id}",
                        rule_code="UNDERSET_SLACK",
                        severity="suggestion",
                        message=f"Szpalta {b.id} zawiera duży luz pionowy ({words} słów w ramce {b.frame.h:.0f} mm).",
                        element_ids=[b.id],
                        remedy="Wstrzyknij ramkę z faktami lub odznakę redakcyjną poniżej tekstu.",
                    )
                )

        # 8. Score Calculation
        score = 100
        if not hard_gate.passed:
            score -= 30
        for d in defects:
            if d.severity == "critical":
                score -= 20
            elif d.severity == "warning":
                score -= 8
            elif d.severity == "suggestion":
                score -= 3

        # Blend with aesthetics
        blended = round(score * 0.6 + aesthetic_score * 0.4)
        overall_score = max(10, min(100, blended))

        # Recommendations summary
        recommendations = list(aesthetic_rep.recommendations)
        for d in defects:
            if d.remedy and d.remedy not in recommendations:
                recommendations.append(d.remedy)

        metrics = {
            "aesthetic_index": aesthetic_rep.total_aesthetic_index,
            "balance_score": aesthetic_rep.balance_score,
            "trapped_whitespace_cm2": aesthetic_rep.trapped_whitespace_cm2,
            "entry_point_score": aesthetic_rep.entry_point_score,
            "bottom_anchor_score": aesthetic_rep.bottom_anchor_score,
            "photo_count": len(photos),
            "elements_count": len(scene.elements),
        }

        return LayoutAuditReport(
            overall_score=overall_score,
            hard_gate_passed=hard_gate.passed,
            aesthetic_score=aesthetic_score,
            defects=defects,
            recommendations=recommendations[:6],
            metrics=metrics,
        )
