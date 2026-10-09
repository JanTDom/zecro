import React, { useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { Candidate } from '../../types/generation';
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

interface CandidateGalleryProps {
  onOpenExport: () => void;
}

export const CandidateGallery: React.FC<CandidateGalleryProps> = ({ onOpenExport }) => {
  const { currentRun, selectedCandidate, setSelectedCandidate, setActiveTab, addToast } = useProject();
  const [filterSort, setFilterSort] = useState<'taste' | 'critic' | 'novelty' | 'energy'>('taste');
  const [filterPassedOnly, setFilterPassedOnly] = useState<boolean>(false);

  if (!currentRun || currentRun.candidates.length === 0) {
    return (
      <div className="p-12 text-center max-w-lg mx-auto space-y-4">
        <Grid3X3 className="w-12 h-12 mx-auto text-ink-600" />
        <h3 className="text-xl font-headline font-bold text-ink-100">Brak wygenerowanych wariantów</h3>
        <p className="text-xs text-ink-400">
          Run the multi-candidate generator to synthesize layout variants for this newspaper edition.
        </p>
        <Button
          variant="editorial"
          leftIcon={<Sparkles className="w-4 h-4" />}
          onClick={() => setActiveTab('generate')}
        >
          Go to Material Intake
        </Button>
      </div>
    );
  }

  // Sort candidates
  const candidates = [...currentRun.candidates]
    .filter((c) => (filterPassedOnly ? c.passHardGates : true))
    .sort((a, b) => {
      if (filterSort === 'taste') return b.tasteScore - a.tasteScore;
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
              Multi-Candidate Synthesis Bank
            </span>
            <Badge variant="success" size="sm">
              {currentRun.candidates.length} wariantów
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Galeria wariantów makiety
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Każdy wariant jest niezależnym grafem sceny ocenionym przez bramkę krytyka i model preferencji.
          </p>
        </div>

        {/* Action & Filter Bar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 bg-ink-900 px-3 py-1.5 rounded-lg border border-ink-800 text-xs font-mono">
            <span className="text-ink-400 uppercase">Sort By:</span>
            <select
              value={filterSort}
              onChange={(e: any) => setFilterSort(e.target.value)}
              className="bg-transparent text-ink-100 font-bold focus:outline-none cursor-pointer"
            >
              <option value="taste" className="bg-ink-900 text-ink-100">Ranking gustu</option>
              <option value="critic" className="bg-ink-900 text-ink-100">Wynik krytyka</option>
              <option value="novelty" className="bg-ink-900 text-ink-100">Odległość nowości</option>
              <option value="energy" className="bg-ink-900 text-ink-100">Energia napięcia</option>
            </select>
          </div>

          <Button
            variant="secondary"
            size="sm"
            leftIcon={<GitCompare className="w-3.5 h-3.5" />}
            onClick={() => setActiveTab('compare')}
          >
            Pairwise A/B Compare
          </Button>
        </div>
      </div>

      {/* Candidates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {candidates.map((candidate) => {
          const isSelected = selectedCandidate?.id === candidate.id;
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
                      Variant #{candidate.candidateNumber}
                    </span>
                    {candidate.tags?.map((t, idx) => (
                      <Badge key={idx} variant="accent" size="sm">
                        {t}
                      </Badge>
                    ))}
                  </div>

                  <Badge
                    variant={candidate.passHardGates ? 'success' : 'danger'}
                    size="sm"
                    icon={candidate.passHardGates ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                  >
                    {candidate.passHardGates ? 'PASS' : 'FAIL'}
                  </Badge>
                </div>

                {/* SVG Thumbnail Miniature */}
                <div
                  onClick={() => {
                    setSelectedCandidate(candidate);
                    setActiveTab('canvas');
                  }}
                  style={{ aspectRatio: `${candidate.sceneGraph.pageFormat.widthMm} / ${candidate.sceneGraph.pageFormat.heightMm}` }}
                  className="w-full bg-paper-100 rounded-lg border border-paper-300 p-3 flex flex-col justify-between shadow-inner cursor-pointer relative overflow-hidden group-hover:scale-[1.01] transition-transform select-none"
                >
                  {candidate.thumbnailSvg ? (
                    <div className="absolute inset-0 bg-paper-100 [&>svg]:w-full [&>svg]:h-full" aria-label={`Podgląd wariantu ${candidate.candidateNumber}`} dangerouslySetInnerHTML={{ __html: candidate.thumbnailSvg }} />
                  ) : (
                    <p className="m-auto text-xs text-center text-ink-700">Podgląd niedostępny</p>
                  )}

                  {/* Hover Overlay Button */}
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-2 transition-opacity">
                    <Button
                      variant="editorial"
                      size="sm"
                      leftIcon={<Inspect className="w-3.5 h-3.5" />}
                    >
                      Inspect Canvas
                    </Button>
                  </div>
                </div>

                {/* Score Pills */}
                <div className="grid grid-cols-3 gap-2 mt-4 text-center font-mono">
                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Critic</span>
                    <strong className="text-xs font-bold text-editorial-ochre">
                      {(candidate.criticScore * 100).toFixed(0)}%
                    </strong>
                  </div>

                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Taste</span>
                    <strong className="text-xs font-bold text-emerald-300">
                      {(candidate.tasteScore * 100).toFixed(0)}%
                    </strong>
                  </div>

                  <div className="p-2 bg-ink-950 rounded-lg border border-ink-800">
                    <span className="text-[9px] uppercase text-ink-400 block">Novelty</span>
                    <strong className="text-xs font-bold text-blue-300">
                      {candidate.noveltyDistance.toFixed(2)}
                    </strong>
                  </div>
                </div>

                {/* Critic Rationale */}
                <div className="mt-3 p-2.5 bg-ink-950/60 rounded-lg border border-ink-800/80 text-[11px] text-ink-300 leading-relaxed line-clamp-2">
                  {candidate.criticRationale}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-4 mt-4 border-t border-ink-800">
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Inspect className="w-3.5 h-3.5" />}
                  onClick={() => {
                    setSelectedCandidate(candidate);
                    setActiveTab('canvas');
                  }}
                >
                  Canvas
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
                  Export
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
