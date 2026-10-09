# Prompt startowy dla agenta Antigravity — budowa aplikacji „Generative Newspaper Layout Studio"

> Wklej całość jako pierwsze zadanie dla agenta. Jeśli w repo jest plik
> `SKILL.md` / `SKILL.en.md` (skill „generative-newspaper-layout"), traktuj go
> jako nadrzędną wiedzę dziedzinową i trzymaj się jego kanonu (generator +
> krytyk, gramatyka jako dane, katalog transgresji, pętla gustu, anty-kopiowanie).

---

## ROLA I CEL

Jesteś zespołem inżynierskim budującym produkcyjną **aplikację webową** o nazwie
roboczej **„Layout Studio"**. Aplikacja pozwala redakcji:

1. **Uczyć się** wizualnego DNA konkretnej gazety na podstawie jej realnych stron.
2. **Kreatywnie generować** nowe strony w tym layoucie — nowe, oryginalne układy,
   NIE kopie istniejących stron — ze szparowaniem, oblewaniem tekstem i
   kontrolowanym, nieregularnym rozmieszczeniem materiału.
3. **Oceniać i wybierać** warianty, a przez wybory użytkownika **przenosić gust
   dyrektora artystycznego** do modelu (pętla preferencji).

**Zasada organizująca całą aplikację: jedna gazeta = jeden PROJEKT.** Każdy
projekt ma własny korpus stron, własne wyuczone DNA (gramatykę), własny model
gustu i własną historię generacji. Projekty są od siebie w pełni odizolowane.

Buduj iteracyjnie, fazami z sekcji „MILESTONES". Po każdej fazie ma działać
uruchamialny, testowalny fragment. Nie pisz całości naraz.

---

## UŻYTKOWNICY I GŁÓWNY PRZEPŁYW

Persona: dyrektor artystyczny / grafik / redaktor wydania.

Ścieżka użytkownika w aplikacji:
1. Tworzy projekt „Gazeta X".
2. Wgrywa realne strony gazety (PDF/obraz/IDML) → aplikacja je analizuje i
   buduje **DNA projektu** (siatka, typografia, paleta, traktowanie zdjęć,
   katalog transgresji, budżet napięcia).
3. Wrzuca materiał na nową stronę (teksty + zdjęcia + wagi redakcyjne).
4. Klika „Generuj" → dostaje **N wariantów** layoutu (miniatury).
5. Ocenia je (wybór najlepszego / porównania parami / ręczne poprawki).
6. Eksportuje zwycięski układ (PDF / IDML / HTML).
7. Z czasem, dzięki jego ocenom, aplikacja generuje coraz bliżej jego gustu.

---

## ARCHITEKTURA (kanon — trzymaj rozdzielne warstwy)

```
[Frontend Web]  →  [API]  →  [Silnik: Gramatyka → Generator → Krytyk → Renderer]
                                                     ↑              │
                                                     └── Pętla gustu ┘ (preferencje)
```

- **Gramatyka (DNA projektu)** — maszynowo-czytelny opis reguł gazety jako DANE
  (JSON), NIE template.
- **Generator** — produkuje wiele kandydatów (eksploracja). Rdzeń: algorytm
  ewolucyjny + solver więzów jako naprawa; opcjonalnie model uczony jako seed.
- **Krytyk** — twarde więzy (bramka pass/fail: czytelność, hierarchia, brak
  kolizji, prepress) + miękki gust (heurystyki → model wizyjny → model
  preferencji użytkownika).
- **Renderer** — z abstrakcyjnego **grafu sceny** do realnego pliku: HTML/CSS
  print → PDF do podglądu i oceny; IDML do produkcji.
- **Pętla gustu** — wybory i poprawki użytkownika trenują model preferencji
  danego projektu.

Kluczowa reprezentacja: **graf sceny** (scene graph) — strona jako lista
elementów z parametrami (role, ramki, z-index, treatment zdjęć, transgresje).
Generator i krytyk pracują na grafie; renderer dopiero zamienia go na piksele.
NIE buduj jednego modelu „treść → gotowy obraz strony" end-to-end.

---

## MODEL DANYCH (minimum)

- **Project** — id, nazwa gazety, format (trim, spady), status, timestamps.
- **TitleDNA** (1:1 z projektem, wersjonowane) — siatka, skala typograficzna,
  paleta, reguły foto, katalog transgresji, budżet napięcia. To wynik uczenia.
- **CorpusPage** — wgrana realna strona (plik + metadane + wyekstrahowane cechy
  układu; służy do uczenia DNA i do metryki nowości).
- **SceneGraph** — abstrakcyjny opis wygenerowanej strony (JSON).
- **GenerationRun** — jedno uruchomienie generatora: wejściowy materiał +
  parametry + lista kandydatów (grafy sceny + miniatury + score).
- **PreferenceSignal** — sygnał od użytkownika: wybór, porównanie parami (A>B),
  delta ręcznej poprawki. Karmi model gustu.
- **TasteModel** (per projekt, wersjonowany) — funkcja oceniająca wyuczona z
  PreferenceSignal.
- **ExportArtifact** — wyeksportowany plik (PDF/IDML/HTML) powiązany z kandydatem.

Wszystko, co da się sparametryzować liczbą, parametryzuj — to genom dla ewolucji
i wektor cech dla krytyka.

---

## FUNKCJE APLIKACJI (zakres)

**Projekty**
- Lista projektów (gazet), tworzenie/edycja/usuwanie, pełna izolacja danych.
- Widok projektu = dashboard: DNA, korpus, generacje, model gustu, eksporty.

**Uczenie DNA (ingest)**
- Wgrywanie stron: PDF, obraz (PNG/JPG), IDML. Parsowanie/segmentacja na
  elementy (tytuł, lead, korpus, zdjęcie, podpis, belka).
- Ekstrakcja cech: siatka, skala kegli, paleta, proporcje zdjęć, częstość i
  zakres transgresji, „budżet napięcia".
- Zapis wyniku jako **TitleDNA** (edytowalne przez człowieka — DNA jako dane,
  nie czarna skrzynka).
- Widok „DNA gazety" z możliwością ręcznej korekty reguł.

**Generacja**
- Formularz materiału: teksty wg ról, zdjęcia (z automatycznym szparowaniem —
  usunięcie tła → maska → ścieżka obcinająca), wagi redakcyjne `importance`.
- Silnik generuje N kandydatów w granicach DNA, z transgresjami do wysokości
  budżetu napięcia, z oblewaniem tekstem wokół konturu pakszotu.
- Galeria kandydatów (miniatury + score krytyka + krótkie uzasadnienie).

**Ocena i pętla gustu**
- Wybór najlepszego, porównania parami, ręczne poprawki (drag/resize/scale na
  grafie sceny) — wszystko logowane jako PreferenceSignal.
- Aktualizacja/retrening modelu gustu projektu; widoczna metryka „jak blisko
  Twojego gustu" (human preference win-rate) i „time-to-approve".

**Anty-kopiowanie**
- Metryka nowości: dystans kandydata od korpusu; blokada near-duplikatów.
- Cel różnorodności w obrębie jednej generacji (bank różnorodnych rozwiązań).

**Eksport**
- Podgląd i eksport PDF (HTML/CSS print). Eksport IDML do produkcji w InDesign.
- Ścieżki obcinające i text wrap zachowane w eksporcie.

---

## SUGEROWANY STACK (dopasuj do konwencji repo, jeśli już istnieją)

- **Frontend:** Next.js (React) + TypeScript, Tailwind. Edytor grafu sceny na
  canvas/SVG (np. Konva/Fabric) z click-to-select, drag/resize, undo/redo.
- **Backend/API:** Python (FastAPI) dla silnika layoutu i ML; lub Node dla API +
  mikroserwis Python dla silnika. Kontrakt: JSON Schema na graf sceny i DNA.
- **Silnik:**
  - solver więzów: OR-Tools (CP-SAT) lub Z3,
  - ewolucja / jakość-różnorodność: pymoo lub DEAP (NSGA-II, MAP-Elites),
  - render do oceny: SVG (miniatury) + HTML/CSS print → PDF (WeasyPrint/Chromium),
  - foto: segmentacja/usuwanie tła → maska alfa → wektoryzacja konturu,
  - krytyk-VLM: pluggable endpoint modelu multimodalnego oceniającego miniatury,
  - preferencje: reward model / ranking loss (DPO-style) na parach.
- **Dane:** PostgreSQL (metadane, DNA, sygnały) + storage obiektowy na pliki i
  miniatury (S3-kompatybilne / lokalny wolumen w dev).
- **Kolejka:** zadania generacji i uczenia jako joby w tle (np. RQ/Celery/BullMQ)
  z podglądem postępu w UI.

Wszystkie „modele AI" (VLM-krytyk, model preferencji, ewentualny model układu)
podpięte przez **adaptery z jednym interfejsem**, żeby dało się je wymieniać.

---

## KONTRAKTY (zdefiniuj wcześnie)

- `scene_graph.schema.json` — kanoniczny graf sceny (page, elements[roles,
  frame, z, treatment, mask_ref, text_wrap, transgressions], reading_order,
  relations).
- `title_dna.schema.json` — DNA gazety (grid, type_scale, palette, photo_rules,
  transgression_catalog, page_energy_budget).
- `POST /projects` · `POST /projects/{id}/corpus` (ingest) ·
  `POST /projects/{id}/dna:learn` · `POST /projects/{id}/generate` ·
  `POST /projects/{id}/preferences` · `POST /candidates/{id}/export`.

Graf sceny jest jednostką wymiany między wszystkimi warstwami i jednostką oceny
krytyka. Ten sam graf zasila render do oceny (SVG/HTML) i produkcję (IDML).

---

## MILESTONES (buduj w tej kolejności, nie przeskakuj)

- **M0 — Szkielet.** Monorepo, frontend + API + baza, model danych, schematy
  JSON, CRUD projektów. Health-check end-to-end.
- **M1 — Ingest + DNA (deterministycznie).** Wgrywanie stron, ekstrakcja cech,
  zapis edytowalnego TitleDNA, widok DNA gazety.
- **M2 — Renderer + solver.** Z materiału + DNA solver składa JEDNĄ poprawną
  stronę; render HTML/CSS → PDF i miniatura SVG. Dowód, że gramatyka działa.
- **M3 — Generator kreatywny.** Ewolucja: N różnych, poprawnych kandydatów,
  transgresje w granicach budżetu, szparowanie i oblewanie. Galeria wariantów.
- **M4 — Krytyk.** Twarde więzy (bramka) + heurystyki + hook VLM. Ranking i
  uzasadnienia. Metryka nowości i różnorodności (anty-kopiowanie).
- **M5 — Pętla gustu.** Zbieranie preferencji (wybór, pary, poprawki), model
  gustu per projekt, retrening, metryki win-rate i time-to-approve.
- **M6 — Eksport produkcyjny.** IDML do InDesign ze ścieżkami obcinającymi i
  text wrap; finalny PDF. Utrwalanie eksportów.
- **M7 — Twardnienie.** Joby w tle z postępem, autoryzacja, testy, seed
  demonstracyjny (jedna przykładowa gazeta z kilkoma stronami).

Każdy milestone: działający kod + krótkie README jak uruchomić + minimalne testy.

---

## KRYTERIA AKCEPTACJI

- Tworzę projekt „Gazeta X", wgrywam kilka stron, dostaję edytowalne DNA.
- Wrzucam materiał, klikam „Generuj", dostaję ≥8 **różnych** kandydatów, każdy
  przechodzący twarde więzy (czytelność, hierarchia, brak kolizji, prepress).
- Żaden kandydat nie jest near-duplikatem strony z korpusu (metryka nowości).
- Widzę szparowanie i oblewanie tekstem wokół pakszotu na co najmniej części
  wariantów.
- Wybieram/oceniam warianty; po serii ocen kolejne generacje są bliżej moich
  wyborów (rosnący win-rate, malejące time-to-approve).
- Eksportuję zwycięzcę do PDF i do IDML otwierającego się w InDesign.
- Drugi projekt „Gazeta Y" ma inne DNA i inny model gustu — dane w pełni
  odseparowane.

---

## GUARDRAILS (czego NIE robić)

- NIE jeden model end-to-end „treść → obraz strony". Zawsze generator + krytyk
  osobno.
- NIE traktuj czytelności/prepressu jako kar miękkich — to bramka pass/fail.
- NIE optymalizuj do jednego optimum — utrzymuj różnorodność (bank rozwiązań).
- NIE trenuj bez metryki nowości — to prowadzi do kopiowania stron. Karz
  near-duplikaty.
- NIE zaszywaj gustu w if-ach — gust przychodzi z pętli preferencji.
- NIE mieszaj formatu oceny i produkcji — oceniaj na tanim renderze, produkuj do
  IDML, z jednego grafu sceny.
- NIE globalizuj DNA ani gustu — wszystko jest per projekt (per gazeta).

---

## NA START

1. Zaproponuj strukturę monorepo i stack (zgodnie z powyższym), poczekaj na moje
   „ok" albo od razu scaffolduj M0, jeśli repo jest puste.
2. Zdefiniuj `scene_graph.schema.json` i `title_dna.schema.json` jako pierwsze.
3. Zbuduj M0–M2, pokaż działający render jednej strony z przykładowego DNA.
4. Dopiero potem ruszaj z generatorem kreatywnym (M3+).

Trzymaj się kanonu ze skilla „generative-newspaper-layout". Pytaj tylko, gdy
decyzja jest nieodwracalna i niejednoznaczna; w innych wypadkach wybierz
rozsądny domyślny wariant i idź dalej, notując założenie.
