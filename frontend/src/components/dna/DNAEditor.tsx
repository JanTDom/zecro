import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { TitleDNA, TypographyStyle, TransgressionRule } from '../../types/dna';
import { api } from '../../api/client';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Slider } from '../common/Slider';
import { Toggle } from '../common/Toggle';
import { MastheadEditor } from './MastheadEditor';
import {
  Sliders,
  Save,
  Layers,
  Type,
  Palette,
  Camera,
  Flame,
  RotateCcw,
  Sparkles,
  Eye,
  ArrowRight,
  FileUp,
} from 'lucide-react';
import { CreationStepper } from '../common/CreationStepper';

export const DNAEditor: React.FC = () => {
  const { activeProject, dna, reloadDNA, addToast, setActiveTab, dnaSubTab, setDnaSubTab } = useProject();
  const [localDna, setLocalDna] = useState<TitleDNA | null>(dna ? JSON.parse(JSON.stringify(dna)) : null);
  const activeSubTab = dnaSubTab;
  const setActiveSubTab = setDnaSubTab;
  const [isSaving, setIsSaving] = useState(false);
  const [isImportingIdml, setIsImportingIdml] = useState(false);
  const idmlInputRef = React.useRef<HTMLInputElement>(null);

  // Sync if dna updates
  React.useEffect(() => {
    if (dna) setLocalDna(JSON.parse(JSON.stringify(dna)));
  }, [dna]);

  if (!activeProject || !localDna) {
    return <div className="p-8 text-center text-ink-400">Nie wczytano zasad stylu gazety.</div>;
  }

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.updateTitleDNA(activeProject.id, localDna);
      await reloadDNA();
      addToast({
        type: 'success',
        title: 'Styl gazety zapisany',
        message: `Zapisano wersję ${localDna.version + 1}. Nowe strony użyją tych ustawień.`,
      });
    } catch (e) {
      addToast({
        type: 'error',
        title: 'Nie udało się zapisać',
        message: 'Spróbuj ponownie zapisać ustawienia stylu.',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleImportIdml = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsImportingIdml(true);
    try {
      const updated = await api.importIdmlDna(activeProject.id, file);
      setLocalDna(updated);
      await reloadDNA();
      addToast({
        type: 'success',
        title: 'Zaimportowano DNA z InDesign (.idml)',
        message: `Wyodrębniono siatkę, kolumny i style akapitowe z pliku ${file.name}.`,
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Błąd importu IDML',
        message: err?.message || 'Nie udało się przetworzyć pliku .idml.',
      });
    } finally {
      setIsImportingIdml(false);
      if (e.target) e.target.value = '';
    }
  };

  const handleTypographyChange = (key: keyof TitleDNA['typography'], styleKey: keyof TypographyStyle, value: any) => {
    setLocalDna((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        typography: {
          ...prev.typography,
          [key]: {
            ...prev.typography[key],
            [styleKey]: value,
          },
        },
      };
    });
  };

  const handleTransgressionToggle = (ruleId: string, allowed: boolean) => {
    setLocalDna((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        transgressionCatalog: prev.transgressionCatalog.map((r) =>
          r.id === ruleId ? { ...r, allowed } : r
        ),
      };
    });
  };

  const handleTransgressionCostChange = (ruleId: string, cost: number) => {
    setLocalDna((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        transgressionCatalog: prev.transgressionCatalog.map((r) =>
          r.id === ruleId ? { ...r, cost } : r
        ),
      };
    });
  };

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <CreationStepper currentStep={2} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-editorial-crimson font-bold">
              Ustawienia wyglądu gazety
            </span>
            <Badge variant="accent" size="sm">
              DNA v{localDna.version}
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Styl i zasady gazety
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Ustaw podział strony, wielkość pisma, kolory i wygląd zdjęć dla gazety <strong className="text-ink-100">{activeProject.name}</strong>.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={idmlInputRef}
            type="file"
            accept=".idml,.zip"
            className="hidden"
            onChange={handleImportIdml}
          />
          <Button
            variant="secondary"
            size="md"
            isLoading={isImportingIdml}
            leftIcon={<FileUp className="w-4 h-4" />}
            onClick={() => idmlInputRef.current?.click()}
            title="Wyodrębnij siatkę modułową, marginesy i typografię z pliku Adobe InDesign (.idml)"
          >
            Importuj IDML
          </Button>
          <Button
            variant="ghost"
            size="md"
            leftIcon={<RotateCcw className="w-4 h-4" />}
            onClick={() => setLocalDna(dna ? JSON.parse(JSON.stringify(dna)) : null)}
          >
            Przywróć
          </Button>
          <Button
            variant="editorial"
            size="md"
            isLoading={isSaving}
            leftIcon={<Save className="w-4 h-4" />}
            onClick={handleSave}
          >
            Zapisz styl gazety
          </Button>
          <Button
            variant="primary"
            size="md"
            rightIcon={<ArrowRight className="w-4 h-4" />}
            onClick={() => setActiveTab('generate')}
          >
            Krok 3: Treść i generowanie →
          </Button>
        </div>
      </div>

      {/* Subtabs for DNA Sections */}
      <div className="flex items-center gap-2 border-b border-ink-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveSubTab('grid')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'grid'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Layers className="w-4 h-4 text-editorial-ochre" />
          1. Podział strony
        </button>

        <button
          onClick={() => setActiveSubTab('typography')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'typography'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Type className="w-4 h-4 text-blue-400" />
          2. Wielkość pisma
        </button>

        <button
          onClick={() => setActiveSubTab('palette')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'palette'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Palette className="w-4 h-4 text-emerald-400" />
          3. Kolory
        </button>

        <button
          onClick={() => setActiveSubTab('photos')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'photos'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Camera className="w-4 h-4 text-purple-400" />
          4. Zdjęcia
        </button>

        <button
          onClick={() => setActiveSubTab('transgressions')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'transgressions'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Flame className="w-4 h-4 text-editorial-crimson" />
          5. Efekty układu
        </button>

        <button
          onClick={() => setActiveSubTab('masthead')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-bold uppercase transition-all ${
            activeSubTab === 'masthead'
              ? 'bg-ink-800 text-ink-100 border-b-2 border-editorial-crimson'
              : 'text-ink-400 hover:text-ink-100'
          }`}
        >
          <Eye className="w-4 h-4 text-editorial-crimson" />
          6. Winieta i logo
        </button>
      </div>

      {activeSubTab === 'masthead' && <MastheadEditor onApproved={() => void reloadDNA()} />}

      {/* Main Grid: Controls + Live Specimen Preview */}
      {activeSubTab !== 'masthead' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Editor Controls (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* TAB 1: MODULAR GRID */}
          {activeSubTab === 'grid' && (
            <Card className="space-y-6">
              <div>
                <h3 className="font-headline font-bold text-base text-ink-100 mb-1">
                  Kolumny i marginesy
                </h3>
                <p className="text-xs text-ink-400">
                  Ustaw liczbę kolumn, odstępy i marginesy strony.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <Slider
                  label="Liczba kolumn"
                  value={localDna.grid.columns}
                  min={3}
                  max={8}
                  step={1}
                  unit=" kolumn"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev ? { ...prev, grid: { ...prev.grid, columns: v } } : prev
                    )
                  }
                  description="Na ile pionowych części podzielić stronę."
                />

                <Slider
                  label="Odstęp między kolumnami"
                  value={localDna.grid.gutterMm}
                  min={2}
                  max={10}
                  step={0.5}
                  unit=" mm"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev ? { ...prev, grid: { ...prev.grid, gutterMm: v } } : prev
                    )
                  }
                  description="Przerwa między sąsiednimi kolumnami tekstu."
                />

                <Slider
                  label="Rytm wierszy tekstu"
                  value={localDna.grid.baselineGridPt}
                  min={8}
                  max={16}
                  step={0.5}
                  unit=" pt"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev ? { ...prev, grid: { ...prev.grid, baselineGridPt: v } } : prev
                    )
                  }
                  description="Pomaga równo układać wiersze w kolumnach."
                />

                <Slider
                  label="Górny margines"
                  value={localDna.grid.marginTopMm}
                  min={10}
                  max={35}
                  step={1}
                  unit=" mm"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev ? { ...prev, grid: { ...prev.grid, marginTopMm: v } } : prev
                    )
                  }
                  description="Odległość treści od górnej krawędzi strony."
                />

                <Slider
                  label="Boczne marginesy"
                  value={localDna.grid.marginLeftMm}
                  min={8}
                  max={30}
                  step={1}
                  unit=" mm"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev
                        ? {
                            ...prev,
                            grid: {
                              ...prev.grid,
                              marginLeftMm: v,
                              marginRightMm: v,
                            },
                          }
                        : prev
                    )
                  }
                  description="Odległość treści od bocznych krawędzi."
                />

                <Slider
                  label="Dolny margines"
                  value={localDna.grid.marginBottomMm}
                  min={12}
                  max={35}
                  step={1}
                  unit=" mm"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev ? { ...prev, grid: { ...prev.grid, marginBottomMm: v } } : prev
                    )
                  }
                  description="Miejsce pod tekstem, także na numer strony."
                />
              </div>
            </Card>
          )}

          {/* TAB 2: TYPOGRAPHY SCALE */}
          {activeSubTab === 'typography' && (
            <Card className="space-y-6">
              <div>
                <h3 className="font-headline font-bold text-base text-ink-100 mb-1">
                  Wielkość nagłówków i tekstu
                </h3>
                <p className="text-xs text-ink-400">
                  Ustaw wielkość pisma i odstępy między wierszami dla różnych części artykułu.
                </p>
              </div>

              <div className="space-y-5">
                {/* Headline Primary */}
                <div className="p-3.5 bg-ink-950/70 rounded-lg border border-ink-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase font-bold text-ink-200">
                      Główny nagłówek
                    </span>
                    <span className="text-xs font-mono text-editorial-ochre font-bold">
                      {localDna.typography.headlinePrimary.sizePt}pt / {localDna.typography.headlinePrimary.lineHeightPt}pt
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider
                      label="Wielkość pisma"
                      value={localDna.typography.headlinePrimary.sizePt}
                      min={24}
                      max={72}
                      step={1}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('headlinePrimary', 'sizePt', v)
                      }
                    />
                    <Slider
                      label="Odstęp między wierszami"
                      value={localDna.typography.headlinePrimary.lineHeightPt}
                      min={22}
                      max={70}
                      step={1}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('headlinePrimary', 'lineHeightPt', v)
                      }
                    />
                  </div>
                </div>

                {/* Kicker */}
                <div className="p-3.5 bg-ink-950/70 rounded-lg border border-ink-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase font-bold text-editorial-crimson">
                      Nadtytuł
                    </span>
                    <span className="text-xs font-mono text-ink-300">
                      {localDna.typography.kicker.sizePt}pt • {localDna.typography.kicker.fontFamily}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider
                      label="Wielkość nadtytułu"
                      value={localDna.typography.kicker.sizePt}
                      min={8}
                      max={18}
                      step={0.5}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('kicker', 'sizePt', v)
                      }
                    />
                    <Slider
                      label="Odstęp między literami"
                      value={localDna.typography.kicker.letterSpacingPt || 1.5}
                      min={0}
                      max={4}
                      step={0.25}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('kicker', 'letterSpacingPt', v)
                      }
                    />
                  </div>
                </div>

                {/* Deck */}
                <div className="p-3.5 bg-ink-950/70 rounded-lg border border-ink-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase font-bold text-ink-200">
                      Podtytuł
                    </span>
                    <span className="text-xs font-mono text-ink-300">
                      {localDna.typography.deck.sizePt}pt / {localDna.typography.deck.lineHeightPt}pt
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider
                      label="Wielkość podtytułu"
                      value={localDna.typography.deck.sizePt}
                      min={10}
                      max={20}
                      step={0.5}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('deck', 'sizePt', v)
                      }
                    />
                    <Slider
                      label="Odstęp między wierszami"
                      value={localDna.typography.deck.lineHeightPt}
                      min={12}
                      max={26}
                      step={0.5}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('deck', 'lineHeightPt', v)
                      }
                    />
                  </div>
                </div>

                {/* Body Text */}
                <div className="p-3.5 bg-ink-950/70 rounded-lg border border-ink-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase font-bold text-ink-200">
                      Tekst artykułu
                    </span>
                    <span className="text-xs font-mono text-ink-300">
                      {localDna.typography.body.sizePt}pt / {localDna.typography.body.lineHeightPt}pt
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider
                      label="Wielkość tekstu"
                      value={localDna.typography.body.sizePt}
                      min={7.5}
                      max={12}
                      step={0.1}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('body', 'sizePt', v)
                      }
                    />
                    <Slider
                      label="Odstęp między wierszami"
                      value={localDna.typography.body.lineHeightPt}
                      min={9}
                      max={16}
                      step={0.1}
                      unit=" pt"
                      onChange={(v) =>
                        handleTypographyChange('body', 'lineHeightPt', v)
                      }
                    />
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* TAB 3: COLOR PALETTE */}
          {activeSubTab === 'palette' && (
            <Card className="space-y-6">
              <div>
                <h3 className="font-headline font-bold text-base text-ink-100 mb-1">
                  Kolory gazety
                </h3>
                <p className="text-xs text-ink-400">
                  Wybierz kolory nagłówków, linii i tła.
                </p>
              </div>

              <div className="space-y-4">
                {localDna.palette.colors.map((c, i) => (
                  <div
                    key={i}
                    className="p-3 bg-ink-950 rounded-lg border border-ink-800 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-md border border-ink-700 shadow-inner"
                        style={{ backgroundColor: c.hex }}
                      />
                      <div>
                        <p className="text-xs font-bold text-ink-100">{c.name}</p>
                        <p className="text-[10px] font-mono text-ink-400">
                          Zastosowanie: {c.role.toUpperCase()} {c.cmyk ? `• CMYK (${c.cmyk})` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={c.hex}
                        onChange={(e) => {
                          const newHex = e.target.value;
                          setLocalDna((prev) => {
                            if (!prev) return prev;
                            const colors = [...prev.palette.colors];
                            colors[i] = { ...colors[i], hex: newHex };
                            return { ...prev, palette: { ...prev.palette, colors } };
                          });
                        }}
                        className="w-7 h-7 rounded border border-ink-700 bg-transparent cursor-pointer"
                      />
                      <span className="text-xs font-mono text-ink-300">{c.hex}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* TAB 4: PHOTO RULES */}
          {activeSubTab === 'photos' && (
            <Card className="space-y-6">
              <div>
                <h3 className="font-headline font-bold text-base text-ink-100 mb-1">
                  Wygląd zdjęć
                </h3>
                <p className="text-xs text-ink-400">
                  Ustaw obrys zdjęcia i odstęp tekstu od wyciętej postaci.
                </p>
              </div>

              <div className="space-y-5">
                <Toggle
                  label="Pozwól na tekst wokół wyciętego zdjęcia"
                  checked={localDna.photos.allowedCutouts}
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev
                        ? {
                            ...prev,
                            photos: { ...prev.photos, allowedCutouts: v },
                          }
                        : prev
                    )
                  }
                  description="Tekst może opływać postać, jeśli zdjęcie ma przezroczyste tło."
                />

                <Slider
                  label="Odstęp tekstu od zdjęcia"
                  value={localDna.photos.wrapPaddingMm}
                  min={1}
                  max={10}
                  step={0.5}
                  unit=" mm"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev
                        ? {
                            ...prev,
                            photos: { ...prev.photos, wrapPaddingMm: v },
                          }
                        : prev
                    )
                  }
                  description="Odległość tekstu od krawędzi wyciętego zdjęcia."
                />

                <Slider
                  label="Grubość ramki zdjęcia"
                  value={localDna.photos.borderRulePt}
                  min={0}
                  max={3}
                  step={0.25}
                  unit=" pt"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev
                        ? {
                            ...prev,
                            photos: { ...prev.photos, borderRulePt: v },
                          }
                        : prev
                    )
                  }
                  description="Grubość obramowania zwykłych zdjęć."
                />
              </div>
            </Card>
          )}

          {/* TAB 5: TRANSGRESSIONS & ENERGY BUDGET */}
          {activeSubTab === 'transgressions' && (
            <Card className="space-y-6">
              <div>
                <h3 className="font-headline font-bold text-base text-ink-100 mb-1">
                  Odważne efekty układu
                </h3>
                <p className="text-xs text-ink-400">
                  Określ, jak mocno układ może odbiegać od zwykłej siatki. Program pilnuje ustalonego limitu.
                </p>
              </div>

              {/* Energy Budget Slider */}
              <div className="p-4 bg-ink-950 rounded-lg border border-ink-800 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase font-bold text-editorial-crimson">
                    Limit odważnych efektów na stronie
                  </span>
                  <span className="text-xs font-mono text-editorial-ochre font-bold">
                    Cel: {localDna.pageEnergyBudget.targetTensionScore} pkt · Maksimum: {localDna.pageEnergyBudget.maxTensionScore} pkt
                  </span>
                </div>
                <Slider
                  label="Docelowa intensywność układu"
                  value={localDna.pageEnergyBudget.targetTensionScore}
                  min={2}
                  max={20}
                  step={0.5}
                  unit=" pts"
                  onChange={(v) =>
                    setLocalDna((prev) =>
                      prev
                        ? {
                            ...prev,
                            pageEnergyBudget: {
                              ...prev.pageEnergyBudget,
                              targetTensionScore: v,
                            },
                          }
                        : prev
                    )
                  }
                />
              </div>

              {/* Catalog rules list */}
              <div className="space-y-3">
                {localDna.transgressionCatalog.map((rule) => (
                  <div
                    key={rule.id}
                    className={`p-3.5 rounded-lg border transition-all space-y-2 ${
                      rule.allowed
                        ? 'bg-ink-950/80 border-ink-700'
                        : 'bg-ink-950/30 border-ink-850 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <Toggle
                        label={rule.name}
                        checked={rule.allowed}
                        onChange={(v) => handleTransgressionToggle(rule.id, v)}
                        description={rule.description}
                      />
                    </div>
                    {rule.allowed && (
                      <div className="pt-2 border-t border-ink-800 flex items-center justify-between gap-4">
                        <span className="text-[11px] font-mono text-ink-400">
                          Warunek: {rule.triggerCondition}
                        </span>
                        <div className="w-48">
                          <Slider
                            label="Intensywność efektu"
                            value={rule.cost}
                            min={0.5}
                            max={6.0}
                            step={0.5}
                            unit=" pt"
                            onChange={(v) =>
                              handleTransgressionCostChange(rule.id, v)
                            }
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Live Editorial Specimen & Grid Visualizer (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-ink-400 font-semibold">
              Podgląd stylu gazety
            </span>
            <Badge variant="outline" size="sm">
              Real-Time Grammar Engine
            </Badge>
          </div>

          <div
            className="aspect-[315/470] w-full rounded-xl border border-paper-300 shadow-2xl p-5 overflow-hidden select-none flex flex-col justify-between"
            style={{
              backgroundColor: localDna.palette.backgroundTone || '#f9f6ef',
              color: localDna.palette.dominantInk || '#0b0f14',
            }}
          >
            {/* Top Folio */}
            <div className="border-b border-ink-950 pb-1.5 flex justify-between items-center text-[8px] font-mono uppercase font-bold text-ink-700">
              <span>{activeProject.newspaperTitle} • EDYCJA PRO</span>
              <span>{localDna.grid.columns} KOLUMNY • SIATKA {localDna.grid.baselineGridPt}PT</span>
            </div>

            {/* Simulated Editorial Spread */}
            <div className="space-y-2.5 my-auto">
              <span
                className="text-[10px] font-bold uppercase tracking-wider block"
                style={{
                  fontFamily: localDna.typography.kicker.fontFamily,
                  color: localDna.typography.kicker.color || '#c1121f',
                  letterSpacing: `${localDna.typography.kicker.letterSpacingPt || 1.5}px`,
                }}
              >
                GŁÓWNY TEMAT WYDANIA • REPORTAŻ
              </span>

              <h2
                className="font-headline font-black leading-tight text-ink-950"
                style={{
                  fontFamily: localDna.typography.headlinePrimary.fontFamily,
                  fontSize: `${Math.min(32, localDna.typography.headlinePrimary.sizePt * 0.7)}px`,
                }}
              >
                Architektura Informacji: Rytm i Napięcie Strony Prasowej
              </h2>

              <p
                className="text-ink-700 font-sans leading-snug line-clamp-3"
                style={{
                  fontSize: `${localDna.typography.deck.sizePt * 0.8}px`,
                }}
              >
                Każdy tytuł prasowy posiada unikalny genotyp graficzny — relację między keglami nagłówków, proporcjami zdjęć oraz odważnymi transgresjami siatki.
              </p>

              {/* Columns Simulation */}
              <div
                className="grid gap-2 pt-2 border-t border-ink-400"
                style={{
                  gridTemplateColumns: `repeat(${localDna.grid.columns}, minmax(0, 1fr))`,
                }}
              >
                {Array.from({ length: localDna.grid.columns }).map((_, i) => (
                  <div
                    key={i}
                    className="text-[7.5px] leading-tight text-justify space-y-1 text-ink-900 overflow-hidden h-32 border-r border-ink-200 pr-1 last:border-none"
                  >
                    <p>
                      Precyzyjny solver więzów geometrycznych optymalizuje rozłożenie szpalt przy zachowaniu pełnej czytelności prepress.
                    </p>
                    <p>
                      Szparowanie obiektów pozwala na dynamiczne oblewanie tekstem i kreowanie głębi kompozycyjnej.
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom Folio */}
            <div className="border-t border-ink-950 pt-1 flex justify-between items-center text-[8px] font-mono text-ink-600">
              <span>STRONA 1 / 24</span>
              <span>BUDŻET NAPIĘCIA: {localDna.pageEnergyBudget.targetTensionScore} PTS</span>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
};
