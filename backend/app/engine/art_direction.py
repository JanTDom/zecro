"""Explainable art-direction and frame-bound copy planning.

The layout generator explores geometry; this module explains why a candidate
works as a newspaper page and turns every text frame into an actionable
writing brief.  It never writes or edits facts.  A deterministic planner makes
the contract useful without an LLM, while a future writer can consume the same
copy slots and return source-bound variants.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from ..models.schemas import (
    ArtDirectionPlan,
    CopySlotPlan,
    PageInputMaterial,
    SceneGraph,
    TitleDNA,
)
from .copyfit import estimate_text_capacity


ARCHITECTURE_INTENT = {
    "dominant-left": (
        "klasyczna dominanta z mocnym wejściem od lewej",
        "Prowadź wzrok od czołówki przez zdjęcie i korpus do prawego pasa skrótów.",
    ),
    "dominant-right": (
        "dominanta po prawej skonfrontowana z pasem krótszych informacji",
        "Rozpocznij od krótkiego kontekstu po lewej, a kulminację umieść w prawej dominantcie.",
    ),
    "stacked": (
        "sekwencja piętrowa z wyraźnym otwarciem i domknięciem u dołu",
        "Czytelnik ma przejść pionowo: obietnica, dowód wizualny, rozwinięcie, drugi temat.",
    ),
    "photo-top": (
        "wizualne otwarcie strony prowadzące do warstwy objaśniającej",
        "Najpierw pokaż wydarzenie, potem nazwij jego sens i dopiero rozwiń fakty.",
    ),
    "modular-grid": (
        "modularna czołówka z równoległymi punktami wejścia",
        "Utrzymaj jedną dominantę, a pozostałe moduły potraktuj jako szybkie, samodzielne wejścia.",
    ),
}


ROLE_JOBS = {
    "kicker": ("ustawić temat i dział", "Nazwij pole tematyczne w 1–4 słowach; nie powtarzaj tytułu."),
    "headline": ("złożyć konkretną obietnicę czytelnikowi", "Podaj zdarzenie i stawkę; użyj czasownika; unikaj ogólnika i komentarza bez faktu."),
    "deck": ("dopowiedzieć kontekst, którego nie mieści tytuł", "Dodaj przyczynę, skalę albo konsekwencję. Nie streszczaj ponownie nagłówka."),
    "lead": ("odpowiedzieć kto, co, gdzie i dlaczego to ważne", "Pierwsze zdanie ma nieść nowy fakt; drugie może wyjaśnić znaczenie."),
    "body": ("dostarczyć dowody i uporządkować narrację", "Prowadź akapitami: fakt → kontekst → konsekwencja. Najważniejsze informacje umieść przed możliwym miejscem cięcia."),
    "caption": ("zidentyfikować obraz i dodać informację", "Napisz, kto lub co jest na zdjęciu, gdzie i kiedy; dodaj fakt niewidoczny w kadrze."),
    "byline": ("zidentyfikować autora", "Użyj redakcyjnej formy podpisu bez dodatkowego komentarza."),
    "pullquote": ("zbudować drugi punkt wejścia", "Wybierz zdanie niosące tezę lub emocję; nie wyrywaj cytatu ze zmieniającego sens kontekstu."),
    "band": ("sprzedać temat poboczny", "Użyj samodzielnej, krótkiej zapowiedzi prowadzącej do konkretu."),
    "infobox": ("skondensować dane", "Zapisz liczby i fakty jako skanowalne punkty; każdy punkt musi być zrozumiały bez tekstu głównego."),
}


def _words(text: str | None) -> int:
    return len((text or "").split())


def _copy_slot(element, dna: TitleDNA) -> CopySlotPlan | None:
    if not element.text_content or element.role not in ROLE_JOBS:
        return None
    style = element.style
    size = float((style.font_size_pt if style else None) or dna.typography.scales.body)
    leading = float((style.line_height_pt if style else None) or size * 1.2)
    columns = max(1, int((style.columns if style else None) or 1))
    report = estimate_text_capacity(
        element.text_content,
        element.frame.w,
        element.frame.h,
        columns,
        size,
        leading,
    )
    source_words = _words(element.text_content)
    # Copyfitting tells us the *ceiling*, not how much copy the editor should
    # invent.  Earlier code turned a large empty frame into an EXPAND order
    # (for example an 18-word secondary became a 343-word brief).  That was a
    # geometry defect masquerading as editorial direction.  Keep supplied
    # copy as the target whenever it fits; only ask for a cut when it cannot.
    capacity_words = max(1, round(report.capacity_characters / 6.4))
    target_words = min(source_words, capacity_words)
    if element.role == "headline":
        target_words = min(source_words, 14)
    elif element.role in {"kicker", "byline"}:
        target_words = min(source_words, 12)
    elif element.role in {"deck", "lead", "caption", "band", "pullquote"}:
        target_words = min(source_words, 70)
    target_chars = min(len(element.text_content.strip()), max(1, round(target_words * 6.4)))
    # Minimums are advisory editorial floors, never a command to fabricate
    # words.  For a short source, the complete source is the valid minimum.
    min_words = max(1, min(source_words, round(target_words * 0.72)))
    max_words = max(min_words, target_words)
    delta = source_words - target_words
    if source_words > max_words or not report.passes:
        fit_status = "SHORTEN"
        recommendations = [f"Skróć o około {max(1, source_words - target_words)} słów i zachowaj najważniejszy fakt."]
    else:
        fit_status = "PASS"
        recommendations = ["Tekst mieści się w tej ramie; nie dopisuj treści tylko po to, by wypełnić biel."]
        if report.free_lines > max(3, report.capacity_lines // 3):
            recommendations.append("Rama ma świadomy oddech. Jeśli strona wymaga większej gęstości, zmień geometrię lub dodaj zatwierdzony moduł, nie sztuczne zdania.")
    if report.widows or report.orphans:
        fit_status = "MANUAL"
        recommendations.append("Przełam ostatni akapit, aby usunąć wdowę lub bękarta.")
    job, instruction = ROLE_JOBS[element.role]
    return CopySlotPlan(
        element_ref=element.id,
        story_ref=element.story_ref,
        role=element.role,
        editorial_job=job,
        writing_instruction=instruction,
        source_words=source_words,
        source_characters=len(element.text_content.strip()),
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        target_lines=max(1, round(report.capacity_lines * 0.82)),
        capacity_lines=report.capacity_lines,
        target_characters=target_chars,
        columns=columns,
        width_mm=round(element.frame.w, 2),
        height_mm=round(element.frame.h, 2),
        fit_status=fit_status,
        delta_words=delta,
        recommendations=recommendations,
    )


def build_art_direction_plan(
    dna: TitleDNA,
    material: PageInputMaterial,
    scene: SceneGraph,
    corpus_guidance: Dict[str, Any] | None = None,
) -> ArtDirectionPlan:
    """Build an art-director decision and exact copy map for a candidate."""

    guidance = dict(corpus_guidance or {})
    architecture = str(scene.metadata.get("layout_mode") or "dominant-left")
    architecture_name, reading_intent = ARCHITECTURE_INTENT.get(
        architecture,
        ("autorska architektura modularna", "Czytaj zgodnie z kolejnością elementów grafu sceny."),
    )
    stories = sorted(material.stories, key=lambda item: item.importance, reverse=True)
    lead = stories[0] if stories else None
    photo_count = sum(len(story.images) for story in stories)
    total_words = sum(_words(story.body) + _words(story.lead) + _words(story.deck) for story in stories)
    body_frames = [element for element in scene.elements if element.role == "body"]
    text_area = sum(element.frame.w * element.frame.h for element in body_frames)
    page_area = float(scene.page.trim[0] * scene.page.trim[1])
    density = text_area / page_area if page_area else 0.0
    if total_words > 750 or density > 0.38:
        copy_strategy = "dense-evidence-led"
    elif photo_count and material.style_blend.dense_to_photo >= 0.55:
        copy_strategy = "visual-first"
    else:
        copy_strategy = "balanced-explanatory"

    copy_slots = [slot for element in scene.elements if (slot := _copy_slot(element, dna))]
    hierarchy = []
    for element in sorted(
        (item for item in scene.elements if item.role in {"headline", "photo", "deck", "lead", "body", "band"}),
        key=lambda item: (-item.importance, item.frame.y, item.frame.x),
    ):
        label = f"{element.role}:{element.story_ref or element.id}"
        if label not in hierarchy:
            hierarchy.append(label)
    reading_path = [element_id for element_id in scene.reading_order if element_id in {item.id for item in scene.elements}]
    active_transgressions = sorted({item for element in scene.elements for item in (element.transgressions or [])})
    sample_count = int(guidance.get("sample_count", 0) or 0)
    # No calibrated preference/VLM model is present in the deterministic
    # path.  A corpus row count is evidence volume, not confidence in an art
    # director's decision, so report zero unless the upstream critic provides
    # an explicit calibrated value.
    confidence = float(guidance.get("confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    lead_title = lead.headline if lead else "materiał strony"
    page_thesis = f"{architecture_name.capitalize()}: „{lead_title}”."
    photo_strategy = "text-led"
    if photo_count:
        photo_strategy = "evidence-photo" if material.style_blend.dense_to_photo < 0.65 else "photo-led"
    decision_trace = [
        f"Wybrano architekturę {architecture}, aby rozdzielić {len(stories)} materiał(y) przy jednej dominancie.",
        f"Plan tekstowy powstał z {len(copy_slots)} rzeczywistych ramek, a nie z ogólnego limitu słów.",
        f"Kierunek zestawiono z {sample_count} zmierzonymi stronami korpusu; to prior, nie werdykt gustu.",
        "Pewność pozostaje 0 bez skalibrowanego modelu preferencji lub sędziego VLM.",
        f"Portfolio strategii korpusu: {', '.join(sorted((guidance.get('strategy_distribution') or {}).keys())) or 'brak profilu'}.",
        reading_intent,
    ]
    return ArtDirectionPlan(
        architecture=architecture,
        page_thesis=page_thesis,
        hierarchy=hierarchy,
        reading_path=reading_path,
        photo_strategy=photo_strategy,
        copy_strategy=copy_strategy,
        allowed_transgressions=active_transgressions,
        hard_constraints=[
            "jedna dominanta redakcyjna",
            "pełny copyfit bez oversetu",
            "czytelna miara kolumny",
            f"zdjęcia co najmniej {dna.photo_rules.min_dpi:g} efektywnych dpi",
            "brak niedozwolonych kolizji",
        ],
        corpus_evidence={
            "sample_count": sample_count,
            "used_fallback": bool(guidance.get("used_fallback", False)),
            "archetype": guidance.get("archetype") or dna.archetype,
            "zone": guidance.get("zone") or material.page_zone,
            "columns_mean": guidance.get("columns_mean"),
            "photo_coverage_pct_mean": guidance.get("photo_coverage_pct_mean"),
            "text_coverage_pct_mean": guidance.get("text_coverage_pct_mean"),
            "strategy_distribution": guidance.get("strategy_distribution", {}),
            "strategy_profiles": guidance.get("strategy_profiles", {}),
        },
        content_diagnosis={
            "stories": len(stories),
            "photos": photo_count,
            "source_words": total_words,
            "body_surface_ratio": round(density, 4),
            "lead_story_ref": lead.id if lead else None,
            "lead_importance": lead.importance if lead else 0.0,
        },
        decision_trace=decision_trace,
        copy_slots=copy_slots,
        confidence=round(confidence, 3),
    )

