import { SceneGraph } from './sceneGraph';

export interface CopySlotPlan {
  element_ref: string;
  story_ref?: string;
  role: string;
  editorial_job: string;
  writing_instruction: string;
  source_words: number;
  target_words: number;
  target_lines: number;
  capacity_lines: number;
  fit_status: 'PASS' | 'SHORTEN' | 'EXPAND' | 'MANUAL';
  delta_words: number;
  recommendations: string[];
  source_characters?: number;
  min_words?: number;
  max_words?: number;
  target_characters?: number;
  columns?: number;
  width_mm?: number;
  height_mm?: number;
}

export interface FrameCopyFit {
  id?: string;
  element_ref: string;
  role: string;
  text: string;
  source_words: number;
  output_words: number;
  target_words: number;
  provider: string;
  needs_more_source: boolean;
  fit: {
    status: 'PASS' | 'FAIL';
    words: number;
    lines: number;
    capacity_lines: number;
    free_space_mm: number;
    overflow_mm: number;
    target_deviation_words: number;
    recommendations: string[];
    warnings?: string[];
  };
  warnings: string[];
}

export interface ArtDirectionPlan {
  architecture: string;
  page_thesis: string;
  hierarchy: string[];
  reading_path: string[];
  photo_strategy: string;
  copy_strategy: string;
  allowed_transgressions: string[];
  corpus_evidence: { sample_count?: number; archetype?: string; zone?: string; [key: string]: any };
  content_diagnosis: { stories?: number; photos?: number; source_words?: number; [key: string]: any };
  decision_trace: string[];
  copy_slots: CopySlotPlan[];
  confidence: number;
}

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
  visualReview?: { status?: string; score?: number; style_fidelity?: number; photo_headline_match?: number; photo_use?: number;
    dead_zones?: string[]; top_3_fixes?: string[]; category_mismatch?: string[];
    category_review?: { status: 'candidate_for_editor' | 'needs_revision'; target: number; editorial_approval_required: boolean } };
  styleReadiness?: { status: string; warnings: string[]; photo_story_count?: number; story_count?: number };
  /** Plain-language explanation: page morphology and the photo editor's choice. */
  layoutStory?: { morphology?: string; photoReason?: string; photoScore?: number; decisions: string[] };
  passHardGates: boolean;
  hardGatesReport: HardGatesReport;
  criticRationale: string;
  noveltyDistance: number; // 0.00 to 1.00 distance from corpus (anti-copying)
  tensionEnergyConsumed: number; // e.g. 7.5 / 15
  transgressionsCount: number;
  tags: string[];
  artDirection?: ArtDirectionPlan;
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
