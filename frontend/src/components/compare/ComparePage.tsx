import React, { useState, useEffect } from 'react';
import { useProject } from '../../context/ProjectContext';
import { Candidate } from '../../types/generation';
import { PreferenceSignal } from '../../types/taste';
import { api } from '../../api/client';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import confetti from 'canvas-confetti';
import {
  GitCompare,
  ThumbsUp,
  TrendingUp,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Flame,
  CheckCircle2,
  Shuffle,
} from 'lucide-react';

export const ComparePage: React.FC = () => {
  const { currentRun, activeProject, tasteMetrics, reloadTasteMetrics, addToast } = useProject();

  const [candIndexA, setCandIndexA] = useState<number>(0);
  const [candIndexB, setCandIndexB] = useState<number>(1);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [comparisonCountSession, setComparisonCountSession] = useState<number>(0);

  const candidates = currentRun?.candidates || [];

  // Pick 2 candidates
  const candA: Candidate | undefined = candidates[candIndexA % (candidates.length || 1)];
  const candB: Candidate | undefined = candidates[candIndexB % (candidates.length || 1)];

  const handleNextPair = () => {
    if (candidates.length < 2) return;
    const nextA = (candIndexA + 1) % candidates.length;
    const nextB = (nextA + 1) % candidates.length;
    setCandIndexA(nextA);
    setCandIndexB(nextB);
  };

  const handleVote = async (winnerId: string, loserId: string) => {
    if (!activeProject || !candA || !candB || isSubmitting || winnerId === loserId) return;

    setIsSubmitting(true);
    try {
      const signal: PreferenceSignal = {
        id: `sig-${Date.now()}`,
        projectId: activeProject.id,
        type: 'pairwise_choice',
        candidateAId: candA.id,
        candidateBId: candB.id,
        winnerCandidateId: winnerId,
        timestamp: new Date().toISOString(),
      };

      const result = await api.submitPreference(signal);
      await reloadTasteMetrics();
      setComparisonCountSession((c) => c + 1);

      // Trigger celebratory confetti if milestone reached
      if ((comparisonCountSession + 1) % 3 === 0) {
        try {
          confetti({
            particleCount: 50,
            spread: 60,
            origin: { y: 0.7 },
          });
        } catch {}
      }

      addToast({
        type: 'success',
        title: 'Taste Signal Logged',
        message: `Updated preference vector. Taste alignment win-rate: ${(result.updatedMetrics.preferenceWinRate * 100).toFixed(0)}%.`,
      });

      handleNextPair();
    } catch (error) {
      addToast({ type: 'error', title: 'Nie udało się zapisać wyboru', message: error instanceof Error ? error.message : 'Błąd API.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Keyboard shortcut listener for fast art director review
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches('input, textarea, select') || isSubmitting) return;
      if (e.key === '1' && candA) {
        handleVote(candA.id, candB?.id || '');
      } else if (e.key === '2' && candB) {
        handleVote(candB.id, candA?.id || '');
      } else if (e.key === 's' || e.key === 'S' || e.key === ' ') {
        handleNextPair();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [candA, candB, isSubmitting]);

  if (!activeProject || candidates.length < 2) {
    return (
      <div className="p-12 text-center max-w-md mx-auto space-y-4">
        <GitCompare className="w-12 h-12 mx-auto text-ink-600" />
        <h3 className="text-xl font-headline font-bold text-ink-100">Potrzebne są co najmniej 2 warianty</h3>
        <p className="text-xs text-ink-400">
          Run the layout generator to synthesize variants, then return here to train the Art Director taste model.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-emerald-400 font-bold">
              Pętla preferencji dyrektora artystycznego
            </span>
            <Badge variant="success" size="sm">
              Session Votes: {comparisonCountSession}
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Porównanie wariantów A/B
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Porównaj dwie makiety i wybierz lepszą, aby zapisać sygnał preferencji projektu. Keyboard: Press <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">1</kbd> for Left, <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">2</kbd> for Right, <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">S</kbd> to Skip.
          </p>
        </div>

        {/* Model Metrics */}
        {tasteMetrics && (
          <div className="flex items-center gap-3 bg-ink-900 border border-ink-800 px-4 py-2 rounded-xl">
            <TrendingUp className="w-5 h-5 text-emerald-400" />
            <div>
              <span className="text-[10px] font-mono uppercase text-ink-400 block">Taste Win-Rate</span>
              <strong className="text-sm font-mono text-emerald-300 font-bold">
                {(tasteMetrics.preferenceWinRate * 100).toFixed(0)}% zgodność z wyborem
              </strong>
            </div>
          </div>
        )}
      </div>

      {/* Side-by-Side Comparison Arena */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* CANDIDATE A (LEFT) */}
        {candA && (
          <Card className="flex flex-col justify-between space-y-4 border-2 hover:border-editorial-crimson transition-all">
            <div>
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-ink-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-ink-800 text-ink-100">
                    OPTION A [Press 1]
                  </span>
                  <Badge variant="accent" size="sm">
                    Variant #{candA.candidateNumber}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-ink-400">Critic:</span>
                  <strong className="text-editorial-ochre">{(candA.criticScore * 100).toFixed(0)}%</strong>
                </div>
              </div>

              <div className="w-full bg-paper-100 rounded-xl border border-paper-300 my-3 overflow-hidden" style={{ aspectRatio: `${candA.sceneGraph.pageFormat.widthMm} / ${candA.sceneGraph.pageFormat.heightMm}` }}>
                {candA.thumbnailSvg ? (
                  <div className="w-full h-full [&>svg]:w-full [&>svg]:h-full" aria-label="Podgląd wariantu" dangerouslySetInnerHTML={{ __html: candA.thumbnailSvg }} />
                ) : (
                  <p className="p-8 text-center text-xs text-ink-700">Podgląd niedostępny</p>
                )}
              </div>

              {/* Feature Pills */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Tension Budget:</span>
                  <strong className="text-ink-200">{candA.tensionEnergyConsumed} pts</strong>
                </div>
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Anti-Copying:</span>
                  <strong className="text-blue-300">{candA.noveltyDistance.toFixed(2)}</strong>
                </div>
              </div>
            </div>

            {/* Vote Action */}
            <Button
              variant="editorial"
              size="lg"
              className="w-full"
              isLoading={isSubmitting}
              leftIcon={<ThumbsUp className="w-4 h-4" />}
              onClick={() => handleVote(candA.id, candB?.id || '')}
            >
              Choose Option A
            </Button>
          </Card>
        )}

        {/* CANDIDATE B (RIGHT) */}
        {candB && (
          <Card className="flex flex-col justify-between space-y-4 border-2 hover:border-editorial-crimson transition-all">
            <div>
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-ink-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-ink-800 text-ink-100">
                    OPTION B [Press 2]
                  </span>
                  <Badge variant="accent" size="sm">
                    Variant #{candB.candidateNumber}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-ink-400">Critic:</span>
                  <strong className="text-editorial-ochre">{(candB.criticScore * 100).toFixed(0)}%</strong>
                </div>
              </div>

              <div className="w-full bg-paper-100 rounded-xl border border-paper-300 my-3 overflow-hidden" style={{ aspectRatio: `${candB.sceneGraph.pageFormat.widthMm} / ${candB.sceneGraph.pageFormat.heightMm}` }}>
                {candB.thumbnailSvg ? (
                  <div className="w-full h-full [&>svg]:w-full [&>svg]:h-full" aria-label="Podgląd wariantu" dangerouslySetInnerHTML={{ __html: candB.thumbnailSvg }} />
                ) : (
                  <p className="p-8 text-center text-xs text-ink-700">Podgląd niedostępny</p>
                )}
              </div>

              {/* Feature Pills */}
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Tension Budget:</span>
                  <strong className="text-ink-200">{candB.tensionEnergyConsumed} pts</strong>
                </div>
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Anti-Copying:</span>
                  <strong className="text-blue-300">{candB.noveltyDistance.toFixed(2)}</strong>
                </div>
              </div>
            </div>

            {/* Vote Action */}
            <Button
              variant="editorial"
              size="lg"
              className="w-full"
              isLoading={isSubmitting}
              leftIcon={<ThumbsUp className="w-4 h-4" />}
              onClick={() => handleVote(candB.id, candA?.id || '')}
            >
              Choose Option B
            </Button>
          </Card>
        )}
      </div>

      {/* Skip Button */}
      <div className="text-center pt-2">
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Shuffle className="w-3.5 h-3.5" />}
          onClick={handleNextPair}
        >
          Skip This Pair [Space]
        </Button>
      </div>
    </div>
  );
};
