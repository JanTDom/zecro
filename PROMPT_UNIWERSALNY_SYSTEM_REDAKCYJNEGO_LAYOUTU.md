# PROMPT: UNIWERSALNY SYSTEM AI DO TWORZENIA AUTORSKICH LAYOUTÓW PRASOWYCH Z TREŚCIĄ I DRUKIEM

Wklej ten prompt do agenta budującego system. Traktuj istniejące `SKILL.md`,
`SKILL.en.md`, `CODEX_SPEC.md`, kontrakty JSON oraz instrukcje repozytorium jako
warstwę bazową. Rozszerz system o pełny przepływ redakcyjny: od briefu i źródeł,
przez planowanie tekstu na stronie, pisanie i weryfikację AI, po skład,
preflight i pliki gotowe do druku. Nie usuwaj istniejących funkcji generatora
layoutu, krytyka, DNA tytułu, nowości, szparowania, oblewania tekstem ani eksportu
IDML/PDF; zintegruj je z poniższymi modułami.

## ROLA I CEL

Jesteś zespołem budującym produkcyjny **Editorial Layout Studio** — system,
który potrafi tworzyć całe autorskie strony gazet, magazynów i wydań cyfrowych
wraz z tekstem, zdjęciami, infografikami i elementami redakcyjnymi. System ma
generować wiele nowych wariantów, oceniać je, prowadzić człowieka przez decyzje
redakcyjne i dostarczać powtarzalny artefakt do DTP oraz drukarni.

Najważniejsza zasada pozostaje bez zmian:

```text
źródła + brief → plan numeru → plan tekstu → AI writing → copyfit
→ graf treści → generator geometrii → krytyk → renderer → preflight → druk
```

Generator treści, generator geometrii, krytyk i renderer muszą być osobnymi
modułami połączonymi kontraktami danych. Nie buduj jednego nieprzejrzystego
modelu „prompt → obraz strony”. Strona ma pozostać edytowalna, wyjaśnialna,
wersjonowana i odtwarzalna.

## ZASADY NIEPODLEGAJĄCE NEGOCJACJI

1. **Generator i krytyk są rozdzielone.** Generator eksploruje przestrzeń treści
   i układów, a krytyk odrzuca naruszenia twardych więzów i rankinguje resztę.
2. **DNA tytułu jest danymi**, a nie sztywnym szablonem. Zawiera również głos
   redakcyjny, reguły długości tekstu, język, ton, hierarchię i reguły foto.
3. **Graf sceny i graf treści są wersjonowanym kontraktem.** Renderer nie może
   odtwarzać strony z bitmapy ani zmieniać geometrii bez zapisu zmiany.
4. **Twarde więzy są bramką `PASS/FAIL`.** Czytelność, faktyczność, kompletność,
   overflow, prepress i prawa do zasobów nie mogą być ukryte w miękkim score.
5. **AI nie dopisuje niepotwierdzonych faktów.** Każda liczba, data, nazwa,
   teza i cytat ma mapowanie do źródła albo jawny status wymagający redaktora.
6. **Zablokowany tekst nie jest nadpisywany.** Layout ma dostosować się do treści,
   a odblokowanie jest świadomą decyzją człowieka.
7. **Nowość i różnorodność są celami systemu.** Nie kopiuj stron z korpusu ani
   jednego optimum; utrzymuj bank dobrych, różnych rozwiązań.
8. **Ocena jest tania, produkcja precyzyjna.** SVG/HTML/CSS służą do eksploracji
   i VLM, a IDML/PDF/X do produkcji z tego samego grafu.
9. **Każdy wynik ma ślad pochodzenia.** Zapisuj źródła, wersje, model, prompt,
   seed, parametry, decyzje człowieka, profil druku i raport preflight.

## 1. WARSTWA PROJEKTÓW, WYDAŃ I MATERIAŁÓW

Wprowadź następujące obiekty, każdy z identyfikatorem, statusem, wersją,
`created_at`, `updated_at` i historią zmian:

- `Project` — tytuł, właściciel, języki, formaty, DNA wizualne i redakcyjne,
  korpus, model gustu oraz profile produkcyjne.
- `Issue` — numer/wydanie, data publikacji, deadline, liczba stron, sekcje,
  kolejność, format, drukarnia, profil kolorystyczny i status produkcji.
- `IssuePlan` / `FlatPlan` — mapa całego numeru: `page_number`, `page_role`
  (`front`, `inside`, `spread`, `back`), `section`, `story_refs`, `asset_refs`,
  `spread_ref`, `ad_slots`, `reserved_house_ads`, `masthead`, `folio`,
  `continuation_links` oraz budżety powierzchni.
- `Assignment` / `EditorialBrief` — temat, kąt, odbiorca, język, ton, deadline,
  priorytet, fakty obowiązkowe, ograniczenia prawne, słowa zakazane i wymagane
  materiały.
- `Source` — plik, URL, depesza, CMS, DOCX/PDF, OCR, transkrypcja, arkusz lub
  wypowiedź; przechowuj autora, datę pozyskania, licencję, embargo, język,
  wiarygodność, hash i fragmenty źródłowe.
- `Asset` — zdjęcie, ilustracja, wykres, logo lub reklama z prawami/licencją,
  kredytem, alt-textem, profilem ICC, DPI, focal pointem i statusem użycia.
- `Story` / `ContentPackage` — kompletny pakiet artykułu i jego elementów.
- `TextPlan` — przydział tekstu do konkretnego slotu i ramki.
- `CopyVariant` — jedna, wersjonowana wersja językowa elementu.
- `GenerationRun`, `PreferenceSignal`, `TasteModel` — generacje, wybory A/B,
  poprawki i model gustu, zgodnie z istniejącym kanonem.
- `ExportArtifact` / `PreflightReport` — pliki, manifesty, proofy, błędy i
  decyzje zatwierdzające.

## 2. PLANER WYDANIA I PLANOWANIE TEKSTU NA STRONIE

Zbuduj osobny **Editorial/Content Engine**, oddzielony od generatora geometrii.
Planer najpierw układa mapę numeru, a dopiero potem przydziela treści do stron.
Nie pozwalaj, aby wygenerowany tekst wypierał zarezerwowane miejsce na zdjęcie,
infografikę, reklamę, maszt, folio lub house ad.

Dla każdego elementu tekstowego utwórz `TextPlan` z polami:

```json
{
  "id": "tp-story-1-body-01",
  "story_ref": "story-1",
  "issue_ref": "issue-12",
  "page_ref": "page-04",
  "frame_ref": "frame-body-1",
  "role": "body",
  "flow_group": "story-1-thread",
  "target_words": 420,
  "min_words": 360,
  "max_words": 480,
  "target_chars": 2600,
  "target_lines": 48,
  "columns": 3,
  "priority": 0.9,
  "required": true,
  "keep_with_next": false,
  "widow_lines": 2,
  "orphan_lines": 2,
  "no_break_tokens": ["Jan", "Kowalski"],
  "overflow_policy": "shorten|alternate|continue|reflow|manual",
  "continuation_policy": "jump_if_needed",
  "max_tracking": 10,
  "max_leading_adjustment_pt": 0.5,
  "min_font_size_pt": 9.0,
  "locked": false,
  "approval": {"editorial": "pending", "fact_check": "pending"}
}
```

Planer musi:

- rozdzielać powierzchnię strony na tekst, fotografie, infografiki, reklamy,
  biel, elementy nawigacyjne i strefy bezpieczne;
- liczyć pojemność slotu po realnych parametrach fontu, szerokości łamu,
  leadingu, kerningu, dzieleniu wyrazów, oblewaniu i kształcie ramki;
- planować artykuły jedno- i wielostronicowe, rozkładówki, ramki kontynuacji,
  `Dalszy ciąg na s. ...` i `Dokończenie ze s. ...`;
- rozwiązywać przydział materiałów jako problem więzów/CP-SAT/knapsack z wagą
  redakcyjną `importance`, zamiast upychać elementy po kolei;
- pokazywać redaktorowi mapę numeru, budżet słów/wierszy na każdej stronie,
  rezerwy i konflikty zanim ruszy generowanie;
- wspierać świadome warianty: wersja gęsta, standardowa, oddechowa, plakatowa,
  z zachowaniem tych samych wymagań redakcyjnych.

## 3. AI WRITING I CONTENT STUDIO

Zbuduj wymienny adapter LLM obsługujący model lokalny i chmurowy. Model ma
pracować retrieval-grounded: korzysta wyłącznie z zatwierdzonych źródeł,
briefu, stylu redakcyjnego i jawnych założeń. Przy braku dowodu ma oznaczyć
lukę jako `unverified` albo poprosić o materiał; nie może wymyślić faktu,
cytatu, statystyki ani nazwiska.

Obsługiwane operacje:

- outline i struktura artykułu;
- draft z briefu i źródeł;
- trzy do ośmiu wariantów kickera, nagłówka i decku;
- lead, korpus, śródtytuły, byline, dateline i jump line;
- podpis zdjęcia z identyfikacją, akcją, miejscem/czasem, kontekstem i credit;
- pull quote, factbox, timeline, lista „key facts”, zajawka i teaser;
- `shorten_to_fit`, `expand`, `rewrite`, neutralizacja opinii, korekta językowa;
- zmiana tonu, rejestru, gatunku i poziomu czytelności;
- tłumaczenie i lokalizacja z zachowaniem nazw, jednostek i dat;
- wariant drukowany, web/mobile cut, newsletter, SEO i alt-text;
- continuation, czyli skrót i aktualizacja odsyłaczy po przeniesieniu historii.

Każdy wynik zwracaj jako strukturalny JSON, nie anonimowy akapit. Wymagaj
wariantów `micro`, `short`, `medium`, `long` i `exact_fit`, z `target_words`,
`target_chars`, `target_lines`, `claim_refs`, `source_refs`, `status` i pełną
proweniencją. Zachowuj sens, kolejność faktów, liczby, daty, jednostki i
dosłowne brzmienie cytatów. Stosuj polską mikrotypografię i reguły zecera
z `newspaper-editorial-copyediting`.

W kontekście modelu uwzględniaj: `editorial_voice`, `style_guide`, język,
lokalizację, odbiorcę, deadline, politykę prawną, słowa zakazane, wymagany
format, `target_length`, `source_refs`, `locked_passages` i wybraną wersję DNA.
Zapisuj: provider/model, wersję modelu, hash promptu, identyfikatory wejściowych
rewizji, temperaturę, `top_p`, seed, czas, koszt/tokeny, informację o użyciu AI
oraz późniejsze zmiany człowieka.

## 4. FAKTY, ŹRÓDŁA, PRAWA I AKCEPTACJA

Po każdej generacji wyodrębnij atomowe twierdzenia, daty, liczby, osoby, miejsca
i cytaty. Dla każdego zapisz `claim_id`, fragment dowodowy, źródło, timestamp,
confidence i status: `unverified`, `partially_verified`, `verified`,
`contradicted`, `needs_editor`. Wykonuj kontrolę konfliktów źródeł, jednostek,
sum, dateline, pisowni nazw i zgodności cytatu znak w znak.

Rozdziel statusy `fact_checked` i `editor_approved`. Do layoutu produkcyjnego
nie dopuszczaj tekstu z niezamkniętymi claimami, placeholderami, brakującym
creditem lub naruszoną licencją, chyba że redaktor jawnie włączy tryb roboczy.
Każdy fragment może być zaakceptowany, odrzucony, poprawiony, zablokowany lub
odblokowany. Zablokowanie fragmentu musi być respektowane przez każdą kolejną
regenerację i copyfitting.

## 5. COPYFITTING SPRZĘŻONY Z GENERATOREM LAYOUTU

Copyfitting jest osobnym silnikiem, który mierzy tekst w realnym rendererze.
Nie zastępuj go prostym liczeniem słów. Po każdym renderze zwracaj do Content
Engine: liczbę wierszy, głębokość, overflow w mm, wolne miejsce, pojemność
kolumn, efekty oblewania, błędy dzielenia, sieroty i bękarty.

Do pomiaru używaj rzeczywistego font shapera (np. HarfBuzz/Pango/Skia) z
kerningiem, ligaturami, językiem, fallbackiem glifów oraz algorytmem łamania
Knuth–Plass/Pyphen. Uwzględniaj baseline grid, `keep_with_next`, nazwiska i
daty jako `no_break_tokens`, minimalną szerokość łamu przy oblewaniu i reguły
locale. Szacowanie na podstawie średniej liczby słów na wiersz może służyć
wyłącznie jako szybki filtr przed dokładnym pomiarem.

Stosuj pętlę:

```text
TextPlan → warianty AI → tani render → pomiar fit/overflow
→ wybór wariantu lub kontrolowana redakcja → ponowny render → krytyk
```

Przy nadmiarze treści kolejność działań to: krótszy zatwierdzony wariant,
usunięcie powtórzeń i zdań niskiego priorytetu, skrót redaktorski z zachowaniem
claimów, podział na kontynuację, zmiana modułu/geometrii, a dopiero na końcu
ograniczona korekta stopnia, leadingu i trackingu w granicach DNA. Przy braku
treści użyj dłuższego wariantu, decku, śródtytułu, pull quote, factboxu lub
modułu uzupełniającego ze źródłem. Nie dopisuj faktów dla wypełnienia dziury.

Copyfit przechodzi tylko wtedy, gdy nie ma overflow, obciętych znaków,
niekontrolowanych sierot/bękartów, zbyt wąskich łamów, uszkodzonych podpisów,
nieaktualnych odsyłaczy ani fontu poniżej minimum. Każda zmiana tekstu jest
diffem z powodem, autorem i rewizją. `exact_fit` może stosować micro-editing,
ale nigdy po cichu.

## 6. ROZSZERZENIE GRAFU SCENY

Nie przechowuj tekstu jako przypadkowego stringa. Rozszerz elementy grafu sceny
o `story_ref`, `content_revision_ref`, `text_plan_ref`, `source_refs`, `fit_status`,
`locked`, `approval_status`, `flow_group`, `continuation_ref` i `claim_refs`.
Rozszerz `page` o `issue_ref`, `page_number`, `page_role`, `spread_ref` i
`production_profile_ref`. Przechowuj osobno:

- `Story` — znaczenie redakcyjne, brief, claimy, źródła i aktywne rewizje;
- `TextPlan` — wymagania powierzchniowe slotu;
- `CopyVariant` — konkretny tekst z proweniencją;
- `TextFitResult` — pomiar i wynik `PASS/FAIL`;
- `SceneGraph` — wyłącznie zatwierdzony wybór treści oraz geometria.

Jeden `story_id`, `claim_id` i `scene_id` musi przechodzić przez UI, graf sceny,
IDML, PDF, raport preflight i manifest produkcyjny.

## 7. MODUŁY UŻYTKOWE DLA REDAKTORA I ART DIRECTORA

Zaprojektuj co najmniej następujące widoki:

1. **Brief i intake** — źródła, assignment, prawa, deadline, fakty i materiały.
2. **Mapa numeru** — flat plan, strony, rozkładówki, sloty, rezerwy i kontynuacje.
3. **Content Studio** — warianty tekstu, źródła, claimy, diff, fact-check i lock.
4. **Planer tekstu** — budżety słów/wierszy/znaków i przewidywany fit przed składem.
5. **Generator** — liczba wariantów, seed, budżet napięcia, styl i ograniczenia.
6. **Galeria A/B/C** — miniatury, score krytyka, nowość, fit, tekst i uzasadnienie.
7. **Edytor grafu sceny** — drag/resize, text wrap, maski, undo/redo i blokady.
8. **Copyfit inspector** — overflow, wolne miejsce, przyczyna i proponowane akcje.
9. **Preflight** — błędy z numerem strony, `scene_id`, wartością i progiem.
10. **Eksport i proof** — PDF/X, IDML, pakiet linków, proof, manifest i akceptacja.
11. **Historia** — porównanie rewizji, odtworzenie wydania i log decyzji.

Zbieraj osobno preferencje dla jakości tekstu, jakości layoutu i ich połączenia;
nie ucz modelu gustu na materiałach odrzuconych przez fact-check.

## 8. WORKFLOW, ROLE I WERSJONOWANIE

Wprowadź role i uprawnienia co najmniej dla: autora, reportera, asystenta AI,
redaktora prowadzącego, fact-checkera, copy editora, fotoedytora, grafika/
dyrektora artystycznego, prepressu i osoby zatwierdzającej druk. Oddziel prawa
do treści, źródeł, geometrii, DNA tytułu, modelu gustu i eksportu.

Stany treści prowadź niezależnie od stanu strony i eksportu:

```text
brief → research → draft → ai_suggestions → editorial_review → fact_check
→ copydesk → approved_for_layout → placed → proof → approved_for_print
→ published → archived
```

Dodaj zadania, terminy, komentarze, wzmianki, checklisty, blokady i bramki
akceptacji. Każdy `Story`, `TextPlan`, `CopyVariant`, `SceneGraph`, `TitleDNA`,
`TasteModel` i `ExportArtifact` musi mieć numer rewizji, rodzica, autora,
timestamp, hash treści, status, diff, decyzje i podpisy. Historia jest
niemutowalnym logiem zdarzeń: kto, co, kiedy, dlaczego i z jakiego wejścia.

Obsłuż undo/redo, snapshoty, branche, merge z wykrywaniem konfliktów, restore
i porównanie rewizji tekstowych oraz geometrycznych. Zapisuj wersje modelu,
fontów, silnika łamania, assetów, promptu, seeda i snapshotu wejściowego, aby
dało się odtworzyć dowolną generację i dokładnie zatwierdzony numer. Nie
nadpisuj historii i nie usuwaj śladu po automatycznej naprawie.

## 9. ASSETY, KOMPONENTY I WIELOFORMATOWE WYJŚCIA

Zbuduj bibliotekę assetów z wersjami i relacjami do historii. `Asset` powinien
przechowywać `sha256`, URI/storage, dostawcę, licencję, właściciela praw,
zakres użycia, datę wygaśnięcia, credit line, zgodę na wizerunek/model release,
oznaczenie `ai_generated`, prompt/provenance, alt-text, caption, focal point,
crop/mask, wymiary, DPI, kanały, profil koloru i powiązane historie. Przed
eksportem wykrywaj brakujące linki, wygasłe licencje, brak credits i konflikt
embarga. Materiały agencyjne, stockowe i generowane przez AI prowadź osobnymi
ścieżkami i zachowuj oznaczenie pochodzenia.

Dodaj wersjonowaną `ComponentLibrary` dla elementów takich jak: factbox, Q&A,
timeline, lista, tabela, wykres, przepis, promo, reklama, legal, pull quote,
indeks i moduł „key facts”. Komponent opisuje rolę, styl, minimalną pojemność,
zachowanie na rozkładówce, alternatywny wariant tekstowy, źródło danych,
caption, credit i alt-text. Tabele i wykresy przyjmuj z CSV/JSON, generuj jako
wektor, powiąż ze źródłem i poddaj temu samemu SceneGraph oraz preflightowi.

Z jednego zatwierdzonego grafu generuj także web/mobile cut, newsletter,
archiwum strukturalne i wersję dostępnościową. Wspólny `story_id`, `claim_id`,
`asset_id` i `scene_id` musi przetrwać wszystkie kanały; kanał może mieć własny
wariant długości, ale nie może zmienić zatwierdzonych faktów bez nowej rewizji.

## 10. MODUŁ PRODUKCJI, PREPRESS I DRUKU

Zbuduj osobną, deterministyczną warstwę produkcyjną. Wprowadź wersjonowany
`ProductionProfile` per tytuł, papier i drukarnia, obejmujący co najmniej:

```json
{
  "output_intent": "ISOnewspaper26v4.icc",
  "pdf_standard": "PDF/X-4:2010",
  "color_space": "CMYK",
  "tac_limit_percent": 240,
  "bleed_mm": 3,
  "safe_margin_mm": 8,
  "gripper_margin_mm": 12,
  "trim_box_mm": [280, 430],
  "paper": "newsprint_coldset",
  "spot_colors": [],
  "imposition": {"scheme": "web_offset", "signature": 16, "creep_mm": 0}
}
```

Pipeline musi obsługiwać ICC/CMYK/DeviceLink, TAC/TIC z limitem profilu,
100% K dla drobnego tekstu, kontrolowany rich black dla dużych apl, overprint,
knockout, trapping, effective DPI, profile obrazów, maski alfa, przezroczystość,
fonty, glify, kerning, osadzanie fontów, boxy PDF (`trim`, `bleed`, `crop`,
`media`, `art`), spady, margines chwytaka, znaczniki drukarskie i slug.

Eksportuj co najmniej:

- IDML/InDesign z mapowaniem 1:1 grafu sceny, stylem, text threadingiem,
  linkami, warstwami, clipping paths, text wrap i stabilnym `scene_id`;
- PDF/X-4 z żywą przezroczystością, jeśli drukarnia ją akceptuje;
- PDF/X-1a jako wariant wymiany CMYK/spot ze spłaszczoną przezroczystością;
- PDF stron netto do archiwum;
- opcjonalny PDF impozycyjny z mapą składek, kolejnością, rewersem, creepem,
  gripperem i parametrami maszyny;
- soft proof, raport preflight, manifest zasobów, fontów i profili ICC.

Preflight jest bramką. `FAIL` obejmuje m.in. zły rozmiar/boxy, brak spadu,
RGB/Lab poza profilem, TAC ponad limitem, za niskie effective DPI, brakujące
fonty, overflow, uszkodzone linki, nieprawidłowy overprint/trapping, niedozwoloną
przezroczystość, złą liczbę stron, niezweryfikowane claimy i brak credits.
Raport ma status `PASS`, `WARN` albo `FAIL`, lokalizację strony i `scene_id`,
zmierzoną wartość, próg i możliwą naprawę. Tylko `PASS` może mieć status
„gotowe do druku”.

Automatyczne naprawy (np. konwersja ICC, redukcja TAC, dodanie spadu, naprawa
boxów) muszą być odwracalne, zapisane jako patch i ponownie sprawdzone. Nie
zmieniaj po cichu treści, geometrii ani hierarchii.

## 11. API, ADAPTERY I ODTWARZALNOŚĆ

Zdefiniuj kontrakty JSON Schema co najmniej dla:
`editorial_brief.schema.json`, `source.schema.json`, `story.schema.json`,
`text_plan.schema.json`, `copy_variant.schema.json`, `text_fit_result.schema.json`,
`production_profile.schema.json`, `preflight_report.schema.json` oraz istniejących
`scene_graph.schema.json` i `title_dna.schema.json`.

Dodaj adaptery z wymiennym interfejsem dla: LLM, embeddings/RAG, fact-checkera,
VLM krytyka, segmentacji zdjęć, renderera HTML/SVG, IDML, PDF/X, profili ICC,
hyphenation i font metrics. Każda generacja musi mieć seed i wersje wszystkich
adapterów, aby ten sam graf i profil dawały ten sam eksport.

Przydatne endpointy:

```text
POST /projects
POST /projects/{id}/issues
POST /issues/{id}/sources
POST /issues/{id}/briefs
POST /issues/{id}/plan
POST /stories/{id}/generate-variants
POST /stories/{id}/rewrite
POST /stories/{id}/shorten
POST /stories/{id}/translate
POST /stories/{id}/factcheck
POST /text-plans/{id}/fit
POST /issues/{id}/generate-layouts
POST /candidates/{id}/preferences
POST /candidates/{id}/preflight
POST /candidates/{id}/export
POST /exports/{id}/proof
POST /exports/{id}/package
POST /exports/{id}/impose
GET  /issues/{id}/manifest
```

Operacje OCR, importu, pisania, fact-checku, renderowania, copyfitu, preflightu
i eksportu uruchamiaj jako idempotentne joby w kolejce z postępem, anulowaniem,
retry, logiem błędów, cache i zdarzeniem po zakończeniu. Nie blokuj nimi żądania
HTTP i zapewnij bezpieczne wznowienie po awarii.

## 12. METRYKI I KRYTERIA AKCEPTACJI

Raportuj osobno: `factuality_rate`, odsetek claimów z dowodem, `copyfit_pass_rate`,
overset/underset, liczbę ręcznych zmian, czas do akceptacji, human preference
win-rate, validity rate, diversity, novelty, production integrity i powtarzalność
eksportu.

System jest gotowy dopiero, gdy użytkownik może:

1. utworzyć projekt i wydanie, wprowadzić źródła oraz brief;
2. zobaczyć mapę numeru i budżet tekstu przed generowaniem layoutu;
3. wygenerować kilka wariantów nagłówka, leadu, korpusu, podpisu i factboxu;
4. prześledzić claim → źródło → fragment dowodowy → decyzję redaktora;
5. dopasować tekst do realnej ramki bez ukrytego overflowu;
6. wygenerować co najmniej osiem różnych, nowych kandydatów layoutu;
7. wybrać wariant i ręcznie poprawić graf sceny bez utraty proweniencji;
8. otrzymać PDF/X, IDML, proof i raport `PASS/WARN/FAIL`;
9. odtworzyć dokładnie zatwierdzoną wersję numeru z manifestu;
10. wykazać, że zablokowany tekst, prawa, credits i odsyłacze nie zostały
    zmienione przez późniejsze generowanie.

## 13. KOLEJNOŚĆ IMPLEMENTACJI

Buduj etapami, po każdym etapie uruchamiając działający, testowalny fragment:

- **M0:** kontrakty danych, projekty, wydania, historia i health check;
- **M1:** intake źródeł, brief, ContentPackage, claimy i mapa numeru;
- **M2:** TextPlan, pomiar pojemności, copyfit oraz polska mikrotypografia;
- **M3:** AI writing z wariantami, proweniencją i bramką akceptacji;
- **M4:** solver/generator grafu sceny, renderer SVG/HTML i galeria;
- **M5:** krytyk, nowość, różnorodność, pętla gustu i edytor grafu;
- **M6:** IDML, PDF/X, ProductionProfile, proof i twardy preflight;
- **M7:** impozycja, paczka drukarska, odtwarzalność i test end-to-end.

Nie uznawaj funkcji za gotową, jeśli pokazuje jedynie wizualną makietę bez
źródeł, planu tekstu, pomiaru fitu, wersjonowania i raportu produkcyjnego.
