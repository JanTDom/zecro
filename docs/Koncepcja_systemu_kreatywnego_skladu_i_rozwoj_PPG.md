# Specyfikacja architektoniczna i algorytmiczna systemu generatywnego składu prasowego oraz integracji z ekosystemem PPG

*Dokumentacja techniczna: model danych, solvery geometryczne, algorytmy ewolucyjne, kształtowanie glifów Knuth–Plass, potok wizyjny, pętla uczenia preferencji i dwukierunkowa wymiana IDML/Prepress*


## 1. Definicja problemu i różnica paradygmatu wobec obecnego systemu w PPG

Zdaję sobie sprawę, że w strukturach produkcyjnych PPG funkcjonuje już zautomatyzowany system zarządzania makietami i składu kolumn prasowych. Narzędzie to realizuje model deterministycznej indeksacji zamkniętego zbioru szablonów (Closed-Set Template Matching). W architekturze tej przestrzeń dopuszczalnych układów strony jest skończonym, statycznym słownikiem predefiniowanych topologii T = {t_1, t_2, ..., t_k}, zaprojektowanych wcześniej przez zespół graficzny. Proces łamania polega tam na kwerendzie do bazy wzorców i wstrzyknięciu bieżących rekordów tekstowo-fotograficznych w sztywno zdefiniowane ramki (Slot-Filling).

Model zamkniętego zbioru wykazuje strukturalną niewydolność w dwóch przypadkach. Po pierwsze, gdy wektor cech napływającego pakietu redakcyjnego (liczba artykułów na kolumnie, rozkład długości tekstów wyrażony w wierszach znormalizowanych, proporcje aspektowe fotografii, obecność wyimków, tabel lub mapek) wykracza poza parametry z góry przewidziane w słowniku T. Wymusza to wówczas albo destrukcyjną ingerencję w materiał (agresywne cięcie tekstu, nieoptymalne kadrowanie obrazu niszczące punkt ogniskowy), albo powstawanie defektów składu: niedopełnienia szpalt (underset), przepełnienia (overset) i uwięzionego światła wewnętrznego (trapped whitespace). Po drugie, w warunkach presji wydawniczej redaktorzy konwergują do wąskiego podzbioru kilku najbardziej uniwersalnych makiet, co prowadzi do entropii wizualnej i powtarzalności kolejnych wydań.

Proponowany system zastępuje statyczne przeszukiwanie tablicy szablonów paradygmatem obliczeniowej kreatywności (Computational Creativity), zdefiniowanym jako iloczyn szerokiej eksploracji przestrzeni stanów i wielokryterialnej selekcji: Kreatywność = Eksploracja × Selekcja. Zamiast dopasowywać treść do martwego rysunku, silnik traktuje charakterystykę pisma jako zbiór reguł formalnych i więzów matematycznych, syntezując nowe, nieistniejące wcześniej w bazie rozwiązania kompozycyjne bezpośrednio pod geometrię i semantykę konkretnego materiału.

| Wymiar architektoniczny | Obecny system PPG (zamknięty zbiór) | Tryb pośredni (hybrydowy dla PPG) | Pełna synteza generatywna |
| --- | --- | --- | --- |
| Reprezentacja wiedzy o układzie | Statyczna biblioteka szablonów T = {t_1, ..., t_k} | Szablony T_PPG jako populacja startowa + gramatyka TitleDNA | Deklaratywna gramatyka TitleDNA + priory korpusowe |
| Mechanizm alokacji geometrii | Sztywne przypisanie treści do predefiniowanych slotów (Slot-Filling) | Relaksacja więzów szablonu bazowego, mutacja genomu i korekta strefowa | Solver strefowy (ZoneSolver) + algorytm ewolucyjny na genomie LayoutGenome |
| Reakcja na nietypowy pakiet treści | Przycięcie materiału, puste światło lub ręczna przebudowa w DTP | Adaptacja podziału szpalt, szparowanie, dodanie modułów wtórnych | Synteza nowej topologii dopasowanej do rzeczywistych wymiarów glifów i zdjęć |
| Ewolucja bazy wzorców | Brak (wymaga ręcznego rysowania nowych makiet przez grafików) | Automatyczna kanonizacja i zapis skorygowanych układów jako nowych wzorów t_{k+1} | Ciągła eksploracja z kontrolą odległości euklidesowej od korpusu (d >= 0.15) |


## 2. Zakres operacyjny: dwie główne gałęzie + wariant pośredni dla PPG

Architektura systemu obsługuje dwa główne strumienie produkcyjne oraz hybrydowy tryb pośredni zaprojektowany specjalnie pod migrację i rozszerzenie obecnej bazy layoutów PPG.


### 2.1. Gałąź A – synteza od zera (Greenfield Generation): nowe gazety, wkładki i dodatki

Pierwsza gałąź realizuje pełną syntezę nowych produktów wydawniczych bez konieczności uprzedniego rysowania księgi makiet w programie DTP. Dotyczy to uruchamiania nowych tytułów lokalnych i regionalnych, wkładek tematycznych, dodatków komercyjnych i samorządowych, wydań specjalnych oraz przewodników telewizyjnych (tv_listing). Na wejściu definiowany jest wyłącznie obiekt gramatyki tytułu (TitleDNA) określający fizyczny format arkusza (np. Berliner 289 × 380 mm, Tabloid, Broadsheet lub formaty niestandardowe), parametry siatki modułowej i wektor stylu. Generator automatycznie wyprowadza z tych reguł kompletne kolumny otwierające (front_page), kolumny wewnętrzne (inside), rozkładówki (spread verso/recto) oraz strony zamykające (back_page).


### 2.2. Gałąź B – refaktoryzacja i optymalizacja istniejących layoutów (Layout Refinement)

Druga gałąź operuje na kolumnach i makietach już istniejących w bieżącym obiegu redakcyjnym. Moduł dekompilacji (dissect_indesign.py) parsuje gotową lub roboczą kolumnę z formatu IDML bądź pakietu produkcyjnego, buduje jej abstrakcyjny graf sceny (SceneGraph) i przekazuje go do modułu diagnostycznego. Krytyk identyfikuje naruszenia twardych więzów oraz suboptymalności kompozycyjne: kolizje brył tekstowych, brak jednoznacznej dominanty optycznej, zachwianie balansu osiowego, wdowy i bękarty łamowe, niską efektywną rozdzielczość rastrową po wykadrowaniu czy martwe strefy w dolnych partiach kolumny. Następnie uruchamiana jest lokalna optymalizacja geometrii i mikrotypografii (zmiana podziału szpaltowego, konwersja statycznego zdjęcia na wycinek szparowany z oblewaniem konturowym, wstawienie wyimka lub ramki faktograficznej w celu skompensowania niedoboru wierszy, wyrównanie do linii bazowej), zwracająca zoptymalizowane warianty tej samej strony.


### 2.3. Opcja pośrednia (ewolucyjna rozbudowa zamkniętego zbioru PPG)

Dla organizacji posiadającej już działający system oparty na zamkniętym zbiorze szablonów najniższy próg wejścia zapewnia tryb pośredni (procedura Seed-Mutate-Canonicalize). Pozwala on rozpocząć pracę na zamkniętym zbiorze makiet PPG, poddawać je algorytmicznej korekcie pod bieżące materiały i zapisywać zatwierdzone modyfikacje jako nowe wzory:

```text
PROCEDURA: SEED-MUTATE-CANONICALIZE (Rozbudowa zamkniętego zbioru PPG)
Wejście: Zbiór szablonów bazowych T_PPG = {t_1, ..., t_k}, pakiet treści M (PageInputMaterial),
         gramatyka tytułu D (TitleDNA), model preferencji W (TasteModel).

1. INICJALIZACJA (Seed Selection):
   a) Dla każdego t_i ∈ T_PPG oblicz błąd niedopasowania pojemności slotów ΔC(t_i, M).
   b) Wybierz podzbiór K najbliższych szablonów bazowych jako populację początkową P_0.

2. ADAPTACYJNA KOREKTA I MUTACJA (Constraint-Guided Mutation):
   Dla każdego osobnika g ∈ P_0:
   a) Przelicz rzeczywistą wysokość łamów algorytmem HarfBuzz + Knuth-Plass (measure_text).
   b) Jeżeli występuje niedobór/nadmiar wierszy (|Δlines| > 3%):
      - zmodyfikuj geny podziału pionowego (skyline_split, bottom_split, photo_height_ratio),
      - przelicz rozpiętość szpaltową nagłówka i zdjęcia (hl_col_span, photo_col_span),
      - aktywuj szparowanie (treatment='cutout') i oblewanie konturowe (TextWrap mode='contour')
        lub wstrzyknij moduł wtórny (pullquote / infobox) z ustrukturyzowanych danych artykułu.

3. SELEKCJA DWUWARSTWOWA I KOREKTA REDAKCYJNA:
   a) Odrzuć warianty naruszające CriticHardGate (total_fitness = 0.0).
   b) Oceń pozostałe warianty funkcją celu i zaprezentuj top-N redaktorowi.
   c) Zarejestruj wybór człowieka oraz wektor korekty ręcznej Δx = φ(G_final) - φ(G_selected).

4. ABSTRAKCJA I ZAPIS NOWEGO WZORCA (Template Canonicalization):
   a) Oczyść zatwierdzony graf sceny G_final z instancyjnych referencji tekstowych i bitmapowych,
      pozostawiając znormalizowaną topologię ramek, role, wagi i reguły TextPlan.
   b) Wyznacz 10-wymiarowy wektor cech v_10 = extract_corpus_feature_vector(G_final)
      oraz 18-wymiarowy wektor strategii v_18 = extract_strategy_feature_vector(G_final).
   c) Oblicz minimalną odległość euklidesową d_min = min_{t ∈ T_PPG} ||v_10 - v_10(t)||_2.
   d) Jeżeli d_min >= 0.15, zapisz G_final do repozytorium wzorców jako T_PPG <- T_PPG ∪ {t_{k+1}}.
```


## 3. Architektura systemowa i formalny model danych

System realizuje architekturę potokową o ścisłej separacji komponentów, połączonych walidowanymi kontraktami JSON Schema. Niedopuszczalne jest stosowanie jednomodelowych architektur typu tekst-do-bitmapy, ponieważ uniemożliwiają one edycję post-factum, kontrolę typograficzną i przygotowanie do druku. Kanoniczny przepływ danych obejmuje cztery odseparowane warstwy obliczeniowe oraz pętlę zwrotną uczenia preferencji:

```text
[Pakiet Treści + Zasoby Foto]
        │
        ▼
[1. GRAMATYKA: TitleDNA + Katalog Transgresji + Priory Korpusu]
        │
        ▼
[2. GENERATOR: Fotoedycja -> Planer Slotu -> Solver Strefowy + Algorytm Ewolucyjny]
        │  (generuje populację N kandydatów w postaci grafów sceny SceneGraph)
        ▼
[3. KRYTYK DWUWARSTWOWY: Bramka Twarda (PASS/FAIL) -> Ranking Miękki (Heurystyki + VLM + Model Gustu)]
        │                                                                 ▲
        ├────────────── Pętla Gustu (Bradley-Terry + Delty Geometryczne) ─┘
        ▼
[4. RENDERER I PREPRESS: Szybki podgląd (SVG/HTML) | Produkcja (IDML + PDF/X + Symulator RIP)]
```


### 3.1. Kontrakt gramatyki tytułu (TitleDNA)

Charakter każdego tytułu prasowego, wkładki lub dodatku jest zdefiniowany deklaratywnie jako obiekt danych TitleDNA (walidowany przez title_dna.schema.json), nigdy jako zaszyty w kodzie szablon. Struktura ta zawiera:

- Parametry formatu i siatki modułowej (GridSpec): wymiary netto arkusza po obcięciu (trim_w_mm, trim_h_mm), wielkość spadu drukarskiego (bleed_mm, standardowo 3.0 mm), marginesy bezpieczne (margin_top_mm, margin_bottom_mm, margin_left_mm, margin_right_mm), liczbę szpalt (columns, np. 5 dla formatu okołotabloidowego/Berliner, 6–12 dla szerokich siatek modularnych), liczbę wierszy modułowych (rows), szerokość rynny międzyszpaltowej (gutter_mm, np. 4.0–4.233 mm) oraz krok linii bazowej (baseline_grid_pt, np. 12.0 pt).

- Skalę i reguły typograficzne (TypographySpec): mapowanie ról redakcyjnych na rodziny i odmiany fontów OpenType/TrueType (headline, body, sans), zdefiniowane stopnie pisma dla poszczególnych ról (headline_xl, headline_l, deck, lead, body, caption, folio), dopuszczalne zakresy trackingu oraz mnożniki interlinii.

- Wektor mieszania stylów (style_blend): trójwymiarowy wektor ciągły z przedziału [0.0, 1.0] sterujący rozkładami prawdopodobieństwa w generatorze: dense_to_photo (balans między gęstym składem tekstowym a dominacją fotografii), opinion_to_tabloid (natężenie ekspresji typograficznej i kontrastu skali) oraz classical_to_avantgarde (skłonność do asymetrii i przełamań siatki).

- Katalog transgresji i budżet energii strony (page_energy_budget): skwantyfikowany limit sumarycznego napięcia kompozycyjnego na jednej kolumnie. Każde kontrolowane odstępstwo od ortogonalnej siatki (np. rotacja nagłówka lub belki o kąt z przedziału [-3.5°, +3.5°], wyjście wyciętego obiektu poza ramkę modułu, nałożenie tekstu na fotografię z podkładką kontrastową scrim, skrajna skala elementu dominującego) posiada zdefiniowany koszt (cost), maksymalną krotność (max_per_page) oraz warunek logiczny aktywacji (precondition, np. page_energy >= 0.6 AND element.importance >= 0.7). Moduł TransgressionManager odrzuca każdy układ, dla którego suma kosztów przekracza budżet zdefiniowany w TitleDNA.


### 3.2. Graf sceny (SceneGraph) i plan slotu tekstowego (TextPlan)

Jednostką wymiany pomiędzy generatorem, krytykiem i wszystkimi rendererami jest graf sceny (SceneGraph, zdefiniowany w scene_graph.schema.json). Składa się on z obiektu PageMeta oraz uporządkowanej kolekcji węzłów Element. Każdy węzeł posiada jednoznaczną rolę semantyczną (role ∈ {logo, folio, kicker, headline, deck, byline, lead, body, photo, caption, pullquote, infobox, rule, band}), wagę redakcyjną (importance ∈ [0.0, 1.0]), referencję do pakietu treści (content_ref, story_ref, claim_refs, source_refs), wektor geometrii ramki Frame(x, y, w, h, rotation_deg, skew_y_deg) wyrażony w milimetrach, indeks głębokości w stosie warstw (z), definicję stylu (ElementStyle), parametry oblewania tekstem (TextWrap: mode ∈ {none, bbox, contour}, offset_mm), wielokąt konturu wycięcia (contour_points) oraz punkt ogniskowy (focal_point = [f_x, f_y]).

Każda ramka tekstowa w grafie sceny jest powiązana z kontraktem TextPlan (text_plan.schema.json). Obiekt ten przechowuje wyliczoną pojemność docelową: liczbę słów (target_words, min_words, max_words), liczbę znaków (target_chars), dokładną pojemność wierszową (target_lines), liczbę łamów wewnętrznych (columns), politykę obsługi nadmiaru tekstu (overflow_policy ∈ {shorten, alternate, continue, reflow, manual}), limity mikrotypograficzne (max_tracking, max_leading_adjustment_pt, min_font_size_pt, widow_lines, orphan_lines), listę tokenów nierozdzielnych (no_break_tokens) oraz flagę blokady redakcyjnej (locked).


## 4. Algorytmy eksploracji i syntezy układów (Generator)

Warstwa generatora składa się z trzech współpracujących mechanizmów: deterministycznego solvera siatki (GridSolver), solvera strefowego sterowanego rangami (ZoneSolver / PlanComposer) oraz wielokryterialnego silnika ewolucyjnego operującego na ciągło-dyskretnym genomie układu.


### 4.1. Dekompozycja strefowa i alokacja oparta na rangach (ZoneSolver)

Przed uruchomieniem alokacji geometrycznej artykuły wejściowe są sortowane malejąco według rangi redakcyjnej (rank_order: lead = 0, second = 1, third = 2, short = 3, brief/column/box = 4, teaser = 5) oraz wagi ciągłej importance. Przestrzeń robocza kolumny (po odjęciu marginesów oraz strefy winiety/paginy o wysokości 18.0 mm dla pierwszej strony lub 9.0 mm dla stron wewnętrznych) dzielona jest na strefy funkcjonalne. Funkcja span_to_w_mm(cols) przelicza rozpiętość szpaltową na wymiar milimetrowy zgodnie z zależnością:

```text
w_col_mm = (trim_w_mm - margin_left_mm - margin_right_mm - (C_total - 1) * gutter_mm) / C_total
span_to_w_mm(k) = k * w_col_mm + (k - 1) * gutter_mm
```

Dla stron wieloartykułowych kompozytor alokuje moduły bez używania sztywnych szablonów, rozwiązując problem podziału powierzchni pomiędzy temat otwierający (dominanta fotograficzno-tytułowa), artykuły drugiego planu oraz pionową lub poziomą szynę modułów skrótowych (brief/short), z zachowaniem ciągłości wątków tekstowych (text_threads).


### 4.2. Kodowanie genomowe (LayoutGenome) i eksploracja ewolucyjna

W celu uzyskania wysokiej różnorodności topologicznej każdy kandydat układu reprezentowany jest przez instancję klasy LayoutGenome (zdefiniowanej w module evolution.py). Chromosom układu zawiera jawne geny strukturalne i parametryczne:

- Gen architektury globalnej (layout_mode): zmienna kategoryczna przyjmująca wartości ze zbioru {dominant-left, dominant-right, stacked, photo-top, type-led, modular-grid}. Wagi losowania poszczególnych architektur są dynamicznie ważone przez rozkład strategii zaobserwowany w korpusie referencyjnym (strategy_distribution: balanced-grid, dense-classic, dominant-hero, visual-opener, modular-rhythm) według formuły w_i' = w_i * (0.72 + 2.1 * S_obs), przy czym tryby odrzucone we wcześniejszej ocenie wizualnej są tłumione mnożnikiem 0.35.

- Gen morfologii okładkowej (cover_morphology): określa topologię stron tytułowych i magazynowych (m.in. okładka ramowa framed_cover, hero z ukośnym wejściem tytułu, szparowana postać przecinająca pole winiety, kolaż dwuskalarny, układ asymetryczny z pionową szyną i naklejką, rozkładówka otwierająca opening_spread).

- Geny ekspozycji nagłówka głównego: kolumna startowa hl_col_start ∈ [0, C_total - 3], rozpiętość szpaltowa hl_col_span, mnożnik skali stopnia pisma hl_scale_mult ∈ {0.9, 1.0, 1.15, 1.35}, kąt rotacji hl_rotation_deg ∈ {0.0°, -3.5°, +3.5°} oraz tryb podania poster_headline_treatment ∈ {banner, overlay}.

- Geny geometrii i traktowania fotografii: lokacja photo_placement ∈ {top_hero, inline_side, bottom_anchor, cutout_overlap}, rozpiętość photo_col_span ∈ [2, min(4, C_total)], kolumna początkowa photo_col_start, współczynnik wysokości photo_height_ratio oraz sposób opracowania krawędzi treatment ∈ {crop, cutout, framed}.

- Geny podziału ciągłego dla układów typograficznych: udział szerokości zdjęcia type_led_photo_share ∈ [0.34, 0.48], położenie belki poprzecznej type_led_strap_y ∈ [0.45, 0.58], punkt podziału strefy nadwinietowej type_led_skyline_split ∈ [0.45, 0.62] oraz podział strefy dolnej type_led_bottom_split ∈ [0.38, 0.60].

Algorytm ewolucyjny inicjalizuje populację osobników, aplikuje operatory mutacji punktowej (perturbacje granic stref, zmiana lokacji zdjęcia, przełączenie szparowania, modyfikacja skali nagłówka) oraz krzyżowania jednopunktowego genomów, a następnie poddaje każdego osobnika ocenie przez dwuwarstwowego krytyka. Selekcja do puli wynikowej maksymalizuje jednocześnie jakość kompozycyjną (total_fitness) oraz odległość w 18-wymiarowej przestrzeni strategii (extract_strategy_feature_vector), gwarantując, że prezentowane redaktorowi warianty reprezentują odmienne architektury informacji, a nie drobne przesunięcia tej samej makiety.


## 5. Dwuwarstwowy krytyk, geometria obliczeniowa i metryki percepcyjne

Moduł oceny (LayoutCritic w critic.py oraz silnik percepcyjny w aesthetics.py) jest całkowicie odseparowany od generatora. Działa w architekturze dwustopniowej: najpierw jako bezwzględna bramka logiczna (Hard Gate), a następnie jako model rankingowy.


### 5.1. Warstwa pierwsza: twarda bramka walidacyjna (CriticHardGate – logika PASS/FAIL)

Naruszenie któregokolwiek z twardych więzów skutkuje natychmiastowym wyzerowaniem funkcji celu (total_fitness = 0.0) i odrzuceniem kandydata lub skierowaniem go do pętli naprawy. Twarde więzy nigdy nie są uśredniane z oceną estetyczną. Poniższa tabela zestawia procedury weryfikacyjne bramki twardej:

| Procedura bramki twardej | Sformułowanie matematyczne / algorytmiczne | Warunek odrzucenia (FAIL) |
| --- | --- | --- |
| Kolizja wielokątów zorientowanych (_overlap_extent) | Transformacja afiniczna wierzchołków (rotation_deg, skew_y_deg) + przecięcie wielokątów Shapely Polygon.intersection | Pole przecięcia > 0 bez autoryzacji transgresji overlap |
| Legalność kolażu foto (_photo_inset_allowed) | Stosunek pola A_inter / A_base oraz bufor wokół focal_point [f_x, f_y] | Pokrycie > 20% powierzchni zdjęcia bazowego lub wejście w bufor ±6.0 mm wokół punktu ogniskowego |
| Detekcja pustych kwadrantów (_largest_empty_editorial_region) | Dyskretyzacja pola zadruku na macierz 40 × 60 i poszukiwanie maksymalnego pustego prostokąta | Przekroczenie progu niezaprojektowanej pustej powierzchni konstrukcyjnej |
| Geometria maski szparowania (cutout_geometry_issue) | Wzór Gaussa (Shoelace Formula): A = 0.5 * |Σ(x_i * y_{i+1} - x_{i+1} * y_i)| w oknie ramki | Pokrycie < 6%, rozpiętość < 18% × 30% (fragment) lub pokrycie > 88% (pozorny prostokąt) |
| Efektywna rozdzielczość druku (effective_print_dpi) | DPI_eff = min(W_px * Δx_crop / (W_mm / 25.4), H_px * Δy_crop / (H_mm / 25.4)) | DPI_eff < 180–200 PPI (gazeta) lub < 300 PPI (magazyn) |
| Domknięcie wierszowe i mikrotypografia | Pomiar uharfbuzz + Knuth-Plass (overset_lines, has_stranded_headline_word) | overset_lines > 0 lub samotny krótki wyraz w ostatnim wierszu tytułu |


### 5.2. Warstwa druga: heurystyki kompozycyjne i indeks estetyczny (PARC + Sophi + Poynter)

Kandydaci, którzy przeszli bramkę twardą, podlegają ocenie ciągłej w module evaluate_heuristics oraz evaluate_page_aesthetics. Silnik ten łączy trzy uznane modele percepcji układu prasowego:

Po pierwsze, model równowagi optycznej Xerox PARC (Harrington et al.). Każdemu elementowi i przypisywana jest masa optyczna M_i = A_i * ρ(role_i) * κ_i, gdzie A_i = w_i * h_i jest powierzchnią ramki w mm², ρ(role_i) współczynnikiem gęstości percepcyjnej (photo: 1.0, logo: 0.85, band/plate: 0.80, kicker: 0.70, headline: 0.65, deck/jump_line: 0.40, lead: 0.35, caption: 0.30, byline: 0.25, body: 0.22, rule: 0.20, folio: 0.15), natomiast κ_i stanowi mnożnik korekcyjny (1.15 dla wycinków szparowanych cutout, 1.05 dla zdjęć na spad full-bleed oraz min(2.5, max(0.8, sqrt(font_size_pt / 14.0))) dla nagłówków ekspozycyjnych). Ze środka ciężkości optycznego kolumny (x_opt = Σ(M_i * c_{x,i}) / Σ M_i, y_opt = Σ(M_i * c_{y,i}) / Σ M_i) wyliczany jest wskaźnik równowagi bocznej względem osi symetrii oraz wskaźnik równowagi pionowej (equilibrium_score), przyjmujący maksimum w psychologicznym centrum optycznym strony położonym na wysokości 44–46% od górnej krawędzi cięcia.

Po drugie, algorytm detekcji uwięzionego światła (Trapped Whitespace podług metodologii Sophi.io / The Globe and Mail). Algorytm odróżnia celowy oddech kompozycyjny przy krawędziach zewnętrznych od przypadkowych kieszeni pustego papieru zamkniętych pomiędzy sąsiadującymi ramkami wewnątrz kolumny (trapped_whitespace_cm2). Równolegle oceniany jest globalny udział bieli (whitespace_ratio = 1 - occupied_area / total_page_area), osiągający optimum w przedziale [0.12, 0.35].

Po trzecie, reguły okulograficzne Poynter Institute Eyetrack (Garcia & Stark). System oblicza: jednoznaczność punktu wejścia wzroku (entry_point_score), zakotwiczenie dolnej krawędzi kolumny zapobiegające wrażeniu „wiszenia” składu (bottom_anchor_score), zgodność wektora spojrzenia postaci ze strukturą szpalt (gaze_alignment_score – wektor wzroku lub ruchu musi być skierowany ku środkowi kolumny i powiązanemu tekstowi, nigdy poza linię cięcia) oraz grawitację ścieżki czytania (reading_gravity_score). Ta ostatnia penalizuje skoki wsteczne w górę osi Y (Δy = y_{t+1} - y_t < -10.0 mm) pomiędzy kolejnymi węzłami wektora reading_order.

Syntetyczny wynik miękki (composite_soft_score) wyliczany jest jako kombinacja liniowa siedmiu składowych znormalizowanych do przedziału [0, 1]:

```text
S_soft = 0.18 * balance_score
       + 0.18 * reading_gravity_score
       + 0.15 * rhythm_and_scale_score
       + 0.12 * breathing_space_score
       + 0.12 * tension_adherence_score
       + 0.10 * corpus_alignment_score
       + 0.15 * aesthetic_index
```

Ostateczna wartość funkcji dopasowania (total_fitness) łączy wynik miękki S_soft, odległość nowości względem korpusu (novelty_vs_corpus, karzącą przybliżenia poniżej d < 0.15 w 10-wymiarowej przestrzeni cech), ocenę wyuczonego modelu preferencji dyrektora artystycznego (pref_score) oraz kalibrację archetypową:

```text
total_fitness = hard_gate.passed * (w_heur * S_soft + w_cal * S_cal + w_nov * Novelty + w_pref * S_pref)
```


## 6. Silnik kształtowania glifów HarfBuzz, algorytm Knuth–Plass i kontrakt Fact-Guard

W przeciwieństwie do uproszczonych systemów szacujących objętość tekstu na podstawie średniej liczby znaków, nasz silnik pomiaru i składu (shaper.py oraz copyfit.py) wykonuje pełne kształtowanie glifów (glyph shaping) i optymalne łamanie akapitów na identycznych plikach fontów, które trafiają później do wynikowego pliku produkcyjnego PDF/IDML.


### 6.1. Pomiar metryk OpenType (HarfBuzz) i polskie dzielenie wyrazów (Pyphen)

Każdy łańcuch tekstowy jest przetwarzany przez bibliotekę uharfbuzz. Z pliku fontu odczytywana jest wartość jednostek na firet (upem), a po ułożeniu glifów w buforze z aktywną tablicą kerningu (kern=True, liga=False) sumowane są wektory przesunięcia poziomego x_advance z korektą o zadany tracking:

```text
advance(text) = (Σ glyph_positions[i].x_advance) / upem
width_pt(text, size_pt, tracking_em) = advance(text) * size_pt + tracking_em * size_pt * len(text)
```

Przed przekazaniem tekstu do łamania wykonywane jest wiązanie polskiej mikrotypografii (zastąpienie spacji zwykłych po jednoliterowych spójnikach i przyimkach a, i, o, u, w, z spacjami niełamliwymi U+00A0, konwersja cudzysłowów na polskie „…” oraz dywizów międzywyrazowych na półpauzy –). Następnie słownik Pyphen (pl_PL, przy minimalnym pozostawieniu 2 znaków po lewej i 3 znaków po prawej stronie podziału: left=2, right=3) wyznacza dopuszczalne punkty podziału wyrazów. Silnik egzekwuje przy tym twarde reguły zecerskie (reguła U5): całkowity zakaz dzielenia wyrazów krótszych niż 6 liter, skrótowców pisanych wersalikami, nazw własnych rozpoczynających się wielką literą oraz tekstów ekspozycyjnych o stopniu pisma >= 14.0 pt (HYPHENATE_BELOW_PT = 14.0).


### 6.2. Algorytm łamania akapitu metodą programowania dynamicznego Knuth–Plass

Każdy akapit jest transformowany na sekwencję trójkowych obiektów modelu TeX/Knuth–Plass: sztywnych pudełek sylabowych (box), elastycznego kleju międzywyrazowego (glue) oraz punktów karnych podziału (penalty). W celu odwzorowania rygorów justowania gazetowego zdefiniowano dwupoziomową elastyczność wiersza: spacja międzywyrazowa posiada rozciągliwość WORD_STRETCH = 0.50 i kurczliwość WORD_SHRINK = 0.20 swojej szerokości naturalnej, natomiast same pudełka wyrazowe dopuszczają mikro-rozciąganie międzyliterowe LETTER_STRETCH = 0.025 (+2.5%) oraz mikro-ściskanie LETTER_SHRINK = 0.015 (-1.5%).

Dla każdego kandydata na punkt przełamania b i aktywnego węzła początkowego a wyliczany jest współczynnik dopasowania wiersza r (adjustment ratio) względem docelowej szerokości szpalty L_w, miara niedopasowania (badness) oraz skumulowany koszt przełamania (demerits d):

```text
r = (L_w - W_{a,b}) / Y_{a,b}   dla W_{a,b} < L_w  (rozciąganie)
r = (L_w - W_{a,b}) / Z_{a,b}   dla W_{a,b} > L_w  (ściskanie)

badness = 100 * |r|^3
d = (1 + badness + max(0, p_b))^2 - (p_b^2 jeśli -INF < p_b < 0) + Δ_hyphen
```

Gdzie p_b = 50 oznacza karę za podział wyrazu dywizem. Algorytm programowania dynamicznego wyszukuje ścieżkę najkrótszą w acyklicznym grafie przełamań (minimalizując sumaryczne demerits dla całego akapitu), stosując dodatkowe więzy strukturalne: zakaz dzielenia wyrazu w pierwszym wierszu akapitu, karę Δ_hyphen = +3000 za dwa kolejne wiersze zakończone dywizem oraz bezwzględną blokadę przekroczenia dwóch dywizów z rzędu (MAX_HYPHEN_RUN = 2). Przeszukiwanie odbywa się w progresywnej kaskadzie progów tolerancji tol ∈ {1.5, 3.0, 6.0, 20.0}, co gwarantuje znalezienie globalnie najczystszego składu bez korytarzy białych plam.


### 6.3. Strażnik faktów (Fact-Guard) i dwukierunkowy copyfitting

W przypadku wykrycia niedopasowania objętości tekstu do pojemności ramki (overset lub underset przekraczający ±3% budżetu wierszowego) uruchamiana jest procedura dwukierunkowa. Jeżeli tekst lub wybrane akapity posiadają flagę locked=True (np. autoryzowane wypowiedzi, cytaty, klauzule prawne), tekst jest traktowany jako niezmiennik, a solver przelicza wysokość ramki lub przenosi nadmiar do powiązanej ramki kontynuacji (jump_if_needed). Jeżeli redaktor dopuszcza adaptację redakcyjną (shorten_to_fit / expand / generowanie wariantów nagłówka micro, short, medium, long, exact_fit), moduł source_guard.py przed wywołaniem modelu językowego ekstrahuje z tekstu źródłowego zbiór twardych twierdzeń i encji (daty, wartości liczbowe, waluty, statystyki, nazwiska, nazwy instytucji). Wygenerowany wariant podlega deterministycznej walidacji względem zamrożonego słownika faktów oraz ponownemu pomiarowi w HarfBuzz/Knuth–Plass; jakakolwiek zmiana liczby, zaokrąglenie kwoty lub halucynacja spoza źródła powoduje automatyczne odrzucenie wariantu.


## 7. Potok wizyjny, segmentacja masek alfa i wektoryzacja konturów

Przetwarzanie fotografii wyprzedza etap układania geometrii strony (fotoedycja przed geometrią – moduł photo_editor.py oraz image_ops.py). Dla każdego zasobu obrazowego wyznaczany jest ustrukturyzowany wektor metadanych wizyjnych: punkt ogniskowy focal_point = [f_x, f_y], klasyfikacja semantyczna obiektu głównego (pozwalająca na automatyczną blokadę szparowania dla kadrów krajobrazowych, architektury lub scen zbiorowych bez wyraźnej sylwetki), wektor orientacji twarzy i ruchu, ocena dynamiki reporterskiej oraz współrzędne obszarów o niskiej wariancji tonalnej (safe zones), na które można bezpiecznie wprowadzić tekst nagłówka.


### 7.1. Ekstrakcja pierścieni krawędziowych i redukcja Ramera–Douglasa–Peuckera

Dla zdjęć zakwalifikowanych do szparowania (treatment='cutout') uruchamiany jest deterministyczny potok wektoryzacji maski alfa (_portable_alpha_rings w image_ops.py). Kanał alfa jest progowany binarnie (threshold), a następnie dla każdego piksela pierwszoplanowego ekstrahowane są wyłącznie jego odsłonięte krawędzie skierowane zgodnie z ruchem wskazówek zegara. Algorytm łączy skierowane krawędzie w zamknięte pętle wielokątne, obliczając dla każdej pętli pole ze znakiem (signed_area). Pętle o polu dodatnim i udziale powierzchni powyżej min_component_ratio tworzą zewnętrzne obrysy sylwetki, natomiast pętle o polu ujemnym zawierające się wewnątrz obrysu (weryfikowane testem przecięcia półprostej – Ray-Casting Algorithm) rejestrowane są jako otwory wewnętrzne (holes), co pozwala poprawnie obsłużyć np. przestrzeń między ramieniem a tułowiem.

Surowy łańcuch pikseli krawędziowych (liczący tysiące wierzchołków) jest następnie upraszczany do gładkiej ścieżki wektorowej za pomocą rekurencyjnego algorytmu Ramera–Douglasa–Peuckera (simplify_douglas_peucker). Dla każdego odcinka łączącego wierzchołek początkowy P_1 = (x_1, y_1) i końcowy P_2 = (x_2, y_2) wyznaczany jest punkt pośredni P_i maksymalizujący odległość prostopadłą d_⊥ wyliczaną z iloczynu wektorowego w przestrzeni 2D:

```text
d_⊥(P_i, P_1 P_2) = |(x_2 - x_1)(y_1 - y_i) - (y_2 - y_1)(x_1 - x_i)| / hypot(x_2 - x_1, y_2 - y_1)
```

Jeżeli max_i(d_⊥) > tolerance (gdzie tolerancja jest przeskalowana do fizycznych milimetrów docelowej ramki: tol = max(0.5, tolerance_mm / max(s_x, s_y))), łańcuch jest dzielony w punkcie P_i i rekurencyjnie upraszczany; w przeciwnym razie zastępowany jest pojedynczym wektorem [P_1, P_2]. Wygenerowany wielokąt stanowi jednocześnie ścieżkę obcinającą (Clipping Path) dla obrazu oraz bazę do wyznaczenia odsuniętego o offset_mm wielokąta oblewania tekstem (TextWrap contour).


### 7.2. Kategoryczna bramka etyczna (Ethical Framing Guard)

W potoku fotoedycji zaszyta jest nienegocjowalna blokada kategoryczna dla materiałów oznaczonych semantycznie jako tragedie, wypadki śmiertelne lub publikacje żałobne. W przypadku wykrycia tej kategorii system programowo blokuje operatory szparowania (allow_cutout = False), wyłącza okrągłe wstawki portretowe (circular insets), ukośne belki (diagonal-break) oraz ozdobne stemple graficzne, wymuszając czysty, ortogonalny kadr dokumentalny o proporcjach 16:9 lub 3:2.


## 8. Aktywne uczenie preferencji (Taste Loop) – model Bradleya–Terry’ego

Transfer gustu dyrektora artystycznego lub zespołu redakcyjnego do funkcji oceniającej odbywa się bez konieczności ręcznego programowania reguł estetycznych. Moduł TasteLoopTrainer (w pliku taste_loop.py) implementuje uczenie preferencyjne na podstawie dwóch klas sygnałów zbieranych w trakcie normalnej pracy nad wydaniem:

- Sygnały wyboru i porównań parami (pairwise_comparison / selection): gdy człowiek wybiera wygrywającego kandydata G_win ponad alternatywę G_lose, system ekstrahuje ich 10-wymiarowe wektory cech geometrycznych x_win = φ(G_win) oraz x_lose = φ(G_lose) (obejmujące znormalizowane współrzędne i wymiary nagłówka głównego [hl_x, hl_y, hl_w, hl_h], geometrię głównej fotografii [photo_x, photo_y, photo_w, photo_h], flagę szparowania is_cutout oraz zużyty budżet energii used_energy) i konstruuje wektor różnicowy Δx = x_win - x_lose z etykietą docelową y = 1.

- Sygnały delty ręcznej korekty na płótnie (manual_edit_delta): gdy redaktor lub grafik modyfikuje wybrany wariant przed wysłaniem do druku (przesuwa ramkę, zmienia rozpiętość szpaltową, powiększa zdjęcie), stan przed koreką G_before jest traktowany jako wariant przegrywający, a stan po korekcie G_after jako wygrywający, co daje kierunkowy gradient poprawki Δx = φ(G_after) - φ(G_before).

Na zgromadzonym zbiorze par trenujemy wektor wag preferencji w ∈ R^10 w logistycznym modelu Bradleya–Terry’ego. Prawdopodobieństwo, że układ o wektorze cech x_win jest preferowany względem x_lose, wyraża się funkcją sigmoidalną iloczynu skalarnego:

```text
P(G_win > G_lose | w) = σ(w^T * Δx) = 1 / (1 + exp(-clip(w^T * Δx, -15.0, +15.0)))
```

Optymalizacja wag w przebiega metodą spadku wzdłuż gradientu (Gradient Descent, 60 epok, współczynnik uczenia η = 0.1) minimalizującą funkcję straty entropii krzyżowej z regularyzacją Tichonowa L_2 (λ = 0.01), zapobiegającą przeuczeniu przy małej liczbie próbek:

```text
grad_i = (σ(w^T * Δx) - 1.0) * Δx_i + λ * w_i
w_i <- w_i - η * grad_i
```

Gdy liczba zebranych sygnałów osiągnie co najmniej 4 pary, najnowsze 25% obserwacji (heldout_count = max(1, N // 4)) jest automatycznie wydzielane poza zbiór treningowy jako zbiór walidacyjny held-out. System na bieżąco oblicza i raportuje zestaw sześciu metryk operacyjnych:

| Metryka ewaluacyjna | Definicja formalna | Interpretacja produkcyjna |
| --- | --- | --- |
| Validity Rate | N_pass / N_generated | Odsetek kandydatów przechodzących wszystkie reguły CriticHardGate |
| Strategy Diversity | Średnia odległość parami ||v_18(G_i) - v_18(G_j)||_2 w puli top-N | Gwarancja, że proponowane warianty reprezentują różne architektury strony |
| Corpus Novelty | min(1.0, min_{c ∈ Corpus} ||v_10(G) - v_10(c)||_2 / 0.5) | Ochrona przed duplikacją istniejących makiet (próg kary d < 0.15) |
| Held-Out Win-Rate | (1 / |H|) * Σ I(w^T * Δx_h >= 0) | Zdolność wyuczonego modelu gustu do przewidywania wyborów redaktora na nowych danych |
| Time-to-Approve | Średni czas (s) oraz liczba iteracji do zatwierdzenia kolumny | Bezpośredni wskaźnik redukcji ręcznej pracy zespołu DTP/redakcji |
| Prepress Integrity | Odsetek eksportów IDML/PDF przechodzących audyt ISO 12647-3 bez błędów | Pewność naświetlenia płyt CTP bez przekroczeń TAC, braku spadów czy błędów overprintu |


## 9. Integracja z obecnym systemem PPG, kompilacja IDML i symulacja RIP/Prepress

Połączenie nowego silnika z obecną infrastrukturą wydawniczą w PPG nie wymaga zastępowania dotychczasowego systemu. Integracja opiera się na natywnych standardach wymiany danych DTP oraz rozdziale formatu oceny od formatu produkcyjnego.


### 9.1. Dwukierunkowa wymiana przez archiwa IDML i dekompilację InDesign

Na etapie eksploracji i oceny wariantów system renderuje graf sceny do lekkich struktur wektorowych SVG oraz HTML/CSS Paged Media, co pozwala na błyskawiczną ocenę dziesiątek kandydatów. Po zatwierdzeniu wybranego wariantu ten sam obiekt SceneGraph jest przekazywany do kompilatora produkcyjnego IDMLRenderer (idml_renderer.py), który buduje pełny pakiet Adobe InDesign Markup Language (.idml) zgodny ze specyfikacją pakietową OCF/ZIP:

- Rozwiązywanie wątków tekstowych (_text_threads): kompilator waliduje spójność łańcuchów ramek dla artykułów wielołamowych i wieloramkowych, generuje pliki Stories/u_story_<id>.xml i wiąże poszczególne ramki TextFrame na kolumnie za pomocą wskaźników PreviousTextFrame oraz NextTextFrame, eliminując ryzyko osieroconych lub cyklicznych referencji.

- Transformacja układu współrzędnych i geometrii ścieżek: wszystkie wymiary milimetrowe grafu sceny są przeliczane na punkty PostScript (mnożnik MM_TO_PT = 2.83464567). Dla elementów nieprostokątnych oraz szparowanych fotografii generowane są natywne węzły Polygon i PathGeometry z wierzchołkami PathPointType oraz aktywnymi właściwościami TextWrapPreference (oblewanie po konturze obiektu z zadanym offsetem).

- Separacja barwna CMYK i style akapitowe: kolory zdefiniowane w palecie tytułu są konwertowane do przestrzeni CMYK i zapisywane w Resources/Graphic.xml jako próbki barwne (Swatches), przy czym dla tekstów czarnych wymuszana jest próbka czystej czerni procesowej Color/Black (C=0, M=0, Y=0, K=100). Style typograficzne są mapowane na definicje ParagraphStyle w Resources/Styles.xml.

W kierunku odwrotnym moduł dissect_indesign.py realizuje inżynierię wsteczną istniejących plików z obecnego systemu PPG: odczytuje z paczek IDML oraz katalogów roboczych InDesigna ustawienia siatki bazowej (GridPreference / BaselineGridIncrement z Resources/Preferences.xml), próbki CMYK/Spot, definicje stylów akapitowych oraz geometrię ramek z plików Spreads/Spread_*.xml. Pozwala to na automatyczne zaimportowanie dowolnej obecnej makiety z zamkniętego zbioru PPG, poddanie jej optymalizacji w naszym silniku i odesłanie z powrotem jako gotowego pliku IDML.


### 9.2. Symulacja naświetlania CTP i kontrola Prepress (norma ISO 12647-3)

Przed przekazaniem pliku PDF/X lub IDML do naświetlarni system wykonuje deterministyczny audyt prepress oraz symulację zachowania farby w druku zwojowym coldset (moduł rip_simulator.py oraz preflight_check.py):

- Kontrola całkowitego pokrycia farbą (Total Area Coverage – TAC / TIC): dla każdego obszaru barwnego i cieni fotografii wyliczana jest suma składowych procesowych TAC = C + M + Y + K. Dla papieru gazetowego (newsprint 45 g/m²) egzekwowany jest twardy limit TAC <= 240% (zgodnie z normą ISO 12647-3). Przekroczenie progu 240% generuje ostrzeżenie średniego ryzyka, a powyżej 260% błąd krytyczny (ryzyko przebicia farby na drugą stronę wstęgi, odciągania i zerwania papieru w maszynie rotacyjnej) wraz z procedurą redukcji składowych chromatycznych metodą GCR (Grey Component Replacement) pod profil ICC WAN-IFRA Newspaper.

- Modelowanie przyrostu punktu rastrowego (Dot Gain) i detekcja zalania cieni (Shadow Crush): symulator odwzorowuje fizyczne rozlewanie się kropli farby na chłonnym podłożu gazetowym, gdzie przyrost punktu w tonach średnich wynosi 26–30%. Zastosowany model nieliniowy T_print = T_nominal + G * (1 - (T_nominal / 100)^1.5) (przy współczynniku G = 28.0 dla papieru gazetowego wobec G = 15.0 dla papieru powlekanego) wykazuje, że nominalny raster 50% daje na papierze gazetowym zaczernienie rzędu 78.3%. Jeżeli partie cieni po uwzględnieniu krzywej przyrostu przekraczają próg 78% (shadow_crush_warning), system wymusza korektę krzywej tonalnej o 5–8% w tonach średnich.

- Weryfikacja nadruku czerni (Overprint 100% K) i zalewkowania (Trapping): wszystkie teksty ciągłe, podpisy, paginy i linie szpaltowe złożone w 100% K muszą posiadać aktywny atrybut overprint=True (zakaz wycinania białego tła knockout w płytach C, M, Y, który przy naturalnym braku pasowania płyt w rotacji gazetowej daje nieczytelne białe obwódki wokół liter). Na stykach pól barwnych kontrolowane jest zalewkowanie (trapping >= 0.15 mm), a dla rozkładówek egzekwowane są spady zewnętrzne 3.0 mm przy zerowym spadzie wewnętrznym w grzbiecie (0.0 mm inner spine bleed).


## 10. Mapa rozwoju systemu i rozszerzenia algorytmiczne

Dalszy rozwój architektury został podzielony na cztery powiązane moduły inżynieryjne, które rozszerzają możliwości silnika od pojedynczej kolumny do pełnej automatyzacji całego wydania i wielokanałowej dystrybucji.


### 10.1. Etap 1: wdrożenie pętli hybrydowej w PPG i fabryki dodatków tematycznych

Pierwszy etap obejmuje bezpośrednie podpięcie dekompilatora IDML pod zamknięty zbiór obecnych szablonów PPG. Istniejące makiety zostaną zindeksowane do postaci wektorów cech w FEATURE_INDEX.json oraz obiektów bazowych SceneGraph. Pozwoli to natychmiast uruchomić opisaną w punkcie 2.3 opcję pośrednią (korekta obecnych layoutów pod bieżący materiał i automatyczny zapis zwalidowanych mutacji jako nowych wzorców w katalogu PPG) oraz równoległą linię do generowania od zera nowych wkładek, dodatków komercyjnych i wydań specjalnych.


### 10.2. Etap 2: optymalizacja kombinatoryczna całego wydania (Flatplan & Ad-Anchoring Engine)

Rozszerzenie solvera z poziomu pojedynczej kolumny i rozkładówki na poziom architektury całego numeru (IssuePlan / FlatPlan w module flatplan_engine.py). Problem alokacji materiałów i reklam w całym wydaniu jest formułowany jako zadanie programowania całkowitoliczbowego z więzami (CP-SAT / Knapsack with Editorial Priorities):

- Więzy składki drukarskiej (Signature Compliance): całkowita liczba stron wydania lub wkładki musi spełniać kongruencję N_pages ≡ 0 (mod 4) przy N_pages >= 4.

- Bilansowanie gęstości reklamowej i algorytmy kotwiczenia reklam (Ad Anchoring): dla każdej strony kontrolowany jest współczynnik pokrycia reklamą ad_density = A_ads / A_printable <= 0.40. Moduły reklamowe (w jednostkach SCM – Standard Column Module) są kotwiczone algorytmicznie od dolnych narożników zewnętrznych w układzie schodkowym (Staircase) lub studniowym (Editorial Well), a pozostała wielokątna przestrzeń redakcyjna jest automatycznie przeliczana przez ZoneSolver bez ryzyka sąsiedztwa dwóch konkurujących reklam lub odcięcia nagłówka od tekstu.

- Automatyczne zarządzanie kontynuacjami wielostronicowymi: gdy artykuł główny z pierwszej strony wymaga podziału i przeniesienia na kolumnę wewnętrzną, planer automatycznie rezerwuje sparowany slot docelowy, dzieli strumień tekstowy w punkcie minimalizującym błąd Knuth–Plass i wstrzykuje obustronnie powiązane odsyłacze kontynuacji (jump lines).


### 10.3. Etap 3: kartografia redakcyjna i synteza wektorowych infografik z danych (Data-to-Chart)

Rozbudowa modułu editorial_cartography.py oraz infographics.py o automatyczną transformację danych liczbowe-geograficznych wyekstrahowanych z artykułu (przez kontrakt Fact-Guard) na gotowe do druku elementy wektorowe SVG/PDF osadzane bezpośrednio w grafie sceny. Obejmuje to generowanie prasowych mapek lokalizacyjnych (Press Locator Maps), wykresów słupkowych i sondażowych oraz tabel modułowych. Każdy taki obiekt jest generowany dokładnie w wymiarze k * w_col_mm + (k - 1) * gutter_mm (wielokrotność szpalty danego tytułu), z wysokością skwantowaną do wielokrotności linii bazowej baseline_grid_pt oraz w bezpiecznej przestrzeni barwnej CMYK (z wariantem monochromatycznym 100% K + rastry szarości dla kolumn czarno-białych).


### 10.4. Etap 4: klasteryzacja strategii korpusowych i wielokanałowe bliźniaki cyfrowe (Digital Twins)

Ostatni kierunek rozwoju dotyczy uczenia nienadzorowanego na archiwach wydawniczych oraz automatycznej rekonfiguracji zatwierdzonego grafu sceny na formaty nieprasowe. W miejsce regułowego przypisywania sygnatur strategii wprowadzona zostanie klasteryzacja wielowymiarowych wektorów topologicznych z historycznych wydań (wyznaczanie centroidów, macierzy kowariancji i anty-wzorców dla każdej strefy wydania). Równolegle, ten sam zatwierdzony i zweryfikowany faktograficznie graf sceny SceneGraph będzie służył jako źródło prawdy do bezstratnego rzutowania na siatki cyfrowe (responsywne wydania webowe, karty social media, formatki mobilne), przy zachowaniu pełnej spójności typograficznej i kolorystycznej z wydaniem drukowanym.
