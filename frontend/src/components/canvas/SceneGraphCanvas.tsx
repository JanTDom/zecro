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
} from 'lucide-react';

export const SceneGraphCanvas: React.FC = () => {
  const { selectedCandidate, activeProject, dna, addToast, reloadTasteMetrics } = useProject();

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
        No candidate layout selected for inspection. Please choose a variant from the gallery.
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
        title: 'Layout saved & taste signal logged',
        message: `${deltas.length} spatial adjustment deltas recorded into taste preference loop.`,
      });
      setDeltas([]);
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Delta Save Failed',
        message: 'Could not log adjustments.',
      });
    } finally {
      setIsLoggingDelta(false);
    }
  };

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto space-y-4 animate-fade-in">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-ink-900 border border-ink-800 p-3.5 rounded-xl shadow-lg">
        {/* Left: Candidate Info & Delta Counter */}
        <div className="flex items-center gap-3">
          <Badge variant="accent" size="sm">
            Variant #{selectedCandidate.candidateNumber}
          </Badge>
          <span className="text-xs font-mono text-ink-300">
            {pageFormat.widthMm} × {pageFormat.heightMm} mm ({pageFormat.columns} cols)
          </span>
          {deltas.length > 0 && (
            <Badge variant="warning" size="sm">
              {deltas.length} Edits Pending
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
            Grid
          </button>
          <button
            onClick={() => setShowBoxes(!showBoxes)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showBoxes ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Boxes
          </button>
          <button
            onClick={() => setShowContours(!showContours)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showContours ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Cutout Wrap
          </button>
          <button
            onClick={() => setShowReadingOrder(!showReadingOrder)}
            className={`px-2.5 py-1 rounded transition-colors ${
              showReadingOrder ? 'bg-ink-800 text-white font-bold' : 'text-ink-400 hover:text-white'
            }`}
          >
            Flow
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
            Record Edit Delta
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
                        alt="Photo"
                        className="w-full h-full object-cover"
                      />
                      {elem.treatment?.isCutout && showContours && (
                        <div className="absolute inset-0 border-2 border-dashed border-purple-500 bg-purple-500/10 flex items-end p-1">
                          <span className="text-[8px] font-mono text-purple-900 bg-white/90 px-1 rounded uppercase font-bold">
                            Cutout Silhouette Wrap (4mm)
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
                  Element Scene Graph Inspector
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
                    Bounding Box Frame (mm)
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <Slider
                      label="X Offset"
                      value={Math.round(selectedElement.frame.x)}
                      min={0}
                      max={pageFormat.widthMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { x: v })}
                    />
                    <Slider
                      label="Y Offset"
                      value={Math.round(selectedElement.frame.y)}
                      min={0}
                      max={pageFormat.heightMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { y: v })}
                    />
                    <Slider
                      label="Width"
                      value={Math.round(selectedElement.frame.width)}
                      min={10}
                      max={pageFormat.widthMm}
                      unit=" mm"
                      onChange={(v) => handleUpdateFrame(selectedElement.id, { width: v })}
                    />
                    <Slider
                      label="Height"
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
                      Typography Override
                    </span>
                    <Slider
                      label="Kegel Size"
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
                      Applied Transgressions
                    </span>
                    <Badge variant="score" size="sm">
                      +{selectedElement.tensionCost} pt tension
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
        </div>
      </div>
    </div>
  );
};
