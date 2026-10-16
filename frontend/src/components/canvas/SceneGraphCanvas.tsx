import React, { useState, useRef } from 'react';
import { useProject } from '../../context/ProjectContext';
import { SceneGraphElement, RectFrame, ElementDelta } from '../../types/sceneGraph';
import { api } from '../../api/client';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Slider } from '../common/Slider';
import { Toggle } from '../common/Toggle';
import {
  Inspect,
  Grid,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  Layers,
  Save,
  RotateCcw,
  Sparkles,
  Scissors,
  CheckCircle2,
  Move,
  Eye,
  Sliders,
  Flame,
  Bot,
  Wand2,
  AlertCircle,
  Wrench,
  History,
} from 'lucide-react';

export const SceneGraphCanvas: React.FC = () => {
  const {
    selectedCandidate,
    setSelectedCandidate,
    currentRun,
    setCurrentRun,
    activeProject,
    dna,
    addToast,
    reloadTasteMetrics,
  } = useProject();

  const [elements, setElements] = useState<SceneGraphElement[]>(
    selectedCandidate ? JSON.parse(JSON.stringify(selectedCandidate.sceneGraph.elements)) : []
  );
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showContours, setShowContours] = useState<boolean>(true);
  const [showReadingOrder, setShowReadingOrder] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [deltas, setDeltas] = useState<ElementDelta[]>([]);
  const [isLoggingDelta, setIsLoggingDelta] = useState<boolean>(false);
  const [isApplyingAiFixes, setIsApplyingAiFixes] = useState<boolean>(false);
  const dragRef = useRef<{ id: string; startX: number; startY: number; frame: RectFrame } | null>(null);

  // Sync if candidate changes
  React.useEffect(() => {
    if (selectedCandidate) {
      setElements(JSON.parse(JSON.stringify(selectedCandidate.sceneGraph.elements)));
      setSelectedElementId(selectedCandidate.sceneGraph.elements[0]?.id || null);
      setDeltas([]);
    }
  }, [selectedCandidate]);

  if (!selectedCandidate || !activeProject || !dna) {
    return (
      <div className="p-12 text-center text-ink-400">
        Nie wybrano strony do poprawiania. Otwórz wariant w galerii.
      </div>
    );
  }

  const selectedElement = elements.find((e) => e.id === selectedElementId) || null;
  const pageFormat = selectedCandidate.sceneGraph.pageFormat;

  const handleUpdateFrame = (id: string, updates: Partial<RectFrame>) => {
    const prevElem = elements.find((e) => e.id === id);
    if (!prevElem) return;

    const previousFrame = { ...prevElem.frame };
    const newFrame = { ...prevElem.frame, ...updates };

    setElements((prev) =>
      prev.map((elem) => (elem.id === id ? { ...elem, frame: newFrame } : elem))
    );

    // Record delta
    const delta: ElementDelta = {
      elementId: id,
      previousFrame,
      newFrame,
      changeType: 'resize',
      timestamp: new Date().toISOString(),
    };
    setDeltas((prev) => [...prev, delta]);
  };

  const handleUpdateStyle = (id: string, styleUpdates: Partial<SceneGraphElement['style']>) => {
    setElements((prev) =>
      prev.map((elem) =>
        elem.id === id ? { ...elem, style: { ...elem.style, ...styleUpdates } } : elem
      )
    );
  };

  const handlePointerDown = (event: React.PointerEvent, element: SceneGraphElement) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    dragRef.current = { id: element.id, startX: event.clientX, startY: event.clientY, frame: { ...element.frame } };
    setSelectedElementId(element.id);
  };

  const handlePointerMove = (event: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    // The preview page is 580px wide at 100%; convert screen movement back to mm.
    const scale = (580 * (zoomLevel / 100)) / pageFormat.widthMm;
    handleUpdateFrame(drag.id, {
      x: Math.max(0, Math.min(pageFormat.widthMm - drag.frame.width, drag.frame.x + (event.clientX - drag.startX) / scale)),
      y: Math.max(0, Math.min(pageFormat.heightMm - drag.frame.height, drag.frame.y + (event.clientY - drag.startY) / scale)),
    });
  };

  const handlePointerUp = () => { dragRef.current = null; };

  const handleSaveAndTrain = async () => {
    if (!activeProject || !selectedCandidate) return;
    setIsLoggingDelta(true);
    try {
      const updatedScene = { ...selectedCandidate.sceneGraph, elements };
      await api.saveCandidate(selectedCandidate.id, updatedScene);
      await api.logEditDelta(activeProject.id, selectedCandidate.id, deltas);
      await reloadTasteMetrics();
      addToast({
        type: 'success',
        title: 'Zmiany strony zapisane',
        message: `Zapisano ${deltas.length} poprawek układu.`,
      });
      setDeltas([]);
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Nie udało się zapisać zmian',
        message: 'Spróbuj ponownie.',
      });
    } finally {
      setIsLoggingDelta(false);
    }
  };

  const critique = selectedCandidate.metadata?.visual_critique || selectedCandidate.visualReview;
  const trace = selectedCandidate.metadata?.art_director_trace;
  const topFixes: string[] = critique?.top_3_fixes || [];
  const defects: string[] = (critique as any)?.defects || (selectedCandidate.visualReview?.dead_zones ? selectedCandidate.visualReview.dead_zones.map((z: string) => `D28: martwa strefa ${z}`) : []);

  const handleApplyAiFixes = async (fixesToApply?: string[]) => {
    if (!activeProject || !selectedCandidate) return;
    const fixes = fixesToApply && fixesToApply.length > 0 ? fixesToApply : topFixes;
    if (fixes.length === 0) {
      addToast({
        type: 'warning',
        title: 'Brak poprawek do zastosowania',
        message: 'Krytyk nie zaproponował żadnych poprawek dla tego wariantu.',
      });
      return;
    }
    setIsApplyingAiFixes(true);
    try {
      const composer = selectedCandidate.metadata?.composer_name || 'framed_cover:wukadka';
      const genes = selectedCandidate.metadata?.composer_genes || {};
      const updatedCandidate = await api.applyArtDirectFixes(
        activeProject.id,
        fixes,
        genes,
        composer
      );
      setSelectedCandidate(updatedCandidate);
      setElements(JSON.parse(JSON.stringify(updatedCandidate.sceneGraph.elements)));
      if (currentRun) {
        const updatedCandidates = currentRun.candidates.map((c) =>
          c.id === updatedCandidate.id ? updatedCandidate : c
        );
        setCurrentRun({ ...currentRun, candidates: updatedCandidates });
      }
      addToast({
        type: 'success',
        title: 'Zastosowano poprawki AI',
        message: `Zaktualizowano układ (${fixes.length} poprawek).`,
      });
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Nie udało się zastosować poprawek',
        message: e instanceof Error ? e.message : 'Błąd silnika.',
      });
    } finally {
      setIsApplyingAiFixes(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-ink-900 border border-ink-800 p-3.5 rounded-xl shadow-lg">
        {/* Left: Candidate Info & Delta Counter */}
        <div className="flex items-center gap-3">
          <Badge variant="accent" size="sm">
            Wariant {selectedCandidate.candidateNumber}
          </Badge>
          <span className="text-xs font-mono text-ink-300">
            {pageFormat.widthMm} × {pageFormat.heightMm} mm · {pageFormat.columns} kolumn
          </span>
          {deltas.length > 0 && (
            <Badge variant="warning" size="sm">
              {deltas.length} niezapisanych zmian
            </Badge>
          )}
        </div>

        {/* Middle: Overlay Toggles */}
        <div className="flex items-center gap-1.5 bg-ink-950 p-1 rounded-lg border border-ink-800 text-xs font-mono">
          <button
            onClick={() => setShowGrid(!showGrid)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showGrid ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Siatka
          </button>
          <button
            onClick={() => setShowBoxes(!showBoxes)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showBoxes ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Ramki
          </button>
          <button
            onClick={() => setShowContours(!showContours)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showContours ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Obrys zdjęć
          </button>
          <button
            onClick={() => setShowReadingOrder(!showReadingOrder)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showReadingOrder ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Kolejność
          </button>
        </div>

        {/* Right: Zoom & Save Action */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-ink-950 p-1 rounded-lg border border-ink-800">
            <button
              onClick={() => setZoomLevel((z) => Math.max(50, z - 10))}
              className="p-1 text-ink-400 hover:text-white"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-xs font-mono text-ink-300 w-12 text-center">{zoomLevel}%</span>
            <button
              onClick={() => setZoomLevel((z) => Math.min(150, z + 10))}
              className="p-1 text-ink-400 hover:text-white"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          <Button
            variant="editorial"
            size="sm"
            disabled={deltas.length === 0}
            isLoading={isLoggingDelta}
            leftIcon={<Save className="w-3.5 h-3.5" />}
            onClick={handleSaveAndTrain}
          >
            Zapisz poprawki
          </Button>
        </div>
      </div>

      {/* Main Grid: Interactive Canvas (8 cols) + Property Inspector (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Interactive Canvas Viewer (8 cols) */}
        <div className="lg:col-span-8 bg-ink-950 border border-ink-800 rounded-xl p-6 flex items-center justify-center overflow-auto min-h-[620px] shadow-2xl relative">
          <div
            className="relative bg-paper-100 rounded shadow-page-elevated border border-paper-300 transition-transform origin-top select-none"
            style={{
              width: `${(pageFormat.widthMm / 315) * 580 * (zoomLevel / 100)}px`,
              height: `${(pageFormat.heightMm / 470) * 860 * (zoomLevel / 100)}px`,
              backgroundColor: dna.palette.backgroundTone || '#f9f6ef',
            }}
          >
            {/* Modular Grid Overlay */}
            {showGrid && (
              <div className="absolute inset-0 pointer-events-none p-[5%] grid grid-cols-5 gap-2 opacity-20">
                {Array.from({ length: pageFormat.columns }).map((_, i) => (
                  <div key={i} className="h-full border-x border-dashed border-ink-50" />
                ))}
              </div>
            )}

            {/* Elements Layer */}
            {elements.map((elem) => {
              const isSelected = elem.id === selectedElementId;
              const leftPct = (elem.frame.x / pageFormat.widthMm) * 100;
              const topPct = (elem.frame.y / pageFormat.heightMm) * 100;
              const widthPct = (elem.frame.width / pageFormat.widthMm) * 100;
              const heightPct = (elem.frame.height / pageFormat.heightMm) * 100;

              return (
                <div
                  key={elem.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedElementId(elem.id);
                  }}
                  onPointerDown={(e) => handlePointerDown(e, elem)}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  className={`absolute transition-all cursor-pointer ${
                    isSelected
                      ? 'ring-2 ring-editorial-crimson ring-offset-1 z-30 shadow-lg'
                      : showBoxes
                      ? 'hover:ring-1 hover:ring-ink-500'
                      : ''
                  }`}
                  style={{
                    left: `${leftPct}%`,
                    top: `${topPct}%`,
                    width: `${widthPct}%`,
                    height: `${heightPct}%`,
                    zIndex: elem.zIndex || 1,
                    backgroundColor: elem.style.backgroundColor || 'transparent',
                    borderColor: elem.style.borderColor || (showBoxes ? '#c1121f20' : 'transparent'),
                    borderWidth: elem.style.borderWidthPt ? `${elem.style.borderWidthPt}px` : (showBoxes ? '1px' : '0px'),
                  }}
                >
                  {/* Element Content Render */}
                  {elem.role === 'masthead' && (
                    <div className="w-full h-full flex items-center justify-center border-b-2 border-ink-50">
                      <h1 className="text-2xl font-headline font-black text-ink-50 uppercase tracking-tight">
                        {elem.content}
                      </h1>
                    </div>
                  )}

                  {elem.role === 'kicker' && (
                    <div className="text-[9px] font-mono font-bold uppercase text-editorial-crimson tracking-wider truncate">
                      {elem.content}
                    </div>
                  )}

                  {elem.role === 'headline' && (
                    <h2
                      className="font-headline font-black text-ink-50 leading-tight"
                      style={{
                        fontFamily: elem.style.fontFamily || 'Fraunces',
                        fontSize: `${(elem.style.fontSizePt || 36) * 0.45 * (zoomLevel / 100)}px`,
                        color: elem.style.color || '#151821',
                      }}
                    >
                      {elem.content}
                    </h2>
                  )}

                  {elem.role === 'deck' && (
                    <p className="text-[10px] text-ink-200 font-sans leading-snug" style={{ color: elem.style.color || '#303646' }}>
                      {elem.content}
                    </p>
                  )}

                  {elem.role === 'image' && (
                    <div className="w-full h-full relative overflow-hidden rounded">
                      <img
                        src={elem.content}
                        alt="Zdjęcie na stronie"
                        className="w-full h-full object-cover"
                      />
                      {elem.treatment?.isCutout && showContours && (
                        <div className="absolute inset-0 border-2 border-dashed border-purple-500 bg-purple-500/10 flex items-end p-1">
                          <span className="text-[8px] font-mono text-purple-900 bg-white/90 px-1 rounded uppercase font-bold">
                            Tekst wokół wyciętego zdjęcia (4 mm)
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {elem.role === 'body' && (
                    <p className="text-[8px] text-ink-50 text-justify leading-snug font-sans line-clamp-12" style={{ color: elem.style.color || '#151821' }}>
                      {elem.content}
                    </p>
                  )}

                  {elem.role === 'pullquote' && (
                    <div className="w-full h-full p-2 border-y border-editorial-crimson flex items-center justify-center text-center">
                      <p className="font-headline font-bold text-xs text-editorial-crimson italic">
                        {elem.content}
                      </p>
                    </div>
                  )}

                  {elem.role === 'rule-line' && (
                    <div
                      className="w-full h-full"
                      style={{ backgroundColor: elem.style.backgroundColor || '#0b0f14' }}
                    />
                  )}

                  {elem.role === 'folio' && (
                    <div className="text-[7px] font-mono text-ink-600 uppercase text-center">
                      {elem.content}
                    </div>
                  )}

                  {/* Bounding Box Role Label */}
                  {showBoxes && (
                    <span className="absolute -top-3 left-0 bg-ink-900 text-white text-[7px] font-mono px-1 rounded shadow-xs opacity-70">
                      {elem.role}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Property & Scene Graph Inspector Sidebar (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <Card className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <Inspect className="w-4 h-4 text-editorial-crimson" />
                <h3 className="font-headline font-bold text-sm text-white">
                  Ustawienia wybranego elementu
                </h3>
              </div>
              {selectedElement && (
                <Badge variant="accent" size="sm">
                  {selectedElement.role.toUpperCase()}
                </Badge>
              )}
            </div>

            {selectedElement ? (
              <div className="space-y-4">
                {/* Frame Coordinates (x, y, w, h in mm) */}
                <div>
                  <span className="text-[10px] font-mono uppercase font-bold text-ink-400 block mb-2">
                    Położenie i rozmiar (mm)
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <Slider
                      label="Od lewej"
                      value={Math.round(selectedElement.frame.x)}
                      min={0}
                      max={pageFormat.widthMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { x: v })}
                    />
                    <Slider
                      label="Od góry"
                      value={Math.round(selectedElement.frame.y)}
                      min={0}
                      max={pageFormat.heightMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { y: v })}
                    />
                    <Slider
                      label="Szerokość"
                      value={Math.round(selectedElement.frame.width)}
                      min={10}
                      max={pageFormat.widthMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { width: v })}
                    />
                    <Slider
                      label="Wysokość"
                      value={Math.round(selectedElement.frame.height)}
                      min={5}
                      max={pageFormat.heightMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { height: v })}
                    />
                  </div>
                </div>

                {/* Typography specs if text */}
                {selectedElement.style.fontSizePt && (
                  <div className="pt-3 border-t border-ink-800 space-y-3">
                    <span className="text-[10px] font-mono uppercase font-bold text-ink-400 block">
                      Rozmiar tekstu
                    </span>
                    <Slider
                      label="Wielkość pisma"
                      value={selectedElement.style.fontSizePt}
                      min={8}
                      max={60}
                      step={1}
                      unit=" pt"
                      onChange={(v) => handleUpdateStyle(selectedElement.id, { fontSizePt: v })}
                    />
                  </div>
                )}

                {/* Transgressions applied */}
                <div className="pt-3 border-t border-ink-800">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono uppercase font-bold text-ink-400">
                      Efekty układu
                    </span>
                    <Badge variant="score" size="sm">
                      +{selectedElement.tensionCost} pkt napięcia
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    {selectedElement.transgressionsApplied.length > 0 ? (
                      selectedElement.transgressionsApplied.map((tr, i) => (
                        <div
                          key={i}
                          className="px-2 py-1 bg-ink-950 rounded border border-ink-800 text-[11px] font-mono text-editorial-ochre flex items-center gap-1.5"
                        >
                          <Flame className="w-3 h-3 text-editorial-crimson" />
                          <span>{tr}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-[11px] text-ink-500 font-mono">Conforms strictly to baseline grid</p>
                    )}
                  </div>
                </div>

                {/* Content editor */}
                <div className="pt-3 border-t border-ink-800">
                  <label className="block text-[10px] font-mono uppercase font-bold text-ink-400 mb-1">
                    Text / Content Value
                  </label>
                  <textarea
                    rows={3}
                    value={selectedElement.content}
                    onChange={(e) => {
                      const newContent = e.target.value;
                      setElements((prev) =>
                        prev.map((elem) =>
                          elem.id === selectedElement.id ? { ...elem, content: newContent } : elem
                        )
                      );
                    }}
                    className="w-full px-2.5 py-1.5 bg-ink-950 border border-ink-700 rounded text-xs text-ink-200 resize-none font-sans"
                  />
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-ink-400">
                Click any element on the canvas to inspect its geometry, styling, and transgression score.
              </div>
            )}
          </Card>

          {/* AI Art Director & Review Panel */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-ink-800">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-emerald-400" />
                <h3 className="font-headline font-bold text-sm text-white">
                  AI Redaktor Techniczny & Pętla
                </h3>
              </div>
              {critique?.status && (
                <Badge
                  variant={
                    critique.status === 'candidate_for_editor' || critique.status === 'PASS'
                      ? 'success'
                      : 'warning'
                  }
                  size="sm"
                >
                  {critique.status === 'candidate_for_editor'
                    ? 'DO OCENY'
                    : critique.status === 'PASS'
                    ? 'ZAAKCEPTOWANE'
                    : 'DO POPRAWY'}
                </Badge>
              )}
            </div>

            {/* Critique Score & Defect summary */}
            <div className="space-y-3">
              {typeof critique?.score === 'number' && (
                <div className="flex items-center justify-between text-xs font-mono bg-ink-950 p-2 rounded border border-ink-800">
                  <span className="text-ink-400">Ocena krytyka wizualnego</span>
                  <span className="font-bold text-emerald-400">
                    {(critique.score <= 1 ? critique.score * 100 : critique.score).toFixed(0)} / 100
                  </span>
                </div>
              )}

              {/* Defekty D01-D30 */}
              <div>
                <span className="text-[10px] font-mono uppercase font-bold text-ink-400 block mb-1.5">
                  Wykryte defekty (katalog D01–D30)
                </span>
                {defects.length > 0 ? (
                  <div className="space-y-1.5">
                    {defects.map((defect, i) => (
                      <div
                        key={i}
                        className="px-2 py-1 bg-rose-950/40 border border-rose-800/60 rounded text-[11px] font-mono text-rose-300 flex items-start gap-1.5"
                      >
                        <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                        <span>{defect}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-ink-500 font-mono flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    Brak krytycznych defektów geometrii
                  </p>
                )}
              </div>

              {/* Proponowane poprawki */}
              <div>
                <span className="text-[10px] font-mono uppercase font-bold text-ink-400 block mb-1.5">
                  Proponowane poprawki układu
                </span>
                {topFixes.length > 0 ? (
                  <div className="space-y-1.5">
                    {topFixes.map((fix, i) => (
                      <div
                        key={i}
                        className="px-2 py-1 bg-ink-950 border border-ink-800 rounded text-[11px] font-mono text-amber-300 flex items-center justify-between gap-1.5"
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <Wrench className="w-3 h-3 text-amber-400 shrink-0" />
                          <span className="truncate">{fix}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleApplyAiFixes([fix])}
                          disabled={isApplyingAiFixes}
                          className="text-[10px] underline text-ink-400 hover:text-white shrink-0 cursor-pointer"
                        >
                          Zastosuj
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-ink-500 font-mono">Brak oczekujących poprawek</p>
                )}
              </div>

              {/* Action Button: Apply all fixes */}
              {topFixes.length > 0 && (
                <Button
                  variant="editorial"
                  size="sm"
                  className="w-full mt-2"
                  disabled={isApplyingAiFixes}
                  isLoading={isApplyingAiFixes}
                  leftIcon={<Wand2 className="w-3.5 h-3.5" />}
                  onClick={() => handleApplyAiFixes()}
                >
                  Zastosuj poprawki AI ({topFixes.length})
                </Button>
              )}

              {/* Loop trace summary if present */}
              {trace && trace.length > 0 && (
                <div className="pt-3 border-t border-ink-800 space-y-2">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase font-bold text-ink-400">
                    <History className="w-3 h-3 text-editorial-crimson" />
                    <span>Ślad rund pętli AI ({trace.length})</span>
                  </div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {trace.map((step, idx) => (
                      <div
                        key={idx}
                        className="p-1.5 bg-ink-950 rounded border border-ink-800/80 text-[10px] font-mono flex items-center justify-between text-ink-400"
                      >
                        <span>Runda {step.round}</span>
                        <Badge
                          variant={step.gate_passed ? 'success' : 'danger'}
                          size="sm"
                        >
                          {step.gate_passed ? 'GATE PASS' : 'GATE FAIL'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
