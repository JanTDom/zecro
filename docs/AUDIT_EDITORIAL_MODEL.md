# Audyt modelu redakcyjnego

Data audytu: 2026-10-12

## Stan zastany

- Backend: FastAPI + Pydantic 2, z SQLite/Supabase adapterem persystencji.
- Geometria: `SceneGraph`, generator deterministyczny i ewolucyjny, solver
  siatki, katalog transgresji z budżetem energii.
- Krytyka: `backend/app/engine/critic.py` ma bramkę twardych więzów oraz
  osobną ocenę heurystyczną, a nowość jest sprawdzana względem korpusu.
- Treść: `Story`, `TextPlan`, `CopyVariant`, source guard i copyfit są już
  rozdzielone od geometrii. Istnieje provider registry z Gemini jako domyślnym
  dostawcą oraz konfiguracją własnych providerów w panelu ustawień.
- Produkcja: wspólny graf sceny zasila SVG/HTML/PDF/IDML. Operacje zdjęciowe
  zachowują focal point, maskę, kontur i text wrap.
- UI: istnieją widoki generatora, porównania, DNA, Copy Studio i eksportu.

## Braki i rozwiązanie

| Obszar | Brak | Rozwiązanie |
|---|---|---|
| Wydanie | plan był głównie jedno-stronicowy | `engine/editorial_model.py` dodaje wersjonowane `Edition`, typy stron, rozkładówkę i paginację |
| Reklamy | brak jednolitego katalogu i walidacji kolizji | katalog modułów, reklama z `locked`, importer CSV i bramka advertorial/konkurencji/kontekstu |
| Copyfit | brak kontraktu obejmującego drabinkę nadwyżki i dziury | `run_copyfit_ladder`, delta oraz source-bound guard |
| Shorty | brak bufora strony i poczekalni | `ShortsBlock`, `ShortItem`, `WaitingRoomItem` |
| Migracja | stare materiały nie miały wydania | czysta migracja z wersji 1 do 2, zachowująca pojedynczą stronę jako plan kompatybilny |
| Kontrakt | brak JSON Schema dla całości | `schemas/editorial_model.schema.json` |

## Zgodność z zasadami projektu

Generator i krytyk są rozdzielone przez modele i funkcje bez współdzielenia
mutowalnego stanu. DNA zawiera katalog reklam, budżety napięcia i reguły
kolizji jako dane. Twarde więzy walidują wynik jako PASS/FAIL; ranking
heurystyczny pozostaje w dotychczasowym krytyku. Nowość i różnorodność pozostają
w istniejącym korpusie/ewolucji. Render oceny i produkcja używają tego samego
Scene Graph.

## Ograniczenia audytu

Istniejący frontend nie ma jeszcze pełnego widoku flatplanu reklam. Backend
udostępnia stabilne endpointy, które można podłączyć do obecnego panelu bez
zmiany jego kontraktu. Brak konfiguracji klucza AI nie blokuje deterministycznej
ścieżki i jest raportowany przez istniejący provider registry.
