import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { NewProjectModal } from '../projects/NewProjectModal';
import { ExportModal } from '../export/ExportModal';
import { X, CheckCircle2, AlertTriangle, Info, AlertCircle } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  isNewProjectOpen: boolean;
  isExportOpen: boolean;
  onOpenNewProject: () => void;
  onCloseNewProject: () => void;
  onCloseExport: () => void;
}

export const Layout: React.FC<LayoutProps> = ({ children, isNewProjectOpen, isExportOpen, onOpenNewProject, onCloseNewProject, onCloseExport }) => {
  const { toasts, removeToast } = useProject();

  return (
    <div className="min-h-screen bg-ink-950 text-ink-100 flex flex-col font-sans selection:bg-editorial-crimson selection:text-white">
      {/* Top Masthead Navbar */}
      <Navbar
        onOpenNewProject={onOpenNewProject}
      />

      {/* Body: Sidebar + Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-ink-950">
          {children}
        </main>
      </div>

      {/* Modals */}
      <NewProjectModal
        isOpen={isNewProjectOpen}
        onClose={onCloseNewProject}
      />

      <ExportModal
        isOpen={isExportOpen}
        onClose={onCloseExport}
      />

      {/* Toast Notifications */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-xl border shadow-2xl flex items-start gap-3 backdrop-blur-md transition-all transform animate-fade-in ${
              toast.type === 'success'
                ? 'bg-white border-emerald-200 text-ink-100'
                : toast.type === 'warning'
                ? 'bg-white border-amber-200 text-ink-100'
                : toast.type === 'error'
                ? 'bg-white border-red-200 text-ink-100'
                : 'bg-white border-ink-800 text-ink-100'
            }`}
          >
            {toast.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />}
            {toast.type === 'warning' && <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />}
            {toast.type === 'error' && <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />}
            {toast.type === 'info' && <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />}

            <div className="flex-1 text-xs">
              <p className="font-bold text-ink-100 tracking-wide">{toast.title}</p>
              {toast.message && <p className="text-ink-400 mt-0.5 leading-relaxed">{toast.message}</p>}
            </div>

            <button
              onClick={() => removeToast(toast.id)}
              className="text-ink-500 hover:text-ink-100 p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
