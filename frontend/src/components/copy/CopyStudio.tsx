import React from 'react';
import { CheckCircle2, Copy, FileText, LockKeyhole, RefreshCw, RotateCcw, Sparkles, Target, Wand2 } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { api } from '../../api/client';
import { Candidate, FrameCopyFit } from '../../types/generation';
import { SceneGraphElement } from '../../types/sceneGraph';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { AIOperations } from './AIOperations';

const TEXT_ROLES = new Set(['headline', 'deck', 'lead', 'body', 'caption', 'kicker', 'byline', 'pullquote', 'infobox', 'band']);

type Snapshot = { candidateId: string; elementId: string; content: string };

export const CopyStudio: React.FC = () => {
  const { selectedCandidate, currentRun, setSelectedCandidate, setCurrentRun, addToast } = useProject();
  const textElements = (selectedCandidate?.sceneGraph.elements || []).filter((element) => TEXT_ROLES.has(element.role) && element.content.trim());
  const [selectedId, setSelectedId] = React.useState<string | null>(textElements[0]?.id || null);
  const [draft, setDraft] = React.useState('');
  const [targetWords, setTargetWords] = React.useState<number | ''>('');
  const [lockedText, setLockedText] = React.useState('');
  const [fit, setFit] = React.useState<FrameCopyFit | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [history, setHistory] = React.useState<Snapshot[]>([]);

  React.useEffect(() => {
    const first = (selectedCandidate?.sceneGraph.elements || []).find((element) => TEXT_ROLES.has(element.role) && element.content.trim());
    setSelectedId(first?.id || null);
    setFit(null);
    setHistory([]);
  }, [selectedCandidate?.id]);

  const selected = textElements.find((element) => element.id === selectedId) || null;
  const selectedSlot = selectedCandidate?.artDirection?.copy_slots.find((slot) => slot.element_ref === selected?.id);
  React.useEffect(() => {
    if (selected) {
      setDraft(selected.content);
      setTargetWords('');
      setFit(null);
    }
  }, [selected?.id, selected?.content]);

  if (!selectedCandidate) {
    return <div className="p-12 text-center text-ink-400">Wybierz wariant w Galerii, aby otekstować konkretne ramy strony.</div>;
  }

  const applyCandidate = (updated: Candidate) => {
    setSelectedCandidate(updated);
    if (currentRun) setCurrentRun({ ...currentRun, candidates: currentRun.candidates.map((item) => item.id === updated.id ? updated : item) });
  };

  const inspectFit = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await api.fitCandidateCopy(selectedCandidate.id, selected.id, {
        text: draft,
        targetWords: targetWords === '' ? undefined : Number(targetWords),
        lockedPassages: lockedText.split(/\n+/).map((item) => item.trim()).filter(Boolean),
      });
      setFit(result);
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się dopasować tekstu', message: error instanceof Error ? error.message : 'Błąd API' });
    } finally { setBusy(false); }
  };

  const applyFit = async () => {
    if (!selected || !fit || fit.fit.status !== 'PASS') return;
    setBusy(true);
    try {
      setHistory((items) => [...items, { candidateId: selectedCandidate.id, elementId: selected.id, content: selected.content }]);
      const scene = JSON.parse(JSON.stringify(selectedCandidate.sceneGraph));
      const element = scene.elements.find((item: SceneGraphElement) => item.id === selected.id);
      if (element) element.content = fit.text;
      const updated = await api.saveCandidate(selectedCandidate.id, scene);
      applyCandidate(updated);
      setFit(null);
      addToast({ type: 'success', title: 'Tekst zastosowany', message: 'Zapisano nową wersję sceny; poprzednia jest dostępna przez Cofnij.' });
    } catch (error) {
      addToast({ type: 'error', title: 'Nie zapisano tekstu', message: error instanceof Error ? error.message : 'Błąd API' });
    } finally { setBusy(false); }
  };

  const undo = async () => {
    const previous = history[history.length - 1];
    if (!previous || previous.candidateId !== selectedCandidate.id) return;
    setBusy(true);
    try {
      const scene = JSON.parse(JSON.stringify(selectedCandidate.sceneGraph));
      const element = scene.elements.find((item: SceneGraphElement) => item.id === previous.elementId);
      if (element) element.content = previous.content;
      const updated = await api.saveCandidate(selectedCandidate.id, scene);
      applyCandidate(updated);
      setHistory((items) => items.slice(0, -1));
      addToast({ type: 'info', title: 'Cofnięto zmianę tekstu' });
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się cofnąć', message: error instanceof Error ? error.message : 'Błąd API' });
    } finally { setBusy(false); }
  };

  const status = fit?.fit.status;
  return (
    <div className="p-6 max-w-[1500px] mx-auto space-y-5">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-editorial-crimson font-mono font-bold">Content Studio / Copyfit</p>
          <h1 className="mt-1 text-3xl font-headline font-black text-ink-100">Otekstowywanie strony</h1>
          <p className="mt-2 text-sm text-ink-400 max-w-2xl">Pracujesz na rzeczywistych ramach wybranego wariantu. System mierzy tekst w milimetrach i może skracać wyłącznie materiał źródłowy; nie dopisuje faktów.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={undo} disabled={!history.length || busy} leftIcon={<RotateCcw className="w-3.5 h-3.5" />}>Cofnij</Button>
          <Badge variant="accent">{textElements.length} ram tekstowych</Badge>
        </div>
      </header>

      <div className="grid grid-cols-[260px_minmax(0,1fr)_360px] gap-5 items-start">
        <Card noPadding className="overflow-hidden">
          <div className="px-4 py-3 border-b border-ink-800 flex items-center gap-2"><FileText className="w-4 h-4 text-editorial-crimson" /><span className="text-xs font-mono uppercase tracking-wider text-ink-400">Ramy strony</span></div>
          <div className="p-2 space-y-1 max-h-[640px] overflow-auto">
            {textElements.map((element) => (
              <button key={element.id} onClick={() => setSelectedId(element.id)} className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedId === element.id ? 'bg-blue-50 border-editorial-crimson' : 'border-transparent hover:bg-ink-950'}`}>
                <div className="flex items-center justify-between gap-2"><span className="text-[10px] font-mono uppercase tracking-wider text-editorial-crimson">{element.role}</span><span className="text-[10px] font-mono text-ink-500">{element.frame.width.toFixed(0)}×{element.frame.height.toFixed(0)} mm</span></div>
                <p className="mt-1 text-xs text-ink-200 line-clamp-3">{element.content}</p>
              </button>
            ))}
            {!textElements.length && <p className="p-4 text-xs text-ink-500">Ten wariant nie zawiera jeszcze tekstowych ramek.</p>}
          </div>
        </Card>

        <Card className="space-y-4">
          {selected ? <>
            <div className="flex items-center justify-between border-b border-ink-800 pb-3"><div className="flex items-center gap-2"><Target className="w-4 h-4 text-editorial-crimson" /><span className="font-mono text-xs uppercase tracking-wider text-ink-400">{selected.role} · {selected.id}</span></div><span className="text-xs text-ink-500">{selected.frame.width.toFixed(1)} × {selected.frame.height.toFixed(1)} mm · {selected.style.columnCount || 1} ł.</span></div>
            {selectedSlot && <div className="rounded-lg border border-blue-100 bg-blue-50 p-3"><p className="text-[10px] uppercase tracking-wider font-mono text-editorial-crimson">Zadanie art directora</p><p className="mt-1 text-xs font-semibold text-ink-100">{selectedSlot.editorial_job}</p><p className="mt-1 text-xs leading-relaxed text-ink-400">{selectedSlot.writing_instruction}</p><p className="mt-2 text-[10px] font-mono text-ink-500">Budżet: {selectedSlot.target_words} słów · {selectedSlot.target_lines} linii · {selectedSlot.fit_status}</p></div>}
            <label className="block"><span className="text-[10px] uppercase font-mono tracking-wider text-ink-500">Tekst źródłowy / wersja robocza</span><textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="mt-2 w-full min-h-[280px] rounded-lg border border-ink-700 bg-ink-950 p-3 text-sm leading-relaxed text-ink-100 focus:border-editorial-crimson focus:outline-hidden" /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-[10px] uppercase font-mono tracking-wider text-ink-500">Docelowa liczba słów</span><input type="number" min={1} value={targetWords} onChange={(event) => setTargetWords(event.target.value === '' ? '' : Number(event.target.value))} placeholder={`${draft.split(/\s+/).filter(Boolean).length} (źródło)`} className="mt-2 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-ink-100 focus:border-editorial-crimson focus:outline-hidden" /></label>
              <label className="block"><span className="text-[10px] uppercase font-mono tracking-wider text-ink-500">Zablokowane frazy</span><textarea value={lockedText} onChange={(event) => setLockedText(event.target.value)} placeholder="Jedna fraza w wierszu" className="mt-2 w-full h-[42px] rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-xs text-ink-100 focus:border-editorial-crimson focus:outline-hidden" /></label>
            </div>
            <div className="flex items-center gap-2"><Button variant="editorial" onClick={inspectFit} isLoading={busy} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Sprawdź dopasowanie</Button><Button variant="outline" onClick={() => setDraft(selected.content)} leftIcon={<RotateCcw className="w-3.5 h-3.5" />}>Przywróć źródło</Button></div>
            <div className="border-t border-ink-800 pt-3"><p className="text-[10px] uppercase font-mono tracking-wider text-ink-500 mb-2">Operacje AI (ze strażnikiem źródeł)</p>
              <AIOperations element={selected} source={selected.content} draft={draft} onUse={setDraft}
                headline={(selectedCandidate.sceneGraph.elements.find((e) => e.role === 'headline' && e.id.split('-').slice(1, 2).join() === selected.id.split('-').slice(1, 2).join()) || selectedCandidate.sceneGraph.elements.find((e) => e.role === 'headline'))?.content} /></div>
          </> : <p className="text-sm text-ink-500">Wybierz ramę po lewej.</p>}
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center gap-2 border-b border-ink-800 pb-3"><Sparkles className="w-4 h-4 text-editorial-ochre" /><span className="font-mono text-xs uppercase tracking-wider text-ink-400">Wynik redakcyjny</span></div>
          {!fit && <div className="py-8 text-center text-ink-500"><Wand2 className="mx-auto w-8 h-8 mb-3 text-ink-600" /><p className="text-sm">Zmierzę tekst w wybranej ramie.</p><p className="mt-1 text-xs">To propozycja do akceptacji, nie automatyczna publikacja.</p></div>}
          {fit && <>
            <div className={`rounded-lg border p-3 ${status === 'PASS' ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}><div className="flex items-center gap-2">{status === 'PASS' ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <Target className="w-4 h-4 text-amber-600" />}<span className="font-semibold text-sm text-ink-100">{status === 'PASS' ? 'Mieści się w ramie' : 'Wymaga skrótu / decyzji'}</span></div><p className="mt-1 text-xs text-ink-400">{fit.output_words} słów · {fit.fit.lines}/{fit.fit.capacity_lines} linii · wolne {fit.fit.free_space_mm.toFixed(1)} mm</p></div>
            <label className="block"><span className="text-[10px] uppercase font-mono tracking-wider text-ink-500">Propozycja</span><textarea readOnly value={fit.text} className="mt-2 w-full min-h-[190px] rounded-lg border border-ink-700 bg-paper-100 p-3 text-sm leading-relaxed text-ink-950" /></label>
            {fit.needs_more_source && <p className="text-xs text-amber-700 bg-amber-50 rounded p-2">Źródło jest za krótkie na żądany limit. Nie dopisałem niepotwierdzonych zdań.</p>}
            {fit.warnings.length > 0 && <div className="space-y-1">{fit.warnings.map((warning) => <p key={warning} className="text-xs text-ink-400">• {warning}</p>)}</div>}
            <div className="flex items-center gap-2"><Button variant="editorial" onClick={applyFit} disabled={status !== 'PASS' || busy} isLoading={busy} leftIcon={<Copy className="w-3.5 h-3.5" />}>Zastosuj do sceny</Button><span className="inline-flex items-center gap-1 text-[10px] text-ink-500"><LockKeyhole className="w-3 h-3" /> blokady są zachowane</span></div>
          </>}
        </Card>
      </div>
    </div>
  );
};
