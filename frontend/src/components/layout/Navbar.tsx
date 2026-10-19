import React, { useState } from 'react';
import { apiUrl } from '../../api/client';
import { useProject } from '../../context/ProjectContext';
import { Button } from '../common/Button';
import { isTechnicalProject } from '../../projectVisibility';
import { Check, ChevronDown, FileText, HelpCircle, LayoutDashboard, LogOut, Menu, Plus, Sparkles, X } from 'lucide-react';

interface NavbarProps {
  onOpenNewProject: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenNewProject }) => {
  const { projects, activeProject, selectProject, setActiveTab } = useProject();
  const visibleProjects = projects.filter(project => !isTechnicalProject(project));
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [aiStatus, setAiStatus] = useState('Sprawdzanie AI…');
  const logout = async () => {
    await fetch(apiUrl('/auth/logout'), { method: 'POST', credentials: 'include' }).catch(() => null);
    window.dispatchEvent(new CustomEvent('zecro-session-expired', { detail: 'logout' }));
  };
  React.useEffect(() => {
    let active = true;
    fetch(apiUrl('/health/ai'), { credentials: 'include' }).then(async response => {
      const body = await response.json().catch(() => ({}));
      if (active) setAiStatus(response.ok && body.status === 'ready' ? `Gemini: ${body.model}` : `AI niedostępne: ${body.detail?.reason || body.reason || response.status}`);
    }).catch(() => { if (active) setAiStatus('AI niedostępne: brak połączenia'); });
    return () => { active = false; };
  }, []);

  const mobileNav = [
    { id: 'osint' as const, label: 'Szyba śledcza', icon: Sparkles },
    { id: 'dashboard' as const, label: 'Zacznij tutaj', icon: LayoutDashboard },
    { id: 'help' as const, label: 'Pomoc', icon: HelpCircle },
    { id: 'generate' as const, label: 'Materiały i strona', icon: Sparkles },
    { id: 'gallery' as const, label: 'Warianty', icon: FileText },
    { id: 'projects' as const, label: 'Moje gazety', icon: Plus },
    { id: 'settings' as const, label: 'AI i źródła', icon: Sparkles },
  ];

  return (
    <header className="h-16 bg-white border-b border-ink-800 sticky top-0 z-40 px-5 lg:px-7 flex items-center justify-between">
      <div className="flex items-center gap-4 min-w-0">
        <div className="md:hidden shrink-0">
            <button onClick={() => setMobileNavOpen((open) => !open)} aria-label={mobileNavOpen ? 'Zamknij menu' : 'Otwórz menu'} aria-expanded={mobileNavOpen} className="w-9 h-9 rounded-lg bg-ink-950 border border-ink-800 flex items-center justify-center overflow-hidden">
            <img src="/zecro-mark.svg" alt="Zecro" className="w-7 h-7" />
          </button>
          {mobileNavOpen && (
            <div className="absolute left-4 top-14 w-56 bg-white border border-ink-800 rounded-xl shadow-page-elevated p-2 animate-fade-in">
              <div className="flex items-center justify-between px-2 py-2 border-b border-ink-800 mb-1">
                <span className="text-[10px] uppercase tracking-[0.16em] font-mono text-ink-500">Nawigacja</span>
                <button onClick={() => setMobileNavOpen(false)} aria-label="Zamknij menu" className="p-1 text-ink-400 hover:text-ink-100"><X className="w-3.5 h-3.5" /></button>
              </div>
              {mobileNav.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => { setActiveTab(id); setMobileNavOpen(false); }} className="w-full flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-[12px] text-ink-200 hover:bg-ink-950">
                  <Icon className="w-4 h-4 text-editorial-crimson" />{label}
                </button>
              ))}
              <button onClick={() => void logout()} className="w-full flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-[12px] text-ink-200 hover:bg-ink-950"><LogOut className="w-4 h-4" />Wyloguj</button>
            </div>
          )}
        </div>
        <div className="hidden sm:flex items-center gap-3 text-[12px] text-ink-500">
          <button onClick={() => setActiveTab('dashboard')} className="font-semibold text-ink-200 hover:text-ink-100">Zacznij tutaj</button>
          <button 
            onClick={() => setActiveTab('help')} 
            className="flex items-center gap-1.5 font-semibold text-editorial-crimson hover:text-editorial-crimson/80 bg-blue-50/80 px-2.5 py-1 rounded-md border border-editorial-crimson/20"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            Pomoc
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative">
          <button onClick={() => setDropdownOpen((open) => !open)} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ink-800 bg-white hover:bg-ink-950 transition-colors min-w-[188px] text-left">
            <span className="w-7 h-7 rounded-md bg-ink-950 flex items-center justify-center shrink-0"><FileText className="w-3.5 h-3.5 text-ink-300" /></span>
            <span className="min-w-0 flex-1"><span className="block text-[12px] font-semibold text-ink-100 truncate">{activeProject?.name || 'Wybierz gazetę'}</span><span className="block text-[10px] text-ink-500">{activeProject ? 'Otwarta gazeta' : 'Moje gazety'}</span></span>
            <ChevronDown className="w-3.5 h-3.5 text-ink-500" />
          </button>
          {dropdownOpen && (
            <div className="absolute right-0 top-[calc(100%+8px)] w-72 bg-white border border-ink-800 rounded-xl shadow-page-elevated py-2 animate-fade-in">
              <div className="px-3 pb-2 mb-1 border-b border-ink-800 flex items-center justify-between"><span className="text-[10px] uppercase tracking-[0.16em] font-mono text-ink-500">Twoje gazety</span><span className="text-[10px] text-ink-500">{visibleProjects.length}</span></div>
              <div className="max-h-64 overflow-y-auto">
                {visibleProjects.length === 0 && <p className="px-3 py-3 text-xs text-ink-500">Nie masz jeszcze własnej gazety.</p>}
                {visibleProjects.map((project) => (
                  <button key={project.id} onClick={() => { void selectProject(project.id); setDropdownOpen(false); }} className="w-full px-3 py-2.5 flex items-center gap-2.5 hover:bg-ink-950 text-left">
                    <span className="w-2 h-2 rounded-full bg-editorial-crimson" /><span className="flex-1 min-w-0"><span className="block text-[12px] font-semibold text-ink-100 truncate">{project.name}</span><span className="block text-[10px] font-mono text-ink-500">Własna gazeta · wersja stylu {project.dnaVersion}</span></span>{project.id === activeProject?.id && <Check className="w-4 h-4 text-editorial-crimson" />}
                  </button>
                ))}
              </div>
              <button onClick={() => { setDropdownOpen(false); setActiveTab('projects'); }} className="w-full px-3 py-2 text-left text-xs font-semibold text-editorial-crimson">Zobacz wszystkie gazety</button>
              <div className="mt-1 pt-2 border-t border-ink-800 px-2"><Button variant="ghost" size="sm" className="w-full justify-start" leftIcon={<Plus className="w-3.5 h-3.5" />} onClick={() => { setDropdownOpen(false); onOpenNewProject(); }}>Nowa gazeta</Button></div>
              <button onClick={() => void logout()} className="w-full px-3 py-2 text-left text-xs text-ink-500 hover:text-ink-100">Wyloguj</button>
            </div>
          )}
        </div>
        <button onClick={() => setActiveTab('settings')} className="hidden lg:flex items-center gap-2 px-2.5 py-2 text-[10px] font-mono text-ink-500 border-l border-ink-800 pl-4"><span className={`w-1.5 h-1.5 rounded-full ${aiStatus.startsWith('Gemini:') ? 'bg-emerald-500' : 'bg-amber-500'}`} />{aiStatus}</button>
        <Button variant="editorial" size="md" leftIcon={<Plus className="w-3.5 h-3.5" />} onClick={onOpenNewProject}>Nowa gazeta</Button>
      </div>
    </header>
  );
};
