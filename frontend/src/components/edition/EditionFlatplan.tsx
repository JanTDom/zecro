import React from 'react';
import { CheckCircle2, CircleAlert, LockKeyhole, Megaphone, RefreshCw, FileDown, FileText } from 'lucide-react';
import { api } from '../../api/client';
import { useProject } from '../../context/ProjectContext';

type EditionPage = { no: number; type: string; section?: string | null; ads: { id: string; format: string; status: string; position?: string; advertiser_category?: string }[]; fixed: { id?: string; role?: string }[]; status: string; editorial_area?: { reserved_ratio?: number } };
type Edition = { pages: number; imposition: number; centerfold: number[]; page_plan: EditionPage[]; shorts_blocks?: { page: number; items: unknown[] }[]; waiting_room?: unknown[] };
const AD_MODULES = ['full-page', 'spread-full', '1/2-horizontal', '1/2-vertical', '1/3-horizontal', '1/3-vertical', '1/4', '1/8', 'footer-strip', 'corner', 'L-shape', 'island', 'front-ear-left', 'front-ear-right', 'front-banner-top', 'front-banner-bottom'];
const AD_LABELS: Record<string, string> = {
  'full-page': 'Cała strona', 'spread-full': 'Cała rozkładówka',
  '1/2-horizontal': 'Pół strony poziomo', '1/2-vertical': 'Pół strony pionowo',
  '1/3-horizontal': 'Jedna trzecia poziomo', '1/3-vertical': 'Jedna trzecia pionowo',
  '1/4': 'Ćwierć strony', '1/8': 'Jedna ósma strony', 'footer-strip': 'Pas na dole',
  corner: 'Narożnik', 'L-shape': 'Reklama w kształcie L', island: 'Wyspa',
  'front-ear-left': 'Lewe ucho pierwszej strony', 'front-ear-right': 'Prawe ucho pierwszej strony',
  'front-banner-top': 'Pas nad winietą', 'front-banner-bottom': 'Pas pod winietą',
};
const PAGE_TYPE_LABELS: Record<string, string> = {
  front: 'Pierwsza strona', back: 'Ostatnia strona',
  'inner-left': 'Lewa strona', 'inner-right': 'Prawa strona',
  'spread-left': 'Lewa część rozkładówki', 'spread-right': 'Prawa część rozkładówki',
};
const PAGE_STATUS_LABELS: Record<string, string> = { empty: 'pusta', in_progress: 'w przygotowaniu', approved: 'zatwierdzona' };
const AD_STATUS_LABELS: Record<string, string> = { booked: 'potwierdzona', tentative: 'wstępna' };
const AD_AREA: Record<string, number> = { 'full-page': 192, 'spread-full': 192, '1/2-horizontal': 96, '1/2-vertical': 96, '1/3-horizontal': 60, '1/3-vertical': 64, '1/4': 48, '1/8': 24, 'footer-strip': 24, corner: 16, 'L-shape': 192, island: 16, 'front-ear-left': 6, 'front-ear-right': 6, 'front-banner-top': 24, 'front-banner-bottom': 24 };
const adOccupation = (page: EditionPage) => Math.min(100, Math.round(page.ads.reduce((sum, ad) => sum + (AD_AREA[ad.format] || 0), 0) / 192 * 100));

/** Wydanie shows the whole flatplan; detailed geometry remains in Makieta. */
export const EditionFlatplan: React.FC = () => {
  const { activeProject, addToast } = useProject();
  const [edition, setEdition] = React.useState<Edition | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [selected, setSelected] = React.useState<number | null>(null);
  const [adFormat, setAdFormat] = React.useState('1/2-horizontal');
  const [adStatus, setAdStatus] = React.useState('booked');
  const [adPosition, setAdPosition] = React.useState('bottom');
  const [adCategory, setAdCategory] = React.useState('');
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

  if (!activeProject) return <div className="p-12 text-center text-ink-400">Wybierz gazetę, aby otworzyć wydanie.</div>;
  const selectedPage = edition?.page_plan.find(page => page.no === selected) || null;
  const addAdAt = async (pageNo: number, format = adFormat) => {
    setBusy(true);
    try {
      const result = await api.addEditorialAds(activeProject.id, pageNo, [{ id: `ad-${Date.now()}`, format, status: adStatus, position: format.startsWith('front-') ? 'front' : adPosition, advertiser_category: adCategory || undefined }]);
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
    try { const result = await api.addEditorialAds(activeProject.id, selectedPage.no, [], undefined, [adId]); setEdition(result.edition || result); addToast({ type: 'success', title: 'Usunięto reklamę', message: 'Wolne miejsce będzie można wypełnić krótkimi notkami.' }); }
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
    try { const result = await api.addEditionShort(activeProject.id, selectedPage.no, { id: `short-${Date.now()}`, rank: 1, headline: shortHeadline, body: shortBody, source: 'editor' }); setEdition(result.edition || result); setShortHeadline(''); setShortBody(''); addToast({ type: 'success', title: 'Dodano krótką notkę' }); }
    catch (error) { addToast({ type: 'error', title: 'Nie dodano krótkiej notki', message: error instanceof Error ? error.message : 'Błąd API' }); }
    finally { setBusy(false); }
  };
  const handleExportEdition = async (format: 'pdf' | 'idml' = 'pdf') => {
    if (!activeProject?.id) return;
    setBusy(true);
    try {
      const artifact = await api.exportFullEdition(activeProject.id, format);
      addToast({
        type: 'success',
        title: 'Wydanie skompilowane',
        message: `Pobieranie ${artifact.fileName} (${Math.round((artifact.fileSizeBytes || 0) / 1024)} KB)...`,
      });
      window.open(artifact.downloadUrl, '_blank');
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Błąd kompilacji wydania',
        message: e instanceof Error ? e.message : 'Nie udało się wyeksportować wydania.',
      });
    } finally {
      setBusy(false);
    }
  };
  return <main className="p-6 max-w-[1400px] mx-auto space-y-5">
    <header className="flex items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-widest text-ink-500">Plan wydania</p><h1 className="text-2xl font-semibold">Makieta numeru</h1><p className="text-sm text-ink-500">Tu rozplanujesz strony, reklamy i środkową rozkładówkę.</p></div>
      <div className="flex flex-wrap gap-2">
        <button className="border rounded px-3 py-2 text-sm flex items-center gap-2" onClick={() => void load()} disabled={busy}><RefreshCw className="w-4 h-4" />{busy ? 'Ładuję…' : 'Odśwież'}</button>
        <button className="bg-editorial-crimson text-white rounded px-3 py-2 text-sm font-semibold" onClick={() => void save()} disabled={busy || !edition}>Zapisz wydanie</button>
        <button
          className="bg-ink-900 border border-ink-700 text-white rounded px-3 py-2 text-sm flex items-center gap-2 hover:bg-ink-800 transition"
          onClick={() => void handleExportEdition('pdf')}
          disabled={busy || !edition}
          title="Kompiluj wszystkie strony numeru w jeden wielostronicowy plik PDF do druku (ze spadami)"
        >
          <FileDown className="w-4 h-4 text-editorial-crimson" />
          Kompiluj numer (PDF)
        </button>
        <button
          className="bg-ink-900 border border-ink-700 text-white rounded px-3 py-2 text-sm flex items-center gap-2 hover:bg-ink-800 transition"
          onClick={() => void handleExportEdition('idml')}
          disabled={busy || !edition}
          title="Kompiluj pakiet wydania InDesign IDML"
        >
          <FileText className="w-4 h-4 text-amber-500" />
          Eksportuj IDML
        </button>
      </div></header>

    {edition && <><div className="flex gap-4 text-xs text-ink-500"><span>{edition.pages} stron</span><span>układ arkusza: {edition.imposition}</span><span>środek: {edition.centerfold.join('–')}</span><span>krótkie notki: {(edition.shorts_blocks || []).reduce((n, block) => n + block.items.length, 0)}</span><span>poczekalnia: {(edition.waiting_room || []).length}</span></div>
      <div className="flex flex-wrap gap-2 items-center border rounded-lg bg-white p-3"><span className="text-xs font-semibold mr-2">Biblioteka reklam</span>{AD_MODULES.map(module => <button key={module} draggable onDragStart={event => event.dataTransfer.setData('application/x-zecro-ad-format', module)} className="border rounded px-2 py-1 text-[10px] cursor-grab" title="Przeciągnij na stronę">{AD_LABELS[module] || module}</button>)}</div>
      <section className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">{edition.page_plan.map(page => { const isCenter = edition.centerfold.includes(page.no); const active = selected === page.no; const occupied = adOccupation(page); return <button key={page.no} onClick={() => setSelected(page.no)} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const format = event.dataTransfer.getData('application/x-zecro-ad-format'); if (format) void addAdAt(page.no, format); }} className={`text-left border rounded-lg p-2 bg-white transition ${active ? 'ring-2 ring-editorial-crimson' : ''} ${isCenter ? 'border-editorial-crimson' : 'border-ink-800'}`}><div className="aspect-[3/4] bg-paper-50 border border-ink-800 p-1.5 relative"><div className="text-[10px] font-mono">{page.no}</div>{page.fixed.length > 0 && <div className="mt-2 h-3 bg-ink-900/80 text-[7px] text-white text-center">winieta</div>}<div className="mt-2 space-y-1">{page.ads.map(ad => <div key={ad.id} className="h-5 bg-amber-100 border border-amber-500 text-[7px] p-1 flex items-center gap-1"><Megaphone className="w-2.5 h-2.5" />{AD_LABELS[ad.format] || ad.format}</div>)}</div><div className="absolute bottom-1 left-1.5 right-1.5 h-1 bg-emerald-200" /></div><div className="mt-1 flex items-center justify-between text-[10px]"><span>{PAGE_TYPE_LABELS[page.type] || page.type}</span>{page.ads.length ? <LockKeyhole className="w-3 h-3 text-amber-700" /> : <CheckCircle2 className="w-3 h-3 text-emerald-600" />}</div><div className="mt-1 text-[9px] text-ink-500">reklamy: {occupied}%</div></button>; })}</section>
      {selected && <aside className="border rounded-lg bg-white p-4 space-y-3"><div><h2 className="font-semibold">Strona {selected}</h2><p className="text-sm text-ink-500">{PAGE_TYPE_LABELS[selectedPage?.type || ''] || selectedPage?.type} · {PAGE_STATUS_LABELS[selectedPage?.status || ''] || selectedPage?.status} · reklamy {selectedPage ? adOccupation(selectedPage) : 0}%</p></div><div className="flex flex-wrap gap-2 text-xs">{selectedPage?.ads.map(ad => <span className="px-2 py-1 rounded bg-amber-100 text-amber-900" key={ad.id}>{ad.id} · {AD_LABELS[ad.format] || ad.format} · {AD_STATUS_LABELS[ad.status] || ad.status}{ad.advertiser_category ? ` · ${ad.advertiser_category}` : ''}<button aria-label={`Usuń ${ad.id}`} className="ml-1 text-red-700" onClick={() => void removeAd(ad.id)}>×</button></span>)}</div><div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-2"><select aria-label="Moduł reklamy" className="border rounded p-2 text-sm" value={adFormat} onChange={event => setAdFormat(event.target.value)}>{AD_MODULES.map(module => <option key={module} value={module}>{AD_LABELS[module] || module}</option>)}</select><select aria-label="Status reklamy" className="border rounded p-2 text-sm" value={adStatus} onChange={event => setAdStatus(event.target.value)}><option value="booked">potwierdzona</option><option value="tentative">wstępna</option></select><select aria-label="Pozycja reklamy" className="border rounded p-2 text-sm" value={adPosition} onChange={event => setAdPosition(event.target.value)}><option value="top">góra</option><option value="middle">środek</option><option value="bottom">dół</option><option value="left">lewa</option><option value="right">prawa</option></select><input aria-label="Kategoria reklamodawcy" className="border rounded p-2 text-sm" value={adCategory} onChange={event => setAdCategory(event.target.value)} placeholder="kategoria" /><button className="border rounded px-3 text-sm" onClick={() => void addAd()} disabled={busy}>Dodaj reklamę</button></div><div className="flex gap-2"><textarea aria-label="Import reklam CSV" className="border rounded p-2 text-xs font-mono flex-1" rows={2} value={csv} onChange={event => setCsv(event.target.value)} placeholder="id,format,status\nad-1,1/2-horizontal,tentative" /><button className="border rounded px-3 text-sm" onClick={() => void importCsv()} disabled={busy || !csv.trim()}>Importuj CSV</button></div><div className="border-t pt-3 space-y-2"><p className="text-xs font-semibold">Krótkie notki</p><input aria-label="Tytuł krótkiej notki" className="border rounded p-2 text-sm w-full" value={shortHeadline} onChange={event => setShortHeadline(event.target.value)} placeholder="Tytuł krótkiej notki (1 linia)" /><textarea aria-label="Treść krótkiej notki" className="border rounded p-2 text-sm w-full" rows={2} value={shortBody} onChange={event => setShortBody(event.target.value)} placeholder="Treść krótkiej notki ze źródła" /><button className="border rounded px-3 py-1.5 text-sm" onClick={() => void addShort()} disabled={busy || !shortHeadline.trim()}>Dodaj notkę</button></div></aside>}
    </>}
    {!edition && !busy && <div className="border rounded-lg p-8 text-center text-ink-500"><CircleAlert className="mx-auto mb-2" />Nie udało się wczytać planu wydania.</div>}
  </main>;
};
