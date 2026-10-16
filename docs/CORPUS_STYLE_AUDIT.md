# Audyt korpusu stylów (13 października 2026)

## Co faktycznie jest w danych

Katalog opisuje 1041 stron, a pełny manifest audytowy zawiera 1133 rekordy.
Liczba 1044 podana wcześniej w rozmowie nie jest potwierdzona przez pliki.
Poprzedni indeks produkcyjny zawierał 1041 pozycji, w tym 493 strony
odrzucone w audycie. Samo przypisanie pliku do folderu tytułu lub strefy
strony nie wystarcza, by uznać go za przykład stylu.

Indeks 3.0.0 zawiera 281 stron z zaakceptowaną tożsamością tytułu i zgodną
strefą. Do kalibracji bieżącego stylu dopuszczono 140 współczesnych,
zwykłych stron. Strony historyczne pozostają widoczne do analizy, ale nie
wyznaczają współczesnego wzorca. Indeks zapisuje poziom dowodu osobno dla
geometrii rastra i rzeczywiście odczytanych obiektów wektorowych PDF.

| Rodzina | Współczesne strony | Współczesne okładki | Tytuły z okładką |
| --- | ---: | ---: | ---: |
| Prasa opiniotwórcza | 10 | 3 | 2 |
| Gazeta masowa | 24 | 3 | 1 |
| Tabloid | 48 | 8 | 5 |
| Magazyn | 31 | 15 | 5 |
| Program TV | 27 | 9 | 4 |

Osiem okładek tabloidów to: Fakt (1), Wukadka (2), The Sun (1), Globe (1)
i National Enquirer (3). Są to co najmniej trzy odrębne języki graficzne:
polska prasa popularna, brytyjski dziennik popularny i amerykański tabloid
celebrycki. Średnia z tych okładek nie jest gramatyką żadnego z nich.
Zdjęcie okładki Faktu obejmuje również tło poza gazetą, więc ma mniejszą
wartość dla automatycznej geometrii.

## Zasady wykorzystywane przez generator

* Dobór strefy i rodzaju pisma jest ścisły. Brak pasujących okładek daje
  jawną lukę dowodową; nie podstawia się rozkładówek lub innego gatunku.
* Preferencje typograficzne z obiektów PDF mogą uogólniać rodzinę dopiero,
  gdy pochodzą z co najmniej trzech niezależnych tytułów. W pozostałych
  przypadkach obowiązuje jawna redakcyjna wartość początkowa.
* Nagłówek dominujący zachowuje słowa redakcji. Skład może zmienić krój,
  kapitalizację, stopień i podział na wiersze po zmierzeniu szerokości glifów.
  Ostatni wiersz z jednym słowem zatrzymuje stronę w twardej bramce.
* Podgląd i PDF korzystają z tego samego grafu sceny, w tym z wybranego
  łamania, obrysu i cienia. Efekty nie są dodawane dopiero przy eksporcie.
* Fotografia nie dowodzi, jaki temat przedstawia. Zgodność zdjęcia z tekstem
  wymaga osobnej kontroli redakcyjnej lub wizualnej i nie jest tu wywnioskowana
  z samych pikseli.

## Granica obecnego dowodu

Raster pozwala oszacować bloki koloru i zgrubne obszary obrazu. Nie pozwala
wiarygodnie rozpoznać hierarchii tematów, kroju pisma, intencji redakcyjnej
ani poprawności zdjęcia. Dlatego wskaźnik wyprowadzony wyłącznie z rastra
nie może być nazywany oceną podobieństwa wizualnego 1,0. Materiał źródłowy
nie był przesyłany do zewnętrznego modelu wizualnego po odmowie automatycznej
kontroli bezpieczeństwa. Analiza semantyczna okładek pozostaje w tym zakresie
niezweryfikowana.
