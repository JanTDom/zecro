# Korpus prasy — pomiar konstrukcji stron

Jeden przyrząd (`measure.py`) mierzy każdą stronę PDF (elektroniczną lub skan z OCR):
format, łamy (liczba, podziałka, rowek), stopień i interlinia tekstu, długość wiersza,
stopień tytułu największego i skoki hierarchii, liczba bloków tytułowych (tematów),
udział tekstu / grafiki / papieru (białych pól), największa plama (dominanta), nasycenie
koloru, liczba krojów, linie i apla (wektorowo). Treść nie jest przechowywana.

Źródła:
- `ff_list.py` + `crawl_ff.py` — pierwsze strony dzienników z galerii Freedom Forum
  (~520 tytułów, 40 krajów) z kilku dat (dni powszednie, niedziele, rok wstecz).
- `ia_select.py`, `ia_select2.py` + `crawl_ia.py` — pełne wydania z archive.org (wszystkie
  strony, do 48 na wydanie): polskie programy TV i gazety, tabloidy (UK, USA), bezpłatne
  dzienniki Metro, dzienniki regionalne (pełne wydania), lokalne gazety USA, TV Guide,
  newsmagazyny, magazyny konsumenckie.
- własne wydania tytułu (Wukadka NR20–22, wszystkie strony).

`analyze.py` → `press_norms.json` (rozkłady p10–p90 per typ × rola strony, formaty,
regiony, pierwsza vs środek) i `press_archetypes.json` (archetypy pierwszych stron
wykryte klasteryzacją). Silnik używa ich w `app/engine/press_norms.py`.
