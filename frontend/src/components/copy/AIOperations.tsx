import React from 'react';
import { studio, errText, Data, StoryPayload } from '../../api/studio';
import { SceneGraphElement } from '../../types/sceneGraph';

// AI copy operations for one frame.  Every output passes the source guard
// (numbers, quotes, names, then an AI pass); unsupported fragments are shown
// and an output with flags cannot be applied without the editor seeing them.
type Result = { kind: string; items: { text: string; note?: string; guard?: Data }[]; info?: string };

const GuardFlags: React.FC<{ guard?: Data }> = ({ guard }) => {
  if (!guard) return null;
  const bad = (guard.flags || []).filter((f: Data) => f.status !== 'supported');
  return <div className={`text-[11px] mt-1 ${guard.status === 'supported' ? 'text-emerald-700' : 'text-amber-700'}`}>
    {guard.status === 'supported' ? 'Strażnik: wszystko ma pokrycie w źródle' : `Strażnik: ${guard.status}`}
    {bad.length > 0 && <ul className="list-disc pl-4">{bad.map((f: Data, i: number) => <li key={i}>{f.kind}: „{f.value}” — {f.reason || f.status}</li>)}</ul>}
    {(guard.unsupported || []).length > 0 && <ul className="list-disc pl-4">{guard.unsupported.map((u: string, i: number) => <li key={i}>{u}</li>)}</ul>}
  </div>;
};

export const AIOperations: React.FC<{ element: SceneGraphElement; source: string; draft: string; headline?: string; onUse: (text: string) => void }> = ({ element, source, draft, headline, onUse }) => {
  const [busy, setBusy] = React.useState('');
  const [result, setResult] = React.useState<Result | null>(null);
  const [error, setError] = React.useState('');
  const [lang, setLang] = React.useState('en');
  const story: StoryPayload = { id: element.id, headline: headline || (element.role === 'headline' ? draft : ''), body: element.role === 'headline' ? source : draft, lead: '' };
  const fontSize = element.style?.fontSizePt || (element.role === 'headline' ? 36 : 9.5);
  const run = async (kind: string, fn: () => Promise<Result>) => {
    setBusy(kind); setError('');
    try { setResult(await fn()); } catch (e) { setError(errText(e)); } finally { setBusy(''); }
  };
  const ops: [string, string, () => Promise<Result>][] = element.role === 'headline' ? [
    ['headlines', 'Warianty tytułu (mierzone)', async () => {
      const r = await studio.headlines({ ...story, headline: draft }, element.frame.width, element.style?.fontFamily || 'serif', fontSize, 2, 5) as unknown as Data[];
      return { kind: 'Warianty tytułu', items: r.map(v => ({ text: v.text, note: `${v.lines} l. · ${v.angle}`, guard: v.guard })), info: r.length ? undefined : 'Żaden wariant nie zmieścił się w ramie — zmniejsz stopień lub poszerz ramę.' };
    }],
  ] : [
    ['fit', 'Skróć do ramy (AI)', async () => {
      const r = await studio.fit(story, element.role, { width_mm: element.frame.width, height_mm: element.frame.height, columns: element.style?.columnCount || 1, font_size_pt: fontSize });
      return { kind: 'Tekst dopasowany', items: [{ text: r.text, note: r.fit?.status ? `${r.fit.status} · ${r.fit.lines ?? '?'}/${r.fit.capacity_lines ?? '?'} linii` : '', guard: r.guard }],
        info: r.provenance?.ai_unavailable ? `AI niedostępne — skrót deterministyczny (${r.provenance.ai_unavailable})` : (r.provenance?.need_more_source ? 'Źródło za krótkie na tę ramę.' : undefined) };
    }],
    ['teaser', 'Zapowiedź', async () => { const r = await studio.teaser(story, 2); return { kind: 'Zapowiedź', items: [{ text: `${r.title}. ${r.sentence} ${r.reference}`, guard: r.guard }] }; }],
    ['quotes', 'Cytaty (dosłowne)', async () => { const r = await studio.pullquotes(story); return { kind: 'Cytaty', items: r.quotes.map((q: Data) => ({ text: q.text, note: q.why || q.reason })), info: r.rejected_not_verbatim?.length ? `Odrzucono ${r.rejected_not_verbatim.length} niedosłownych` : undefined }; }],
    ['infobox', 'Ramka faktów', async () => { const r = await studio.infobox(story); return { kind: r.title || 'Ramka faktów', items: r.points.map((p: Data) => ({ text: p.point, note: p.source_sentence })), info: r.dropped_unsourced ? `Pominięto ${r.dropped_unsourced} punktów bez źródła` : undefined }; }],
    ['translate', 'Tłumacz', async () => { const r = await studio.translate(story, lang); return { kind: `Tłumaczenie (${lang})`, items: [{ text: r.translation, note: (r.terms || []).join(', ') }] }; }],
  ];
  const guardDraft = () => run('guard', async () => { const g = await studio.factGuard(draft, source); return { kind: 'Kontrola wersji roboczej', items: [{ text: draft.slice(0, 400) + (draft.length > 400 ? '…' : ''), guard: g }] }; });

  return <div className="space-y-2">
    <div className="flex flex-wrap gap-1.5">{ops.map(([k, label, fn]) => <button key={k} disabled={!!busy} onClick={() => void run(k, fn)} className="px-2 py-1 text-xs rounded border border-ink-700 disabled:opacity-50">{busy === k ? '…' : label}</button>)}
      {element.role !== 'headline' && <select aria-label="Język" className="text-xs border rounded" value={lang} onChange={e => setLang(e.target.value)}>{['en', 'de', 'uk', 'fr', 'es'].map(l => <option key={l}>{l}</option>)}</select>}
      <button disabled={!!busy} onClick={() => void guardDraft()} className="px-2 py-1 text-xs rounded border border-ink-700 disabled:opacity-50">Sprawdź fakty w wersji roboczej</button></div>
    {error && <p className="text-xs text-red-700">{error}</p>}
    {result && <div className="space-y-2"><p className="text-[10px] uppercase font-mono tracking-wider text-ink-500">{result.kind}</p>{result.info && <p className="text-xs text-amber-700">{result.info}</p>}
      {result.items.map((it, i) => <div key={i} className="rounded border border-ink-800 p-2 text-xs">
        <p className="whitespace-pre-wrap text-ink-100">{it.text}</p>{it.note && <p className="text-[11px] text-ink-500 mt-0.5">{it.note}</p>}<GuardFlags guard={it.guard} />
        {result.kind !== 'Kontrola wersji roboczej' && <button className="mt-1 underline" onClick={() => onUse(it.text)}>{it.guard && it.guard.status !== 'supported' ? 'Użyj mimo flag (sprawdź!)' : 'Wstaw do wersji roboczej'}</button>}
      </div>)}</div>}
  </div>;
};
