# Audyt Supabase — 10 października 2026

Audyt został wykonany na projekcie `mhbyguobbctbskahyfqf` przez połączenie
Supabase MCP. Po audycie zastosowano idempotentne utwardzenie backend-only:
włączono RLS na 14 tabelach, odebrano `anon`/`authenticated` uprawnienia do
tych tabel i dodano osiem indeksów kluczy obcych. Obiektów Storage nie usuwano.

## Stan danych

- 14 tabel w `public` odpowiada modelowi backendu: projekty (18), DNA tytułów
  (16), strony korpusu (12), globalny indeks (1), strony globalne (1041),
  archetypy (5), przebiegi generacji (7), kandydaci (41), sygnały gustu (6),
  modele gustu (4), obiekty i rewizje redakcyjne (18/20/662).
- Bucket `zecro-storage` istnieje i zawiera 377 obiektów: 137 uploadów i 240
  eksportów.
- `export_artifacts` ma 0 rekordów przy 240 obiektach w prefiksie `exports/`.
  To oznacza osierocone pliki z wcześniejszego przepływu. Nie zostały usunięte;
  trzeba je najpierw zmapować po nazwie i dopiero potem sprzątać.
- W `corpus_pages.file_path` jest 11 historycznych ścieżek absolutnych z
  workstation. Ich odpowiedniki po basename istnieją w Storage, więc backend
  dostał leniwe materializowanie i nie wymaga ręcznej migracji tych rekordów.

## Stan bezpieczeństwa i wydajności

- RLS jest włączone na wszystkich 14 tabelach publicznych, a role
  `anon`/`authenticated` nie mają do nich uprawnień. Backend korzysta z
  połączenia serwisowego, więc Data API jest zamknięte bez łamania bieżącego
  przepływu FastAPI: [supabase_backend_only_hardening.sql](supabase_backend_only_hardening.sql).
  Security Advisor pokazuje teraz 14 wpisów informacyjnych
  `rls_enabled_no_policy`; brak polityk jest celowy, bo model dostępu jest
  backend-only i brak polityki oznacza deny-by-default.
- Performance Advisor przestał zgłaszać nieindeksowane klucze obce. Osiem
  świeżo utworzonych indeksów jest obecnie oznaczonych jako `unused_index`,
  ponieważ nie zdążyły jeszcze zebrać użycia; nie usuwamy ich przed ruchem
  produkcyjnym.
- Bucket jest publiczny i nie ma ograniczeń MIME/rozmiaru. Po przejściu na
  signed URLs lub proxy backendu można go ustawić jako prywatny; odpowiedni
  wariant jest zapisany jako komentarz w SQL.
- `supabase_list_migrations` nadal zwraca pustą historię, bo schemat powstał
  poza migracjami. Zastosowany plik SQL jest teraz punktem wyjścia do kontroli
  schematu; kolejne zmiany powinny trafiać do wersjonowanych migracji.
- Końcowy smoke test backendu z wymaganiem trybu zdalnego zwrócił
  `healthy`, `db_backend=postgres`, `persistent_db=true`,
  `storage_backend=supabase` i `persistent_storage=true`.

Oficjalne zalecenia Supabase dotyczące ochrony tabel publicznych są opisane w
[secure data](https://supabase.com/docs/guides/database/secure-data), a opis
aktualnego wpisu informacyjnego jest w [linterze RLS bez polityki](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
