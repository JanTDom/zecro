---
name: editorial-flatplan-pagination
description: Architektura całego numeru pisma, makieta wielostronicowa (flatplan), rozkładówki verso/recto, podział sekcji tematycznych, reguły łamania przez grzbiet, balans objętości reklam i rygor składki drukarskiej (arkusze % 4). Używaj przy planowaniu wydań, alokacji materiałów na strony, kontrolowaniu pacingu numeru i sprawdzaniu makiet.
---

# Architektura Makiety Wielostronicowej (Editorial Flatplan & Pagination)

Gazeta i periodyk to nie zbiór oderwanych stron, lecz spójna sekwencja narracyjna tworzona w rygorze poligraficznym. Skill ten odpowiada za zarządzanie makietą wydania (*flatplan*), równoważenie rozkładówek oraz kontrolę reguł montażowych.

---

## 1. Rygory Poligraficzne i Składka Drukarska (Signatures)

1. **Podzielność przez 4 (Zasada Nienegocjowalna):**
   - Liczba stron w wydaniu musi być wielokrotnością 4 ($4, 8, 12, 16, 20, 24, 28, 32\dots$).
   - Wynika to ze zginania arkusza drukarskiego w pół (jedna karta to 4 strony: przód, tył lewa, tył prawa, rewers).
2. **Pacing i Orientacja Stron:**
   - **Strona 1 (Okładka):** Zawsze *recto* (prawa strona). Pełna dominanta wizualna, winieta, brak reklam zakłócających markę.
   - **Rozkładówki wewnętrzne (Spreads):**
     - Strony parzyste ($2, 4, 6, 8\dots$) to *verso* (lewa strona).
     - Strony nieparzyste ($3, 5, 7, 9\dots$) to *recto* (prawa strona – punkt pierwszego skupienia wzroku czytelnika).
   - **Ostatnia strona (Back Cover):** Zawsze *verso* przy wydaniach $\ge 4$ stron. Tradycyjne miejsce na duży felieton, satyrę, plakat lub całostronicową reklamę premium.

---

## 2. Balans Sekcji i Pacing Narracyjny

Wzorcowy rozkład 8-stronicowego wydania lokalnego (archetyp Wukadka):
- **Strona 1:** Okładka ramowa / news otwarcia.
- **Strony 2–3 (Rozkładówka Newsowa):** Bieżące wydarzenia, komunikaty samorządowe, transport i infrastruktura (inwestycje).
- **Strony 4–5 (Środek Wydania / Rozkładówka Środkowa):** Reportaż główny, historia, wywiad pogłębiony, duża infografika lub panorama przez grzbiet.
- **Strony 6–7 (Rozkładówka Społeczno-Kulturalna):** Edukacja, kultura, sport, ogłoszenia drobne i moduły reklamowe.
- **Strona 8 (Tył):** Felieton, kalendarium wydarzeń, stopka redakcyjna (*colophon*).

---

## 3. Reguły Grzbietu (Gutter Safety & Crossover)

1. **Margines wewnętrzny (Spine margin):**
   - Minimum $15\text{ mm}$ wolnego miejsca od linii zgięcia dla kolumn tekstu bieżącego, aby zapobiec „wpadaniu” wierszy w grzbiet przy zszywaniu lub zginaniu coldsetowym.
2. **Łamanie zdjęć przez grzbiet (*Gutter Crossover*):**
   - Dopuszczalne **wyłącznie** dla horyzontalnych dominant fotograficznych i panoram na rozkładówkach środkowych (np. strony 4–5).
   - **Zakaz:** Nigdy nie umieszczaj twarzy, oczu ani kluczowych napisów na osi zgięcia arkusza ($x = \text{szerokość strony}$).

---

## 4. Budżet Reklamowy (Ad-to-Editorial Ratio)

- **Maksymalne nasycenie strony:** Reklamy nie mogą zajmować więcej niż **35–40%** powierzchni żywej strony redakcyjnej.
- **Czystość stron kluczowych:**
  - Strona 1: Max 1 mały moduł sponsorski (ear/uхо) w rogu winiety lub 1 belka dolna.
  - Strony 4–5: Bezwzględny priorytet materiału reportażowego.
- **Oznaczenia prawne:** Każdy moduł płatny musi posiadać etykietę `REKLAMA` lub `OGŁOSZENIE PŁATNE` (min. 7pt, majuskuła, ramka separacyjna).

---

## 5. Narzędzia CLI

Generowanie i walidacja makiety wydania:
```bash
python3 scripts/flatplan_engine.py --title "Wukadka" --issue 21 --pages 8
```

Eksport makiety w formacie JSON do integracji z pipeline Zecro:
```bash
python3 scripts/flatplan_engine.py --title "Wukadka" --issue 21 --pages 8 --json --output output/flatplan_nr21.json
```
