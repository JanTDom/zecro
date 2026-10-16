import React from 'react';
import { useProject, NavigationTab } from '../../context/ProjectContext';
import { BookOpen, Camera, CheckCircle2, ChevronDown, Download, FileStack, FolderKanban, GitCompare, Grid3X3, HelpCircle, Inspect, LayoutDashboard, Newspaper, Settings2, SlidersHorizontal, Sparkles, Type } from 'lucide-react';
import { clsx } from 'clsx';

type Item = { id: NavigationTab; label: string; icon: React.ElementType; done?: boolean; anchor?: string; exportStep?: boolean };

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab, currentRun, activeProject, selectedCandidate } = useProject();
  const [toolsOpen, setToolsOpen] = React.useState(false);
  // One guided path for a non-DTP editor; everything else lives under
  // "Pozostałe narzędzia" so it never competes with the main steps.
  const main: Item[] = [
    { id: 'projects', label: '1. Nazwa i rodzaj gazety', icon: Newspaper, done: Boolean(activeProject) },
    { id: 'generate', label: '2. Materiały', icon: Sparkles, anchor: 'lead-story-fields' },
    { id: 'generate', label: '3. Kontrola zdjęć', icon: Camera, anchor: 'photo-check-title' },
    { id: 'generate', label: '4. Generowanie', icon: Sparkles, done: Boolean(currentRun?.candidates.length) },
    { id: 'gallery', label: `5. Trzy najlepsze propozycje${currentRun?.candidates.length ? ` (${currentRun.candidates.length})` : ''}`, icon: Grid3X3, done: Boolean(selectedCandidate) },
    { id: 'canvas', label: '6. Proste poprawki', icon: Inspect },
    { id: 'gallery', label: '7. Eksport PDF / InDesign', icon: Download, exportStep: true },
  ];
  const advanced: Item[] = [
    { id: 'help', label: 'Jak to działa (schemat i pomoc)', icon: HelpCircle },
    { id: 'dashboard', label: 'Ekran startowy', icon: LayoutDashboard },
    { id: 'corpus', label: 'Przykłady stylu', icon: FileStack },
    { id: 'edition', label: 'Całe wydanie', icon: BookOpen },
    { id: 'dna', label: 'Styl i zasady gazety', icon: SlidersHorizontal },
    { id: 'plan', label: 'Plan treści strony', icon: Grid3X3 },
    { id: 'copy', label: 'Redakcja tekstu', icon: Type },
    { id: 'compare', label: 'Porównaj dwa warianty', icon: GitCompare },
    { id: 'settings', label: 'AI i źródła', icon: Settings2 },
  ];
  React.useEffect(() => {
    if (advanced.some(item => item.id === activeTab)) setToolsOpen(true);
  }, [activeTab]);
  const go = (item: Item) => {
    setActiveTab(item.id);
    if (item.exportStep) window.setTimeout(() => window.dispatchEvent(new Event('zecro-open-export')), 0);
    if (item.anchor) window.setTimeout(() => document.getElementById(item.anchor!)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
  };
  const itemButton = (item: Item) => {
    const Icon = item.done ? CheckCircle2 : item.icon;
    const active = activeTab === item.id && !item.anchor && !item.exportStep;
    return <button key={item.label} onClick={() => go(item)} aria-current={active ? 'page' : undefined} className={clsx('w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm', active ? 'bg-blue-50 text-editorial-crimson font-semibold' : 'text-ink-300 hover:bg-ink-950 hover:text-ink-100')}><Icon className={clsx('w-4 h-4 shrink-0', item.done && 'text-emerald-600')} />{item.label}</button>;
  };
  return <aside className="w-[260px] bg-white border-r border-ink-800 shrink-0 hidden md:flex min-h-[calc(100vh-4rem)] flex-col">
    <button onClick={() => setActiveTab('dashboard')} className="px-6 pt-7 pb-5 text-left" aria-label="Wróć na początek"><img src="/zecro-logo.png" alt="Zecro" className="w-[176px] h-auto object-contain object-left" /></button>
    <nav aria-label="Główne kroki" className="px-3 space-y-1"><p className="px-3 mb-2 text-xs font-semibold text-ink-500">Twoja droga do gazety</p>{main.map(itemButton)}</nav>
    <div className="mt-7 border-t border-ink-800 px-3 pt-4"><button onClick={() => setToolsOpen(!toolsOpen)} aria-expanded={toolsOpen} className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-ink-500">Pozostałe narzędzia<ChevronDown className={clsx('h-4 w-4 transition-transform', toolsOpen && 'rotate-180')} /></button>{toolsOpen && <nav aria-label="Pozostałe narzędzia" className="space-y-1">{advanced.map(itemButton)}</nav>}</div>
  </aside>;
};
