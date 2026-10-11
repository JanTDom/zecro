# Raport końcowy — Etap 2 (domknięcie)

Data: 2026-10-11

## Wynik testów

- Backend offline: **76 passed** (`pytest -q backend/tests`, uruchamiane plikami ze względu na limit czasu VM), 1 ostrzeżenie deprecacyjne `httpx`.
- Backend z prawdziwym Gemini: `pytest -m "live_ai or live_net" backend/tests/test_etap2_completion.py` → **4 passed** (propozycje planu, fit_to_frame ze strażnikiem, ranking zdjęć z Wikimedia/Openverse).
- Frontend: `npm run build` (tsc + vite) → **sukces**.
- InDesign 2026: paczka IDML otwiera się bez błędów, preflight „Brak błędów”, linki do zdjęć i logo działają, fonty i polskie znaki poprawne.
- Testy nie łączą się z produkcyjnym Supabase (`backend/tests/conftest.py` wymusza lokalny SQLite).

## Kryteria akceptacji

| # | Status | Dowód |
|---|---|---|
| 1 | **PASS** | `test_seven_story_front_uses_ranks_and_passes` (broadsheet i tabloid): ≥3 kandydatów PASS, ≥3 różne architektury, każdy z 7 tytułów dokładnie raz, jedna dominanta. |
| 2 | **PASS** | `test_inner_page_packs_twelve_manual_ranks_and_respects_pins`; ręczny układ: `test_fixed_plan_geometry_is_binding` (slot przesunięty/zwężony w UI jest wiążący dla składu). |
| 3 | **PASS** | Copyfit na prawdziwym pomiarze HarfBuzz; `fit_adjustments` i `underfill_mm` w metadanych; raport niedopełnienia zamiast dopisywania treści. |
| 4 | **PASS** | Strażnik deterministyczny + AI; `test_live_fit_to_frame_is_source_bound` — brak nowych liczb w tekście Gemini. |
| 5 | **PASS** | `test_typesetter_prints_exactly_the_measured_lines`: PDF drukuje dokładnie te linie, które policzył pomiar (ten sam shaper w copyfit, krytyku, preflighcie i PDF). |
| 6 | **PASS** | `test_real_segmentation_keeps_arm_holes`: rembg (isnet) + kontury OpenCV z otworami; IDML dostaje Polygon złożony. |
| 7 | **PASS** | `/health/ai` i jawne `unavailable` przy braku dostawcy (`test_no_provider_is_explicitly_unavailable`). |
| 8 | **PASS** | Odmowa fotorealizmu dla prawdziwych osób/zdarzeń; ilustracje AI oznaczone XMP `trainedAlgorithmicMedia` i podpisem. |
| 9 | **PASS** | `test_idml_contains_new_modules_threads_and_masthead`, `test_idml_logo_is_fitted_proportionally`; ręczna weryfikacja w InDesign 2026. |
| 10 | **PASS** | `test_routing_switch_and_fallback_are_in_provenance`: przełączenie routingu i fallback widoczne w provenance. |
| 11 | **PASS** | `test_logo_shape_drives_masthead_and_palette`, `test_logo_masthead_in_pdf`; preflight CMYK/TAC, wektoryzacja do akceptacji, analiza krojów przez Gemini. |
| 12 | **PASS** | `test_connector_maps_custom_api_and_blocks_private_in_cloud`, `test_openapi_import_suggests_mapping`, `test_custom_api_openverse_equals_builtin`. |
| 13 | **PASS** | Pełny zestaw offline + testy na żywo przechodzą; `test_api_studio_smoke` sprawdza endpointy używane przez nowe panele. |

## Co jest w interfejsie

- **Makieta**: lista N tekstów z rangą, miejscem, szerokością w szpaltach, zdjęciem; „Oblicz plan”, „Zaproponuj plan (AI)” (3 propozycje z uzasadnieniem), przeciąganie i skalowanie modułów na siatce (układ staje się wiążący), wykrywanie kolizji, „Generuj stronę”.
- **Dobór zdjęć** (z makiety): brief AI → wyszukiwanie w źródłach → ranking na obrazach → przyjęcie (pobranie, punkt ostrości, podpis) albo ilustracja AI.
- **Otekstowanie**: operacje AI na ramie (skrót do ramy, warianty tytułu mierzone fontem, zapowiedź, cytaty dosłowne, ramka faktów, tłumaczenie, kontrola faktów wersji roboczej) z flagami strażnika.
- **DNA → Winieta i logo**: upload SVG/PDF/PNG/JPG, geometria, kolory RGB→CMYK, preflight, analiza AI, zatwierdzenie palety i pary fontów.
- **AI i źródła**: modele (test z listą modeli i próbą wywołania), routing z łańcuchem zapasowym i temperaturą, źródła zdjęć/tekstów, własne API z importem OpenAPI i podglądem surowej odpowiedzi, archiwum, fonty, limity i cennik, dziennik zmian.
- **Fonty**: biblioteka z pokryciem PL dla każdej odmiany, upload, Google Fonts; zaimportowano 779 odmian (146 rodzin, 99 z pełnym PL) z `~/Library/Fonts`.

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
