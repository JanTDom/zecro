# Raport prac Claude — 15 października 2026

> Część II (praca nocna, bez wdrożenia) znajduje się na końcu dokumentu.

Kontynuacja według `Zecro_przekazanie_dla_Claude.docx`. Progi oceny nie zostały obniżone. Generator i krytyk pozostają rozdzielone.

## Stan testów

- Backend: `150 passed, 1 skipped, 4 deselected` (wcześniej 136). Nowe testy zachowania są w `backend/tests/test_tabloid_morphologies.py`.
- Frontend: `npm run build` przechodzi (tsc i vite).
- Wdrożenie produkcyjne: **nie zostało wykonane z tej sesji**, bo nie miała danych logowania Vercel CLI. Polecenia znajdują się na końcu raportu.

## A. Fotoedycja przed geometrią

- `backend/app/ai/photo_editor.py` (prompt `photo_ranking` v3) ocenia teraz: emocję, ruch, reporterskość, pozowanie, liczbę i wielkość twarzy, kierunek spojrzenia i ruchu, ramkę motywu, wolną strefę pod tytuł, możliwość szparowania, zgodność z tytułem oraz jakość druku po kadrowaniu. Tożsamości osób nie rozpoznaje.
- Wynik końcowy jest liczony deterministycznie z wag zapisanych w kodzie (`editorial_score`). Obserwacje trafiają do `StoryImageInput.photo_analysis`, a punkt ogniskowy jest wyznaczany z ramki motywu.
- Zdjęcie główne jest oceniane także wtedy, gdy jest jedno. Gdy jego wynik spada poniżej `photo_rules.min_lead_photo_score` (0,52) albo zgodność z tytułem poniżej `min_lead_photo_match` (0,45), API zwraca `422 photo_needed` z komunikatem „Potrzebne inne zdjęcie…”. Redaktor może świadomie wybrać „Generuj mimo to” (`accept_weak_photos`).
- Podglądy wysyłane do VLM są pomniejszane do 1280 px. Pełnorozdzielcze pliki powodowały timeout i ciche powrócenie do kolejności z uploadu.
- Test na żywym modelu (gemini-3.1-pro-preview), zdjęcie z demonstracji „Nie mamy jak wrócić do domu!”: model rozpoznał pozowaną scenę stockową (relevance 0,10, headline_match 0,00), wybrał lepsze z dwóch zdjęć i zatrzymał generowanie z uzasadnieniem. Dokładnie tę wadę opisywał wcześniej niezależny krytyk.
- Interfejs pokazuje komunikat o potrzebie innego zdjęcia, a przy każdym wariancie podaje: układ, uzasadnienie wyboru zdjęcia i decyzje podjęte na podstawie zdjęcia.

## B. Morfologie tabloidu (`backend/app/engine/tabloid_morphologies.py`)

Pięć morfologii generowanych z `TitleDNA.cover_grammar["morphologies"]` i grafu sceny (nie z obrazów ani SVG):

| Morfologia | Co ją uruchamia |
| --- | --- |
| `diagonal_hero_entry` – ukośne wejście tytułu w zdjęcie | kąt z nastroju ≥ 2,5° |
| `dual_scale_collage` – kolaż dwóch zdjęć w różnej skali, z passe-partout | drugi materiał ma zdjęcie; wkładka nigdy nie zasłania punktu ogniskowego |
| `photo_dominant_strip` – dominanta fotograficzna z nieregularnym, schodkowym paskiem | rozdzielczość zdjęcia na pełną szerokość; tytuł w wolnej strefie wskazanej przez fotoedytora |
| `directional_tension` – postać patrzy lub idzie w stronę kolumny tytułu | kierunek albo boczna wolna strefa z fotoedycji |
| `type_behind_subject` – tytuł częściowo za szparowaną postacią | prawdziwa maska alfa |

Dodatkowo: „ucho” winiety z prawdziwą zajawką zamiast pustego pola obok tytułu, kontrola budżetu napięcia na stronie oraz `topology_signature` jako miara różnorodności.

Krytyk (twarda bramka):
- kolizje i marginesy są liczone na rzeczywistym, obróconym obrysie, a nie na nieobróconym prostokącie;
- nowy, wąski wyjątek `intentional_photo_inset`: wkładka może przykryć najwyżej 20% zdjęcia i nie może zasłaniać jego motywu.

Eksport: IDML zapisywał wcześniej każdą ramkę bez obrotu, więc ukośne tytuły z podglądu były w InDesignie proste. Teraz `ItemTransform` obraca ramki wokół środka, tak jak SVG, HTML i PDF. Pokrywa to test.

Generator: nowy gen `cover_morphology`. Każda wykonalna morfologia jest sondowana przez tę samą bramkę, a nisze (architektura + morfologia) są oferowane od najlepszej. Do oceny VLM trafia teraz najlepszy kandydat z każdej architektury, a nie trzech sąsiadów optimum heurystyki.

## C. Emocja → forma (`page_mood.py`)

Doszły nastroje `scandal` i `entertainment`. `MoodForm` steruje: kątem, nasyceniem palety, wersalikami, szerokością kroju, obrysem i cieniem, kosztem transgresji, udziałem zdjęcia, ciasnością kadru i długością zajawek. `mood_palette` buduje płaszczyzny materiału z DNA. Dla żałoby nie ma tabloidowej czerwieni ani żółci. Palety rozrywki i triumfu są danymi w gramatyce tytułu, a winieta zachowuje kolory marki.

## Poprawka TV guide

Karty programu TV miały stałe przesunięcia, przez co przy 4–5 materiałach tytuł nachodził na tekst. Każdy z 10 materiałów testowych odpadał w twardej bramce. Po poprawce przechodzą wszystkie.

## Pomiar (procedura §9, `python -m backend.scripts.benchmark_quality`)

Stały zestaw: 10 materiałów (urgent, scandal, solemn, celebratory, entertainment, human) × 6 wariantów, zdjęcia z lokalnego korpusu, novelty liczone wobec FEATURE_INDEX.

| Gatunek | Twarda bramka | Topologie na materiał (mediana / P10) | Novelty (mediana / P10) | Martwe strefy | Czas na materiał | Pamięć szczytowa |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tabloid | 100% (60/60) | 5 / 4 | 0,68 / 0,54 | 2 | 2,1 s | 5,9 MB |
| Magazyn | 100% (50/50) | **1 / 1** | 0,69 / 0,69 | 0 | 1,7 s | 2,2 MB |
| Program TV | 100% (50/50) | **2 / 2** | 0,68 / 0,67 | 0 | 1,9 s | 2,5 MB |

Ocena VLM (gemini-3.1-pro-preview) jednego materiału demonstracyjnego, pojedyncze przebiegi, czyli **orientacyjnie, nie statystycznie**:

| Wariant | overall | style_fidelity | photo_use | photo/headline |
| --- | ---: | ---: | ---: | ---: |
| Wcześniejszy najlepszy (przekazanie) | 0,47 | 0,44 | 0,50 | 0,48 |
| asymmetric_hero_rail (ten sam materiał, dziś) | 0,58 | 0,55 | 0,60 | 0,70 |
| diagonal_hero_entry + ucho | 0,56 | 0,54 | 0,57 | 0,58 |
| dual_scale_collage (bez ucha) | 0,52 | 0,46 | 0,55 | 0,55 |
| photo_dominant_strip + ucho | **0,70** | **0,75** | **0,80** | **0,85** |

Cel „gotowe do redakcji” (0,80 / 0,90 / 0,65 / 0,65) **nie jest osiągnięty**. Najlepsza morfologia spełnia progi zdjęciowe, ale nie ogólny i stylowy.

Pełny pomiar VLM według §9 wymaga stałego zestawu, w którym zdjęcia **pasują** do tematów. Zdjęcia z korpusu przypisane mechanicznie do 10 tematów to fotografie prasowe z innych historii, w tym realnych polityków. VLM słusznie ocenia je na 0,05–0,30 zgodności, więc taki wynik mierzyłby dobór zdjęć, a nie skład. Potrzebny jest zestaw 10 materiałów z własnymi, licencjonowanymi zdjęciami.

## Co pozostaje

1. **Kalibracja heurystycznego krytyka.** Nie ruszałem jego wag. W 6 wariantach na materiał 4 miejsca dostają modułowe układy `popular_collage` (heurystyka ok. 0,79–0,80, morfologie ok. 0,73–0,75), a niezależny VLM ocenia je niżej. Wagi należy kalibrować parami A/B i wynikami VLM, a nie ręcznie.
2. **D. Magazyn:** jedna topologia niezależnie od genu. Generator ignoruje `layout_mode`. Potrzebne są morfologie: portret, detal, martwa natura, reportaż, okładka typograficzna, rozkładówka otwierająca.
3. **E. Program TV:** dwie topologie. Brak pasm godzinowych, stacji jako nawigacji i gęstego copyfittingu ramówki.
4. **Dolny pasek tabloidu** wciąż bywa oceniany jako „sterylny”: zbyt wyrównane kafle i brak wybić oraz stempli.
5. **F.** Prowadzony proces 7 kroków dla laika: dodano tylko obsługę „potrzebne inne zdjęcie” i wyjaśnienia przy wariantach.

## Wdrożenie (do wykonania na komputerze z zalogowanym Vercel CLI)

```
cd /Users/macbookpro/PROJEKTY/LAYOUT && npx vercel --prod --yes
cd /Users/macbookpro/PROJEKTY/LAYOUT/frontend && npx vercel --prod --yes
curl -fsS https://api.zecro.pl/health
```

Następnie należy przejść scenariusz w przeglądarce: logowanie → nowa gazeta → materiały → zdjęcia → generowanie → porównanie → podgląd → PDF/IDML.

Rendery z tej sesji: `output/claude-2026-10-15/` (m5 = wersja końcowa, m4 = przed dodaniem ucha, `vlm-demo.json`). Wyniki pomiaru: `output/benchmark-2026-10-15/`.


---

# Część II — praca nocna 15/16 października (kod gotowy, **niewdrożony**)

Backend z części I jest na produkcji (`api.zecro.pl` – health OK), frontend z części I również.
Zmiany poniżej przechodzą testy i build, ale wymagają ponownego wdrożenia (polecenia na końcu).

## Stan testów
- Backend: **161 passed, 1 skipped, 4 deselected**.
- Frontend: `npm run build` przechodzi.

## 1. Kalibracja krytyka parami A/B (`engine/critic_calibration.py`, `scripts/calibrate_critic.py`)
- 50 par kandydatów z 10 stałych materiałów tabloidu, oceny parami przez osobny krytyk wizualny (`visual_pairwise`, losowa kolejność A/B, ten sam materiał i te same zdjęcia w obu renderach). 47 rozstrzygnięć, 3 remisy.
- Model Bradleya–Terry'ego na 15 interpretowalnych cechach (m.in. jednorodność modułów, udział zdjęcia głównego, ukośne wejście, największa pusta strefa).
- **Stary heurystyczny krytyk zgadzał się z oceną parami tylko w 40% par** (gorzej niż losowo). Model skalibrowany: **95,7% trafności leave-one-out**.
- Bilans architektur w parach: modular-grid 0 wygranych / 11 porażek, stacked 1/11, diagonal_hero_entry 9/0, asymmetric_hero_rail 9/1, photo_dominant_strip 9/4, dual_scale_collage 11/7.
- Kalibracja zapisana jako dane: `backend/app/engine/calibration/tabloid.json` (źródło: VLM; liczba par; LOO; heurystyka). Krytyk używa jej tylko, gdy ≥20 par i LOO ≥ 0,70. Wtedy wynik = 0,30 heurystyka + 0,30 kalibracja + nowość (+ preferencje projektu z pętli gustu).
- Efekt: dla tego samego materiału ranking otwierają diagonal_hero_entry (0,877), asymmetric_hero_rail (0,872), photo_dominant_strip (0,828); siatka modułowa spada na koniec (0,598).
- **Uczciwie:** to kalibracja do niezależnego krytyka VLM, nie gustu człowieka. Pary od redaktora można dopisywać do `output/calibration/tabloid/pairs.jsonl` z `"source": "human"` i ponownie uruchomić `fit`. Pętla gustu projektu nadal działa niezależnie.

## 2. Magazyn (`engine/magazine_morphologies.py`)
- Cztery morfologie okładki: **portret** (zdjęcie na spad, linie okładkowe w zmierzonej przestrzeni negatywnej), **detal / martwa natura** (świadoma pustka), **reportaż**, **okładka typograficzna**. Do tego **rozkładówka otwierająca** (zdjęcie na spad po lewej, tytuł, lead i dwułamowy tekst po prawej).
- Linie okładkowe na zdjęciu: kompozytor mierzy jasność i fakturę pikseli pod linią i wybiera farbę o wyższym kontraście. Gdy tło jest niespokojne albo pliku nie da się zmierzyć, linia dostaje podkładkę. Strona linii wynika z ramki postaci (`subject_box`) z fotoedycji.
- Twarda bramka: linia na zdjęciu musi mieć zmierzony kontrast ≥ 3:1 i nie może zakrywać więcej niż 15% ramki postaci. Test sprawdza, że przesunięcie linii na postać jest odrzucane.
- Portret wymaga potwierdzonej postaci i co najmniej 30% wolnej szerokości obok niej. Na zdjęciu demonstracyjnym (dwie osoby na całej szerokości) system słusznie odmawia tej morfologii.
- Pomiar: topologie na materiał wzrosły z 1 do 4 (mediana i P10).

## 3. Program TV (`engine/tv_listing.py`, `PageInputMaterial.tv_schedule`)
- Ramówka to dane: stacja, godzina, tytuł, gatunek, opis, program dnia.
- Strona ma: zakładki stacji w kolorach z DNA (kolor = nawigacja), „program dnia” na górze albo na dole (gen architektury), pasma godzinowe (Rano / Popołudnie / Wieczór / Noc) z etykietą, kolumnę każdej stacji pod jej zakładką oraz gęsty copyfitting do 6,5 pt.
- Programy, które się nie mieszczą, oraz stacje ponad limit **nie znikają po cichu**: trafiają do `missing_content_refs` i twarda bramka zatrzymuje stronę.
- W interfejsie dodano pole ramówki dla programu TV (format `stacja; godzina; tytuł; gatunek; *`).
- Strony poradnikowe TV nie zostały zrobione.

## 4. Prowadzony proces dla laika
- Pasek boczny prowadzi przez 7 kroków: nazwa i rodzaj → materiały → kontrola zdjęć → generowanie → trzy najlepsze propozycje → proste poprawki → eksport. Ukończone kroki mają zielony znacznik. Pozostałe narzędzia (DNA, korpus, wydanie, plan, porównanie, AI) są ukryte w „Pozostałe narzędzia”.
- Krok 3: nowy endpoint `POST /projects/{id}/photo-check` i sekcja „Kontrola zdjęć przed składem” z oceną, zgodnością z tytułem, emocją i uzasadnieniem, zanim powstanie jakikolwiek układ.
- Krok 5: sekcja „Trzy najlepsze propozycje i czym się różnią” pokazuje różnice liczone ze strony: układ, udział zdjęcia, liczbę zdjęć i tematów, ukośny tytuł.
- Odczyt i zapis `localStorage` są bezpieczne. Wcześniej wyjątek przeglądarki mógł przerwać ładowanie projektów.

## 5. Pomiar końcowy (10 materiałów × 6 wariantów, `output/benchmark-2026-10-15-final`)

| Gatunek | Bramka | Topologie / materiał (med / P10) | Novelty (med / P10) | Czas | Pamięć |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tabloid | 100% | 6 / 4 | 0,64 / 0,45 | 2,6 s | 6 MB |
| Magazyn | 100% | 4 / 4 (wcześniej 1 / 1) | 0,71 / 0,69 | 0,5 s | 1,9 MB |
| Program TV (z ramówką) | 100% | 2 / 2 | — (brak ramówek w korpusie) | 3,6 s | 6,5 MB |

W magazynie 6 kandydatów ma dużą pustą strefę. To świadoma przestrzeń negatywna morfologii „detal”; bramka pustych stref dotyczy tylko okładek popularnych.

## 6. Czego nie zrobiłem lub nie mogłem sprawdzić
- **Scenariusz E2E na produkcji:** zecro.pl wymaga hasła dostępu, a hasła nie wpisuję. Sprawdziłem tylko: `api.zecro.pl/health` (healthy, Postgres i Supabase trwałe) oraz konsolę ekranu logowania. Konsola pokazuje dwa wyjątki „Access to storage is not allowed”, prawdopodobnie z rozszerzenia; utwardziłem kod na ten przypadek.
- **Ocena VLM pełnego zestawu:** nadal wymaga zestawu materiałów z pasującymi, licencjonowanymi zdjęciami.
- **Brak:** inicjału (drop cap) w rozkładówce (renderery go nie obsługują), stron poradnikowych TV, kalibracji dla magazynu i TV (za mało par).

## Wdrożenie części II
```
cd /Users/macbookpro/PROJEKTY/LAYOUT && npx vercel --prod --yes
rm -rf /tmp/zecro-fe && mkdir -p /tmp/zecro-fe/.vercel && \
rsync -a --exclude node_modules --exclude dist --exclude .vercel --exclude '.env*' \
  /Users/macbookpro/PROJEKTY/LAYOUT/frontend/ /tmp/zecro-fe/frontend/ && \
cp /Users/macbookpro/PROJEKTY/LAYOUT/frontend/.vercel/project.json /tmp/zecro-fe/.vercel/ && \
cd /tmp/zecro-fe && npx vercel --prod --yes
curl -fsS https://api.zecro.pl/health
```

---

## Część III — okładka warstwowa na przykładzie Wukadki (15.10.2026, wieczór)

### Diagnoza
Dotychczasowy silnik zakładał, że materiały na stronie to prostokąty, które na siebie nie nachodzą (bramka kolizji, nałożenie tylko jako „wykroczenie” z budżetu). Tabloid działa odwrotnie: nakładanie warstw to podstawa składu. Dlatego wcześniejsze okładki wyglądały jak przestawianie klocków.

### Co powstało
- **Zestaw tytułu (`backend/app/engine/title_kits/wukadka/`)** — dane zmierzone z plików produkcyjnych NR20–NR22: format 264,6 × 390 mm, paleta (czerwień #e62e33, granat panelu #567199, żółć, turkus, cyjan), kroje z folderu „Document fonts” (Nimbus Sans D Black Condensed, Myriad Pro Bold Condensed Italic, Utopia Bold), winieta wycięta z PDF NR20 do PNG z przezroczystością, geometria ramy marki (panel, winieta, pasek z datą, karta, skybox).
- **Kompozytor `layered_cover.py`** — warstwy: rama marki → karta → wycięte postacie → tytuły składane słowo po słowie → naklejki i roundel. Kluczowe mechanizmy:
  - tytuł-stos: podział na linie wybierany ze wszystkich możliwych; każda linia skalowana do szerokości; słowa wyróżnione (`headline_emphasis`) w kolorze akcentu; odstępy liczone z rzeczywistych konturów glifów (kreski nad Ś/Ć, ogonki Ą/Ę);
  - miejsce na lead wybierane razem z łamaniem tytułu (obok krótkiej linii albo pod stosem); na NR21 algorytm sam doszedł do rozwiązania grafika: „TAK NIE / DASZ / SIĘ + lead / OKRAŚĆ”;
  - postać główna: możliwie wysoko, ale zakrywa najwyżej 12% winiety (mierzone z maski), twarz nie może wejść pod pasek z datą ani skybox; tytuł, imię i lead na tułowiu, nigdy na twarzy;
  - roundel „W środku” stawiany w największej pustej przestrzeni;
  - teaser dolny: pasek na całą szerokość albo moduł w rogu z wyciętą głową;
  - tekst ciągły nie powiększa ramki: skracany po zdaniach albo powiększany w zakresie stopni zestawu, aż wypełni ramkę.
- **Reguły krytyka dla okładek warstwowych (`layered_rules.py`)** zamiast zakazu kolizji: tekst nie leży na tekście (kontury glifów), nic nie zakrywa twarzy (detektor YuNet), postać zakrywa najwyżej dopuszczalną część winiety (z maski), kontrast WCAG mierzony na rzeczywistych pikselach pod tekstem (≥ 3:1 dla dużego, ≥ 4,5:1 dla małego tekstu). Kompozytor sam naprawia kontrast konturem albo kolorem zastępczym z zestawu i zapisuje każdą taką decyzję.
- **Silnik czcionek**: wybór odmiany po kursywie i szerokości (`font_style`, `font_stretch`, wagi liczbowe) — w PDF, w copyfit i w krytyku ten sam krój.
- **Logo w PDF** zachowuje przezroczystość (wcześniej było spłaszczane na biało).
- **Testy**: `test_layered_cover.py` (7 testów); cały zestaw: 181 zaliczonych.

### Wynik
Okładki A, B i C z materiałów NR21 (te same teksty i zdjęcia, wycięcia rembg isnet) przechodzą twardą bramkę. Porównanie parami przez model wizyjny (`output/wukadka-demo/vlm-pary*.json`): **oryginał grafika wygrywa każde porównanie (6/6, pewność 0,85–0,9)**. Powody wskazane przez model: mocniejsze skosy, postać śmielej wchodząca na winietę, dolny moduł z dwiema postaciami, mniej pustego miejsca. Między naszymi wariantami: A > C > B.

### Czego jeszcze nie ma
- Okładka warstwowa nie jest jeszcze podpięta pod generator w aplikacji (na razie silnik i skrypt `backend/scripts/wukadka_demo.py`).
- Wycinanie postaci działa w kontenerze roboczym (rembg); na Vercelu rembg nie jest zainstalowany — trzeba użyć istniejącej ścieżki segmentacji Gemini albo osobnej usługi.
- Brak wariantu „temat główny z ludźmi” (NR22: dwie postacie przy tytule) i modułów z kilkoma postaciami.
- Wyróżnione słowa tytułu na razie podaje redaktor; propozycja przez AI to następny krok.

### Poprawka po uwagach (wieczór): wiersz na krawędzi ramki, szparowanie
Przyczyna: parametry okładki były zgadnięte, a nie zmierzone, a bramka nie sprawdzała wierszy leżących na krawędzi plamy.
- **Kroje i stopnie odczytane z fontów osadzonych w PDF okładek NR20–NR22**: stos i belki tytułu głównego — Gotham XNarrow Black (134–218 pt); tytuł postaci — Upgrade Black Italic; „Rozmowy Wukadki” — Upgrade Medium/Semibold Italic; dolne zapowiedzi i roundel — Nimbus Sans D Black Condensed; STR. — AmsiPro Narrow Black 10 pt; tekst — Utopia Bold 8,8–9,6 pt. Wcześniejszy zestaw wziąłem z folderu „Document fonts” rozkładówki 4–5, a nie z okładki.
- **Obrót tytułu głównego zmierzony: 8,8–9,0°** (wcześniej −3°). Stos jest teraz składany w obróconym układzie: wolne miejsce to karta minus postać, jej tytuły i dolna zapowiedź, obrócone o ten kąt. Wiersze mają jeden skośny margines; każdy wiersz jest sprawdzany w miejscu, w którym naprawdę ląduje.
- **Tracking** (szparowanie) — z IDML NR22 4–5: Gotham XNarrow Black −20…−30, Nimbus Sans D Black Cond −30…−50, Upgrade Black Italic −50 (1/1000 em). Obsługiwany teraz przez shaper, copyfit, krytyka, PDF, SVG, HTML i IDML (`ElementStyle.tracking_em`).
- **Nowa reguła bramki**: wiersz tekstu nie może leżeć na widocznej krawędzi plamy (karty, panelu, belki); krawędź zasłonięta przez postać się nie liczy. Gdy tytuł schodzi niżej niż karta, karta i niebieski panel idą do spadu.
- **Brak w bibliotece rodziny Upgrade** — tytuł postaci, „Rozmowy” i pasek z datą są składane zamiennikami (Avenir Next Heavy Italic, Myriad Pro) i każda zamiana jest zapisywana w decyzjach strony. Do wgrania: Upgrade Black Italic, Medium Italic, Semibold Italic, Semibold, Regular.
- Ponowne porównanie przez model wizyjny (`vlm-pary-2.json`): oryginał wygrywa 3/3 (pewność 0,85–0,9) — „bardziej masywny tytuł, brak pustych pól, dolna zajawka z dwiema postaciami”. Testy: 181 zaliczonych.

## Część IV — okładka z modułów (szkielet ramy Wukadki)

- **Szkielet zmierzony z wektorów PDF NR20–NR22** (`engine/cover_modules.py`): rama tytułu (pas winiety, lewa listwa, belka 13° szer. 9,7 mm, dolna listwa), okno tematu dnia między listwą a belką, skybox 22–71,2 mm (odstęp 11,2), postać 3,8 mm pod skyboxem do spadu, blok tekstów postaci do x = 258,7, roundel ze środkiem na osi belki, zapowiedź dolna od stopy belki (narożnik) albo pas pod ramą (NR22).
- **Tytuł pochylony, nie obracany**: `Frame.skew_y_deg` (pionowe kreski zostają pionowe, prawy koniec wznosi się o 8,8°) — PDF, SVG, HTML, krytyk i kontury glifów. Wiersze wypełniają okno na swojej wysokości, kotwica = lewy margines okna; wiersze bez słowa wyróżnionego ≤ 0,8 × największy wyróżniony; odstępy między wierszami liczone z kolizji ogonków i akcentów (wiersze się zazębiają jak w NR21).
- **Kompozytor `engine/framed_cover.py`** tylko wypełnia moduły. Każdy element ma znacznik `module:<nazwa>`; bramka odrzuca element bez modułu („pływający”) i element wychodzący poza moduł (poza wyjściami dozwolonymi przez gramatykę tytułu). Nowe reguły bramki: wycięcie postaci nie zasłania tekstu; szew między dwiema plamami tego samego koloru nie jest krawędzią.
- **Postać**: położenie liczone tak, by twarz nie wchodziła pod pasek daty, a włosy zakrywały najwyżej 12 % winiety (zmierzone w NR21: 9 %); obraz większy od strony jest kadrowany na spadzie, nigdy zniekształcany.
- **Błąd w ocenie**: wcześniejsze porównania przez model wizyjny i zestawienia obcinały nasze strony o 10 mm z każdej strony (PNG jest już w formacie netto). Wyniki z części III były przez to zaniżone. Poprawione.
- **Wynik (uczciwy)**: F1 i F2 przechodzą bramkę. Porównanie parami z oryginałem NR21 (obie kolejności): oryginał wygrywa 3 z 4, F2 wygrał raz (pewność 0,8) — wynik zależny od kolejności, więc remisu nie ogłaszam. Model wskazuje: puste pola przy dolnym module, skala zdjęć polityków (pas F2), zamiennik kroju Upgrade.
- Testy: 183 zaliczone.

## Część V — wiedza z korpusu prasy i AI w roli dyrektora/redaktora (15–16.10.2026)

**Korpus.** Zmierzono 14 315 stron z 3 966 wydań (800 tytułów, 39 krajów) jednym przyrządem
(`backend/scripts/press_corpus/measure.py`): pierwsze strony ~520 dzienników (Freedom Forum, 8 dat),
pełne wydania (archive.org: tabloidy UK i inne, Metro, dzienniki regionalne, lokalne USA, programy TV
PL i TV Guide, newsmagazyny, magazyny, gazety PL) oraz wszystkie strony Wukadki NR20–22. Wynik:
`backend/app/knowledge/press_norms.{json,md}`, `press_archetypes.json`, surowe pomiary
`backend/corpus/press/*.jsonl` (bez treści).

**Wiedza w silniku.** `knowledge/rulebook.md` (U1–U14, gramatyki typów, N1–N7 z pomiarów),
`knowledge/defects.json` (D01–D25). `engine/press_norms.py` mierzy naszą stronę tymi samymi miarami
i podaje jej położenie w normach gatunku.

**Role AI.** `engine/art_director.py`: dyrektor planuje wyłącznie ruchami kompozytora (Wukadka:
łamanie × akcent mierzone przez silnik, dolna zapowiedź, skala postaci…; kompozytor ogólny: architektura,
dominanta, zdjęcia — dla quality_press, mass_market, tabloid, magazyn, TV, pierwsza i środek); redaktor
techniczny ocenia całość i zbliżenia z pomiarami jako faktami; sędzia tytułu porównuje w obu
kolejnościach, remis rozstrzyga odległość od norm. Skrypt: `scripts/art_direct_demo.py`.

**Mechanizm.** Wykańczanie każdego wycięcia (kontur po wewnętrznej stronie włosów, odkażony brzeg,
~0,15 mm), bez wielokątnego clipu; reguły bramki D05 (drobny tekst na zdjęciu), D07 (twarz < 12 mm),
D09 (proste cięcie kadru tylko na rysowanej krawędzi, pod elementem albo na spadzie); solver gwiazdy
chowa cięcia; maks. 2 przeniesienia z rzędu; stały stopień tekstu tytułu.

**Stan.** Testy: 186 ✓, 1 ✗ (`test_frame_fill_and_shapes::test_short_source…` — zależny od biblioteki
krojów, nie od tych zmian). Nic nie zacommitowano ani nie wdrożono. Znane braki: redaktor wizyjny
nadal bywa niekonsekwentny (pomiary w promptach to ograniczają); kompozytor ogólny tabloidu-kolażu daje
słabe strony (pętla to pokazuje, wymaga przebudowy jak framed_cover); bramka D09 działa tylko dla
kompozycji modułowych (layered).

## VI. Domknięcie zasad z okładki NR21 (16.10.2026)

Zasady działają ogólnie, w silniku i w bramce, a nie tylko dla jednej okładki.

- **Bohater w kolumnie (U16–U18).** Solver kadru ma twarde limity: twarz widoczna, winieta zasłonięta najwyżej w 12 %, druk ≥ 180 dpi. W ich granicach zdjęcie sięga jak najdalej pod pochyloną belkę. To, czego nie sięgnie, zamyka grunt ramy, nigdy papier. Większa łata (> 4 cm²) oznacza błąd D30, a redaktor dostaje wskazówkę: wyższy moduł dolny albo inne zdjęcie. Wynik solvera jest zapamiętywany.
- **Twarz rozcięta między dwa kadry tego samego zdjęcia** jest oceniana w całości (wcześniej dawała fałszywe „11 mm”).
- **Tytuł w oknie.** Koniec wiersza ograniczają podstawa wiersza przy belce (belka pochyla się w lewo ku dołowi), górna listwa okna i naklejka z pierścieniem. Lead bez miejsca obok wiersza idzie pod stos.
- **Dziura w oknie (D28 dla okien).** Bramka mierzy największe wolne pole okna; limit to 30 cm². Gdy cały tekst źródłowy jest złożony, a łamania nie wymusił dyrektor, zamiast błędu powstaje prośba o dłuższy lead. Ramka tekstu ciągłego bez apli ma wysokość złożonego tekstu, więc pusta stopa modułu jest widoczna jako dziura.
- **Pomiar łamań dla dyrektora** zawiera teraz `dziura_okna_cm2`, liczoną tą samą miarą co bramka. Łamania z dziurą > 30 cm² trafiają na koniec listy.
- **Redaktor a pomiar.** Defekty mierzone przez silnik (D07, D09, D26, D27, D29, D30) zgłoszone przez AI wbrew bramce są odrzucane razem z poprawkami, które tylko na nich się opierały.
- **Redaktor techniczny przed rundą** sprawdza poprawki na silniku. Ruch, który łamie bramkę, odpada z zapisanym powodem.
- **Katalog i podręcznik:** D30 (klin papieru) w `defects.json`, rozszerzone U18 w `rulebook.md`.

Testy: 186 przechodzi, a 2 testy wolnego kolażu są oznaczone jako znane błędy (xfail). Poza tym nie przechodzi `test_short_source_becomes_an_expansion_request_not_a_hole` (kompozytor kafelkowy, copyfit 1,25×). Ten błąd nie wynika z tych zmian: występuje także po wyłączeniu nowych reguł dzielenia wyrazów. Test `test_contract_title_dna_schema_validation` wymaga uruchomienia z katalogu głównego repozytorium.

Znane luki: na podglądzie PNG widać włoskowatą linię na wspólnej krawędzi zdjęcia i plamy (antyaliasing podglądu; na naświetlarce jej nie ma). Pętla AI potrafi oscylować między wariantem narożnika a paskiem. Wariant narożnika z wycięciami zostawia lukę nad głową (bramka to łapie).

## VII. Ustabilizowanie pętli AI, eliminacja defektów i integracja ze studiem (16.10.2026)

Wszystkie zaplanowane zadania kontynuacji zostały zrealizowane jako reguły ogólne w silniku, bramce, API i interfejsie użytkownika.

1. **Pętla AI bez oscylacji (`backend/app/engine/art_director.py`, `backend/app/ai/prompts/layout_review.md`):**
   - Do promptu Redaktora Technicznego przekazywana jest pełna historia dotychczasowych prób: zestaw genów, werdykt bramki (PASS/FAIL) oraz zgłoszone defekty.
   - Wprowadzono twardą blokadę `forbidden_genes`: konfiguracja genów, która w poprzednich rundach przegrała pojedynek u sędziego lub została odrzucona przez bramkę, nie może być ponownie wybrana.
   - W trybie `breakout` (domyślnym dla okładki ramowej z wyjściem postaci) ukryto nieaktywne ruchy (`hero_shift`, `hero_dy`), które wprowadzały szum decyzyjny. Aktywne ruchy to m.in. `bottom: strip/corner`, `headline_case: upper/title`, `head_scale`, `corner_photos`.
   - Rezultat: 4 rundy pętli AI kończą się stabilnym kandydatem z wynikiem bramki PASS, bez cyklicznych nawrotów do gorszego układu.

2. **Narożnik z wycięciami (`corner_photos: cutout`) bez dziury nad głową (`backend/app/engine/framed_cover.py`):**
   - Usunięto defekt D28 (luka 24 cm² nad głową w żółtym pudełku zapowiedzi dolnej).
   - Skalowanie i pozycjonowanie wycięć w narożniku (`cutout`) zostało powiązane bezpośrednio z faktyczną wysokością modułu dolnego (`b_h`) zamiast stałej wartości.
   - Wariant z wycięciami w narożniku przechodzi bramkę jakości (GATE PASS).

3. **Likwidacja włoskowatej linii na wspólnej krawędzi (`backend/app/renderers/pdf_renderer.py`):**
   - Zaimplementowano regułę trappingu (nadlewu krawędzi) dla antyaliasingu rasteryzatora PNG: elementy spodnie leżące pod wyższymi elementami o wspólnej krawędzi otrzymują nadlew 0,25 mm pod element przykrywający.
   - Włoskowata linia tła na styku zdjęcia i belki zniknęła na podglądach renderera.

4. **Przeniesienie prymitywów U15–U19 do pozostałych kompozytorów (`backend/app/engine/plan_composer.py`):**
   - Rozszerzono kontekst `_Ctx` w kompozytorze planowanym o:
     - `photo_fill`: kadr typu cover wypełniający moduł (U16) ze skalowaniem do minimalnej wysokości twarzy (`min_face_mm=14.0`) i flagą `fills_module`.
     - `fill_block`: formatowanie tytułu z wypełnieniem modułu bez wiszących spójników i sierotek (U5/U16).
     - `snap_near_edges`: eliminacja mikroszczelin 0,3–2,5 mm (U18/D29) z ochroną przed ujemnymi wymiarami ramek i ignorowaniem linii dekoracyjnych (< 2 mm).
   - Wpięto automatyczne wywołanie `ctx.snap_near_edges()` do układów dzienników (`compose_planned_page`), magazynów i okładek popularnych (`_compose_popular_cover`, `_compose_popular_poster_cover`, `_compose_popular_type_cover`, `_compose_editorial_or_service_cover`).
   - Zabezpieczono nowym zestawem testów w `backend/tests/test_plan_composer_primitives.py` (3/3 przeszły).

5. **Naprawa kompozytora kafelkowego (`backend/app/engine/frame_fill.py`):**
   - Poprawiono obsługę copyfit 1,25× w teście `test_short_source_becomes_an_expansion_request_not_a_hole`. Zamiast błędnego oznaczania za krótkiego tekstu źródłowego jako dziury w makiecie, silnik prawidłowo generuje żądanie rozbudowy tekstu (`needs_more_source = True`, `expansion_request`).

6. **Wystawienie okładki ramowej i pętli AI w API oraz studiu zecro.pl:**
   - **Backend API (`backend/app/api/generate.py`):**
     - `POST /projects/{project_id}/framed-cover`: generowanie wariantu okładki ramowej z wyliczeniem metryk i miniaturą SVG.
     - `POST /projects/{project_id}/art-direct`: uruchomienie pełnej pętli AI (Dyrektor → Silnik → Redaktor → Sędzia) z zapisem rund i śladu decyzyjnego w metadanych kandydata.
     - `POST /projects/{project_id}/art-direct/apply-fixes`: aplikacja poprawek redaktora do genów kompozytora i wygenerowanie poprawionego kandydata.
     - Testy API w `backend/tests/test_api_framed_and_art_direct.py` (3/3 przeszły).
   - **Frontend Studio (`frontend/src/`):**
     - W `GeneratePage.tsx`: przycisk „Pętla AI (okładka ramowa)” uruchamiający pętlę na materiałach projektu.
     - W `SceneGraphCanvas.tsx`: dedykowana karta boczna „AI Redaktor Techniczny & Pętla” prezentująca status werdyktu, ocenę wizualną, listę defektów D01–D30, proponowane poprawki, historię rund pętli oraz interaktywny przycisk **„Zastosuj poprawki AI”**, który natychmiast aktualizuje stronę w studiu.
     - Weryfikacja buildu: `npm run build` w `frontend/` kompiluje się czysto (TypeScript 0 błędów, Vite production bundle wygenerowany w 2,95 s).

7. **Silnik estetyki matematycznej i percepcji wizualnej (`backend/app/engine/aesthetics.py`):**
   - **Xerox PARC (Stephen Harrington et al.):** Optyczna masa elementów (`element_optical_weight`), równowaga pozioma (`calculate_visual_balance`), równomierność pionowa względem złotego środka optycznego 45% wysokości (`calculate_visual_equilibrium`) oraz miara regularności osi Gestalt (`calculate_alignment_rhythm`).
   - **Sophi.io (The Globe and Mail):** Zaawansowany detektor uwięzionej bieli (`detect_trapped_whitespace`), odróżniający naturalny oddech na marginesach zewnętrznych od przypadkowych pustych kieszeni uwięzionych między blokami redakcyjnymi.
   - **Poynter Eyetrack (Mario Garcia):** Weryfikacja jednoznaczności punktu startowego (`evaluate_entry_point`), analiza wektora spojrzenia postaci (`evaluate_gaze_direction` — eliminacja ucieczki wzroku poza krawędź) oraz stabilności kotwicy dolnej (`evaluate_bottom_anchor`).
   - Integracja z krytykiem (`critic.py` -> `aesthetic_index` w heurystykach i bramka na uwięzioną biel) oraz pomiarami pętli AI (`measurements` w `art_director.py`).
   - Zabezpieczono 9 testami w `backend/tests/test_aesthetics.py` (9/9 passed). Cały zestaw: 212 passed, 2 xfailed.


