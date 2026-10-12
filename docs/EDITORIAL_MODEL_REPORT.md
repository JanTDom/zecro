# Raport wdrożenia modelu redakcyjnego

Data: 2026-10-12

## Zakres

Dodano wersjonowany model wydania (`Edition`, `EditorialPage`), typy stron,
środkową rozkładówkę, elementy stałe, katalog reklam i walidator twardych
więzów. Reklamy są zablokowane, advertorial wymaga etykiety, a kolizje
konkurencyjne i kontekstowe są flagowane.

Materiały mają rangi A/B/C, elementy z `source`, `lock`, zakresem długości,
statusem i `verbatim`. Dodano shorty, poczekalnię, liczenie powierzchni
redakcyjnej, sugestię pojemności i przyrostową obsługę późnej zmiany reklamy.

Wydania są zapisywane jako `editorial_edition` w istniejącym store rewizji.
Panel „Wydanie” pozwala wybrać stronę, dodać moduł z katalogu, zaimportować
CSV, oznaczyć reklamę jako tentative i dodać short do bufora strony.

## Migracja i zachowanie istniejących funkcji

Migracja `migrate_editorial_model` otwiera stare jedno-stronicowe materiały i
tworzy kompatybilny plan czterostronicowy. Istniejące Scene Graph, generator,
krytyk i provider registry pozostają bez zmian. Eksporty zostały rozszerzone o
zachowanie etykiet advertorial w SVG, HTML i IDML.

## Uruchomienie

```bash
pytest -q backend/tests
uvicorn backend.app.main:app --reload
```

Endpointy modelu są dostępne pod `/editorial-model/*`, w tym `/editions`,
`/editions/migrate`, `/editions/validate`, `/ads/import-csv` i `/copyfit`.
Przykładowe dane akceptacyjne są w `examples/editorial_edition_16.json`, a
stary kontrakt migracyjny w `examples/editorial_legacy_v1.json`.

## Instrukcja redakcyjna

1. Utwórz wydanie przez `/editorial-model/editions` i wybierz objętość 4/8/16.
2. Dodaj reklamy z katalogu DNA albo zaimportuj CSV; oznacz tentative, jeśli
   potrzebujesz dwóch wariantów strony.
3. Dodaj materiały A/B/C i źródła, a następnie wylicz `editorial_area`.
4. Art Director generuje warianty grafu sceny na obszarze redakcyjnym.
5. Copyfit raportuje `delta`; skróty przechodzą przez source guard i diff.
6. Krytyk uruchamia bramkę twardych więzów, potem ranking miękki.
7. Zatwierdź wariant i eksportuj istniejącą ścieżką SVG/HTML/PDF/IDML.

Etykiety advertorial są przekazywane przez `SceneGraph.metadata` jako
`advertorial_labels` i `advertorial_ids`; preflight odrzuca brak etykiety,
a renderery SVG, HTML i IDML zachowują ją w wyniku.

## Otwarte pozycje

Zobacz [OPEN_ITEMS.md](OPEN_ITEMS.md). Decyzje są w
[DECISIONS.md](DECISIONS.md), a pełny audyt w
[AUDIT_EDITORIAL_MODEL.md](AUDIT_EDITORIAL_MODEL.md).
