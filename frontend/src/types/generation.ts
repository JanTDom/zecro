import { SceneGraph } from './sceneGraph';

export interface HardGatesReport {
  passed: boolean;
  collisionsFound: number;
  readabilityScore: number; // 0..100
  prepressOversetLines: number;
  hierarchyViolations: number;
  marginViolations: number;
  details: string[];
}

export interface Candidate {
  id: string;
  runId: string;
  candidateNumber: number;
  sceneGraph: SceneGraph;
  thumbnailSvg?: string;
  previewImageUrl?: string;
  criticScore: number; // 0.00 to 1.00 (e.g. 0.94)
  tasteScore: number; // 0.00 to 1.00 (predicted by TasteModel)
  passHardGates: boolean;
  hardGatesReport: HardGatesReport;
  criticRationale: string;
  noveltyDistance: number; // 0.00 to 1.00 distance from corpus (anti-copying)
  tensionEnergyConsumed: number; // e.g. 7.5 / 15
  transgressionsCount: number;
  tags: string[];
  isBookmarked?: boolean;
  createdAt: string;
}

export interface GenerationRun {
  id: string;
  projectId: string;
  timestamp: string;
  status: 'completed' | 'running' | 'failed';
  requestedCandidateCount: number;
  candidates: Candidate[];
  bestCandidateId: string;
  targetTension: number;
  noveltyMean: number;
  elapsedMs: number;
}
