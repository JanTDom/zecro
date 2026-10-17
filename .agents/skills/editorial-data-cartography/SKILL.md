---
name: editorial-data-cartography
description: Generowanie wektorowych mapek sytuacyjnych (Press Locator Maps) w formacie SVG, wykresów sondażowych oraz tabel modułowych zoptymalizowanych do druku czarno-białego i kolorowego, idealnie wpasowanych w modularną siatkę szpaltową gazety.
---

# Kartografia Prasowa i Infografiki Wektorowe (Editorial Data & Cartography)

W prasie informacyjnej (a w szczególności w gazetach lokalnych i miejskich, takich jak Wukadka) infografiki i mapki sytuacyjne są niezbędne do wizualizacji zdarzeń: remontów, objazdów, inwestycji drogowych czy lokalizacji wydarzeń kulturalnych. Skill ten odpowiada za tworzenie czystych wektorowych grafik SVG idealnie dopasowanych do szerokości szpalt.

---

## 1. Zasady Kartografii Prasowej

1. **Rygor szpaltowy (Column Snap):**
   - Szerokość mapki musi odpowiadać dokładnej wielokrotności szpalt wraz z odstępami:
     - 1 szpalta: $\approx 50\text{ mm}$
     - 2 szpalty: $\approx 104\text{--}106\text{ mm}$
     - 3 szpalty: $\approx 158\text{--}162\text{ mm}$
     - 5 szpalt (cała szerokość): $\approx 260\text{--}265\text{ mm}$
2. **Minimalizm i hierarchia dróg:**
   - Eliminacja zbędnych szczegółów topograficznych. Wyraźne rozróżnienie:
     - Główna arteria / linia kolejowa (gruba linia kontrastowa),
     - Siatka ulic lokalnych (cienkie szare linie),
     - Punkt zdarzenia (kontrastowy marker / pin z pulsem),
     - Etykieta tekstowa w ramce z białym tłem, by nie zlewała się z siatką ulic.
3. **Elementy obowiązkowe:**
   - Belka tytułowa z nagłówkiem,
   - Strzałka północy (róża wiatrów),
   - Skalówka liczbowa (np. $250\text{ m}$, $1\text{ km}$) z podziałką metryczną.
4. **Typografia:**
   - Nazwy ulic i etykiety składane krojem bezszeryfowym technicznym gazety (np. *Barlow*, stopień 8–9 pt).

---

## 2. Generowanie Mapki Prasowej CLI

Generowanie wektorowej mapki na 2 szpalty:
```bash
python3 scripts/editorial_cartography.py --title "Remont Dworca Warszawa Zachodnia" --label "Stacja WKD Warszawa Zachodnia" --cols 2 --output output/mapka_zachodnia.svg
```

Generowanie małej mapki 1-szpaltowej:
```bash
python3 scripts/editorial_cartography.py --title "Punkt Zbiórki" --label "Park Miejski" --cols 1 --output output/mapka_park.svg
```
