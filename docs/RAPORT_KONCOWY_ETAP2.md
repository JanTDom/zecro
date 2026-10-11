# Raport końcowy — Etap 2

Data: 2026-10-11

## Wynik testów

- Backend: `pytest -q` → **60 passed**, 1 ostrzeżenie deprecacyjne `httpx`/Starlette.
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
| 5 | **FAIL — częściowo** | `test_shaper_is_explicitly_estimate_without_font` dowodzi tylko jawnego trybu `estimate`; brak testu zgodności 0 linii z renderem PDF, a biblioteki fontów nie są zainstalowane. |
| 6 | **FAIL — środowisko** | Implementacja OpenCV/rembg/Shapely jest realna i bez fallbacku, ale biblioteki są nieobecne; test potwierdza brak fabrykowania konturu dla brakującej maski. |
| 7 | **PASS** | `test_health_ai_reports_missing_key`; `/health/ai` zwraca 503 `unavailable`, pasek UI pokazuje stan niedostępności. |
| 8 | **PASS** | `test_real_event_image_generation_is_refused`; zdarzenie z nazwiskiem odmawia fotorealizmu. |
| 9 | **FAIL — częściowo** | Istniejące testy rendererów i IDML (`test_renderers.py`, `test_idml_production.py`, testy API eksportu) przechodzą, ale nie sprawdzają otwarcia nowych modułów w InDesign ani wątkowania ich ramek. |
| 10 | **FAIL — częściowo** | `test_admin_integration_secret_is_encrypted_and_masked` potwierdza szyfrowanie i maskowanie. Test połączenia ma realny probe, ale brak testu przełączenia routingu i provenance kolejnego wyniku. |
| 11 | **FAIL — częściowo** | `test_logo_profiles_change_masthead_geometry` potwierdza różne warianty geometrii. Brak testu pełnego preflight CMYK/TAC, otwarcia PDF/IDML i propozycji Gemini. |
| 12 | **FAIL — częściowo** | `test_custom_api_blocks_private_cloud_endpoint` potwierdza blokadę SSRF. Brak testu end-to-end mapowania Openverse przez własne API. |
| 13 | **PASS** | Pełny zestaw 60 testów przechodzi. |

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

