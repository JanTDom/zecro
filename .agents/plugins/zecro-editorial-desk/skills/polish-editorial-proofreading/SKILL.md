---
name: polish-editorial-proofreading
description: >-
  Profesjonalna korekta, adiustacja i mikrotypografia tekstów w języku polskim dla prasy i publikacji DTP. Używaj, gdy zadanie dotyczy: polskiej ortografii (PWN, RJP), interpunkcji, mikrotypografii (usuwanie wiszących spójników/sierotek za pomocą spacji niełamliwych, polskie cudzysłowy „...”, dywiz vs półpauza – vs pauza —, formatowanie dat, liczb i jednostek), wyłapywania pleonazmów i błędów stylistycznych, oraz odmiany nazwisk i toponimów.
---

# Profesjonalna Korekta i Mikrotypografia Prasowa (Język Polski)

Ten skill zawiera reguły i narzędzia do bezbłędnej korekty językowej, adiustacji redakcyjnej oraz mikrotypografii polskiej według standardów PWN, Rady Języka Polskiego (RJP) i czołowych polskich redakcji prasowych.

---

## 1. Żelazne Reguły Polskiej Mikrotypografii DTP

### A. Wiszące Spójniki i Przyimki (Sierotki)
Nigdy nie zostawiaj jedno- i dwuliterowych wyrazów na końcu wiersza składu:
- **Wyrazy jednoliterowe**: `a`, `i`, `o`, `u`, `w`, `z`.
- **Wyrazy dwuliterowe**: `na`, `do`, `od`, `po`, `za`, `ze`, `we`, `ku`, `że`, `co`, `by`, `to`, `np.`, `albo`.
- **Liczby i jednostki**: `15` + `km`, `2026` + `r.`, `100` + `tys.`, `art.` + `5`.
- **Zasada**: Wstawiaj **spację niełamliwą** (`&nbsp;` w HTML, `\u00A0` w Unicode, `~` w Typst/TeX, `^s` w InDesign).

### B. Polskie Cudzysłowy
- **Główny poziom**: `„` (dolny, `\u201E`) oraz `”` (górny, `\u201D`) — np. `„Zbrodnia i kara”`.
  - ❌ Zakaz: cudzysłowy proste `"` (ASCII 34) lub angielskie `“...”` (`\u201C...\u201D`).
- **Drugi poziom (cudzysłów w cudzysłowie)**: Cudzysłów ostrokątny `»...«` (`\u00BB...\u00AB`) lub `«...»`.
  - Przykład: `„Minister powiedział: »To przełomowa ustawa« i zakończył”.`

### C. Znaki Kreskowe: Dywiz, Półpauza i Pauza
- **Dywiz (łącznik `-`, hyphen)**: Służy do łączenia wyrazów złożonych (*biało-czerwony*, *Warszawa-Śródmieście*, *COVID-19*). **Nigdy nie ma spacji po bokach**.
- **Półpauza (`–`, en-dash, `\u2013`)**: Polski myślnik w tekście. **Zawsze otoczona spacjami**:
  - `Warszawa – stolica Polski – rozwija się dynamicznie.`
  - W zakresach liczbowych **bez spacji**: `lata 2020–2026`, `s. 14–28`, `godz. 8.00–16.00`.
- **Pauza (`—`, em-dash, `\u2014`)**: W nagłówkach gazetowych, wyliczeniach dialogowych lub po dateline bez spacji:
  - `WARSZAWA (PAP) — Premier ogłosił...`

### D. Liczby, Daty i Punctuation
- **Zapis daty**: `15 października 2026 r.` lub `15.10.2026 r.` (po miesiącu słownym nie stawiamy kropki!).
- **Separatory tysięcy**: Spacja cienka lub niełamliwa (`10 000 000 PLN`), nigdy przecinek ani kropka (`10,000,000` to zapis angielski).
- **Separator dziesiętny**: Przecinek (`3,14`), nigdy kropka.

---

## 2. Typowe Błędy Językowe i Pleonazmy (Lista Kontrolna)

| ❌ Błędna forma | ✅ Poprawna forma | Uwaga |
|---|---|---|
| *w każdym bądź razie* | **w każdym razie** lub **bądź co bądź** | Kontaminacja |
| *cofać się w tył* | **cofać się** | Pleonazm |
| *okres czasu* | **okres** lub **czas** | Pleonazm |
| *w miesiącu maju* | **w maju** | Rozwlekłość urzędowa |
| *akwen wodny* | **akwen** | Pleonazm (akwen = zbiornik wodny) |
| *w cudzysłowiu* | **w cudzysłowie** | Błąd fleksyjny (miejscownik) |
| *pod rząd* | **z rzędu** | Rusycyzm |
| *ilość ludzi / samochodów* | **liczba ludzi / samochodów** | Rzeczowniki policzalne $\rightarrow$ liczba |
| *za wyjątkiem* | **z wyjątkiem** | Błąd składniowy |
| *po najmniejszej linii oporu* | **po linii najmniejszego oporu** | Zniekształcenie frazeologizmu |
| *włanczać / wyłanczać* | **włączać / wyłączać** | Błąd fonetyczny |

---

## 3. Skróty Prasowe i Odmiana Nazwisk

### A. Odmiana Nazwisk w Polszczyźnie
- **Złota reguła**: Jeśli nazwisko da się odmienić (posiada wzorzec fleksyjny w języku polskim), **MUSI być odmienione** (*artykuł Adama Mickiewicza*, *konferencja prezydenta Emmanuela Macrona*, *książka Jerzego Dudy-Gracza*).
- Nazwiska obcojęzyczne kończące się na spółgłoskę odmieniają się jak polskie rzeczowniki męskie (*Trump $\rightarrow$ Trumpa*, *Biden $\rightarrow$ Bidena*, *Scholz $\rightarrow$ Scholza*).

### B. Kropki w Skrótach
- Skrót kończy się na **ostatnią literę wyrazu skracanego** $\rightarrow$ **BEZ kropki**: `dr` (doktor), `mgr` (magister), `nr` (numer), `wg` (według).
  - *Wyjątek*: W przypadkach zależnych stawiamy kropkę, jeśli końcówka się zmienia: `Nie ma dra Kowalskiego`.
- Skrót urywa się **w środku wyrazu** $\rightarrow$ **Z kropką**: `prof.` (profesor), `hab.` (habilitowany), `ul.` (ulica), `al.` (aleja), `tys.` (tysięcy), `mln` (milion — bez kropki!), `mld` (miliard — bez kropki!).

---

## 4. Narzędzie Automatycznej Korekty Tekstu

Uruchom skrypt automatycznej korekty polskiej mikrotypografii i błędów:
```bash
python3 scripts/polish_proofreader.py --text "To jest tekst w ktorym 'cytat' i spójniki wpadaja na koniec wiersza w miesiacu maju 2026 r."
```
Lub przeskanuj i napraw plik artykułu:
```bash
python3 scripts/polish_proofreader.py --file sciezka/do/artykulu.txt --fix
```

## Referencje
- [Zasady Pisowni i Interpunkcji PWN](./references/pwn-rules.md)
- [Reguły Rady Języka Polskiego (RJP)](./references/rjp-reforms.md)
