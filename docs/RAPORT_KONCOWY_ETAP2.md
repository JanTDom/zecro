# Raport końcowy — Etap 2

Data: 2026-10-11

## Wynik testów

- Backend: `pytest -q` → **57 passed**, 1 ostrzeżenie deprecacyjne `httpx`/Starlette.
- Frontend: `cd frontend && npm run build` → **sukces**.
- Python: `python3 -m compileall -q backend/app scripts/audit_corpus.py` → **sukces**.
- Audyt korpusu: 1145 sprawdzonych, 48 `rejected`, 1097 `unavailable` bez Gemini.

## Kryteria akceptacji

| # | Status | Dowód / ograniczenie |
|---|---|---|
| 1 | **PASS** | `test_evolution_produces_three_architectures_for_seven_stories`; 8 PASS kandydatów w broadsheet i tabloid, 4 architektury, nagłówki dokładnie raz. |
| 2 | **PASS** | `test_inner_page_packs_twelve_manual_ranks_and_respects_pins`; 12 slotów, plan `valid`, walidacja bez błędów w obu presetach. |
| 3 | **PASS** | Pętla copyfit zapisuje `fit_adjustments`; test ewolucji sprawdza obecność metadanych i przejście bramki. |
| 4 | **PASS** | `test_source_guard_rejects_unsupported_number`; dopisana liczba ma status `unsupported`. |
| 5 | **PASS** | `test_shaper_is_explicitly_estimate_without_font`; pomiar zwraca linie i jawny status `estimate`. Pełna zgodność z PDF wymaga zainstalowanego fontu/shapera. |
| 6 | **FAIL — środowisko** | Implementacja OpenCV/rembg/Shapely jest realna i bez fallbacku, ale biblioteki są nieobecne; test potwierdza brak fabrykowania konturu dla brakującej maski. |
| 7 | **PASS** | `test_health_ai_reports_missing_key`; `/health/ai` zwraca 503 `unavailable`, pasek UI pokazuje stan niedostępności. |
| 8 | **PASS** | `test_real_event_image_generation_is_refused`; zdarzenie z nazwiskiem odmawia fotorealizmu. |
| 9 | **PASS** | Istniejące testy rendererów i IDML (`test_renderers.py`, `test_idml_production.py`, testy API eksportu) przechodzą; moduły mają style IDML. Pełna kontrola otwarcia w InDesign wymaga aplikacji DTP. |
| 10 | **PASS** | `test_admin_integration_secret_is_encrypted_and_masked`; sekret jest zaszyfrowany i zamaskowany, endpoint testu wykonuje realny probe dostawcy. |
| 11 | **FAIL — częściowo** | Profil logo, geometria winiety i placed graphic w IDML są zaimplementowane, ale brak osobnego testu akceptacyjnego dla dwóch wariantów logo, CMYK/TAC i live propozycji Gemini. |
| 12 | **FAIL — częściowo** | Rejestr własnych API, import OpenAPI i blokada SSRF są zaimplementowane, ale brak pełnego testu end-to-end mapowania Openverse w bieżącym zestawie. |
| 13 | **PASS** | Pełny zestaw 57 testów przechodzi. |

## Uruchomienie lokalne

```bash
cd /Users/macbookpro/PROJEKTY/LAYOUT
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# backend
uvicorn backend.app.main:app --reload

# frontend
cd frontend
npm install
npm run dev
```

Ustaw `GEMINI_API_KEY` i opcjonalnie `ZECRO_SECRETS_KEY` oraz `ZECRO_ADMIN_TOKEN` w lokalnym `.env.local`. Panel nie pokazuje sekretów po zapisie. Bez pakietu `google-genai` aplikacja działa w trybie offline z jawnym `unavailable` dla AI.

## Zgodność z zasadami projektu

Generator i krytyk są rozdzielone; DNA tytułu i transgresje są danymi; twarde więzy są bramką PASS/FAIL; graf sceny jest wspólnym źródłem podglądu i produkcji; brak maski/modelu nie jest zastępowany atrapą.

