# PROMPT I SPECYFIKACJA DLA CODEX: UNIWERSALNY SILNIK GENERATYWNEGO SKŁADU PRASOWEGO (TITLEDNA STUDIO)

> **Zlecenie:** Zbuduj w pełni funkcjonalną, działającą **lokalnie aplikację webową (FastAPI + React/Vite)** o nazwie **„TitleDNA Studio”**. Aplikacja to autonomiczny silnik projektowania i składu gazet w języku polskim, który potrafi kreować autorskie układy stron w oparciu o 5 globalnych archetypów wyuczonych z **1041 stron z 51 światowych tytułów**, z rygorystycznym polskim zecerstwem, automatycznym szparowaniem zdjęć, oblewaniem tekstem i eksportem do **Adobe InDesign (IDML)** oraz PDF.

---

## 1. DANE I ZASOBY DO WYKORZYSTANIA W REPOZYTORIUM

Codex ma natychmiastowy dostęp do gotowego korpusu w katalogu `corpus/` (zindeksowanego w `corpus/CATALOG.md` i `corpus/INDEX.json`):

* **1041 stron z 51 tytułów pogrupowanych w 5 kategorii:**
  1. **1_powazne_opiniotworcze** (190 stron): *The New York Times, Financial Times, The Wall Street Journal, The Guardian, Le Monde, El País, Corriere della Sera, DER SPIEGEL, Die Zeit, NZZ*.
  2. **2_magazyny** (246 stron): *The Economist, The New Yorker, TIME, National Geographic, The Atlantic, Monocle, Vanity Fair, WIRED, Smithsonian, The Spectator*.
  3. **3_tv_guidy** (160 stron): *Radio Times, TV Guide Magazine, TV Times, What's on TV, TV Choice, Total TV Guide, TV Spielfilm, Télé 7 Jours, Télé Star, TV Hebdo*.
  4. **4_tabloidy_bulwarowe** (238 stron): *Fakt, Bild, The Sun, Daily Mirror, Daily Star, Daily Mail, New York Post, Blick, National Enquirer, Globe* oraz polski tytuł referencyjny: *Wukadka*.
  5. **5_posrednie_masowe** (208 stron): *USA Today, The Times, The Daily Telegraph, i paper, Evening Standard, Ouest-France, La Repubblica, El Mundo, Die Welt, De Telegraaf*.

* **Każdy tytuł posiada podział zecerski na 3 strefy makiety:**
  - `1_pierwsza_strona` (262 okładki/czołówki: winiety, maszty, teasery, wielkie nagłówki, dominanty).
  - `2_srodek_rozkladowki` (528 stron wnętrz: rytm 2–8 szpalt, oblewki, szparowania, infografiki, ramki).
  - `3_ostatnia_strona` (252 strony zamknięcia: dominanty sportowe, felietony, układy plakatowe).

* **Materiały testowe DTP (Wukadka):**
  - Ścieżki: `corpus/wukadka/` oraz `corpus/4_tabloidy_bulwarowe/wukadka/` (6 wydań, 38 plików PDF, 36 plików InDesign `.indd`, 6 pakietów `.idml`, 27 fontów `.otf`, zdjęcia i teksty redakcyjne `.docx`). Służą jako polski poligon doświadczalny i wzorzec walidacji eksportu do InDesigna.

* **Istniejące kontrakty:** `contracts/scene_graph.schema.json`, `contracts/title_dna.schema.json`.

---

## 2. REGUŁY FUNDAMENTALNE ARCHITEKTURY

1. **Generator i Krytyk ZAWSZE rozdzielone:**
   - Generator (algorytmy ewolucyjne + solver geometrii) tworzy dziesiątki kandydatów.
   - Krytyk dwuwarstwowy: **bramka twarda** (brak kolizji, minimalna szerokość łamu 30 mm, hierarchia, prepress) + **miękki gust** (złoty podział, środek ciężkości, ścieżka wzroku, model preferencji użytkownika A/B).
   - ZAKAZ generowania strony jako jednego płaskiego rastra/pikseli (Midjourney-style).

2. **Model danych: Graf Sceny (Scene Graph) w JSON:**
   - Elementy to obiekty ze współrzędnymi `frame (x, y, w, h)`, wagami `importance (0..1)`, rolami (`headline`, `lead`, `body`, `photo`, `caption`, `kicker`, `pullquote`), parametrami szparowania (`treatment: cutout`) i oblewania tekstem (`text_wrap: contour, offset_mm`).

3. **Globalna Przestrzeń Stylów i Suwaki (Style Blending):**
   - System nie jest przypisany do jednej gazety. Użytkownik w UI może stworzyć dowolny polski tytuł i płynnie mieszać cechy archetypów za pomocą suwaków:
     - `[Dziennik Opinii] <――――――●―――――> [Tabloid]`
     - `[Siatka Klasyczna] <―――●―――――――――> [Awangarda Magazynowa]`
     - `[Gęsty Tekst] <――――――――●――――> [Dominanta Foto]`

4. **Anty-Kopiowanie (Novelty Search):**
   - Generator tworzy świeże kompozycje od zera. Krytyk porównuje układ z bazą 1041 stron w `corpus/` i karze/odrzuca układy będące plagiatami.

5. **Rozdział formatów:**
   - Podgląd i oceny: szybki render HTML/CSS print (CSS Paged Media, `shape-outside`) / SVG.
   - Produkcja DTP: **Adobe InDesign (.IDML)** oraz PDF/X.

---

## 3. MODUŁY DO ZAIMPLEMENTOWANIA PRZEZ CODEX LOKALNIE

### Moduł 1: Ekstraktor Cech i Baza Stylów (TitleDNA Engine)
- Analizator plików stron z `corpus/` (wykrywanie liczby kolumn, szerokości rynien, siatki bazowej, histogramu stopni pisma, proporcji foto/tekst).
- Silnik profili: 5 gotowych archetypów bazowych + możliwość importu własnych stron redakcji i zapisu jako edytowalny profil `TitleDNA`.

### Moduł 2: Trzystrefowy Generator Geometrii
- **Czołówka (1. strona):** stała rezerwacja na maszt/winietę, teaser-bary na inne tematy, potężna dominanta wizualna (nagłówek na 4–6 kolumn lub pakszot).
- **Rozkładówki (Środek):** parowanie lewa/prawa (verso/recto), łamanie wieloszpaltowe, połączone wątki tekstu (*text threading*), infografiki i ramki.
- **Zamknięcie (Ostatnia strona):** układ sportowy, felietonowy lub plakatowy.

### Moduł 3: Wirtualny Fotoedytor (Dwutorowy)
- **Tor A (Agencje / Stocki):** pobieranie zdjęć pod słowa kluczowe artykułu (API Unsplash/Pexels w dev, interfejs pod PAP/Getty).
- **Tor B (Generacja AI):** generowanie reporterskich zdjęć syntetycznych (styl 35mm, naturalne światło reporterskie) z zachowaniem tożsamości postaci (Consistent Face / InstantID / Flux LoRA).
- **Szparowanie i Text Wrap:** segmentacja tła (maska alfa) -> wektoryzacja konturu wielokąta (Douglas-Peucker) -> automatyczne oblewanie tekstem (`shape-outside: polygon(...)` w CSS oraz `TextWrapPreference` w IDML).

### Moduł 4: Polska Mikrotypografia i Zecerstwo (Rygor PWN/RJP)
Wdrożenie w `backend/app/engine/polish_typography.py`:
- Automatyczne wstawianie twardych spacji (`&nbsp;` / `\u00A0` / InDesign `NoBreak`) po wiszących spójnikach i przyimkach (*w, z, o, i, a, u, na, do, od, za, po, że, itp.*).
- Wymuszenie polskich cudzysłowów: `„` oraz `”`.
- Wymuszenie półpauz myślnikowych (` – `) i dywizów.
- Copyfitting: mikro-dostrajanie trackingu/kerningu, aby uniknąć bękartów i wdów na końcach kolumn.

### Moduł 5: Pętla Gustu Dyrektora Artystycznego (Human-in-the-Loop)
- Wyświetlanie galerii 6 wygenerowanych propozycji w UI.
- Narzędzie porównań parami A vs B oraz mikro-korekty ręczne (drag & resize na grafie sceny).
- Zapis do bazy `PreferenceSignal` i aktualizacja wag Krytyka (Reward Model).

### Moduł 6: Eksporter Produkcyjny InDesign (IDML) i PDF
- Kompilator grafu sceny do pliku `.idml`:
  - Poprawny kontener ZIP z `designmap.xml`, `Stories/` i `Spreads/`.
  - Zdefiniowane style akapitowe (*Tytul*, *Lead*, *Korpus*, *Podpis*).
  - Połączone wątki ramek tekstowych.
  - Wektorowe ścieżki obcinające na ramkach zdjęć.
- Kompilator PDF/X (Chromium print / Typst) z paserami, spadami 3 mm i tekstem 100% K.

---

## 4. STOS TECHNOLOGICZNY I STRUKTURA PROJEKTU

* **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLite (`backend/data/layout_studio.db`), Pydantic v2, Pillow, NumPy.
* **Frontend:** Vite + React + TypeScript + Tailwind CSS (`frontend/`), interaktywny edytor grafu sceny Canvas/SVG.
* **Uruchomienie lokalne:**
  - Backend: `uvicorn backend.app.main:app --reload --port 8000`
  - Frontend: `cd frontend && npm install && npm run dev`

---

## 5. KROKI WDROŻENIA DLA CODEX (DO WYKONANIA PO KOLEI)

1. **Krok 1:** Zweryfikuj i uruchom lokalne API FastAPI (`backend/app/main.py`) oraz frontend Vite.
2. **Krok 2:** Zaimplementuj ładowanie i indeksowanie 1041 stron z `corpus/` do bazy SQLite oraz generowanie 5 wektorów archetypów stylu.
3. **Krok 3:** Zaimplementuj generator układów obsługujący suwaki stylów i 3 strefy makiety (1. strona, rozkładówka, ostatnia strona).
4. **Krok 4:** Podłącz moduł `image_ops`: szparowanie zdjęć, obliczanie wektorowego konturu i oblewanie tekstem w podglądzie HTML.
5. **Krok 5:** Zintegruj filtr polskiej mikrotypografii (`polish_typography.py`) przy każdym łamaniu tekstu.
6. **Krok 6:** Zaimplementuj sprawdzanie nowości (anty-plagiat) względem bazy stron korpusu w module Krytyka.
7. **Krok 7:** Uruchom generator eksportu do `.idml` (InDesign) i zweryfikuj testowy plik w programie Adobe InDesign.
8. **Krok 8:** Przetestuj pełną pętlę w UI: wprowadzenie polskiego tekstu i zdjęcia -> wygenerowanie wariantów -> wybór wariantu -> pobranie gotowego pliku IDML.
