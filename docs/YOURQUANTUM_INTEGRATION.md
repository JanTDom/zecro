# Integracja Zecro z YourQuantum

Zecro używa YourQuantum jako opcjonalnego, zewnętrznego solvera małego
problemu binarnego. Solver wybiera zestaw obsługiwanych transgresji strony
(`diagonal-break`, `extreme-scale`, `cutout-wrap`) przy limicie
`TitleDNA.page_energy_budget`.

## Konfiguracja

Ustaw po stronie backendu:

```dotenv
YOURQUANTUM_API_URL=https://yourquantum.pl
YOURQUANTUM_API_KEY=<token lub klucz YourQuantum>
YOURQUANTUM_TIMEOUT_S=12
```

Przy braku URL albo klucza integracja ma stan `disabled` i generator działa
lokalnie bez żądań sieciowych. Klucz nie trafia do frontendu.

## Przepływ

```text
Title DNA + materiał
        │
        ▼
adapter YourQuantum (jedno wywołanie na run)
        │  wybór binarny + koszt energii
        ▼
LayoutGenome (lokalne współrzędne i wariacje)
        │
        ▼
LayoutCritic: twarda bramka, copyfit, nowość i prepress
        │
        ▼
SVG / HTML / PDF / IDML
```

YourQuantum nie dostaje tekstu artykułu, obrazów ani grafiki sceny. Nie
ustala współrzędnych, typografii, szparowania, oblewania ani wyniku krytyka.
Jego wynik jest zapisywany w `scene_graph.metadata.yourquantum` oraz w
`GenerationRun.stats.yourquantum` razem z użytym solverem i paszportem SHA-256.

## Uczciwość wyniku

`solver=auto` może wybrać klasyczny CP-SAT. Symulator QAOA w YourQuantum działa
na CPU, a adapter fizycznego QPU jest obecnie odłączonym stubem. Paszport
potwierdza wynik modelu binarnego YourQuantum; nie zastępuje lokalnej bramki
geometrii, czytelności i produkcji.
