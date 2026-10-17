---
name: zecro-petla-ai
description: Pętla AI dyrektor artystyczny – silnik – redaktor techniczny – sędzia w Zecro (art_director.py, prompty art_director/layout_review/layout_pairwise). Używaj przy uruchamianiu, debugowaniu i ulepszaniu pętli, ruchów kompozytorów i promptów oceny.
---

# Pętla AI Zecro

## Architektura
- `backend/app/engine/art_director.py`: `COMPOSERS` (`framed_cover:wukadka`, `planned_page:<archetyp>:<strefa>`), `Move` (ruchy, które dyrektor może wykonać), `measure_moves` (silnik mierzy opcje, np. łamania tytułu z `dziura_okna_cm2`), `art_direct(...)`.
- Dyrektor (`ai/prompts/art_director.md`) planuje wyłącznie ruchami kompozytora. Redaktor (`layout_review.md`) dostaje pomiary jako fakty, normy z korpusu i katalog defektów. Sędzia (`layout_pairwise.md`) porównuje dwie strony w obu kolejnościach; remis rozstrzyga `norm_distance`, potem waga defektów.
- `_against_measurements`: defekty mierzone przez silnik (D07, D09, D26, D27, D29, D30), których bramka nie potwierdziła, są odrzucane razem z poprawkami opartymi tylko na nich.
- `_vet`: przed kolejną rundą poprawki są próbowane na silniku; ruch, który łamie bramkę, odpada z zapisanym powodem.
- Schematy odpowiedzi: `ai/schemas.py` (`ArtPlan`, `LayoutReview`), rejestr zadań: `ai/integration_registry.py`.

## Uruchamianie
- `cd backend && ZECRO_DATA_DIR=<katalog> ../.venv/bin/python -u -m scripts.art_direct_demo --composer framed_cover:wukadka --tag <tag> --rounds 4 --step 1 [--resume]`
- Ślad: `output/wukadka-demo/<tag>.trace.json` (plan, geny, naruszenia bramki, recenzja, odrzucone ruchy, werdykty sędziego), rundy: `<tag>-r<N>.png/pdf`.
- Klucze API są w środowisku (`.env.local`). Nigdy ich nie wypisuj, nie loguj i nie wpisuj do kodu.

## Znane problemy do rozwiązania
1. Oscylacja: redaktor przełącza narożnik ↔ pasek dolny i wraca do już ocenianych genów. Kierunek: przekazywać redaktorowi historię prób (geny + wynik bramki) i blokować powrót do przegranej konfiguracji.
2. Ruchy `hero_shift` i `hero_dy` nie działają w trybie `breakout` (domyślnym). Ukryj je przed dyrektorem w tym trybie albo podłącz do solvera jako preferencję.
3. Redaktor wizyjny bywa nietrafny (np. „8 pt”, „kikut” tam, gdzie go nie ma). Rozszerzaj listę defektów mierzonych i dodawaj pomiary do `measurements()`.
4. Krok pętli trwa 2–3 min; `_vet` ma limit prób (3).
