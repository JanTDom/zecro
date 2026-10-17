---
name: editorial-doc-ingestion-taxonomy
description: Parsowanie surowych manuskryptów dziennikarskich (.docx, .md, .txt), automatyczna dekompozycja na klocki redakcyjne (kicker, tytuł, deck, lead, akapity, wyimki, ramki faktów) oraz zamrażanie faktów i liczb (daty, kwoty, statystyki) do rygorystycznego kontraktu strażnika faktów (Fact-Guard).
---

# Ingest Manuskryptów Dziennikarskich i Taksonomia Redakcyjna (Editorial Doc Ingestion & Taxonomy)

Do redakcji materiały trafiają w postaci surowych plików edytorów tekstu (`.docx`, notatki ze spotkań, depesze agencyjne). Aby silnik Zecro mógł nimi operować, tekst musi zostać rozbity na ustrukturyzowane jednostki redakcyjne, a wszelkie twarde fakty (daty, kwoty, statystyki) zamrożone, by model AI ich nie zniekształcił w pętli copyfittingu.

---

## 1. Architektura Pakietu Artykułu (Editorial Article Package)

Z surowego tekstu ekstrahowane są składowe:
1. **Nadtytuł (Kicker / Rubryka):** 1–3 słowa określające tematykę lub dział (np. `TRANSPORT`, `HISTORIA REGIONU`).
2. **Tytuł Główny (Headline):** Silna fraza czasownikowa, syntetyczna, niosąca sens artykułu.
3. **Deck / Podtytuł:** Dopełnienie tytułu w 1–2 zdaniach, rozwijające kontekst.
4. **Lead:** Pogrubiony wstęp odpowiadający na pytania: *kto, co, gdzie, kiedy i dlaczego* (zasada odwróconej piramidy).
5. **Akapity korpusu (Body):** Podzielone logicznie bloki tekstu, przygotowane do łamania w szpalty.
6. **Wyimki (Pull Quotes):** Mocne cytaty lub tezy wyciągnięte do powiększenia w ramce graficznej.
7. **Ramka faktów (Fact Box):** Wypunktowane kluczowe liczby, terminy, godziny lub koszty.
8. **Podpis (Byline) i Datolinia (Dateline):** Identyfikator autora i miejsca wydarzenia.

---

## 2. Kontrakt Strażnika Faktów (Fact-Guard Contract)

Silnik Zecro chroni dziennikarską wiarygodność przed halucynacjami modeli LLM:
- **Zasada nienaruszalności:** Podczas skracania, wydłużania czy przepisywania tekstu w procesie copyfittingu, **żadna nowa liczba, data ani nazwisko nie może pojawić się w tekście**, a fakty zamrożone w kontrakcie wejściowym nie mogą ulec modyfikacji.
- Kategoryzacja zamrażanych faktów:
  - `date`: np. *25 czerwca*, *2023 r.*, *3 września 2024*
  - `currency`: np. *12 mln zł*, *450 tys. PLN*, *1.5 mld EUR*
  - `percentage`: np. *14.2%*, *75%*
  - `number`: np. *1000 pociągów*, *24 km torowiska*

---

## 3. Uruchamianie Narzędzia Ingestu CLI

Parsowanie pliku Worda z wydania Wukadka:
```bash
python3 scripts/ingest_editorial_doc.py "/Users/macbookpro/Desktop/LAYOUTY/WUKADKA/NR21/WKD a remont Warszawy Zachodniej.docx"
```

Eksport ustrukturyzowanego pakietu JSON dla silnika Zecro:
```bash
python3 scripts/ingest_editorial_doc.py article.docx --json --output output/article_package.json
```
