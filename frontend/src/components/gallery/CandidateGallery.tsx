import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { api } from '../../api/client';
import { Candidate } from '../../types/generation';
import { styleReviewState } from '../../styleReview';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Grid3X3,
  Inspect,
  GitCompare,
  Download,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Flame,
  TrendingUp,
  Bookmark,
  Filter,
} from 'lucide-react';

const architectureLabels: Record<string, string> = {
  'dominant-left': 'Dominanta lewa',
  'dominant-right': 'Dominanta prawa',
  stacked: 'Układ piętrowy',
  'photo-top': 'Otwarcie foto',
  'type-led': 'Typografia i portret',
  'modular-grid': 'Siatka modułowa',
};

type PageFacts = { photoShare: number; photos: number; stories: number; tilted: boolean; morphology?: string };

function pageFacts(candidate: Candidate): PageFacts {
  const scene = candidate.sceneGraph;
  const area = Math.max(1, scene.pageFormat.widthMm * scene.pageFormat.heightMm);
  const images = scene.elements.filter(element => element.role === 'image');
  const largest = Math.max(0, ...images.map(element => element.frame.width * element.frame.height));
  const stories = new Set(scene.elements.map(element => element.storyId).filter(Boolean));
  const tilted = scene.elements.some(element => element.role === 'headline'
    && Math.abs(Number(element.canonical?.frame?.rotation_deg ?? 0)) >= 2);
  return { photoShare: largest / area, photos: images.length, stories: stories.size, tilted,
    morphology: candidate.layoutStory?.morphology };
}

function describeDifferences(base: PageFacts, other: PageFacts): string[] {
  const out: string[] = [];
  if (other.morphology && other.morphology !== base.morphology) out.push(`inny układ (${other.morphology.toLowerCase()})`);
  const delta = Math.round((other.photoShare - base.photoShare) * 100);
  if (Math.abs(delta) >= 8) out.push(delta > 0 ? `większe zdjęcie główne (+${delta} pkt %)` : `mniejsze zdjęcie główne (${delta} pkt %)`);
  if (other.photos !== base.photos) out.push(`${other.photos} zamiast ${base.photos} zdjęć`);
  if (other.stories !== base.stories) out.push(`${other.stories} zamiast ${base.stories} tematów`);
  if (other.tilted !== base.tilted) out.push(other.tilted ? 'tytuł wchodzi ukośnie' : 'tytuł prosty');
  return out.length ? out : ['podobna struktura, inne proporcje'];
}

interface CandidateGalleryProps {
  onOpenExport: () => void;
}

const warianty = (count: number) => `${count} ${count === 4 ? 'warianty' : 'wariantów'}`;

export const CandidateGallery: React.FC<CandidateGalleryProps> = ({ onOpenExport }) => {
  const { activeProject, currentRun, selectedCandidate, setSelectedCandidate, setActiveTab, addToast, reloadTasteMetrics } = useProject();
  const [filterSort, setFilterSort] = useState<'taste' | 'critic' | 'novelty' | 'energy'>('critic');
  const [filterPassedOnly, setFilterPassedOnly] = useState<boolean>(false);
  const [selectedForEditionId, setSelectedForEditionId] = useState<string | null>(null);
  const [isSubmittingPreference, setIsSubmittingPreference] = useState<string | null>(null);

  const handleSelectForEdition = async (candidate: Candidate) => {
    if (!activeProject) return;
    try {
      setIsSubmittingPreference(candidate.id);
      await api.submitPreference({
        id: '',
        projectId: activeProject.id,
        type: 'direct_favorite',
        candidateAId: candidate.id,
        winnerCandidateId: candidate.id,
        timestamp: new Date().toISOString(),
      });
      const otherCandidates = (currentRun?.candidates || []).filter(c => c.id !== candidate.id);
      for (const other of otherCandidates.slice(0, 3)) {
        await api.submitPreference({
          id: '',
          projectId: activeProject.id,
          type: 'pairwise_choice',
          candidateAId: candidate.id,
          candidateBId: other.id,
          winnerCandidateId: candidate.id,
          timestamp: new Date().toISOString(),
        });
      }
      setSelectedForEditionId(candidate.id);
      await reloadTasteMetrics();
      addToast({
        type: 'success',
        title: 'Zapisano wybór do wydania',
        message: 'Model preferencji AI uwzględnił Twoją decyzję w przyszłych propozycjach.',
      });
    } catch (err) {
      addToast({
        type: 'error',
        title: 'Błąd zapisu preferencji',
        message: err instanceof Error ? err.message : 'Nie udało się zapisać wyboru.',
      });
    } finally {
      setIsSubmittingPreference(null);
    }
  };

  if (!currentRun || currentRun.candidates.length === 0) {
    return (
      <div className="p-12 text-center max-w-lg mx-auto space-y-4">
        <Grid3X3 className="w-12 h-12 mx-auto text-ink-600" />
        <h3 className="text-xl font-headline font-bold text-ink-100">Brak wygenerowanych wariantów</h3>
        <p className="text-xs text-ink-400">
          Dodaj własne materiały i przygotuj pierwsze propozycje strony.
        </p>
        <Button
          variant="editorial"
          leftIcon={<Sparkles className="w-4 h-4" />}
          onClick={() => setActiveTab('generate')}
        >
          Dodaj materiały
        </Button>
      </div>
    );
  }

  // The backend returns candidates best-first (hard gate, then critic and
  // visual review).  The guided step shows the first three that passed.
  const topThree = currentRun.candidates.filter(candidate => candidate.passHardGates).slice(0, 3);

  // Sort candidates
  const candidates = [...currentRun.candidates]
    .filter((c) => (filterPassedOnly ? c.passHardGates : true))
    .sort((a, b) => {
      if (filterSort === 'taste') return (b.visualReview?.style_fidelity ?? -1) - (a.visualReview?.style_fidelity ?? -1);
      if (filterSort === 'critic') return b.criticScore - a.criticScore;
      if (filterSort === 'novelty') return b.noveltyDistance - a.noveltyDistance;
      if (filterSort === 'energy') return b.tensionEnergyConsumed - a.tensionEnergyConsumed;
      return 0;
    });

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-editorial-crimson font-bold">
              Propozycje Twojej strony
            </span>
            <Badge variant="success" size="sm">
              {warianty(currentRun.candidates.length)}
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Propozycje strony
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Otwórz propozycję, aby ją dopracować. Poprawny skład nie oznacza jeszcze wiarygodnego wyglądu ani zgody na wydanie.
          </p>
        </div>

        {/* Action & Filter Bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-ink-900 px-3 py-1.5 rounded-lg border border-ink-800 text-xs font-mono">
            <span className="text-ink-400 uppercase">Sortuj według:</span>
            <select
              value={filterSort}
              onChange={(e: any) => setFilterSort(e.target.value)}
              className="bg-transparent text-ink-100 font-bold focus:outline-hidden cursor-pointer"
            >
              <option value="taste" className="bg-ink-900 text-ink-100">Ocena wyglądu</option>
              <option value="critic" className="bg-ink-900 text-ink-100">Ocena układu</option>
              <option value="novelty" className="bg-ink-900 text-ink-100">Najbardziej oryginalne</option>
              <option value="energy" className="bg-ink-900 text-ink-100">Najbardziej wyraziste</option>
            </select>
          </div>

          <Button
            variant="secondary"
            size="sm"
            leftIcon={<GitCompare className="w-3.5 h-3.5" />}
            onClick={() => setActiveTab('compare')}
          >
            Porównaj dwa warianty
          </Button>
        </div>
      </div>

      {topThree.length > 0 && (
        <section aria-labelledby="top-three-title" className="rounded-xl border border-ink-800 bg-white p-5 space-y-3">
          <h2 id="top-three-title" className="font-headline text-lg font-bold text-ink-100">Trzy najlepsze propozycje i czym się różnią</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {topThree.map((candidate, index) => {
              const facts = pageFacts(candidate);
              const base = pageFacts(topThree[0]);
              const differences = index === 0 ? [] : describeDifferences(base, facts);
              return (
                <button key={candidate.id} type="button" onClick={() => { setSelectedCandidate(candidate); setActiveTab('canvas'); }}
                  className="text-left rounded-lg border border-ink-800 p-3 hover:border-editorial-crimson focus-visible:outline-2 focus-visible:outline-editorial-crimson">
                  <p className="text-xs font-semibold text-editorial-crimson">Propozycja {index + 1}</p>
                  <p className="text-sm font-semibold text-ink-100">{candidate.layoutStory?.morphology || 'Układ modułowy'}</p>
                  <p className="mt-1 text-[11px] text-ink-400">Zdjęcie główne zajmuje {Math.round(facts.photoShare * 100)}% strony · {facts.photos} zdj. · {facts.stories} tematów{facts.tilted ? ' · tytuł ukośny' : ''}</p>
                  {differences.length > 0 && <p className="mt-1 text-[11px] text-ink-300">W porównaniu z propozycją 1: {differences.join('; ')}.</p>}
                  {candidate.layoutStory?.photoReason && <p className="mt-1 text-[11px] text-ink-400">Zdjęcie: {candidate.layoutStory.photoReason}</p>}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Candidates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {candidates.map((candidate) => {
          const isSelected = selectedCandidate?.id === candidate.id;
          const styleWarning = candidate.styleReadiness?.warnings?.[0];
          const visualMismatch = candidate.visualReview?.category_mismatch?.[0];
          const photoMismatch = candidate.sceneGraph.elements.some(element => element.role === 'image')
            && typeof candidate.visualReview?.photo_headline_match === 'number'
            && candidate.visualReview.photo_headline_match < 0.65;
          const reviewState = styleReviewState(candidate);
          return (
            <Card
              key={candidate.id}
              variant={isSelected ? 'elevated' : 'default'}
              className={`flex flex-col justify-between relative group hover:border-ink-600 transition-all ${
                isSelected ? 'border-editorial-crimson ring-2 ring-editorial-crimson/50' : ''
              }`}
            >
              <div>
                {/* Candidate Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-headline font-bold text-sm text-ink-100">
                      Wariant {candidate.candidateNumber}
                    </span>
                    {candidate.tags?.map((t, idx) => (
                      <Badge key={idx} variant="accent" size="sm">
                        {t}
                      </Badge>
                    ))}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {selectedForEditionId === candidate.id && (
                      <Badge variant="success" size="sm" icon={<CheckCircle2 className="w-3 h-3" />}>
                        Wybrany do wydania
                      </Badge>
                    )}
                    <Badge
                      variant={candidate.passHardGates ? 'success' : 'danger'}
                      size="sm"
                      icon={candidate.passHardGates ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                    >
                      {candidate.passHardGates ? 'Skład poprawny' : 'Błąd składu'}
                    </Badge>
                  </div>
                </div>

                {/* SVG Thumbnail Miniature */}
                <button type="button"
                  onClick={() => {
                    setSelectedCandidate(candidate);
                    setActiveTab('canvas');
                  }}
                  aria-label={`Otwórz wariant ${candidate.candidateNumber}`}
                  style={{ aspectRatio: `${candidate.sceneGraph.pageFormat.widthMm} / ${candidate.sceneGraph.pageFormat.heightMm}` }}
                  className="w-full bg-paper-100 rounded-lg border border-paper-300 p-3 flex flex-col justify-between shadow-inner cursor-pointer relative overflow-hidden group-hover:scale-[1.01] transition-transform select-none focus-visible:outline-2 focus-visible:outline-editorial-crimson"
                >
                  {candidate.thumbnailSvg ? (
                    <img className="absolute inset-0 w-full h-full object-contain bg-paper-100" alt={`Podgląd wariantu ${candidate.candidateNumber}`} src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(candidate.thumbnailSvg)}`} />
                  ) : (
                    <p className="m-auto text-xs text-center text-ink-700">Podgląd niedostępny</p>
                  )}

                  <span className="absolute bottom-2 left-2 right-2 rounded bg-editorial-crimson px-3 py-2 text-center text-xs font-semibold text-white">Otwórz wariant</span>
                </button>

                {candidate.layoutStory && (
                  <div className="mt-2 space-y-0.5 text-[11px] leading-snug text-ink-300">
                    {candidate.layoutStory.morphology && (
                      <p><span className="font-semibold text-ink-100">Układ:</span> {candidate.layoutStory.morphology}</p>
                    )}
                    {candidate.layoutStory.photoReason && (
                      <p><span className="font-semibold text-ink-100">Zdjęcie:</span> {candidate.layoutStory.photoReason}</p>
                    )}
                    {candidate.layoutStory.decisions.slice(0, 2).map((decision, index) => (
                      <p key={index} className="text-ink-400">• {decision}</p>
                    ))}
                  </div>
                )}

                {/* Score Pills */}
                <div className="grid grid-cols-3 gap-2 mt-4 text-center font-mono">
                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Układ</span>
                    <strong className="text-xs font-bold text-editorial-ochre">
                      {(candidate.criticScore * 100).toFixed(0)}%
                    </strong>
                  </div>

                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Wygląd</span>
                    <strong className="text-xs font-bold text-emerald-300">
                      {typeof candidate.visualReview?.style_fidelity === 'number' ? `${(candidate.visualReview.style_fidelity * 100).toFixed(0)}%` : '—'}
                    </strong>
                  </div>

                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Oryginalność</span>
                    <strong className="text-xs font-bold text-blue-300">
                      {candidate.noveltyDistance.toFixed(2)}
                    </strong>
                  </div>
                </div>

                {styleWarning && <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                  <strong>Styl wymaga materiałów:</strong> {styleWarning}
                </div>}
                {visualMismatch && <div className="mt-2 rounded-lg border border-orange-300 bg-orange-50 p-3 text-xs text-orange-900">
                  <strong>Ocena wyglądu:</strong> {visualMismatch}
                </div>}
                {photoMismatch && <div className="mt-2 rounded-lg border border-orange-300 bg-orange-50 p-3 text-xs text-orange-900">
                  <strong>Zdjęcie może nie opowiadać tej historii.</strong> Wybierz ujęcie, które pokazuje ludzi, miejsce lub zdarzenie opisane w głównym tytule.{' '}
                  <button type="button" className="font-semibold underline" onClick={() => setActiveTab('generate')}>Wróć do zdjęć</button>
                </div>}
                {reviewState === 'needs_revision' && <div className="mt-2 rounded-lg border border-red-300 bg-red-50 p-3 text-xs text-red-900">
                  <strong>Wygląd wymaga poprawy.</strong> Krytyk wizualny nie uznał tej strony za wystarczająco wiarygodną dla wybranego rodzaju gazety. To szkic do dalszej pracy.
                </div>}
                {reviewState === 'unreviewed' && <div className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                  <strong>Wygląd nieoceniony.</strong> Nie traktuj tego wariantu jako gotowego do wydania; najpierw potrzebna jest ocena wizualna.
                </div>}
                {reviewState === 'candidate_for_editor' && <div className="mt-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-900">
                  <strong>Do oceny redaktora.</strong> Wynik AI jest obiecujący, lecz ostateczna decyzja należy do człowieka.
                </div>}
                {/* Critic Rationale */}
                <div className="mt-3 p-2.5 bg-ink-950/60 rounded-lg border border-ink-800/80 text-[11px] text-ink-300 leading-relaxed line-clamp-2">
                  {candidate.passHardGates
                    ? 'Tekst i elementy przeszły kontrolę składu. Ocena stylu jest osobna.'
                    : 'Ten układ wymaga poprawek. Otwórz go, aby zobaczyć szczegóły kontroli.'}
                </div>

                {candidate.artDirection && (
                  <div className="mt-2 p-2.5 rounded-lg border border-editorial-ochre/30 bg-editorial-ochre/5 text-[10px] text-ink-300 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono uppercase tracking-wide text-editorial-ochre">{architectureLabels[candidate.artDirection.architecture] || candidate.artDirection.architecture}</span>
                      <span className="font-mono text-ink-500">{candidate.artDirection.confidence > 0 ? `${Math.round(candidate.artDirection.confidence * 100)}% pewności oceny` : 'ocena stylu jeszcze się uczy'}</span>
                    </div>
                    <p className="line-clamp-2 text-ink-400">{candidate.artDirection.page_thesis}</p>
                    <div className="flex items-center justify-between font-mono text-[9px]">
                      <span>{candidate.artDirection.copy_slots.length} miejsc na tekst</span>
                      <span>{candidate.artDirection.copy_slots.filter((slot) => slot.fit_status !== 'PASS').length} do dopracowania</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 pt-4 mt-4 border-t border-ink-800">
                <Button
                  variant={selectedForEditionId === candidate.id ? "editorial" : "outline"}
                  size="sm"
                  leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                  isLoading={isSubmittingPreference === candidate.id}
                  onClick={() => handleSelectForEdition(candidate)}
                  className={selectedForEditionId === candidate.id ? "shadow-md" : "border-emerald-600/40 text-emerald-400 hover:bg-emerald-950/30"}
                >
                  {selectedForEditionId === candidate.id ? 'Wybrany do wydania' : 'Wybierz do wydania'}
                </Button>

                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<Inspect className="w-3.5 h-3.5" />}
                    onClick={() => {
                      setSelectedCandidate(candidate);
                      setActiveTab('canvas');
                    }}
                  >
                    Otwórz
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<Download className="w-3.5 h-3.5" />}
                    onClick={() => {
                      setSelectedCandidate(candidate);
                      onOpenExport();
                    }}
                  >
                    Pobierz
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
