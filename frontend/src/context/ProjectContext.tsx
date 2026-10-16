import { safeStorage } from '../safeStorage';
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Project } from '../types/project';
import { TitleDNA } from '../types/dna';
import { GenerationRun, Candidate } from '../types/generation';
import { TasteModelMetrics } from '../types/taste';
import { api } from '../api/client';

export type NavigationTab = 
  | 'projects'
  | 'dashboard' 
  | 'corpus' 
  | 'dna' 
  | 'generate' 
  | 'plan'
  | 'edition'
  | 'settings'
  | 'gallery' 
  | 'copy'
  | 'canvas' 
  | 'compare';

export interface ToastMessage {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message?: string;
}

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  activeTab: NavigationTab;
  dna: TitleDNA | null;
  currentRun: GenerationRun | null;
  selectedCandidate: Candidate | null;
  tasteMetrics: TasteModelMetrics | null;
  isLoading: boolean;
  toasts: ToastMessage[];
  setActiveTab: (tab: NavigationTab) => void;
  selectProject: (id: string) => Promise<void>;
  reloadProjects: () => Promise<void>;
  reloadDNA: () => Promise<void>;
  reloadTasteMetrics: () => Promise<void>;
  setSelectedCandidate: (candidate: Candidate | null) => void;
  setCurrentRun: (run: GenerationRun | null) => void;
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
  createProject: (data: Partial<Project>) => Promise<Project>;
  deleteProject: (id: string) => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState<NavigationTab>('dashboard');
  const [dna, setDna] = useState<TitleDNA | null>(null);
  const [currentRun, setCurrentRun] = useState<GenerationRun | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [tasteMetrics, setTasteMetrics] = useState<TasteModelMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const reloadProjects = useCallback(async () => {
    try {
      const list = await api.getProjects();
      setProjects(list);
      if (!activeProject && list.length > 0) {
        const savedId = safeStorage.get('layout_studio_active_proj_id');
        const match = list.find((p) => p.id === savedId);
        if (match) setActiveProject(match);
      }
    } catch (e) {
      console.error('Failed to load projects:', e);
      addToast({ type: 'error', title: 'ZECRO API niedostępne', message: e instanceof Error ? e.message : 'Sprawdź połączenie z usługą ZECRO API.' });
    }
  }, [activeProject, addToast]);

  const selectProject = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const p = await api.getProject(id);
      if (p) {
        setActiveProject(p);
        safeStorage.set('layout_studio_active_proj_id', id);
        const [loadedDna, loadedMetrics, runs] = await Promise.all([
          api.getTitleDNA(p.id),
          api.getTasteMetrics(p.id),
          api.getGenerationRuns(p.id),
        ]);
        setDna(loadedDna);
        setTasteMetrics(loadedMetrics);
        if (runs.length > 0) {
          setCurrentRun(runs[0]);
          if (runs[0].candidates.length > 0) {
            setSelectedCandidate(runs[0].candidates[0]);
          }
        } else {
          setCurrentRun(null);
          setSelectedCandidate(null);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reloadDNA = useCallback(async () => {
    if (!activeProject) return;
    try {
      const loaded = await api.getTitleDNA(activeProject.id);
      setDna(loaded);
    } catch (e) {
      console.error('Failed to load DNA:', e);
    }
  }, [activeProject]);

  const reloadTasteMetrics = useCallback(async () => {
    if (!activeProject) return;
    try {
      const metrics = await api.getTasteMetrics(activeProject.id);
      setTasteMetrics(metrics);
    } catch (e) {
      console.error('Failed to load taste metrics:', e);
    }
  }, [activeProject]);

  // Initial load
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        const list = await api.getProjects();
        setProjects(list);
        if (list.length > 0) {
          const savedId = safeStorage.get('layout_studio_active_proj_id');
          const current = list.find((p) => p.id === savedId);
          if (!current) return;
          setActiveProject(current);
          const [loadedDna, loadedMetrics, runs] = await Promise.all([
            api.getTitleDNA(current.id),
            api.getTasteMetrics(current.id),
            api.getGenerationRuns(current.id),
          ]);
          setDna(loadedDna);
          setTasteMetrics(loadedMetrics);
          if (runs.length > 0) {
            setCurrentRun(runs[0]);
            if (runs[0].candidates.length > 0) {
              setSelectedCandidate(runs[0].candidates[0]);
            }
          }
        }
      } catch (e) {
        console.error('Failed to initialize ZECRO:', e);
        addToast({ type: 'error', title: 'ZECRO API niedostępne', message: e instanceof Error ? e.message : 'Sprawdź połączenie z usługą ZECRO API.' });
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  const createProject = useCallback(async (data: Partial<Project>) => {
    const newProj = await api.createProject(data);
    await reloadProjects();
    await selectProject(newProj.id);
    addToast({
      type: 'success',
      title: 'Gazeta utworzona',
      message: `Gazeta „${newProj.name}” jest gotowa. Dodaj pierwszy artykuł, aby przygotować stronę.`,
    });
    return newProj;
  }, [reloadProjects, selectProject, addToast]);

  const deleteProject = useCallback(async (id: string) => {
    await api.deleteProject(id);
    const list = await api.getProjects();
    setProjects(list);
    if (activeProject?.id === id && list.length > 0) {
      await selectProject(list[0].id);
    }
    addToast({
      type: 'info',
      title: 'Gazeta usunięta',
      message: 'Gazeta i jej ustawienia zostały usunięte.',
    });
  }, [activeProject, selectProject, addToast]);

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        activeTab,
        dna,
        currentRun,
        selectedCandidate,
        tasteMetrics,
        isLoading,
        toasts,
        setActiveTab,
        selectProject,
        reloadProjects,
        reloadDNA,
        reloadTasteMetrics,
        setSelectedCandidate,
        setCurrentRun,
        addToast,
        removeToast,
        createProject,
        deleteProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};
