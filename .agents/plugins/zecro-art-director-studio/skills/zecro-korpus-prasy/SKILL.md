---
name: zecro-korpus-prasy
description: Korpus pomiarów prasy Zecro (14 315 stron, 800 tytułów, 39 krajów) i normy gatunków. Używaj przy rozbudowie korpusu, ponownych pomiarach, liczeniu norm i archetypów oraz przy podpinaniu norm do bramki i promptów.
---

# Korpus prasy

- Skrypty: `backend/scripts/press_corpus/` — `crawl_ff.py` (pierwsze strony Freedom Forum), `crawl_ia.py`/`ia_select*.py` (pełne wydania z archive.org), `measure.py` (przyrząd pomiarowy, wersja 2 łączy słowa w wiersze), `analyze.py` (normy, archetypy, pierwsza strona vs środek), `write_knowledge.py` (raport po polsku). Opis: `README.md` w tym katalogu.
- Dane: `backend/corpus/press/*.jsonl` (wyłączone z wdrożenia przez `.vercelignore`). Wyniki: `backend/app/knowledge/press_norms.json`, `press_norms.md`, `press_archetypes.json`.
- Silnik: `backend/app/engine/press_norms.py` — `scene_metrics`, `norm_report`, `norm_distance`, `GENRE_KINDS`, `KEY_METRICS`.
- Klucz Freedom Forum wyłącznie z env `FF_APPSYNC_KEY`. Nie zapisuj go w kodzie ani w logach.
- Liczby z korpusu podawaj tylko z plików wynikowych. Gdy czegoś nie zmierzono, napisz to wprost; nie szacuj bez oznaczenia założeń.
- Pomiary kolumn, interlinii i długości wiersza są wiarygodne tylko z `measure_version == 2`; starsze rekordy mają te pola wyzerowane w `analyze.py`.
