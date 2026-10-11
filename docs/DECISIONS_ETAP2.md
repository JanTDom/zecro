# Decyzje techniczne — Etap 2

## Zakres

Etap 2 wdraża planowanie strony, integrację Gemini z jawnym statusem dostępności, źródłowo ograniczone operacje redakcyjne, pomiar tekstu, moduły renderowania, realne maski alfa, logo oraz panel integracji. Generator geometrii i krytyk pozostały osobnymi etapami pipeline'u: planer tworzy kontrakt `PagePlan`, generator buduje graf sceny, a krytyk wykonuje twardą bramkę i miękki ranking.

## Decyzje

### 1. Plan strony przed geometrią

Wybrano deterministyczny packer siatki w `backend/app/engine/page_planner.py`. Ranga, pin, numer strony i `teaser_only` są danymi wejściowymi. Każdy tekst jest umieszczany dokładnie raz; zapowiedź jest osobnym, jawnym slotem. Przy stronach gęstych planner przełącza się na zwarty profil wysokości modułów, ale nie schodzi poniżej dwóch szpalt dla modułów tekstowych.

Alternatywa: pozwolić ewolucji wymyślać hierarchię od zera. Odrzucono, ponieważ prowadziło to do duplikowania zapowiedzi i niestabilnej dominaty.

### 2. Gemini przez oficjalny klient i rejestr integracji

`backend/app/ai/gemini_client.py` używa `google-genai`, cache'uje wynik po hashu wejścia i zapisuje provenance oraz zużycie. Prompty są plikami z `prompt_id` i wersją. `IntegrationRegistry` rozdziela routing zadań od implementacji dostawcy.

Jeśli SDK, klucz lub usługa są niedostępne, klient nie generuje zastępczego wyniku: zwraca `unavailable`, a endpoint zdrowia odpowiada HTTP 503. Tryb deterministyczny jest dostępny tylko dla funkcji offline i jest tak oznaczony.

### 3. Sekrety

Sekrety z panelu są szyfrowane Fernetem z kluczem głównym `ZECRO_SECRETS_KEY`. API zwraca wyłącznie maskę i źródło wartości. Wartości `.env.local` są ignorowane przez Git; flaga `ZECRO_LOAD_ENV_FILES` nie blokuje wczytania kluczy dostawców AI.

### 4. Pętla copyfit

Przepełnienie nie kończy się natychmiastowym odrzuceniem. Solver próbuje kolejno wariantu źródłowego, skrócenia ograniczonego materiałem, realokacji w granicach planu i `jump_line`, po czym zapisuje `fit_adjustments` w metadanych sceny. Nie zmieniamy faktów ani nie dopisujemy treści.

### 5. Szparowanie

Kontur powstaje wyłącznie z rzeczywistej maski alfa przez OpenCV `findContours` (`RETR_CCOMP` z hierarchią otworów). Odsunięcie korzysta z `shapely.buffer`, gdy biblioteka jest zainstalowana. Brak maski lub biblioteki nie tworzy sylwetki: element przechodzi do prostokątnego kadru i otrzymuje jawny status.

Starszy eksportowany helper `generate_default_silhouette_contour` pozostaje wyłącznie dla kompatybilności istniejącego testu jednostkowego; nie jest importowany ani wywoływany przez żadną ścieżkę produkcyjną.

### 6. Logo i produkcja

Profil logo jest częścią `TitleDNA`, a element winiety wskazuje na zasób logo. SVG/HTML renderują obraz wektorowy, IDML umieszcza grafikę jako zablokowany linked asset. Graf sceny jest wspólnym źródłem podglądu i eksportu.

### 7. Korpus

Audyt korpusu działa bez fałszywego wyniku Gemini: heurystycznie oznacza oczywiste zanieczyszczenia jako `rejected`, a pozostałe jako `unavailable`, gdy brak modelu. Nic nie jest kasowane; tryb `--apply` przenosi odrzucone pliki do `_quarantine`.

