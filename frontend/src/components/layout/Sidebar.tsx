import React from 'react';
import { useProject, NavigationTab } from '../../context/ProjectContext';
import {
  Archive,
  BookOpen,
  ChevronRight,
  FileStack,
  FolderKanban,
  GitCompare,
  Grid3X3,
  Inspect,
  LayoutDashboard,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Type,
} from 'lucide-react';
import { clsx } from 'clsx';

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab, currentRun, tasteMetrics, activeProject } = useProject();

  const primary: { id: NavigationTab; label: string; icon: React.ElementType; badge?: string }[] = [
    { id: 'dashboard', label: 'Studio', icon: LayoutDashboard },
    { id: 'corpus', label: 'Korpus inspiracji', icon: FileStack, badge: activeProject?.corpusCount ? String(activeProject.corpusCount) : undefined },
    { id: 'dna', label: 'DNA tytułu', icon: SlidersHorizontal, badge: activeProject ? `v${activeProject.dnaVersion}` : undefined },
    { id: 'plan', label: 'Makieta', icon: Grid3X3 },
    { id: 'edition', label: 'Wydanie', icon: BookOpen },
    { id: 'generate', label: 'Generator', icon: Sparkles },
    { id: 'gallery', label: 'Galeria', icon: Grid3X3, badge: currentRun?.candidates.length ? String(currentRun.candidates.length) : undefined },
    { id: 'copy', label: 'Studio tekstu', icon: Type },
    { id: 'compare', label: 'Porównanie A/B', icon: GitCompare, badge: tasteMetrics ? `${Math.round(tasteMetrics.preferenceWinRate * 100)}%` : undefined },
    { id: 'canvas', label: 'Edytor strony', icon: Inspect },
    { id: 'settings', label: 'AI i źródła', icon: Settings2 },
  ];

  return (
    <aside className="w-[248px] bg-white border-r border-ink-800 shrink-0 hidden md:flex min-h-[calc(100vh-4rem)] flex-col">
      <div className="px-6 pt-7 pb-5">
        <button onClick={() => setActiveTab('dashboard')} className="block w-full text-left" aria-label="Otwórz Studio Zecro">
          <img src="/zecro-logo.png" alt="Zecro Generative Layout Engine" className="w-[176px] h-auto object-contain object-left" />
        </button>
      </div>

      <div className="px-3 flex-1">
        <p className="px-3 mb-2 text-[10px] font-mono tracking-[0.18em] uppercase text-ink-500">Workspace</p>
        <nav className="space-y-1">
          {primary.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={clsx(
                  'group w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-[13px] transition-all',
                  active ? 'bg-blue-50 text-editorial-crimson font-semibold' : 'text-ink-300 hover:bg-ink-950 hover:text-ink-100'
                )}
              >
                <span className="flex items-center gap-3">
                  <Icon className={clsx('w-[17px] h-[17px]', active ? 'text-editorial-crimson' : 'text-ink-400 group-hover:text-ink-200')} strokeWidth={active ? 2.2 : 1.8} />
                  {item.label}
                </span>
                {item.badge && <span className={clsx('text-[10px] font-mono tabular-nums', active ? 'text-editorial-crimson' : 'text-ink-500')}>{item.badge}</span>}
              </button>
            );
          })}
        </nav>

        <div className="my-6 border-t border-ink-800" />
        <p className="px-3 mb-2 text-[10px] font-mono tracking-[0.18em] uppercase text-ink-500">Biblioteka</p>
        <button onClick={() => setActiveTab('projects')} className={clsx('group w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-[13px] transition-all', activeTab === 'projects' ? 'bg-blue-50 text-editorial-crimson font-semibold' : 'text-ink-300 hover:bg-ink-950 hover:text-ink-100')}>
          <span className="flex items-center gap-3"><FolderKanban className="w-[17px] h-[17px] text-ink-400 group-hover:text-ink-200" strokeWidth={1.8} />Projekty</span>
          <ChevronRight className="w-3.5 h-3.5 text-ink-500" />
        </button>
      </div>

      <div className="px-5 py-5 border-t border-ink-800">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full rounded-full bg-emerald-300 opacity-60 animate-ping" /><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" /></span>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-ink-200 truncate">Sesja aktywna</p>
            <p className="text-[10px] text-ink-500 truncate">Silnik Zecro · API + Supabase</p>
          </div>
          <Settings2 className="ml-auto w-4 h-4 text-ink-500" strokeWidth={1.7} />
        </div>
        <div className="mt-4 flex items-center gap-2 text-[10px] text-ink-500 font-mono"><BookOpen className="w-3.5 h-3.5" /> Scene Graph v1 <span className="text-ink-700">·</span> <Archive className="w-3.5 h-3.5" /> DB-first</div>
      </div>
    </aside>
  );
};
