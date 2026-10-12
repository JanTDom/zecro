# Decyzje implementacyjne

## 2026-10-12 — Model wydania jako adapter

**Kontekst:** repozytorium ma działające kontrakty `IssuePlan` i `PagePlan`, a
projekt wymaga pełnego wydania z reklamami, shortami i poczekalnią.

**Wybór:** dodać `EditorialModel`/`Edition` jako warstwę kompatybilności w
`backend/app/engine/editorial_model.py` i pozostawić istniejące klasy bez
usuwania ani zmiany semantyki. Nowe endpointy są pod prefiksem
`/editorial-model`.

**Odrzucone alternatywy:** przebudowanie `IssuePlan` od zera (ryzyko utraty
starych projektów) oraz zapis bez wersjonowania (brak bezpiecznej migracji).

**Cofnięcie:** usunąć router `editorial_model` z `main.py` oraz nowe moduły;
istniejące API nie zależy od nich.

## 2026-10-12 — Deterministyczny fallback copyfitu

**Kontekst:** usługa AI może być niedostępna, a reguła zakazuje dopisywania
faktów bez materiału źródłowego.

**Wybór:** skrót działa wyłącznie na źródłowym tekście, zachowuje całe słowa i
oznacza nadwyżkę do decyzji redaktora. Walidator encji sprawdza liczby i nazwy.

**Odrzucone alternatywy:** ciche dopisywanie tekstu generowanego przez model
oraz zmiana geometrii przez copyfit.

## 2026-10-12 — Reklamy są zawsze zablokowane

Reklama ma `locked=true`, a walidacja kolizji odbywa się przed generacją
geometrii. Pozwala to zachować istniejący generator i zgłaszać konflikty w UI.
