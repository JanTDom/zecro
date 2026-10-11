# Ograniczenia — Etap 2

- **BiRefNet** (`birefnet-general-lite`, domyślny model segmentacji) potrzebuje ponad 3 GB RAM. W środowisku 3 GB działa `isnet-general-use` (`ZECRO_SEGMENTATION_MODEL`).
- **Agencje (PAP, Reuters, AP)** wymagają umów i danych dostępowych; podłącza się je jako Własne API (konektor uniwersalny). Bez tego status `unconfigured`.
- **Unsplash, Pexels, Pixabay** działają po dodaniu klucza w panelu; Wikimedia i Openverse bez klucza.
- **Adobe Fonts** nie są plikami do pobrania — działają tylko po aktywacji w Creative Cloud; do PDF/IDML trafiają fonty z biblioteki Zecro.
- **Fonty pominięte przy imporcie z Maca**: 2 puste pliki (niepobrane z iCloud) i duże kolekcje CJK (Hiragino, STHeiti), których rozbicie trwa >45 s. Do wgrania ręcznie przez panel, jeśli będą potrzebne.
- **Koszt AI** liczy się tylko dla modeli wpisanych do cennika w zakładce „Limity i koszty”; bez cennika budżet nie blokuje wywołań, a panel to pokazuje.
- **Szare paski w InDesignie** przy małym powiększeniu to greeking tekstu poniżej progu wyświetlania (podpisy 7,5 pt), nie błąd eksportu.
