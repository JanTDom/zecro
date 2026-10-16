Kontynuujesz projekt Zecro — generator stron gazet i magazynów, który ma pracować jak profesjonalny grafik łamiący. Repozytorium: /Users/macbookpro/PROJEKTY/LAYOUT (gałąź main).

Zanim cokolwiek zmienisz:
1. Przeczytaj docs/ANTIGRAVITY_INSTRUKCJE.md w całości oraz część VI raportu docs/RAPORT_CLAUDE_2026-10-15.md.
2. Wczytaj skille z .agents/skills/: zecro-okladka-ramowa, zecro-petla-ai, zecro-korpus-prasy.
3. Uruchom testy (.venv/bin/python -m pytest -q backend/tests) i podgląd domyślnej okładki (cd backend && ZECRO_DATA_DIR=$HOME/zdata ../.venv/bin/python -m scripts.wukadka_demo --framed --tag start --genes '{}'). Potwierdź, że wynik zgadza się ze stanem opisanym w instrukcjach (186 testów przechodzi, okładka: GATE PASS). Jeśli się nie zgadza, najpierw ustal dlaczego.

Potem realizuj zadania z sekcji 7 instrukcji po kolei, zaczynając od zadania 1 (pętla AI bez oscylacji). Dla każdego zadania:
- przedstaw krótki plan (3–5 kroków), potem wykonaj;
- naprawiaj zasadę ogólną (silnik, solver, reguła bramki), a nie jedną okładkę;
- po zmianie wygeneruj podgląd co najmniej trzech wariantów, obejrzyj PNG w zbliżeniu (styk zdjęcia z belką, górna krawędź kolumny, okno tytułu, moduł dolny) i uruchom testy;
- dopisz test i krótką notatkę do raportu w docs/;
- spełnij definicję „gotowe” z sekcji 8.

Twarde zasady:
- Nie odczytuj, nie wypisuj i nie zapisuj sekretów (klucze są w .env.local i w Vercel; Freedom Forum tylko przez env FF_APPSYNC_KEY).
- Nie wykonuj git reset, git checkout ., czyszczenia ani automatycznego formatowania całego repozytorium. Commit i push tylko na moją prośbę.
- Nie obniżaj progów bramki i nie zmyślaj liczb; czego nie zmierzono, nazwij wprost.
- Interfejs i dokumentacja po polsku. Wdrożenie robię sam.

Po każdym zadaniu raportuj: co zmieniłeś (pliki), wynik testów, wynik bramki dla wariantów, ścieżki do PNG oraz co zostało otwarte.
