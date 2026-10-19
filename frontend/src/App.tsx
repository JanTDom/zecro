import React from 'react';
import { ProjectProvider, useProject } from './context/ProjectContext';
import { Layout } from './components/layout/Layout';
import { ProjectDashboard } from './components/dashboard/ProjectDashboard';
import { CorpusManager } from './components/corpus/CorpusManager';
import { DNAEditor } from './components/dna/DNAEditor';
import { GeneratePage } from './components/generate/GeneratePage';
import { CandidateGallery } from './components/gallery/CandidateGallery';
import { CopyStudio } from './components/copy/CopyStudio';
import { SceneGraphCanvas } from './components/canvas/SceneGraphCanvas';
import { ComparePage } from './components/compare/ComparePage';
import { ProjectsList } from './components/projects/ProjectsList';
import { AccessGate } from './components/auth/AccessGate';
import { IntegrationsSettings } from './components/settings/IntegrationsSettings';
import { PagePlanner } from './components/plan/PagePlanner';
import { EditionFlatplan } from './components/edition/EditionFlatplan';
import { SystemHelpAndFlow } from './components/help/SystemHelpAndFlow';

interface MainContentProps {
  onOpenNewProject: () => void;
  onOpenExport: () => void;
}

const MainContent: React.FC<MainContentProps> = ({ onOpenNewProject, onOpenExport }) => {
  const { activeTab } = useProject();

  let content: React.ReactNode;
  switch (activeTab) {
    case 'dashboard':
      content = <ProjectDashboard onOpenNewProject={onOpenNewProject} />;
      break;
    case 'help':
      content = <SystemHelpAndFlow />;
      break;
    case 'corpus':
      content = <CorpusManager />;
      break;
    case 'dna':
      content = <DNAEditor />;
      break;
    case 'plan':
      content = <PagePlanner />;
      break;
    case 'edition':
      content = <EditionFlatplan />;
      break;
    case 'settings':
      content = <IntegrationsSettings />;
      break;
    case 'generate':
      content = <GeneratePage />;
      break;
    case 'gallery':
      content = <CandidateGallery onOpenExport={onOpenExport} />;
      break;
    case 'copy':
      content = <CopyStudio />;
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
      content = <ProjectDashboard onOpenNewProject={onOpenNewProject} />;
      break;
  }
  return <>{content}</>;
};

export function App() {
  const [isNewProjectOpen, setIsNewProjectOpen] = React.useState(false);
  const [isExportOpen, setIsExportOpen] = React.useState(false);
  React.useEffect(() => {
    const open = () => setIsExportOpen(true);
    window.addEventListener('zecro-open-export', open);
    return () => window.removeEventListener('zecro-open-export', open);
  }, []);

  return (
    <AccessGate>
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
    </AccessGate>
  );
}

export default App;
