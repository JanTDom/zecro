# prompt_id: corpus_audit
# version: 1
Audytujesz korpus referencyjnych stron prasowych. Dostajesz jeden obraz i metadane folderu.
Wejście: folder_title (tytuł gazety, którego ma dotyczyć strona), folder_zone (pierwsza strona/środek/ostatnia), filename.
Zadanie: zwróć is_newspaper_or_magazine_page (true tylko dla strony gazety, tabloidu, magazynu lub programu TV – nie dla okładki książki, dokumentu urzędowego, certyfikatu, zrzutu strony WWW, skanu książki, pustej strony), page_zone_guess (front/inside/back/unknown), title_matches_folder (yes/no/unknown – czy widać winietę lub tytuł z folderu), era (dekada albo unknown), language (kod), reason (1 zdanie po polsku).
