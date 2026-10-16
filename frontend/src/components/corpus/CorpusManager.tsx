import React, { useState, useEffect } from 'react';
import { useProject } from '../../context/ProjectContext';
import { CorpusPage } from '../../types/corpus';
import { api } from '../../api/client';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  FileStack,
  Upload,
  Layers,
  Sparkles,
  Trash2,
  CheckCircle2,
  Scan,
  Eye,
  BarChart3,
  RefreshCw,
  ArrowRight,
} from 'lucide-react';
import { CreationStepper } from '../common/CreationStepper';

export const CorpusManager: React.FC = () => {
  const { activeProject, reloadDNA, addToast, setActiveTab, setDnaSubTab } = useProject();
  const [corpusPages, setCorpusPages] = useState<CorpusPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<CorpusPage | null>(null);
  const [previewUnavailable, setPreviewUnavailable] = useState(false);
  const uploadInput = React.useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isLearning, setIsLearning] = useState(false);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);

  useEffect(() => {
    if (activeProject) {
      api.getCorpusPages(activeProject.id).then((pages) => {
        setCorpusPages(pages);
        setSelectedPage(pages[0] || null);
      }).catch((error) => addToast({ type: 'error', title: 'Nie udało się wczytać przykładów', message: error instanceof Error ? error.message : 'Nie udało się pobrać stron.' }));
    }
  }, [activeProject, addToast]);

  useEffect(() => setPreviewUnavailable(false), [selectedPage?.id]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !activeProject) return;

    setIsUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const uploaded = await api.uploadCorpusPage(activeProject.id, files[i]);
        setCorpusPages((prev) => [uploaded, ...prev]);
        setSelectedPage(uploaded);
      }
      addToast({
        type: 'success',
        title: 'Przykładowa strona dodana',
        message: 'Program przeanalizował jej układ.',
      });
    } catch (err) {
      addToast({
        type: 'error',
        title: 'Błąd wysyłania',
        message: 'Nie udało się przetworzyć pliku strony.',
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleLearnDNA = async () => {
    if (!activeProject) return;
    setIsLearning(true);
    try {
      await api.learnDNAFromCorpus(activeProject.id);
      await reloadDNA();
      addToast({
        type: 'success',
        title: 'Styl gazety zaktualizowany',
        message: 'Program rozpoznał styl. Przejdź do wgrania logo gazety.',
      });
      setDnaSubTab('masthead');
      setActiveTab('dna');
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się zastosować przykładów', message: error instanceof Error ? error.message : 'Spróbuj ponownie.' });
    } finally {
      setIsLearning(false);
    }
  };

  const handleDeletePage = async (pageId: string) => {
    if (!activeProject) return;
    await api.deleteCorpusPage(activeProject.id, pageId);
    setCorpusPages((prev) => prev.filter((p) => p.id !== pageId));
    if (selectedPage?.id === pageId) {
      setSelectedPage(corpusPages.find((p) => p.id !== pageId) || null);
    }
    addToast({
      type: 'info',
      title: 'Strona usunięta',
      message: 'Przykład usunięty z listy.',
    });
  };

  if (!activeProject) return null;

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <CreationStepper currentStep={1} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-blue-400 font-bold">
              Krok opcjonalny · pokaż styl
            </span>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Przykładowe strony
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Dodaj 2–10 stron, których wygląd Ci się podoba. Program rozpozna ich styl, ale ułoży nową stronę od podstaw.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <>
            <input
              ref={uploadInput}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              variant="secondary"
              isLoading={isUploading}
              leftIcon={<Upload className="w-4 h-4" />}
              onClick={() => uploadInput.current?.click()}
            >
              Dodaj strony (PDF/obraz)
            </Button>
          </>

          <Button
            variant="editorial"
            isLoading={isLearning}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLearning ? 'animate-spin' : ''}`} />}
            onClick={handleLearnDNA}
          >
            Zastosuj styl z przykładów
          </Button>

          <Button
            variant="primary"
            rightIcon={<ArrowRight className="w-4 h-4" />}
            onClick={() => {
              setDnaSubTab('masthead');
              setActiveTab('dna');
            }}
          >
            Krok 2: Winieta i logo →
          </Button>
        </div>
      </div>

      {/* Main Grid: Thumbnails Tray + Large Feature Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Col: Pages List / Upload Dropzone (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-ink-400 font-semibold">
              Dodane przykłady ({corpusPages.length})
            </span>
            <span className="text-[10px] text-ink-500 font-mono">Projekt {activeProject.name}</span>
          </div>

          <div className="space-y-3 max-h-[680px] overflow-y-auto pr-1">
            {corpusPages.map((page) => {
              const isSelected = selectedPage?.id === page.id;
              return (
                <div
                  key={page.id}
                  onClick={() => setSelectedPage(page)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-ink-800 border-editorial-crimson ring-1 ring-editorial-crimson/50'
                      : 'bg-ink-900/80 border-ink-800 hover:border-ink-700'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-16 bg-paper-200 rounded border border-ink-700 flex items-center justify-center overflow-hidden shadow-xs shrink-0">
                      {page.thumbnailUrl ? (
                        <img src={page.thumbnailUrl} alt={page.fileName} className="w-full h-full object-cover" />
                      ) : (
                        <FileStack className="w-6 h-6 text-ink-700" />
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-ink-100 line-clamp-1">{page.fileName}</p>
                      <p className="text-[10px] text-ink-400 font-mono">
                        Strona {page.pageNumber} • {page.fileType.toUpperCase()} • {(page.fileSize / 1024 / 1024).toFixed(1)} MB
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <Badge variant="success" size="sm">
                          {page.features.detectedColumns} kolumn
                        </Badge>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeletePage(page.id);
                    }}
                    className="p-1.5 text-ink-500 hover:text-red-400 hover:bg-ink-700/60 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })}

            {corpusPages.length === 0 && (
              <div className="p-8 border-2 border-dashed border-ink-800 rounded-xl text-center text-ink-400">
                <Upload className="w-8 h-8 mx-auto mb-2 text-ink-500" />
                <p className="text-xs font-medium">Brak wgranych stron</p>
                <p className="text-[10px] text-ink-500 mt-1">Dodaj 2–10 stron, aby pokazać programowi ulubiony styl.</p>
              </div>
            )}
          </div>

          <div className="p-4 bg-ink-900/90 border border-ink-800 rounded-xl space-y-2">
            <p className="text-xs text-ink-300 font-medium">
              Chcesz przejść do logo i winiety?
            </p>
            <p className="text-[11px] text-ink-500">
              Styl z przykładów jest opcjonalny. W kolejnym kroku wgrasz znak swojej gazety.
            </p>
            <Button
              variant="editorial"
              className="w-full justify-center mt-2"
              rightIcon={<ArrowRight className="w-4 h-4" />}
              onClick={() => {
                setDnaSubTab('masthead');
                setActiveTab('dna');
              }}
            >
              Przejdź dalej: Wgraj logo (Krok 2) →
            </Button>
          </div>
        </div>

        {/* Right Col: Interactive Feature & Layout Inspector (8 cols) */}
        <div className="lg:col-span-8">
          {selectedPage ? (
            <div className="space-y-6">
              <Card>
                <div className="flex items-center justify-between pb-4 border-b border-ink-800 mb-4">
                  <div>
                    <h3 className="font-headline font-bold text-base text-ink-100">
                      Jak zbudowana jest ta strona
                    </h3>
                    <p className="text-xs text-ink-400 font-mono">{selectedPage.fileName}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant={showBoundingBoxes ? 'editorial' : 'outline'}
                      size="sm"
                      leftIcon={<Scan className="w-3.5 h-3.5" />}
                      onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
                    >
                      {showBoundingBoxes ? 'Ramki analizy: włączone' : 'Ramki analizy: wyłączone'}
                    </Button>
                  </div>
                </div>

                <div
                  className="relative max-w-full w-fit mx-auto bg-paper-100 rounded-lg border border-paper-300 shadow-2xl overflow-hidden select-none"
                  style={{ aspectRatio: `${selectedPage.widthMm} / ${selectedPage.heightMm}`, height: 500 }}
                >
                  {previewUnavailable || !selectedPage.previewUrl ? (
                    <div className="h-full min-w-[260px] flex flex-col items-center justify-center gap-2 px-6 text-center text-ink-700">
                      <FileStack className="w-8 h-8" />
                      <p className="text-sm">Podgląd tej strony jest niedostępny.</p>
                      <p className="text-xs">Podsumowanie układu jest widoczne poniżej.</p>
                    </div>
                  ) : (
                    <img
                      src={selectedPage.previewUrl}
                      alt={`Strona korpusu: ${selectedPage.fileName}`}
                      onError={() => setPreviewUnavailable(true)}
                      className="block w-full h-full object-contain"
                    />
                  )}
                  {showBoundingBoxes && !previewUnavailable && selectedPage.boundingBoxes.map((box, index) => (
                    <div
                      key={index}
                      className="absolute border border-editorial-crimson bg-editorial-crimson/10 pointer-events-none rounded-xs"
                      style={{
                        left: `${(box.x / selectedPage.widthMm) * 100}%`,
                        top: `${(box.y / selectedPage.heightMm) * 100}%`,
                        width: `${(box.width / selectedPage.widthMm) * 100}%`,
                        height: `${(box.height / selectedPage.heightMm) * 100}%`,
                      }}
                    >
                      <span className="absolute top-0 left-0 bg-editorial-crimson text-ink-100 text-[8px] font-mono px-1 uppercase">
                        {box.role} ({Math.round(box.confidence * 100)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Tabela zmierzonych cech */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card className="text-center p-3">
                  <span className="text-[10px] font-mono uppercase text-ink-400 block">Podział na kolumny</span>
                  <span className="text-lg font-mono font-bold text-ink-100">
                    {selectedPage.features.detectedColumns} kolumn ({selectedPage.features.detectedGutterMm} mm)
                  </span>
                </Card>

                <Card className="text-center p-3">
                  <span className="text-[10px] font-mono uppercase text-ink-400 block">Największy nagłówek</span>
                  <span className="text-lg font-mono font-bold text-editorial-ochre">
                    {selectedPage.features.maxHeadlineSizePt} pt
                  </span>
                </Card>

                <Card className="text-center p-3">
                  <span className="text-[10px] font-mono uppercase text-ink-400 block">Udział zdjęć</span>
                  <span className="text-lg font-mono font-bold text-ink-100">
                    {(selectedPage.features.photoRatio * 100).toFixed(0)}% zdjęć
                  </span>
                </Card>

                <Card className="text-center p-3">
                  <span className="text-[10px] font-mono uppercase text-ink-400 block">Wolna przestrzeń</span>
                  <span className="text-lg font-mono font-bold text-emerald-300">
                    {(selectedPage.features.whiteSpaceRatio * 100).toFixed(0)}%
                  </span>
                </Card>
              </div>
            </div>
          ) : (
            <Card className="p-12 text-center text-ink-400">
              Wybierz przykładową stronę z listy, aby zobaczyć analizę jej układu.
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
