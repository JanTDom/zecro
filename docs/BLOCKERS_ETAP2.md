# Blockery i ograniczenia — Etap 2

## Zależności opcjonalne nieobecne w środowisku testowym

Następujące moduły nie są zainstalowane w bieżącym środowisku: `google.genai`, `cv2`, `shapely`, `rembg`, `uharfbuzz`, `fontTools`, `pyphen`. Kod nie udaje ich działania:

- Gemini, gdy brakuje SDK/klucza, zwraca `unavailable`, a `/health/ai` HTTP 503.
- Shaper bez pliku fontu zwraca `status=estimate` z ostrzeżeniem.
- Segmentacja bez `rembg` zwraca `unavailable`/503.
- Kontur bez OpenCV lub bez maski jest pusty; solver używa kadru prostokątnego.
- Offset bez Shapely zachowuje zmierzony kontur i oznacza ograniczenie zamiast wymyślać kształt.

Do pełnej weryfikacji produkcyjnej trzeba zainstalować zależności z `backend/requirements.txt`, dostarczyć `GEMINI_API_KEY` oraz pliki fontów DNA. Testy wywołujące zewnętrzne AI powinny być uruchamiane osobno jako `@pytest.mark.live_ai`.

## Funkcje wymagające dalszej integracji

- Semantyczne wyszukiwanie zdjęć, krytyk VLM, import OpenAPI z mapowaniem odpowiedzi i adaptery agencji mają kontrakty, rejestr i statusy konfiguracji, ale nie są raportowane jako działające bez realnego dostawcy i testu połączenia.
- UI planera ma edycję listy/rang i podgląd siatki; pełne przeciąganie i resize slotów oraz trzy propozycje Gemini wymagają podłączenia live modelu.
- Profil logo ma analizę deterministyczną i upload; propozycje fontów/palety z Gemini oraz pełny preflight CMYK/TAC wymagają usług produkcyjnych.

## Bezpieczeństwo

Sekrety `.env.local` i runtime SQLite są ignorowane przez Git. Nie zapisano kluczy w kodzie, fixture'ach, logach ani dokumentacji.

