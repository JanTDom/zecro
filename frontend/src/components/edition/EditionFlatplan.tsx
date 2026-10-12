import React from 'react';
import { CheckCircle2, CircleAlert, LockKeyhole, Megaphone, RefreshCw } from 'lucide-react';
import { api } from '../../api/client';
import { useProject } from '../../context/ProjectContext';

type EditionPage = { no: number; type: string; section?: string | null; ads: { id: string; format: string; status: string }[]; fixed: { id?: string; role?: string }[]; status: string };
type Edition = { pages: number; imposition: number; centerfold: number[]; page_plan: EditionPage[]; shorts_blocks?: { page: number; items: unknown[] }[]; waiting_room?: unknown[] };
const AD_MODULES = ['full-page', 'spread-full', '1/2-horizontal', '1/2-vertical', '1/3-horizontal', '1/3-vertical', '1/4', '1/8', 'footer-strip', 'corner', 'L-shape', 'island', 'front-ear-left', 'front-ear-right', 'front-banner-top', 'front-banner-bottom'];

/** Wydanie shows the whole flatplan; detailed geometry remains in Makieta. */
export const EditionFlatplan: React.FC = () => {
  const { activeProject, addToast } = useProject();
  const [edition, setEdition] = React.useState<Edition | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [selected, setSelected] = React.useState<number | null>(null);
  const [adFormat, setAdFormat] = React.useState('1/2-horizontal');
  const [adStatus, setAdStatus] = React.useState('booked');
  const [csv, setCsv] = React.useState('');
  const [shortHeadline, setShortHeadline] = React.useState('');
  const [shortBody, setShortBody] = React.useState('');

  const load = React.useCallback(async () => {
    if (!activeProject?.id) return;
    setBusy(true);
    try { const saved = await api.getProjectEditorialEdition(activeProject?.id || ''); setEdition(saved as Edition); setSelected(current => current || 1); }
    catch (error) { addToast({ type: 'error', title: 'Wydanie niedostępne', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  }, [activeProject?.id, addToast]);
  React.useEffect(() => { void load(); }, [load]);

  if (!activeProject) return <div className="p-12 text-center text-ink-400">Wybierz projekt, aby otworzyć wydanie.</div>;
  const selectedPage = edition?.page_plan.find(page => page.no === selected) || null;
  const addAdAt = async (pageNo: number, format = adFormat) => {
    setBusy(true);
    try {
      const result = await api.addEditorialAds(activeProject.id, pageNo, [{ id: `ad-${Date.now()}`, format, status: adStatus }]);
      setEdition(result.edition || result);
    } catch (error) { addToast({ type: 'error', title: 'Nie dodano reklamy', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  const addAd = async () => { if (selectedPage) await addAdAt(selectedPage.no); };
  const importCsv = async () => {
    if (!selectedPage || !csv.trim()) return;
    setBusy(true);
    try { const result = await api.addEditorialAds(activeProject.id, selectedPage.no, [], csv); setEdition(result.edition || result); setCsv(''); addToast({ type: 'success', title: 'Zaimportowano reklamy' }); }
    catch (error) { addToast({ type: 'error', title: 'Import CSV nieudany', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  const removeAd = async (adId: string) => {
    if (!selectedPage) return;
    setBusy(true);
    try { const result = await api.addEditorialAds(activeProject.id, selectedPage.no, [], undefined, [adId]); setEdition(result.edition || result); addToast({ type: 'success', title: 'Usunięto reklamę', message: 'Powierzchnia zostanie uzupełniona shortami.' }); }
    catch (error) { addToast({ type: 'error', title: 'Nie usunięto reklamy', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!edition) return;
    setBusy(true);
    try { setEdition(await api.saveProjectEditorialEdition(activeProject.id, edition) as Edition); addToast({ type: 'success', title: 'Wydanie zapisane' }); }
    catch (error) { addToast({ type: 'error', title: 'Nie zapisano wydania', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  const addShort = async () => {
    if (!selectedPage || !shortHeadline.trim()) return;
    setBusy(true);
    try { const result = await api.addEditionShort(activeProject.id, selectedPage.no, { id: `short-${Date.now()}`, rank: 1, headline: shortHeadline, body: shortBody, source: 'editor' }); setEdition(result.edition || result); setShortHeadline(''); setShortBody(''); addToast({ type: 'success', title: 'Dodano shorta' }); }
    catch (error) { addToast({ type: 'error', title: 'Nie dodano shorta', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  return <main className="p-6 max-w-[1400px] mx-auto space-y-5">
    <header className="flex items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-widest text-ink-500">Plan wydania</p><h1 className="text-2xl font-semibold">Makieta numeru</h1><p className="text-sm text-ink-500">Miniatury stron, reklamy locked, środkowa rozkładówka i statusy pracy.</p></div>
      <div className="flex gap-2"><button className="border rounded px-3 py-2 text-sm flex items-center gap-2" onClick={() => void load()} disabled={busy}><RefreshCw className="w-4 h-4" />{busy ? 'Ładuję…' : 'Odśwież'}</button><button className="bg-editorial-crimson text-white rounded px-3 py-2 text-sm" onClick={() => void save()} disabled={busy || !edition}>Zapisz wydanie</button></div></header>
    {edition && <><div className="flex gap-4 text-xs text-ink-500"><span>{edition.pages} stron</span><span>impozycja {edition.imposition}</span><span>środek: {edition.centerfold.join('–')}</span><span>shorty: {(edition.shorts_blocks || []).reduce((n, block) => n + block.items.length, 0)}</span><span>poczekalnia: {(edition.waiting_room || []).length}</span></div>
      <div className="flex flex-wrap gap-2 items-center border rounded-lg bg-white p-3"><span className="text-xs font-semibold mr-2">Biblioteka reklam</span>{AD_MODULES.map(module => <button key={module} draggable onDragStart={event => event.dataTransfer.setData('application/x-zecro-ad-format', module)} className="border rounded px-2 py-1 text-[10px] cursor-grab" title="Przeciągnij na stronę">{module}</button>)}</div>
      <section className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">{edition.page_plan.map(page => { const isCenter = edition.centerfold.includes(page.no); const active = selected === page.no; return <button key={page.no} onClick={() => setSelected(page.no)} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const format = event.dataTransfer.getData('application/x-zecro-ad-format'); if (format) void addAdAt(page.no, format); }} className={`text-left border rounded-lg p-2 bg-white transition ${active ? 'ring-2 ring-editorial-crimson' : ''} ${isCenter ? 'border-editorial-crimson' : 'border-ink-800'}`}><div className="aspect-[3/4] bg-paper-50 border border-ink-800 p-1.5 relative"><div className="text-[10px] font-mono">{page.no}</div>{page.fixed.length > 0 && <div className="mt-2 h-3 bg-ink-900/80 text-[7px] text-white text-center">winieta</div>}<div className="mt-2 space-y-1">{page.ads.map(ad => <div key={ad.id} className="h-5 bg-amber-100 border border-amber-500 text-[7px] p-1 flex items-center gap-1"><Megaphone className="w-2.5 h-2.5" />{ad.format}</div>)}</div><div className="absolute bottom-1 left-1.5 right-1.5 h-1 bg-emerald-200" /></div><div className="mt-1 flex items-center justify-between text-[10px]"><span>{page.type}</span>{page.ads.length ? <LockKeyhole className="w-3 h-3 text-amber-700" /> : <CheckCircle2 className="w-3 h-3 text-emerald-600" />}</div></button>; })}</section>
      {selected && <aside className="border rounded-lg bg-white p-4 space-y-3"><div><h2 className="font-semibold">Strona {selected}</h2><p className="text-sm text-ink-500">{selectedPage?.type} · {selectedPage?.status}</p></div><div className="flex flex-wrap gap-2 text-xs">{selectedPage?.ads.map(ad => <span className="px-2 py-1 rounded bg-amber-100 text-amber-900" key={ad.id}>{ad.id} · {ad.format} · {ad.status}<button aria-label={`Usuń ${ad.id}`} className="ml-1 text-red-700" onClick={() => void removeAd(ad.id)}>×</button></span>)}</div><div className="grid sm:grid-cols-[1fr_auto_auto] gap-2"><select aria-label="Moduł reklamy" className="border rounded p-2 text-sm" value={adFormat} onChange={event => setAdFormat(event.target.value)}>{AD_MODULES.map(module => <option key={module}>{module}</option>)}</select><select aria-label="Status reklamy" className="border rounded p-2 text-sm" value={adStatus} onChange={event => setAdStatus(event.target.value)}><option value="booked">booked</option><option value="tentative">tentative</option></select><button className="border rounded px-3 text-sm" onClick={() => void addAd()} disabled={busy}>Dodaj reklamę</button></div><div className="flex gap-2"><textarea aria-label="Import reklam CSV" className="border rounded p-2 text-xs font-mono flex-1" rows={2} value={csv} onChange={event => setCsv(event.target.value)} placeholder="id,format,status\nad-1,1/2-horizontal,tentative" /><button className="border rounded px-3 text-sm" onClick={() => void importCsv()} disabled={busy || !csv.trim()}>Importuj CSV</button></div><div className="border-t pt-3 space-y-2"><p className="text-xs font-semibold">Blok shortów</p><input aria-label="Tytuł shorta" className="border rounded p-2 text-sm w-full" value={shortHeadline} onChange={event => setShortHeadline(event.target.value)} placeholder="Tytuł shorta (1 linia)" /><textarea aria-label="Treść shorta" className="border rounded p-2 text-sm w-full" rows={2} value={shortBody} onChange={event => setShortBody(event.target.value)} placeholder="Treść shorta ze źródła" /><button className="border rounded px-3 py-1.5 text-sm" onClick={() => void addShort()} disabled={busy || !shortHeadline.trim()}>Dodaj do shortów</button></div></aside>}
    </>}
    {!edition && !busy && <div className="border rounded-lg p-8 text-center text-ink-500"><CircleAlert className="mx-auto mb-2" />Nie udało się wczytać planu wydania.</div>}
  </main>;
};
