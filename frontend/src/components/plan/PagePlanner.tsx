import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { api } from '../../api/client';
import { studio, errText, Data, StoryPayload } from '../../api/studio';
import { PhotoPicker } from '../photos/PhotoPicker';

// Page planning desk: the editor sets the hierarchy of N texts, asks the
// planner (deterministic or AI) for slot geometry, can drag/resize slots on
// the grid (the plan then becomes "fixed") and generates the page from it.
type Slot = { slot_id: string; story_ref: string; rank: string; col_start: number; col_span: number; row_start: number; row_span: number;
  module_type: string; page_number: number; teaser_only: boolean; continuation_page?: number | null };
type Plan = { status: string; columns: number; rows: number; masthead_rows: number; warnings: string[]; slots: Slot[]; geometry?: 'auto' | 'fixed'; page_zone?: string };
type Proposal = { name: string; rationale: string; valid: boolean; errors: string[]; plan: Plan; assignments: Data[] };

const RANKS: [string, string][] = [['lead', 'Dominanta'], ['second', 'Drugi'], ['third', 'Trzeci'], ['short', 'Krótki'], ['brief', 'Wzmianka'],
  ['teaser', 'Zapowiedź'], ['box', 'Ramka'], ['column', 'Felieton']];
const PINS: [string, string][] = [['', 'dowolnie'], ['top', 'góra'], ['under_masthead', 'pod winietą'], ['left_rail', 'lewa szpalta'],
  ['right_rail', 'prawa szpalta'], ['center', 'środek'], ['bottom', 'dół']];
const RANK_COLOR: Record<string, string> = { lead: 'bg-red-100 border-red-500', second: 'bg-amber-50 border-amber-500', third: 'bg-yellow-50 border-yellow-500',
  short: 'bg-green-50 border-green-600', brief: 'bg-sky-50 border-sky-500', teaser: 'bg-violet-50 border-violet-500', box: 'bg-slate-100 border-slate-500', column: 'bg-pink-50 border-pink-500' };

const blank = (i: number, rank = 'second'): StoryPayload => ({ id: `t${Date.now().toString(36)}${i}`, kicker: '', headline: '', lead: '', body: '', rank, span_cols: null, pin_zone: null, images: [] });
const words = (s: string) => (s.trim() ? s.trim().split(/\s+/).length : 0);
const storageKey = (id: string) => `zecro:planner:${id}`;

function overlaps(slots: Slot[]): string[] {
  const out: string[] = [];
  for (let i = 0; i < slots.length; i++) for (let j = i + 1; j < slots.length; j++) {
    const a = slots[i], b = slots[j];
    if (a.col_start < b.col_start + b.col_span && b.col_start < a.col_start + a.col_span && a.row_start < b.row_start + b.row_span && b.row_start < a.row_start + a.row_span)
      out.push(`${a.story_ref} nachodzi na ${b.story_ref}`);
  }
  return out;
}

export const PagePlanner: React.FC = () => {
  const { activeProject, setCurrentRun, setActiveTab, addToast } = useProject();
  const pid = activeProject?.id || '';
  const [stories, setStories] = React.useState<StoryPayload[]>([blank(1, 'lead'), blank(2), blank(3, 'brief')]);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [proposals, setProposals] = React.useState<Proposal[]>([]);
  const [status, setStatus] = React.useState('Wpisz teksty, ustaw rangi i oblicz plan.');
  const [busy, setBusy] = React.useState('');
  const [photoFor, setPhotoFor] = React.useState<string | null>(null);
  const [meta, setMeta] = React.useState({ issueDate: new Date().toISOString().slice(0, 10), issueNumber: '1', section: 'Kraj', candidates: 4 });
  const gridRef = React.useRef<HTMLDivElement>(null);
  const drag = React.useRef<{ id: string; mode: 'move' | 'resize'; x: number; y: number; slot: Slot } | null>(null);

  React.useEffect(() => {
    if (!pid) return;
    try { const raw = localStorage.getItem(storageKey(pid)); if (raw) { const d = JSON.parse(raw); if (d.stories?.length) setStories(d.stories); if (d.plan) setPlan(d.plan); } } catch { /* storage unavailable */ }
  }, [pid]);
  React.useEffect(() => {
    if (!pid) return;
    try { localStorage.setItem(storageKey(pid), JSON.stringify({ stories, plan })); } catch { /* storage unavailable */ }
  }, [pid, stories, plan]);

  if (!activeProject) return <div className="p-12 text-center text-ink-400">Wybierz projekt, aby planować stronę.</div>;

  const edit = (id: string, patch: Partial<StoryPayload>) => setStories(list => list.map(s => s.id === id ? { ...s, ...patch } : s));
  const move = (i: number, d: number) => setStories(list => { const l = [...list]; const j = i + d; if (j < 0 || j >= l.length) return l; [l[i], l[j]] = [l[j], l[i]]; return l; });
  const payload = () => stories.filter(s => s.headline.trim() || s.body.trim()).map(s => ({ ...s, pin_zone: s.pin_zone || null, span_cols: s.span_cols || null,
    importance: s.rank === 'lead' ? 1 : s.rank === 'second' ? .7 : s.rank === 'third' ? .55 : .4, teaser_only: s.rank === 'teaser' }));

  const compute = async () => {
    setBusy('plan');
    try { const p = await studio.plan(pid, payload()) as Plan; setPlan({ ...p, geometry: 'auto' }); setProposals([]);
      setStatus(p.status === 'valid' ? 'Plan obliczony. Możesz przesuwać i skalować moduły na siatce.' : `Plan wymaga poprawek: ${p.warnings.join('; ')}`); }
    catch (e) { setStatus(`Plan niedostępny: ${errText(e)}`); } finally { setBusy(''); }
  };
  const proposeAI = async () => {
    setBusy('ai'); setStatus('AI układa trzy różne hierarchie strony…');
    try { const r = await studio.proposePlans(pid, payload()); setProposals(r.proposals || []); setStatus(`AI zaproponowało ${r.proposals?.length || 0} plany. Wybierz jeden.`); }
    catch (e) { setStatus(`Propozycje AI niedostępne: ${errText(e)}`); } finally { setBusy(''); }
  };
  const applyProposal = (p: Proposal) => {
    const by: Record<string, Data> = Object.fromEntries(p.assignments.map(a => [a.story_id, a]));
    setStories(list => list.map(s => by[s.id] ? { ...s, rank: by[s.id].rank, span_cols: by[s.id].span_cols || null, pin_zone: by[s.id].pin_zone && by[s.id].pin_zone !== 'anywhere' ? by[s.id].pin_zone : null } : s));
    setPlan({ ...p.plan, geometry: 'auto' }); setStatus(`Zastosowano plan „${p.name}”.`);
  };
  const generate = async () => {
    setBusy('gen'); setStatus('Składam stronę: pomiar tekstu, dobór architektury, krytyk wizualny…');
    try {
      const run = await api.generateFromPlan(pid, { stories: payload(), pagePlan: plan, issueDate: meta.issueDate, issueNumber: meta.issueNumber, section: meta.section, candidates: meta.candidates });
      setCurrentRun(run); addToast({ type: 'success', title: 'Strona wygenerowana', message: `${run.candidates.length} wariantów` }); setActiveTab('gallery');
    } catch (e) { setStatus(`Generowanie nieudane: ${errText(e)}`); } finally { setBusy(''); }
  };

  // ---- drag & resize on the grid (snap to cells)
  const onDown = (e: React.PointerEvent, slot: Slot, mode: 'move' | 'resize') => {
    e.preventDefault(); e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { id: slot.slot_id, mode, x: e.clientX, y: e.clientY, slot: { ...slot } };
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current; if (!d || !plan || !gridRef.current) return;
    const r = gridRef.current.getBoundingClientRect();
    const dc = Math.round((e.clientX - d.x) / (r.width / plan.columns)), dr = Math.round((e.clientY - d.y) / (r.height / plan.rows));
    const s = d.slot, minRow = plan.masthead_rows;
    const next = d.mode === 'move'
      ? { col_start: Math.max(0, Math.min(plan.columns - s.col_span, s.col_start + dc)), row_start: Math.max(minRow, Math.min(plan.rows - s.row_span, s.row_start + dr)) }
      : { col_span: Math.max(1, Math.min(plan.columns - s.col_start, s.col_span + dc)), row_span: Math.max(1, Math.min(plan.rows - s.row_start, s.row_span + dr)) };
    setPlan(p => p ? { ...p, geometry: 'fixed', slots: p.slots.map(x => x.slot_id === d.id ? { ...x, ...next } : x) } : p);
  };
  const onUp = () => { drag.current = null; };

  const conflicts = plan ? overlaps(plan.slots.filter(s => !s.teaser_only)) : [];
  const storyBy = Object.fromEntries(stories.map(s => [s.id, s]));
  const leadCount = stories.filter(s => s.rank === 'lead').length;

  return <main className="p-6 max-w-[1400px] mx-auto space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-2xl font-semibold">Makieta strony</h1><p className="text-sm text-ink-500">Hierarchia tekstów → plan siatki → strona. Plan ręcznie zmieniony na siatce jest wiążący dla składu.</p></div>
      <div className="flex flex-wrap gap-2 text-sm">
        <label>Data <input type="date" className="border rounded p-1" value={meta.issueDate} onChange={e => setMeta({ ...meta, issueDate: e.target.value })} /></label>
        <label>Nr <input className="border rounded p-1 w-16" value={meta.issueNumber} onChange={e => setMeta({ ...meta, issueNumber: e.target.value })} /></label>
        <label>Dział <input className="border rounded p-1 w-28" value={meta.section} onChange={e => setMeta({ ...meta, section: e.target.value })} /></label>
        <label>Wariantów <input type="number" min={1} max={12} className="border rounded p-1 w-16" value={meta.candidates} onChange={e => setMeta({ ...meta, candidates: Number(e.target.value) || 4 })} /></label>
      </div>
    </header>
    <p role="status" className="text-sm border rounded p-3 bg-white">{status}{leadCount !== 1 && <span className="text-amber-700"> · Strona powinna mieć dokładnie jedną dominantę (teraz: {leadCount}).</span>}</p>

    <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
      <section className="space-y-3">
        <div className="flex items-center justify-between"><h2 className="font-semibold">Teksty ({stories.length})</h2>
          <div className="flex gap-2"><button className="border rounded px-3 py-1.5 text-sm" onClick={() => setStories(l => [...l, blank(l.length + 1, 'brief')])}>Dodaj tekst</button></div></div>
        {stories.map((s, i) => <div key={s.id} className="border rounded-lg p-3 bg-white space-y-2">
          <div className="flex flex-wrap gap-2 items-center text-sm">
            <span className="font-mono text-xs text-ink-500">{i + 1}. {s.id}</span>
            <select aria-label="Ranga" className="border rounded p-1" value={s.rank} onChange={e => edit(s.id, { rank: e.target.value })}>{RANKS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <select aria-label="Miejsce" className="border rounded p-1" value={s.pin_zone || ''} onChange={e => edit(s.id, { pin_zone: e.target.value || null })}>{PINS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <label className="text-xs">szpalt <input type="number" min={1} max={12} className="border rounded p-1 w-14" value={s.span_cols || ''} placeholder="auto" onChange={e => edit(s.id, { span_cols: Number(e.target.value) || null })} /></label>
            {s.rank === 'teaser' && <label className="text-xs">str. <input type="number" min={2} className="border rounded p-1 w-14" value={s.continue_to_page || ''} onChange={e => edit(s.id, { continue_to_page: Number(e.target.value) || null })} /></label>}
            <span className="ml-auto text-xs text-ink-500">{words(s.body)} słów{s.images?.length ? ' · zdjęcie' : ''}</span>
            <button aria-label="W górę" className="text-xs px-1" onClick={() => move(i, -1)}>↑</button><button aria-label="W dół" className="text-xs px-1" onClick={() => move(i, 1)}>↓</button>
            <button className="text-xs text-red-700" onClick={() => setStories(l => l.filter(x => x.id !== s.id))}>usuń</button>
          </div>
          <input aria-label="Nadtytuł" className="border rounded p-1.5 w-full text-xs" placeholder="Nadtytuł (np. WARSZAWA)" value={s.kicker || ''} onChange={e => edit(s.id, { kicker: e.target.value })} />
          <input aria-label="Tytuł" className="border rounded p-1.5 w-full font-semibold" placeholder="Tytuł" value={s.headline} onChange={e => edit(s.id, { headline: e.target.value })} />
          <textarea aria-label="Lead" className="border rounded p-1.5 w-full text-sm" rows={2} placeholder="Lead" value={s.lead || ''} onChange={e => edit(s.id, { lead: e.target.value })} />
          <textarea aria-label="Tekst" className="border rounded p-1.5 w-full text-sm" rows={4} placeholder="Tekst" value={s.body} onChange={e => edit(s.id, { body: e.target.value })} />
          <div className="flex flex-wrap gap-2 items-center text-xs">
            <button className="border rounded px-2 py-1" onClick={() => setPhotoFor(photoFor === s.id ? null : s.id)}>{s.images?.length ? 'Zmień zdjęcie' : 'Dobierz zdjęcie'}</button>
            {s.images?.[0] && <><span className="truncate max-w-[260px]">{s.images[0].credit || s.images[0].url}</span><button className="text-red-700" onClick={() => edit(s.id, { images: [] })}>usuń zdjęcie</button></>}
          </div>
          {photoFor === s.id && <PhotoPicker story={s} projectId={pid} onClose={() => setPhotoFor(null)} onPick={img => { edit(s.id, { images: [img] }); setPhotoFor(null); }} />}
        </div>)}
        <div className="flex flex-wrap gap-2 sticky bottom-0 bg-paper-50/90 py-2">
          <button disabled={!!busy} className="border rounded px-3 py-2 disabled:opacity-50" onClick={() => void compute()}>Oblicz plan</button>
          <button disabled={!!busy} className="border rounded px-3 py-2 disabled:opacity-50" onClick={() => void proposeAI()}>{busy === 'ai' ? 'AI myśli…' : 'Zaproponuj plan (AI)'}</button>
          <button disabled={!!busy || conflicts.length > 0} className="bg-editorial-crimson text-white rounded px-4 py-2 disabled:opacity-50" onClick={() => void generate()}>{busy === 'gen' ? 'Składam…' : 'Generuj stronę'}</button>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between"><h2 className="font-semibold">Siatka {plan ? `${plan.columns}×${plan.rows}` : ''}</h2>
          {plan && <span className="text-xs">{plan.geometry === 'fixed' ? <>układ ręczny (wiążący) · <button className="underline" onClick={() => setPlan({ ...plan, geometry: 'auto' })}>przywróć automat</button></> : 'tylko rangi wiążące; geometrię dobiera kompozytor'}</span>}</div>
        {proposals.length > 0 && <div className="grid md:grid-cols-3 gap-2">{proposals.map(p => <article key={p.name} className={`border rounded p-2 text-xs bg-white ${p.valid ? '' : 'border-amber-500'}`}>
          <h3 className="font-semibold text-sm">{p.name}</h3><p className="text-ink-500 my-1">{p.rationale}</p>
          <ul className="mb-1">{p.assignments.map(a => <li key={a.story_id}>{storyBy[a.story_id]?.headline || a.story_id}: <b>{RANKS.find(r => r[0] === a.rank)?.[1] || a.rank}</b>{a.span_cols ? ` · ${a.span_cols} szp.` : ''}</li>)}</ul>
          {!p.valid && <p className="text-amber-700">{p.errors.join('; ')}</p>}
          <button className="border rounded px-2 py-1 w-full" onClick={() => applyProposal(p)}>Użyj tego planu</button></article>)}</div>}
        {plan ? <div ref={gridRef} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp} className="relative border bg-white aspect-[7/10] select-none touch-none"
          style={{ backgroundImage: `linear-gradient(to right, rgba(0,0,0,.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,.06) 1px, transparent 1px)`, backgroundSize: `${100 / plan.columns}% ${100 / plan.rows}%` }}>
          {plan.masthead_rows > 0 && <div className="absolute inset-x-0 top-0 bg-ink-950/5 border-b text-[10px] text-center" style={{ height: `${plan.masthead_rows / plan.rows * 100}%` }}>winieta</div>}
          {plan.slots.map(slot => <div key={slot.slot_id} onPointerDown={e => onDown(e, slot, 'move')}
            className={`absolute border-2 p-1 text-[11px] leading-tight overflow-hidden cursor-move ${RANK_COLOR[slot.rank] || 'bg-blue-50 border-blue-500'}`}
            style={{ left: `${slot.col_start / plan.columns * 100}%`, top: `${slot.row_start / plan.rows * 100}%`, width: `${slot.col_span / plan.columns * 100}%`, height: `${slot.row_span / plan.rows * 100}%` }}>
            <strong>{RANKS.find(r => r[0] === slot.rank)?.[1] || slot.rank}</strong> · {slot.col_span} szp.<br />{storyBy[slot.story_ref]?.headline || slot.story_ref}
            <span onPointerDown={e => onDown(e, slot, 'resize')} aria-label="Zmień rozmiar" className="absolute right-0 bottom-0 w-3 h-3 bg-ink-900 cursor-se-resize" />
          </div>)}
        </div> : <p className="text-sm text-ink-500">Plan pojawi się po obliczeniu. Bez planu generator sam dobierze układ z rang.</p>}
        {plan && (plan.warnings.length > 0 || conflicts.length > 0) && <ul className="text-xs text-amber-700 list-disc pl-5">{[...plan.warnings, ...conflicts].map((w, i) => <li key={i}>{w}</li>)}</ul>}
      </section>
    </div>
  </main>;
};
