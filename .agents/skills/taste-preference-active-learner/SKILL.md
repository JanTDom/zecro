---
name: taste-preference-active-learner
description: Aktywne uczenie modelu preferencji estetycznych dyrektora artystycznego (Active Learning / Uncertainty Sampling). Dobór par A/B o maksymalnej entropii wyboru, aktualizacja wag cech kompozycyjnych modelem Bradleya-Terry'ego oraz uczenie się z delty przesunięć i modyfikacji geometrii w interfejsie makiety.
---

# Aktywne Uczenie Gustu Dyrektora Artystycznego (Taste Preference Active Learner)

Prawdziwy transfer gustu człowieka do silnika AI nie może opierać się na losowym przeglądaniu setek stron. Skill ten implementuje rygorystyczną pętlę aktywnego uczenia (*Active Learning*), wybierając dla człowieka pary o najwyższej niepewności modelu decyzyjnego oraz adaptując wagi cech na podstawie manualnych korekt w edytorze makiety.

---

## 1. Wybór Par A/B na Zasadzie Maksymalnej Entropii (Uncertainty Sampling)

Zamiast pokazywać człowiekowi warianty, co do których maszyna jest pewna oceny, silnik oblicza entropię Shannona prawdopodobieństwa wyboru:
$$P(A \succ B) = \frac{1}{1 + e^{-(\mathbf{w}^T (\mathbf{x}_A - \mathbf{x}_B))}}$$
$$H(A, B) = - P(A) \log P(A) - P(B) \log P(B)$$
- Para o $H \approx 0.693$ ($P \approx 50\%$) dostarcza **maksymalnego przyrostu informacji** (*information gain*).
- Zaledwie kilkanaście takich decyzji kalibruje wektor wag $\mathbf{w}$ szybciej niż setki losowych ocen.

---

## 2. Aktualizacja Wag Modelem Bradleya-Terry'ego

Gdy dyrektor artystyczny wybierze wariant $A$ nad $B$:
$$\mathbf{w}_{\text{new}} = \mathbf{w}_{\text{old}} + \eta \cdot (1 - P(A \succ B)) \cdot (\mathbf{x}_A - \mathbf{x}_B)$$
Gdzie cechy kompozycyjne $\mathbf{x}$ obejmują:
- `hierarchy_contrast`: Dominacja wizualna głównego artykułu nad pozostałymi.
- `whitespace_balance`: Równomierność i celowość białych plam oddechowych.
- `visual_tension`: Kontrolowane napięcie asymetryczne (budżet transgresji).
- `column_harmony`: Stopień dopasowania szerokości modułów do modularnych wielokrotności szpalt.
- `novelty_distance`: Odległość euklidesowa od korpusu historycznego (ochrona przed autoplagiatem).

---

## 3. Uczenie z Delty Przesunięć na Płótnie (Canvas Delta Ingestion)

Gdy użytkownik w edytorze makiety ręcznie:
- Przesunie ramkę zdjęcia o $+15\text{ mm}$,
- Rozszerzy moduł tekstu z 2 do 3 szpalt,
- Zmniejszy wysokość tytułu o $4\text{ pt}$:

Delta $\Delta = \mathbf{pos}_{\text{człowiek}} - \mathbf{pos}_{\text{AI}}$ jest logowana jako nienegocjowalna preferencja geometryczna danego wydania i zasila rozkład a priori kolejnych generacji.

---

## 4. Uruchamianie Narzędzia CLI

Demonstracja wyboru par o maksymalnej entropii i adaptacji wag:
```bash
python3 scripts/tune_preference_model.py --demo
```
