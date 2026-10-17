---
name: dtp-softproofing-rip-simulator
description: Symulacja naświetlania CTP i fizycznych zjawisk druku gazetowego (ISO 12647-3). Kontrola limitu nafarbienia (Total Area Coverage TAC < 240%), przyrostu punktu rastrowego (dot gain 25-30%), zalewkowania (trapping 0.15 mm) oraz weryfikacja overprintu dla czerni 100% K.
---

# Symulator Naświetlania RIP i Druku Prasowego (DTP Soft-Proofing & RIP Simulator)

W procesie druku gazetowego (coldset web offset na papierze drzewnym $42\text{--}48.8\text{ g/m}^2$) fizyka papieru i farby różni się diametralnie od druku akcydensowego na papierze kredowym. Skill ten odpowiada za symulację tych zjawisk przed wysłaniem plików do naświetlarni CTP.

---

## 1. Zjawiska Fizyczne Druku Prasowego

1. **Limit Nafarbienia (Total Area Coverage - TAC / TIC):**
   - Na papierze gazetowym maksymalna dopuszczalna suma składowych wynosi **$\text{TAC} \le 220\text{--}240\%$** ($\text{C} + \text{M} + \text{Y} + \text{K}$).
   - Przekroczenie limitu prowadzi do:
     - Rozmazywania mokrej farby na wałkach prowadzących maszyny zwojowej ($10\text{--}15\text{ m/s}$),
     - Efektu przebijania na drugą stronę karty (*show-through*),
     - Ryzyka rozmiękania i zerwania wstęgi papieru w agregacie drukującym.
2. **Przyrost Punktu Rastrowego (*Dot Gain* / TVI):**
   - Z powodu porowatej struktury włókien celulozy kropla farby rozlewa się po wsiąknięciu.
   - W tonach średnich ($50\%$) przyrost wynosi **$25\text{--}30\%$**, co oznacza, że szarość $50\%$ w pliku zostanie wydrukowana jako około $75\text{--}80\%$.
   - **Kompensacja:** Wymaga stosowania profili ICC WAN-IFRA (np. `ISOnewspaper26v4.icc`) z silnym GCR (*Grey Component Replacement*).
3. **Nadruk Czerni (*Black Overprint*):**
   - Tekst ciągły (np. $9.5\text{ pt}$ w $100\%\text{ K}$) musi mieć **bezwzględnie włączony nadruk** (`overprint: true`).
   - Włączenie wybrania (*knockout*) powoduje, że przy typowym błędzie pasowania płyt ($\pm 0.1\text{--}0.15\text{ mm}$) wokół liter pojawią się białe obwódki papieru, czyniąc tekst nieczytelnym.
4. **Zalewkowanie (*Trapping*):**
   - W przypadku białego tekstu w ciemnym tle (negatyw) lub styku barwnych apli, minimalna szerokość trapu wynosi **$0.15\text{ mm}$** ($0.42\text{ pt}$).

---

## 2. Pomiary i Audyt CLI

Szybki test separacji CMYK:
```bash
python3 scripts/rip_simulator.py --c 60 --m 50 --y 50 --k 70 --substrate newsprint
```

Generowanie pełnego raportu weryfikacyjnego JSON dla potoku produkcyjnego:
```bash
python3 scripts/rip_simulator.py --c 80 --m 75 --y 65 --k 85 --json
```
