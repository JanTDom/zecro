import React from 'react';
import { CheckCircle2, CircleAlert, LockKeyhole, Megaphone, RefreshCw } from 'lucide-react';
import { api } from '../../api/client';
import { useProject } from '../../context/ProjectContext';

type EditionPage = { no: number; type: string; section?: string | null; ads: { id: string; format: string; status: string }[]; fixed: { id?: string; role?: string }[]; status: string };
type Edition = { pages: number; imposition: number; centerfold: number[]; page_plan: EditionPage[] };

/** Wydanie shows the whole flatplan; detailed geometry remains in Makieta. */
export const EditionFlatplan: React.FC = () => {
  const { activeProject, addToast } = useProject();
  const [edition, setEdition] = React.useState<Edition | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [selected, setSelected] = React.useState<number | null>(null);

  const load = React.useCallback(async () => {
    setBusy(true);
    try { setEdition(await api.createEditorialEdition(16, 8, new Date().toISOString().slice(0, 10)) as Edition); }
    catch (error) { addToast({ type: 'error', title: 'Wydanie niedostępne', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  }, [addToast]);
  React.useEffect(() => { void load(); }, [load]);

  if (!activeProject) return <div className="p-12 text-center text-ink-400">Wybierz projekt, aby otworzyć wydanie.</div>;
  return <main className="p-6 max-w-[1400px] mx-auto space-y-5">
    <header className="flex items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-widest text-ink-500">Plan wydania</p><h1 className="text-2xl font-semibold">Makieta numeru</h1><p className="text-sm text-ink-500">Miniatury stron, reklamy locked, środkowa rozkładówka i statusy pracy.</p></div>
      <button className="border rounded px-3 py-2 text-sm flex items-center gap-2" onClick={() => void load()} disabled={busy}><RefreshCw className="w-4 h-4" />{busy ? 'Ładuję…' : 'Odśwież'}</button></header>
    {edition && <><div className="flex gap-4 text-xs text-ink-500"><span>{edition.pages} stron</span><span>impozycja {edition.imposition}</span><span>środek: {edition.centerfold.join('–')}</span></div>
      <section className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">{edition.page_plan.map(page => { const isCenter = edition.centerfold.includes(page.no); const active = selected === page.no; return <button key={page.no} onClick={() => setSelected(page.no)} className={`text-left border rounded-lg p-2 bg-white transition ${active ? 'ring-2 ring-editorial-crimson' : ''} ${isCenter ? 'border-editorial-crimson' : 'border-ink-800'}`}><div className="aspect-[3/4] bg-paper-50 border border-ink-800 p-1.5 relative"><div className="text-[10px] font-mono">{page.no}</div>{page.fixed.length > 0 && <div className="mt-2 h-3 bg-ink-900/80 text-[7px] text-white text-center">winieta</div>}<div className="mt-2 space-y-1">{page.ads.map(ad => <div key={ad.id} className="h-5 bg-amber-100 border border-amber-500 text-[7px] p-1 flex items-center gap-1"><Megaphone className="w-2.5 h-2.5" />{ad.format}</div>)}</div><div className="absolute bottom-1 left-1.5 right-1.5 h-1 bg-emerald-200" /></div><div className="mt-1 flex items-center justify-between text-[10px]"><span>{page.type}</span>{page.ads.length ? <LockKeyhole className="w-3 h-3 text-amber-700" /> : <CheckCircle2 className="w-3 h-3 text-emerald-600" />}</div></button>; })}</section>
      {selected && <aside className="border rounded-lg bg-white p-4"><h2 className="font-semibold">Strona {selected}</h2><p className="text-sm text-ink-500">{edition.page_plan.find(page => page.no === selected)?.type}</p><div className="mt-3 flex gap-2 text-xs">{edition.page_plan.find(page => page.no === selected)?.ads.map(ad => <span className="px-2 py-1 rounded bg-amber-100 text-amber-900" key={ad.id}>{ad.id} · {ad.status}</span>)}</div></aside>}
    </>}
    {!edition && !busy && <div className="border rounded-lg p-8 text-center text-ink-500"><CircleAlert className="mx-auto mb-2" />Nie udało się wczytać planu wydania.</div>}
  </main>;
};
