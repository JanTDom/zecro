import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { apiUrl } from '../../api/client';
import { Layers, Eye, Sparkles, Check, ArrowRight } from 'lucide-react';

interface CreationStepperProps {
  currentStep: 1 | 2 | 3;
}

const resolveLogoUrl = (ref?: string) => {
  if (!ref) return '';
  if (/^(https?:|\/static\/)/.test(ref)) return apiUrl(ref);
  return apiUrl(`/static/uploads/${ref.split('/').pop()}`);
};

export const CreationStepper: React.FC<CreationStepperProps> = ({ currentStep }) => {
  const { activeProject, dna, setActiveTab, setDnaSubTab } = useProject();

  const hasLogo = Boolean(dna?.logo_profile?.asset_ref);
  const logoUrl = resolveLogoUrl(dna?.logo_profile?.asset_ref);
  const newspaperTitle = activeProject?.newspaperTitle || activeProject?.name || 'Nowa Gazeta';

  const steps = [
    {
      step: 1 as const,
      title: 'Krok 1: Przykłady stylu',
      subtitle: 'Opcjonalny styl z Twoich plików',
      icon: Layers,
      onClick: () => setActiveTab('corpus'),
      completed: (dna?.corpusMetrics?.pagesAnalyzed ?? 0) > 0,
    },
    {
      step: 2 as const,
      title: 'Krok 2: Winieta i logo',
      subtitle: hasLogo ? 'Logo wgrane i aktywne' : 'Wgraj znak swojej gazety',
      icon: Eye,
      onClick: () => {
        setDnaSubTab('masthead');
        setActiveTab('dna');
      },
      completed: hasLogo,
      badge: hasLogo && logoUrl ? (
        <img
          src={logoUrl}
          alt="Logo gazety"
          className="max-h-5 max-w-[70px] object-contain bg-white/90 rounded px-1 py-0.5 border border-ink-700"
        />
      ) : null,
    },
    {
      step: 3 as const,
      title: 'Krok 3: Treść i skład',
      subtitle: 'Wprowadź materiał i generuj',
      icon: Sparkles,
      onClick: () => setActiveTab('generate'),
      completed: false,
    },
  ];

  return (
    <div className="bg-ink-900/90 border border-ink-800 rounded-2xl p-4 sm:p-5 shadow-lg mb-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-ink-800/80">
        <div className="flex items-center gap-3">
          {hasLogo && logoUrl ? (
            <div className="h-10 w-16 bg-white rounded-lg p-1 border border-ink-700 flex items-center justify-center shrink-0 overflow-hidden shadow-xs">
              <img src={logoUrl} alt={newspaperTitle} className="max-h-full max-w-full object-contain" />
            </div>
          ) : (
            <div className="h-10 w-10 bg-editorial-crimson/20 border border-editorial-crimson/40 rounded-lg flex items-center justify-center text-editorial-crimson font-bold text-sm shrink-0">
              {newspaperTitle.slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-editorial-ochre font-semibold">
                Kreator wydania · Krok {currentStep} z 3
              </span>
              {hasLogo && (
                <span className="text-[10px] font-mono bg-emerald-950/80 text-emerald-400 border border-emerald-700/50 rounded-full px-2 py-0.2">
                  Logo aktywne
                </span>
              )}
            </div>
            <h2 className="text-base font-headline font-bold text-ink-100 flex items-center gap-2">
              Gazeta: <span>{newspaperTitle}</span>
            </h2>
          </div>
        </div>

        <div className="text-xs text-ink-400 hidden sm:block">
          Kliknij dowolny krok, aby swobodnie przejść między etapami.
        </div>
      </div>

      {/* Steps Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-4">
        {steps.map((s, idx) => {
          const isCurrent = s.step === currentStep;
          const isPast = s.step < currentStep || s.completed;
          const Icon = s.icon;

          return (
            <button
              key={s.step}
              type="button"
              onClick={s.onClick}
              className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                isCurrent
                  ? 'bg-ink-800/90 border-editorial-crimson ring-1 ring-editorial-crimson/40 shadow-md'
                  : 'bg-ink-950/50 border-ink-800/80 hover:bg-ink-800/50 hover:border-ink-700'
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 transition-colors ${
                    isCurrent
                      ? 'bg-editorial-crimson text-white shadow-xs'
                      : s.completed
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-ink-800 text-ink-400 border border-ink-700'
                  }`}
                >
                  {s.completed ? <Check className="w-4 h-4" /> : s.step}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-xs font-bold truncate ${
                        isCurrent ? 'text-ink-100' : 'text-ink-300'
                      }`}
                    >
                      {s.title}
                    </span>
                    {s.badge}
                  </div>
                  <p className="text-[11px] text-ink-400 truncate">{s.subtitle}</p>
                </div>
              </div>

              <Icon
                className={`w-4 h-4 shrink-0 ml-2 ${
                  isCurrent ? 'text-editorial-crimson' : 'text-ink-600'
                }`}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
};
