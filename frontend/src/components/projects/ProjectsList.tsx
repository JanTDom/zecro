import React from 'react';
import { ArrowRight, Plus, Trash2 } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import type { Project, NewspaperFormat } from '../../types/project';
import { editorialStyle } from '../../editorialStyles';
import { isTechnicalProject } from '../../projectVisibility';
import { errorMessage } from '../../api/client';

interface ProjectsListProps {
  onOpenNewProject: () => void;
}

const formatNames: Record<NewspaperFormat, string> = {
  broadsheet: 'duży format',
  berliner: 'średni format',
  tabloid: 'mały format',
  compact: 'kompaktowy format',
  custom: 'własny format',
};

export const ProjectsList: React.FC<ProjectsListProps> = ({ onOpenNewProject }) => {
  const { projects, activeProject, selectProject, deleteProject, setActiveTab, addToast } = useProject();
  const regular = projects.filter(project => !isTechnicalProject(project));
  const technical = projects.filter(isTechnicalProject);

  const card = (project: Project) => {
    const active = project.id === activeProject?.id;
    return <article key={project.id} className="rounded-2xl border border-ink-800 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
          {project.editorialCharacter ? editorialStyle(project.editorialCharacter).name : 'Gazeta'}
        </span>
        {active && <span className="text-xs font-semibold text-emerald-700">Otwarta</span>}
      </div>
      <h3 className="font-headline text-2xl font-bold text-ink-100">{project.name}</h3>
      <p className="mt-1 text-sm text-ink-500">{formatNames[project.format]} · {project.generationRunsCount ? `${project.generationRunsCount} przygotowanych stron` : 'Jeszcze bez przygotowanych stron'}</p>
      <p className="mt-3 text-sm text-ink-400">Otwórz gazetę, aby dodać materiały i przygotować stronę.</p>
      <div className="mt-5 flex items-center justify-between border-t border-ink-800 pt-4">
        <button type="button" className="rounded-lg p-2 text-red-500 hover:bg-red-50" title={`Usuń gazetę ${project.name}`}
          onClick={() => { if (confirm(`Usunąć gazetę „${project.name}” wraz z jej materiałami?`)) void deleteProject(project.id); }}>
          <Trash2 className="h-4 w-4" />
        </button>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg bg-editorial-crimson px-4 py-2 text-sm font-semibold text-white"
          onClick={async () => {
            try {
              await selectProject(project.id);
              setActiveTab('dashboard');
            } catch (error) {
              addToast({ type: 'error', title: 'Nie udało się otworzyć gazety', message: errorMessage(error) });
            }
          }}>
          Otwórz gazetę <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </article>;
  };

  return <main className="mx-auto max-w-6xl space-y-8 p-6 lg:p-10">
    <header className="rounded-2xl border border-ink-800 bg-white p-6 sm:p-8">
      <span className="text-xs font-semibold uppercase tracking-widest text-editorial-crimson">Twoja pracownia</span>
      <h1 className="mt-2 font-headline text-4xl font-bold text-ink-100">Moje gazety</h1>
      <p className="mt-3 max-w-2xl text-sm text-ink-500">Każda gazeta ma własny styl, teksty i wydania. Aby zacząć od początku, wybierz przycisk poniżej.</p>
      <button type="button" onClick={onOpenNewProject} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-editorial-crimson px-5 py-3 font-semibold text-white shadow-sm">
        <Plus className="h-5 w-5" /> Utwórz nową gazetę
      </button>
    </header>

    <section aria-label="Utworzone gazety">
      {regular.length ? <div className="grid gap-5 md:grid-cols-2">{regular.map(card)}</div> : <div className="rounded-2xl border border-dashed border-ink-700 bg-white p-8 text-center">
        <h2 className="font-headline text-2xl">Nie masz jeszcze własnej gazety</h2>
        <p className="mt-2 text-sm text-ink-500">Kliknij „Utwórz nową gazetę”. W pierwszym kroku wystarczy nazwa i rodzaj gazety.</p>
        <button type="button" onClick={onOpenNewProject} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-editorial-crimson px-5 py-3 font-semibold text-white"><Plus className="h-4 w-4" /> Utwórz nową gazetę</button>
      </div>}
    </section>

    {technical.length > 0 && <details className="rounded-xl border border-ink-800 bg-white p-5">
      <summary className="cursor-pointer text-sm font-semibold text-ink-500">Gazety techniczne użyte do testów ({technical.length})</summary>
      <p className="mt-3 text-sm text-ink-500">To stare projekty testowe. Nie musisz ich otwierać, żeby stworzyć własną gazetę.</p>
      <div className="mt-5 grid gap-5 md:grid-cols-2">{technical.map(card)}</div>
    </details>}
  </main>;
};
