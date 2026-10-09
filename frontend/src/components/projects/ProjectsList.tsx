import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import {
  Plus,
  ArrowRight,
  Trash2,
  Layers,
  Sparkles,
  TrendingUp,
  Clock,
  BookOpen,
} from 'lucide-react';

interface ProjectsListProps {
  onOpenNewProject: () => void;
}

export const ProjectsList: React.FC<ProjectsListProps> = ({ onOpenNewProject }) => {
  const { projects, activeProject, selectProject, deleteProject, setActiveTab } = useProject();

  return (
    <div className="p-6 lg:p-10 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-ink-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] uppercase font-mono tracking-widest text-editorial-crimson font-bold">
              Tytuły i przestrzenie robocze
            </span>
          </div>
          <h1 className="text-3xl font-headline font-black text-ink-100 tracking-tight">
            Projekty redakcyjne
          </h1>
          <p className="text-sm text-ink-400 mt-1 max-w-2xl">
            Każdy tytuł ma własny korpus, DNA i model gustu dyrektora artystycznego. Pracuj nad wieloma wydaniami bez mieszania ich języka wizualnego.
          </p>
        </div>
        <Button
          variant="editorial"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={onOpenNewProject}
        >
          Nowy tytuł
        </Button>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((project) => {
          const isActive = project.id === activeProject?.id;
          return (
            <Card
              key={project.id}
              variant={isActive ? 'elevated' : 'default'}
              className={`flex flex-col justify-between relative group hover:border-ink-600 transition-all ${
                isActive ? 'border-editorial-crimson ring-1 ring-editorial-crimson/50' : ''
              }`}
            >
              {/* Top Accent Strip */}
              <div
                className="h-1.5 w-full rounded-t-xl absolute top-0 left-0"
                style={{ backgroundColor: project.themeColor }}
              />

              <div className="pt-2">
                {/* Status & Format */}
                <div className="flex items-center justify-between mb-3">
                  <Badge variant="outline" size="sm">
                    {project.format.toUpperCase()}
                  </Badge>
                  {isActive && (
                    <Badge variant="accent" size="sm">
                      Aktywne studio
                    </Badge>
                  )}
                </div>

                {/* Newspaper Title */}
                <h3 className="text-xl font-headline font-bold text-ink-100 mb-1 group-hover:text-editorial-ochre transition-colors">
                  {project.name}
                </h3>
                <p className="text-xs font-mono text-ink-400 mb-3 tracking-wider uppercase">
                  {project.newspaperTitle} • {project.editionCode}
                </p>

                <p className="text-xs text-ink-300 line-clamp-2 mb-5">
                  {project.description}
                </p>

                {/* Metrics Pill Grid */}
                <div className="grid grid-cols-2 gap-2 bg-ink-950/70 p-3 rounded-lg border border-ink-800/80 mb-5 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <Layers className="w-3.5 h-3.5 text-editorial-ochre" />
                    <div>
                      <span className="text-ink-400 block text-[10px] uppercase">DNA tytułu</span>
                      <strong className="text-ink-100">v{project.dnaVersion}</strong>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-3.5 h-3.5 text-ink-400" />
                    <div>
                      <span className="text-ink-400 block text-[10px] uppercase">Korpus</span>
                      <strong className="text-ink-100">{project.corpusCount} stron</strong>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-editorial-crimson" />
                    <div>
                      <span className="text-ink-400 block text-[10px] uppercase">Generacje</span>
                      <strong className="text-ink-100">{project.generationRunsCount} przeb.</strong>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                    <div>
                      <span className="text-ink-400 block text-[10px] uppercase">Zgodność gustu</span>
                      <strong className="text-emerald-300 font-bold">
                        {(project.tasteModelWinRate * 100).toFixed(0)}%
                      </strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-4 border-t border-ink-800">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-400 hover:text-red-300 hover:bg-red-950/40 p-2"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Usunąć projekt „${project.name}” wraz z jego modelami?`)) {
                      deleteProject(project.id);
                    }
                  }}
                  title="Usuń projekt"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>

                <div className="flex items-center gap-2">
                  <Button
                    variant={isActive ? 'editorial' : 'secondary'}
                    size="sm"
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                    onClick={async () => {
                      await selectProject(project.id);
                      setActiveTab('dashboard');
                    }}
                  >
                    {isActive ? 'Otwórz studio' : 'Przełącz projekt'}
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
