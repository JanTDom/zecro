import React from 'react';
import { ProjectProvider, useProject } from './context/ProjectContext';
import { Layout } from './components/layout/Layout';
import { ProjectDashboard } from './components/dashboard/ProjectDashboard';
import { CorpusManager } from './components/corpus/CorpusManager';
import { DNAEditor } from './components/dna/DNAEditor';
import { GeneratePage } from './components/generate/GeneratePage';
import { CandidateGallery } from './components/gallery/CandidateGallery';
import { SceneGraphCanvas } from './components/canvas/SceneGraphCanvas';
import { ComparePage } from './components/compare/ComparePage';
import { ProjectsList } from './components/projects/ProjectsList';

interface MainContentProps {
  onOpenNewProject: () => void;
  onOpenExport: () => void;
}

const MainContent: React.FC<MainContentProps> = ({ onOpenNewProject, onOpenExport }) => {
  const { activeTab } = useProject();

  let content: React.ReactNode;
  switch (activeTab) {
    case 'dashboard':
      content = <ProjectDashboard />;
      break;
    case 'corpus':
      content = <CorpusManager />;
      break;
    case 'dna':
      content = <DNAEditor />;
      break;
    case 'generate':
      content = <GeneratePage />;
      break;
    case 'gallery':
      content = <CandidateGallery onOpenExport={onOpenExport} />;
      break;
    case 'canvas':
      content = <SceneGraphCanvas />;
      break;
    case 'compare':
      content = <ComparePage />;
      break;
    case 'projects':
      content = <ProjectsList onOpenNewProject={onOpenNewProject} />;
      break;
    default:
      content = <ProjectDashboard />;
      break;
  }
  return <>{content}</>;
};

export function App() {
  const [isNewProjectOpen, setIsNewProjectOpen] = React.useState(false);
  const [isExportOpen, setIsExportOpen] = React.useState(false);

  return (
    <ProjectProvider>
      <Layout
        isNewProjectOpen={isNewProjectOpen}
        isExportOpen={isExportOpen}
        onOpenNewProject={() => setIsNewProjectOpen(true)}
        onCloseNewProject={() => setIsNewProjectOpen(false)}
        onCloseExport={() => setIsExportOpen(false)}
      >
        <MainContent
          onOpenNewProject={() => setIsNewProjectOpen(true)}
          onOpenExport={() => setIsExportOpen(true)}
        />
      </Layout>
    </ProjectProvider>
  );
}

export default App;
