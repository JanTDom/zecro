import React from 'react';
import { studio, errText, Data } from '../../api/studio';

// Font library: everything usable for layout and PDF/IDML.  Polish coverage is
// measured per face (ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ „” – …); restricted-embedding fonts are
// rejected at upload.  Google Fonts are installed from the official repository.
const PL_SAMPLE = 'Zażółć gęślą jaźń — „Łódź” ĄĆĘŁŃÓŚŹŻ';

export const FontLibrary: React.FC = () => {
  const [families, setFamilies] = React.useState<Data[]>([]);
  const [filter, setFilter] = React.useState('');
  const [polishOnly, setPolishOnly] = React.useState(true);
  const [google, setGoogle] = React.useState<Data[]>([]);
  const [gq, setGq] = React.useState('');
  const [status, setStatus] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    try { setFamilies(await studio.fonts(polishOnly)); } catch (e) { setStatus(`Biblioteka niedostępna: ${errText(e)}`); }
  }, [polishOnly]);
  React.useEffect(() => { void load(); }, [load]);

  const searchGoogle = async () => {
    setBusy(true);
    try { setGoogle(await studio.googleFonts(gq)); } catch (e) { setStatus(`Katalog Google niedostępny: ${errText(e)}`); } finally { setBusy(false); }
  };
  const install = async (family: string) => {
    setBusy(true); setStatus(`Instaluję ${family}…`);
    try { const r = await studio.installGoogle(family, [400, 700], true); setStatus(`${family}: zainstalowano ${Array.isArray(r) ? r.length : 0} odmian.`); await load(); }
    catch (e) { setStatus(`Nie zainstalowano: ${errText(e)}`); } finally { setBusy(false); }
  };
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setStatus(`Analizuję ${files.length} plików…`);
    try {
      const r = await studio.uploadFonts(Array.from(files));
      const ok = r.filter(x => x.status === 'added').length; const dup = r.filter(x => x.status === 'duplicate').length;
      const bad = r.filter(x => ['unsupported', 'error', 'rejected'].includes(x.status));
      setStatus(`Dodano ${ok} odmian${dup ? `, ${dup} już było` : ''}.${bad.length ? ` Odrzucone: ${bad.map(b => `${b.file || b.family} (${b.reason})`).join('; ')}` : ''}`); await load();
    } catch (e) { setStatus(`Nie udało się dodać czcionki: ${errText(e)}`); } finally { setBusy(false); }
  };
  const remove = async (id: string) => { try { await studio.deleteFont(id); await load(); } catch (e) { setStatus(errText(e)); } };

  const shown = families.filter(f => f.family.toLowerCase().includes(filter.toLowerCase()));
  const counts = { all: families.length, full: families.filter(f => f.polish === 'full').length };
  return <section className="space-y-4">
    {status && <p role="status" className="text-sm border rounded p-2 bg-white">{status}</p>}
    <div className="grid md:grid-cols-2 gap-4">
      <div className="rounded-xl border bg-white p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Dodaj czcionki z komputera</h2>
        <input type="file" multiple accept=".otf,.ttf,.ttc,.otc,.dfont" disabled={busy} onChange={e => void upload(e.target.files)} />
        <p className="text-xs text-ink-500">Wybierz pliki z Albumu czcionek na Macu. Program sprawdzi polskie znaki i możliwość osadzenia w gazecie.</p>
      </div>
      <div className="rounded-xl border bg-white p-4 space-y-2 text-sm">
        <h2 className="font-semibold">Dodatkowe kroje z Google Fonts</h2>
        <div className="flex gap-2"><input className="flex-1 border rounded p-1.5" placeholder="np. Lora, Source Serif" value={gq} onChange={e => setGq(e.target.value)} onKeyDown={e => e.key === 'Enter' && void searchGoogle()} />
          <button disabled={busy} className="border rounded px-3" onClick={() => void searchGoogle()}>Szukaj</button></div>
        <ul className="max-h-48 overflow-auto divide-y text-xs">{google.map(g => <li key={g.family} className="py-1 flex justify-between gap-2"><span>{g.family} <span className="text-ink-500">· {g.category} · {g.weights?.join(', ')}</span></span>
          <button disabled={busy} className="underline" onClick={() => void install(g.family)}>instaluj</button></li>)}</ul>
      </div>
    </div>
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <input className="border rounded p-1.5" placeholder="Filtruj rodziny" value={filter} onChange={e => setFilter(e.target.value)} />
      <label className="flex items-center gap-1"><input type="checkbox" checked={polishOnly} onChange={e => setPolishOnly(e.target.checked)} /> tylko z pełnymi polskimi znakami</label>
      <span className="text-ink-500">{counts.all} rodzin z biblioteki · {counts.full} z pełnym zestawem polskich znaków</span>
    </div>
    <div className="grid gap-2">{shown.map(f => <details key={f.family} className="rounded border bg-white p-3 text-sm">
      <summary className="cursor-pointer flex flex-wrap items-center gap-3"><b>{f.family}</b>
        <span className={`text-[11px] px-1.5 rounded ${f.polish === 'full' ? 'bg-green-100 text-green-800' : f.polish === 'partial' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'}`}>PL: {f.polish === 'full' ? 'pełne' : f.polish === 'partial' ? 'częściowe' : 'brak'}</span>
        <span className="text-xs text-ink-500">{f.faces.length} odmian</span>
        <span className="text-ink-700 truncate" style={{ fontFamily: `"${f.family}"` }}>{PL_SAMPLE}</span></summary>
      <table className="w-full text-xs mt-2"><tbody>{f.faces.map((x: Data) => <tr key={x.id} className="border-t">
        <td className="py-1">{x.subfamily}</td><td>{x.weight}{x.italic ? ' kursywa' : ''}</td><td>{x.format === 'truetype' ? 'TrueType' : 'OpenType'}</td><td>{x.embedding === 'preview_print' ? 'do podglądu i druku' : x.embedding === 'editable' ? 'do edycji' : 'do osadzania'}</td><td>{x.has_kerning ? 'dopasowanie liter' : 'bez dopasowania liter'}</td>
        <td className={x.missing_chars?.length ? 'text-amber-700' : 'text-green-700'}>{x.missing_chars?.length ? `brak: ${x.missing_chars.join(' ')}` : 'PL komplet'}</td>
        <td><button className="text-red-700" onClick={() => void remove(x.id)}>usuń</button></td></tr>)}</tbody></table>
    </details>)}{shown.length === 0 && <p className="text-sm text-ink-500">Brak fontów w bibliotece.</p>}</div>
  </section>;
};
