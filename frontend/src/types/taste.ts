import { ElementDelta } from './sceneGraph';

export interface PreferenceSignal {
  id: string;
  projectId: string;
  type: 'pairwise_choice' | 'manual_delta' | 'direct_favorite' | 'export_selected';
  candidateAId: string;
  candidateBId?: string;
  winnerCandidateId: string;
  userDeltaEdits?: ElementDelta[];
  feedbackNotes?: string;
  timestamp: string;
}

export interface TasteModelMetrics {
  modelVersion: string;
  lastTrainedAt: string;
  totalComparisons: number;
  preferenceWinRate: number; // e.g. 0.88 -> 88%
  avgTimeToApproveSec: number;
  featureWeights: {
    tensionTolerance: number;
    cutoutAffinity: number;
    whitespaceGenerosity: number;
    headlineDominance: number;
    asymmetryPreference: number;
  };
  learningHistory: {
    date: string;
    winRate: number;
    approvalsCount: number;
  }[];
}
