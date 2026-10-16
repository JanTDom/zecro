# Zecro — instrukcje dla Google Antigravity (kontynuacja projektu)

Stan na 16.10.2026. Repozytorium: `/Users/macbookpro/PROJEKTY/LAYOUT` (GitHub `JanTDom/zecro`, gałąź `main`). Frontend: zecro.pl, API: api.zecro.pl (Vercel).

## 1. Cel projektu
Zecro to generator stron gazet i magazynów, który ma pracować jak profesjonalny grafik łamiący, dla każdego typu pisma. Układ: **AI dyrektor artystyczny → silnik kompozycji → bramka jakości → AI redaktor techniczny → AI sędzia porównujący warianty**. Silnik jest deterministyczny i mierzy; AI wybiera ruchy i ocenia, ale nie rysuje geometrii.

## 2. Zasady pracy (obowiązkowe)
- **Sekrety.** Klucze są skonfigurowane w `.env.local` i w Vercel. Nie odczytuj ich do logów, nie wypisuj, nie wpisuj do kodu ani dokumentacji. Klucz Freedom Forum tylko przez env `FF_APPSYNC_KEY`.
- **Git.** Bez `git reset`, `git checkout .`, czyszczenia repozytorium i automatycznego formatowania całego repo. Commit i push tylko na prośbę użytkownika.
- **Jakość.** Nie obniżaj progów bramki, żeby strona przeszła. Nie zmyślaj danych ani liczb; gdy czegoś nie zmierzono, napisz to wprost.
- **Ogólność.** Każdy błąd widoczny na jednej okładce naprawiaj jako zasadę ogólną (prymityw silnika, ograniczenie solvera, reguła bramki) i zabezpieczaj testem.
- **Weryfikacja.** Po każdej zmianie wygeneruj podgląd, obejrzyj PNG (także w zbliżeniu) i uruchom testy.
- **Język.** Interfejs i dokumentacja po polsku.
- **Logowanie.** Nie wpisuj hasła do zecro.pl za użytkownika.
- **Wdrożenie** robi użytkownik: `cd /Users/macbookpro/PROJEKTY/LAYOUT && npx vercel --prod --yes`.

## 3. Skille (folder `.agents/skills/`)
Nowe, przygotowane do tej kontynuacji:
- **`zecro-okladka-ramowa`.** Silnik okładki ramowej (`framed_cover`), prymitywy i bramka, reguły U15–U19, defekty D26–D30, sposób podglądu i warianty do sprawdzania.
- **`zecro-petla-ai`.** Pętla dyrektor–silnik–redaktor–sędzia, uruchamianie `art_direct_demo`, ślad rund i znane problemy pętli.
- **`zecro-korpus-prasy`.** Korpus 14 315 stron (800 tytułów, 39 krajów), skrypty pomiarowe, normy i archetypy, zasady korzystania z liczb.

Istniejące, nadal przydatne:
- **`generative-newspaper-layout`.** Ogólna metodyka layoutu generatywnego.
- **`newspaper-copyfitting-engine`.** Dopasowanie tekstu do kolumn.
- **`newspaper-corpus-dissector`.** Rozbiór siatki i typografii z archiwów.
- **`newspaper-prepress-preflight`.** Kontrola przed drukiem.
- **`newspaper-pdf-export`.** Eksport do PDF.
- **`polish-editorial-proofreading` i `newspaper-editorial-copyediting`.** Korekta i redakcja tekstów po polsku.

Dokumenty wiedzy: `backend/app/knowledge/rulebook.md` (U1–U19, normy N1–N7), `defects.json` (D01–D30), `press_norms.md`; raport z przebiegu prac: `docs/RAPORT_CLAUDE_2026-10-15.md` (części I–VI).

## 4. Mapa kodu
| Obszar | Plik |
|---|---|
| Okładka ramowa | `backend/app/engine/framed_cover.py`, `cover_modules.py` |
| Prymitywy warstwowe | `backend/app/engine/layered_cover.py` |
| Bramka (reguły geometrii) | `backend/app/engine/layered_rules.py`, `critic.py` |
| Wycięcia i krawędzie | `backend/app/engine/cutout_quality.py`, `renderers/pdf_renderer.py` |
| Skład tekstu, dzielenie | `backend/app/engine/shaper.py`, `copyfit.py` |
| Pętla AI | `backend/app/engine/art_director.py`, `backend/app/ai/prompts/{art_director,layout_review,layout_pairwise}.md`, `ai/schemas.py` |
| Normy prasy | `backend/app/engine/press_norms.py`, `backend/app/knowledge/press_norms.*` |
| Kompozytor planowany (inne typy pism) | `backend/app/engine/plan_composer.py` |
| Demo i pętla | `backend/scripts/wukadka_demo.py`, `backend/scripts/art_direct_demo.py` |
| Testy | `backend/tests/` (m.in. `test_layered_cover.py`, `test_knowledge_and_cuts.py`) |

## 5. Polecenia
```bash
# podgląd okładki (wynik: output/wukadka-demo/okladka-<tag>.png/.pdf/.scene.json + GATE PASS/FAIL)
cd backend && ZECRO_DATA_DIR=$HOME/zdata ../.venv/bin/python -m scripts.wukadka_demo --framed --tag t1 --genes '{}'
cd backend && ZECRO_DATA_DIR=$HOME/zdata ../.venv/bin/python -m scripts.wukadka_demo --framed --tag t2 --genes '{"bottom":"strip"}'

# pętla AI, jedna runda na wywołanie
cd backend && ZECRO_DATA_DIR=$HOME/zdata ../.venv/bin/python -u -m scripts.art_direct_demo --composer framed_cover:wukadka --tag ad20 --rounds 4 --step 1
cd backend && ZECRO_DATA_DIR=$HOME/zdata ../.venv/bin/python -u -m scripts.art_direct_demo --composer framed_cover:wukadka --tag ad20 --rounds 4 --step 1 --resume

# testy (z katalogu głównego)
.venv/bin/python -m pytest -q backend/tests
```

## 6. Stan na dziś
- Domyślna okładka (narożnik) przechodzi bramkę. Ręka bohaterki jest cała, krawędź zdjęcia schowana pod belką, okno tytułu wypełnione.
- Wariant z dolnym paskiem: zdjęcie demo ma za mało pikseli, żeby sięgnąć pod belkę (łata 5 cm² → D30). To prawidłowa decyzja bramki.
- Testy: 186 przechodzi, 2 xfail (stary wolny kolaż), 1 znany błąd w kompozytorze kafelkowym (`test_short_source_becomes_an_expansion_request_not_a_hole`, copyfit 1,25×), niezwiązany z okładką ramową.
- Pętla AI działa (dyrektor, redaktor, sędzia, odrzucanie defektów sprzecznych z pomiarem, próba poprawek na silniku), ale nie doszła jeszcze do strony „do druku” i bywa, że oscyluje.

## 7. Zadania w kolejności
1. **Pętla bez oscylacji.** Przekaż redaktorowi historię prób (geny + wynik bramki), zablokuj powrót do przegranej konfiguracji, ukryj ruchy nieaktywne w trybie `breakout` (`hero_shift`, `hero_dy`). Cel: przebieg 4 rund kończy się stroną z bramką PASS, a redaktor nie zgłasza defektu major.
2. **Narożnik z wycięciami (`corner_photos: cutout`).** Usuń pustkę nad głową w żółtym pudełku (D28, 24 cm²): skala i położenie wycięć według wysokości modułu, nie stałej.
3. **Włoskowata linia na wspólnej krawędzi** zdjęcia i plamy w podglądzie PNG: zastosuj w rendererze nadlew 0,2–0,3 mm spodniego elementu pod krawędzią przykrytą przez wyższy.
4. **Przeniesienie zasad U15–U19 do innych kompozytorów:** `plan_composer` (dzienniki, magazyny, program TV) i tabloid‑kolaż. Te same prymitywy (`photo_fill`, `fill_block`, `snap_near_edges`) i ta sama bramka; kolaż przebudować na moduły jak `framed_cover`.
5. **API i interfejs:** wystawić okładkę ramową i pętlę AI w API (`backend/app/api/generate.py`) oraz w studiu na zecro.pl (podgląd rund, werdykty, przycisk „zastosuj poprawki”).
6. **Kompozytor kafelkowy:** naprawić znany test copyfit.
7. **Dokumentacja:** po każdym etapie dopisać część do raportu w `docs/` i zaktualizować `rulebook.md`/`defects.json`, gdy powstaje nowa reguła.

## 8. Definicja „gotowe” dla każdego zadania
- Zasada działa ogólnie (co najmniej 3 warianty genów albo 2 różne materiały).
- Bramka PASS tam, gdzie strona jest dobra, i FAIL z czytelnym komunikatem tam, gdzie nie jest.
- Nowy albo zaktualizowany test w `backend/tests/`.
- Obejrzany PNG; opis zmian w raporcie; żadnych sekretów w diffie.
