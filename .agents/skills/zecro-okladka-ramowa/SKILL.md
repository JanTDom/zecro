---
name: zecro-okladka-ramowa
description: Silnik okładki ramowej Zecro (framed_cover, wzorzec Wukadka NR21) i jego bramka jakości. Używaj przy każdej zmianie kompozycji okładki, kadrowania zdjęć, wycięć (szparowania), tytułu w oknie, modułów dolnych oraz reguł U15–U19 i defektów D26–D30.
---

# Okładka ramowa Zecro

## Gdzie co jest (`backend/app/engine/`)
- `framed_cover.py` — kompozytor `compose_framed_cover(material, kit_name="wukadka", genes=...)`. Rama, okno tytułu, bohater (`_place_hero_breakout` z pamięcią podręczną → `_solve_hero_breakout`), skyboxy, moduł dolny, naklejka.
- `cover_modules.py` — szkielet stron (`wukadka_skeleton`), wiersze tytułu w oknie (`lead_slots`), pomiar łamań dla dyrektora (`lead_breakings`, pole `dziura_okna_cm2`).
- `layered_cover.py` — prymitywy: `photo_fill`, `breakout`, `fade`, `fill_block`, `copy` (ramka tekstu bez apli ma wysokość złożonego tekstu), `snap_near_edges`.
- `layered_rules.py` — bramka `layered_violations`: `figures_on_paper` (D26), `unowned_white` (D27), `empty_in_boxes` i `window_holes` (D28), `near_miss_edges` (D29), `tapered_gaps` i łata gruntu `hero_ground_patch` (D30), twarze D07 (twarz rozcięta między kadry tego samego zdjęcia liczona w całości).
- `knowledge/rulebook.md` (U1–U19, normy N1–N7), `knowledge/defects.json` (D01–D30), `title_kits/` (zestaw Wukadki).

## Zasady, których nie wolno złamać
1. **U15.** Każdy fragment żywej strony należy do modułu. Moduł bez treści znika, a sąsiad przejmuje jego miejsce.
2. **U16.** Moduł jest wypełniony do krawędzi. Zdjęcie w ramce ma własne tło (cover‑crop wokół twarzy), tytuł wypełnia pudełko, twarz ma co najmniej 12–14 mm.
3. **U17.** Wycięcie jest częściowe: zdjęcie w prostokącie wypełnia kolumnę, wycina się tylko część wychodzącą poza moduł (głowa nad winietą). Pełne wycięcie tylko na gruncie. Postać na gołym papierze i kończyna ucięta brzegiem oryginału („kikut”) to błąd.
4. **U18.** Moduły stykają się albo dzieli je stały rowek. Prawie‑styk 0,3–2,5 mm to błąd. Zdjęcie sięga pod pochyloną belkę; czego nie sięgnie, zamyka grunt ramy (nigdy papier), a łata > 4 cm² to D30.
5. **U19.** Nie przenosi się wyrazów z wielkiej litery ani w pierwszym wierszu akapitu; najwyżej dwa przeniesienia z rzędu.
6. Solver bohatera ma twarde limity: twarz widoczna, winieta zasłonięta ≤ 12 % (NR21: ~9 %), druk ≥ 180 dpi. Nie obniżaj progów, żeby strona przeszła.
7. Wiersz tytułu kończy się przed belką liczoną u podstawy wiersza, pod górną listwą okna i przed pierścieniem naklejki.

## Jak pracować
- Zmieniaj zasadę ogólną (prymityw, solver, reguła bramki), nie jedną okładkę. Każdy błąd widoczny na zrzucie przekuj w regułę bramki albo w ograniczenie kompozytora, a potem dopisz test.
- Podgląd: `cd backend && ZECRO_DATA_DIR=<katalog z zapisem> ../.venv/bin/python -m scripts.wukadka_demo --framed --tag <tag> --genes '<json>'`. Wynik w `output/wukadka-demo/okladka-<tag>.{pdf,png,scene.json}` i linia `GATE PASS/FAIL`.
- Zawsze oglądaj PNG po zmianie (zbliżenia newralgicznych miejsc: styk zdjęcia z belką, górna krawędź kolumny, okno tytułu, moduł dolny).
- Warianty do sprawdzenia przy każdej zmianie: `{}` (narożnik), `{"bottom":"strip"}`, `{"corner_photos":"cutout"}`, wymuszone `lead_lines`.
- Testy: z katalogu głównego `../.venv/bin/python -m pytest -q backend/tests` (≈ 3 min). Znane: `test_short_source_becomes_an_expansion_request_not_a_hole` nie przechodzi niezależnie od tych prac; dwa testy wolnego kolażu są xfail.
