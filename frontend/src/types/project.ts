export type NewspaperFormat = 'broadsheet' | 'berliner' | 'tabloid' | 'compact' | 'custom';

export interface PageDimensions {
  widthMm: number;
  heightMm: number;
  columnsCount: number;
  gutterMm: number;
  marginTopMm: number;
  marginBottomMm: number;
  marginLeftMm: number;
  marginRightMm: number;
  bleedMm: number;
}

export type ProjectStatus = 'draft' | 'learning' | 'ready' | 'generating' | 'exporting';

export interface Project {
  id: string;
  name: string;
  slug: string;
  newspaperTitle: string;
  editionCode: string;
  format: NewspaperFormat;
  dimensions: PageDimensions;
  description: string;
  status: ProjectStatus;
  corpusCount: number;
  generationRunsCount: number;
  tasteSignalsCount: number;
  tasteModelWinRate: number; // 0.0 to 1.0 (e.g. 0.88)
  avgTimeToApproveSec: number;
  dnaVersion: number;
  createdAt: string;
  updatedAt: string;
  themeColor: string;
  accentFont: string;
}
