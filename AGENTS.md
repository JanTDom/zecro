# SYSTEM GENERATYWNEGO SKŁADU PRASOWEGO (AI ART DIRECTOR)

Ten projekt jest środowiskiem budowy i działania silników AI, które **kreatywnie generują layouty prasowe** (gazety, magazyny, wydania cyfrowe) zgodnie z DNA tytułu, bez kopiowania istniejących stron.

Główna instrukcja projektu: `SKILL.md` (oraz `SKILL.en.md`).

---

## 1. Reguła Fundamentalna: Kreatywność = Eksploracja × Selekcja
1. **Generator i Krytyk ZAWSZE rozdzielone**: Maszyna eksploruje przestrzeń rozwiązań (generator), a krytyk z wyuczonym gustem (selekcja) wybiera najlepsze warianty.
2. **Gramatyka tytułu jako DANE (nie template)**: Siatka modułowa, skala typograficzna, traktowanie foto, szparowanie (maski alfa / ścieżki obcinające), oblewanie konturem (`text_wrap`), katalog dozwolonych transgresji i budżet napięcia (`page_energy_budget`).
3. **Model danych: Graf Sceny (Scene Graph)**: Abstrakcyjna reprezentacja obiektowa w JSON (role, wagi `importance`, `frame`, `z`, `treatment`, `constraints`, `transgressions`, `relations`). Generator operuje na grafie sceny.
4. **Krytyk dwuwarstwowy**:
   - **Twarde więzy (Bramka Pass/Fail)**: Czytelność, brak kolizji, hierarchia (jedna dominanta), kompletność, prepress.
   - **Miękki gust (Ranking)**: Heurystyki kompozycyjne + sędzia VLM + model preferencji wyuczony z pętli gustu dyrektora artystycznego (RLHF / DPO).
5. **Pętla Gustu**: Transfer gustu człowieka do funkcji oceniającej poprzez zbieranie wyborów parami (A vs B) i delty poprawek ręcznych.
6. **Rozdział formatów**:
   - Tani szybki render do oceny i VLM (SVG / HTML/CSS print).
   - Produkcja do druku i DTP (IDML / InDesign / PDF/X / Typst) z tego samego grafu sceny.
7. **Anty-kopiowanie i Nowość**: Generowanie struktury od zera, metryka odległości od korpusu (kary za duplikaty), poszukiwanie nowości (Novelty Search / MAP-Elites / Pareto Front).

---

## 2. Checklista Realizacyjna
Przed zakończeniem każdego zadania weryfikuj:
- [ ] Czy generator i krytyk są ściśle rozdzielone?
- [ ] Czy DNA tytułu istnieje w postaci danych, a nie sztywnego szablonu?
- [ ] Czy uwzględniono katalog transgresji z budżetem napięcia?
- [ ] Czy twarde więzy działają jako bramka (pass/fail), a nie miękkie kary?
- [ ] Czy działa metryka nowości/różnorodności wykluczająca plagiat?
- [ ] Czy ocena odbywa się na tanim renderze, a produkcja trafia do IDML/PDF z tego samego grafu sceny?
