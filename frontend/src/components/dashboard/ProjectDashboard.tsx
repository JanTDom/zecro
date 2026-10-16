import React from 'react';
import { useProject, NavigationTab } from '../../context/ProjectContext';
import { api } from '../../api/client';
import { ArrowRight, CheckCircle2, Plus, Sparkles } from 'lucide-react';

const specialistNames: Record<string, string> = {
  corpus_analyst: 'Analiza przykładów', layout_generator: 'Tworzenie układów',
  hard_critic: 'Kontrola błędów', taste_critic: 'Ocena stylu',
  visual_critic: 'Ocena wyglądu', copy_editor: 'Redakcja tekstu',
};
const specialistStatus: Record<string, string> = {
  ready: 'Gotowe', blocked: 'Brak przykładów', learned: 'Uczy się z wyborów',
  heuristic: 'Ocena podstawowa', unconfigured: 'Nieustawione',
  unavailable: 'Niedostępne', source_bound_fallback: 'Na podstawie źródła',
};

export const ProjectDashboard: React.FC<{ onOpenNewProject: () => void }> = ({ onOpenNewProject }) => {
  const { activeProject, currentRun, selectedCandidate, setActiveTab, setSelectedCandidate } = useProject();
  const [aiContract, setAiContract] = React.useState<any>(null);

  React.useEffect(() => {
    if (!activeProject?.id) { setAiContract(null); return; }
    let active = true;
    api.getAIDirectorContract(activeProject.id).then(data => { if (active) setAiContract(data); }).catch(() => { if (active) setAiContract(null); });
    return () => { active = false; };
  }, [activeProject?.id]);

  const candidates = currentRun?.candidates || [];
  const steps: { title: string; description: string; tab: NavigationTab; action: string; done: boolean }[] = [
    { title: 'Utwórz gazetę', description: 'Nadaj nazwę, wybierz rodzaj gazety i rozmiar papieru.', tab: 'projects', action: 'Utwórz nową gazetę', done: !!activeProject },
    { title: 'Dodaj przykładowe strony', description: 'Pokaż, jaki styl Ci się podoba. Ten krok możesz pominąć.', tab: 'corpus', action: 'Dodaj przykłady', done: !!activeProject?.corpusCount },
    { title: 'Dodaj materiały i wygeneruj stronę', description: 'Wpisz własne teksty, dodaj zdjęcia i zobacz propozycje układu.', tab: 'generate', action: 'Przygotuj stronę', done: candidates.length > 0 },
    { title: 'Wybierz i dopracuj wariant', description: 'Otwórz propozycje, porównaj je i przygotuj do wydania.', tab: 'gallery', action: 'Zobacz warianty', done: !!selectedCandidate },
  ];

  return <main className="max-w-6xl mx-auto px-5 sm:px-8 py-10 space-y-8">
    <section className="rounded-2xl border bg-white p-6 sm:p-9">
      <p className="text-xs font-semibold uppercase tracking-widest text-editorial-crimson">Zacznij tutaj</p>
      <h1 className="mt-2 font-headline text-4xl sm:text-5xl text-ink-100">{activeProject ? `Twoja gazeta: ${activeProject.name}` : 'Stwórz swoją gazetę'}</h1>
      <p className="mt-4 max-w-2xl text-ink-400">{activeProject ? 'Przejdź przez poniższe kroki. W każdej chwili możesz wrócić do tego miejsca.' : 'Zacznij od nazwy, rodzaju gazety i rozmiaru papieru. Potem dodasz materiały i wygenerujesz pierwszą stronę.'}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button onClick={onOpenNewProject} className="inline-flex items-center gap-2 rounded-lg bg-editorial-crimson px-5 py-3 text-sm font-semibold text-white"><Plus className="w-4 h-4" />Nowa gazeta</button>
        {activeProject && <button onClick={() => setActiveTab('generate')} className="inline-flex items-center gap-2 rounded-lg border px-5 py-3 text-sm font-semibold"><Sparkles className="w-4 h-4" />Przygotuj stronę</button>}
      </div>
    </section>

    <section aria-labelledby="steps-title">
      <h2 id="steps-title" className="font-headline text-2xl mb-4">Jak zrobić pierwszą stronę</h2>
      <ol className="grid gap-3 md:grid-cols-2">{steps.map((step, index) => <li key={step.title} className="rounded-xl border bg-white p-5 flex gap-4">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${step.done ? 'bg-green-100 text-green-800' : 'bg-blue-50 text-editorial-crimson'}`}>{step.done ? <CheckCircle2 className="w-5 h-5" /> : index + 1}</span>
        <div><h3 className="font-semibold text-ink-100">{step.title}</h3><p className="mt-1 text-sm text-ink-500">{step.description}</p>
          {index === 0 && !activeProject ? <button onClick={onOpenNewProject} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-editorial-crimson">Utwórz gazetę<ArrowRight className="w-4 h-4" /></button>
            : index === 0 ? <p className="mt-3 text-sm font-semibold text-green-700">Gazeta utworzona</p>
            : !activeProject ? <p className="mt-3 text-sm text-ink-400">Najpierw utwórz gazetę</p>
            : index === 3 && candidates.length === 0 ? <p className="mt-3 text-sm text-ink-400">Najpierw przygotuj stronę</p>
            : <button onClick={() => setActiveTab(step.tab)} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-editorial-crimson">{step.action}<ArrowRight className="w-4 h-4" /></button>}
        </div>
      </li>)}</ol>
    </section>

    <section className="rounded-xl border bg-white p-5">
      <div className="flex items-center justify-between gap-3"><h2 className="font-headline text-2xl">Ostatnie propozycje stron</h2>{candidates.length > 0 && <button onClick={() => setActiveTab('gallery')} className="text-sm font-semibold text-editorial-crimson">Otwórz wszystkie</button>}</div>
      {candidates.length === 0 ? <p className="mt-3 text-sm text-ink-500">Nie ma jeszcze wygenerowanych stron. Po dodaniu materiałów pojawią się tutaj prawdziwe warianty, które możesz otworzyć.</p> : <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{candidates.slice(0, 3).map((candidate, index) => <button key={candidate.id} onClick={() => { setSelectedCandidate(candidate); setActiveTab('canvas'); }} className="rounded-lg border p-3 text-left hover:border-editorial-crimson focus-visible:outline-2 focus-visible:outline-editorial-crimson"><div className="aspect-[3/4] bg-slate-50 flex items-center justify-center overflow-hidden">{candidate.thumbnailSvg && <img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(candidate.thumbnailSvg)}`} alt={`Podgląd wariantu ${index + 1}`} className="max-h-full max-w-full object-contain" />}</div><strong className="mt-3 block">Wariant {index + 1}</strong><span className="text-xs text-ink-500">{candidate.passHardGates ? 'Przeszedł kontrolę jakości' : 'Wymaga poprawek'} · Otwórz</span></button>)}</div>}
    </section>

    {aiContract && <details className="rounded-xl border bg-white p-5"><summary className="cursor-pointer font-semibold">Stan narzędzi AI i kontroli jakości</summary><p className="mt-2 text-sm text-ink-500">To szczegóły techniczne. Możesz tworzyć gazetę bez zmiany tych ustawień.</p><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(aiContract.specialists || {}).map(([key, value]: [string, any]) => <div key={key} className="rounded-lg border p-3 text-sm"><strong>{specialistNames[key] || key}</strong><p className="text-ink-500">{specialistStatus[value.status] || value.status}</p></div>)}</div><button onClick={() => setActiveTab('settings')} className="mt-4 text-sm font-semibold text-editorial-crimson">Sprawdź modele i źródła</button></details>}
  </main>;
};
