import React from 'react';
import { apiUrl } from '../../api/client';
import { studio, errText, Data, StoryPayload } from '../../api/studio';

// Photo desk for one story: AI brief → search in configured sources →
// ranking on the images themselves → accept (download, focal point, caption)
// or an AI illustration labelled as such.  Real-event photorealism is refused
// server-side.
export const PhotoPicker: React.FC<{ story: StoryPayload; projectId?: string; onPick: (image: Data) => void; onClose: () => void }> = ({ story, projectId, onPick, onClose }) => {
  const [result, setResult] = React.useState<Data | null>(null);
  const [illus, setIllus] = React.useState<Data | null>(null);
  const [busy, setBusy] = React.useState('');
  const [status, setStatus] = React.useState('');
  const [style, setStyle] = React.useState('redakcyjna ilustracja wektorowa, płaskie plamy koloru');

  const search = async () => {
    setBusy('search'); setStatus('Brief AI i wyszukiwanie w źródłach…');
    try { const r = await studio.proposePhotos(story, projectId, 8); setResult(r); setStatus(r.candidates?.length ? `Znaleziono ${r.candidates.length} propozycji.` : (r.reason || 'Brak wyników.')); }
    catch (e) { setStatus(`Wyszukiwanie nieudane: ${errText(e)}`); } finally { setBusy(''); }
  };
  const accept = async (candidate: Data) => {
    setBusy(candidate.url); setStatus('Pobieram oryginał, liczę punkt ostrości i podpis…');
    try {
      const a = await studio.acceptPhoto(candidate, story, projectId);
      onPick({ id: `img-${Date.now()}`, url: a.url, caption: a.caption || candidate.title || '', credit: a.credit || '', width_px: a.width_px,
        height_px: a.height_px, dpi: a.dpi, focal_point: a.focal_point, importance: 1, license: a.license, source_page: a.source_page });
      setStatus('Zdjęcie przypisane do tekstu.');
    } catch (e) { setStatus(`Nie przyjęto zdjęcia: ${errText(e)}`); } finally { setBusy(''); }
  };
  const illustrate = async () => {
    setBusy('illus'); setStatus('Generuję ilustrację…');
    try { const r = await studio.illustrate(story, style); setIllus(r); setStatus(r.status === 'refused' ? r.reason : `Gotowe: ${r.files?.length || 0} wersje (oznaczone jako AI).`); }
    catch (e) { setStatus(`Ilustracja niedostępna: ${errText(e)}`); } finally { setBusy(''); }
  };
  const brief = result?.brief;
  return <div className="border rounded-lg bg-white p-3 space-y-3 text-sm">
    <div className="flex items-center justify-between"><strong>Zdjęcie do: {story.headline || story.id}</strong><button className="text-xs underline" onClick={onClose}>zamknij</button></div>
    <div className="flex flex-wrap gap-2">
      <button disabled={!!busy} onClick={() => void search()} className="px-3 py-1.5 rounded bg-editorial-crimson text-white disabled:opacity-50">Szukaj zdjęć (AI)</button>
      <input className="border rounded px-2 py-1 flex-1 min-w-[200px]" value={style} onChange={e => setStyle(e.target.value)} aria-label="Styl ilustracji" />
      <button disabled={!!busy} onClick={() => void illustrate()} className="px-3 py-1.5 rounded border disabled:opacity-50">Ilustracja AI</button>
    </div>
    {status && <p role="status" className="text-xs text-ink-500">{status}</p>}
    {brief && <p className="text-xs bg-blue-50 rounded p-2">Brief: {brief.subject || ''} {brief.queries ? `· zapytania: ${(brief.queries as string[]).join(', ')}` : ''} {brief.real_people ? '· prawdziwe osoby: tylko zdjęcia źródłowe' : ''}</p>}
    {(result?.candidates?.length ?? 0) > 0 && <div className="grid grid-cols-2 md:grid-cols-4 gap-2">{result!.candidates.map((c: Data) =>
      <figure key={c.url} className="border rounded overflow-hidden">
        <img src={c.thumb_url || c.url} alt={c.title || ''} className="w-full h-28 object-cover" loading="lazy" />
        <figcaption className="p-1.5 space-y-1 text-[11px]">
          <div className="font-medium line-clamp-2">{c.title}</div>
          <div className="text-ink-500">{c.provider} · {c.license || 'licencja?'} · {c.width_px}×{c.height_px}</div>
          {c.score != null && <div>Ocena {Math.round(c.score * 100)} {c.ai?.depicts_claimed_subject === 'no' ? '· nie przedstawia tematu' : ''}</div>}
          {c.ai?.risks?.length > 0 && <div className="text-amber-700">{(c.ai.risks as string[]).join('; ')}</div>}
          <button disabled={!!busy} onClick={() => void accept(c)} className="w-full mt-1 px-2 py-1 rounded border disabled:opacity-50">{busy === c.url ? '…' : 'Użyj'}</button>
        </figcaption>
      </figure>)}</div>}
    {(illus?.files?.length ?? 0) > 0 && <div className="grid grid-cols-2 md:grid-cols-3 gap-2">{illus!.files.map((f: Data | string, i: number) => {
      const url = typeof f === 'string' ? f : (f.url || f.path);
      return <figure key={i} className="border rounded overflow-hidden"><img src={apiUrl(url)} alt="Ilustracja AI" className="w-full h-32 object-cover" />
        <figcaption className="p-1.5 text-[11px]"><div>Ilustracja wygenerowana przez AI</div>
          <button onClick={() => onPick({ id: `ill-${Date.now()}-${i}`, url, caption: '', credit: 'Ilustracja: AI (Gemini)', importance: 1, ai_generated: true })} className="w-full mt-1 px-2 py-1 rounded border">Użyj</button></figcaption></figure>;
    })}</div>}
  </div>;
};
