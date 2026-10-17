---
name: editorial-asset-curation-artbuyer
description: Profesjonalna kuratela materiału zdjęciowego, art buying prasowy, wyliczanie efektywnego PPI w skali 1:1 ramki, kontrola kadrowania, weryfikacja praw autorskich (ZAIKS/PAP) oraz nienegocjowalna bramka etyczna zakazująca ozdobnych wstawek na materiałach o tragediach.
---

# Kuratela Zdjęć i Art Buying Prasowy (Editorial Asset Curation & Art Buyer)

W prasie drukowanej zdjęcie pełni rolę kotwicy uwagi (*visual hero*). Dobór i przygotowanie fotografii nie może polegać na przypadkowym skalowaniu – wymaga weryfikacji fizycznej rozdzielczości, geometrii kadrowania oraz etyki dziennikarskiej.

---

## 1. Efektywna Rozdzielczość w Druku (Effective PPI)

1. **Wzór na efektywne PPI:**
   $$\text{PPI}_{\text{efektywne}} = \frac{\text{szerokość w pikselach}}{\text{szerokość ramki w calach}} = \frac{\text{width\_px}}{\text{width\_mm} / 25.4}$$
2. **Progi jakościowe dla prasy:**
   - **Papier gazetowy (Coldset / Newsprint):** $\ge 180\text{--}200\text{ PPI}$ (liniatura rastra 100–120 lpi).
   - **Papier magazynowy powlekany (Heatset / Sheetfed):** $\ge 300\text{ PPI}$ (liniatura 150–175 lpi).
   - Zdjęcia poniżej $180\text{ PPI}$ ulegają pikselizacji na płycie CTP i muszą zostać odrzucone lub pomniejszone w layoucie.

---

## 2. Kadrowanie Emocjonalne i Oś Wzroku

1. **Kierunek wzroku bohatera (*Gaze Orientation*):**
   - Postać sfotografowana profilem lub półprofilem musi patrzeć **do wnętrza rozkładówki** (w stronę tekstu artykułu), nigdy na zewnątrz strony.
2. **Reguła trójpodziału i margines głowy (*Headroom*):**
   - Twarz w dominancie musi znajdować się w górnej $1/3$ kadru. Ucinanie czubka głowy dopuszczalne jest wyłącznie przy zamierzonym, ciasnym portrecie psychologicznym.
3. **Maksymalna utrata powierzchni kadru:**
   - Obcięcie przekraczające $30\text{--}35\%$ powierzchni oryginalnego zdjęcia wymaga manualnej autoryzacji art directora.

---

## 3. Nienegocjowalna Bramka Etyczna (Wypadki, Tragedie i Żałoba)

Zgodnie z regułą stałą projektu:
- W artykułach o wypadkach śmiertelnych, katastrofach, pożarach i żałobie **bezwzględnie zabrania się**:
  - Nakładania krzykliwych belek i stempli („PILNE”, „TRAGEDIA”, „AFERA”),
  - Wycinań w kształcie koła / owalu / naklejek (*circular head insets*).
- Obowiązuje wyłącznie spokojne, prostokątne kadrowanie dokumentalne w proporcji $16:9$ lub $3:2$ z dyskretnym podpisem.

---

## 4. Oznaczenia Mediów Syntetycznych (Generatywnych AI)

Każda ilustracja wygenerowana maszynowo (np. Midjourney, Imagen, DALL-E) musi:
1. Posiadać metadane XMP: `dc:creator` = "AI Generator", `photoshop:Credit` = "Ilustracja AI", znacznik `trainedAlgorithmicMedia`.
2. Zawierać czytelny podpis pod kadrem informujący czytelnika o syntetycznym pochodzeniu grafiki.

---

## 5. Uruchamianie Audytu CLI

Weryfikacja parametrów zdjęcia przed osadzeniem w makiecie:
```bash
python3 scripts/art_buyer.py --image "DSC_0222.JPG" --width-px 4288 --height-px 2848 --frame-w 180 --frame-h 120
```

Audyt zdjęcia dla materiału wrażliwego z blokadą kołowych wstawek:
```bash
python3 scripts/art_buyer.py --image "wypadek.jpg" --width-px 2400 --height-px 1600 --frame-w 120 --frame-h 90 --tragedy
```
