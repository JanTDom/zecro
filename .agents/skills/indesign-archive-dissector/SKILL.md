---
name: indesign-archive-dissector
description: Inżynieria wsteczna i ekstrakcja parametrów typograficznych, siatek modułowych (baseline grid, gutters, marginesy), stylów akapitowych i próbek barwnych CMYK bezpośrednio z archiwów Adobe InDesign (.idml oraz folderów wydań z plikami .indd). Używaj przy dekompilacji istniejących gazet i czasopism do formatu TitleDNA Zecro.
---

# Inżynieria Wsteczna Archiwów InDesign (InDesign Archive Dissector)

Format `.idml` (InDesign Markup Language) oraz pakiety archiwalne wydań (`.indd` wraz z podpiętymi grafikami i plikami tekstowymi) stanowią najbogatsze źródło wiedzy o autentycznym DNA tytułu prasowego. Skill ten odpowiada za dekompilację tych zasobów i konwersję do abstrakcyjnego modelu gramatyki tytułu (**TitleDNA**) oraz geometrii **Scene Graph**.

---

## 1. Wewnętrzna Struktura Pakietu IDML

Plik `.idml` jest archiwum ZIP zawierającym hierarchię XML:
- `designmap.xml` — główny manifest dokumentu, definicje stron wzorcowych (*Master Spreads*) i powiązania z wątkami tekstowymi (*Stories*).
- `Resources/Preferences.xml` — kluczowe parametry:
  - `<GridPreference BaselineGridIncrement="12" BaselineGridStart="15" />` (skok siatki bazowej).
  - `<MarginPreference Top="15" Bottom="18" Left="15" Right="12" ColumnCount="5" ColumnGutter="12" />`.
- `Resources/Styles.xml` — definicje stylów akapitowych i znakowych:
  - `<ParagraphStyle Name="Lead" AppliedFont="PT Serif" PointSize="11.5" Leading="14.5" />`.
- `Resources/Graphic.xml` — biblioteka kolorów CMYK i RGB:
  - `<Color Name="Brand_Navy" Space="CMYK" ColorValue="100 85 10 45" />`.
- `Spreads/Spread_*.xml` — bezwzględne współrzędne geometrii ramek (`<TextFrame GeometricBounds="top left bottom right" />`).

---

## 2. Mapowanie do Gramatyki TitleDNA Zecro

Podczas analizy archiwum następuje konwersja jednostek DTP (punkty pica, mm) na model Zecro:
1. **Siatka bazowa (Baseline Grid):**
   - Skok w punktach (np. $12\text{ pt} = 4.233\text{ mm}$) staje się atomowym kwantem wysokości dla wszystkich ramek tekstowych.
2. **Kroń i hierarchia typograficzna:**
   - Wyodrębnienie pary: Antykwowa (szeryfowa do tekstu ciągłego, np. *PT Serif*, *Minion Pro*) + Bezszeryfowa techniczna (do nagłówków, leadów i etykiet, np. *Barlow*, *Franklin Gothic*).
   - Zestawienie skali modularnej: Tytuł wielki ($\ge 36\text{ pt}$), Tytuł sekcyjny ($20\text{--}24\text{ pt}$), Lead ($11\text{--}12\text{ pt}$), Tekst główny ($9\text{--}10\text{ pt}$), Podpis ($7.5\text{--}8.5\text{ pt}$).
3. **Próbki CMYK:**
   - Standaryzacja próbek barwnych do wartości procentowych CMYK, z eliminacją przypadkowych kolorów RGB zdefiniowanych w InDesignie.

---

## 3. Uruchamianie Narzędzia Dekompilacji

Analiza pliku IDML lub folderu archiwalnego numeru (np. Wukadka NR21):
```bash
python3 scripts/dissect_indesign.py /Users/macbookpro/Desktop/LAYOUTY/WUKADKA/NR21
```

Zapis wyniku w formacie JSON TitleDNA:
```bash
python3 scripts/dissect_indesign.py path/to/document.idml --json --output output/extracted_title_dna.json
```
