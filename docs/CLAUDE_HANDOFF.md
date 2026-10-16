# Zecro — przekazanie prac dla Claude

Data przekazania: 15 października 2026  
Repozytorium: `/Users/macbookpro/PROJEKTY/LAYOUT`  
Frontend produkcyjny: `https://zecro.pl/`  
API produkcyjne: `https://api.zecro.pl/`

## 1. Cel produktu

Zecro ma być generatywnym studiem składu prasowego dla użytkownika bez wiedzy DTP. Ma tworzyć autentyczne gazety, magazyny i programy TV na podstawie materiałów redakcyjnych, korpusu stron oraz DNA konkretnego tytułu.

Nie chodzi o wybieranie gotowych szablonów. System powinien:

1. rozumieć gatunek publikacji i temat konkretnej strony;
2. wybrać właściwą architekturę informacji;
3. wybrać zdjęcia pasujące treścią i emocją do materiału;
4. dobrać kadrowanie, fonty, skalę, kapitaliki, outline, cień i kolor;
5. dopasować tekst do rzeczywistych ramek;
6. wygenerować kilka istotnie różnych rozwiązań;
7. odrzucić technicznie lub wizualnie słabe wyniki;
8. wyprowadzić ten sam graf sceny do podglądu i produkcji PDF/IDML.

## 2. Obowiązujące zasady architektury

Przeczytaj przed rozpoczęciem:

- `/Users/macbookpro/PROJEKTY/LAYOUT/AGENTS.md`
- `/Users/macbookpro/PROJEKTY/LAYOUT/SKILL.md`
- `/Users/macbookpro/PROJEKTY/LAYOUT/docs/CORPUS_STYLE_AUDIT.md`
- `/Users/macbookpro/PROJEKTY/LAYOUT/docs/PRESS_TYPOLOGY.md`

Zasady, których nie wolno upraszczać:

- Generator i krytyk muszą pozostać oddzielnymi systemami.
- DNA tytułu jest danymi, nie zestawem zakodowanych szablonów.
- Layout jest grafem sceny z rolami, geometrią, relacjami, ograniczeniami i transgresjami.
- Twarda bramka pass/fail działa przed miękkim rankingiem estetycznym.
- VLM może oceniać i przekazywać ustrukturyzowane uwagi, ale nie może bezpośrednio ustawiać współrzędnych elementów.
- Musi istnieć kontrola nowości i podobieństwa do korpusu, aby system nie kopiował stron.
- Podgląd i eksport produkcyjny muszą korzystać z tego samego grafu sceny.
- Słaby wynik nie może dostać statusu „gotowy” wyłącznie dlatego, że nic nie wychodzi poza stronę.

## 3. Stan wdrożenia

Backend produkcyjny został ostatnio wdrożony jako:

```text
dpl_7WdT34pfPEoz4k1aMKKtb24DkHvp
```

Ostatnia kontrola produkcji:

- API: healthy;
- baza: PostgreSQL, persistent;
- pliki: Supabase Storage, persistent;
- Gemini: ready;
- aktywny model routingu: `gemini-3.8-flash`;
- frontend: działa po polsku, ekran startowy i kreator gazety nie zgłaszały błędów konsoli.

Nie wpisuj sekretów do kodu, dokumentacji ani logów. Klucze Gemini, token administratora, klucz szyfrowania i hasła wejściowe istnieją już w środowisku produkcyjnym lub zaszyfrowanych integracjach.

## 4. Stan testów

Ostatni pełny stabilny przebieg:

```text
136 passed, 1 skipped, 4 deselected
```

Pominięty test dotyczy opcjonalnego OpenCV. Cztery odznaczone testy są oznaczone jako `slow` lub `live_ai`.

Uruchamianie stabilnego zestawu:

```bash
cd /Users/macbookpro/PROJEKTY/LAYOUT
.venv/bin/pytest -q -m 'not slow and not live_ai'
```

Frontend:

```bash
cd /Users/macbookpro/PROJEKTY/LAYOUT/frontend
npm run build
```

Nie wdrażaj, jeśli którykolwiek z tych etapów nie przechodzi.

## 5. Co już zostało zrobione

### Integracje i bezpieczeństwo

- Gemini działa przez centralny routing z fallbackami.
- Klucz jest zaszyfrowany po stronie serwera.
- Panel ustawień nie zapisuje sekretów w przeglądarce.
- Istnieje prywatna bramka dostępu z podpisaną sesją HttpOnly.
- Produkcja korzysta z Supabase dla bazy i plików.

### Interfejs dla laika

- Główna ścieżka zaczyna się od wyraźnego „Nowa gazeta”.
- Użytkownik widzi cztery kroki wykonania pierwszej strony.
- Kreator wyjaśnia rodzaj gazety i format papieru zwykłym językiem.
- Kategorie są po polsku: wiadomości, lokalna, popularna, bulwarowa, magazyn, program TV, biznes, sport, nauka, kultura.
- Listy projektów filtrują techniczne projekty testowe z widoku zwykłego użytkownika.
- Interfejs ustawień, generowania, porównania i eksportu został spolonizowany.

### Typografia i copyfitting

- Tekst jest mierzony rzeczywistym fontem z HarfBuzz/fontTools.
- PDF osadza właściwe fonty.
- System wykrywa pojedyncze słowo pozostawione w ostatnim wierszu tytułu.
- Główny tytuł może przechodzić na wersaliki, zmieniać krój i rozmiar oraz używać outline’u i cienia.
- Tekst może zostać skrócony przez AI, ale tylko w granicach materiału źródłowego i po ponownej kontroli bramki.

### Zdjęcia

- Gemini wyznacza punkt ogniskowy i klasyfikuje typ głównego obiektu.
- System nie próbuje szparować obiektów i scen, które nie są osobą lub zwierzęciem.
- Szparowanie tworzy prawdziwą maskę alfa i kontur.
- Twarda bramka odrzuca maski będące prostokątem lub pokazujące tylko mały fragment obiektu.
- W trakcie generowania z oceną wizualną moduł `backend/app/ai/photo_editor.py` porównuje alternatywne zdjęcia materiału i ustawia najlepsze jako pierwsze. Uwzględnia trafność, reporterskość, jakość techniczną, ryzyka i sugerowany punkt kadrowania.

### Krytyk

- Twarda bramka kontroluje m.in. kolizje, granice strony, kompletność, DPI, copyfit, budżet napięcia, jakość konturu, pusty niezaprojektowany obszar oraz nadmierne podobieństwo do korpusu.
- Gemini ocenia gotowy render PDF, a nie same metadane.
- Próg zgodności gatunkowej dla kandydata redakcyjnego wynosi `0.90`.
- Nawet przekroczenie progu nie jest automatyczną akceptacją redakcyjną.
- Krytyk wizualny działa domyślnie sekwencyjnie, aby kilka równoległych renderów nie zabiło procesu Vercel przez pamięć.

### Typy publikacji

- Osobne architektury istnieją dla gazety opiniotwórczej, tabloidu, prasy masowej, magazynu i programu TV.
- Typy zmieniają architekturę informacji, siatkę, proporcje zdjęć, liczbę modułów, rytm, paletę i transgresje.

## 6. Najważniejszy nierozwiązany problem

Aktualne tabloidy są technicznie znacznie lepsze, ale nadal potrafią wyglądać zbyt modułowo i statycznie. Najlepszy zachowany przykład:

```text
/private/tmp/zecro-final-tabloid.png
/private/tmp/zecro-final-tabloid.pdf
/private/tmp/zecro-final-scene.json
```

Ocena ostatniego renderu przez niezależnego krytyka:

```text
overall:              0.47
style_fidelity:       0.44
photo_use:            0.50
photo_headline_match: 0.48
```

Główne uwagi krytyka:

- statyczna siatka modułowa bardziej przypomina biuletyn niż tabloid;
- fotografie są zbyt spokojne i pozowane;
- za mało reporterskiego napięcia;
- dolne moduły potrafią zawierać martwe pola.

Nie próbuj podnosić wyniku przez zmianę progu albo prompt mówiący modelowi, że wynik ma być wysoki. Trzeba poprawić rzeczywisty render.

## 7. Priorytety dalszej pracy

### Priorytet A — fotoedycja przed geometrią

Obecny moduł wyboru zdjęcia jest pierwszym krokiem. Rozbuduj go:

1. Jeżeli główne zdjęcia mają słaby wynik zgodności, generowanie powinno zatrzymać się z jasnym komunikatem „potrzebne inne zdjęcie”, zamiast układać słabą okładkę.
2. Wynik fotoedycji powinien obejmować:
   - emocję zdjęcia;
   - poziom ruchu i reporterskości;
   - liczbę i wielkość twarzy;
   - kierunek spojrzeń/ruchu;
   - bezpieczny obszar pod tytuł;
   - możliwość szparowania;
   - zgodność z tematem i tytułem;
   - jakość druku po docelowym kadrze.
3. Przekazuj te cechy jako dane do generatora, aby geometria reagowała na zdjęcie.
4. Nie rozpoznawaj tożsamości osób na podstawie twarzy.

Kryterium odbioru: przy dwóch lub większej liczbie zdjęć system konsekwentnie wybiera bardziej dynamiczny i trafny kadr, zapisuje uzasadnienie, a wybór jest widoczny w metadanych sceny i w interfejsie.

### Priorytet B — morfologie zamiast prostokątnych kart

Rozbuduj gramatykę tabloidu o kilka morfologii, które są generowane z parametrów DNA:

- hero z ukośnym wejściem tytułu;
- szparowana postać przecinająca pole tytułowe;
- kolaż dwóch zdjęć o różnej skali;
- dominanta fotograficzna z nieregularnym paskiem informacyjnym;
- asymetryczny układ hero + pionowa szyna + naklejka;
- duży tytuł typograficzny częściowo przykryty obiektem ze zdjęcia;
- kompozycja z wyraźnym napięciem kierunkowym wynikającym z ruchu lub spojrzenia na fotografii.

Każda morfologia musi powstać z danych w `TitleDNA.cover_grammar` i grafu sceny. Nie koduj strony jako jednego SVG ani obrazu tła.

Kryteria odbioru:

- co najmniej trzy istotnie różne, poprawne morfologie dla tego samego materiału;
- ich różnica nie może sprowadzać się do wielkości fontu;
- wszystkie przechodzą twardą bramkę;
- żadna nie zawiera przypadkowych kolizji;
- każda ma jedną dominantę i logiczną drogę wzroku;
- graf sceny pozostaje edytowalny i eksportowalny do PDF oraz IDML.

### Priorytet C — powiązanie emocji materiału z formą

`backend/app/engine/page_mood.py` i metadane materiału powinny wpływać na:

- kąt i kierunek kompozycji;
- nasycenie i kontrast palety;
- wielkość oraz szerokość kroju tytułu;
- wersaliki versus zapis mieszany;
- outline i cień;
- liczbę oraz koszt transgresji;
- rodzaj kadru;
- udział zdjęcia na stronie;
- gęstość i długość zapowiedzi.

Nie stosuj jednej „tabloidowej czerwieni” do wszystkich tematów. Materiał tragiczny, skandaliczny, triumfalny, rozrywkowy i alarmowy powinien mieć różne profile.

### Priorytet D — magazyn

Magazyn nie może być tabloidem z mniejszą liczbą elementów. Potrzebuje:

- świadomej przestrzeni negatywnej;
- fotografii prowadzącej;
- relacji okładkowych linii z sylwetką lub kierunkiem zdjęcia;
- zmiennych morfologii: portret, detal, martwa natura, reportaż, okładka typograficzna;
- eleganckich par fontów i kontrolowanego kontrastu;
- zasad dla okładki oraz rozkładówki otwierającej.

Kryterium odbioru: krytyk rozpoznaje magazyn bez znajomości etykiety gatunku i nie wskazuje struktury gazety codziennej.

### Priorytet E — program TV i poradnik

Program TV wymaga odrębnej logiki użytkowej:

- szybkie skanowanie czasu, stacji i tytułu;
- powtarzalne pasma godzinowe;
- wyróżnienie programu dnia;
- kolor jako nawigacja, nie dekoracja;
- kontrola bardzo gęstego copyfittingu;
- osobne zasady dla okładki, ramówki i stron poradnikowych.

Kryterium odbioru: użytkownik znajduje stację, godzinę i program bez czytania całej strony; layout nadal ma charakter konkretnego tytułu.

### Priorytet F — interfejs laika

Nie dodawaj kolejnych równorzędnych zakładek. Główna ścieżka powinna być prowadzonym procesem:

1. nazwa i typ publikacji;
2. materiały;
3. kontrola jakości materiałów i zdjęć;
4. generowanie;
5. trzy najlepsze propozycje z jasnym wyjaśnieniem różnic;
6. proste poprawki;
7. eksport.

Zaawansowane DNA, routing, dzienniki i koszty powinny być dostępne, ale nie mogą dominować pierwszej ścieżki.

Wszystkie teksty widoczne użytkownikowi mają być po polsku. Angielskie identyfikatory mogą istnieć wyłącznie wewnątrz kodu/API.

## 8. Wymagane testy jakościowe

Nie wystarczą snapshoty komponentów. Dodaj testy, które sprawdzają zachowanie systemu:

1. **Tytuł** — brak uciętych liter, brak samotnego słowa, brak przepełnienia po zmianie fontu i kapitalików.
2. **Zdjęcie** — twarz lub główny obiekt pozostaje w kadrze, efektywne DPI jest wystarczające.
3. **Szparowanie** — maska nie jest prostokątem, fragmentem ani prawie pustym obrazem.
4. **Kompozycja** — jedna dominanta, brak niezaprojektowanej dużej pustej strefy.
5. **Gatunek** — tabloid, magazyn i TV guide dostają różne architektury dla tego samego materiału.
6. **Emocja** — pilny materiał generuje inny profil niż spokojny reportaż.
7. **Różnorodność** — trzy warianty różnią się topologią, nie kosmetyką.
8. **Antykopiowanie** — wynik zbyt podobny do jednej strony korpusu odpada.
9. **Eksport** — SVG/HTML/PDF/IDML reprezentują ten sam graf sceny.
10. **Przeciążenie** — kilka ocen VLM nie zabija procesu i nie gubi częściowych wyników.

## 9. Procedura mierzalnej oceny

Dla każdego gatunku przygotuj stały zestaw co najmniej 10 materiałów testowych o różnych tematach i zdjęciach. Dla każdego generuj minimum 6 wariantów.

Raportuj osobno:

- procent przejścia twardej bramki;
- zgodność gatunkową VLM;
- dopasowanie zdjęcia do tytułu;
- wykorzystanie zdjęcia;
- liczbę martwych stref;
- różnorodność topologiczną;
- nowość wobec korpusu;
- ręczną ocenę par A/B;
- czas i pamięć generowania.

Nie raportuj pojedynczego maksimum jako jakości całego systemu. Podawaj medianę, percentyl 10 i odsetek wyników przekraczających próg.

Docelowe kryterium „gotowe do redakcji”:

- hard gate: pass;
- style fidelity: co najmniej 0.90;
- overall visual score: co najmniej 0.80;
- photo/headline match: co najmniej 0.65;
- photo use: co najmniej 0.65;
- brak `category_mismatch`;
- jawna akceptacja redaktora nadal wymagana.

Wynik 1.0 nie powinien być wymagany mechanicznie. Modelowa ocena VLM nie ma takiej precyzji. Celem jest powtarzalna jakość profesjonalna potwierdzona zestawem testowym i oceną człowieka.

## 10. Ważne pliki

Silnik i kompozycja:

- `backend/app/engine/plan_composer.py`
- `backend/app/engine/evolution.py`
- `backend/app/engine/critic.py`
- `backend/app/engine/display_headline.py`
- `backend/app/engine/copyfit.py`
- `backend/app/engine/page_mood.py`
- `backend/app/engine/editorial_style.py`
- `backend/app/engine/corpus_indexer.py`
- `backend/app/engine/corpus_knowledge.py`

Zdjęcia:

- `backend/app/ai/photo_editor.py`
- `backend/app/ai/photo_focal.py`
- `backend/app/engine/segmentation.py`
- `backend/app/engine/image_ops.py`

AI i krytyk:

- `backend/app/ai/runtime.py`
- `backend/app/ai/integration_registry.py`
- `backend/app/ai/visual_critic.py`
- `backend/app/ai/prompts/visual_critic.md`
- `backend/app/api/generate.py`

Renderery:

- `backend/app/engine/renderers/svg_renderer.py`
- `backend/app/engine/renderers/html_renderer.py`
- `backend/app/engine/renderers/pdf_renderer.py`
- `backend/app/engine/renderers/idml_renderer.py`

Interfejs:

- `frontend/src/App.tsx`
- `frontend/src/components/dashboard/ProjectDashboard.tsx`
- `frontend/src/components/projects/NewProjectModal.tsx`
- `frontend/src/components/generate/GeneratePage.tsx`
- `frontend/src/components/gallery/CandidateGallery.tsx`
- `frontend/src/components/canvas/SceneGraphCanvas.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

Najważniejsze testy:

- `backend/tests/test_cover_grammar.py`
- `backend/tests/test_visual_critic_style.py`
- `backend/tests/test_photo_editor.py`
- `backend/tests/test_image_ops_and_critic.py`
- `backend/tests/test_renderers.py`
- `backend/tests/test_page_mood.py`
- `backend/tests/test_evolution_and_taste_loop.py`

## 11. Pułapki

- Repozytorium zawiera dużą liczbę niezacommitowanych zmian. Nie wykonuj `git reset`, `git checkout .`, czyszczenia ani automatycznego formatowania całego repozytorium.
- Pliki `corpus/FEATURE_INDEX.json` oraz `backend/corpus/FEATURE_INDEX.json` są bardzo duże. Nie regeneruj ich bez konkretnego powodu i dowodu poprawności.
- Nie kopiuj całego lokalnego korpusu do wdrożenia Vercel. Produkcja korzysta z danych zdalnych.
- Nie uruchamiaj wielu pełnych renderów PDF/VLM równocześnie w małym procesie serverless.
- Nie zastępuj braku zdjęcia fikcyjnym obrazem bez jawnej informacji dla użytkownika.
- Nie traktuj metadanych jako dowodu poprawnego renderu. Krytyk musi widzieć raster gotowej strony.
- Nie rozwiązuj kolizji przez ogólne wyłączenie kontroli overlapów.
- Nie twórz szparowania z prostokątnego bounding boxa.
- Nie usuwaj polskich znaków ani nie zamieniaj fontu bez ponownego pomiaru tekstu.
- Nie nazywaj aplikacji perfekcyjną bez raportu z reprezentatywnego zestawu testowego.

## 12. Wdrożenie

Frontend jest połączony z projektem Vercel `zecro-frontend`, backend z `zecro-api`.

Backend ma ustawiony w Vercel Root Directory `backend`. Lokalny deploy wykonuj z katalogu repozytorium, korzystając z istniejącego `.vercel/project.json` oraz `.vercelignore`:

```bash
cd /Users/macbookpro/PROJEKTY/LAYOUT
npx vercel --prod --yes
```

Po każdym wdrożeniu sprawdź:

```bash
curl -fsS https://api.zecro.pl/health
```

Następnie przejdź pełny scenariusz przez produkcyjną przeglądarkę:

```text
logowanie → nowa gazeta → materiały → zdjęcia → generowanie
→ porównanie → podgląd → PDF/IDML
```

Sprawdź błędy konsoli oraz rzeczywisty render, nie tylko odpowiedź API.

## 13. Gotowy prompt startowy dla Claude

Skopiuj Claude’owi poniższy tekst razem z tym dokumentem:

> Pracujesz nad aplikacją Zecro w repozytorium `/Users/macbookpro/PROJEKTY/LAYOUT`. Najpierw przeczytaj `AGENTS.md`, `SKILL.md` i `docs/CLAUDE_HANDOFF.md`. Kontynuuj od obecnego stanu; nie resetuj ani nie cofaj istniejących zmian. Twoim priorytetem jest rzeczywista, mierzalna jakość gazet bulwarowych, magazynów i programów TV. Generator i krytyk muszą pozostać oddzielone, DNA tytułu ma być danymi, a całość ma działać na grafie sceny z twardą bramką przed rankingiem VLM. Najpierw przeprowadź audyt bieżącego renderu i przepływu zdjęć, potem popraw fotoedycję przed geometrią oraz rozbuduj morfologie kompozycyjne tabloidu. Następnie dopracuj odrębne gramatyki magazynu i programu TV. Każdą zmianę potwierdzaj testem zachowania i rzeczywistym renderem. Uruchom pełne testy backendu oraz build frontendu, wykonaj produkcyjne wdrożenie i przejdź cały scenariusz użytkownika w przeglądarce. Nie podnoś wyników przez obniżanie progów. Nie twierdź, że aplikacja jest perfekcyjna bez raportu z reprezentatywnego zestawu testowego. Wszystkie teksty użytkownika mają być po polsku. Sekrety są już skonfigurowane; nie odczytuj ich do logów ani nie zapisuj w kodzie.

