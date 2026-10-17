import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { Candidate } from '../../types/generation';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Card } from '../common/Card';
import { Trophy, Check, RefreshCw, X, Sliders, Sparkles, Scale, Info } from 'lucide-react';

interface PairwiseTasteModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onToast: (toast: { type: 'success' | 'error' | 'warning' | 'info'; title: string; message: string }) => void;
}

export const PairwiseTasteModal: React.FC<PairwiseTasteModalProps> = ({
  projectId,
  isOpen,
  onClose,
  onToast,
}) => {
  const [composer, setComposer] = useState('framed_cover:wukadka');
  const [isLoading, setIsLoading] = useState(false);
  const [pairData, setPairData] = useState<{
    pair_id: string;
    candidate_a: Candidate;
    candidate_b: Candidate;
    features_a: Record<string, number>;
    features_b: Record<string, number>;
    archetype: string;
  } | null>(null);

  const [calibStatus, setCalibStatus] = useState<{
    human_pairs_count: number;
    valid: boolean;
    loo_accuracy?: number;
    source?: string;
  } | null>(null);

  const [isVoting, setIsVoting] = useState(false);
  const [selectedWinner, setSelectedWinner] = useState<'A' | 'B' | 'tie' | null>(null);

  const loadPair = async (selectedComposer = composer) => {
    setIsLoading(true);
    setSelectedWinner(null);
    try {
      const data = await api.getPairwiseCandidates(projectId, selectedComposer);
      setPairData(data);
      const status = await api.getPairwiseCalibrationStatus(projectId);
      setCalibStatus(status as any);
    } catch (e) {
      onToast({
        type: 'error',
        title: 'Nie udało się pobrać pary',
        message: e instanceof Error ? e.message : 'Błąd połączenia z serwerem.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadPair();
    }
  }, [isOpen, composer]);

  if (!isOpen) return null;

  const handleVote = async (winner: 'A' | 'B' | 'tie') => {
    if (!pairData || isVoting) return;
    setIsVoting(true);
    setSelectedWinner(winner);
    try {
      const res = await api.submitPairwiseVote(projectId, {
        pair_id: pairData.pair_id,
        candidate_a_id: pairData.candidate_a.id,
        candidate_b_id: pairData.candidate_b.id,
        winner,
        features_a: pairData.features_a,
        features_b: pairData.features_b,
        archetype: pairData.archetype,
      });

      onToast({
        type: 'success',
        title: 'Głos zapisany',
        message: winner === 'tie'
          ? 'Odnotowano remis. Wybór zasila pętlę gustu.'
          : `Wybrano Wariant ${winner}. Model Bradleya-Terry'ego uczy się Twojej estetyki!`,
      });

      // Aktualizujemy status i pobieramy kolejną parę po krótkiej pauzie
      setTimeout(() => {
        loadPair();
      }, 700);
    } catch (e) {
      onToast({
        type: 'error',
        title: 'Błąd zapisu głosu',
        message: e instanceof Error ? e.message : 'Nie udało się zarejestrować preferencji.',
      });
    } finally {
      setIsVoting(false);
    }
  };

  const handleForceCalibrate = async () => {
    try {
      const res = await api.forceRecalibrateTaste(projectId);
      onToast({
        type: 'success',
        title: 'Model gustu zaktualizowany',
        message: `Przeliczono wagi Bradleya-Terry'ego na ${res.pairs_used} parach. Trafność LOO: ${Math.round((res.loo_accuracy || 0) * 100)}%.`,
      });
      const status = await api.getPairwiseCalibrationStatus(projectId);
      setCalibStatus(status as any);
    } catch (e) {
      onToast({
        type: 'warning',
        title: 'Kalibracja wstrzymana',
        message: e instanceof Error ? e.message : 'Zbierz więcej par przed kalibracją.',
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto animate-fade-in">
      <div className="relative w-full max-w-6xl bg-ink-900 border border-ink-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-ink-800 bg-ink-950/60">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] uppercase font-mono tracking-widest text-editorial-crimson font-bold">
                Pętla Gustu Redaktora · Bradley–Terry
              </span>
              <Badge variant="accent" size="sm">
                Pojedynek A/B
              </Badge>
              {calibStatus && (
                <span className="text-xs font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                  {calibStatus.human_pairs_count} ocen człowieka
                  {calibStatus.valid && ` · LOO: ${Math.round((calibStatus.loo_accuracy || 0) * 100)}%`}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-headline font-bold text-ink-100 mt-1">
              Który układ lepiej oddaje charakter tytułu?
            </h2>
            <p className="text-xs text-ink-400">
              Oceń ułamkiem sekundy. Model Bradleya-Terry'ego uczy się proporcji, napięcia i hierarchii z Twoich wyborów.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={composer}
              onChange={(e) => setComposer(e.target.value)}
              className="bg-ink-800 border border-ink-700 text-ink-200 text-xs rounded-lg px-3 py-2 outline-none focus:border-editorial-crimson font-mono"
            >
              <option value="framed_cover:wukadka">Tabloid: okładka ramowa</option>
              <option value="title_kit:daily_broadsheet">Dziennik: broadsheet (6 szpalt)</option>
              <option value="title_kit:opinion_magazine">Magazyn opinii (A4)</option>
            </select>

            <Button variant="ghost" size="sm" onClick={() => loadPair()} leftIcon={<RefreshCw className="w-4 h-4" />}>
              Nowa para
            </Button>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-ink-400 hover:text-ink-100 hover:bg-ink-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading || !pairData ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <RefreshCw className="w-8 h-8 text-editorial-crimson animate-spin" />
              <p className="text-sm font-mono text-ink-400">Układanie dwóch odmiennych wariantów do pojedynku…</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
              {/* Wariant A */}
              <div
                className={`relative flex flex-col p-4 rounded-xl border-2 transition-all ${
                  selectedWinner === 'A'
                    ? 'border-emerald-500 bg-emerald-950/20 shadow-emerald-900/30 shadow-xl'
                    : 'border-ink-800 bg-ink-950/40 hover:border-ink-700'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-ink-800 text-ink-200 font-bold text-xs flex items-center justify-center font-mono">
                      A
                    </span>
                    <h3 className="font-headline font-bold text-ink-100">Wariant Alfa</h3>
                  </div>
                  <Badge variant={pairData.candidate_a.passHardGates ? 'success' : 'warning'} size="sm">
                    {pairData.candidate_a.passHardGates ? 'Bramka zaliczona' : 'Uwagi'}
                  </Badge>
                </div>

                {/* Podgląd SVG */}
                <div
                  className="w-full bg-white rounded-lg shadow-inner overflow-hidden flex items-center justify-center min-h-[420px] max-h-[520px]"
                  dangerouslySetInnerHTML={{ __html: pairData.candidate_a.thumbnailSvg || '' }}
                />

                {/* Metryki estetyki */}
                <div className="mt-4 pt-3 border-t border-ink-800/80 grid grid-cols-3 gap-2 text-[11px] font-mono text-ink-400">
                  <div>
                    <span className="block text-ink-500">Wyważenie:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_a.balance || 0) * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-ink-500">Napięcie:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_a.tension || 0) * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-ink-500">Udział foto:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_a.hero_photo_share || 0) * 100)}%
                    </span>
                  </div>
                </div>

                <div className="mt-4">
                  <Button
                    variant={selectedWinner === 'A' ? 'editorial' : 'secondary'}
                    size="lg"
                    className="w-full font-bold shadow-md"
                    leftIcon={<Check className="w-5 h-5" />}
                    isLoading={isVoting && selectedWinner === 'A'}
                    onClick={() => handleVote('A')}
                  >
                    Wybieram Wariant A
                  </Button>
                </div>
              </div>

              {/* Wariant B */}
              <div
                className={`relative flex flex-col p-4 rounded-xl border-2 transition-all ${
                  selectedWinner === 'B'
                    ? 'border-emerald-500 bg-emerald-950/20 shadow-emerald-900/30 shadow-xl'
                    : 'border-ink-800 bg-ink-950/40 hover:border-ink-700'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-ink-800 text-ink-200 font-bold text-xs flex items-center justify-center font-mono">
                      B
                    </span>
                    <h3 className="font-headline font-bold text-ink-100">Wariant Beta</h3>
                  </div>
                  <Badge variant={pairData.candidate_b.passHardGates ? 'success' : 'warning'} size="sm">
                    {pairData.candidate_b.passHardGates ? 'Bramka zaliczona' : 'Uwagi'}
                  </Badge>
                </div>

                {/* Podgląd SVG */}
                <div
                  className="w-full bg-white rounded-lg shadow-inner overflow-hidden flex items-center justify-center min-h-[420px] max-h-[520px]"
                  dangerouslySetInnerHTML={{ __html: pairData.candidate_b.thumbnailSvg || '' }}
                />

                {/* Metryki estetyki */}
                <div className="mt-4 pt-3 border-t border-ink-800/80 grid grid-cols-3 gap-2 text-[11px] font-mono text-ink-400">
                  <div>
                    <span className="block text-ink-500">Wyważenie:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_b.balance || 0) * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-ink-500">Napięcie:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_b.tension || 0) * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="block text-ink-500">Udział foto:</span>
                    <span className="text-ink-200 font-bold">
                      {Math.round((pairData.features_b.hero_photo_share || 0) * 100)}%
                    </span>
                  </div>
                </div>

                <div className="mt-4">
                  <Button
                    variant={selectedWinner === 'B' ? 'editorial' : 'secondary'}
                    size="lg"
                    className="w-full font-bold shadow-md"
                    leftIcon={<Check className="w-5 h-5" />}
                    isLoading={isVoting && selectedWinner === 'B'}
                    onClick={() => handleVote('B')}
                  >
                    Wybieram Wariant B
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-ink-800 bg-ink-950/80 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => handleVote('tie')} disabled={isVoting}>
              Oba są dobre (Remis)
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleForceCalibrate}
              leftIcon={<Sliders className="w-3.5 h-3.5" />}
            >
              Wymuś przeliczenie wag gustu
            </Button>
          </div>

          <div className="text-xs text-ink-400 font-mono flex items-center gap-2">
            <Info className="w-4 h-4 text-editorial-crimson" />
            Wybory parami uaktualniają model preferencji Bradleya-Terry'ego, który waży oceny krytyka w generatorze.
          </div>
        </div>
      </div>
    </div>
  );
};
