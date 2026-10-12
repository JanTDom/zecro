# Format importu reklam CSV

Minimalne kolumny to `id,format`. Opcjonalne kolumny:
`position,status,advertiser,advertiser_category,asset,is_advertorial`.

`status` przyjmuje `booked` albo `tentative`. `format` musi należeć do katalogu
DNA (np. `1/2-horizontal`, `full-page`, `front-ear-right`). Brak assetu jest
dozwolony: renderer używa placeholdera z wymiarami i etykietą. Import nie
przenosi reklamy do geometrii; robi to Art Director po przejściu walidacji.
