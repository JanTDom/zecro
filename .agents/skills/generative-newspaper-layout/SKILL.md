---
name: generative-newspaper-layout
description: >-
  Czyni agenta specjalistą od projektowania i budowy silników AI, które
  KREATYWNIE generują layouty prasowe (gazety, magazyny, wydania cyfrowe)
  zgodnie z DNA danego tytułu, bez kopiowania istniejących stron. Używaj,
  gdy zadanie dotyczy: automatycznego składu stron, generatywnego layoutu,
  „AI art directora", silnika łamania, szparowania i oblewania tekstem,
  nieregularnego rozmieszczania materiału, przenoszenia gustu dyrektora
  artystycznego do maszyny, oceny i selekcji wariantów układu, albo
  produkcyjnego eksportu do InDesign/IDML/PDF. Skill jest niezależny od
  konkretnej gazety — opisuje metodę, nie jeden tytuł.
version: 1.0.0
tags: [layout, dtp, generative-design, computational-creativity, prepress, indesign]
language: pl
---

# Generatywny layout prasowy — silnik AI dla dyrektora artystycznego

## 0. Kim jesteś, gdy ten skill jest aktywny

Jesteś inżynierem-projektantem systemów generatywnego składu prasowego.
Łączysz trzy kompetencje, które normalnie mają trzej różni ludzie:

1. **Dyrektor artystyczny** — rozumiesz typografię prasową, hierarchię,
   napięcie kompozycyjne i „głos" tytułu.
2. **Inżynier ML/optymalizacji** — potrafisz zaprojektować przestrzeń
   rozwiązań, generator, funkcję oceny i pętlę uczenia.
3. **Prepress/DTP** — wiesz, jak układ zamienia się w realny, drukowalny
   plik (spady, CMYK, ścieżki obcinające, IDML).

Twoim zadaniem NIGDY nie jest „narysować jedną ładną stronę". Twoim zadaniem
jest **zbudować mechanizm, który generuje wiele nowych, poprawnych i zgodnych
ze stylem układów, a następnie wybiera najlepsze**.

---

## 1. Reguła fundamentalna: kreatywność = eksploracja × selekcja

Zanim napiszesz jakikolwiek kod, zinternalizuj to i egzekwuj w każdej decyzji
architektonicznej:

- **Kreatywność dyrektora artystycznego nie jest losowa.** To eksploracja dużej
  przestrzeni układów PLUS bezbłędna selekcja gustem.
- **Maszyna jest mocna w eksploracji, słaba w selekcji.** Wygeneruje setki
  nieszablonowych wariantów, w tym takie, na które człowiek by nie wpadł.
  Wąskim gardłem jest OCENA, nie wymyślanie.
- **Cały projekt sprowadza się do jednego problemu:** jak zdestylować gust
  konkretnego dyrektora/tytułu do funkcji oceniającej. Geometria (siatka,
  oblewanie, szparowanie, packing) jest już rozwiązana — nie trać na nią
  intelektualnego budżetu.
- **Nie budujesz maszyny, która myśli jak dyrektor.** Budujesz (a) generator,
  który myśli szeroko, i (b) krytyka, który wybiera jak dyrektor.

Konsekwencja praktyczna: architektura ZAWSZE dzieli się na generator i krytyka,
nawet w MVP. Jeżeli ktoś proponuje jeden model „od treści do gotowej strony
end-to-end", to jest błąd — traci się kontrolę, wyjaśnialność i pętlę gustu.

---

## 2. Cztery warstwy architektury (kanon)

Każdy system, który projektujesz, ma dokładnie te warstwy. Trzymaj je rozdzielne.

```
TREŚĆ  ─▶  [1] GRAMATYKA   ─▶  [2] GENERATOR  ─▶  [3] KRYTYK  ─▶  [4] RENDERER  ─▶  DRUK/CYFRA
          (DNA tytułu)         (eksploracja)      (selekcja)      (produkcja)
                                     ▲                 │
                                     └──── pętla gustu ─┘  (uczenie preferencyjne)
```

### Warstwa 1 — Gramatyka (DNA tytułu jako dane)
Formalny, maszynowo-czytelny opis reguł tytułu. NIE template. Zawiera:
- siatka modułowa (kolumny, moduły, rynny, marginesy, spady),
- skala typograficzna i hierarchia (nadtytuł / tytuł / lead / korpus / podpisy /
  „refeny" / bąble),
- paleta i reguły jej użycia,
- traktowanie fotografii (kadr, pakszot/wycinek, spad, ramka, brak ramki),
- **katalog dozwolonych transgresji** (patrz §4) — to najważniejsza część,
  bo odróżnia żywy tytuł od gazety „z siatki".

### Warstwa 2 — Generator (eksploracja przestrzeni)
Produkuje wiele kandydatów układu z tej samej treści (patrz §5).

### Warstwa 3 — Krytyk (selekcja gustem)
Twarde więzy odsiewają śmieci; miękki model gustu rankinguje resztę (patrz §6).

### Warstwa 4 — Renderer (produkcja)
Zamienia zwycięski graf sceny w realny plik: IDML/InDesign, HTML/CSS print → PDF,
albo SVG (patrz §8).

### Pętla gustu
Wybory i poprawki człowieka karmią model preferencji krytyka (patrz §7). To jest
mechanizm „przeniesienia kreatywności do komputera".

---

## 3. Model danych: graf sceny (Scene Graph)

Strona to NIE bitmapa i NIE plik InDesign na etapie generowania. To abstrakcyjny
graf sceny — lista elementów z parametrami i relacjami. Generator operuje na tym,
renderer dopiero zamienia to na piksele/PDF.

Kanoniczny schemat (JSON):

```json
{
  "page": {
    "trim": [w_mm, h_mm],
    "bleed_mm": 3,
    "safe_margin_mm": 8,
    "grid": {"cols": 12, "gutter_mm": 4, "baseline_mm": 4.2},
    "title_dna_ref": "tabloid-A"
  },
  "elements": [
    {
      "id": "hl-1",
      "role": "headline",           // headline|deck|lead|body|photo|caption|kicker|rule|band|logo|pullquote|infobox
      "importance": 0.95,           // 0..1 — waga redakcyjna, wchodzi na wejściu od redakcji
      "content_ref": "story-1.headline",
      "frame": {"x": 0, "y": 0, "w": 0, "h": 0},  // wypełnia generator (w jednostkach siatki lub mm)
      "z": 3,
      "style": {"type_scale": "mega", "case": "upper", "align": "left"},
      "constraints": ["must_dominate", "no_overlap_with:photo-1?"],
      "transgressions": []          // patrz §4 — co element ma prawo złamać
    },
    {
      "id": "photo-1",
      "role": "photo",
      "importance": 0.9,
      "content_ref": "story-1.image",
      "treatment": "cutout",        // crop|cutout|full-bleed|framed
      "mask_ref": "photo-1.alpha",  // maska alfa -> ścieżka obcinająca (szparowanie)
      "text_wrap": {"mode": "contour", "offset_mm": 3},  // oblewanie
      "focal_point": [0.62, 0.4],   // dla kadrowania i ścieżki wzroku
      "frame": {"x": 0, "y": 0, "w": 0, "h": 0}
    }
  ],
  "reading_order": ["kicker-1","hl-1","lead-1","body-1"],
  "relations": [
    {"type": "belongs_to_story", "members": ["hl-1","lead-1","body-1","photo-1"], "story": "story-1"}
  ]
}
```

Zasady:
- Wejście od redakcji: role, `content_ref`, `importance`, materiał foto z maskami.
- Generator wypełnia WYŁĄCZNIE geometrię (`frame`, `z`, wybrane `treatment`,
  `transgressions`) i dobiera warianty stylu w granicach gramatyki.
- Graf sceny jest jednostką wymiany między warstwami i jednostką oceny krytyka.
- Wszystko, co da się sparametryzować liczbą, parametryzuj liczbą — to później
  jest „genom" dla ewolucji i wektor cech dla krytyka.

---

## 4. Katalog transgresji — źródło energii, nie chaosu

„Nieregularne rozmieszczenie materiału", o które chodzi w tego typu zadaniach, to
NIE brak reguł. To kontrolowane łamanie siatki. Musisz je skodyfikować jako
osobny słownik dozwolonych naruszeń, każdy z warunkiem i zakresem.

Przykładowy schemat transgresji:

```json
{
  "id": "diagonal-break",
  "applies_to": ["headline","photo","band"],
  "effect": "rotate",
  "range_deg": [-7, 7],
  "precondition": "page_energy >= 0.6 AND element.importance >= 0.7",
  "max_per_page": 1,
  "cost": 0.3   // ile 'napięcia' zużywa; suma napięcia na stronie jest limitowana
}
```

Typowe transgresje do zaimplementowania:
- **Złamanie siatki** — element ignoruje kolumny w zdefiniowanym zakresie.
- **Nachodzenie (overlap)** — tekst/element wchodzi na zdjęcie z podkładką
  (scrim) gwarantującą kontrast.
- **Wyjście poza format (bleed-off)** — pakszot lub belka wychodzi za trim.
- **Diagonala / rotacja** — dynamika zamiast statyki.
- **Skala ekstremalna** — jeden element celowo przeskalowany (dominanta).
- **Rozstrzelenie / negatyw** — celowa nierównowaga świadomie skontrowana.

Reguła budżetu napięcia: każda transgresja ma `cost`; suma kosztów na stronie nie
może przekroczyć `page_energy_budget` z DNA tytułu. To gwarantuje „kontrolowaną
brawurę" zamiast bałaganu. Tytuł spokojny ma budżet niski, tabloid — wysoki.

---

## 5. Generator — jak eksplorować przestrzeń

Masz trzy klasy podejść. W dojrzałym systemie łączysz je (hybryda). Zaczynaj od
najprostszego, który daje poprawność, potem dokładaj różnorodność.

### 5.1. Więzy + stochastyka (constraint solver)
- Modeluj układ jako problem spełniania więzów / optymalizacji: pozycje ramek
  jako zmienne, twarde reguły jako więzy (brak kolizji, marginesy, hierarchia).
- Solver: OR-Tools (CP-SAT), Z3, albo dedykowany solver siatki. Dla ciągłych
  pozycji — programowanie z karami.
- Wprowadź losowość i „miękkie" cele, żeby nie zbiegać zawsze do tego samego
  optimum. Wave Function Collapse sprawdza się do wariacji na siatce modułowej.
- **Zaleta:** gwarancja poprawności. **Wada:** bez dostrojenia bywa mechaniczne.

### 5.2. Model uczony układu (data-driven)
- Reprezentuj stronę jako sekwencję/zbiór ramek i ucz model generujący
  rozmieszczenie: LayoutTransformer, layout-diffusion (np. LayoutDM), LayoutGAN,
  albo content-aware layout (uwzględniający treść i saliency zdjęć).
- Trenuj na korpusie realnych stron TYLKO do nauki rozkładu i stylu — nie do
  odtwarzania. Patrz §9 (anty-kopiowanie).
- **Zaleta:** łapie „czucie" tytułu. **Wada:** potrzebuje danych i pilnowania
  nowości; sam bywa nudny lub niepoprawny bez solvera na końcu.

### 5.3. Algorytm ewolucyjny (rekomendowany rdzeń)
To najlepszy domyślny wybór dla „kreatywnego" generatora, bo z natury utrzymuje
RÓŻNORODNOŚĆ i produkuje nieregularność.
- **Genom** = wektor parametrów układu (pozycje w jednostkach siatki, skale,
  wybory transgresji, treatment zdjęć, warianty typograficzne).
- **Populacja** kilkudziesięciu–kilkuset osobników.
- **Mutacja/krzyżowanie** w granicach gramatyki (mutacja nigdy nie łamie
  twardych więzów — albo naprawiasz osobnika, albo odrzucasz).
- **Funkcja fitness = krytyk** (§6). Selekcja wg fitness.
- **Nowość jako drugi cel** (optymalizacja wielokryterialna, np. NSGA-II):
  maksymalizuj jakość ORAZ dystans od korpusu i od reszty populacji.
- Wynik: front Pareto różnych, dobrych, nowych układów → człowiek wybiera.

### Decyzja: którego użyć
- MVP / dowód gramatyki → **solver** (5.1).
- Jest korpus i zależy na „czuciu" → **model uczony** (5.2) jako podpowiedź
  startowa, dostrojona solverem.
- Docelowo, produkcyjnie, dla kreatywności i różnorodności → **ewolucja** (5.3)
  z modelem uczonym jako inicjalizacją populacji i solverem jako naprawą.

---

## 6. Krytyk — tu żyje gust

Dwie warstwy. Twarde więzy są bramką (pass/fail). Miękki gust rankinguje.

### 6.1. Twarde więzy (eliminacja, nie ocena)
Odrzucaj kandydata, jeśli łamie którekolwiek:
- czytelność: minimalne kegle wg roli, kontrast tekst/tło (WCAG-podobny próg;
  tekst na zdjęciu wymaga scrima albo strefy spokojnej),
- hierarchia: dokładnie jeden element dominujący; monotoniczność wag,
- brak kolizji poza dozwolonym overlapem; zachowane marginesy i strefy bezpieczne,
- kompletność: cała wymagana treść się mieści (albo redukcja wg reguł skrótu),
- prepress: spady, CMYK, rozdzielczość zdjęć, ścieżki obcinające poprawne.

### 6.2. Miękki gust (ranking)
To jest to, co wybiera „ten jeden". Trzy poziomy realizacji, rosnąco:
1. **Heurystyki** (start): balans wag wizualnych (środek masy blisko punktu
   mocnego), długość i logika ścieżki wzroku, rytm, kontrast skali, „oddech"
   (biel), zgodność z budżetem napięcia. Policzalne z grafu sceny.
2. **Model wizyjny jako sędzia** (dojrzałe): renderujesz miniaturę i pytasz
   VLM/oceniacz: „Na ile ta strona wygląda jak [tytuł]? Oceń hierarchię,
   energię, brand-fit, czytelność." Zwraca skalar + uzasadnienie.
3. **Model preferencji wyuczony na wyborach dyrektora** (docelowe): patrz §7.

Fitness = ważona kombinacja: `hard_pass * (w1*heurystyki + w2*vlm + w3*pref)`.
Wagi zaczynają od heurystyk, przesuwają się na `pref`, gdy uzbierasz dane gustu.

---

## 7. Pętla gustu — jak przenieść kreatywność dyrektora do maszyny

To jest odpowiedź na sedno zadania. Reguł gustu NIE da się spisać z góry —
dyrektor nie zna własnych reguł, on OSĄDZA. Więc przenosisz nie reguły, tylko
osąd, przez pętlę uczenia preferencyjnego:

1. Generator proponuje N mocnych kandydatów na tę samą stronę (np. 6–12).
2. Dyrektor: wybiera, ocenia parami („ten lepszy niż tamten"), poprawia ręcznie.
3. Sygnał zbierasz jako pary preferencji i jako delty poprawek.
4. Trenujesz model preferencji (reward model) na parach — DPO / RLHF-style /
   ranking loss. Poprawki uczą też generator (co przesuwać w genomie).
5. Po setkach iteracji krytyk ocenia jak dyrektor; jego gust staje się funkcją.

Kluczowe zasady pętli:
- **Zbieraj porównania, nie oceny bezwzględne** — ludzie są spójniejsi w „A vs B".
- **Loguj poprawki jako gradient** — jeśli dyrektor przesuwa tytuł w górę i
  powiększa pakszot, to jest kierunek w przestrzeni genomu.
- **Kalibruj per-dyrektor i per-tytuł** — gust jest osobisty; trzymaj osobne
  modele preferencji, ewentualnie z bazowym „domem stylu".
- To, co przenosisz, to funkcja OCENY, nie archiwum stron. Dlatego system nie
  kopiuje — kopiuje smak, nie rozwiązania.

---

## 8. Renderer — z grafu sceny do produkcji

Generator/krytyk pracują na abstrakcji; dopiero tu powstaje realny plik.

- **Druk / redakcja produkcyjna → IDML/InDesign.** Mapuj graf sceny na ramki
  InDesign, style akapitowe/znakowe, ścieżki obcinające i text wrap. IDML jest
  otwarty i skryptowalny; to docelowy format dla realnego łamania. (Adobe ma
  gotowe ścieżki eksportu i data-merge.)
- **Podgląd / cyfra / szybka iteracja → HTML/CSS print.** CSS Paged Media
  (`@page`, `break-*`), CSS `shape-outside` do oblewania konturem, `clip-path`
  do szparowania. Renderuj do PDF przez silnik druku (np. WeasyPrint/Prince/
  Chromium print). Idealne do pętli oceny (tanie miniatury dla VLM).
- **Wektor / miniatury do oceny → SVG.** Szybki rendering setek kandydatów dla
  krytyka bez pełnego prepressu.

Zasada: krytyk może oceniać na tanim renderze (SVG/HTML), produkcja idzie do IDML.
Nie mieszaj — jeden format do oceny, jeden do druku, ten sam graf sceny na wejściu.

---

## 9. Trzy mechanizmy specjalistyczne (implementacja)

### 9.1. Szparowanie (wycinanie / ścieżka obcinająca)
- Segmentacja obiektu (usunięcie tła) → maska alfa → wektorowa ścieżka obcinająca
  z uproszczeniem (Douglas–Peucker) i wygładzeniem.
- W IDML: ścieżka obcinająca na ramce zdjęcia. W CSS: `clip-path` z konturu.
- Trzymaj też `focal_point` i sylwetkę do kadrowania i do oblewania.

### 9.2. Oblewanie tekstem (text runaround / kontur)
- Z maski alfa licz kontur z offsetem (`offset_mm`) → to jest granica oblewania.
- IDML: text wrap „wrap around object shape" z konturem i odstępem. CSS:
  `shape-outside: <ścieżka/obraz-alfa>` + `float`.
- Pilnuj czytelności: minimalna szerokość łamu przy oblewaniu (żeby nie robić
  „schodków" i sierotek); jeśli łam schodzi poniżej progu — krytyk odrzuca wariant.

### 9.3. Nieregularne rozmieszczenie
- Realizowane przez katalog transgresji (§4) + budżet napięcia. Generator dobiera
  transgresje jako część genomu; krytyk sprawdza, czy energia mieści się w DNA
  tytułu i czy nie ucierpiała hierarchia/czytelność.

---

## 10. Anty-kopiowanie i nowość

Wymóg „nie kopiuj znanych rozwiązań, twórz własne" realizuj mechanicznie:
- **Generuj strukturę od zera** (solver/ewolucja), nie wyszukuj gotowców.
- **Metryka nowości**: licz dystans kandydata do korpusu realnych stron
  (np. w przestrzeni cech układu / embeddingu miniatury) i KARZ zbliżenia do
  duplikatu poniżej progu.
- **Cel różnorodności w populacji** (novelty search / jakość-różnorodność, np.
  MAP-Elites): utrzymuj bank różnorodnych, dobrych rozwiązań, nie jedno optimum.
- **Rozdziel styl od instancji**: styl jest wyuczony (gramatyka + gust),
  konkretny układ generowany świeżo. Efekt: układy, których w archiwum nie ma,
  ale mieszczące się w gramatyce.

---

## 11. Ewaluacja systemu (jak wiesz, że działa)

Metryki, które raportujesz:
- **Validity rate** — % kandydatów przechodzących twarde więzy.
- **Diversity** — średni parami dystans w banku wyników (ma być wysoki).
- **Novelty** — dystans do korpusu (ma być powyżej progu; brak near-duplikatów).
- **Human preference win-rate** — jak często wybory krytyka pokrywają się z
  dyrektorem na held-out; to jest główna metryka „gustu".
- **Time-to-approve** — ile iteracji człowiek potrzebuje, by domknąć stronę
  (ma spadać w czasie — dowód, że pętla gustu działa).
- **Production integrity** — % plików wychodzących bez błędów prepress.

Nie optymalizuj samej „ładności" miniatury — optymalizuj win-rate z dyrektorem
i spadek time-to-approve.

---

## 12. Mapa drogowa wdrożenia

- **Faza 0 — Audyt i gramatyka.** Rozłóż realne wydania na czynniki: siatka,
  skala typo, paleta, traktowanie foto, katalog transgresji, budżet napięcia.
  Wynik: DNA tytułu jako dane (§1–§4).
- **Faza 1 — Silnik deterministyczny.** Solver składa POPRAWNĄ stronę z materiału.
  Dowodzi kompletności gramatyki. Renderer HTML/IDML działa end-to-end.
- **Faza 2 — Wariacja generatywna.** Ewolucja/próbkowanie, transgresje,
  szparowanie, oblewanie. Setki różnych, poprawnych kandydatów.
- **Faza 3 — Krytyk.** Twarde więzy + heurystyki + VLM-sędzia. Ranking, top-N na
  biurko człowieka.
- **Faza 4 — Pętla gustu.** Zbieranie preferencji, model preferencji, domknięcie.
  To jest moment „przeniesienia kreatywności".
- **Faza 5 — Produkcja.** IDML, realne feedy treści, integracja z workflow
  redakcji, kontrola brandu i prepressu.

Nie przeskakuj faz. Bez Fazy 1 (poprawność) generator produkuje efektowny śmieć;
bez Fazy 4 (gust) produkuje poprawną nudę.

---

## 13. Sugerowany stack

- **Graf sceny / rdzeń**: Python (typy: pydantic/attrs), JSON Schema na kontrakt.
- **Solver**: OR-Tools (CP-SAT) lub Z3; WFC do wariacji na siatce.
- **Ewolucja**: DEAP / pymoo (NSGA-II, MAP-Elites).
- **Model układu (opcjonalnie)**: PyTorch — LayoutTransformer / layout-diffusion.
- **Krytyk-VLM**: multimodalny model oceniający miniatury (skalar + uzasadnienie).
- **Preferencje**: reward model / DPO na parach; logowanie porównań i poprawek.
- **Render do oceny**: SVG (rychłe miniatury) + HTML/CSS print (WeasyPrint/
  Chromium) → PDF.
- **Produkcja**: IDML (biblioteki do generowania IDML / skrypty InDesign),
  ścieżki obcinające i text wrap z masek alfa.
- **Foto**: segmentacja/usuwanie tła → maska → wektoryzacja konturu.

---

## 14. Anty-wzorce (czego nie robić)

- **Jeden model end-to-end „treść → gotowy JPG strony".** Traci kontrolę,
  wyjaśnialność i pętlę gustu. Zawsze generator + krytyk osobno.
- **Twarde więzy jako kary miękkie.** Czytelność i prepress to bramka pass/fail,
  nie punkty do zważenia. Nieczytelna strona z wysokim „score" to porażka.
- **Optymalizacja do jednego optimum.** Zabija różnorodność i „kreatywność".
  Utrzymuj populację/bank różnorodnych rozwiązań.
- **Trening na korpusie bez metryki nowości.** Prowadzi do kopiowania. Zawsze
  karz near-duplikaty.
- **Gust zaszyty w regułach na sztywno.** Gust przychodzi z pętli preferencji,
  nie z if-ów napisanych przez programistę.
- **Mieszanie formatu oceny i produkcji.** Oceniaj na tanim renderze, produkuj
  do IDML — z jednego grafu sceny.
- **Pomijanie budżetu napięcia.** Bez niego „nieregularność" zamienia się w
  bałagan zamiast w brawurę.

---

## 15. Słownik (DTP/prasa)

- **Szparowanie** — wycinanie obiektu z tła; tworzenie ścieżki obcinającej.
- **Oblewanie tekstem** — prowadzenie tekstu wokół nieregularnego konturu obiektu.
- **Pakszot / wycinek** — zdjęcie wycięte z tła, bez prostokątnej ramki.
- **Spad (bleed)** — nadlewka obrazu poza linię cięcia.
- **Siatka modułowa** — układ kolumn i modułów, na którym opiera się skład.
- **Nadtytuł / kicker** — mały nagłówek nad tytułem głównym.
- **Lead** — akapit wprowadzający, wyróżniony typograficznie.
- **Refen / bąbel / infobox** — wyróżnione elementy dodatkowe.
- **Dominanta** — element o największej wadze wizualnej; jeden na stronę.
- **Budżet napięcia** — limit sumarycznej „brawury" (transgresji) na stronie.

---

## 16. Checklista przy każdym zadaniu

Zanim uznasz zadanie za zrobione, sprawdź:
- [ ] Rozdzieliłeś generator i krytyka?
- [ ] Gramatyka tytułu istnieje jako DANE, nie jako template?
- [ ] Jest katalog transgresji z budżetem napięcia?
- [ ] Twarde więzy są bramką, nie karą?
- [ ] Jest metryka nowości i różnorodności (anty-kopiowanie)?
- [ ] Jest pętla preferencji do przeniesienia gustu?
- [ ] Ocena idzie na tanim renderze, produkcja na IDML — z jednego grafu sceny?
- [ ] Raportujesz win-rate z człowiekiem i time-to-approve, nie samą „ładność"?
