# Raport końcowy — Etap 2 (domknięcie)

Data: 2026-10-11

## Wynik testów

- Backend w bieżącym środowisku: **64 passed, 12 skipped, 5 deselected** (`pytest -q`; 76 testów jest wybranych przez konfigurację). Skips dotyczą braku `fontTools`/`uharfbuzz`/`opencv`/`shapely` oraz zakazu nasłuchu localhost w sandboxie. Pozostaje 1 ostrzeżenie deprecacyjne `httpx`.
- Testy z prawdziwym Gemini nie są odtwarzalne w tym środowisku: pakiet `google-genai` nie jest zainstalowany, a dostęp do PyPI/sieci jest niedostępny. Commit `8c7bb7b` zawiera testy oznaczone `live_ai`/`live_net`, ale nie traktuję ich jako lokalnie wykonanych.
- Frontend: `npm run build` (tsc + vite) → **sukces**.
- InDesign 2026: commit `8c7bb7b` zawiera ręczny raport Claude’a o otwarciu paczki, lecz InDesign nie jest dostępny w tym środowisku do niezależnego powtórzenia.
- Testy nie łączą się z produkcyjnym Supabase (`backend/tests/conftest.py` wymusza lokalny SQLite).

## Kryteria akceptacji

| # | Status | Dowód |
|---|---|---|
| 1 | **PASS** | `test_seven_story_front_uses_ranks_and_passes` (broadsheet i tabloid): ≥3 kandydatów PASS, ≥3 różne architektury, każdy z 7 tytułów dokładnie raz, jedna dominanta. |
| 2 | **PASS** | `test_inner_page_packs_twelve_manual_ranks_and_respects_pins`; ręczny układ: `test_fixed_plan_geometry_is_binding` (slot przesunięty/zwężony w UI jest wiążący dla składu). |
| 3 | **PASS** | Copyfit na prawdziwym pomiarze HarfBuzz; `fit_adjustments` i `underfill_mm` w metadanych; raport niedopełnienia zamiast dopisywania treści. |
| 4 | **PASS** | Strażnik deterministyczny + AI; `test_live_fit_to_frame_is_source_bound` — brak nowych liczb w tekście Gemini. |
| 5 | **FAIL — środowisko** | Test dokładnych linii jest obecny, ale pominięty bez FontTools/HarfBuzz. Bez tych bibliotek PDF przełącza się jawnie na estymator/fallback ReportLab. |
| 6 | **FAIL — środowisko** | Test konturu jest obecny, ale pominięty bez OpenCV/Shapely; ścieżka produkcyjna nie fabrykuje maski i zwraca jawny brak geometrii. |
| 7 | **PASS** | `/health/ai` i jawne `unavailable` przy braku dostawcy (`test_no_provider_is_explicitly_unavailable`). |
| 8 | **PASS** | Odmowa fotorealizmu dla prawdziwych osób/zdarzeń; ilustracje AI oznaczone XMP `trainedAlgorithmicMedia` i podpisem. |
| 9 | **FAIL — częściowo** | Strukturalne testy IDML przechodzą, a ręczna weryfikacja jest opisana w commicie Claude’a; brak niezależnego otwarcia w InDesign w tym środowisku. |
| 10 | **PASS** | `test_routing_switch_and_fallback_are_in_provenance`: przełączenie routingu i fallback widoczne w provenance. |
| 11 | **FAIL — częściowo** | `test_logo_shape_drives_masthead_and_palette` przechodzi; test PDF i pełny preflight zależny od fontów/Gemini nie został wykonany tutaj. |
| 12 | **PASS** | `test_connector_maps_custom_api_and_blocks_private_in_cloud`, `test_openapi_import_suggests_mapping`, `test_custom_api_openverse_equals_builtin`. |
| 13 | **PASS — z pominięciami** | 64 testy przechodzą; 12 jest jawnie pominiętych z powodu brakujących zależności lub ograniczenia sandboxa. `test_api_studio_smoke` jest pominięty razem z biblioteką fontów. |

## Co jest w interfejsie

- **Makieta**: lista N tekstów z rangą, miejscem, szerokością w szpaltach, zdjęciem; „Oblicz plan”, „Zaproponuj plan (AI)” (3 propozycje z uzasadnieniem), przeciąganie i skalowanie modułów na siatce (układ staje się wiążący), wykrywanie kolizji, „Generuj stronę”.
- **Dobór zdjęć** (z makiety): brief AI → wyszukiwanie w źródłach → ranking na obrazach → przyjęcie (pobranie, punkt ostrości, podpis) albo ilustracja AI.
- **Otekstowanie**: operacje AI na ramie (skrót do ramy, warianty tytułu mierzone fontem, zapowiedź, cytaty dosłowne, ramka faktów, tłumaczenie, kontrola faktów wersji roboczej) z flagami strażnika.
- **DNA → Winieta i logo**: upload SVG/PDF/PNG/JPG, geometria, kolory RGB→CMYK, preflight, analiza AI, zatwierdzenie palety i pary fontów.
- **AI i źródła**: modele (test z listą modeli i próbą wywołania), routing z łańcuchem zapasowym i temperaturą, źródła zdjęć/tekstów, własne API z importem OpenAPI i podglądem surowej odpowiedzi, archiwum, fonty, limity i cennik, dziennik zmian.
- **Fonty**: baza lokalna zawiera 779 odmian i 146 rodzin; źródłowy katalog `Fonts/` jest lokalny i ignorowany przez Git, a pliki są trzymane w runtime `backend/data/fonts`.

## Korpus

Audyt Gemini 1133 stron: 575 przyjętych, 558 odrzuconych (oprawy, karty katalogowe ERIC/CIA, siatki Midjourney, dokumenty). 493 przeniesione do `corpus/_quarantine/` (folder `wukadka` wyłączony z przenoszenia — to własne materiały). `FEATURE_INDEX.json` przycięty do 548 stron z przeliczeniem archetypów (`scripts/prune_feature_index.py`).

## Uruchomienie lokalne

```bash
cd /Users/macbookpro/PROJEKTY/LAYOUT
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload          # backend
cd frontend && npm install && npm run dev      # frontend
```

`.env.local` zawiera `GEMINI_API_KEY`, `ZECRO_ADMIN_TOKEN` (wpisywany w panelu „AI i źródła”) i `ZECRO_SECRETS_KEY` (szyfrowanie kluczy zapisanych w panelu).
