# Changelog — Etap 2

## 2026-10-11 — domknięcie

- IDML otwiera się w InDesign 2026: instrukcja `aid`, sekcja, style bazowe, warstwy, linie jako GraphicLine, logo dopasowane proporcjonalnie w ramce, ścieżki linków przemapowane na Maca, paczka z Links/Document fonts.
- Makieta: ręczna edycja slotów (przeciąganie, skalowanie) z `PagePlan.geometry = "fixed"` honorowanym przez kompozytor; 3 propozycje planu z Gemini; generowanie strony prosto z makiety.
- Nowe panele: dobór zdjęć i ilustracji, operacje AI w otekstowaniu ze strażnikiem, winieta i logo, pełne ustawienia AI i źródeł, biblioteka fontów.
- Ilustracje i zaakceptowane zdjęcia dostają publiczny URL (`/static/uploads/…`) używany przez podgląd i renderery.
- Import 779 odmian fontów z Maca (wznawialny, pomija puste pliki i zbyt wolne kolekcje); fonty odnajdywane także po przeniesieniu biblioteki.
- Audyt korpusu dokończony, odrzucone strony w kwarantannie, indeks cech przycięty (`scripts/prune_feature_index.py`).
- Wygenerowane `ZECRO_ADMIN_TOKEN` i `ZECRO_SECRETS_KEY` w `.env.local`.

## 2026-10-11

### Etap 1 — plan, integracje, moduły i logo

- Dodano wersjonowany `PagePlan`, deterministiczny packer oraz endpoint `POST /projects/{project_id}/page-plan`.
- Rangi, piny, strony kontynuacji, zapowiedzi i grupy są polami `StoryInput`/`Story`; `build_flat_plan()` został zastąpiony planem rank-aware.
- Naprawiono podwójne składanie: `teaser_only` trafia do paska, a pełny tekst pozostaje na stronie rozwinięcia.
- Dodano moduły `brief_column`, `pullquote`, `infobox`, `jump_line`, `teaser_band`, `column` i `masthead` w grafie oraz rendererach SVG/HTML/IDML.
- Dodano panel `Ustawienia → AI i źródła`, routing zadań, limity, audit log, szyfrowanie sekretów i blokadę SSRF dla własnych API.
- Dodano analizę logo, profil `logo_profile` i umieszczanie logo w grafie oraz IDML.

### Etap 2 — redakcja i pomiar

- Dodano oficjalnego klienta Gemini, pliki promptów, cache `ai_calls`, provenance i `/health/ai`.
- Dodano `source_guard`, `fit_to_frame`, warianty nagłówków oraz jawne statusy `draft`/`unavailable`.
- Dodano shaper z próbą użycia fontTools/uharfbuzz/pyphen oraz deterministycznym statusem `estimate` bez fontu.

### Etap 3 — szparowanie

- Kontur korzysta z realnej maski alfa i hierarchii otworów OpenCV; brak maski nie fabrykuje geometrii.
- `auto_cutout` próbuje lokalnej segmentacji `rembg`, a przy braku zależności zwraca `unavailable`/HTTP 503.

### Etap 4 — fotoedycja

- Dodano konserwatywny `PhotoBrief` i twardą odmowę fotorealistycznego obrazu dla prawdziwego zdarzenia lub nazwanych osób.
- Generator dodaje provenance i podpis AI wyłącznie dla faktycznie wygenerowanych ilustracji.

### Etap 5 — krytyk i audyt korpusu

- Zachowano rozdział twardej bramki i miękkiego rankingu krytyka.
- `scripts/audit_corpus.py` przeskanował 1145 plików: 48 odrzuconych heurystycznie, 1097 z wynikiem `unavailable` bez Gemini.

### Weryfikacja

- `pytest -q`: **60 passed**, 1 ostrzeżenie deprecacyjne Starlette/httpx.
- `cd frontend && npm run build`: **sukces**, Vite wygenerował produkcyjny bundle.
- `python3 -m compileall -q backend/app scripts/audit_corpus.py`: **sukces**.
- Pomiar 7 tekstów: 8 kandydatów w każdym presecie, architektury `dominant-left`, `dominant-right`, `modular-grid`, `stacked`, wszystkie z twardą bramką PASS.
- Pomiar 12 tekstów: 12 slotów, status `valid`, walidacja bez błędów w broadsheet i tabloid.

