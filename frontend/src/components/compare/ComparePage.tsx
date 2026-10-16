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
  const [pairStartedAt, setPairStartedAt] = useState<number>(() => Date.now());

  const candidates = currentRun?.candidates || [];

  // Pick 2 candidates
  const candA: Candidate | undefined = candidates[candIndexA % (candidates.length || 1)];
  const candB: Candidate | undefined = candidates[candIndexB % (candidates.length || 1)];

  const chooseUncertainPair = (excludeA = candIndexA, excludeB = candIndexB): [number, number] => {
    if (candidates.length < 2) return [0, 1];
    let best: [number, number] = [(excludeA + 1) % candidates.length, (excludeA + 2) % candidates.length];
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let a = 0; a < candidates.length; a += 1) {
      for (let b = a + 1; b < candidates.length; b += 1) {
        if ((a === excludeA && b === excludeB) || (a === excludeB && b === excludeA)) continue;
        const distance = Math.abs((candidates[a].tasteScore || 0) - (candidates[b].tasteScore || 0));
        if (distance < bestDistance) { bestDistance = distance; best = [a, b]; }
      }
    }
    return best;
  };

  const handleNextPair = () => {
    if (candidates.length < 2) return;
    // Active learning: ask about the pair the current model finds hardest to
    // distinguish, rather than walking through the gallery in a fixed order.
    const [nextA, nextB] = chooseUncertainPair();
    setCandIndexA(nextA);
    setCandIndexB(nextB);
    setPairStartedAt(Date.now());
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
        reviewDurationSec: Math.round((Date.now() - pairStartedAt) / 100) / 10,
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
        title: 'Zapisano wybór',
        message: `Dopasowanie do Twoich wyborów: ${(result.updatedMetrics.preferenceWinRate * 100).toFixed(0)}%.`,
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
          Najpierw przygotuj stronę z własnych materiałów. Gdy pojawią się warianty, porównasz je tutaj.
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
              Wybierz styl, który Ci odpowiada
            </span>
            <Badge variant="success" size="sm">
              Wybory w tej sesji: {comparisonCountSession}
            </Badge>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Porównanie wariantów A/B
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Obejrzyj obie strony i wybierz tę, która bardziej Ci się podoba. Dzięki temu kolejne propozycje lepiej trafią w Twój gust. Skróty: <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">1</kbd> wybiera lewą, <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">2</kbd> prawą, a <kbd className="px-1.5 py-0.5 bg-ink-800 text-ink-100 rounded font-mono text-xs">S</kbd> pomija parę.
          </p>
        </div>

        {/* Model Metrics */}
        {tasteMetrics && (
          <div className="flex items-center gap-3 bg-ink-900 border border-ink-800 px-4 py-2 rounded-xl">
            <TrendingUp className="w-5 h-5 text-emerald-400" />
            <div>
              <span className="text-[10px] font-mono uppercase text-ink-400 block">Dopasowanie do Twoich wyborów</span>
              <strong className="text-sm font-mono text-emerald-300 font-bold">
                {(tasteMetrics.preferenceWinRate * 100).toFixed(0)}% zgodność na treningu
              </strong>
              <span className="block text-[10px] text-ink-500 mt-1">
                {tasteMetrics.evaluatedSampleCount > 0
                  ? `${(tasteMetrics.heldOutWinRate * 100).toFixed(0)}% na nowych parach · ${tasteMetrics.evaluatedSampleCount} testowych`
                  : 'Brak odłożonych par testowych — zbierz jeszcze kilka wyborów.'}
              </span>
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
                    WARIANT A [klawisz 1]
                  </span>
                  <Badge variant="accent" size="sm">
                    Wariant {candA.candidateNumber}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-ink-400">Ocena układu:</span>
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
                  <span className="text-ink-400">Śmiałość układu:</span>
                  <strong className="text-ink-200">{candA.tensionEnergyConsumed} pts</strong>
                </div>
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Oryginalność:</span>
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
              Wybieram wariant A
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
                    WARIANT B [klawisz 2]
                  </span>
                  <Badge variant="accent" size="sm">
                    Wariant {candB.candidateNumber}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-ink-400">Ocena układu:</span>
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
                  <span className="text-ink-400">Śmiałość układu:</span>
                  <strong className="text-ink-200">{candB.tensionEnergyConsumed} pts</strong>
                </div>
                <div className="p-2 bg-ink-950 rounded border border-ink-800 flex justify-between">
                  <span className="text-ink-400">Oryginalność:</span>
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
              Wybieram wariant B
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
          Pomiń tę parę [spacja]
        </Button>
      </div>
    </div>
  );
};
