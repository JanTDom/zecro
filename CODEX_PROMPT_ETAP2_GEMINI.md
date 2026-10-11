# ZLECENIE DLA CODEX — ETAP 2: PRAWDZIWA KREATYWNOŚĆ ZECRO (GEMINI)

> Repozytorium: `LAYOUT/` (Zecro Generative Layout Engine, FastAPI + React/Vite).
> Cel: z tekstów przesłanych lub napisanych przez AI według wskazówek szybko generować strony gotowe do produkcji (PDF/IDML), z realną hierarchią wielu tekstów, realnym doborem zdjęć i realnym szparowaniem.
> Modelem AI całego systemu jest **Gemini API** (Google AI Studio).
> **Tryb pracy: autonomiczny i ciągły** — wykonaj całość (etapy 1–5) bez zatrzymywania się i bez zadawania pytań (zasady 6–7).

---

## 0. ZASADY NADRZĘDNE (obowiązują w każdym module)

1. **Zero atrap.** Żadna funkcja nie może udawać wyniku. Jeśli model, klucz albo usługa są niedostępne, zwracaj jawny status (`unavailable` + powód, HTTP 503 w API) i pokazuj go w UI. Usuń istniejące atrapy, w szczególności `generate_default_silhouette_contour()` jako fallback w `engine/image_ops.py`.
2. **Każdy wynik AI ma provenance.** Zapisuj: model, wersję promptu (`prompt_id@wersja`), hash wejścia, czas, zużycie tokenów, surową odpowiedź (do audytu). Wyniki AI mają status `draft`, dopóki redaktor ich nie zatwierdzi.
3. **Nie fabrykujemy faktów.** Tekst generowany ze źródeł przechodzi przez strażnika źródeł (moduł D). Zdjęcia generowane przez AI nigdy nie udają fotoreportażu (moduł F).
4. **Generator i krytyk zostają rozdzielone**, a graf sceny pozostaje jedynym źródłem dla podglądu i produkcji. Nie łam istniejących kontraktów w `contracts/`; rozszerzaj je z wersjonowaniem (np. `scene_graph.schema.json` → pole `schema_version`).
5. **Każdy moduł kończy się testami** w `backend/tests/` (pytest). Testy wywołujące Gemini oznacz `@pytest.mark.live_ai` i domyślnie pomijaj; testy jednostkowe używają nagranych odpowiedzi (fixtures JSON).
6. **Tryb autonomiczny — pracuj bez przerwy od początku do końca.** Nie zatrzymuj się po etapach, nie pytaj o zgodę, nie czekaj na potwierdzenie. Realizuj kolejno wszystkie etapy z sekcji 12 w jednym ciągu. Decyzje techniczne podejmuj sam, wybierając rozwiązanie najbardziej zgodne z tym dokumentem, i zapisuj je w `docs/DECISIONS_ETAP2.md` (decyzja, alternatywy, powód). Postęp dokumentuj na bieżąco w `docs/CHANGELOG_ETAP2.md`.
7. **Blokery nie zatrzymują pracy.** Jeśli coś się nie da zrobić (brak klucza zewnętrznego API, niedostępna biblioteka, błąd usługi), zapisz to w `docs/BLOCKERS_ETAP2.md` (co, dlaczego, co trzeba dostarczyć), zostaw jawny status `unconfigured`/`unavailable` zgodnie z zasadą 1 i przejdź do kolejnego zadania. Nie obchodź blokera atrapą.

---

## 1. STAN WYJŚCIOWY (wynik audytu — zweryfikuj i napraw)

- `engine/zone_solver.py`: hierarchia to tylko `importance` 0..1; teksty sortowane, pierwszy = dominanta, reszta dzieli miejsce po równo. Na czołówce **każdy tekst poboczny jest składany dwa razy** (pasek zapowiedzi `band` + pełny moduł). Przy 7 tekstach paski mają 40–50 mm szerokości i 10 mm wysokości → tytuły się nie mieszczą.
- Pomiar: generator ewolucyjny przy 7 tekstach na czołówce zwraca **0 kandydatów** (broadsheet i tabloid); przy 3 tekstach w tabloidzie też 0. Przyczyna: przepełnienie tekstu = odrzucenie; brak skracania, realokacji miejsca i „ciągu dalszego”.
- `rank_copy_variants_for_plan()` w `engine/content_engine.py` istnieje, ale nic jej nie wywołuje.
- `build_flat_plan()` rozdziela teksty po stronach modulo (drugi najważniejszy → str. 2). Do wymiany.
- Warianty tekstu (`generate_copy_variants`) to wyłącznie przycięcia; `long`/`exact_fit` = oryginał. Tytuły skracane do prefiksu.
- `pullquote` i `infobox` są przyjmowane w `StoryInput`, ale nigdy nie trafiają na stronę.
- `OPENAI_API_KEY` i `VLM_ENDPOINT` są w `config.py`, ale nieużywane. `DisabledVisionCritic` jest na sztywno.
- Copyfit (`engine/copyfit.py`) szacuje znaki — bez metryk fontów, bez polskiego dzielenia wyrazów, bez Knutha-Plassa.
- Zdjęcia: brak wyszukiwania, generowania, oceny trafności; focal point zawsze `[0.5, 0.5]`.
- Szparowanie: `api/assets.py` przyjmuje tylko gotowe PNG z alfą. `extract_alpha_contour()` bierze skrajne lewe/prawe piksele co n-ty wiersz (gubi wklęsłości), `offset_contour_polygon()` skaluje od centroidu (błędne dla kształtów wklęsłych).
- Korpus `corpus/` jest zanieczyszczony: np. `4_tabloidy_bulwarowe/fakt/1_pierwsza_strona/cbfc-ecinepramaan-*` to indyjskie certyfikaty filmowe, `1_powazne_opiniotworcze/el_pais/1_pierwsza_strona/diccionariohisto00cast_p1.jpg` to oprawa słownika. Skala problemu niezmierzona.

---

## 2. INFRASTRUKTURA GEMINI

### 2.1 Klucz i konfiguracja
- Klucz jest już zapisany jako `GEMINI_API_KEY` w `LAYOUT/.env.local` i `LAYOUT/backend/.env.local` (oba w `.gitignore`). **Nigdy nie wpisuj go do kodu, testów, fixtures, logów ani commitów.** W `.env.example` jest pusty placeholder.
- Zmień `config.py` tak, by klucze dostawców AI (`GEMINI_*`) były wczytywane z `.env.local` zawsze, niezależnie od `ZECRO_LOAD_ENV_FILES` (ta flaga ma dalej sterować tylko bazą/Supabase).
- Zmienne:
  ```
  GEMINI_API_KEY=...
  GEMINI_MODEL_TEXT_PRO=gemini-3.1-pro-preview     # pisanie, redakcja, planowanie strony, krytyka
  GEMINI_MODEL_TEXT_FAST=gemini-3.8-flash          # klasyfikacja, ekstrakcja, warianty masowe
  GEMINI_MODEL_IMAGE=gemini-3-pro-image            # ilustracje (fallback: gemini-3.1-flash-image)
  GEMINI_MODEL_EMBED=gemini-embedding-2            # wyszukiwanie semantyczne w archiwum
  GEMINI_TIMEOUT_S=90
  GEMINI_MAX_RETRIES=3
  AI_MONTHLY_BUDGET_USD=                           # opcjonalny limit; po przekroczeniu jawny 429
  ```
  Nazwy modeli zweryfikowano listą `GET /v1beta/models` z tym kluczem (10.2026). Na starcie aplikacji pobierz listę modeli i zaloguj ostrzeżenie, jeśli skonfigurowanego modelu nie ma.

### 2.2 Klient
- `backend/app/ai/gemini_client.py` na oficjalnym SDK `google-genai` (dodaj do `backend/requirements.txt`).
- Funkcje: `generate_json(model, prompt_id, inputs, response_schema, images=None)`, `generate_image(prompt, aspect_ratio, ...)`, `embed(texts|images)`.
- Zawsze **structured output** (`response_mime_type="application/json"` + `response_schema` z modeli Pydantic). Walidacja Pydantic po stronie serwera; przy błędzie jedna ponowna próba z komunikatem błędu walidacji, potem jawny błąd.
- Retry z backoffem na 429/5xx, timeout, cache wyników po `sha256(model + prompt_id@wersja + inputs)` w tabeli `ai_calls` (SQLite/Postgres przez istniejącą warstwę `models/database.py`).
- Logowanie zużycia (`usage_metadata`) do `ai_calls`; endpoint `GET /ai/usage`.
- Prompty jako pliki w `backend/app/ai/prompts/*.md` z nagłówkiem wersji; żadnych promptów zaszytych w kodzie.
- `GET /health/ai`: realne wywołanie `gemini-3.8-flash` z krótkim zapytaniem + lista dostępnych modeli.
- Zastąp `adapters.py` (adaptery rejestrowane w `IntegrationRegistry`, sekcja 2.3): `GeminiContentWriter`, `GeminiFactChecker`, `GeminiVisionCritic`, `ImageSegmenter` (lokalny, moduł G), `PhotoSearch`, `ImageGenerator`. Deterministyczne implementacje zostają jako tryb offline, ale UI ma jasno pokazywać, który dostawca działa.

### 2.3 Ustawienia integracji (panel „Ustawienia → AI i źródła”)

Zbuduj rozbudowany, edytowalny z poziomu UI panel konfiguracji, w którym użytkownik sam dodaje, testuje i przełącza klucze API do modeli AI oraz do źródeł treści i zdjęć. `.env.local` jest tylko wartością domyślną; konfiguracja z panelu ma pierwszeństwo.

**Model danych i bezpieczeństwo**
- Tabela `integrations`: `{id, kind: ai_provider|photo_source|text_source|agency|storage|other, provider, label, scope: global|project, project_id, enabled, priority, config_json, secret_ref, status, last_test_at, last_test_result, created_by, updated_at}`.
- Sekrety szyfrowane po stronie serwera (`cryptography.Fernet`, klucz główny `ZECRO_SECRETS_KEY` w `.env.local`; bez niego panel pozwala czytać konfigurację, ale nie zapisać nowego sekretu i mówi to wprost). W Supabase — kolumna szyfrowana tak samo, nigdy jawny tekst.
- API nigdy nie zwraca sekretu po zapisie: tylko maska (`AQ.Ab8…ULA`), źródło (`panel` / `env`) i datę zmiany. Frontend nie przechowuje kluczy w localStorage.
- Dziennik zmian (`integration_audit`): kto, kiedy, co zmienił (bez wartości sekretu).
- Dostęp do panelu tylko dla roli administratora (istniejący `AccessGate` rozszerz o role).

**Dostawcy AI (rejestr adapterów, łatwy do rozszerzenia)**
- Gemini (domyślny), OpenAI, Anthropic, Mistral, lokalne modele przez endpoint zgodny z OpenAI (Ollama / LM Studio / vLLM), dowolny „Custom OpenAI-compatible” (base_url + klucz + nazwa modelu).
- Dla każdego dostawcy: klucz, opcjonalny `base_url`, organizacja/projekt, przycisk **„Pobierz listę modeli”** (realne zapytanie do API dostawcy), przycisk **„Testuj połączenie”** (krótkie wywołanie, wynik i czas odpowiedzi).
- **Routing zadań do modeli**: tabela zadanie → (dostawca, model, temperatura, max tokens, limit kosztu, fallback). Zadania co najmniej: `page_planning`, `copy_fit`, `headline_variants`, `write_from_brief`, `fact_guard`, `translate`, `photo_brief`, `photo_ranking`, `image_generation`, `mask_qa`, `visual_critic`, `corpus_audit`, `embeddings`, `logo_analysis`. Domyślne wartości = modele z sekcji 2.1.
- Łańcuch fallbacku per zadanie (np. Gemini Pro → Gemini Flash → OpenAI). Każde przełączenie na fallback zapisywane w provenance wyniku i widoczne w UI.
- Limity: budżet miesięczny globalny i per projekt, limit zapytań na minutę, licznik zużycia z `ai_calls` (tokeny, szacowany koszt według edytowalnego cennika w panelu — cennik wpisuje użytkownik, system go nie zgaduje).

**Źródła zdjęć i treści**
- Zdjęcia: Wikimedia Commons, Openverse (bez klucza — tylko włącz/wyłącz), Unsplash, Pexels, Pixabay, Adobe Stock, Shutterstock, Getty Images, Reuters Connect, AP Newsroom, PAP Fotoserwis, East News, Forum, Agencja Gazeta — każda jako adapter z polami wymaganymi przez danego dostawcę (klucz, login/hasło, ID konta, endpoint). Adaptery agencji, których API nie da się przetestować bez umowy, mają kompletny formularz i status `unconfigured`; nie udają wyników.
- Archiwum redakcji: lokalny katalog, Supabase bucket, S3 / Google Drive / Dropbox (ścieżka lub token), harmonogram indeksowania.
- Źródła tekstów: serwisy agencyjne (PAP, Reuters, AP — format NewsML/IPTC G2 gdzie dostępny), kanały RSS/Atom, strony WWW do pobierania (lista URL z regułą ekstrakcji), skrzynka e-mail redakcji (IMAP — opcjonalnie), import plików (.docx, .md, .txt, .pdf).
- Dla każdego źródła: priorytet w wynikach, domyślna licencja/zakres użycia, wymagany format podpisu (`credit_line` szablon, np. „Fot. {autor}/{agencja}”), filtr języka, przycisk „Testuj” (realne zapytanie testowe z frazą wpisaną przez użytkownika, podgląd 3 wyników).

**Dowolne API (konektor uniwersalny)**
Oprócz gotowych adapterów panel ma przycisk **„Dodaj własne API”**, którym użytkownik podłącza dowolną usługę bez zmian w kodzie:
- Typ: REST (JSON/XML), GraphQL, endpoint zgodny z OpenAI, webhook przychodzący (np. agencja wysyła teksty do Zecro), RSS/Atom.
- Uwierzytelnianie: brak, klucz w nagłówku (dowolna nazwa nagłówka), klucz w query, Bearer, Basic, OAuth2 client credentials (z odświeżaniem tokenu), własne nagłówki stałe.
- Szablon zapytania: metoda, URL z placeholderami (`{query}`, `{lang}`, `{limit}`, `{page}`, `{story.headline}`, `{brief.search_queries_en[0]}`), nagłówki, body (szablon Jinja2 w piaskownicy), paginacja (offset / cursor / link), limit zapytań, timeout.
- **Mapowanie odpowiedzi** (JSONPath / XPath) na kontrakt wewnętrzny wybranej roli, np. dla roli `photo_source`: `results[*].url → url`, `results[*].author → rights_owner`, `results[*].license → license`, `results[*].width → width_px`; dla `text_source`: tytuł, lead, treść, data, autor, URL źródła; dla `ai_provider`: ścieżka do tekstu odpowiedzi i do zużycia tokenów.
- Role, w których można użyć własnego API: `ai_provider` (tekst / obraz / embeddingi / wizja), `photo_source`, `text_source`, `agency`, `fact_source` (bazy danych do weryfikacji, np. rejestry), `storage`, `export_target` (np. wysłanie gotowego PDF do systemu drukarni / CMS).
- Import specyfikacji **OpenAPI / Swagger** (URL lub plik): panel pokazuje listę operacji do wyboru i podpowiada mapowanie.
- „Testuj”: wykonuje realne zapytanie, pokazuje surową odpowiedź obok wyniku mapowania i błędy mapowania pole po polu.
- Konfiguracje własnych API można eksportować/importować jako JSON (bez sekretów).
- Bezpieczeństwo: blokada adresów prywatnych/localhost dla trybu chmurowego (ochrona przed SSRF; w trybie lokalnym dozwolone po jawnym zaznaczeniu), szablony bez dostępu do systemu plików i zmiennych środowiskowych, limity rozmiaru odpowiedzi.
- Własne API rejestruje się w `IntegrationRegistry` tak samo jak adaptery wbudowane i może być użyte w routingu zadań oraz w łańcuchach fallbacku.

**Ustawienia per projekt (tytuł)**
- Projekt może nadpisać: dostawców AI, routing, budżet, listę i kolejność źródeł zdjęć, domyślny styl ilustracji AI, wymagania licencyjne (np. „tylko zdjęcia z licencją redakcyjną”).

**UI**
- `frontend/src/components/settings/IntegrationsSettings.tsx` z zakładkami: *Modele AI*, *Routing zadań*, *Źródła zdjęć*, *Źródła tekstów*, *Własne API*, *Archiwum*, *Limity i koszty*, *Dziennik zmian*.
- Każda karta integracji: status (działa / błąd z komunikatem dostawcy / nieskonfigurowane / wyłączone), data ostatniego testu, maska klucza, źródło wartości (panel/env).
- Na górze aplikacji (pasek statusu) — skrót: które zadania AI i źródła są aktywne; kliknięcie prowadzi do panelu.

**API**
- `GET/POST/PUT/DELETE /settings/integrations`, `POST /settings/integrations/{id}/test`, `GET /settings/integrations/{id}/models`, `POST /settings/integrations/import-openapi`, `GET/PUT /settings/routing`, `GET/PUT /settings/limits`, `GET /settings/audit`.
- Wszystkie moduły (D, F, G, H, I, L) pobierają dostawcę i model wyłącznie przez `IntegrationRegistry.resolve(task, project_id)`; żaden moduł nie czyta kluczy z env bezpośrednio.

---

## 3. MODUŁ A — PLAN STRONY I HIERARCHIA WIELU TEKSTÓW

### 3.1 Model danych
Rozszerz `StoryInput` / `Story` (i kontrakty JSON) o:
```
rank: Literal["lead", "second", "third", "short", "brief", "teaser", "box", "column"]
span_cols: Optional[int]            # docelowa szerokość w szpaltach (None = decyduje plan)
depth_hint: Optional[Literal["S","M","L","XL"]]
target_words: Optional[int]
pin_zone: Optional[Literal["top","under_masthead","left_rail","right_rail","center","bottom","anywhere"]]
pin_page: Optional[int]
teaser_only: bool = False           # tylko zapowiedź na tej stronie, tekst gdzie indziej
continue_to_page: Optional[int]     # dla "ciąg dalszy na str. X"
group: Optional[str]                # teksty powiązane (np. temat + ramka + komentarz)
```
`importance` zostaje jako tie-breaker wewnątrz rangi.

### 3.2 PagePlan (przed geometrią)
- Nowy kontrakt `contracts/page_plan.schema.json` + model `PagePlan`: lista slotów `{slot_id, story_ref, rank, col_start, col_span, row_start, row_span, module_type}` na siatce DNA (szpalty × rzędy modułowe), plus pasek zapowiedzi i winieta (wysokość winiety z Modułu L).
- `engine/page_planner.py`:
  1. **Deterministyczny packer** (dokładny, sprawdzalny): rozmieszcza sloty na siatce według rang, pinów i budżetów (np. czołówka z 7 tekstami → 1 lead, 2 second, szpalta `brief` z 4 tekstami albo pasek zapowiedzi). Gwarantuje: każdy tekst dokładnie raz (albo jawnie jako `teaser_only`), brak kolizji, minimalny łam 30 mm.
  2. **Gemini (TEXT_PRO) jako redaktor wydania**: otrzymuje teksty (tytuł, lead, długość, temat), DNA tytułu i strefę strony; zwraca 3 propozycje planu z uzasadnieniem redakcyjnym (JSON: rangi, grupy, piny, co idzie do zapowiedzi). Packer zamienia każdą propozycję na sloty; propozycje niewykonalne są odrzucane z powodem.
- Generator ewolucyjny dostaje plan jako ograniczenie i eksploruje geometrię **w ramach planu** (proporcje slotów ±1 szpalta, położenie zdjęć, warianty modułów), a nie wymyśla hierarchii od nowa.
- Napraw podwójne składanie: tekst jest albo w `band`, albo w module.

### 3.3 Plan wydania
Zastąp `build_flat_plan()`: czołówka zbiera rangi `lead/second` + zapowiedzi; rozwinięcia idą na wskazane strony; respektuj `pin_page`, `group`, `continue_to_page`. Gemini może proponować plan wydania, packer go waliduje.

### 3.4 UI (frontend)
- Nowy widok **„Makieta”** (`frontend/src/components/plan/PagePlanner.tsx`): lista tekstów z rangą (dropdown), przeciąganie kolejności, przypinanie do strefy; obok siatka strony z prostokątami slotów (drag & resize po szpaltach i rzędach, przyciąganie do siatki). Przycisk „Zaproponuj plan (AI)” pokazuje 3 propozycje z uzasadnieniem; redaktor wybiera i poprawia.
- Wejście do generatora = zatwierdzony plan. `GeneratePage` nie ogranicza liczby tekstów; wprowadź import wielu tekstów naraz (wklejenie, .docx, .md, JSON).

---

## 3A. MODUŁ L — LOGO / WINIETA TYTUŁU I LAYOUT DOSTOSOWANY DO LOGO

Dziś winieta to tekst `masthead_title` złożony fontem nagłówkowym. Ma być możliwość dodania prawdziwego logo gazety, a cały układ ma się do niego dostosowywać.

**Wgrywanie i analiza logo**
- Upload w ustawieniach projektu / edytorze DNA: SVG (preferowany), PDF, EPS, AI (przez konwersję), PNG/WebP z przezroczystością. Wiele wariantów: główny (czołówka), skrócony/znak (strony wewnętrzne, paginacja), monochromatyczny, negatyw (na ciemne tło), wersja pozioma i pionowa.
- Raster bez przezroczystości → automatyczne wycięcie tła (moduł G) i opcjonalna wektoryzacja (`potrace` / `vtracer`), z podglądem i akceptacją redaktora; system nie podmienia logo bez akceptacji.
- Analiza (deterministyczna + Gemini TEXT_PRO z obrazem): proporcje i bounding box treści (bez pustych marginesów pliku), kolory dominujące (k-means w Lab) z konwersją do CMYK, obecność tekstu i jego charakter (szeryfowy / bezszeryfowy / display, wersaliki, kontrast), ciężar optyczny, minimalna czytelna szerokość, wymagane pole ochronne. Wynik zapisany jako `logo_profile` w TitleDNA (rozszerz `title_dna.schema.json`).

**Jak layout dostosowuje się do logo**
- **Wysokość i układ winiety** liczone z proporcji logo i siatki: logo szerokie → winieta pozioma na pełną szerokość; logo zwarte/kwadratowe → winieta z logo po lewej (lub po środku) i „uszami” (ears) po bokach na zapowiedzi, datę, cenę, pogodę; logo pionowe → pas boczny. Wysokość przyciągana do siatki bazowej i rzędów modułowych.
- **Pole ochronne** logo jest twardym więzem w krytyku (kolizja = FAIL).
- **Paleta**: kolory z logo stają się propozycją akcentów DNA (nadtytuły, linie, tła ramek, paski zapowiedzi); redaktor zatwierdza. Kontrola kontrastu (WCAG dla wersji cyfrowej, zasada min. kontrastu / max. TAC dla druku).
- **Typografia**: Gemini proponuje 2–3 pary fontów harmonizujące z charakterem logo (z listy fontów dostępnych w projekcie / Adobe Fonts jeśli podłączone przez panel), z uzasadnieniem; nic nie zmienia się bez akceptacji.
- **Warianty stref**: czołówka = pełne logo; strony wewnętrzne = znak skrócony w paginie; ostatnia strona = wariant wybrany w DNA. Gdy na stronie jest ciemne zdjęcie pod winietą (transgresja „overlap”) — automatycznie wariant negatyw + scrim.
- Generator ewolucyjny traktuje układ winiety jako gen (pozioma / z uszami / boczna / nachodząca na zdjęcie — ta ostatnia tylko jeśli DNA na to pozwala), a krytyk wizualny ocenia relację logo ↔ dominanta strony.

**Produkcja**
- HTML/SVG/PDF: logo osadzone wektorowo (SVG/PDF), bez rasteryzacji; raster tylko jeśli nie ma wektora, z kontrolą DPI.
- IDML: logo jako placed graphic z linkiem do pliku w pakiecie eksportu, na osobnej warstwie „Winieta”, zablokowane.
- Preflight: brak logo wektorowego, za niska rozdzielczość, kolor spoza palety CMYK, naruszenie pola ochronnego → ostrzeżenie/FAIL.

**UI**
- `frontend/src/components/dna/MastheadEditor.tsx`: upload wariantów, podgląd winiety w 3 strefach na żywo, suwaki (wysokość winiety w rzędach, wyrównanie, pole ochronne), propozycje palety i fontów z logo do akceptacji.

---

## 4. MODUŁ B — TYPY MODUŁÓW I RENDEROWANIE

Dodaj do `zone_solver` (lub nowego `module_library.py`) i do **wszystkich** rendererów (`svg`, `html`, `pdf`, `idml`):
- `brief_column` — szpalta krótkich wiadomości (nadtytuł + tytuł + 2–5 zdań, separatory).
- `pullquote` — cytat wyróżniony w łamie (z regułą, że cytat musi dosłownie występować w tekście).
- `infobox` — ramka z danymi (punkty / liczby / mini-tabela), styl z DNA.
- `jump_line` — „ciąg dalszy na str. X” / „dokończenie ze str. X” z wątkowaniem ramek w IDML.
- `teaser_band` — pasek zapowiedzi z numerem strony, szerokość komórki min. 2 szpalty; przy nadmiarze zapowiedzi — mniej zapowiedzi, nie węższe.
- `column` — felieton/komentarz z małym portretem autora.
- `masthead` — winieta z logo (Moduł L) z uszami i paginą.
- Style akapitowe IDML dla każdego modułu (`Cytat`, `Infobox`, `Krotkie`, `Zapowiedz`, `CiagDalszy`).

---

## 5. MODUŁ C — PĘTLA TEKST ↔ UKŁAD (zamiast odrzucania)

W `evolution.py` / `critic.py` przepełnienie tekstu przestaje być natychmiastowym FAIL. Kolejność naprawy dla każdego modułu:
1. Wybór gotowego, zatwierdzonego wariantu tekstu (`rank_copy_variants_for_plan`).
2. Zlecenie Gemini dopasowania do ramy (moduł D, `fit_to_frame`) — wynik jako `draft`.
3. Realokacja miejsca między slotami w granicach planu (±1 szpalta / ±1 rząd).
4. `jump_line` na stronę wskazaną w planie (jeśli dozwolone).
5. Dopiero potem FAIL z konkretną przyczyną i propozycją dla redaktora.
Mikroregulacje (tracking ≤ 10/1000 em, interlinia ≤ DNA) tylko na końcu i tylko w granicach DNA. Wynik pętli zapisuj w metadanych kandydata (co zmieniono i dlaczego).

**Kryterium:** test „7 tekstów na czołówce” (sekcja 11) zwraca ≥ 3 kandydatów PASS w ≥ 3 różnych architekturach, w obu presetach DNA.

---

## 6. MODUŁ D — GEMINI JAKO REDAKTOR TEKSTU

### 6.1 Operacje (`backend/app/ai/editorial_writer.py`, endpointy w `api/editorial.py`)
- `fit_to_frame(story, role, frame, target_words|target_lines)` — skrót/rozwinięcie wyłącznie z materiału źródłowego, styl DNA tytułu.
- `headline_variants(story, width_mm, font, size_pt, max_lines, n=5)` — tytuły pisane pod konkretną szerokość; każdy wariant od razu mierzony copyfitem (moduł E), zwracane tylko mieszczące się.
- `kicker`, `deck/lead`, `caption(image_analysis, story)`, `pullquote_select(story)` (dosłowny cytat z tekstu), `infobox_extract(story)` (liczby i fakty z tekstu, z wskazaniem zdania źródłowego).
- `write_from_brief(brief, sources[], rank, target_words)` — tekst ze źródeł (URL, PDF, notatki); każde zdanie z odnośnikiem do fragmentu źródła.
- `translate(story, lang)` — tłumaczenie z zachowaniem nazw własnych i liczb.
- `teaser(story, page_number)` — zapowiedź na czołówkę.
- Styl: prompt zawiera profil językowy tytułu (np. tabloid: krótkie zdania, mocny czasownik, konkret; dziennik opinii: precyzja, kontekst) oraz listę zakazanych fraz typu AI-slop. Polska mikrotypografia (`polish_typography.py`) zawsze na wyjściu.

### 6.2 Strażnik źródeł (obowiązkowy dla każdej operacji tworzącej tekst)
1. **Deterministycznie**: wyciągnij z wyniku i ze źródła nazwy własne, liczby, daty, kwoty, cytaty w cudzysłowie (regex + prosta normalizacja polskiej fleksji, np. porównanie po rdzeniu / lematyzacji `spacy pl_core_news_sm` jeśli dostępne, inaczej heurystyka prefiksowa — opisz wybór).
2. Każdy element z wyniku, którego nie ma w źródle → flaga `unsupported`.
3. **Gemini (TEXT_FAST), drugie przejście**: weryfikacja twierdzeń zdanie po zdaniu względem źródła (JSON: `supported | partially | unsupported` + cytat ze źródła).
4. Wariant z jakimkolwiek `unsupported` nie może zostać zatwierdzony bez ręcznej decyzji redaktora; UI podświetla te fragmenty.
5. `locked_passages` przechodzą bajt w bajt (już istnieje — zachowaj).

### 6.3 UI
`CopyStudio`: przy każdej ramie przyciski operacji, podgląd wariantów z wynikiem copyfitu (PASS/linie/wolne miejsce) i flagami strażnika; zatwierdzanie wariantu aktualizuje graf sceny.

---

## 7. MODUŁ E — PRAWDZIWY POMIAR TEKSTU

- `engine/shaper.py`: `uharfbuzz` + `fontTools` na fontach z DNA (pliki `.otf/.ttf` — w repo są fonty Wukadki w `corpus/wukadka/`), polskie dzielenie wyrazów `pyphen` (`pl_PL`), łamanie akapitów Knuth-Plass (własna implementacja lub `texhyphen`/biblioteka — opisz wybór), kontrola wdów/bękartów, justowanie z limitami rozstrzelenia.
- Wspólny pomiar dla krytyka, copyfitu, HTML/PDF i IDML. Gdy brak pliku fontu → jawnie tryb `estimate` (obecny estymator) z ostrzeżeniem w preflighcie.
- Test: dla 3 akapitów polskiego tekstu liczba linii z shapera zgadza się z renderem PDF (± 0 linii) przy tym samym foncie.

---

## 8. MODUŁ F — FOTOEDYCJA: DOBÓR, OCENA, GENEROWANIE, KADR

### 8.1 Brief zdjęciowy
`ai/photo_brief.py` (TEXT_FAST): z tekstu → JSON `{who[], where, what_event, when, shot_type: portrait|wide|detail|archival|illustration, must_show[], must_not_show[], search_queries_pl[], search_queries_en[], is_real_event: bool, real_people[]}`.

### 8.2 Tor A — wyszukiwanie (adaptery `PhotoSearch`, konfigurowane w panelu 2.3)
- **Archiwum redakcji** (lokalne/Supabase): indeksowanie zdjęć embeddingami `GEMINI_MODEL_EMBED` (sprawdź, czy model przyjmuje obrazy; jeśli nie — `open_clip` lokalnie i opisz to w CHANGELOG) + metadane IPTC/EXIF (`exiftool` lub `pyexiv2`). Wyszukiwanie semantyczne tekst→obraz.
- **Wikimedia Commons API** i **Openverse API** (bez klucza) — z zapisem licencji i autora.
- **Unsplash / Pexels / inne stocki i agencje** — aktywne tylko gdy klucz jest ustawiony w panelu; inaczej status `unconfigured`.
- **Dowolne własne API** z roli `photo_source` (konektor uniwersalny z 2.3).
- Każdy wynik → rekord `Asset` z `license`, `rights_owner`, `credit_line`, `provider`, `usage_scope`.

### 8.3 Ocena trafności
`GeminiVisionCritic.rank_photos(story, brief, candidates[])` (TEXT_PRO z obrazami): JSON per zdjęcie `{relevance 0-1, depicts_claimed_subject: yes|no|unknown, newsworthiness, technical_quality, crop_suggestion box_2d, risks[], reason}`. Zasada: rozpoznanie konkretnej osoby tylko na podstawie podpisu/metadanych źródła, nie z twarzy — model ocenia zgodność podpisu z treścią obrazu. Redaktor dostaje 4–6 propozycji z uzasadnieniem.

### 8.4 Tor B — generowanie ilustracji
- `ai/image_generator.py` na `GEMINI_MODEL_IMAGE` (fallback `gemini-3.1-flash-image`): ilustracje redakcyjne, tła, infografiki-ilustracje, zdjęcia poglądowe (produkt, przedmiot, scena ogólna).
- **Twarda reguła:** jeśli `brief.is_real_event` lub `brief.real_people` niepuste, generator odmawia trybu fotorealistycznego i proponuje styl ilustracyjny (rysunek, kolaż, grafika) albo Tor A. Żadnych syntetycznych „zdjęć reporterskich” prawdziwych osób i zdarzeń (wycofaj z projektu założenie „Consistent Face / InstantID” ze starej specyfikacji).
- Każdy wygenerowany obraz: `ai_generated=True`, `prompt_provenance`, IPTC `DigitalSourceType = trainedAlgorithmicMedia`, automatyczny dopisek w podpisie „Ilustracja wygenerowana przez AI”.
- Prompt budowany z briefu + DNA (paleta, styl tytułu) + proporcji slotu; generuj 3–4 warianty, oceniaj je tym samym krytykiem co Tor A.

### 8.5 Inteligentny kadr
- Detekcja twarzy (`mediapipe` lub OpenCV DNN) + mapa istotności (OpenCV saliency) + `crop_suggestion` z Gemini → `focal_point` i kadr dopasowany do proporcji slotu.
- Kontrola rozdzielczości: efektywne DPI po kadrze ≥ `dna.photo_rules.min_dpi`; jeśli nie — solver zmniejsza slot albo proponuje inne zdjęcie (już częściowo jest — rozszerz o kadr).

---

## 9. MODUŁ G — PRAWDZIWE SZPAROWANIE

- `engine/segmentation.py`: lokalny model wycinania tła — `rembg` z modelem `birefnet-general` (lub `birefnet-portrait` dla ludzi, `isnet-general-use` jako lżejszy), uruchamiany przez ONNX Runtime (CPU, opcjonalnie CoreML na macOS). Dopracowanie krawędzi: alpha matting w `rembg` dla włosów. Możliwość podpięcia zewnętrznej usługi wycinania tła przez panel 2.3 (wbudowany adapter lub własne API).
- Opcjonalnie Gemini jako wskazówka obiektu: `box_2d` głównego obiektu z briefu („osoba na pierwszym planie”), przekazywany do segmentacji jako kadr wejściowy — nie jako źródło maski.
- Endpoint `POST /assets/{id}/cutout` → zapisuje maskę PNG jako osobny asset (`alpha_mask_url`), zwraca kontur. `auto_cutout=true` przy uploadzie wywołuje segmentację dla JPG i PNG (nie tylko PNG z alfą).
- **Kontur:** przepisz `extract_alpha_contour()` na OpenCV `findContours` (`RETR_CCOMP`, z otworami), wybór głównej składowej + opcja „wszystkie składowe > X% powierzchni”, upraszczanie `approxPolyDP`/RDP w mm, odsunięcie `shapely.buffer(offset_mm, join_style=round)`. Usuń `offset_contour_polygon()` oparte na centroidzie i fallback z wymyśloną sylwetką.
- Jakość maski: metryka (np. udział pikseli półprzezroczystych na krawędzi, liczba składowych) + ocena Gemini na podglądzie maski (JSON: `clean|minor_issues|unusable` + opis). `unusable` → zdjęcie zostaje w kadrze prostokątnym.
- **UI:** podgląd maski na szachownicy, pędzel dodaj/usuń, suwak progu, ponowne liczenie konturu.
- Produkcja: ścieżka obcinająca w IDML i `clip-path`/`shape-outside` w HTML z tego samego konturu; transgresja „postać wychodzi poza ramę / nachodzi na tytuł” korzysta z realnej maski.

---

## 10. MODUŁ H — KRYTYK WIZUALNY I MODUŁ I — SANACJA KORPUSU

### 10.1 Krytyk wizualny
- Render kandydata do PNG (Playwright/Chromium z istniejącego HTML lub z PDF przez `pdftoppm`).
- `GeminiVisionCritic.score_page(png, page_plan, dna)` (TEXT_PRO): JSON `{hierarchy_clear, single_dominant, eye_path, photo_headline_match, masthead_balance, dead_zones[], crowding[], typographic_issues[], score 0-1, top_3_fixes[]}`.
- Wynik wchodzi do **miękkiego** rankingu (waga konfigurowalna) i do raportu kandydata; nie zastępuje twardej bramki. Cache po hashu renderu. Uruchamiaj tylko dla kandydatów, którzy przeszli bramkę (koszt).

### 10.2 Sanacja korpusu
- Skrypt `scripts/audit_corpus.py`: każda strona z `corpus/` → Gemini TEXT_FAST z obrazem: `{is_newspaper_or_magazine_page, page_zone_guess, title_matches_folder: yes|no|unknown, era, language, reason}`.
- Strony odrzucone → `corpus/_quarantine/` z raportem CSV (nie kasuj). Raport z realnymi liczbami: ile stron sprawdzono, ile odrzucono, per tytuł.
- Przebuduj `FEATURE_INDEX.json` tylko na stronach zaakceptowanych.
- Parser IDML Wukadki (`corpus/wukadka/`) → dokładna geometria (ramki, style, siatka) jako najwyżej ważone dane referencyjne dla DNA.

---

## 11. KRYTERIA AKCEPTACJI (testy obowiązkowe)

1. **7 tekstów na czołówce** (1 lead ~400 słów, 2 second ~250, 4 brief ~60): ≥ 3 kandydatów PASS w ≥ 3 architekturach, broadsheet i tabloid; każdy tekst na stronie dokładnie raz; brak tytułu w ramie węższej niż 2 szpalty.
2. **12 tekstów na stronie wewnętrznej** z rangami ustawionymi ręcznie: plan respektuje piny i rangi.
3. **Pętla tekstu**: lead 900 słów w slocie na 400 → wynik PASS przez skrót (draft) albo `jump_line`; w metadanych zapis zastosowanych kroków.
4. **Strażnik źródeł**: wariant z dopisaną liczbą, której nie ma w źródle, dostaje `unsupported` i nie da się go zatwierdzić bez decyzji redaktora.
5. **Tytuły pod szerokość**: wszystkie zwrócone warianty mieszczą się w zadanej liczbie linii według shapera.
6. **Szparowanie**: zdjęcie osoby z ręką odsuniętą od tułowia → kontur zawiera otwór/wklęsłość; offset nie przecina konturu; brak jakiejkolwiek sztucznej sylwetki w kodzie (test grep).
7. **Brak klucza Gemini** → endpointy AI zwracają 503 z powodem, UI pokazuje „AI niedostępne”, deterministyczny tryb offline działa i jest tak oznaczony.
8. **Generowanie obrazu dla tekstu o prawdziwym zdarzeniu z nazwiskami** → odmowa trybu fotorealistycznego + propozycja ilustracji/Toru A.
9. **Eksport**: PDF i IDML z nowymi modułami (brief, pullquote, infobox, jump, masthead) otwierają się bez błędów; IDML zawiera wątkowane ramki i ścieżki obcinające z realnych masek.
10. **Ustawienia integracji**: dodanie klucza w panelu → maska w API, sekret zaszyfrowany w bazie (test odczytu surowej kolumny), „Testuj połączenie” wykonuje realne zapytanie; zmiana routingu `headline_variants` na inny model jest widoczna w provenance kolejnego wyniku; wyłączenie Gemini przełącza zadania na skonfigurowany fallback albo daje jawny 503.
11. **Logo**: wgranie logo szerokiego i logo kwadratowego daje różne układy winiety (pozioma vs z uszami), wysokość winiety przyciągnięta do siatki, pole ochronne nienaruszone we wszystkich kandydatach, logo wektorowe w PDF i jako placed graphic w IDML; kolory z logo pojawiają się jako propozycja palety DNA (do akceptacji).
12. **Dowolne API**: dodanie w panelu własnego REST API (np. Openverse skonfigurowane ręcznie jako „własne API” z mapowaniem JSONPath) zwraca zdjęcia w Torze A identyczne jak adapter wbudowany; import OpenAPI pokazuje listę operacji; zapytanie do adresu prywatnego w trybie chmurowym jest zablokowane.
13. Istniejące testy `backend/tests/` pozostają zielone (albo zmiana jest uzasadniona w CHANGELOG).

---

## 12. KOLEJNOŚĆ PRACY

1. **Etap 1:** infrastruktura Gemini i panel ustawień integracji z konektorem dowolnego API (sekcja 2, w tym 2.3) + Moduł A (plan, rangi, packer, naprawa duplikatów) + Moduł L (logo/winieta) + Moduł B + Moduł C. Kryteria 1–3, 7, 10, 11, 12.
2. **Etap 2:** Moduł D (redaktor + strażnik) + Moduł E (shaper). Kryteria 4–5.
3. **Etap 3:** Moduł G (szparowanie). Kryterium 6.
4. **Etap 4:** Moduł F (fotoedycja). Kryterium 8.
5. **Etap 5:** Moduł H + sanacja korpusu (I). Kryteria 9, 13.

**Wykonanie ciągłe:** przechodź od etapu 1 do etapu 5 bez zatrzymywania się i bez pytań. Na końcu każdego etapu (bez przerwy w pracy):
- uruchom pełny zestaw testów; jeśli coś pada — napraw i dopiero wtedy idź dalej (maks. kilka prób na problem; jeśli nadal pada — wpis do `docs/BLOCKERS_ETAP2.md` i kontynuuj),
- dopisz do `docs/CHANGELOG_ETAP2.md` realne wyniki pomiarów (liczby kandydatów, czasy, zużycie tokenów z `ai_calls`) i listę rzeczy niezrobionych,
- zrób commit z opisem etapu (jeśli katalog nie jest repozytorium git — najpierw `git init`; sprawdź, że `.env*` z sekretami jest ignorowany).

Po zakończeniu etapu 5 przygotuj `docs/RAPORT_KONCOWY_ETAP2.md`: status każdego z 13 kryteriów akceptacji (PASS/FAIL + dowód: nazwa testu i wynik), lista blokerów z tym, co trzeba dostarczyć, instrukcja uruchomienia całości lokalnie. Nie zgłaszaj funkcji jako działającej, jeśli nie ma testu, który to pokazuje. Dopiero wtedy zakończ pracę.
